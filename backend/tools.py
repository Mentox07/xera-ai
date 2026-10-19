import asyncio
import os
import json
import re
import shlex
import shutil
import httpx
from pathlib import Path
from . import config, standort

URL_PATTERN = re.compile(r'https?://[^\s<>"]+', re.IGNORECASE)

TOOL_TIMEOUT = 10

# Websuche (Stand 2026-10-01): DuckDuckGo, Qwant und Brave sperren CT 207
# (CAPTCHA bzw. "too many requests"), Google/Yahoo/Mojeek liefern. Vorher
# stand hier "google,duckduckgo,wikipedia,brave" — davon kam nur Google durch.
SUCHMASCHINEN = "google,yahoo,mojeek,wikipedia"
# SearXNGs Bot-Erkennung erwartet einen Proxy-Header; ohne ihn steht im Log
# "X-Forwarded-For nor X-Real-IP header is set!" und Anfragen werden gedrosselt.
_ABSENDER = os.getenv("SEARXNG_ABSENDER", "127.0.0.1")   # eigene Adresse, aus .env
SEARXNG_HEADER = {"X-Forwarded-For": _ABSENDER, "X-Real-IP": _ABSENDER}

ALLOWED_COMMANDS = {
    "uptime", "whoami", "hostname", "date", "uname",
    "df", "free", "top", "ps", "lsblk", "lscpu", "lsof",
    "cat", "head", "tail", "wc", "ls", "find", "grep", "file", "stat", "du",
    "ip", "ss", "ping", "dig", "nslookup", "traceroute", "curl",
    "nvidia-smi", "nvtop",
    "docker", "systemctl", "journalctl",
    "git",
}


HOMELAB_ONLY_TOOLS = {"shell_execute", "system_info", "knowledge_search", "ssh_execute", "docker_manage", "monitoring_query"}
MEMORY_DIR = Path("/opt/xera-ai/data/memory")

def _load_user_memory(user_id: str) -> dict:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    p = MEMORY_DIR / f"{user_id}.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}

def _save_user_memory(user_id: str, data: dict) -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    p = MEMORY_DIR / f"{user_id}.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2))

# ── Local tool execution (CLI platform) ────────────────────────────────────
LOCAL_TOOLS: set[str] = {"read_file", "list_files", "find_files", "git_execute", "write_file", "str_replace_file"}

_tool_local_pending: dict = {}
_tool_local_results: dict = {}


async def wait_for_local_tool(tool_id: str, timeout: float = 30.0) -> dict:
    import asyncio as _asyncio
    event = _asyncio.Event()
    _tool_local_pending[tool_id] = event
    try:
        await _asyncio.wait_for(_asyncio.shield(event.wait()), timeout=timeout)
        return _tool_local_results.pop(tool_id, {"success": False, "output": "Kein Ergebnis"})
    except _asyncio.TimeoutError:
        return {"success": False, "output": f"CLI hat nicht geantwortet (timeout {timeout}s)"}
    finally:
        _tool_local_pending.pop(tool_id, None)


def resolve_local_tool(tool_id: str, result: dict) -> bool:
    event = _tool_local_pending.get(tool_id)
    if not event:
        return False
    _tool_local_results[tool_id] = result
    event.set()
    return True


# SSH-Ziele des Homelabs aus der Standort-Datei (standort.py) — Adressen und Benutzer stehen
# seit 2026-10-19 nicht mehr im Quelltext. Ohne Datei gibt es keine Ziele.
SSH_ALLOWED_HOSTS = standort.ssh_ziele()
_SSH_TEXTE = standort.STANDORT.get("texte") or {}
_SSH_ZIELE_TEXT = (_SSH_TEXTE.get("ssh_ziele")
                   or ", ".join(f"{n} ({z.get('label', n)})" for n, z in SSH_ALLOWED_HOSTS.items())
                   or "none configured")
_SSH_ZIEL_AUSWAHL = _SSH_TEXTE.get("ssh_ziel_auswahl") or ", ".join(repr(n) for n in SSH_ALLOWED_HOSTS)

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "shell_execute",
            "description": "Execute a read-only shell command on the Homelab GPU server. Use for system info, diagnostics, logs, network checks. Destructive commands are blocked.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute (e.g. 'df -h', 'nvidia-smi', 'docker ps')"
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file on the server. Use for configs, logs, scripts, markdown files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute file path (e.g. '/etc/hostname', '/opt/xera-ai/backend/config.py')"
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Max lines to read (default: 200). Use for large files.",
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file on the server. Creates the file if it doesn't exist. Use for creating scripts, configs, notes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute file path to write to"
                    },
                    "content": {
                        "type": "string",
                        "description": "The full content to write to the file"
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a given path. Returns names, sizes and types.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path to list (e.g. '/opt/xera-ai/', '/home/')"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_files",
            "description": "Search for files matching a pattern. Uses 'find' under the hood.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Root directory to search from"
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Filename pattern (e.g. '*.py', '*.log', 'docker-compose*')"
                    }
                },
                "required": ["directory", "pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "system_info",
            "description": "Get a comprehensive system overview: CPU, RAM, disk, GPU, uptime, network. No arguments needed.",
            "parameters": {
                "type": "object",
                "properties": {},
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "knowledge_search",
            "description": "Search the Homelab knowledge base (Obsidian documentation). Use this for questions about the Homelab infrastructure, network, containers, VMs, setup guides, configs, VLANs, Proxmox, Router, Switch, Monitoring, Discord, VPN, KI-Agent and more.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query in natural language (e.g. 'Wie ist das VLAN Setup?', 'Proxmox Node Konfiguration', 'Router Firewall Regeln')"
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Number of results (default: 5, max: 10)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information. Returns titles, URLs and snippets from Google, DuckDuckGo and Brave.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Delete a file or empty directory. Use when asked to remove files. Non-empty directories are not deleted for safety.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the file or empty directory to delete"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Create a directory (including parent directories if needed).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path of the directory to create"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_file",
            "description": "Move or rename a file or directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "Absolute path of the source file/directory"
                    },
                    "destination": {
                        "type": "string",
                        "description": "Absolute path of the destination"
                    }
                },
                "required": ["source", "destination"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "copy_file",
            "description": "Copy a file to a new location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "Absolute path of the source file"
                    },
                    "destination": {
                        "type": "string",
                        "description": "Absolute path of the destination"
                    }
                },
                "required": ["source", "destination"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ssh_execute",
            "description": f"Execute a command on a remote Homelab server via SSH. Available targets: {_SSH_ZIELE_TEXT}. Use for remote diagnostics, config checks, service status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": f"Target server: {_SSH_ZIEL_AUSWAHL}"
                    },
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute on the remote server"
                    }
                },
                "required": ["target", "command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "docker_manage",
            "description": "Manage Docker containers on a remote Homelab server. Actions: list (show all containers), logs (read container logs), start/stop/restart a container.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Target server: 'node1', 'node2', 'node3', or 'searxng' (CT 207)"
                    },
                    "action": {
                        "type": "string",
                        "description": "Action: 'list', 'logs', 'start', 'stop', 'restart'"
                    },
                    "container": {
                        "type": "string",
                        "description": "Container name (required for logs/start/stop/restart)"
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Number of log lines (default: 50, only for 'logs' action)"
                    }
                },
                "required": ["target", "action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "monitoring_query",
            "description": "Query Homelab monitoring data from Prometheus and Grafana. Use 'status' for a quick overview of all monitored systems, 'query' for custom Prometheus PromQL queries, 'dashboards' to list available Grafana dashboards.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Action: 'status' (system overview), 'query' (custom PromQL), 'dashboards' (list Grafana dashboards)"
                    },
                    "query": {
                        "type": "string",
                        "description": "PromQL query (only for action 'query'). Examples: 'up', 'node_memory_MemAvailable_bytes', '100 - avg by(instance)(rate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100'"
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_document",
            "description": "Create a file and return a download link. Use 'pdf'/'docx' for formatted reports (Markdown content). Use 'xlsx' for tables: one row per line, cells separated by | (Markdown tables work, the |---| line is skipped); first row = header; start a new sheet with a line '## Sheet name'. Header styling, column widths, wrapping and number formats are applied automatically — no post-processing needed. Use code types for scripts: 'py', 'sh', 'js', 'ts', 'html', 'css', 'json', 'yaml', 'md', 'sql', 'ps1', 'txt' etc. ALWAYS use this after writing any script so the user has a download link.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_type": {
                        "type": "string",
                        "description": "File type: 'pdf', 'docx', 'xlsx' for documents; or code extensions: 'py', 'sh', 'js', 'ts', 'html', 'css', 'json', 'yaml', 'md', 'sql', 'ps1', 'txt', 'go', 'rs', 'java', 'toml', 'conf'"
                    },
                    "content": {
                        "type": "string",
                        "description": "COMPLETE file content — never truncate. For code files: the full script without any omissions."
                    },
                    "filename": {
                        "type": "string",
                        "description": "Output filename without extension (e.g. 'server', 'deploy_script', 'bericht')"
                    },
                    "theme": {
                        "type": "string",
                        "description": "Color theme: built-in names (purple, blue, green, dark, warm, minimal) OR any color name (rot, gelb, orange, pink, türkis, indigo, gold, silber) OR any hex code (#ff6600). Default: purple."
                    },
                    "layout": {
                        "type": "string",
                        "enum": ["compact", "normal", "spacious"],
                        "description": "Layout density. compact=small font/tight spacing fits more content. normal=default. spacious=large font/wide spacing easier to read."
                    },
                    "show_header": {
                        "type": "boolean",
                        "description": "Show Xera AI header and footer bar on each page. Default: true. Set false for clean documents without branding."
                    },
                    "cover_page": {
                        "type": "boolean",
                        "description": "Add a dedicated cover/title page before the content. Only for PDF. Default: false."
                    },
                    "toc": {
                        "type": "boolean",
                        "description": "Insert an automatically generated Table of Contents page (with real page numbers) right after the cover page, listing all ## and ### headings. Only for PDF. Use for longer/structured documents (reports, scientific papers, guides with many sections) or whenever the user asks for 'Inhaltsverzeichnis' / 'table of contents'. Default: false."
                    },
                    "header_left": {
                        "type": "string",
                        "description": "Text shown on the LEFT side of the PDF header (e.g. company name, project name). Default: 'Xera AI'."
                    },
                    "header_right": {
                        "type": "string",
                        "description": "Text shown on the RIGHT side of the PDF header (e.g. website, department). Default: 'xera-app.com'."
                    }
                },
                "required": ["doc_type", "content", "filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "describe_image",
            "description": "Analyse an image using a vision model. The image must be provided as a base64-encoded data URL. Returns a text description of what the image shows.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image": {
                        "type": "string",
                        "description": "Base64-encoded image data URL (e.g. data:image/png;base64,...)"
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Question or instruction about the image (default: 'Describe this image in detail.')"
                    }
                },
                "required": ["image"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_document",
            "description": "Read and extract text content from an uploaded document (PDF, Word, Excel, PowerPoint, CSV, HTML, Markdown, etc.). Pass the filename exactly as the user provided it or as it appears in the conversation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Filename of the document to read (e.g. 'report.pdf', 'data.xlsx')"
                    }
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delegate_to_agent",
            "description": "Delegate a subtask to a specialized agent. Use when the task requires expertise outside your own specialization, or to parallelize research and analysis.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "enum": [
                            "code", "devops", "proxmox", "monitoring", "knowledge",
                            "research", "security", "network", "docker", "log_analysis",
                            "documentation", "database", "backup", "incident_response",
                            "home_automation", "finance", "content", "discord", "email", "calendar",
                            "document_reader", "document_write",
                            "file_reader", "file_writer", "dir_navigator", "shell_executor",
                            "file_editor", "web_fetcher", "python_repl", "git_agent",
                            "memory_store", "rag_agent", "agents_loop", "cli_master",
                        ],
                        "description": "ID of the target specialist agent"
                    },
                    "task": {
                        "type": "string",
                        "description": "Precise description of what the sub-agent should accomplish"
                    },
                    "context": {
                        "type": "string",
                        "description": "Optional: relevant background context for the sub-agent"
                    }
                },
                "required": ["agent_id", "task"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch the text content of a specific URL. Returns cleaned body text (no HTML tags). Use for reading documentation, GitHub READMEs, API docs, or any user-specified URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Full URL to fetch (must start with http:// or https://)"
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Max characters to return (default: 3000, max: 8000)"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "str_replace_file",
            "description": "Precisely edit a file by replacing an exact string. Safer than write_file — only changes the specified region. Fails if old_string appears 0 or 2+ times.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute file path to edit"
                    },
                    "old_string": {
                        "type": "string",
                        "description": "Exact text to find and replace (must be unique in the file)"
                    },
                    "new_string": {
                        "type": "string",
                        "description": "Replacement text"
                    }
                },
                "required": ["path", "old_string", "new_string"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "python_exec",
            "description": "Execute Python 3 code and return stdout/stderr. Safe sandbox: no os/subprocess/network access. Use for calculations, data processing, algorithm testing, regex, JSON parsing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python 3 code to execute"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Execution timeout in seconds (default: 10, max: 30)"
                    }
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_execute",
            "description": "Execute a git command in a specified directory. Use for git status, diff, log, commit, branch operations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Git subcommand and args (without the 'git' prefix, e.g. 'status', 'log --oneline -10', 'diff HEAD')"
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory for the git command (default: /tmp)"
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "memory_save",
            "description": "Save a key-value pair to persistent user memory. Use to remember user preferences, project names, settings across sessions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Memory key (e.g. 'user.name', 'preference.language', 'project.current')"
                    },
                    "value": {
                        "type": "string",
                        "description": "Value to store (max 200 characters)"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "User identifier for namespacing (auto-filled by system)"
                    }
                },
                "required": ["key", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "memory_load",
            "description": "Load from persistent user memory. Omit key to get all stored memories.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Memory key to load (omit to load all)"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "User identifier for namespacing (auto-filled by system)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "memory_delete",
            "description": "Delete a specific key from persistent user memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Memory key to delete"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "User identifier for namespacing (auto-filled by system)"
                    }
                },
                "required": ["key"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rag_search",
            "description": "Search the general knowledge base (personal notes, tutorials, school docs). Excludes Homelab infrastructure docs. Use for finding notes, guides, concept explanations from the personal Obsidian vault.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query in natural language"
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Number of results (default: 5, max: 10)"
                    }
                },
                "required": ["query"]
            }
        }
    },
]

def get_tools_for_mode(mode: str) -> list[dict]:
    if mode == "homelab":
        return TOOLS_SCHEMA
    return [t for t in TOOLS_SCHEMA if t["function"]["name"] not in HOMELAB_ONLY_TOOLS]


def get_tools_for_agent(allowed_names: set[str]) -> list[dict]:
    """Return tool schemas filtered to only the names an agent is allowed to use."""
    return [t for t in TOOLS_SCHEMA if t["function"]["name"] in allowed_names]


import contextvars as _cv

# Pro Frage der neuen Oberfläche gesetzt (vermittler.py): {"seiten": 3, "suchen": 4}.
# Ein dict, damit Agents in eigenen Tasks dasselbe Budget aufbrauchen.
RECHERCHE_BUDGET: _cv.ContextVar = _cv.ContextVar("recherche_budget", default=None)

# llama-server-Slot für Agent-Aufrufe (agents/base.py _call_llm); None = automatisch.
LLAMA_SLOT: _cv.ContextVar = _cv.ContextVar("llama_slot", default=None)

# Web-Sandkasten (seit 2026-10-16, siehe arbeitsbereich.py): {"user_id",
# "session_id", "admin"} für Anfragen aus dem Web ausser dem Homelab-Bereich,
# sonst None (Homelab, CLI, interne Aufgaben). Gesetzt in main.py pro Anfrage.
SANDBOX: _cv.ContextVar = _cv.ContextVar("xera_sandbox", default=None)


async def _dokument_im_arbeitsordner(filename: str) -> dict | None:
    """read_document auf eine Datei im Arbeitsordner dieses Gesprächs (seit
    2026-10-17): Excel aus create_document, Code-Dateien, Uploads unter ihrem
    Namen ohne Präfix. Vorher „nicht gefunden“ — Szenario S3: der Agent suchte
    mit find_files/list_files weiter. Nur der eigene Ordner, keine fremden Dateien."""
    sb = SANDBOX.get()
    if sb is None:
        return None
    from . import arbeitsbereich
    erg = await arbeitsbereich.ausfuehren("read_file", {"path": filename}, sb)
    return erg if erg.get("success") else None


def _budget_seiten(wunsch: int) -> int:
    b = RECHERCHE_BUDGET.get()
    if b is None:
        return wunsch
    n = max(0, min(wunsch, b["seiten"]))
    b["seiten"] -= n
    return n


import time as _time

_SUCH_CACHE: dict = {}
_SEITEN_CACHE: dict = {}
_CACHE_SEK = 3600


def _aus_cache(cache: dict, schluessel: str):
    eintrag = cache.get(schluessel)
    if eintrag and _time.time() - eintrag[0] < _CACHE_SEK:
        return eintrag[1]
    return None


_WEG = re.compile(r"<(head|script|style|noscript|svg|nav|header|footer|aside|form|template|iframe)\b[^>]*>.*?</\1\s*>", re.S | re.I)


async def _sicher_holen(url: str, timeout: float = 8.0, intern_erlaubt: bool = False) -> httpx.Response:
    """GET mit Prüfung auf Adressen im eigenen Netz — auch für jede
    Weiterleitung (seit 2026-10-16). Vorher folgten alle Abrufe Weiterleitungen
    blind, und web_search lud URLs aus der Suchanfrage ohne jede Prüfung: ein
    Agent hätte so http://127.0.0.1:8000/api/internal/… abrufen können."""
    from urllib.parse import urljoin
    from .permissions import _ist_interne_adresse
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        for _ in range(6):
            if not intern_erlaubt and _ist_interne_adresse(url):
                raise ValueError(f"Adresse im internen Netz nicht erlaubt: {url}")
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; XeraAI/1.0)"})
            ziel = resp.headers.get("location")
            if resp.is_redirect and ziel:
                url = urljoin(str(resp.url), ziel)
                continue
            return resp
    raise ValueError("zu viele Weiterleitungen")


async def _seitentext(url: str, max_chars: int = 15000, intern_erlaubt: bool = False) -> str:
    """Lesbarer Fliesstext einer Seite (leer bei Fehler oder Nicht-HTML)."""
    import html as _html
    try:
        resp = await _sicher_holen(url, 8.0, intern_erlaubt)
        if "html" not in resp.headers.get("content-type", ""):
            return ""
        roh = resp.text[:600000]
        roh = re.sub(r"<!--.*?-->", " ", roh, flags=re.S)
        roh = _WEG.sub(" ", roh)
        roh = re.sub(r"<(br|/p|/div|/li|/h[1-6]|/tr)\b[^>]*>", ". ", roh, flags=re.I)
        roh = re.sub(r"<[^>]+>", " ", roh)
        text = _html.unescape(roh)
        text = re.sub(r"\s*\.\s*(\.\s*)+", ". ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars]
    except Exception:
        return ""


async def _seite_gecacht(url: str) -> str:
    text = _aus_cache(_SEITEN_CACHE, url)
    if text is None:
        text = await _seitentext(url, max_chars=15000)
        _SEITEN_CACHE[url] = (_time.time(), text)
        if len(_SEITEN_CACHE) > 500:
            for k in sorted(_SEITEN_CACHE, key=lambda k: _SEITEN_CACHE[k][0])[:100]:
                _SEITEN_CACHE.pop(k, None)
    return text


def _woerter(text: str) -> list[str]:
    # Grobe Stammform: die ersten 6 Buchstaben ("Lizenzmodell" ~ "Lizenzen")
    return [w[:6] for w in re.findall(r"[0-9a-zäöüß][0-9a-zäöüß.\-]{2,}", text.lower())]


def _absaetze(text: str, laenge: int = 550) -> list[str]:
    saetze = re.split(r"(?<=[.!?])\s+", text)
    teile, aktuell = [], ""
    for satz in saetze:
        if aktuell and len(aktuell) + len(satz) > laenge:
            teile.append(aktuell)
            aktuell = ""
        aktuell = (aktuell + " " + satz).strip()
    if aktuell:
        teile.append(aktuell)
    # JSON-LD, Code, Menüleisten: viele Klammern/Anführungszeichen → kein Fliesstext
    return [t[:450] for t in teile
            if len(t) > 80 and (t.count("{") + t.count('"') + t.count("|") + t.count("<")) < 8]


def _bewertung(frage: set[str], absatz: str) -> float:
    w = _woerter(absatz)
    if not w:
        return 0.0
    vielfalt = len(frage & set(w))           # wie viele Suchbegriffe vorkommen
    dichte = sum(1 for x in w if x in frage) / (len(w) ** 0.5)
    zahlen = 0.3 if re.search(r"\d", absatz) else 0.0   # Versionen, Preise, Daten
    return vielfalt * 2 + dichte + zahlen


async def _suche_kompakt(query: str) -> dict:
    schluessel = " ".join(query.lower().split())
    treffer_cache = _aus_cache(_SUCH_CACHE, schluessel)
    if treffer_cache is not None:
        return {"success": True, "output": treffer_cache}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{config.SEARXNG_URL}/search",
            params={"q": query, "format": "json", "engines": SUCHMASCHINEN},
            headers=SEARXNG_HEADER,
        )
        resp.raise_for_status()
        ergebnisse = resp.json().get("results", [])[:6]
    if not ergebnisse:
        return {"success": True, "output": "Keine Ergebnisse gefunden."}

    urls = [r.get("url", "") for r in ergebnisse[:3] if r.get("url", "").startswith("http")]
    urls = urls[:_budget_seiten(len(urls))]
    texte = await asyncio.gather(*[_seite_gecacht(u) for u in urls], return_exceptions=True)
    nummer = {r.get("url", ""): i for i, r in enumerate(ergebnisse, 1)}
    frage = set(_woerter(query))
    kandidaten = []
    for url, text in zip(urls, texte):
        if isinstance(text, str) and len(text) > 200:
            for absatz in _absaetze(text):
                kandidaten.append((_bewertung(frage, absatz), nummer.get(url, 0), absatz))
    kandidaten.sort(key=lambda k: -k[0])
    auswahl, je_quelle = [], {}
    for punkte, nr, absatz in kandidaten:
        if punkte <= 0 or je_quelle.get(nr, 0) >= 3:
            continue
        je_quelle[nr] = je_quelle.get(nr, 0) + 1
        auswahl.append((nr, absatz))
        if len(auswahl) >= 5:
            break

    zeilen = [f"[{i}] {r.get('title', '')} — {r.get('url', '')}\n    {r.get('content', '')[:160]}"
              for i, r in enumerate(ergebnisse, 1)]
    ausgabe = "Treffer:\n" + "\n".join(zeilen)
    if auswahl:
        ausgabe += "\n\nRelevante Auszüge aus den besten Seiten (Quelle in [ ]):\n" + "\n\n".join(
            f"[{nr}] {absatz}" for nr, absatz in auswahl)
    _SUCH_CACHE[schluessel] = (_time.time(), ausgabe)
    return {"success": True, "output": ausgabe}


async def _fetch_page_text(url: str, max_chars: int = 3000, intern_erlaubt: bool = False) -> str:
    """Fetch a URL and return cleaned body text. Returns empty string on any failure."""
    try:
        resp = await _sicher_holen(url, 8.0, intern_erlaubt)
        if "html" not in resp.headers.get("content-type", ""):
            return ""
        body = resp.text[:12000]
        body = re.sub(r'<script[^>]*>.*?</script>', '', body, flags=re.DOTALL | re.IGNORECASE)
        body = re.sub(r'<style[^>]*>.*?</style>', '', body, flags=re.DOTALL | re.IGNORECASE)
        body = re.sub(r'<[^>]+>', ' ', body)
        body = re.sub(r'\s+', ' ', body).strip()
        return body[:max_chars]
    except Exception:
        return ""


async def _run_cmd(cmd: str) -> str:
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=TOOL_TIMEOUT)
    except asyncio.TimeoutError:
        proc.kill()
        return f"[TIMEOUT after {TOOL_TIMEOUT}s]"
    out = stdout.decode(errors="replace").strip()
    err = stderr.decode(errors="replace").strip()
    if err and not out:
        return err
    if err:
        return f"{out}\n\n[stderr]: {err}"
    return out or "[no output]"


async def execute_tool(name: str, args: dict) -> dict:
    try:
        sb = SANDBOX.get()
        if sb is not None:
            from . import arbeitsbereich as _ab
            if name in _ab.gesperrte_werkzeuge(sb):
                return {"success": False, "output": f"Werkzeug '{name}' gibt es nur im Homelab-Bereich."}
            if name in _ab.SANDBOX_WERKZEUGE:
                return await _ab.ausfuehren(name, args, sb)
            if name.startswith("memory_"):
                # Vorher bestimmte das Modell die user_id selbst — und konnte
                # so die Erinnerungen anderer Nutzer lesen.
                args = {**args, "user_id": sb["user_id"]}
            if name == "read_document":
                args = {**args, "_exakt": True}
            if name == "describe_image" and not str(args.get("image", "")).startswith("data:"):
                # llama-server lädt http(s)-Bilder selbst herunter — im Web nur
                # eingebettete Bilder, keine Adressen (SSRF vom GPU-Server aus).
                return {"success": False, "output": "Nur hochgeladene Bilder (data:-URI), keine Adressen."}

        if name == "shell_execute":
            cmd = args.get("command", "").strip()
            if not cmd:
                return {"success": False, "output": "Empty command"}
            base = cmd.split()[0].split("/")[-1]
            if base not in ALLOWED_COMMANDS:
                return {"success": False, "output": f"Command '{base}' not in allowlist"}
            output = await _run_cmd(cmd)
            return {"success": True, "output": output}

        elif name == "read_file":
            path = args.get("path", "")
            max_lines = args.get("lines", 600)
            p = Path(path)
            if not p.exists():
                return {"success": False, "output": f"File not found: {path}"}
            if not p.is_file():
                return {"success": False, "output": f"Not a file: {path}"}
            try:
                text = p.read_text(errors="replace")
                lines = text.splitlines()
                if len(lines) > max_lines:
                    text = "\n".join(lines[:max_lines]) + f"\n\n[... truncated, {len(lines)} lines total]"
                return {"success": True, "output": text}
            except PermissionError:
                return {"success": False, "output": f"Permission denied: {path}"}

        elif name == "write_file":
            path = args.get("path", "").strip()
            content = args.get("content", "")
            if not path:
                return {"success": False, "output": "Kein Pfad angegeben"}
            p = Path(path)
            if p.is_dir():
                return {"success": False, "output": f"Pfad ist ein Verzeichnis: {path}"}
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return {"success": True, "output": f"Written {len(content)} bytes to {path}"}

        elif name == "list_files":
            path = args.get("path", ".")
            p = Path(path)
            if not p.exists():
                return {"success": False, "output": f"Path not found: {path}"}
            if not p.is_dir():
                return {"success": False, "output": f"Not a directory: {path}"}
            entries = []
            for item in sorted(p.iterdir()):
                kind = "dir" if item.is_dir() else "file"
                size = item.stat().st_size if item.is_file() else 0
                entries.append(f"{'d' if kind == 'dir' else '-'} {size:>10}  {item.name}")
            return {"success": True, "output": "\n".join(entries) or "[empty directory]"}

        elif name == "find_files":
            directory = args.get("directory", ".")
            pattern = args.get("pattern", "*")
            output = await _run_cmd(f"find {shlex.quote(directory)} -maxdepth 5 -name {shlex.quote(pattern)} -type f 2>/dev/null | head -50")
            return {"success": True, "output": output}

        elif name == "system_info":
            parts = []
            parts.append("=== SYSTEM ===")
            parts.append(await _run_cmd("uname -a"))
            parts.append(await _run_cmd("uptime -p"))
            parts.append("\n=== CPU ===")
            parts.append(await _run_cmd("lscpu | grep -E 'Model name|CPU\\(s\\)|Thread'"))
            parts.append("\n=== RAM ===")
            parts.append(await _run_cmd("free -h"))
            parts.append("\n=== DISK ===")
            parts.append(await _run_cmd("df -h / /home 2>/dev/null"))
            parts.append("\n=== GPU ===")
            gpu = await _run_cmd("nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu --format=csv,noheader 2>/dev/null")
            parts.append(gpu if "command not found" not in gpu.lower() else "[no GPU detected]")
            parts.append("\n=== NETWORK ===")
            parts.append(await _run_cmd("ip -br addr | grep -v lo"))
            return {"success": True, "output": "\n".join(parts)}

        elif name == "knowledge_search":
            from .rag import search as rag_search
            query = args.get("query", "")
            n = min(args.get("n_results", 5), 10)
            hits = rag_search(query, n_results=n)
            if not hits:
                return {"success": False, "output": "Knowledge base is empty. Run /api/rag/ingest first."}
            parts = []
            for i, h in enumerate(hits, 1):
                parts.append(f"[{i}] {h['path']}\n{h['text']}")
            return {"success": True, "output": "\n\n---\n\n".join(parts)}

        elif name == "web_search":
            query = args.get("query", "")
            if not query:
                return {"success": False, "output": "Empty query"}
            _b = RECHERCHE_BUDGET.get()
            if _b is not None:
                if _b["suchen"] <= 0:
                    return {"success": False, "output": "Suchbudget für diese Frage aufgebraucht (höchstens 4 Suchen). Antworte jetzt mit dem, was du hast; der Nutzer kann nachfragen."}
                _b["suchen"] -= 1
            found_urls = URL_PATTERN.findall(query)
            if found_urls:
                parts = []
                for url in found_urls[:3]:
                    try:
                        resp = await _sicher_holen(url, 15.0)
                        resp.raise_for_status()
                        ct = resp.headers.get("content-type", "")
                        if "html" in ct:
                            body = resp.text[:8000]
                            body = re.sub(r'<script[^>]*>.*?</script>', '', body, flags=re.DOTALL | re.IGNORECASE)
                            body = re.sub(r'<style[^>]*>.*?</style>', '', body, flags=re.DOTALL | re.IGNORECASE)
                            body = re.sub(r'<[^>]+>', ' ', body)
                            body = re.sub(r'\s+', ' ', body).strip()[:4000]
                            parts.append(f"=== {url} ===\n{body}")
                        else:
                            parts.append(f"=== {url} ===\n[Content-Type: {ct}, {len(resp.content)} bytes]")
                    except Exception as e:
                        parts.append(f"=== {url} ===\n[Fehler: {str(e)}]")
                clean_query = URL_PATTERN.sub('', query).strip()
                if clean_query:
                    parts.append(f"\n--- Zusaetzliche Suche: '{clean_query}' ---")
                    try:
                        async with httpx.AsyncClient(timeout=15.0) as client:
                            resp = await client.get(f"{config.SEARXNG_URL}/search", params={"q": clean_query, "format": "json", "engines": SUCHMASCHINEN}, headers=SEARXNG_HEADER)
                            resp.raise_for_status()
                            data = resp.json()
                        for i, r in enumerate(data.get("results", [])[:5], 1):
                            parts.append(f"[{i}] {r.get('title','')} — {r.get('url','')}\n    {r.get('content','')[:200]}")
                    except Exception:
                        pass
                return {"success": True, "output": "\n\n".join(parts)}
            if RECHERCHE_BUDGET.get() is not None:
                try:
                    return await _suche_kompakt(query)
                except Exception as e:
                    return {"success": False, "output": f"Search error: {e}"}
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(
                        f"{config.SEARXNG_URL}/search",
                        params={"q": query, "format": "json", "engines": SUCHMASCHINEN},
                        headers=SEARXNG_HEADER,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                results = data.get("results", [])[:8]
                if not results:
                    return {"success": True, "output": "Keine Ergebnisse gefunden."}

                # Fetch full page content for top 3 results in parallel —
                # this gives the LLM real article text (3000 chars/page)
                # instead of 250-char meta-description snippets.
                top_urls = [r.get("url", "") for r in results[:3] if r.get("url", "").startswith("http")]
                top_urls = top_urls[:_budget_seiten(len(top_urls))]
                page_texts = await asyncio.gather(*[_fetch_page_text(u) for u in top_urls], return_exceptions=True)
                page_map = {
                    url: text for url, text in zip(top_urls, page_texts)
                    if isinstance(text, str) and len(text) > 200
                }

                parts = []
                source_lines = []
                for i, r in enumerate(results, 1):
                    title   = r.get("title", "")
                    url     = r.get("url", "")
                    snippet = r.get("content", "")[:400]
                    if url in page_map:
                        parts.append(
                            f"[{i}] {title}\n    {url}\n"
                            f"    Snippet: {snippet}\n"
                            f"    Volltext-Auszug:\n    {page_map[url]}"
                        )
                    else:
                        parts.append(f"[{i}] {title}\n    {url}\n    {snippet}")
                    source_lines.append(f"[{i}] {title} — {url}")

                fetched = sum(1 for u in top_urls if u in page_map)
                header = f"[{fetched}/{len(top_urls)} Seiten vollständig geladen]\n\n"
                output = header + "\n\n".join(parts) + "\n\n---\nQuellen:\n" + "\n".join(source_lines)
                return {"success": True, "output": output}
            except Exception as e:
                return {"success": False, "output": f"Search error: {str(e)}"}

        elif name == "delete_file":
            path = args.get("path", "")
            p = Path(path)
            if not p.exists():
                return {"success": False, "output": f"Not found: {path}"}
            if p.is_dir():
                if any(p.iterdir()):
                    return {"success": False, "output": f"Directory not empty: {path}"}
                p.rmdir()
            else:
                p.unlink()
            return {"success": True, "output": f"Deleted: {path}"}

        elif name == "create_directory":
            path = args.get("path", "")
            p = Path(path)
            if p.exists():
                return {"success": False, "output": f"Already exists: {path}"}
            p.mkdir(parents=True, exist_ok=True)
            return {"success": True, "output": f"Created directory: {path}"}

        elif name == "move_file":
            src = args.get("source", "")
            dst = args.get("destination", "")
            ps = Path(src)
            if not ps.exists():
                return {"success": False, "output": f"Source not found: {src}"}
            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            shutil.move(src, dst)
            return {"success": True, "output": f"Moved: {src} → {dst}"}

        elif name == "copy_file":
            src = args.get("source", "")
            dst = args.get("destination", "")
            ps = Path(src)
            if not ps.exists():
                return {"success": False, "output": f"Source not found: {src}"}
            if not ps.is_file():
                return {"success": False, "output": f"Not a file: {src}"}
            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            return {"success": True, "output": f"Copied: {src} → {dst}"}

        elif name == "ssh_execute":
            target = args.get("target", "").lower()
            cmd = args.get("command", "").strip()
            if target not in SSH_ALLOWED_HOSTS:
                return {"success": False, "output": f"Unknown target '{target}'. Available: {', '.join(SSH_ALLOWED_HOSTS.keys())}"}
            if not cmd:
                return {"success": False, "output": "Empty command"}
            host_info = SSH_ALLOWED_HOSTS[target]
            ssh_cmd = f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 {host_info['host']} {shlex.quote(cmd)}"
            output = await _run_cmd(ssh_cmd)
            return {"success": True, "output": f"[{host_info['label']}]\n{output}"}

        elif name == "docker_manage":
            target = args.get("target", "").lower()
            action = args.get("action", "").lower()
            container = args.get("container", "")
            lines = args.get("lines", 50)
            if target not in SSH_ALLOWED_HOSTS:
                return {"success": False, "output": f"Unknown target '{target}'. Available: {', '.join(SSH_ALLOWED_HOSTS.keys())}"}
            host = SSH_ALLOWED_HOSTS[target]["host"]
            label = SSH_ALLOWED_HOSTS[target]["label"]
            if action == "list":
                docker_cmd = 'docker ps -a --format "table {{.Names}}\\t{{.Status}}\\t{{.Ports}}\\t{{.Image}}"'
            elif action == "logs":
                if not container:
                    return {"success": False, "output": "Container name required for 'logs'"}
                docker_cmd = f"docker logs --tail {min(lines, 200)} {container}"
            elif action in ("start", "stop", "restart"):
                if not container:
                    return {"success": False, "output": f"Container name required for '{action}'"}
                docker_cmd = f"docker {action} {container}"
            else:
                return {"success": False, "output": f"Unknown action '{action}'. Use: list, logs, start, stop, restart"}
            ssh_cmd = f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 {host} '{docker_cmd}'"
            output = await _run_cmd(ssh_cmd)
            return {"success": True, "output": f"[{label}]\n{output}"}

        elif name == "monitoring_query":
            action = args.get("action", "").lower()
            if action == "status":
                parts = ["=== Homelab Monitoring Status ===\n"]
                async with httpx.AsyncClient(timeout=10.0) as client:
                    # Targets status
                    resp = await client.get(f"{config.PROMETHEUS_URL}/api/v1/targets")
                    resp.raise_for_status()
                    targets = resp.json()["data"]["activeTargets"]
                    parts.append("Scrape Targets:")
                    for t in targets:
                        parts.append(f"  {t['labels'].get('job','?'):25s} {t['labels'].get('instance',''):30s} {t['health']}")
                    # CPU per host
                    resp = await client.get(f"{config.PROMETHEUS_URL}/api/v1/query", params={"query": '100 - avg by(instance)(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100'})
                    resp.raise_for_status()
                    cpus = resp.json()["data"]["result"]
                    parts.append("\nCPU Usage:")
                    for r in cpus:
                        parts.append(f"  {r['metric']['instance']:30s} {float(r['value'][1]):.1f}%")
                    # Memory per host
                    resp = await client.get(f"{config.PROMETHEUS_URL}/api/v1/query", params={"query": '100 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100'})
                    resp.raise_for_status()
                    mems = resp.json()["data"]["result"]
                    parts.append("\nRAM Usage:")
                    for r in mems:
                        parts.append(f"  {r['metric']['instance']:30s} {float(r['value'][1]):.1f}%")
                    # Disk per host (root filesystem)
                    resp = await client.get(f"{config.PROMETHEUS_URL}/api/v1/query", params={"query": '100 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100'})
                    resp.raise_for_status()
                    disks = resp.json()["data"]["result"]
                    parts.append("\nDisk Usage (/):")
                    for r in disks:
                        parts.append(f"  {r['metric']['instance']:30s} {float(r['value'][1]):.1f}%")
                return {"success": True, "output": "\n".join(parts)}

            elif action == "query":
                query = args.get("query", "")
                if not query:
                    return {"success": False, "output": "PromQL query required for action 'query'"}
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(f"{config.PROMETHEUS_URL}/api/v1/query", params={"query": query})
                    resp.raise_for_status()
                    data = resp.json()
                if data["status"] != "success":
                    return {"success": False, "output": f"Prometheus error: {data.get('error', 'unknown')}"}
                results = data["data"]["result"]
                if not results:
                    return {"success": True, "output": "Keine Ergebnisse fuer diese Query."}
                parts = []
                for r in results:
                    labels = ", ".join(f"{k}={v}" for k, v in r["metric"].items() if k != "__name__")
                    name_label = r["metric"].get("__name__", "")
                    val = r["value"][1] if "value" in r else str(r.get("values", ""))
                    parts.append(f"{name_label}{{{labels}}} = {val}")
                return {"success": True, "output": "\n".join(parts[:30])}

            elif action == "dashboards":
                if not config.GRAFANA_TOKEN:
                    return {"success": False, "output": "Grafana Token nicht konfiguriert"}
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(
                        f"{config.GRAFANA_URL}/api/search?type=dash-db",
                        headers={"Authorization": f"Bearer {config.GRAFANA_TOKEN}"},
                    )
                    resp.raise_for_status()
                    dashboards = resp.json()
                if not dashboards:
                    return {"success": True, "output": "Keine Dashboards gefunden."}
                parts = ["Grafana Dashboards:\n"]
                for d in dashboards:
                    url = f"{config.GRAFANA_URL}/d/{d['uid']}"
                    parts.append(f"  {d['title']}\n    UID: {d['uid']}\n    URL: {url}")
                return {"success": True, "output": "\n".join(parts)}
            else:
                return {"success": False, "output": f"Unknown action '{action}'. Use: status, query, dashboards"}

        elif name == "create_document":
            from .docgen import create_document
            doc_type = args.get("doc_type") or args.get("document_type") or args.get("format", "pdf")
            filename = (args.get("filename") or args.get("file_name") or "dokument").rstrip(".pdf").rstrip(".docx").rstrip(".xlsx")
            show_hdr = args.get("show_header", True)
            if isinstance(show_hdr, str):
                show_hdr = show_hdr.lower() not in ("false", "0", "no", "nein")
            cover = args.get("cover_page", False)
            if isinstance(cover, str):
                cover = cover.lower() in ("true", "1", "yes", "ja")
            toc = args.get("toc", False)
            if isinstance(toc, str):
                toc = toc.lower() in ("true", "1", "yes", "ja")
            url = create_document(
                doc_type.lower(),
                args.get("content", ""),
                filename,
                theme=args.get("theme", "purple"),
                layout=args.get("layout", "normal"),
                show_header=show_hdr,
                cover_page=cover,
                toc=toc,
                header_left=args.get("header_left", "Xera AI"),
                header_right=args.get("header_right", "xera-app.com"),
            )
            return {"success": True, "output": f"Dokument erstellt: [Download]({url})"}

        elif name == "read_document":
            filename = args.get("filename", "").strip()
            if not filename:
                return {"success": False, "output": "Kein Dateiname angegeben."}
            from .docgen import DOCS_DIR
            from .docparse import parse_document
            if args.get("_exakt"):
                # Im Web nur der genaue gespeicherte Name (mit Zufallspräfix).
                # Die Suche unten fand sonst auch gleichnamige Dateien anderer
                # Nutzer ("*_lebenslauf.pdf").
                kandidat = (DOCS_DIR / Path(filename).name)
                if not kandidat.is_file():
                    im_ordner = await _dokument_im_arbeitsordner(filename)
                    if im_ordner:
                        return im_ordner
                    return {"success": False, "output": f"Dokument '{filename}' nicht gefunden. Nenne den Namen genau so, wie er im Gespräch steht."}
                result = parse_document(kandidat.name, kandidat.read_bytes())
                return {"success": True, "output": f"[Datei: {kandidat.name}]\n\n{result['content']}"}
            # Search in DOCS_DIR (with or without UUID prefix)
            candidates = list(DOCS_DIR.glob(f"*_{filename}")) + list(DOCS_DIR.glob(filename))
            if not candidates:
                # Try partial match by original name
                candidates = [f for f in DOCS_DIR.iterdir() if f.name.endswith(filename) or filename in f.name]
            if not candidates:
                im_ordner = await _dokument_im_arbeitsordner(filename)
                if im_ordner:
                    return im_ordner
                return {"success": False, "output": f"Dokument '{filename}' nicht gefunden. Stelle sicher dass die Datei hochgeladen wurde."}
            path = sorted(candidates, key=lambda f: f.stat().st_mtime, reverse=True)[0]
            data = path.read_bytes()
            result = parse_document(path.name, data)
            return {"success": True, "output": f"[Datei: {path.name}]\n\n{result['content']}"}

        elif name == "describe_image":
            image = args.get("image", "")
            prompt = args.get("prompt", "Describe this image in detail.")
            if not image:
                return {"success": False, "output": "No image provided"}
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{config.LLAMA_API_URL}/v1/chat/completions",
                    json={
                        "model": "xera-ai",
                        "messages": [{"role": "user", "content": [
                            {"type": "image_url", "image_url": {"url": image}},
                            {"type": "text", "text": prompt},
                        ]}],
                        "max_tokens": 512,
                        "stream": False,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            return {"success": True, "output": data["choices"][0]["message"]["content"]}

        elif name == "web_fetch":
            url = args.get("url", "").strip()
            max_chars = min(int(args.get("max_chars", 3000)), 8000)
            if not url.startswith(("http://", "https://")):
                return {"success": False, "output": "URL muss mit http:// oder https:// beginnen."}
            if _budget_seiten(1) == 0:
                return {"success": False, "output": "Seitenbudget für diese Frage aufgebraucht (höchstens 3 Seiten). Antworte jetzt mit dem, was du hast; der Nutzer kann nachfragen."}
            if RECHERCHE_BUDGET.get() is not None:
                text = (await _seite_gecacht(url))[:min(max_chars, 3000)]
            else:
                # Interne Adressen nur ausserhalb des Web-Sandkastens (Homelab,
                # nach Freigabe — classify_tool stuft sie als "admin" ein).
                text = await _fetch_page_text(url, max_chars=max_chars, intern_erlaubt=SANDBOX.get() is None)
            if not text:
                return {"success": False, "output": f"Konnte {url} nicht laden (leer, Fehler oder JS-only)."}
            return {"success": True, "output": f"[{url}]\n\n{text}"}

        elif name == "str_replace_file":
            path = args.get("path", "").strip()
            old_str = args.get("old_string", "")
            new_str = args.get("new_string", "")
            if not path or old_str == "":
                return {"success": False, "output": "path und old_string sind erforderlich."}
            p = Path(path)
            if not p.exists():
                return {"success": False, "output": f"Datei nicht gefunden: {path}"}
            content_file = p.read_text(encoding="utf-8", errors="replace")
            if old_str not in content_file:
                return {"success": False, "output": f"old_string nicht gefunden in {path}. Prüfe die genaue Schreibweise inkl. Leerzeichen."}
            count = content_file.count(old_str)
            if count > 1:
                return {"success": False, "output": f"old_string ist {count}x vorhanden — erweitere den Kontext damit er einzigartig ist."}
            new_content = content_file.replace(old_str, new_str, 1)
            p.write_text(new_content, encoding="utf-8")
            return {"success": True, "output": f"✓ Ersetzt in {path} ({len(old_str)} → {len(new_str)} Zeichen)."}

        elif name == "python_exec":
            import tempfile, os as _os
            code = args.get("code", "").strip()
            timeout = min(int(args.get("timeout", 10)), 30)
            if not code:
                return {"success": False, "output": "Kein Code angegeben."}
            BLOCKED_IMPORTS = ["import subprocess", "import shutil", "from subprocess", "__import__"]
            for b in BLOCKED_IMPORTS:
                if b in code:
                    return {"success": False, "output": f"Verboten: `{b}` — nur sichere Standard-Module erlaubt."}
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir="/tmp") as f:
                f.write(code)
                tmp_path = f.name
            try:
                proc = await asyncio.create_subprocess_exec(
                    "python3", tmp_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env={"PATH": "/usr/bin:/usr/local/bin", "HOME": "/tmp"},
                )
                try:
                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                except asyncio.TimeoutError:
                    proc.kill()
                    return {"success": False, "output": f"[TIMEOUT nach {timeout}s]"}
                out = stdout.decode(errors="replace").strip()
                err = stderr.decode(errors="replace").strip()
                if proc.returncode != 0:
                    combined = f"[stdout]\n{out}\n\n[stderr]\n{err}" if out else f"[stderr]\n{err}"
                    return {"success": False, "output": combined}
                result = out if out else "[kein output]"
                if err:
                    result += f"\n\n[warnings]\n{err}"
                return {"success": True, "output": result}
            finally:
                _os.unlink(tmp_path)

        elif name == "git_execute":
            git_cmd = args.get("command", "").strip()
            cwd = args.get("cwd", "/tmp")
            if not git_cmd:
                return {"success": False, "output": "Kein git-Befehl angegeben."}
            result = await _run_cmd(f"cd {shlex.quote(cwd)} && git {git_cmd} 2>&1")
            return {"success": True, "output": result}

        elif name == "memory_save":
            key = args.get("key", "").strip()
            value = str(args.get("value", "")).strip()[:200]
            uid = str(args.get("user_id", "default")).strip() or "default"
            if not key or not value:
                return {"success": False, "output": "key und value sind erforderlich."}
            data = _load_user_memory(uid)
            data[key] = value
            _save_user_memory(uid, data)
            return {"success": True, "output": f"Gespeichert: {key} = {value}"}

        elif name == "memory_load":
            key = args.get("key", "").strip()
            uid = str(args.get("user_id", "default")).strip() or "default"
            data = _load_user_memory(uid)
            if key:
                val = data.get(key)
                if val is None:
                    return {"success": True, "output": f"Kein Eintrag für '{key}' gefunden."}
                return {"success": True, "output": f"{key} = {val}"}
            if not data:
                return {"success": True, "output": "Keine gespeicherten Erinnerungen."}
            lines = [f"- {k}: {v}" for k, v in data.items()]
            return {"success": True, "output": "Gespeicherte Erinnerungen:\n" + "\n".join(lines)}

        elif name == "memory_delete":
            key = args.get("key", "").strip()
            uid = str(args.get("user_id", "default")).strip() or "default"
            if not key:
                return {"success": False, "output": "key ist erforderlich."}
            data = _load_user_memory(uid)
            if key not in data:
                return {"success": True, "output": f"Kein Eintrag '{key}' vorhanden."}
            del data[key]
            _save_user_memory(uid, data)
            return {"success": True, "output": f"Gelöscht: {key}"}

        elif name == "rag_search":
            from .rag import search as _rag_search
            query = args.get("query", "")
            n = min(args.get("n_results", 5), 10)
            hits = _rag_search(query, n_results=n * 2)
            if not hits:
                return {"success": False, "output": "Wissensbasis ist leer oder kein Ergebnis gefunden."}
            # Filter out homelab-specific docs (Homelab-HQ vault)
            general_hits = [h for h in hits if "Homelab-HQ" not in h.get("path", "") and "homelab" not in h.get("path", "").lower()]
            if not general_hits:
                general_hits = hits[:n]
            else:
                general_hits = general_hits[:n]
            parts = []
            for i, h in enumerate(general_hits, 1):
                score = h.get("score", 0)
                parts.append(f"[{i}] {h['path']} (Relevanz: {score:.0%})\n{h['text']}")
            return {"success": True, "output": "\n\n---\n\n".join(parts)}

        else:
            return {"success": False, "output": f"Unknown tool: {name}"}

    except Exception as e:
        return {"success": False, "output": f"Error: {str(e)}"}

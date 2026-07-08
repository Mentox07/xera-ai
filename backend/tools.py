import asyncio
import os
import json
import re
import shlex
import shutil
import httpx
from pathlib import Path
from . import config

URL_PATTERN = re.compile(r'https?://[^\s<>"]+', re.IGNORECASE)

TOOL_TIMEOUT = 10

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

SSH_ALLOWED_HOSTS = {
    "router":     {"host": "router@192.168.10.1",        "label": "Router (hl-rtr-core-01)"},
    "node1":      {"host": "root@192.168.20.10",          "label": "Proxmox Node 1"},
    "node2":      {"host": "root@192.168.20.11",          "label": "Proxmox Node 2"},
    "node3":      {"host": "root@192.168.20.12",          "label": "Proxmox Node 3"},
    "monitoring": {"host": "root@192.168.20.20",          "label": "Monitoring (CT 200)"},
    "automation": {"host": "root@192.168.20.21",          "label": "Automation (CT 201)", "password": "Aut0Hm!2026#Dsc"},
    "searxng":    {"host": "root@192.168.20.27",          "label": "SearXNG (CT 207)"},
    "gpu":        {"host": "romadmin@192.168.70.10",      "label": "GPU-Server (hl-srv-gpu-01)"},
}

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
            "description": "Execute a command on a remote Homelab server via SSH. Available targets: router (hl-rtr-core-01), node1/node2/node3 (Proxmox), gpu (GPU-Server), searxng (CT 207). Use for remote diagnostics, config checks, service status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Target server: 'router', 'node1', 'node2', 'node3', 'gpu', or 'searxng'"
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
            "description": "Create a file and return a download link. Use 'pdf'/'docx' for formatted reports (Markdown content). Use 'xlsx' for tables (rows with | separator). Use code types for scripts: 'py', 'sh', 'js', 'ts', 'html', 'css', 'json', 'yaml', 'md', 'sql', 'ps1', 'txt' etc. ALWAYS use this after writing any script so the user has a download link.",
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
]


def get_tools_for_mode(mode: str) -> list[dict]:
    if mode == "homelab":
        return TOOLS_SCHEMA
    return [t for t in TOOLS_SCHEMA if t["function"]["name"] not in HOMELAB_ONLY_TOOLS]


def get_tools_for_agent(allowed_names: set[str]) -> list[dict]:
    """Return tool schemas filtered to only the names an agent is allowed to use."""
    return [t for t in TOOLS_SCHEMA if t["function"]["name"] in allowed_names]


async def _fetch_page_text(url: str, max_chars: int = 3000) -> str:
    """Fetch a URL and return cleaned body text. Returns empty string on any failure."""
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; XeraAI/1.0)"})
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
            path = args.get("path", "")
            content = args.get("content", "")
            p = Path(path)
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
            found_urls = URL_PATTERN.findall(query)
            if found_urls:
                parts = []
                for url in found_urls[:3]:
                    try:
                        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; XeraAI/1.0)"})
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
                            resp = await client.get(f"{config.SEARXNG_URL}/search", params={"q": clean_query, "format": "json", "engines": "google,duckduckgo,wikipedia,brave"})
                            resp.raise_for_status()
                            data = resp.json()
                        for i, r in enumerate(data.get("results", [])[:5], 1):
                            parts.append(f"[{i}] {r.get('title','')} — {r.get('url','')}\n    {r.get('content','')[:200]}")
                    except Exception:
                        pass
                return {"success": True, "output": "\n\n".join(parts)}
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(
                        f"{config.SEARXNG_URL}/search",
                        params={"q": query, "format": "json", "engines": "google,duckduckgo,wikipedia,brave"},
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
            password = host_info.get("password")
            if password:
                ssh_cmd = f"sshpass -p {shlex.quote(password)} ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 {host_info['host']} {shlex.quote(cmd)}"
            else:
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
            # Search in DOCS_DIR (with or without UUID prefix)
            candidates = list(DOCS_DIR.glob(f"*_{filename}")) + list(DOCS_DIR.glob(filename))
            if not candidates:
                # Try partial match by original name
                candidates = [f for f in DOCS_DIR.iterdir() if f.name.endswith(filename) or filename in f.name]
            if not candidates:
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
                    f"{config.LLAMA_FAST_URL}/v1/chat/completions",
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

        else:
            return {"success": False, "output": f"Unknown tool: {name}"}

    except Exception as e:
        return {"success": False, "output": f"Error: {str(e)}"}

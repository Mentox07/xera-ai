import asyncio
import logging
from datetime import datetime, timezone
from . import database as db

logger = logging.getLogger(__name__)

RISK_LEVELS = {
    "read": {"auto": True, "label": "READ"},
    "write": {"auto": False, "label": "WRITE"},
    "admin": {"auto": False, "label": "ADMIN"},
    "blocked": {"auto": False, "label": "BLOCKED"},
}

READ_COMMANDS = {
    "uptime", "whoami", "hostname", "date", "uname",
    "df", "free", "top", "ps", "lsblk", "lscpu", "lsof",
    "cat", "head", "tail", "wc", "ls", "find", "grep", "file", "stat", "du",
    "ip", "ss", "ping", "dig", "nslookup", "traceroute",
    "nvidia-smi", "nvtop",
    "git",
}

WRITE_COMMANDS = {
    "docker", "systemctl", "journalctl", "curl",
}

BLOCKED_PATTERNS = [
    "rm ", "rm\t", "rmdir", "mkfs", "dd ", "shutdown", "reboot", "poweroff",
    "kill ", "killall", "pkill", "> /dev/", "chmod 777", ":(){ ", "fork",
    "mv /", "cp /dev/", "wget", "| bash", "| sh", "|bash", "|sh", "eval", "exec",
]


def classify_tool(name: str, args: dict) -> str:
    if name == "knowledge_search":
        return "read"
    if name == "system_info":
        return "read"
    if name == "read_file":
        return "read"
    if name == "list_files":
        return "read"
    if name == "find_files":
        return "read"
    if name == "web_search":
        return "read"
    if name == "monitoring_query":
        return "read"
    if name == "create_document":
        return "read"
    if name == "describe_image":
        return "read"
    if name == "write_file":
        return "write"
    if name == "delete_file":
        return "write"
    if name == "create_directory":
        return "write"
    if name == "move_file":
        return "write"
    if name == "copy_file":
        return "write"
    if name == "ssh_execute":
        return "admin"
    if name == "docker_manage":
        action = args.get("action", "")
        if action == "list":
            return "write"
        return "admin"
    if name == "shell_execute":
        return _classify_shell(args.get("command", ""))
    return "write"


def _classify_shell(cmd: str) -> str:
    stripped = cmd.strip()
    if not stripped:
        return "blocked"
    for pat in BLOCKED_PATTERNS:
        if pat in stripped:
            return "blocked"
    base = stripped.split()[0].split("/")[-1]
    if base in READ_COMMANDS:
        return "read"
    if base in WRITE_COMMANDS:
        return "write"
    return "blocked"


def needs_approval(level: str) -> bool:
    return not RISK_LEVELS.get(level, {}).get("auto", False)


def is_blocked(level: str) -> bool:
    return level == "blocked"


def level_label(level: str) -> str:
    return RISK_LEVELS.get(level, {}).get("label", level.upper())


_pending: dict[str, asyncio.Event] = {}
_results: dict[str, bool] = {}


def create_approval(action_id: str) -> asyncio.Event:
    event = asyncio.Event()
    _pending[action_id] = event
    return event


def resolve_approval(action_id: str, approved: bool):
    _results[action_id] = approved
    event = _pending.get(action_id)
    if event:
        event.set()


def get_approval_result(action_id: str) -> bool:
    return _results.pop(action_id, False)


def cleanup_approval(action_id: str):
    _pending.pop(action_id, None)
    _results.pop(action_id, None)


def log_action(user_id: str, session_id: int | None, tool: str, args: dict, level: str, approved: bool, result: str):
    try:
        db.log_audit(user_id, session_id, tool, str(args), level, approved, result[:500])
    except Exception as e:
        logger.warning(f"Audit log failed: {e}")

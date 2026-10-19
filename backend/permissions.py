import asyncio
import re
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


#: Schalter, die aus einem harmlosen Befehl einen eingreifenden machen.
#: ``find`` und ``git`` gelten als lesend — mit diesen Schaltern sind sie es nicht.
#: Pfade, deren Inhalt niemand ungefragt zu sehen bekommt. Lesen ist harmlos,
#: Geheimnisse lesen nicht — "cat /etc/shadow" lief vorher ohne Rueckfrage
#: durch, weil "cat" in READ_COMMANDS steht.
HEIKLE_PFADE = (
    "/etc/shadow", "/etc/gshadow", "/etc/sudoers",
    ".ssh/", "id_rsa", "id_ed25519", ".gnupg",
    ".env", "credentials", "secrets", ".netrc", ".pgpass",
    "/root/", "vaultwarden", ".aws/", ".kube/config",
)


SCHREIBENDE_SCHALTER = (
    "-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fls",
    "clean", "reset", "checkout", "push", "rebase", "filter-branch",
    "-i", "--in-place", "-o", "--output", "--force", "-f",
)


def _ist_interne_adresse(url: str) -> bool:
    """Ob eine URL ins eigene Netz zeigt (privat, loopback, link-local) oder
    sich nicht sicher als oeffentlich erkennen laesst."""
    import ipaddress
    import socket
    from urllib.parse import urlparse
    try:
        host = urlparse(url if "://" in url else "http://" + url).hostname or ""
        if not host or host in ("localhost",) or host.endswith((".local", ".lan", ".internal", ".home")):
            return True
        try:
            adressen = {info[4][0] for info in socket.getaddrinfo(host, None)}
        except socket.gaierror:
            return False  # gibt es nicht — der Abruf scheitert sofort, keine Freigabe nötig
        return any(
            ipaddress.ip_address(a).is_private
            or ipaddress.ip_address(a).is_loopback
            or ipaddress.ip_address(a).is_link_local
            for a in adressen
        )
    except Exception:
        return True


def classify_tool(name: str, args: dict) -> str:
    if name == "knowledge_search":
        return "read"
    if name == "system_info":
        return "read"
    if name == "read_file":
        return "admin" if _beruehrt_heikles(str(args.get("path", ""))) else "read"
    if name == "list_files":
        return "admin" if _beruehrt_heikles(str(args.get("path", ""))) else "read"
    if name == "find_files":
        return "read"
    if name == "web_search":
        return "read"
    # Seit 2026-10-02: Diese lesenden Werkzeuge fielen bisher ans Ende durch
    # und galten als "write" — jeder Seitenabruf brauchte eine Freigabe, ohne
    # Freigabe drehte der Recherche-Agent Runden um Runden.
    if name == "web_fetch":
        # Oeffentliche Seiten lesen ist harmlos. Adressen im eigenen Netz
        # nicht: sonst fragt ein Agent ungefragt interne Dienste ab (SSRF).
        return "admin" if _ist_interne_adresse(str(args.get("url", ""))) else "read"
    if name in ("read_document", "rag_search", "memory_load"):
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
    """Stuft einen Shell-Befehl ein.

    Frueher: Sperrliste. Das erste Wort entschied, und ein paar Zeichenketten
    waren verboten. Nachgerechnet am laufenden System liefen damit ohne
    jede Rueckfrage durch:

        find /daten -name "*" -delete
        git clean -fdx
        git push --force
        cat /etc/shadow

    ``find`` und ``git`` standen in READ_COMMANDS, und die Sperrliste kannte
    weder ``-delete`` noch ``clean``. Eine Sperrliste kann das grundsaetzlich
    nicht leisten: sie muss alles Schaedliche vorher kennen.

    Jetzt umgekehrt. Ohne Freigabe laeuft nur, was als harmlos **erwiesen**
    ist — und auch das nur, wenn der Befehl keine Verkettung enthaelt und
    keinen Schalter traegt, der aus einem Lesebefehl einen Schreibbefehl macht.
    Alles andere geht zur Rueckfrage, statt still ausgefuehrt zu werden.
    """
    stripped = cmd.strip()
    if not stripped:
        return "blocked"

    # Verkettung, Umleitung, Ersetzung: ab hier ist nicht mehr zu sehen, was
    # tatsaechlich laeuft. Das erste Wort sagt dann nichts mehr aus.
    for zeichen in ("|", ";", "&", ">", "<", "`", "$(", "\n"):
        if zeichen in stripped:
            return "admin"

    for pat in BLOCKED_PATTERNS:
        if pat in stripped:
            return "blocked"

    base = stripped.split()[0].split("/")[-1]

    # Schalter, die einen Lesebefehl zum Schreibbefehl machen. Ohne diese
    # Pruefung ist "find ... -delete" ein Lesebefehl.
    for schalter in SCHREIBENDE_SCHALTER:
        if re.search(rf"(?:^|\s){re.escape(schalter)}(?:\s|=|$)", stripped):
            return "admin"

    if base in READ_COMMANDS:
        return "admin" if _beruehrt_heikles(stripped) else "read"
    if base in WRITE_COMMANDS:
        return "write"
    return "blocked"


def _beruehrt_heikles(text: str) -> bool:
    """Ob irgendwo in der Zeile ein Pfad steht, der nicht ungefragt gelesen wird."""
    klein = text.lower()
    return any(pfad.lower() in klein for pfad in HEIKLE_PFADE)


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

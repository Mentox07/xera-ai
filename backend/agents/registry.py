"""
Xera AI — Agent Registry
Imports all 20 agents from individual definition files in definitions/.
"""

from .definitions.code import AGENT as _code
from .definitions.devops import AGENT as _devops
from .definitions.proxmox import AGENT as _proxmox
from .definitions.monitoring import AGENT as _monitoring
from .definitions.knowledge import AGENT as _knowledge
from .definitions.research import AGENT as _research
from .definitions.web_search import AGENT as _web_search
from .definitions.security import AGENT as _security
from .definitions.network import AGENT as _network
from .definitions.docker import AGENT as _docker
from .definitions.log_analysis import AGENT as _log_analysis
from .definitions.documentation import AGENT as _documentation
from .definitions.database import AGENT as _database
from .definitions.backup import AGENT as _backup
from .definitions.incident_response import AGENT as _incident_response
from .definitions.home_automation import AGENT as _home_automation
from .definitions.finance import AGENT as _finance
from .definitions.content import AGENT as _content
from .definitions.discord_agent import AGENT as _discord
from .definitions.email import AGENT as _email
from .definitions.calendar import AGENT as _calendar
from .definitions.document_reader import AGENT as _document_reader
from .definitions.document_write import AGENT as _document_write

_ALL_AGENTS = [
    _code,
    _devops,
    _proxmox,
    _monitoring,
    _knowledge,
    _research,
    _web_search,
    _security,
    _network,
    _docker,
    _log_analysis,
    _documentation,
    _database,
    _backup,
    _incident_response,
    _home_automation,
    _finance,
    _content,
    _discord,
    _email,
    _calendar,
    _document_reader,
    _document_write,
]

AGENTS: dict[str, dict] = {a["id"]: a for a in _ALL_AGENTS}

# ─────────────────────────────────────────────
# Lookup helpers
# ─────────────────────────────────────────────

def get_agent(agent_id: str) -> dict | None:
    return AGENTS.get(agent_id)


_HOMELAB_AGENTS = {
    "proxmox", "monitoring", "knowledge", "network",
    "home_automation", "discord", "incident_response",
}


def list_agents(tab: str | None = None) -> list[dict]:
    agents = list(AGENTS.values())
    if tab == "chat":
        agents = [a for a in agents if a["tab"] in ("both", "chat")]
    elif tab == "homelab":
        agents = [a for a in agents if a["tab"] in ("both", "homelab")]
    return [
        {
            "id": a["id"],
            "name": a["name"],
            "icon": a["icon"],
            "color": a["color"],
            "brain": a["brain"],
            "tab": a["tab"],
            "description": a["description"],
            "scope": "homelab" if a["id"] in _HOMELAB_AGENTS else "general",
        }
        for a in agents
    ]

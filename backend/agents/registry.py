"""
Xera AI — Agent-Register.

Seit 2026-10-19 nur noch die Agents aus dem Neubau (neubau.py, Manifeste unter
/opt/xera-ai/neubau-agents). Die 34 alten Agents aus definitions/ gehörten zur alten
Oberfläche mit Stichwort-Orchestrator; ihre Prompts trugen Adressen und Namen aus dem
Homelab und wurden mit der Veröffentlichung des Quelltexts entfernt.
"""

AGENTS: dict[str, dict] = {}

# Die 95 Agents aus dem Neubau, im Testbetrieb (seit 2026-10-02). Ohne
# Stichwoerter — der Orchestrator waehlt sie nie von selbst. Siehe neubau.py.
from . import neubau as _neubau

_NEUBAU = _neubau.laden()
AGENTS.update({a["id"]: a for a in _NEUBAU})

# ─────────────────────────────────────────────
# Lookup helpers
# ─────────────────────────────────────────────

def get_agent(agent_id: str) -> dict | None:
    # Neubau-Prompts delegieren mit ihren eigenen Kennungen ("recherche"),
    # die hier "neu_recherche" heissen.
    return AGENTS.get(agent_id) or AGENTS.get("neu_" + agent_id)


_HOMELAB_AGENTS = {a["id"] for a in _NEUBAU if a.get("homelab")}


def list_agents(tab: str | None = None, nur_neu: bool = False) -> list[dict]:
    agents = list(AGENTS.values())
    if nur_neu:
        agents = [a for a in agents if a.get("neubau")]
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
            # Seit der Umstellung auf ein Modell (23.08.2026) fehlt brain bei
            # 14 Agents; a["brain"] liess /api/agents mit HTTP 500 abstuerzen.
            "brain": a.get("brain"),
            "tab": a["tab"],
            "description": a["description"],
            "scope": "homelab" if a["id"] in _HOMELAB_AGENTS else "general",
            "neubau": bool(a.get("neubau")),
            "kategorie": a.get("kategorie"),
        }
        for a in agents
    ]

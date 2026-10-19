"""Die 95 Agents aus dem Neubau (~/xera) im Testbetrieb.

Liest Manifeste und Prompts aus /opt/xera-ai/neubau-agents (Kopie von
core/xera_core/agents/manifeste) und baut daraus Agent-Einträge im Format des
Altbestands. Seit 2026-10-02.

Bewusst so angebunden, dass sich am bisherigen Verhalten nichts ändert:

* Kennung mit Vorsatz ``neu_`` — keine Kollision mit den 35 alten Agents
  (beide haben z. B. "docker").
* Keine Stichwörter — der Orchestrator wählt sie nie von selbst. Man wählt sie
  gezielt in der Oberfläche (Agents-Übersicht, @).
* Ausgeführt über den normalen Ablauf in base.py, also mit Freigabeabfrage und
  Protokoll für eingreifende Werkzeuge.
* Denkmodus ("denkmodus: an") wird über brain="denken" an _call_llm gemeldet.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .. import standort

_log = logging.getLogger(__name__)

ORDNER = Path("/opt/xera-ai/neubau-agents")
VORSATZ = "neu_"

# Eine Farbe je Kategorie, damit die Übersicht nicht 95-mal dieselbe zeigt.
_FARBEN = {
    "homelab": "#f59e0b",
    "code": "#4f9cf9",
    "dokumente": "#0891b2",
    "darstellung": "#a855f7",
    "web": "#0ea5e9",
    "cloud": "#06b6d4",
    "daten": "#10b981",
    "wissen": "#8b5cf6",
    "lernen": "#22c55e",
    "beruf": "#f97316",
    "geschaeft": "#eab308",
    "alltag": "#ec4899",
    "recht": "#64748b",
    "kommunikation": "#14b8a6",
    "schreiben": "#e879f9",
    "bilder": "#f43f5e",
}


def laden() -> list[dict]:
    """Alle Manifeste als Agent-Einträge. Fehlerhafte werden übersprungen."""
    try:
        import yaml
    except ImportError:  # pragma: no cover
        _log.warning("neubau: PyYAML fehlt, keine Neubau-Agents")
        return []
    if not ORDNER.is_dir():
        return []

    agents: list[dict] = []
    for datei in sorted(ORDNER.glob("*.yaml")):
        try:
            roh = yaml.safe_load(datei.read_text(encoding="utf-8")) or {}
            kennung = str(roh["kennung"]).strip()
            prompt = str(roh.get("prompt", "")).strip()
            if prompt.endswith(".md"):
                prompt = (datei.parent / prompt).read_text(encoding="utf-8").strip()
            # Adressen dieses Homelabs stehen nicht im Repo, sondern in der Standort-Datei
            prompt = standort.einsetzen(prompt)
            nicht = roh.get("nicht_zustaendig") or []
            if nicht:
                prompt += "\n\nNicht zuständig für:\n" + "\n".join(f"- {n}" for n in nicht)
            kategorie = str(roh.get("kategorie", "sonstiges"))
            homelab = str(roh.get("lizenz", "")) == "homelab" or kategorie == "homelab"
            agents.append({
                "id": VORSATZ + kennung,
                "name": str(roh.get("name", kennung)),
                "icon": "",
                "color": _FARBEN.get(kategorie, "#7c7c8a"),
                "tab": "homelab" if homelab else "both",
                "description": str(roh.get("kurz", "")),
                "keywords": [],
                "tools": list(roh.get("werkzeuge") or []),
                "max_tokens": int(roh.get("max_token") or 4096),
                "brain": "denken" if str(roh.get("denkmodus", "aus")) == "an" else "big",
                "system_prompt": prompt,
                "neubau": True,
                "kategorie": kategorie,
                "homelab": homelab,
            })
        except Exception as e:  # ein kaputtes Manifest darf nicht alle anderen mitreissen
            _log.warning("neubau: %s übersprungen: %s", datei.name, e)
    _log.info("neubau: %d Agents geladen", len(agents))
    return agents

"""Was nur dieses Homelab betrifft — SSH-Ziele, Netz-Beschreibungen in Prompts — liegt in einer
Datei ausserhalb des Repos (seit 2026-10-19, vor der Veröffentlichung des Quelltexts).

Pfad: ``XERA_STANDORT``, Standard ``/opt/xera-ai/privat/standort.json``. Fehlt sie, gibt es keine
Homelab-Ziele, und Platzhalter in Prompts bleiben leer. Vorlage: ``standort.example.json``.
"""

import json
import logging
import os
import re
from pathlib import Path

_log = logging.getLogger(__name__)

DATEI = Path(os.getenv("XERA_STANDORT", "/opt/xera-ai/privat/standort.json"))


def _laden() -> dict:
    try:
        return json.loads(DATEI.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as fehler:
        _log.warning("standort: %s nicht lesbar: %s", DATEI, fehler)
        return {}


STANDORT = _laden()


def ssh_ziele() -> dict[str, dict]:
    """Ziele für ssh_execute: Name → {"host": "benutzer@adresse", "label": …, "use_key": …}."""
    return dict(STANDORT.get("ssh_ziele") or {})


def einsetzen(text: str) -> str:
    """``{{name}}`` in Prompt-Texten durch ``texte.name`` aus der Standort-Datei ersetzen."""
    texte = STANDORT.get("texte") or {}
    return re.sub(r"\{\{(\w+)\}\}", lambda m: str(texte.get(m.group(1), "")), text)

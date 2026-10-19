"""Kontextschutz: lange Gespräche zusammenfassen statt abbrechen (seit 2026-10-02).

Wie bei Claude Code / Codex:

* Jede Antwort meldet, wie voll das Gesprächsfenster ist (Ereignis ``kontext``).
* Ab ``SCHWELLE_HINWEIS`` zeigt die Oberfläche einen Hinweis mit zwei Knöpfen:
  "Zusammenfassen und weiter" und "Neuer Chat mit Übergabe".
* Ab ``SCHWELLE_AUTO`` fasst Xera selbst zusammen: Das Ältere wird zu einer
  Zusammenfassung, die letzten ``WOERTLICH_TOKENS`` bleiben wörtlich.
* Die Zusammenfassung wird pro Gespräch gespeichert und wiederverwendet, damit
  sie nicht bei jeder Frage neu entsteht. Der Nutzer sieht im Verlauf weiter
  alles — gekürzt wird nur, was das Modell bekommt.

Ein Slot fasst höchstens ``FENSTER`` Tokens (``--kv-unified-per-slot``);
darüber lehnt llama-server ab, statt abzustürzen.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone

import httpx

from . import config
from .database import get_db

_log = logging.getLogger(__name__)

FENSTER = 65536  # Startwert — fenster_aktualisieren() holt den echten Wert von llama-server


async def fenster_aktualisieren() -> int:
    """Kontext je Slot aus llama-server /props (n_ctx), seit 2026-10-16.
    Vorher stand 65536 fest im Code (hier und in der Oberfläche) — mit einem
    grösseren Fenster hätte der Kontextschutz trotzdem bei 64k eingegriffen."""
    global FENSTER
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(3.0)) as client:
            r = await client.get(f"{config.LLAMA_API_URL}/props")
            r.raise_for_status()
            n = int((r.json().get("default_generation_settings") or {}).get("n_ctx") or 0)
        if n >= 8192 and n != FENSTER:
            _log.warning("kontext: Fenster je Slot jetzt %s Tokens (vorher %s)", n, FENSTER)
            FENSTER = n
    except Exception:
        pass
    return FENSTER
RESERVE = 6000              # Systemprompt, Regeln, Platz für die Antwort
SCHWELLE_HINWEIS = 0.75
SCHWELLE_AUTO = 0.85
WOERTLICH_TOKENS = 12000
ZEICHEN_PRO_TOKEN = 3.0     # gemessen am Prüftext: ~3,1 bei Deutsch, Code eher weniger


def _tabelle() -> None:
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS kontext_verdichtung (
            session_id INTEGER PRIMARY KEY,
            bis_nachricht INTEGER NOT NULL,
            bis_hash TEXT NOT NULL,
            zusammenfassung TEXT NOT NULL,
            erstellt TEXT NOT NULL
        )""")
    conn.commit()
    conn.close()


_tabelle()


# --- Zählen --------------------------------------------------------------------

def _text(inhalt) -> str:
    if isinstance(inhalt, list):
        return " ".join(p.get("text", "") for p in inhalt if isinstance(p, dict))
    return str(inhalt or "")


def _bilder(inhalt) -> int:
    if isinstance(inhalt, list):
        return sum(1 for p in inhalt if isinstance(p, dict) and p.get("type") == "image_url")
    return 0


def schaetzen(messages: list[dict]) -> int:
    """Grobe Tokenzahl. Bilder kosten bei 1568 px rund 3000 Tokens."""
    zeichen = sum(len(_text(m.get("content"))) for m in messages)
    bilder = sum(_bilder(m.get("content")) for m in messages)
    return int(zeichen / ZEICHEN_PRO_TOKEN) + 3000 * bilder + 8 * len(messages)


def stufe(tokens: int) -> str:
    if tokens >= FENSTER * SCHWELLE_AUTO:
        return "voll"
    if tokens >= FENSTER * SCHWELLE_HINWEIS:
        return "lang"
    return "ok"


def ereignis(tokens: int, verdichtet: bool = False) -> dict:
    return {"type": "kontext", "belegt": int(tokens), "max": FENSTER,
            "stufe": "verdichtet" if verdichtet else stufe(tokens)}


# --- Zusammenfassen --------------------------------------------------------------

_AUFTRAG = """Fasse das bisherige Gespräch so zusammen, dass es ohne den Originalverlauf weitergehen kann. Schreib auf Deutsch, sachlich, in Stichpunkten unter diesen Überschriften (leere weglassen):

## Anliegen
Was der Nutzer will, in seinen eigenen Worten, und Vorgaben/Vorlieben, die er genannt hat.
## Stand
Was bereits erledigt, beantwortet oder entschieden ist — mit den konkreten Ergebnissen (Zahlen, Namen, Versionen, Befehle).
## Wichtige Details
Fakten, Dateinamen, Pfade, IPs, Code-Stellen (kurze Ausschnitte wörtlich), Fehlermeldungen und ihre Lösung, Quellen-Links.
## Offen
Was noch zu tun ist oder zuletzt gefragt wurde.

Höchstens etwa 1500 Wörter. Erfinde nichts dazu."""


def _hash(m: dict) -> str:
    return hashlib.sha1(_text(m.get("content")).encode()).hexdigest()[:16]


def _laden(session_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM kontext_verdichtung WHERE session_id = ?", (session_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def _speichern(session_id: int, bis: int, bis_hash: str, text: str) -> None:
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO kontext_verdichtung (session_id, bis_nachricht, bis_hash, zusammenfassung, erstellt)"
        " VALUES (?, ?, ?, ?, ?)",
        (session_id, bis, bis_hash, text, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def _als_paar(zusammenfassung: str) -> list[dict]:
    return [
        {"role": "user", "content": "[Zusammenfassung des bisherigen Gesprächs — die älteren Nachrichten sind ausgeblendet]\n\n" + zusammenfassung},
        {"role": "assistant", "content": "Verstanden, ich habe den bisherigen Stand."},
    ]


# Für die Zusammenfassung im Gespräch selbst (seit 2026-10-17): als letzte
# Nachricht hinter dem Verlauf, den das Modell schon im Slot hat.
AUFTRAG_IM_GESPRAECH = ("(System: Dieses Gespräch wird zu lang für dein Arbeitsgedächtnis. Beantworte jetzt keine "
                        "Frage und rufe kein Werkzeug auf — schreib nur eine Zusammenfassung des bisherigen Gesprächs "
                        "nach diesen Regeln:\n\n" + _AUFTRAG + ")")


async def strom(anfrage: dict, fortschritt: dict | None = None) -> str:
    """Anfrage gestreamt, mit Einlese-Fortschritt (seit 2026-10-17). Das
    Zeitlimit gilt pro Stück statt für die ganze Antwort: Vorher brach eine
    Zusammenfassung über ~100 000 Tokens unter Last nach 15 min ab (Test K6/K7)
    — die Arbeit war verloren, und bei jeder weiteren Nachricht begann sie von vorn."""
    from . import slotsperre
    anfrage = {**anfrage, "stream": True, "return_progress": True}
    teile: list[str] = []
    async with slotsperre.slot(anfrage.get("id_slot")), \
            httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=300.0, write=30.0, pool=10.0)) as client:
        await slotsperre.leeren_slot_anstossen(client, config.LLAMA_API_URL, anfrage.get("id_slot"))
        async with client.stream("POST", f"{config.LLAMA_API_URL}/v1/chat/completions", json=anfrage) as r:
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code}: {(await r.aread()).decode('utf-8', 'replace')[:300]}")
            async for zeile in r.aiter_lines():
                if not zeile.startswith("data: "):
                    continue
                roh = zeile[6:]
                if roh == "[DONE]":
                    break
                try:
                    stueck = json.loads(roh)
                except json.JSONDecodeError:
                    continue
                if stueck.get("error"):
                    raise RuntimeError(json.dumps(stueck["error"], ensure_ascii=False)[:300])
                if stueck.get("prompt_progress"):
                    if fortschritt is not None:
                        fortschritt.update(stueck["prompt_progress"])
                    continue
                for wahl in stueck.get("choices") or []:
                    teile.append((wahl.get("delta") or {}).get("content") or "")
    return "".join(teile).strip()


async def zusammenfassen(messages: list[dict], vorherige: str = "", fortschritt: dict | None = None) -> str:
    verlauf = "\n\n".join(f"### {m.get('role')}\n{_text(m.get('content'))}" for m in messages)
    if vorherige:
        verlauf = "### Frühere Zusammenfassung\n" + vorherige + "\n\n" + verlauf
    # Sicherheitsnetz: was zusammengefasst wird, muss selbst ins Fenster passen.
    grenze = int((FENSTER - 4000) * ZEICHEN_PRO_TOKEN * 0.9)
    if len(verlauf) > grenze:
        verlauf = "[… Anfang gekürzt …]\n" + verlauf[-grenze:]
    anfrage = {
        "model": "xera-ai",
        "messages": [
            {"role": "system", "content": _AUFTRAG},
            {"role": "user", "content": "Hier ist das Gespräch:\n\n" + verlauf + "\n\nSchreib jetzt die Zusammenfassung."},
        ],
        "max_tokens": 3000,
        "id_slot": 4,  # Nebenaufgaben-Slot (seit 2026-10-16 statt 2: dort startet jeder erste Agent)
        "temperature": 0.3,
    }
    return await strom(anfrage, fortschritt)


def _schnitt(messages: list[dict]) -> int:
    """Index, ab dem die Nachrichten wörtlich bleiben (die letzten ~WOERTLICH_TOKENS).
    Schneidet nur vor einer Nutzerfrage, damit Frage und Antwort zusammenbleiben."""
    summe = 0
    schnitt = len(messages)
    for i in range(len(messages) - 1, -1, -1):
        summe += schaetzen([messages[i]])
        if summe > WOERTLICH_TOKENS and i < len(messages) - 1:
            break
        schnitt = i
    while schnitt < len(messages) - 1 and messages[schnitt].get("role") != "user":
        schnitt += 1
    return schnitt


def anwenden(messages: list[dict], session_id: int | None) -> tuple[list[dict], bool]:
    """Ersetzt bereits zusammengefasste Nachrichten durch die gespeicherte
    Zusammenfassung. Stimmt der Verlauf nicht mehr (bearbeitet, gekürzt),
    wird sie verworfen."""
    if not session_id:
        return messages, False
    v = _laden(session_id)
    if not v or v["bis_nachricht"] > len(messages) or v["bis_nachricht"] < 1:
        return messages, False
    if _hash(messages[v["bis_nachricht"] - 1]) != v["bis_hash"]:
        return messages, False
    return _als_paar(v["zusammenfassung"]) + messages[v["bis_nachricht"]:], True


async def verdichten(messages: list[dict], session_id: int | None, *, erzwingen: bool = False,
                     im_gespraech=None, fortschritt: dict | None = None) -> tuple[list[dict], bool]:
    """Liefert den Verlauf fürs Modell und ob er zusammengefasst ist.
    Fasst (neu) zusammen, wenn das Fenster zu voll ist oder ``erzwingen``.

    ``im_gespraech(bisher, anker)`` (vermittler.py, seit 2026-10-17) fasst im
    Slot des Gesprächs zusammen, mit genau dem Verlauf, den das Modell zuletzt
    hatte — llama-server nimmt ihn aus dem Cache und liest nur den Auftrag
    ein. Vorher lief die Zusammenfassung im Nebenaufgaben-Slot und las das
    ganze Gespräch noch einmal ein (K6: ~108 000 Tokens)."""
    gekuerzt, verdichtet = anwenden(messages, session_id)
    if not erzwingen and schaetzen(gekuerzt) + RESERVE < FENSTER * SCHWELLE_AUTO:
        return gekuerzt, verdichtet

    schnitt = _schnitt(messages)
    if schnitt < 2:
        return gekuerzt, verdichtet  # nichts Älteres zum Zusammenfassen — eine Riesennachricht
    alt = _laden(session_id) if session_id else None
    vorherige = ""
    start = 0
    if alt and verdichtet and alt["bis_nachricht"] <= schnitt:
        vorherige, start = alt["zusammenfassung"], alt["bis_nachricht"]
    text = ""
    # Im Gespräch nur, solange Verlauf + Auftrag + Zusammenfassung sicher in den
    # Slot passen (Schätzung Zeichen/3; Code und Zahlen brauchen mehr Tokens).
    if (im_gespraech is not None and len(gekuerzt) > 1 and messages[-1].get("role") == "user"
            and schaetzen(gekuerzt[:-1]) + RESERVE < FENSTER * 0.92):
        try:
            # Alles bis vor die neue Frage, so wie das Modell es zuletzt gesehen hat.
            anker = _text(messages[schnitt].get("content"))[:120] if schnitt < len(messages) - 1 else ""
            text = await im_gespraech(gekuerzt[:-1], anker)
        except Exception:
            _log.exception("kontext: Zusammenfassung im Gespräch fehlgeschlagen — jetzt getrennt")
    if not text:
        try:
            text = await zusammenfassen(messages[start:schnitt], vorherige, fortschritt)
        except Exception:
            _log.exception("kontext: Zusammenfassung fehlgeschlagen")
            return gekuerzt, verdichtet
    if not text:
        return gekuerzt, verdichtet
    if session_id:
        _speichern(session_id, schnitt, _hash(messages[schnitt - 1]), text)
    _log.info("kontext: Sitzung %s bis Nachricht %s zusammengefasst (%s Zeichen)", session_id, schnitt, len(text))
    return _als_paar(text) + messages[schnitt:], True


def zusammenfassung_von(session_id: int) -> str | None:
    v = _laden(session_id)
    return v["zusammenfassung"] if v else None

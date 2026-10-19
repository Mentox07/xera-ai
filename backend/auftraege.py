"""Parallele Aufträge an Agents (seit 2026-10-02).

Wie bei Claude Code / Codex / Gemini CLI: Das Hauptmodell macht die Arbeit und
gibt Teilaufgaben an Agents ab.

* Ein Agent bekommt **nur seinen Auftrag** (leerer Kontext, eigener Prompt),
  nicht das Gespräch.
* Mehrere Aufträge laufen **gleichzeitig**, jeder auf einem eigenen
  llama-Slot (2–5, siehe ``_AGENT_SLOTS``).
* Der Agent liefert eine **Zusammenfassung an das Hauptmodell**, nicht an den
  Nutzer; das Hauptmodell schreibt die Antwort.
* Werkzeug-Schritte, Freigaben und Fortschritt gehen live an die Oberfläche,
  markiert mit ``lauf`` (welcher Auftrag).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from typing import AsyncGenerator

from . import arbeitsbereich
from .agents.base import _execute_agent
from .tools import LLAMA_SLOT, SANDBOX
from .agents.registry import AGENTS

_log = logging.getLogger(__name__)

MAX_AUFTRAEGE = 4
MAX_RUNDEN_AGENT = 4      # Werkzeugrunden je Auftrag (sonst 12), danach Schlussantwort
# Wer mit Dateien arbeitet, braucht mehr: lesen, gezielt ändern (oft mehrere
# Stellen), testen, nachbessern (seit 2026-10-17).
MAX_RUNDEN_DATEIEN = 8
_DATEI_WERKZEUGE = {"read_file", "write_file", "str_replace_file", "python_exec", "find_files", "list_files"}
MAX_TOKENS_AGENT = 16384
ZUSAMMENFASSUNG_MAX_ZEICHEN = 6000

_ROLLE = """

---
(Du arbeitest als Helfer für das Hauptmodell, nicht direkt für den Nutzer. Das Gespräch kennst du nicht — alles Nötige steht im Auftrag oben.
Schreib auf Deutsch, nie chinesische oder andere fremde Schriftzeichen. Erledige genau den Auftrag — nicht mehr. Schreib vor Werkzeugaufrufen KEINEN Text (kein „Ich suche jetzt …“) — ruf das Werkzeug direkt auf; Text nur in der Schluss-Zusammenfassung. Arbeite zielgerichtet: meist reichen 2–4 Werkzeugaufrufe; recherchiere nichts, was nicht verlangt ist (z. B. keine Preise, wenn nach Versionen gefragt ist). Erfinde keine URLs — öffne nur Adressen aus Suchergebnissen.
Dokumente (PDF, Word, Excel, Präsentation) erzeugst du direkt mit create_document (xlsx: eine Zeile pro Tabellenzeile, Zellen mit | getrennt, erste Zeile = Kopf, „## Blattname“ beginnt ein neues Blatt), nicht mit python_exec. Erzeuge jede Datei GENAU EINMAL und lies sie danach nicht zur Kontrolle wieder ein — create_document ist zuverlässig.
NEUE CODE-DATEIEN (Programme, Webseiten, Spiele, Skripte): NIE als Werkzeug-Argument — schreib den vollständigen Code als Codeblock mit Dateinamen in deine Schlussantwort: ```html datei=spiel.html (bzw. ```python datei=auswertung.py), und schliess den Codeblock mit ``` ab. Xera speichert ihn im Arbeitsordner, testet ihn und gibt dem Hauptmodell den Link. Prüfe vorher selbst: jede Variable ist dort definiert, wo sie benutzt wird.
BESTEHENDE DATEIEN (stehen in der Dateiliste des Auftrags): read_file, dann gezielt str_replace_file, danach datei_testen — nicht neu schreiben, nicht in Python nachbauen. Steht eine genannte Datei nicht in der Liste und findet read_file sie nicht: sofort melden und aufhören.
Du hast höchstens {runden} Werkzeugrunden und für die ganze Frage zusammen nur 3 Webseiten; danach antwortest du mit dem, was du hast. Für Code-Reparaturen keine Websuche.
Schliesse mit einer kompakten Zusammenfassung für das Hauptmodell:
- das Ergebnis (konkret: Zahlen, Namen, Versionen, Befehle, Code-Ausschnitte)
- Quellen als Markdown-Links
- erzeugte Dateien mit ihrem Download-Link, unverändert übernommen
- was nicht geklappt hat oder offen ist
Höchstens etwa 800 Wörter, keine Rückfragen.)"""


# Je Agent-Slot läuft immer nur ein Agent. Bis 2026-10-15 bekamen Aufträge
# reihum Slot 2/3 — bei 3–4 Aufträgen teilten sich zwei gleichzeitig laufende
# Agents einen Slot, ihre Schritte wechselten sich ab und jeder Schritt musste
# den ganzen Prompt neu einlesen (~2 000+ Tokens, ~15 s). Seitdem hat
# llama-server 6 Slots: 2–5 für Agents, ein Auftrag nimmt den niedrigsten
# freien. Ein Agent, der auf eine Freigabe wartet, hält so niemanden auf. Nur
# wenn mehrere Anfragen gleichzeitig Agents starten, kann einer warten.
# Slot 5 teilen sich die Agents mit Homelab (unwichtigster Bereich, wird erst
# beim vierten gleichzeitigen Agent verdrängt).
_AGENT_SLOTS = (2, 3, 4, 5)
_freie_slots: asyncio.PriorityQueue | None = None


class _Gestoppt(Exception):
    """Stopp-Knopf, bevor ein Agent-Slot frei wurde."""


def _slots() -> asyncio.PriorityQueue:
    # PriorityQueue: immer der niedrigste freie Slot. Mit einer normalen
    # Queue wanderten die Slots reihum, und ein einzelner Agent landete auf
    # Slot 5 (Homelab).
    global _freie_slots
    if _freie_slots is None:
        _freie_slots = asyncio.PriorityQueue()
        for slot in _AGENT_SLOTS:
            _freie_slots.put_nowait(slot)
    return _freie_slots


def _sse(daten: dict) -> str:
    return f"data: {json.dumps(daten, ensure_ascii=False)}\n\n"


def _code_kuerzen(text: str) -> str:
    """Grosse Codeblöcke, die schon als Datei vorliegen, nicht ans Hauptmodell
    weiterreichen. Sonst schnitt ZUSAMMENFASSUNG_MAX_ZEICHEN die Antwort mitten
    im Code ab — samt dem Download-Link am Ende (Chat 512) — und das
    Hauptmodell schrieb das ganze Programm noch einmal ab."""
    def kurz(m: re.Match) -> str:
        code = m.group(2)
        zeilen = code.count("\n") + 1
        if zeilen < 25:
            return m.group(0)
        sprache = (m.group(1).split() or ["Code"])[0]
        return f"[{sprache}-Code, {zeilen} Zeilen — als Datei gespeichert, Link unten]"
    return re.sub(r"```([^\n`]*)\n(.*?)\n?```", kurz, text, flags=re.S)


async def _ein_lauf(
    lauf: str,
    agent_def: dict,
    auftrag: str,
    schlange: asyncio.Queue,
    *,
    user_id: str,
    session_id: int | None,
    projektwissen: str,
    stop_event,
) -> dict:
    teile: list[str] = []
    fehler = ""
    dateien: list[str] = []
    # Eigener Stopp je Lauf: greift beim Stopp-Knopf UND sobald der Agent eine
    # Datei erzeugt hat — er hört nach der laufenden Runde auf. Im Test erzeugte
    # `tabelle` sonst dieselbe Datei sechsmal neu.
    mein_stopp = asyncio.Event()

    async def weiterreichen():
        if stop_event:
            while not stop_event.is_set():
                await asyncio.sleep(0.5)
            mein_stopp.set()
    waechter = asyncio.create_task(weiterreichen())

    await schlange.put(_sse({
        "type": "auftrag_start", "lauf": lauf, "kennung": agent_def["id"].removeprefix("neu_"),
        "name": agent_def["name"], "auftrag": auftrag[:400], "color": agent_def.get("color"),
    }))
    slot = None
    try:
        frei = _slots()
        if frei.empty():  # nur bei mehreren gleichzeitigen Anfragen
            await schlange.put(_sse({"type": "status", "status": "wartet auf einen freien Platz", "lauf": lauf}))
        while slot is None and not mein_stopp.is_set():
            try:
                slot = await asyncio.wait_for(frei.get(), timeout=0.5)
            except asyncio.TimeoutError:
                pass
        if slot is None:  # gestoppt, bevor ein Platz frei wurde
            raise _Gestoppt
        LLAMA_SLOT.set(slot)  # gilt nur in diesem Task (asyncio kopiert den Kontext)
        # Dateiliste des Gesprächs in den Auftrag (seit 2026-10-17): der Agent
        # kennt das Gespräch nicht — ohne Liste suchte er 40 min (Gespräch 580).
        liste = await arbeitsbereich.dateiliste_text(SANDBOX.get())
        if liste:
            dateien_text = ("\n\nDATEIEN IM ARBEITSORDNER DIESES GESPRÄCHS (mit read_file lesen, mit str_replace_file "
                            "ändern, mit datei_testen prüfen):\n" + liste)
        elif SANDBOX.get() is not None and set(agent_def.get("tools") or []) & _DATEI_WERKZEUGE:
            # Sonst sucht der Agent erst nach Dateien, die es nicht gibt (Test 2026-10-17: 6 Aufrufe).
            dateien_text = ("\n\nDer Arbeitsordner dieses Gesprächs ist noch LEER — es gibt keine Datei aus früheren "
                            "Runden; nicht danach suchen. Neue Code-Dateien schreibst du als Codeblock in deine Schlussantwort.")
        else:
            dateien_text = ""
        rolle = _ROLLE.replace("{runden}", str(agent_def.get("max_iterations") or MAX_RUNDEN_AGENT))
        async for roh in _execute_agent(
            agent_def, [{"role": "user", "content": auftrag + dateien_text + rolle}],
            user_id=user_id, session_id=session_id, visited_agents=frozenset({agent_def["id"]}),
            stop_event=mein_stopp, projektwissen=projektwissen,
        ):
            if not roh.startswith("data: "):
                continue
            nutz = roh[6:].strip()
            if not nutz or nutz == "[DONE]":
                continue
            try:
                daten = json.loads(nutz)
            except json.JSONDecodeError:
                continue
            art = daten.get("type")
            if art == "content" or (art is None and "content" in daten):
                teile.append(daten.get("content") or "")
                continue
            if art == "agent_selected":
                continue
            if art == "stopped":
                break
            if art == "tool_result" and daten.get("success"):
                # Download-Links aus allen Werkzeugen (create_document,
                # write_file, python_exec im Arbeitsordner).
                for link in re.findall(r"\[[^\]]*\]\(/api/download/[^)]+\)", daten.get("output") or ""):
                    if link not in dateien:
                        dateien.append(link)
                if daten.get("name") == "create_document":
                    mein_stopp.set()
            if art == "document" and daten.get("url"):
                # Codeblock der Schlussantwort als Datei (agents/base.py _code_dateien).
                link = f"[{daten.get('filename') or 'Datei'}]({daten['url']})"
                if daten.get("geprueft"):
                    link += f" — {daten['geprueft']}"
                dateien.append(link)
            if art == "error":
                fehler = daten.get("message") or "Fehler"
            # Werkzeuge, Freigaben, Status, Dokumente: mit Lauf-Kennung weiter.
            await schlange.put(_sse({**daten, "lauf": lauf}))
    except _Gestoppt:
        fehler = "abgebrochen"
    except Exception as e:  # pragma: no cover
        _log.exception("auftrag %s", agent_def["id"])
        fehler = f"{type(e).__name__}: {e}"
    finally:
        waechter.cancel()
        if slot is not None:
            _slots().put_nowait(slot)

    # Werkzeugaufrufe, die das Modell in der Schlussantwort als Text schrieb
    # (Chat 518: "<tool_call><function=read_file>…" in der Zusammenfassung).
    roh = re.sub(r"<tool_call>.*?(?:</tool_call>|$)", "", "".join(teile), flags=re.S).strip()
    text = _code_kuerzen(roh) if dateien else roh
    if dateien:
        fehlend = [d for d in dateien if d.split("(")[-1] not in text]
        if fehlend:
            text = (text + "\n\n" if text else "Datei erstellt.\n\n") + "Erzeugte Dateien:\n" + "\n".join(f"- {d}" for d in fehlend)
    ok = bool(text) and not fehler
    await schlange.put(_sse({
        "type": "auftrag_fertig", "lauf": lauf, "ok": ok,
        "zusammenfassung": text[:1500] if text else fehler,
    }))
    return {"kennung": agent_def["id"].removeprefix("neu_"), "auftrag": auftrag, "ok": ok,
            "ergebnis": (text or f"[Kein Ergebnis — {fehler or 'Agent hat nichts geliefert'}]")[:ZUSAMMENFASSUNG_MAX_ZEICHEN]}


async def ausfuehren(
    auftraege: list[dict],
    *,
    user_id: str,
    session_id: int | None,
    denken: bool,
    mit_homelab: bool,
    projektwissen: str = "",
    stop_event=None,
    gesperrt: set[str] | None = None,
) -> AsyncGenerator[tuple[str, object], None]:
    """Führt die Aufträge parallel aus.

    Liefert ``("sse", str)`` für die Oberfläche und zum Schluss genau einmal
    ``("ergebnisse", list[dict])`` für das Hauptmodell.
    """
    schlange: asyncio.Queue = asyncio.Queue()
    laeufe = []
    ergebnisse_fehler = []
    for a in auftraege[:MAX_AUFTRAEGE]:
        kennung = str(a.get("kennung", "")).strip().removeprefix("neu_")
        auftrag = str(a.get("auftrag", "")).strip()
        agent_def = AGENTS.get("neu_" + kennung)
        if gesperrt and kennung in gesperrt:
            ergebnisse_fehler.append({"kennung": kennung, "auftrag": auftrag, "ok": False,
                                      "ergebnis": f"[Agent '{kennung}' nicht beauftragt — Recherche, Vergleich und Erklärungen machst du selbst mit web_search (höchstens 3 Seiten).]"})
            continue
        if not agent_def or (agent_def.get("homelab") and not mit_homelab) or not auftrag:
            ergebnisse_fehler.append({"kennung": kennung, "auftrag": auftrag, "ok": False,
                                      "ergebnis": f"[Agent '{kennung}' ist hier nicht verfügbar oder der Auftrag ist leer]"})
            continue
        # Genug Tokens für ganze Dateien: mit 6 000 brach der Agent oberflaechen
        # mitten im Werkzeugaufruf ab (HTTP 500, 2026-10-15).
        mit_dateien = bool(set(agent_def.get("tools") or []) & _DATEI_WERKZEUGE) and SANDBOX.get() is not None
        agent_def = {**agent_def, "max_iterations": MAX_RUNDEN_DATEIEN if mit_dateien else MAX_RUNDEN_AGENT,
                     "max_tokens": max(int(agent_def.get("max_tokens") or 0), MAX_TOKENS_AGENT)}
        if denken:
            agent_def = {**agent_def, "brain": "denken"}
        lauf = uuid.uuid4().hex[:8]
        laeufe.append(asyncio.create_task(_ein_lauf(
            lauf, agent_def, auftrag, schlange,
            user_id=user_id, session_id=session_id, projektwissen=projektwissen, stop_event=stop_event,
        )))

    if laeufe:
        _log.info("auftraege: %s parallel", len(laeufe))
        yield ("sse", _sse({"type": "status", "status": f"{len(laeufe)} Agents arbeiten" if len(laeufe) > 1 else "1 Agent arbeitet"}))
    offen = set(laeufe)
    while offen:
        warten = asyncio.create_task(schlange.get())
        fertig, _ = await asyncio.wait(offen | {warten}, return_when=asyncio.FIRST_COMPLETED)
        if warten in fertig:
            yield ("sse", warten.result())
        else:
            warten.cancel()
        offen -= fertig
    while not schlange.empty():
        yield ("sse", schlange.get_nowait())

    yield ("ergebnisse", [t.result() for t in laeufe] + ergebnisse_fehler)


def fuer_modell(ergebnisse: list[dict]) -> str:
    """Werkzeug-Ergebnis für das Hauptmodell."""
    teile = []
    for e in ergebnisse:
        kopf = f"## Agent `{e['kennung']}` — {'fertig' if e['ok'] else 'FEHLGESCHLAGEN'}"
        teile.append(f"{kopf}\nAuftrag: {e['auftrag'][:300]}\n\n{e['ergebnis']}")
    return "\n\n".join(teile) + (
        "\n\n---\nSchreib jetzt die Antwort an den Nutzer aus diesen Ergebnissen — nur noch einmal beauftragen, wenn etwas fehlgeschlagen ist oder ein Folgeschritt (z. B. eine Datei) darauf aufbaut, nicht für mehr Details. "
        "Download-Links und Quellen unverändert übernehmen — als Markdown-Link [name](/api/download/…), nie als Code; Bilder (PNG/JPG/SVG) als ![name](/api/download/…). Code, der schon als Datei vorliegt, schreibst du NICHT noch einmal ab — "
        "Link, kurze Beschreibung (z. B. Steuerung, wie man es startet) und das Testergebnis genügen. Code-Dateien hat Xera bereits automatisch "
        "getestet (Ergebnis steht beim Link) — keine eigene Prüfrunde, keine Websuche dazu. Download-Links (/api/download/…) sind für den Nutzer; "
        "die Dateien selbst liegen im Arbeitsordner des Gesprächs (read_file, datei_testen). Fehlgeschlagenes ehrlich nennen."
    )

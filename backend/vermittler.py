"""Das Modell entscheidet selbst, ob es einen Agent braucht (seit 2026-10-02).

Vorher wählte der Orchestrator vor jeder Antwort per Stichwortsuche einen
Agent — bei "mach mir ein PDF" sprang er an, auch wenn das Modell es selbst
gekonnt hätte, und jede Agent-Runde kostet Zeit. Qwen3.8 ist stark genug, um
die meisten Fragen direkt zu beantworten.

Jetzt (wie bei ChatGPT/Claude):

* Das Modell antwortet normal und **streamt sofort** (der alte Chat-Weg in
  chat.py puffert die ganze Antwort).
* Grundwerkzeuge hat es **selbst**: ``web_search``, ``web_fetch``,
  ``read_document``. Eine Faktenfrage aus dem Netz braucht keinen Agent mehr
  (eigene Schleife, eigener Prompt — das kostete die Zeit).
* Schalter "Websuche": Xera sucht selbst vorab mit der Frage (``tool_choice:
  required`` ignoriert llama.cpp bei diesem Modell), das Modell bekommt die
  Treffer und kann weitersuchen.
* Agents nur in Code, Cowork und Homelab (``mit_agents``) — im normalen Chat
  nicht, wie bei den grossen Anbietern.
* In Code, Cowork und Homelab kennt es den Katalog der Neubau-Agents und das
  Werkzeug ``agents_beauftragen``: bis zu 4 Aufträge, die **parallel** laufen
  (auftraege.py). Jeder Agent bekommt nur seinen Auftrag und liefert eine
  Zusammenfassung zurück; die Antwort schreibt das Hauptmodell. Höchstens
  zwei Auftragsrunden pro Frage. Bis 2026-10-02 übernahm stattdessen ein
  einzelner Agent das ganze Gespräch und antwortete selbst.
* Denkmodus: das Modell denkt (Gedanken gehen als Ereignis ``denken`` hinaus),
  und ein beauftragter Agent denkt ebenfalls. Das Denken hat ein Budget
  (``DENK_BUDGET``) — ohne dachte Qwen3.8 bei „code mir ein Spiel“ 12 288 Tokens
  lang (12 min) und antwortete gar nicht.
* Lange Antworten: wird eine am Token-Limit abgeschnitten, schreibt das Modell
  bis zu ``FORTSETZUNGEN``-mal an der Abbruchstelle weiter.

Genutzt nur von der neuen Oberfläche (Feld ``routing: "modell"``). Alte
Oberfläche, CLI und Gäste bleiben beim bisherigen Weg.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import time
from datetime import datetime
from typing import AsyncGenerator

import httpx

from . import arbeitsbereich, aufwand, codepruefung, config, kontext, slotsperre
from .agents.registry import AGENTS
from .auftraege import ausfuehren as ausfuehren_auftraege, fuer_modell
from .chat import SYSTEM_PROMPT
from .learning import get_learnings_context
from .permissions import classify_tool, is_blocked, log_action, needs_approval
from .tools import RECHERCHE_BUDGET, SANDBOX, execute_tool, get_tools_for_agent

_log = logging.getLogger(__name__)

_REGELN = """
WERKZEUGE: Du HAST Zugang zum Internet. Sag NIE, du hättest keinen Internetzugang oder könntest nicht suchen.
- `web_search`: für alles, was aktuell sein muss oder nach deinem Wissensstand liegt (Neuigkeiten, Wetter, Kurse, Versionen, Preise) — und IMMER, wenn der Nutzer sagt, du sollst im Netz suchen oder nachschauen. Danach bei Bedarf `web_fetch` für eine Seite im Detail.
- `read_document`: für hochgeladene Dokumente, deren Text nicht schon in der Nachricht steht ([Dokument-Datei: name]). Fragt der Nutzer nach dem Inhalt eines solchen Dokuments, rufst du ZUERST read_document auf — antworte nie aus dem Gedächtnis und erfinde keine Inhalte.
- Sei sparsam: pro Frage hast du höchstens 4 Suchen und 3 Seiten (eine Suche lädt die besten Treffer schon mit). Meist reicht EINE Suche. Antworte, sobald du genug weisst — lieber knapp mit Quelle; will der Nutzer mehr, fragt er nach.
- Nenne bei Antworten aus dem Netz die Quellen als Markdown-Links.
SPRACHE: Antworte in der Sprache des Nutzers (meist Deutsch, Schweizer Schreibweise mit ss). Nie chinesische oder andere fremde Schriftzeichen einstreuen. Du duzt den Nutzer (nie „Sie“), ausser er siezt dich zuerst.
OBERFLÄCHE: Hier gibt es keinen Play-Button am Code und kein create_document() für dich selbst (die Anleitung oben dazu gilt nicht) — Dokumente (PDF, Word, Excel, Präsentation) und ausgeführter Code entstehen über einen Agent.
Vor einem Werkzeugaufruf schreibst du keinen Text — ruf das Werkzeug direkt auf.
Alles, was du selbst gut beantworten kannst — Erklärungen, Texte, Code schreiben, Übersetzen, Zusammenfassen, Beratung — beantwortest du DIREKT, ohne Werkzeug.
RECHNEN UND LOGIK: Bei Textaufgaben, Zeit- und Datumsrechnungen, Prozenten und Rätseln schreibst du den Rechenweg in wenigen kurzen Schritten hin und erst dann das Ergebnis — nie nur eine Zahl.
CODE: Beim Code-Schreiben suchst du NICHT im Netz — ausser der Nutzer verlangt es oder es geht um aktuelle Versionen/APIs, die du nicht sicher kennst. Fremden Code holst du nie aus dem Netz (GitHub, CDN, Beispielseiten) — du schreibst ihn selbst.
- Ein ganzes Programm oder eine ganze Seite schreibst du als EINEN vollständigen Codeblock. Gehört er in eine Datei, steht der Dateiname im Codezaun: ```html datei=spiel.html — Xera legt ihn automatisch als Download ab und testet HTML/JS im Browser. Behaupte nie, eine Datei liege schon beim Nutzer; den Link fügt Xera an.
- „klein“, „einfach“, „kurz“, „schnell“: kompakter Code (etwa 150–400 Zeilen), nur das Verlangte, keine Extras.
- Prüfe vor dem Abschicken: jede Variable ist dort definiert, wo sie benutzt wird (Gültigkeitsbereich!), jede Funktion existiert, Klammern und Tags sind geschlossen.
NACHDENKEN: Wenn du vor der Antwort nachdenkst, dann knapp in Stichpunkten: Ziel, Aufbau, Stolperstellen. Code schreibst du NIE ins Nachdenken — er kommt nur einmal, vollständig, in die Antwort.
"""

_REGELN_CHAT = """
DATEIEN: Hier im Chat kannst du keine Dateien erzeugen (PDF, Word, Excel …). Gib den Inhalt direkt in der Antwort (z. B. als Tabelle) und sag in einem Satz, dass Xera die Datei im Bereich Code oder Cowork erstellt. Such NICHT im Netz, wie man Dateien erzeugt.
"""

_REGELN_AGENTS = """
AGENTS (`agents_beauftragen`): Du machst die Arbeit — Agents sind deine Helfer. Gib Aufträge ab, wenn
- viel Arbeit auf einmal ansteht, die sich in unabhängige Teile zerlegen lässt (z. B. mehrere getrennte Dateien) → mehrere Aufträge GLEICHZEITIG (bis zu 4). Nie einen Auftrag in dieselbe Runde, der auf den Ergebnissen eines anderen aufbaut: Soll ein Agent eine Datei bauen und ein anderer sie testen, prüfen oder dokumentieren, sind das ZWEI Runden — der zweite findet die Datei sonst nicht. Eine einzelne Datei (z. B. ein Spiel) baut EIN Agent; getestet wird sie von Xera automatisch.
- ein Werkzeug nötig ist, das du selbst nicht hast: Dateien erzeugen (PDF, Word, Excel, Präsentation, Diagramm), auf Servern/Containern nachsehen oder ändern, Code ausführen, Projektdateien lesen/schreiben, gründliche Recherche über viele Quellen
Kleinigkeiten (eine Erklärung, ein Codeschnipsel) und RECHERCHE im Netz machst du selbst mit web_search — auch Vergleiche mehrerer Dinge. Will der Nutzer CODE (ein Programm, eine Seite, ein Spiel, ein Skript), schreibst du ihn SELBST als Codeblock mit datei= — das geht schneller und der Nutzer sieht den Fortschritt; Agents dafür nur, wenn der Nutzer sie ausdrücklich will oder mehrere Dateien gleichzeitig entstehen sollen. Will er ein ERGEBNIS, das erst durch Ausführen entsteht (Diagramm/Bild als PNG, berechnete Zahlen, Excel aus Daten), beauftragst du einen Agent — der führt Python aus und liefert die Datei. Recherche-Agents nur, wenn der Nutzer ausdrücklich eine gründliche/umfassende Recherche verlangt.
Ein Agent sieht das Gespräch NICHT. Jeder Auftrag muss für sich allein verständlich sein, aber KURZ: höchstens etwa 60 Wörter — Ziel, die nötigen Angaben (Namen, Zahlen, Pfade, Vorgaben des Nutzers), gewünschtes Ergebnis. Keine langen Spalten- oder Gliederungsvorgaben.
Gib in Aufträgen nur das in Auftrag, was der Nutzer gefragt hat — keine zusätzlichen Themen (z. B. keine Preise, wenn nach Versionen gefragt ist).
Du bekommst von jedem Agent eine Zusammenfassung zurück und schreibst dann SELBST die Antwort an den Nutzer — Download-Links und Quellen unverändert übernehmen.
Eine zweite Auftragsrunde NUR, wenn ein Auftrag fehlgeschlagen ist oder ein Folgeschritt auf den Ergebnissen aufbaut (z. B. aus den Recherchen eine Datei erstellen). Nie, um mehr Details nachzurecherchieren.

DATEIEN DES GESPRÄCHS: Alles, was in diesem Gespräch entstanden oder hochgeladen worden ist (deine Codeblöcke mit datei=, Dateien von Agents, Dokumente), liegt im Arbeitsordner des Gesprächs — die aktuelle Liste steht am Ende der Nutzerfrage. Du kannst sie selbst lesen (`read_file`), auflisten (`list_files`), gezielt ändern (`str_replace_file`) und testen (`datei_testen`: HTML läuft in einem echten Browser und wird mit Klicks und Tasten bedient).
- Eine BESTEHENDE Datei ändern, reparieren oder auf Fehler prüfen: zuerst `datei_testen` und `read_file`, dann gezielt `str_replace_file` je Stelle — mehrere Stellen in EINER Runde (alle Aufrufe gleichzeitig), jeder Aufruf testet automatisch. Schreib die Datei NICHT komplett neu und baue nichts nach. Einen Agent nur bei sehr vielen Änderungen — mit dem genauen Dateinamen aus der Liste.
- Zum Schluss sagst du dem Nutzer, was du geändert hast (kurze Liste) und wie der Test ausging, mit dem Download-Link.
- Agents bekommen die Dateiliste automatisch: nenne den Dateinamen und was zu tun ist. Verlange nichts, wofür es kein Werkzeug gibt.

KATALOG (kennung: wofür):
"""


def _katalog(mit_homelab: bool) -> list[dict]:
    agents = [
        a for a in AGENTS.values()
        if a.get("neubau") and (mit_homelab or not a.get("homelab"))
    ]
    return sorted(agents, key=lambda a: (a.get("kategorie", ""), a["id"]))


def _werkzeug(kennungen: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": "agents_beauftragen",
            "description": "Gibt 1 bis 4 Aufträge an Agents ab; sie laufen gleichzeitig. Jeder Agent sieht nur seinen Auftrag und liefert eine Zusammenfassung zurück.",
            "parameters": {
                "type": "object",
                "properties": {
                    "auftraege": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 4,
                        "items": {
                            "type": "object",
                            "properties": {
                                "kennung": {"type": "string", "enum": kennungen, "description": "Kennung aus dem Katalog"},
                                "auftrag": {"type": "string", "description": "Kurzer, für sich allein verständlicher Auftrag (höchstens ~60 Wörter) mit den nötigen Angaben"},
                            },
                            "required": ["kennung", "auftrag"],
                        },
                    },
                },
                "required": ["auftraege"],
            },
        },
    }


GRUNDWERKZEUGE = {"web_search", "web_fetch", "read_document"}
# Dateien des Gesprächs (Arbeitsordner) — für das Hauptmodell in Code/Cowork
# (seit 2026-10-17). Immer dieselbe Liste in derselben Reihenfolge: die
# Werkzeuge stehen im Prompt-Anfang, jede Änderung kostet den Prompt-Cache.
DATEI_WERKZEUGE = ("read_file", "list_files", "str_replace_file", "datei_testen")
DATEI_MAX_ZEICHEN = 60000      # read_file liefert ganze Dateien (WERKZEUG_MAX_ZEICHEN gilt für Webseiten)


def _dateiwerkzeuge(mit_agents: bool, mit_homelab: bool) -> list[dict]:
    """Im Homelab arbeitet das Modell am echten Server, nicht im Arbeitsordner."""
    return arbeitsbereich.schemas(DATEI_WERKZEUGE) if mit_agents and not mit_homelab else []

# "gründlich" & Co. → grösseres Recherche-Budget. (Eine Sperre für Recherche-
# Agents gab es kurz am 2026-10-02 — das Modell wich auf andere Agents aus.
# Stattdessen sind Agents jetzt schneller, siehe tools._suche_kompakt.)
_GRUENDLICH = re.compile(r"gr(ü|ue)ndlich|umfassend|ausf(ü|ue)hrlich|tiefgehend|detailliert|deep research", re.I)
MAX_RUNDEN = 6             # letzte Runde ohne Werkzeuge → sicher eine Antwort
# Code/Cowork: Dateien prüfen, lesen, an mehreren Stellen ändern, nochmals
# testen — das sind schnell 6+ Runden (seit 2026-10-17 mit Dateiwerkzeugen).
MAX_RUNDEN_ARBEIT = 14
VERLAENGERUNG = 4           # einmal so viele Runden mehr, wenn der letzte Datei-Test noch Fehler zeigt
# Token-Grenzen je Antwort. Ein Slot fasst 64k; vorher waren es 4 096, und ein
# ganzes HTML-Spiel kam abgeschnitten an (2026-10-15).
MAX_TOKENS_CHAT = 8192
MAX_TOKENS_ARBEIT = 16384   # Code, Cowork, Homelab — ganze Dateien
DENK_BUDGET = 4096          # Denk-Tokens im Denkmodus, danach muss es antworten
# Sampling im Denkmodus laut Qwen/Unsloth (seit 2026-10-16) — der Server ist
# auf die Instruct-Werte eingestellt (0.7 / 0.8 / presence 1.5), mit denen
# Qwen3.8 beim Denken eher abschweift. Gilt nur für die Denkrunde.
DENK_SAMPLING = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "presence_penalty": 0.0}
FORTSETZUNGEN = 2           # so oft bei abgeschnittener Antwort weiterschreiben
_HINWEIS_WEITER = ("(System: Deine letzte Antwort wurde wegen der Längengrenze mitten im Text abgeschnitten. "
                   "Schreib GENAU an der Abbruchstelle weiter — ohne Einleitung, ohne Wiederholung, ohne Kommentar. "
                   "Endete sie mitten in einem Wort, einer Zeile oder einem Code-Block, setz genau dort fort. Letzte Zeichen: {ende})")
_HINWEIS_WERKZEUG = ("(System: Dein letzter Werkzeugaufruf war zu lang und ist unterwegs abgebrochen — das Werkzeug lief nicht. "
                     "Gib keine ganzen Dateien als Werkzeug-Argument mit: schreib grossen Code als Code-Block direkt in die Antwort, "
                     "oder gib einem Agent nur einen kurzen Auftrag.)")


class _Gestoppt(Exception):
    """Stopp-Knopf, während auf llama-server gewartet wird."""


class _DenkenBeendet(Exception):
    """Xera beendet das Nachdenken (Code im Denken, Zeitgrenze, „Jetzt antworten“)."""

    def __init__(self, grund: str):
        super().__init__(grund)
        self.grund = grund


async def _llama_zeilen(anfrage: dict, timeout: httpx.Timeout, stop_event):
    """SSE-Zeilen von llama-server — bricht beim Stopp-Knopf SOFORT ab.

    Vorher wurde der Stopp nur geprüft, wenn eine Zeile ankam. Wartete die
    Anfrage noch auf ihren Slot (anderes Gespräch im selben Bereich) oder las
    llama-server gerade einen langen Prompt ein, kam minutenlang nichts — der
    Stopp griff nicht, und die Anfrage lief danach trotzdem (2026-10-15). Jetzt
    holt ein eigener Task die Zeilen; beim Stopp wird er abgebrochen, die
    Verbindung geht zu, und llama-server bricht die Aufgabe ab.
    """
    schlange: asyncio.Queue = asyncio.Queue()
    ende = object()

    async def holen():
        try:
            # Nie zwei Anfragen gleichzeitig an denselben Slot (slotsperre.py).
            async with slotsperre.slot(anfrage.get("id_slot")), httpx.AsyncClient(timeout=timeout) as client:
                await slotsperre.warten_bis_frei(client, config.LLAMA_API_URL, anfrage.get("id_slot"))
                await slotsperre.leeren_slot_anstossen(client, config.LLAMA_API_URL, anfrage.get("id_slot"))
                async with client.stream("POST", f"{config.LLAMA_API_URL}/v1/chat/completions", json=anfrage) as resp:
                    if resp.status_code >= 400:
                        raise _LlamaFehler(resp.status_code, (await resp.aread()).decode("utf-8", "replace"))
                    async for zeile in resp.aiter_lines():
                        await schlange.put(zeile)
            await schlange.put(ende)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            await schlange.put(e)

    holer = asyncio.create_task(holen())
    stopp = asyncio.create_task(stop_event.wait()) if stop_event else None
    try:
        while True:
            naechste = asyncio.create_task(schlange.get())
            fertig, _ = await asyncio.wait({naechste} | ({stopp} if stopp else set()),
                                           return_when=asyncio.FIRST_COMPLETED)
            if naechste not in fertig:
                naechste.cancel()
                raise _Gestoppt
            stueck = naechste.result()
            if stueck is ende:
                return
            if isinstance(stueck, Exception):
                raise stueck
            yield stueck
    finally:
        holer.cancel()
        if stopp:
            stopp.cancel()


class _LlamaFehler(Exception):
    def __init__(self, status: int, text: str):
        super().__init__(f"HTTP {status}")
        self.status, self.text = status, text

    @property
    def werkzeug_kaputt(self) -> bool:
        return "parse tool call" in self.text
WERKZEUG_MAX_ZEICHEN = 8000
DOKUMENT_MAX_ZEICHEN = 24000   # vorab gelesene Dokumente (~8k Tokens)

# Qwen-Ausrutscher (seit 2026-10-16): selten rutscht ein chinesisches Wort mitten in
# ein deutsches ("Elektronen缺 lassen", "einem内置 elektrischen Feld", "oder裸 auf";
# 2 von 132 Antworten seit 01.10.). Entfernt werden nur kurze CJK-Läufe, die direkt an
# einem lateinischen Buchstaben kleben — gewollte Zeichen ("auf Chinesisch 谢谢")
# stehen mit Leerzeichen davor und bleiben. Schreibt der Nutzer selbst CJK, gar nichts.
_CJK_LAUF = re.compile(r"[぀-ヿ㐀-䶿一-鿿가-힯豈-﫿]+")
_LATEIN = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]")


def _cjk_ausrutscher_weg(t: str, davor: str) -> str:
    def weg(m: re.Match) -> str:
        vor = t[m.start() - 1] if m.start() else davor[-1:]
        return "" if len(m.group()) <= 4 and vor and _LATEIN.match(vor) else m.group()
    return _CJK_LAUF.sub(weg, t)


# Frage bezieht sich auf ein hochgeladenes Dokument? (für das Vorab-Lesen)
_DOKUMENT_BEZUG = re.compile(
    r"dokument|datei|pdf|docx|word|excel|tabelle|anhang|hochgeladen|\bdrin\b|darin|darüber|steht|laut (dem|der|diesem)|"
    r"im text|vertrag|bericht|protokoll|rechnung|lebenslauf|offerte|angebot|seite \d|kapitel|abschnitt|fasse? .*zusammen",
    re.I)


def _dokumente_ohne_text(messages: list[dict]) -> list[str]:
    """Dokumente, die nur als Verweis ([Dokument-Datei: name]) im Gespräch
    stehen, nicht mit Text — neueste zuerst."""
    mit_text: set[str] = set()
    reihe: list[str] = []
    for m in reversed(messages):
        c = m.get("content")
        texte = [p.get("text", "") for p in c if isinstance(p, dict)] if isinstance(c, list) else [c or ""]
        for t in texte:
            mit_text.update(re.findall(r"\[Dokument: ([^\]\n]+)\]", t))
            for name in re.findall(r"\[Dokument-Datei: ([^\]\n]+)\]", t):
                if name not in reihe:
                    reihe.append(name)
    return [n for n in reihe if n not in mit_text]


def _dokumente_im_gespraech(messages: list[dict]) -> set[str]:
    """Dateinamen, die im Gespräch genannt sind. read_document sucht sonst im
    ganzen Upload-Ordner — also auch in Dateien anderer Nutzer."""
    namen: set[str] = set()
    for m in messages:
        c = m.get("content")
        texte = [p.get("text", "") for p in c if isinstance(p, dict)] if isinstance(c, list) else [c or ""]
        for t in texte:
            namen.update(re.findall(r"\[Dokument(?:-Datei)?: ([^\]\n]+)\]", t))
    return namen


# Feste Slots fürs Hauptmodell, je Bereich einer (anderer Systemprompt):
# Chat = 0, Code/Cowork = 1, Homelab = 5. Agents laufen auf 2–5 (auftraege.py),
# Nebenaufgaben (learning.py, kontext.py) auf 4 — den nimmt erst der dritte
# gleichzeitige Agent (bis 2026-10-16: Slot 2, und der erste Agent nach einer
# Antwort fand seinen Slot von der Lernnotiz belegt). Homelab ist am unwichtigsten
# und teilt sich Slot 5 mit dem vierten parallelen Agent. Das Hybrid-Modell
# kann seinen Cache nur bis zum letzten Checkpoint zurückdrehen — fremde
# Prompts im selben Slot heissen alles neu einlesen.
SLOT_CHAT, SLOT_CODE, SLOT_HOMELAB = 0, 1, 5
HINTERGRUND_KOPF = "[Hintergrund für dieses Gespräch — keine Frage, nicht darauf antworten]\n\n"


def _slot(mit_agents: bool, mit_homelab: bool) -> int:
    if not mit_agents:
        return SLOT_CHAT
    return SLOT_HOMELAB if mit_homelab else SLOT_CODE


def _systemprompt(mit_agents: bool, katalog: list[dict]) -> str:
    # Reihenfolge = Prompt-Cache: was sich nie ändert vorne (Systemprompt,
    # Regeln, Katalog), was je Nutzer/Tag/Anfrage wechselt hinten. Ändert sich
    # etwas vorne, muss llama-server alles danach neu einlesen (~200 Tokens/s).
    prompt = SYSTEM_PROMPT + "\n" + _REGELN
    if mit_agents:
        prompt += _REGELN_AGENTS + "\n".join(f"- {a['id'][len('neu_'):]}: {a['description']}" for a in katalog)
    else:
        prompt += _REGELN_CHAT
    return prompt


def _datumszeile() -> str:
    return f"Heutiges Datum: {datetime.now().strftime('%A, %d. %B %Y')}"


def _grundwerkzeuge(mit_dokumenten: bool) -> list[dict]:
    grund = get_tools_for_agent(GRUNDWERKZEUGE)
    if not mit_dokumenten:
        # Sonst erfindet das Modell Dateinamen und probiert sie durch.
        grund = [t for t in grund if t["function"]["name"] != "read_document"]
    return grund


# Aufwärmen: Nach einem Start von llama-server sind alle Slots leer, und die
# erste Frage je Bereich müsste den ganzen Systemprompt einlesen (Chat ~2 300,
# Code ~4 700 Tokens → 12–25 s, kalt nach dem Booten bis 45 s). Darum schickt
# Xera die echten Prompts (gleicher Systemprompt, gleiche Werkzeuge, Anfang der
# Hintergrund-Nachricht) vorab — nur in leere Slots, damit kein laufendes
# Gespräch verdrängt wird. Homelab (Slot 5) bewusst nicht — unwichtigster
# Bereich, dafür ist keine Vorlast gewünscht.
_BEREICHE = [  # (Name, mit_agents, mit_homelab)
    ("chat", False, False),
    ("code", True, False),
]


async def _slots(client: httpx.AsyncClient) -> list[dict]:
    r = await client.get(f"{config.LLAMA_API_URL}/slots")
    r.raise_for_status()
    return r.json()


# Je Start von llama-server wird jeder Slot höchstens einmal aufgewärmt. Einen
# Neustart erkennt man an den Task-Nummern: sie beginnen wieder bei 0.
_gewaermt: set[int] = set()
_hoechster_task = -1


async def aufwaermen() -> None:
    global _hoechster_task
    timeout = httpx.Timeout(10.0, read=300.0, write=30.0, pool=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        task = max((s.get("id_task") or -1) for s in await _slots(client))
        if task < _hoechster_task:
            _gewaermt.clear()  # llama-server wurde neu gestartet
        _hoechster_task = task
        for name, mit_agents, mit_homelab in _BEREICHE:
            slot = _slot(mit_agents, mit_homelab)
            if slot in _gewaermt:
                continue
            slots = {s["id"]: s for s in await _slots(client)}
            if slots.get(slot, {}).get("n_prompt_tokens"):
                _gewaermt.add(slot)
                continue  # Slot hat schon einen Prompt — nicht verdrängen
            katalog = _katalog(mit_homelab)
            # Genau wie in antworten(): Grund-, Datei-, Agent-Werkzeug.
            werkzeuge = _grundwerkzeuge(False) + _dateiwerkzeuge(mit_agents, mit_homelab)
            if mit_agents:
                werkzeuge = werkzeuge + [_werkzeug([a["id"][len("neu_"):] for a in katalog])]
            anfrage = {
                "model": "xera-ai",
                "messages": [
                    {"role": "system", "content": _systemprompt(mit_agents, katalog)},
                    {"role": "user", "content": HINTERGRUND_KOPF + _datumszeile()},
                ],
                "tools": werkzeuge,
                "tool_choice": "auto",
                "max_tokens": 1,
                "stream": False,
                "id_slot": slot,
            }
            t0 = datetime.now()
            async with slotsperre.slot(slot):
                # Leerer Slot: so holt llama-server den Prompt aus dem RAM-Cache statt
                # ihn nach jedem Neuladen von xera-ai neu einzulesen (~40 s).
                await slotsperre.leeren_slot_anstossen(client, config.LLAMA_API_URL, slot)
                r = await client.post(f"{config.LLAMA_API_URL}/v1/chat/completions", json=anfrage)
            r.raise_for_status()
            _gewaermt.add(slot)
            _hoechster_task = max(_hoechster_task, max((s.get("id_task") or -1) for s in await _slots(client)))
            nutzung = r.json().get("usage") or {}
            _log.info("aufwaermen: %s (Slot %s) %s Tokens in %.1f s", name, slot,
                      nutzung.get("prompt_tokens"), (datetime.now() - t0).total_seconds())


async def aufwaerm_schleife() -> None:
    """Läuft im Hintergrund (main.py startup). Prüft jede Minute, ob
    llama-server leere Slots hat (Neustart) und wärmt sie auf."""
    while True:
        await kontext.fenster_aktualisieren()
        try:
            arbeitsbereich.aufraeumen()
        except Exception as e:  # pragma: no cover
            _log.warning("aufraeumen: %s", e)
        try:
            await aufwaermen()
        except Exception as e:  # llama-server aus / startet gerade
            _log.debug("aufwaermen: %s", e)
        await asyncio.sleep(60)


_HINWEIS_LEER = ("(System: Deine letzte Antwort war leer. Werkzeuge sind jetzt aus. Schreib die Antwort an den Nutzer: "
                 "was du gemacht oder herausgefunden hast, das Testergebnis und den Download-Link, falls es eine Datei gibt.)")


def _datei_merken(geaendert: dict, werkzeug: str, ausgabe: str) -> None:
    """Geänderte Dateien dieser Antwort mit Link und letztem Testergebnis merken."""
    if werkzeug == "str_replace_file":
        m = re.search(r"\[([^\]]+)\]\((/api/download/[^)\s]+)\)", ausgabe)
        if m:
            geaendert[m.group(1)] = (m.group(2), geaendert.get(m.group(1), ("", ""))[1])
    t = re.search(r"Automatischer Test von ([^\s(]+)[^:\n]*\):\s*(keine Fehler|FEHLER)", ausgabe)
    if t and t.group(1) in geaendert:
        art = "Im Browser getestet" if "im Browser" in ausgabe else "Geprüft"
        if t.group(2) == "keine Fehler":
            ergebnis = f"{art}: keine Fehler"
        else:
            # Welche Fehler, nicht nur „noch Fehler“ (seit 2026-10-17, Mario v5b).
            fehler = re.findall(r"^- (.+)$", ausgabe[t.end():], re.M)[:2]
            ergebnis = f"{art}: noch Fehler" + (" — " + "; ".join(f[:160] for f in fehler) if fehler else "")
        geaendert[t.group(1)] = (geaendert[t.group(1)][0], ergebnis)


async def _projektdateien_uebernehmen(sb: dict | None, projekt_id: int | None) -> None:
    """Dateien eines Vorhabens (Cowork) vollständig als Text in den Arbeitsordner —
    im Prompt steht nur ein Auszug (8 000 Zeichen je Datei, database.projektwissen)."""
    if sb is None or projekt_id is None:
        return
    from pathlib import Path
    from . import database as db
    basis = (config.BASE_DIR / "data" / "projekte").resolve()
    conn = db.get_db()
    try:
        zeilen = conn.execute("SELECT name, pfad FROM projekt_dateien WHERE projekt_id=?", (projekt_id,)).fetchall()
    finally:
        conn.close()
    for z in zeilen[:20]:
        quelle = Path(z["pfad"]).resolve()
        if basis not in quelle.parents:
            continue
        name = z["name"] if z["name"].lower().endswith(".txt") else z["name"] + ".txt"
        try:
            await arbeitsbereich.einspielen(sb, quelle, name)
        except Exception as e:  # pragma: no cover
            _log.warning("projektdatei %s: %s", name, e)


def _liste_anhaengen(verlauf: list[dict], liste: str) -> list[dict]:
    """Dateiliste an die (letzte) Nutzerfrage hängen — hinten, damit der
    Prompt-Cache davor gültig bleibt."""
    hinweis = "\n\n[Dateien im Arbeitsordner dieses Gesprächs:\n" + liste + "]"
    for i in range(len(verlauf) - 1, -1, -1):
        m = verlauf[i]
        if m.get("role") != "user":
            continue
        c = m.get("content")
        if isinstance(c, list):
            neu = {**m, "content": c + [{"type": "text", "text": hinweis.strip()}]}
        else:
            neu = {**m, "content": (c or "") + hinweis}
        return verlauf[:i] + [neu] + verlauf[i + 1:]
    return verlauf


async def _ausfuehren(name: str, args: dict, erlaubte_dokumente: set[str]) -> dict:
    if name in DATEI_WERKZEUGE:
        # Arbeitsordner des Gesprächs (Sandkasten) — keine Freigabe nötig.
        if SANDBOX.get() is None:
            return {"success": False, "output": "Dateien gibt es hier nicht."}
        try:
            return await execute_tool(name, args)
        except Exception as e:  # pragma: no cover
            return {"success": False, "output": f"Fehler: {e}"}
    if name not in GRUNDWERKZEUGE:
        return {"success": False, "output": f"Werkzeug '{name}' gibt es hier nicht."}
    if name == "read_document":
        datei = str(args.get("filename", "")).strip()
        treffer = next((d for d in erlaubte_dokumente if d == datei or d.endswith("_" + datei)), None)
        if not treffer:
            return {"success": False, "output": "Dieses Dokument gehört nicht zum Gespräch."}
        args = {**args, "filename": treffer}
    stufe = classify_tool(name, args)
    if is_blocked(stufe) or needs_approval(stufe):
        return {"success": False, "output": "Diese Adresse ist im Chat nicht erlaubt (internes Netz)."}
    try:
        return await execute_tool(name, args)
    except Exception as e:  # pragma: no cover
        return {"success": False, "output": f"Fehler: {e}"}


TEXTAUFRUF = "<tool_call>"


def _textaufrufe(text: str) -> list[dict]:
    """Werkzeugaufrufe, die das Modell als Text geschrieben hat (Qwen-XML):

        <tool_call><function=NAME><parameter=KEY>WERT</parameter>…</function></tool_call>

    llama.cpp erkennt sie nicht, wenn der Name unbekannt ist — so geschehen
    mit dem alten Namen ``agent_beauftragen``. Der wird auf
    ``agents_beauftragen`` umgebogen."""
    aufrufe = []
    for block in re.findall(r"<tool_call>(.*?)(?:</tool_call>|$)", text, re.S):
        m = re.search(r"<function=([\w\-]+)>", block)
        if not m:
            continue
        name = m.group(1)
        args: dict = {}
        for key, wert in re.findall(r"<parameter=([\w\-]+)>\s*(.*?)\s*</parameter>", block, re.S):
            try:
                args[key] = json.loads(wert)
            except (json.JSONDecodeError, ValueError):
                args[key] = wert
        if name == "agent_beauftragen":
            name, args = "agents_beauftragen", {"auftraege": [{"kennung": args.get("kennung", ""), "auftrag": args.get("auftrag", "")}]}
        aufrufe.append({"id": "", "name": name, "args": json.dumps(args, ensure_ascii=False)})
    return aufrufe


def _letzte_frage(messages: list[dict]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            c = m.get("content")
            if isinstance(c, list):
                return " ".join(p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text").strip()
            return str(c or "").strip()
    return ""


def _sse(daten: dict) -> str:
    return f"data: {json.dumps(daten, ensure_ascii=False)}\n\n"


def _nachrichten_aufbereiten(messages: list[dict]) -> list[dict]:
    """Wie in chat.py: Bilder bleiben als Teile (das Modell sieht sie selbst),
    reine Textteile werden zusammengefügt."""
    aus = []
    for m in messages:
        c = m.get("content")
        if isinstance(c, list) and not any(p.get("type") == "image_url" for p in c):
            aus.append({**m, "content": " ".join(p.get("text", "") for p in c if p.get("type") == "text")})
        else:
            aus.append(m)
    return aus


# Exakter Verlauf der letzten Antwort je Gespräch (seit 2026-10-16).
# Die Oberfläche schickt bei der nächsten Frage nur den sichtbaren Text — ohne
# Werkzeugrunden und Agent-Ergebnisse. Damit passte der Anfang nicht mehr zu
# dem, was llama-server im Slot hat, und das Hybrid-Modell musste alles ab der
# ersten Nutzerfrage neu einlesen (Chat 512: 12 700 Tokens, 2 min). Ist das
# Gespräch bis auf die neue Frage unverändert, geht jetzt der gemerkte Verlauf
# hinaus — llama-server liest nur die neue Frage.
_VERLAEUFE: dict[int, dict] = {}
_VERLAEUFE_MAX = 40
WIEDERVERWENDEN_MAX_ANTEIL = 0.5   # Werkzeugrunden nur, solange sie nicht zu viel Platz brauchen


def _signatur(messages: list[dict]) -> list[tuple[str, str]] | None:
    """Vergleichbare Form des Gesprächs. Ein Dokument steht beim ersten Mal mit
    Text in der Nachricht („[Dokument: name]\n…“), danach schickt die
    Oberfläche nur noch den Verweis („[Dokument-Datei: name]“) — beides zählt
    als dasselbe, sonst ginge der Verlauf mit dem Dokumenttext nie wieder
    hinaus und das Modell müsste bei jeder Folgefrage neu lesen (oder rät)."""
    aus = []
    for m in messages:
        c = m.get("content")
        if isinstance(c, list):
            if any(isinstance(t, dict) and t.get("type") == "image_url" for t in c):
                return None  # Bilder: nicht vergleichbar, normaler Weg
            teile = []
            for t in c:
                text = t.get("text", "") if isinstance(t, dict) else ""
                d = re.match(r"\[Dokument: ([^\]\n]+)\]", text)
                teile.append(f"[Dokument-Datei: {d.group(1)}]" if d else text)
            c = " ".join(teile)
        aus.append((str(m.get("role")), re.sub(r"\s+", " ", str(c or "")).strip()))
    return aus


def _verlauf_merken(session_id, messages: list[dict], sichtbar: str, verlauf: list[dict], antwort: str, slot) -> None:
    if not session_id:
        return
    sig = _signatur(messages)
    if sig is None:
        _VERLAEUFE.pop(session_id, None)
        return
    _log.info("verlauf: merke Sitzung %s (%s Nachrichten, Slot %s)", session_id, len(verlauf) + 1, slot)
    _VERLAEUFE[session_id] = {"signatur": sig + [("assistant", re.sub(r"\s+", " ", sichtbar).strip())], "slot": slot,
                              "verlauf": verlauf + [{"role": "assistant", "content": antwort}]}
    while len(_VERLAEUFE) > _VERLAEUFE_MAX:
        _VERLAEUFE.pop(next(iter(_VERLAEUFE)))


def _verlauf_wiederverwenden(session_id, messages: list[dict], slot) -> list[dict] | None:
    gemerkt = _VERLAEUFE.pop(session_id, None) if session_id else None
    if not gemerkt or gemerkt["slot"] != slot or not messages or messages[-1].get("role") != "user":
        if gemerkt:
            _log.info("verlauf: Sitzung %s — anderer Slot (%s/%s), normaler Weg", session_id, slot, gemerkt.get("slot"))
        return None
    sig = _signatur(messages[:-1])
    if sig is None or sig != gemerkt["signatur"]:
        alt = gemerkt["signatur"]
        unterschied = next((i for i, (a, b) in enumerate(zip(sig or [], alt)) if a != b), None)
        _log.info("verlauf: Sitzung %s — Signatur passt nicht: %s vs %s Nachrichten, erste Abweichung %s: %r vs %r",
                     session_id, len(sig or []), len(alt), unterschied,
                     (sig or [])[unterschied][1][:120] if unterschied is not None else "",
                     alt[unterschied][1][:120] if unterschied is not None else "")
        return None
    verlauf = gemerkt["verlauf"] + _nachrichten_aufbereiten(messages[-1:])
    groesse = sum(len(json.dumps(m, ensure_ascii=False)) for m in verlauf) / kontext.ZEICHEN_PRO_TOKEN
    if groesse + kontext.RESERVE >= kontext.FENSTER * WIEDERVERWENDEN_MAX_ANTEIL:
        return None  # zu gross — normaler Weg, der lässt die Werkzeugrunden weg
    return verlauf


def _einlese_meldung(p: dict) -> str:
    """„liest das Gespräch ein … 46 %“ — nur bei spürbar langem Einlesen.
    ``processed`` zählt den Cache mit (bis 2026-10-20 übersehen: mit Cache sprang die
    Anzeige über 100 % oder blieb ganz weg)."""
    try:
        neu = int(p.get("total", 0)) - int(p.get("cache", 0))
        fertig = int(p.get("processed", 0)) - int(p.get("cache", 0))
    except (TypeError, ValueError):
        return ""
    if neu < 1500 or fertig >= neu:
        return ""
    return f"liest das Gespräch ein ({neu:,} Tokens) … {int(100 * fertig / neu)} %".replace(",", " ")


async def _nachfragen(verlauf: list[dict], inhalt: str, auftrag: str, slot) -> str:
    """Kurze Rückfrage im selben Slot (gleicher Anfang → aus dem Cache)."""
    anfrage = {"model": "xera-ai", "stream": False, "max_tokens": 3000, "temperature": 0.3,
               "messages": verlauf + [{"role": "assistant", "content": inhalt}, {"role": "user", "content": auftrag}]}
    if slot is not None:
        anfrage["id_slot"] = slot
    async with slotsperre.slot(slot), httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=600.0, write=30.0, pool=10.0)) as client:
        r = await client.post(f"{config.LLAMA_API_URL}/v1/chat/completions", json=anfrage)
        r.raise_for_status()
        return r.json()["choices"][0]["message"].get("content") or ""


async def _code_nachbearbeiten(inhalt: str, sichtbar: str, frage: str, nachfragen):
    """Codeblöcke der fertigen Antwort: prüfen, korrigieren lassen, als Datei
    ablegen (codepruefung.py). Liefert SSE-Stücke und ("sichtbar", text),
    wenn sich der angezeigte Text geändert hat."""
    gewuenscht = codepruefung.datei_gewuenscht(frage)
    # Im ganzen sichtbaren Text suchen, nicht nur in der letzten Runde: bei
    # einer Fortsetzung (Antwort zu lang) steht ein Codeblock auf zwei Runden.
    kandidaten = [b for b in codepruefung.bloecke(sichtbar) if codepruefung.dateiwuerdig(b, gewuenscht)][:4]
    if not kandidaten:
        return
    sb = SANDBOX.get()
    neu_sichtbar = sichtbar
    zeilen = []
    for i, b in enumerate(kandidaten):
        name = codepruefung.dateiname_fuer(b, i)
        code, fehler, korrigiert = b.code, None, 0
        async for e in codepruefung.pruefen_und_flicken(b.code, b.sprache, sb, nachfragen, name):
            if e[0] == "status":
                yield _sse({"type": "status", "status": e[1]})
            else:
                _, code, fehler, korrigiert = e
        if code != b.code and b.code in neu_sichtbar:
            neu_sichtbar = neu_sichtbar.replace(b.code, code, 1)
        try:
            # Im Arbeitsordner des Gesprächs UND als Download (seit 2026-10-17) —
            # Folgefragen und Agents finden die Datei dort unter demselben Namen.
            url, name = await arbeitsbereich.ablegen(sb, code, name)
        except OSError as e:  # pragma: no cover
            _log.warning("datei_ablegen: %s", e)
            continue
        satz = codepruefung.bericht(fehler, korrigiert, b.sprache)
        zeilen.append(f"**Datei:** [{name}]({url})" + (f" · {satz}" if satz else ""))
        _log.info("vermittler: Datei %s (%s Zeilen, %s) %s", name, len(code.splitlines()), b.sprache, satz)
    if neu_sichtbar != sichtbar:
        yield _sse({"type": "ersetzen", "content": neu_sichtbar})
        yield ("sichtbar", neu_sichtbar)
    if zeilen:
        yield _sse({"content": "\n\n" + "\n\n".join(zeilen)})


async def antworten(
    messages: list[dict],
    *,
    user_id: str,
    session_id: int | None,
    projektwissen: str = "",
    denken: bool = False,
    mit_homelab: bool = False,
    websuche: bool = False,
    mit_agents: bool = True,
    vorgabe_agent: str | None = None,
    stop_event=None,
    projekt_id: int | None = None,
    aufwand_stufe: str = "aus",
    denk_ende=None,
) -> AsyncGenerator[str, None]:
    # Denkaufwand (seit 2026-10-19, aufwand.py): Stufe statt an/aus. Das alte
    # „denken=True“ heisst „mittel“.
    stufe = aufwand.stufe(aufwand_stufe)
    if stufe == "aus" and denken:
        stufe = "mittel"
    denken = stufe != "aus"
    denk_budget = aufwand.budget(stufe)
    aufwand.AKTUELL.set(stufe)   # Agents dieser Anfrage denken mit (gedeckelt, agents/base.py)
    # Höchstens 3 Seiten / 4 Suchen pro Frage — für das Modell und alle Agents
    # zusammen. Mehr Details holt sich der Nutzer mit einer Nachfrage.
    gruendlich = bool(_GRUENDLICH.search(_letzte_frage(messages)))
    RECHERCHE_BUDGET.set({"seiten": 8, "suchen": 8} if gruendlich else {"seiten": 3, "suchen": 4})
    katalog = _katalog(mit_homelab)
    kennungen = [a["id"][len("neu_"):] for a in katalog]

    prompt = _systemprompt(mit_agents, katalog)
    # Alles, was wechselt (Lernnotizen, Datum, Vorgabe, Projektwissen), steht
    # NICHT im Systemprompt, sondern in einer eigenen Hintergrund-Nachricht
    # danach. llama.cpp legt am Anfang jeder Nutzernachricht einen Checkpoint
    # an; ändern sich z. B. die Lernnotizen, wird nur diese kurze Nachricht neu
    # eingelesen statt des ganzen Prompts (Hybrid-Modell: kein Zurückdrehen
    # ohne Checkpoint).
    hintergrund = [_datumszeile()]
    lernen = get_learnings_context(user_id) if user_id else ""
    if lernen:
        hintergrund.append(lernen)
    if mit_agents and vorgabe_agent:
        hintergrund.append(f"VORGABE: Der Nutzer hat für diese Frage ausdrücklich den Agent `{vorgabe_agent.removeprefix('neu_')}` gewählt. "
                           "Beauftrage ihn (allein oder zusammen mit weiteren).")
    if projektwissen:
        hintergrund.append(projektwissen)
    vorspann = [
        {"role": "user", "content": HINTERGRUND_KOPF + "\n\n".join(hintergrund)},
        {"role": "assistant", "content": "Verstanden."},
    ]

    # Werkzeuge vorab: die Zusammenfassung unten braucht dieselbe Liste (Prompt-Cache).
    erlaubte_dokumente = _dokumente_im_gespraech(messages)
    grund = _grundwerkzeuge(bool(erlaubte_dokumente))
    beauftragen = _werkzeug(kennungen)
    sb = SANDBOX.get()
    datei_wz = _dateiwerkzeuge(mit_agents, mit_homelab) if sb is not None else []
    werkzeuge_alle = grund + datei_wz + [beauftragen] if mit_agents else grund + datei_wz

    # Kontextschutz: gespeicherte Zusammenfassung einsetzen, bei vollem
    # Fenster (neu) zusammenfassen — statt dass llama-server ablehnt.
    gespraech, verdichtet = kontext.anwenden(messages, session_id)
    if kontext.schaetzen(gespraech) + kontext.RESERVE >= kontext.FENSTER * kontext.SCHWELLE_AUTO:
        yield _sse({"type": "status", "status": "fasst das bisherige Gespräch zusammen"})
        fortschritt: dict = {}

        async def im_gespraech(bisher: list[dict], anker: str) -> str:
            # Im Slot des Gesprächs, gleicher Systemprompt, gleiche Werkzeuge,
            # gleicher Verlauf wie zuletzt → aus dem Cache (kontext.verdichten).
            auftrag = kontext.AUFTRAG_IM_GESPRAECH
            if anker:
                auftrag += (f"\n\nDie Nachrichten ab der Nutzerfrage, die mit »{anker}« beginnt, bleiben wörtlich "
                            "erhalten — die musst du nicht zusammenfassen.")
            z = {"model": "xera-ai", "max_tokens": 3000, "temperature": 0.3, "id_slot": _slot(mit_agents, mit_homelab),
                 "messages": [{"role": "system", "content": prompt}] + vorspann + _nachrichten_aufbereiten(bisher)
                 + [{"role": "user", "content": auftrag}]}
            if werkzeuge_alle:
                z["tools"], z["tool_choice"] = werkzeuge_alle, "none"
            return await kontext.strom(z, fortschritt)

        aufgabe = asyncio.ensure_future(kontext.verdichten(messages, session_id, im_gespraech=im_gespraech,
                                                           fortschritt=fortschritt))
        letzte_meldung = ""
        try:
            while not aufgabe.done():
                await asyncio.wait({aufgabe}, timeout=3)
                if stop_event is not None and stop_event.is_set():
                    yield _sse({"type": "stopped"})
                    return
                meldung = _einlese_meldung(fortschritt).replace("liest das Gespräch ein", "fasst zusammen — liest das Gespräch ein")
                if meldung and meldung != letzte_meldung:
                    letzte_meldung = meldung
                    yield _sse({"type": "status", "status": meldung})
            gespraech, verdichtet = aufgabe.result()
        finally:
            if not aufgabe.done():
                aufgabe.cancel()

    verlauf = [{"role": "system", "content": prompt}] + vorspann + _nachrichten_aufbereiten(gespraech)
    gemerkt = None if verdichtet or websuche else _verlauf_wiederverwenden(session_id, messages, _slot(mit_agents, mit_homelab))
    if gemerkt is not None:
        verlauf = gemerkt
        _log.info("vermittler: Sitzung %s — gemerkter Verlauf (%s Nachrichten), nur die neue Frage wird eingelesen",
                  session_id, len(verlauf))
    anfrage = {
        "model": "xera-ai",
        "messages": verlauf,
        "max_tokens": (MAX_TOKENS_ARBEIT if mit_agents else MAX_TOKENS_CHAT) + denk_budget,
        "stream": True,
        "stream_options": {"include_usage": True},
        # Fortschritt beim Einlesen (seit 2026-10-16): Liest llama-server ein
        # langes Gespräch neu ein (Chat 512: 12 700 Tokens, 2 min), sah man
        # nur „denkt nach“ — und hielt es für einen Hänger.
        "return_progress": True,
        "id_slot": _slot(mit_agents, mit_homelab),
    }
    aufwand.anfrage_ergaenzen(anfrage, stufe)

    if datei_wz:
        # Ein Ablageort pro Gespräch (seit 2026-10-17): Uploads in den
        # Arbeitsordner, und die Frage nennt alle Dateien des Gesprächs — sonst
        # rät das Modell Dateinamen, und Agents suchen (Gespräch 580: 40 min).
        await arbeitsbereich.dokumente_uebernehmen(sb, erlaubte_dokumente)
        await _projektdateien_uebernehmen(sb, projekt_id)
        liste = await arbeitsbereich.dateiliste_text(sb)
        if liste:
            verlauf = _liste_anhaengen(verlauf, liste)
    timeout = httpx.Timeout(10.0, read=900.0 if denken else 300.0, write=30.0, pool=10.0)
    belegt = 0
    sichtbar = ""          # alles, was diese Antwort an Text gezeigt hat
    frage_jetzt = _letzte_frage(messages)
    auftragsrunden = 0
    werkzeugrunden = 0
    fortsetzungen = 0
    werkzeug_neu_versucht = False
    schluss_gesagt = False
    leer_neu_versucht = False
    geaendert: dict[str, tuple[str, str]] = {}   # Datei → (Download-Link, letztes Testergebnis)

    def _texte(m: dict) -> list[str]:
        c = m.get("content")
        return [p.get("text", "") for p in c if isinstance(p, dict)] if isinstance(c, list) else [c or ""]
    cjk_im_gespraech = any(_CJK_LAUF.search(t) for m in messages if m.get("role") == "user" for t in _texte(m))

    def text_sse(t: str) -> str:
        nonlocal sichtbar
        if not cjk_im_gespraech:
            t = _cjk_ausrutscher_weg(t, sichtbar)
        sichtbar += t
        return _sse({"content": t})

    def kontext_ereignis() -> str:
        geschaetzt = int(sum(len(json.dumps(m, ensure_ascii=False)) for m in verlauf) / kontext.ZEICHEN_PRO_TOKEN)
        return _sse(kontext.ereignis(belegt or geschaetzt, verdichtet))

    # Dokument vorab lesen (seit 2026-10-16): Bei Folgefragen schickt die
    # Oberfläche nur den Verweis aufs Dokument. Qwen3.8 rief read_document
    # dann nicht auf und erfand Inhalte („Terminverschiebung um zwei Wochen“
    # statt „Lieferverzug Server“) — trotz ausdrücklicher Regel.
    if gemerkt is None and _DOKUMENT_BEZUG.search(_letzte_frage(messages)):
        for name in _dokumente_ohne_text(messages)[:2]:
            aufruf_id = f"call_dok_{len(verlauf)}"
            yield _sse({"type": "tool_call", "id": aufruf_id, "name": "read_document", "args": {"filename": name}, "level": "READ"})
            ergebnis = await _ausfuehren("read_document", {"filename": name}, erlaubte_dokumente)
            ausgabe = ergebnis["output"]
            yield _sse({"type": "tool_result", "id": aufruf_id, "name": "read_document", "success": ergebnis["success"],
                        "output": ausgabe[:300] + ("…" if len(ausgabe) > 300 else "")})
            verlauf = verlauf + [
                {"role": "assistant", "content": None, "tool_calls": [{"id": aufruf_id, "type": "function",
                 "function": {"name": "read_document", "arguments": json.dumps({"filename": name}, ensure_ascii=False)}}]},
                {"role": "tool", "tool_call_id": aufruf_id, "content": ausgabe[:DOKUMENT_MAX_ZEICHEN]},
            ]

    if websuche:
        frage = _letzte_frage(messages)[:300]
        if frage:
            aufruf_id = "call_vorab"
            yield _sse({"type": "tool_call", "id": aufruf_id, "name": "web_search", "args": {"query": frage}, "level": "READ"})
            ergebnis = await _ausfuehren("web_search", {"query": frage}, erlaubte_dokumente)
            log_action(user_id, session_id, "web_search", {"query": frage}, "read", ergebnis["success"], ergebnis["output"])
            ausgabe = ergebnis["output"]
            yield _sse({"type": "tool_result", "id": aufruf_id, "name": "web_search", "success": ergebnis["success"],
                        "output": ausgabe[:300] + ("…" if len(ausgabe) > 300 else "")})
            verlauf = verlauf + [
                {"role": "assistant", "content": None, "tool_calls": [{"id": aufruf_id, "type": "function",
                 "function": {"name": "web_search", "arguments": json.dumps({"query": frage}, ensure_ascii=False)}}]},
                {"role": "tool", "tool_call_id": aufruf_id, "content": ausgabe[:WERKZEUG_MAX_ZEICHEN]},
            ]

    max_runden = MAX_RUNDEN_ARBEIT if mit_agents else MAX_RUNDEN
    verlaengert = False
    for runde in range(max_runden + VERLAENGERUNG + FORTSETZUNGEN + 2):
        if (werkzeugrunden >= max_runden - 1 and not verlaengert and runde > 0
                and any("noch Fehler" in t for _, t in geaendert.values())):
            # Mitten in einer Reparatur, letzter Test noch rot: ein paar Runden mehr
            # statt Schluss (Mario v5b: 11 Korrekturen, die letzte baute einen neuen
            # Fehler ein, dann waren die Runden aus — die Antwort war nur „noch Fehler“).
            verlaengert = True
            max_runden += VERLAENGERUNG
            _log.info("vermittler: letzter Test noch mit Fehlern — %s Runden mehr", VERLAENGERUNG)
        letzte = werkzeugrunden >= max_runden - 1
        # Werkzeugliste bleibt immer gleich (Prompt-Cache): Ein weiterer Agent-
        # Auftrag nach zwei Runden wird unten abgelehnt, in der letzten Runde gilt
        # tool_choice "none" — die Werkzeuge stehen weiter im Prompt, nur Aufrufe
        # sind aus. Vorher fielen sie weg, der Prompt-Anfang änderte sich, und
        # llama-server las das ganze Gespräch neu ein (Gespräch 580: 13 500 Tokens, 75 s).
        werkzeuge = grund + datei_wz + [beauftragen] if mit_agents else grund + datei_wz
        if letzte and runde > 0 and not schluss_gesagt:
            # Ohne diesen Hinweis schreibt das Modell den nächsten Aufruf als Text hin.
            schluss_gesagt = True
            verlauf = verlauf + [{"role": "user", "content": "(System: Keine weiteren Werkzeuge mehr. Antworte jetzt vollständig mit dem, was du gefunden hast, mit Quellen.)"}]
        anfrage = {k: v for k, v in anfrage.items() if k not in ("tools", "tool_choice")}
        anfrage["messages"] = verlauf
        if werkzeuge:
            anfrage["tools"] = werkzeuge
            anfrage["tool_choice"] = "none" if letzte else "auto"

        aufrufe: dict[int, dict] = {}
        inhalt = ""
        gezeigt = 0          # so viel von `inhalt` ist schon an die Oberfläche
        textaufruf = False   # Modell schreibt einen Werkzeugaufruf als Text
        ende = None          # finish_reason: "stop", "length", "tool_calls"
        gedacht = False
        gedanken = ""          # Denktext dieser Runde (für Code-Erkennung und Plan)
        denk_start = None
        geprueft_bis = 0
        letzte_meldung = ""
        if slotsperre.belegt(anfrage.get("id_slot")):
            yield _sse({"type": "status", "status": "wartet, bis die laufende Antwort in diesem Bereich fertig ist"})
        try:
            async with contextlib.aclosing(_llama_zeilen(anfrage, timeout, stop_event)) as zeilen:
                async for zeile in zeilen:
                    if not zeile.startswith("data: "):
                        continue
                    roh = zeile[6:]
                    if roh == "[DONE]":
                        break
                    try:
                        stueck = json.loads(roh)
                    except json.JSONDecodeError:
                        continue
                    if stueck.get("error"):  # Fehler mitten im Strom
                        fehler = stueck["error"]
                        raise _LlamaFehler(int(fehler.get("code") or 500) if isinstance(fehler, dict) else 500,
                                           json.dumps(fehler, ensure_ascii=False))
                    fortschritt = stueck.get("prompt_progress")
                    if fortschritt:
                        meldung = _einlese_meldung(fortschritt)
                        if meldung and meldung != letzte_meldung:
                            letzte_meldung = meldung
                            yield _sse({"type": "status", "status": meldung})
                        continue
                    nutzung = stueck.get("usage") or {}
                    if nutzung.get("prompt_tokens"):
                        belegt = int(nutzung["prompt_tokens"]) + int(nutzung.get("completion_tokens") or 0)
                    auswahl = stueck.get("choices") or []
                    if not auswahl:
                        continue
                    ende = auswahl[0].get("finish_reason") or ende
                    delta = auswahl[0].get("delta") or {}
                    gedanke = delta.get("reasoning_content") or ""
                    if gedanke:
                        gedacht = True
                        gedanken += gedanke
                        denk_start = denk_start or time.monotonic()
                        yield _sse({"type": "denken", "text": gedanke})
                        # Denken beenden, wenn Code ins Denken wandert (Gespräch 622:
                        # das ganze Spiel im Denken), die Zeitgrenze der Stufe um ist
                        # oder der Nutzer „Jetzt antworten“ drückt.
                        if denk_ende is not None and denk_ende.is_set():
                            raise _DenkenBeendet("du hast „Jetzt antworten“ gedrückt")
                        if len(gedanken) - geprueft_bis >= 300:
                            geprueft_bis = len(gedanken)
                            if aufwand.code_im_denken(gedanken):
                                raise _DenkenBeendet("im Nachdenken stand schon Code")
                        if aufwand.sekunden(stufe) and time.monotonic() - denk_start > aufwand.sekunden(stufe):
                            raise _DenkenBeendet(f"die Denkzeit der Stufe „{stufe}“ ist um")
                    text = delta.get("content") or ""
                    if text:
                        inhalt += text
                        # Werkzeugaufrufe, die das Modell als Text schreibt
                        # (<tool_call>…), nicht anzeigen. Die letzten Zeichen
                        # zurückhalten, falls das Kennwort gerade beginnt.
                        if not textaufruf:
                            pos = inhalt.find(TEXTAUFRUF)
                            if pos >= 0:
                                textaufruf = True
                                bis = pos
                            else:
                                bis = max(gezeigt, len(inhalt) - len(TEXTAUFRUF))
                            if bis > gezeigt:
                                yield text_sse(inhalt[gezeigt:bis])
                                gezeigt = bis
                    for tc in delta.get("tool_calls") or []:
                        a = aufrufe.setdefault(tc.get("index", 0), {"id": "", "name": "", "args": ""})
                        a["id"] = tc.get("id") or a["id"]
                        fn = tc.get("function") or {}
                        a["name"] += fn.get("name") or ""
                        a["args"] += fn.get("arguments") or ""
        except httpx.ConnectError:
            yield _sse({"type": "error", "message": "KI-Server nicht erreichbar. Bitte später nochmal versuchen."})
            return
        except _Gestoppt:
            yield _sse({"type": "stopped"})
            return
        except _DenkenBeendet as e:
            # Antwortrunde ohne Denken, mit den Überlegungen (ohne Code) als Hinweis.
            # Der Verlauf davor liegt im Cache — neu eingelesen wird nur der Hinweis.
            _log.info("vermittler: Denken beendet (%s) nach %s Zeichen", e.grund, len(gedanken))
            yield _sse({"type": "denken_ende", "grund": e.grund})
            yield _sse({"type": "status", "status": "schreibt jetzt die Antwort"})
            if "chat_template_kwargs" in anfrage:
                anfrage = aufwand.anfrage_ohne_denken(anfrage)
                anfrage["max_tokens"] -= denk_budget
            if denk_ende is not None:
                denk_ende.clear()
            verlauf = verlauf + [{"role": "user", "content": aufwand.hinweis_antworten(gedanken, e.grund)}]
            continue
        except _LlamaFehler as e:
            if e.werkzeug_kaputt and not werkzeug_neu_versucht:
                # Abgeschnittener Werkzeugaufruf (meist eine ganze Datei als
                # Argument) — einmal mit Hinweis neu, statt abzubrechen.
                _log.warning("vermittler: Werkzeugaufruf kaputt, neuer Versuch")
                werkzeug_neu_versucht = True
                yield _sse({"type": "status", "status": "Werkzeugaufruf war zu lang — versucht es anders"})
                verlauf = verlauf + [{"role": "user", "content": _HINWEIS_WERKZEUG}]
                continue
            _log.warning("vermittler: llama %s %s", e.status, e.text[:300])
            yield _sse({"type": "error", "message": f"LLM-Fehler: HTTP {e.status}"})
            return
        except httpx.TimeoutException:
            yield _sse({"type": "error", "message": "Das Modell hat zu lange nicht geantwortet (ausgelastet?). Bitte nochmal versuchen."})
            return
        except Exception as e:  # pragma: no cover
            _log.exception("vermittler")
            yield _sse({"type": "error", "message": f"Fehler: {type(e).__name__} {e}"})
            return

        if not textaufruf and gezeigt < len(inhalt):
            yield text_sse(inhalt[gezeigt:])
            gezeigt = len(inhalt)
        if textaufruf:
            gefunden = _textaufrufe(inhalt)
            inhalt = inhalt[:inhalt.find(TEXTAUFRUF)].rstrip()
            if not aufrufe and gefunden and not letzte:
                _log.warning("vermittler: %s Werkzeugaufruf(e) als Text erkannt", len(gefunden))
                aufrufe = dict(enumerate(gefunden))

        # Abgeschnitten: am Token-Limit — oder das Modell hörte mitten in einem
        # Code-Block auf (ungerade Zahl ```; so am 2026-10-15 im Denkmodus nach
        # erzwungenem Denk-Ende gesehen: Antwort endete mitten im CSS).
        offen = inhalt.count("```") % 2 == 1
        # Gedacht wird nur in der ersten Runde. Sonst denkt das Modell nach
        # jeder Websuche und vor jeder Fortsetzung wieder bis zu DENK_BUDGET
        # Tokens (Mario-Spiel 2026-10-15: 3× gedacht, 576 s, und die
        # Fortsetzung sah wie ein Hänger aus).
        hatte_denken = "chat_template_kwargs" in anfrage
        if hatte_denken:
            anfrage = aufwand.anfrage_ohne_denken(anfrage)
            anfrage["max_tokens"] -= denk_budget
        if not aufrufe and (ende == "length" or (offen and ende == "stop")):
            if not inhalt.strip() and gedacht and hatte_denken:
                # Nur gedacht, keine Antwort: ohne Denken nochmal.
                yield _sse({"type": "status", "status": "antwortet ohne weiteres Nachdenken"})
                continue
            if inhalt.strip() and fortsetzungen < FORTSETZUNGEN:
                fortsetzungen += 1
                _log.info("vermittler: Antwort abgeschnitten, Fortsetzung %s", fortsetzungen)
                yield _sse({"type": "status", "status": "Antwort war zu lang — schreibt weiter"})
                verlauf = verlauf + [
                    {"role": "assistant", "content": inhalt},
                    {"role": "user", "content": _HINWEIS_WEITER.format(ende=json.dumps(inhalt[-80:], ensure_ascii=False))},
                ]
                continue

        if not aufrufe:
            if not inhalt.strip() and not leer_neu_versucht and not (stop_event and stop_event.is_set()):
                # Leere Antwort — einmal mit klarer Anweisung nachfassen (Test
                # 2026-10-17: nach 9 Werkzeugrunden schrieb das Modell in der
                # letzten Runde nur noch einen Werkzeugaufruf als Text; der Nutzer
                # bekam nichts, obwohl die Datei repariert war).
                leer_neu_versucht = True
                yield _sse({"type": "status", "status": "schreibt die Antwort"})
                verlauf = verlauf + [{"role": "user", "content": _HINWEIS_LEER}]
                continue
            if not (stop_event and stop_event.is_set()):
                async def nachfragen(auftrag: str, _verlauf=verlauf, _inhalt=inhalt) -> str:
                    return await _nachfragen(_verlauf, _inhalt, auftrag, anfrage.get("id_slot"))
                anhang = ""
                async for ereignis in _code_nachbearbeiten(inhalt, sichtbar, frage_jetzt, nachfragen):
                    if isinstance(ereignis, tuple):
                        sichtbar = ereignis[1]
                    else:
                        if ereignis.startswith('data: {"content"'):
                            stueck_text = json.loads(ereignis[6:])["content"]
                            sichtbar += stueck_text
                            anhang += stueck_text
                        yield ereignis
                # Geänderte Dateien immer mit Link und Testergebnis (seit 2026-10-17) —
                # das Modell vergass ihn, oder die Antwort blieb leer.
                zeilen = [f"**Datei:** [{n}]({u})" + (f" · {t}" if t else "") for n, (u, t) in geaendert.items() if u not in sichtbar]
                if zeilen and not sichtbar.strip() and any("noch Fehler" in t for _, t in geaendert.values()):
                    zeilen.append("Die Arbeitsschritte für diese Antwort sind aufgebraucht. Schreib „weiter“, dann behebe ich den Rest.")
                if not sichtbar.strip() and not zeilen:
                    zeilen = ["(Keine Antwort erhalten — bitte die Frage noch einmal stellen.)"]
                if zeilen:
                    stueck_text = ("\n\n" if sichtbar.strip() else "") + "\n\n".join(zeilen)
                    yield text_sse(stueck_text)
                    anhang += stueck_text
                # Für die nächste Frage: genau das, was im Slot steht (die
                # erzeugte Antwort unverändert, Datei-Links danach).
                _verlauf_merken(session_id, messages, sichtbar, verlauf, inhalt + anhang, anfrage.get("id_slot"))
            yield kontext_ereignis()
            return

        werkzeugrunden += 1

        # Aufträge an Agents: parallel ausführen, Zusammenfassungen zurück ans Modell.
        agent_aufruf = next((a for a in aufrufe.values() if a["name"] == "agents_beauftragen"), None)
        if agent_aufruf and mit_agents and auftragsrunden >= 2:
            aufruf_id = agent_aufruf["id"] or f"call_{runde}_agents"
            verlauf = verlauf + [
                {"role": "assistant", "content": inhalt or None, "tool_calls": [{
                    "id": aufruf_id, "type": "function",
                    "function": {"name": "agents_beauftragen", "arguments": agent_aufruf["args"] or "{}"}}]},
                {"role": "tool", "tool_call_id": aufruf_id,
                 "content": "Keine weiteren Agent-Aufträge in dieser Antwort (höchstens zwei Runden). Schreib jetzt die "
                            "Antwort mit dem, was vorliegt — offene Punkte ehrlich nennen."},
            ]
            continue
        if agent_aufruf and mit_agents:
            try:
                auftraege = json.loads(agent_aufruf["args"] or "{}").get("auftraege") or []
            except (json.JSONDecodeError, AttributeError):
                auftraege = []
            aufruf_id = agent_aufruf["id"] or f"call_{runde}_agents"
            ergebnisse_agents: list[dict] = []
            async for art, wert in ausfuehren_auftraege(
                auftraege if isinstance(auftraege, list) else [],
                user_id=user_id, session_id=session_id, denken=denken, mit_homelab=mit_homelab,
                projektwissen=projektwissen, stop_event=stop_event,
            ):
                if art == "sse":
                    yield wert
                else:
                    ergebnisse_agents = wert
            if stop_event and stop_event.is_set():
                yield _sse({"type": "stopped"})
                return
            auftragsrunden += 1
            verlauf = verlauf + [
                {"role": "assistant", "content": inhalt or None, "tool_calls": [{
                    "id": aufruf_id, "type": "function",
                    "function": {"name": "agents_beauftragen", "arguments": agent_aufruf["args"] or "{}"}}]},
                {"role": "tool", "tool_call_id": aufruf_id,
                 "content": fuer_modell(ergebnisse_agents) if ergebnisse_agents else "Keine gültigen Aufträge."},
            ]
            if inhalt:
                yield text_sse("\n\n")
            continue

        # Grundwerkzeuge selbst ausführen, Ergebnisse zurück ans Modell.
        tool_calls = []
        ergebnisse = []
        for i, a in sorted(aufrufe.items()):
            aufruf_id = a["id"] or f"call_{runde}_{i}"
            try:
                werkzeug_args = json.loads(a["args"] or "{}")
            except json.JSONDecodeError:
                werkzeug_args = {}
            tool_calls.append({"id": aufruf_id, "type": "function",
                               "function": {"name": a["name"], "arguments": a["args"] or "{}"}})
            yield _sse({"type": "tool_call", "id": aufruf_id, "name": a["name"], "args": werkzeug_args, "level": "READ"})
            ergebnis = await _ausfuehren(a["name"], werkzeug_args, erlaubte_dokumente)
            if ergebnis["success"] and a["name"] in ("str_replace_file", "datei_testen"):
                _datei_merken(geaendert, a["name"], ergebnis["output"])
            log_action(user_id, session_id, a["name"], werkzeug_args, "read", ergebnis["success"], ergebnis["output"])
            ausgabe = ergebnis["output"]
            yield _sse({"type": "tool_result", "id": aufruf_id, "name": a["name"], "success": ergebnis["success"],
                        "output": ausgabe[:300] + ("…" if len(ausgabe) > 300 else "")})
            grenze = DATEI_MAX_ZEICHEN if a["name"] in DATEI_WERKZEUGE else WERKZEUG_MAX_ZEICHEN
            ergebnisse.append({"role": "tool", "tool_call_id": aufruf_id, "content": ausgabe[:grenze]})
        verlauf = verlauf + [{"role": "assistant", "content": inhalt or None, "tool_calls": tool_calls}] + ergebnisse
        if inhalt:
            yield text_sse("\n\n")
    else:
        yield kontext_ereignis()
        return

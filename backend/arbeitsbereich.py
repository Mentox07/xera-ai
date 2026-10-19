"""Arbeitsordner und Sandkasten für Werkzeuge im Web (seit 2026-10-16).

Vorher liefen read_file, write_file, list_files, shell_execute und
python_exec der Agents direkt auf CT 203 — als root, mit dem ganzen Dateisystem.
Im Chat 512 las ein Code-Agent ``/opt/xera-ai/`` aus (samt ``.env`` in der
Liste); ein freigegebener write_file hätte Xera selbst überschreiben können,
python_exec liess sich mit ``import os`` aus der Sperrliste heraus bedienen.
Für den eigenen Admin-Zugang war das tragbar, für ein Web-Angebot nicht.

Jetzt gilt im Web (alles ausser dem Homelab-Bereich):

* Jedes Gespräch hat einen **Arbeitsordner** (``/var/lib/xera-arbeit``).
  Pfade, die das Modell nennt, landen dort — ``/opt/xera-ai/spiel.html``
  wird zu ``spiel.html``. Nach draussen geht nichts.
* Dateizugriffe und Python laufen in einem **Sandkasten**: eigene
  Benutzerkennung je Nutzer (30000–49999), kein Netz (``unshare -n``), keine
  Rechte (``setpriv --no-new-privs``), Grenzen für CPU, Speicher, Dateigrösse
  und Prozesse (``prlimit``), harte Zeitgrenze.
* Was ein Agent schreibt oder Python erzeugt, bekommt der Nutzer als
  **Download-Link** — dieselbe Datei behält ihren Link, wenn sie neu
  geschrieben wird.
* Shell, SSH, Docker, Systeminfos bleiben dem Homelab-Bereich vorbehalten.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import re
import shutil
import signal
import subprocess
import time
import uuid
from pathlib import Path, PurePosixPath

_log = logging.getLogger(__name__)

WURZEL = Path("/var/lib/xera-arbeit")
HELFER = Path(__file__).with_name("sandbox_helfer.py")
PYTHON = "/usr/bin/python3"

# Werkzeuge, die im Web im Sandkasten laufen bzw. dort gar nicht angeboten werden.
SANDBOX_WERKZEUGE = {"read_file", "write_file", "str_replace_file", "list_files", "find_files", "python_exec",
                     "datei_testen"}
NUR_HOMELAB = {"shell_execute", "ssh_execute", "docker_manage", "system_info", "monitoring_query",
               "knowledge_search", "git_execute"}
# Wissensbasis (Obsidian-Notizen des Betreibers) nur für Admins.
NUR_ADMIN = {"rag_search"}

# Dateien, die nach python_exec als Download angeboten werden.
_DOWNLOAD_ENDUNGEN = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".pdf", ".csv", ".tsv", ".xlsx",
                      ".xls", ".docx", ".pptx", ".json", ".txt", ".md", ".html", ".htm", ".zip", ".py",
                      ".js", ".ts", ".css", ".sql", ".xml", ".yaml", ".yml", ".sh", ".ps1", ".mp3", ".wav"}


# ── Ein Ablageort pro Gespräch (seit 2026-10-17) ──────────────────────────────
# Vorher landeten Codeblöcke (Hauptmodell und Agents), erzeugte Dokumente und
# Uploads nur unter /api/download — im Arbeitsordner lagen bloss Notizen. In
# Gespräch 580 suchten Reparatur-Agents 40 min nach dem Spiel aus der ersten
# Runde (`/api/download/…`, `mario.html`, `super-pixel-bros….html`), bauten es
# aus Notizen nach und simulierten es in Python. Jetzt liegt alles, was im
# Gespräch entsteht oder hochgeladen wird, im Arbeitsordner — unter dem Namen,
# den der Nutzer im Download-Link sieht — und jeder Auftrag nennt die Dateien.

# Werkzeug-Beschreibungen für den Sandkasten: die allgemeinen in tools.py
# sprechen von Serverpfaden ('/etc/hostname') — dann raten Agents Pfade wie
# /opt/xera-ai/tmp/… statt die Datei im Arbeitsordner zu nehmen.
_PFAD = {"type": "string", "description": "Dateiname im Arbeitsordner, z. B. 'spiel.html' (genau wie in der Dateiliste)"}
SCHEMAS = {
    "read_file": {"type": "function", "function": {
        "name": "read_file",
        "description": ("Liest eine Datei aus dem Arbeitsordner dieses Gesprächs (ganz, bis 60 000 Zeichen pro Aufruf). "
                        "Grosse Dateien abschnittsweise: offset = erste Zeile, lines = Anzahl. Download-Links "
                        "(/api/download/…) aus dem Gespräch gehen auch."),
        "parameters": {"type": "object", "properties": {
            "path": _PFAD,
            "offset": {"type": "integer", "description": "Erste Zeile (1 = Anfang)"},
            "lines": {"type": "integer", "description": "Anzahl Zeilen ab offset"}}, "required": ["path"]}}},
    "write_file": {"type": "function", "function": {
        "name": "write_file",
        "description": ("Schreibt eine KLEINE Datei (Notiz, Konfiguration, unter ~80 Zeilen) in den Arbeitsordner. "
                        "Grosse Code-Dateien als Codeblock mit datei=name in die Antwort schreiben; bestehende "
                        "Dateien mit str_replace_file ändern."),
        "parameters": {"type": "object", "properties": {
            "path": _PFAD, "content": {"type": "string", "description": "Vollständiger Inhalt"}},
            "required": ["path", "content"]}}},
    "str_replace_file": {"type": "function", "function": {
        "name": "str_replace_file",
        "description": ("Ändert eine Datei im Arbeitsordner gezielt: ersetzt old_string (muss genau einmal vorkommen, "
                        "mit Leerzeichen und Einrückung wie in read_file) durch new_string. Für Korrekturen an "
                        "bestehenden Dateien — nicht die ganze Datei neu schreiben. Danach wird automatisch getestet."),
        "parameters": {"type": "object", "properties": {
            "path": _PFAD, "old_string": {"type": "string", "description": "Exakter alter Text (eindeutig)"},
            "new_string": {"type": "string", "description": "Neuer Text"}},
            "required": ["path", "old_string", "new_string"]}}},
    "list_files": {"type": "function", "function": {
        "name": "list_files",
        "description": "Listet alle Dateien im Arbeitsordner dieses Gesprächs mit Grösse und Zeilenzahl.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Unterordner, sonst leer lassen"}}, "required": []}}},
    "find_files": {"type": "function", "function": {
        "name": "find_files",
        "description": "Sucht Dateien im Arbeitsordner nach Muster (z. B. '*.html'), Gross-/Kleinschreibung egal.",
        "parameters": {"type": "object", "properties": {
            "pattern": {"type": "string", "description": "Muster, z. B. '*.html'"},
            "directory": {"type": "string", "description": "Unterordner, sonst leer lassen"}}, "required": ["pattern"]}}},
    "python_exec": {"type": "function", "function": {
        "name": "python_exec",
        "description": ("Führt Python 3 im Arbeitsordner aus (ohne Internet, max. 60 s). Dateien des Gesprächs liegen "
                        "im aktuellen Ordner (open('daten.xlsx')). Neue Dateien bekommt der Nutzer als Download-Link. "
                        "Für Berechnungen, Datenauswertung, Diagramme — nicht, um HTML/JS-Programme nachzubauen. "
                        "Änderst du eine vorhandene Datei (Excel, Word …), speichere sie unter DEMSELBEN Namen."),
        "parameters": {"type": "object", "properties": {
            "code": {"type": "string", "description": "Python-Code"},
            "timeout": {"type": "integer", "description": "Sekunden (Standard 30, höchstens 60)"}}, "required": ["code"]}}},
    "datei_testen": {"type": "function", "function": {
        "name": "datei_testen",
        "description": ("Testet eine Datei aus dem Arbeitsordner: HTML wird in einem echten Browser (headless Chromium) "
                        "geladen und mit Klicks und Tasten bedient, JavaScript-Fehler werden mit Zeile gemeldet; "
                        "Python/JS/JSON/Shell werden auf Syntax geprüft."),
        "parameters": {"type": "object", "properties": {"path": _PFAD}, "required": ["path"]}}},
}


def schemas(namen) -> list[dict]:
    """Sandkasten-Beschreibungen für diese Werkzeuge (Reihenfolge wie übergeben)."""
    return [SCHEMAS[n] for n in namen if n in SCHEMAS]


_PRAEFIX = re.compile(r"^[0-9a-f]{8,32}_")

# Für „nicht gefunden“: Test 2026-10-17 — Agents mit dem Auftrag, ein Spiel NEU zu
# bauen, suchten die Datei, versuchten sie per str_replace_file anzulegen oder
# meldeten „kann keine Datei speichern“. Die Meldung sagt jetzt, wie Neues entsteht.
_NEU_HINWEIS = ("Soll {name} NEU entstehen: schreib die vollständige Datei als Codeblock mit Dateinamen in deine "
                "Schlussantwort (```html datei={name} … ```) oder gib sie GANZ als new_string mit leerem old_string — "
                "Xera speichert und testet sie. "
                "Soll eine bestehende Datei geändert werden, die es hier nicht gibt: melde das, statt etwas nachzubauen.")

# Platzhalter, die Agents als old_string schicken, wenn sie eine Datei anlegen wollen.
_PLATZHALTER = re.compile(r"[\s<!\-/#*]*(placeholder|platzhalter|todo|tbd|leer|empty|neu|new|dummy|x+|\.\.\.|…)?[\s\-*/>#]*", re.I)


def _ganze_datei(pfad: str, alt, neu) -> bool:
    """str_replace_file auf eine Datei, die es nicht gibt, mit dem ganzen Inhalt
    als new_string — anlegen statt ablehnen. Test 2026-10-17 (Mario v5a): ein
    Agent schickte dreimal die komplette Spieldatei (20 KB, old_string
    'placeholder'), jedes Mal 7–50 min Erzeugen, jedes Mal abgelehnt."""
    if not isinstance(neu, str) or len(neu.strip()) < 200:
        return False
    kopf = neu.lstrip()[:200].lower()
    if PurePosixPath(pfad).suffix.lower() in (".html", ".htm") and kopf.startswith(("<!doctype", "<html")):
        return True
    alt = alt if isinstance(alt, str) else ""
    return bool(_PLATZHALTER.fullmatch(alt)) and _sieht_nach_code_aus(neu)


# Binärdateien, die read_file als Text liefert (docparse) statt als Zeichensalat.
# Szenario S3 2026-10-17: read_file auf produkte.xlsx gab 5 KB „PK…“ zurück; der
# Agent hielt die Datei für unlesbar, suchte (find_files, read_document,
# list_files) und speicherte das Ergebnis am Ende als produkte_neu.xlsx.
_BUERO = {".xlsx", ".xlsm", ".xls", ".docx", ".doc", ".pptx", ".ppt", ".pdf"}
_BILD = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


async def _buero_als_text(sb: dict, pfad: str) -> dict | None:
    """Excel/Word/PowerPoint/PDF als Text, Bilder mit Hinweis; None = keine solche Datei da."""
    endung = PurePosixPath(pfad).suffix.lower()
    if endung not in _BUERO | _BILD:
        return None
    ok, daten = await _helfer(sb, "export", {"pfad": pfad})
    if not ok or not isinstance(daten, str):
        return None
    name = PurePosixPath(pfad).name
    roh = base64.b64decode(daten)
    if endung in _BILD:
        return {"success": True, "output": f"{name} ist ein Bild ({max(1, len(roh) // 1024)} KB) — als Text nicht lesbar. "
                                           "Auswerten oder ändern mit python_exec (z. B. PIL), unter demselben Namen speichern."}
    from .docparse import parse_document
    try:
        text = parse_document(name, roh).get("content") or "(leer)"
    except Exception as e:  # pragma: no cover
        text = f"(Inhalt nicht lesbar: {type(e).__name__})"
    if endung in (".xlsx", ".xlsm"):
        wie = f"python_exec mit openpyxl: wb = openpyxl.load_workbook('{name}') … wb.save('{name}')"
    elif endung == ".docx":
        wie = f"python_exec mit python-docx: d = docx.Document('{name}') … d.save('{name}')"
    else:
        wie = "python_exec"
    return {"success": True, "output": f"[Inhalt von {name} als Text — die Datei selbst ist binär]\n{text[:60000]}\n\n"
                                       f"[Ändern: {wie} — unter DEMSELBEN Namen speichern; der Nutzer erwartet die "
                                       "geänderte Datei, keine Kopie.]"}


def _name_aus_link(roh: str) -> str:
    """'/api/download/75064b56_spiel.html' → 'spiel.html'; sonst unverändert."""
    roh = str(roh or "").strip().strip('"').strip("'")
    if "/api/download/" in roh:
        roh = roh.split("/api/download/", 1)[1].split("?", 1)[0].split("#", 1)[0]
        roh = _PRAEFIX.sub("", roh)
    return roh


async def dateiliste(sb: dict | None) -> list[dict]:
    """Dateien im Arbeitsordner, neueste zuerst: {pfad, bytes, zeit, zeilen}."""
    if sb is None:
        return []
    ok, daten = await _helfer(sb, "uebersicht", {})
    if not ok or not isinstance(daten, list):
        return []
    liste = [{"pfad": p, "bytes": b, "zeit": t, "zeilen": z} for p, b, t, z in daten]
    return sorted(liste, key=lambda d: -d["zeit"])


def _groesse(b: int) -> str:
    return f"{b} Bytes" if b < 2048 else f"{b / 1024:.0f} KB" if b < 2 * 1024 * 1024 else f"{b / 1024 / 1024:.1f} MB"


async def dateiliste_text(sb: dict | None, max_n: int = 40) -> str:
    """'- spiel.html (19 KB, 477 Zeilen)' je Datei — leer, wenn der Ordner leer ist."""
    liste = await dateiliste(sb)
    zeilen = [f"- {d['pfad']} ({_groesse(d['bytes'])}" + (f", {d['zeilen']} Zeilen" if d["zeilen"] else "") + ")"
              for d in liste[:max_n]]
    if len(liste) > max_n:
        zeilen.append(f"- … und {len(liste) - max_n} weitere (list_files)")
    return "\n".join(zeilen)


async def ablegen(sb: dict | None, inhalt: str, dateiname: str) -> tuple[str, str]:
    """Code (aus einem Codeblock) als Datei des Gesprächs ablegen: im Arbeitsordner
    UND als Download. Gleicher Name → gleiche Datei, gleicher Link. → (url, name)"""
    name = _sicherer_name(dateiname)
    if sb is None:  # Homelab, CLI: kein Arbeitsordner
        return datei_ablegen(inhalt, name), name
    ok, rel = await _helfer(sb, "schreiben", {"pfad": name, "inhalt": inhalt})
    if not ok:
        _log.warning("ablegen %s: %s", name, rel)
        return datei_ablegen(inhalt, name), name
    url = await download(sb, str(rel))
    return (url or datei_ablegen(inhalt, name)), str(rel)


async def einspielen(sb: dict | None, quelle: Path, ziel: str, *, ueberschreiben: bool = False) -> str | None:
    """Datei vom Server (Upload, erzeugtes Dokument) in den Arbeitsordner kopieren. → rel. Pfad"""
    if sb is None or not quelle.is_file() or quelle.stat().st_size > 20 * 1024 * 1024:
        return None
    ziel = _sicherer_name(ziel)
    if not ueberschreiben:
        vorhanden = {d["pfad"] for d in await dateiliste(sb)}
        if ziel in vorhanden:
            return ziel
    ok, rel = await _helfer(sb, "einspielen", {"pfad": ziel, "daten": base64.b64encode(quelle.read_bytes()).decode()})
    return str(rel) if ok else None


async def download_uebernehmen(sb: dict | None, url: str) -> str | None:
    """Ein erzeugtes Dokument (/api/download/…) zusätzlich in den Arbeitsordner legen."""
    name = url.rsplit("/", 1)[-1]
    if sb is None or not re.fullmatch(r"[\w.\-]+", name):
        return None
    return await einspielen(sb, _docs_dir() / name, _PRAEFIX.sub("", name), ueberschreiben=True)


async def dokumente_uebernehmen(sb: dict | None, gespeicherte: set[str] | list[str]) -> None:
    """Hochgeladene Dokumente des Gesprächs in den Arbeitsordner (einmal je Datei),
    damit Agents sie mit Python auswerten oder als Datei lesen können."""
    if sb is None:
        return
    basis = _docs_dir().resolve()
    for name in list(gespeicherte)[:10]:
        quelle = (basis / str(name)).resolve()
        if quelle.parent != basis:
            continue
        try:
            await einspielen(sb, quelle, _PRAEFIX.sub("", quelle.name))
        except Exception as e:  # pragma: no cover
            _log.warning("dokument %s: %s", name, e)


_AUFGERAEUMT = 0.0


def aufraeumen(tage: int = 7) -> None:
    """Arbeitsordner, die seit `tage` Tagen unberührt sind, löschen (höchstens
    einmal am Tag; aufgerufen aus der Hintergrundschleife in vermittler.py)."""
    global _AUFGERAEUMT
    jetzt = time.time()
    if jetzt - _AUFGERAEUMT < 86400 or not WURZEL.is_dir():
        return
    _AUFGERAEUMT = jetzt
    grenze = jetzt - tage * 86400
    for nutzer in WURZEL.iterdir():
        if not nutzer.is_dir() or nutzer.is_symlink():
            continue
        for sitzung in nutzer.iterdir():
            try:
                juengste = max((p.stat().st_mtime for p in sitzung.rglob("*")), default=sitzung.stat().st_mtime)
                if juengste < grenze:
                    shutil.rmtree(sitzung, ignore_errors=True)
            except OSError:
                pass
    if len(_LINKS) > 5000:
        _LINKS.clear()


def gesperrte_werkzeuge(sb: dict | None) -> set[str]:
    """Was im Sandkasten gar nicht erst angeboten wird."""
    if sb is None:
        return set()
    return NUR_HOMELAB | (set() if sb.get("admin") else NUR_ADMIN)


_UIDS: dict[str, int] = {}


def uid_fuer(user_id) -> int:
    """Sandkasten-Kennung des Nutzers (30000–49999), fest in der Datenbank vergeben und eindeutig.
    Bis 2026-10-19 nur aus dem Hash modulo 20 000: Bei 100 Nutzern hätten sich mit rund 22 %
    zwei denselben Ordner, dieselbe Kennung und denselben OpenCode-Speicher geteilt. Der Hash
    bleibt der Wunsch, damit bestehende Ordner ihren Namen behalten."""
    schluessel = str(user_id)
    if schluessel not in _UIDS:
        from . import database as db
        wunsch = 30000 + int(hashlib.sha256(schluessel.encode()).hexdigest(), 16) % 20000
        _UIDS[schluessel] = db.sandbox_uid(schluessel, wunsch, range(30000, 50000))
    return _UIDS[schluessel]


#: Platz je Nutzer im Arbeitsbereich, alle Gespräche zusammen (seit 2026-10-19). Vorher ohne
#: Grenze — ein Nutzer hätte die Platte von CT 203 füllen können, dann stünde die Datenbank.
PLATZ_JE_NUTZER = 1024**3
#: Liegt weniger frei, nimmt Xera keine Antworten mit Dateien mehr an — die Datenbank geht vor.
PLATZ_REST_MIN = 3 * 1024**3


def platz_belegt(user_id) -> int:
    """Bytes im Arbeitsbereich des Nutzers (du folgt keinen Links)."""
    p = WURZEL / f"u{uid_fuer(user_id)}"
    if not p.is_dir():
        return 0
    r = subprocess.run(["du", "-sb", "--", str(p)], capture_output=True, text=True, timeout=30)
    try:
        return int(r.stdout.split()[0])
    except (ValueError, IndexError):
        return 0


def platz_pruefen(user_id, *, grenze: int = PLATZ_JE_NUTZER) -> str | None:
    """None, wenn genug Platz ist; sonst ein Satz für den Nutzer."""
    if shutil.disk_usage(WURZEL if WURZEL.is_dir() else "/").free < PLATZ_REST_MIN:
        return "Xera hat gerade zu wenig Speicherplatz für Dateien. Versuch es später nochmal."
    belegt = platz_belegt(user_id)
    if belegt > grenze:
        return (f"Dein Arbeitsplatz ist voll ({belegt / 1024**3:.1f} GB, Grenze {PLATZ_JE_NUTZER / 1024**3:.0f} GB). "
                "Lösch Gespräche mit grossen Dateien, dann ist der Platz sofort wieder frei.")
    return None


def ordner_loeschen(user_id, session_id) -> None:
    """Arbeitsordner eines gelöschten Gesprächs gleich mit löschen — als Sandkasten-Benutzer,
    der Ordner gehört ihm (ein Link darin träfe sonst fremde Dateien)."""
    uid = uid_fuer(user_id)
    p = WURZEL / f"u{uid}" / f"s{int(session_id)}"
    if p.exists() or p.is_symlink():
        subprocess.run(["setpriv", f"--reuid={uid}", f"--regid={uid}", "--clear-groups", "--no-new-privs",
                        "rm", "-rf", "--", str(p)], env={"PATH": "/usr/bin:/bin"}, timeout=120)


def ordner(sb: dict) -> Path:
    """Arbeitsordner dieses Gesprächs, gehört der Sandkasten-Kennung."""
    uid = uid_fuer(sb["user_id"])
    nutzer = WURZEL / f"u{uid}"
    teil = f"s{sb['session_id']}" if sb.get("session_id") else f"g{int(time.time()) // 86400}"
    p = nutzer / teil
    if not p.is_dir():
        WURZEL.mkdir(mode=0o711, parents=True, exist_ok=True)
        os.chmod(WURZEL, 0o711)
        for q in (nutzer, p):
            q.mkdir(mode=0o700, exist_ok=True)
            os.chown(q, uid, uid)
            os.chmod(q, 0o700)
    return p


def abbilden(roh: str) -> str:
    """Pfad des Modells → Pfad im Arbeitsordner (relativ)."""
    roh = (str(roh or "")).strip().strip('"').strip("'")
    if not roh or roh in (".", "./", "/", "~", "~/"):
        return "."
    if roh.startswith("~/"):
        roh = roh[2:]
    p = PurePosixPath(roh)
    if p.is_absolute():
        teile = p.parts
        # Ein Pfad aus einer früheren Ausgabe, der schon im Arbeitsordner liegt.
        if "xera-arbeit" in teile:
            i = teile.index("xera-arbeit")
            rest = teile[i + 3:]
            return str(PurePosixPath(*rest)) if rest else "."
        return p.name or "."
    teile = [t for t in p.parts if t not in ("..",)]
    return str(PurePosixPath(*teile)) if teile else "."


def _ordnerpfad(roh) -> str:
    """Wie abbilden(), aber ein Serverpfad (/opt/xera-ai, /home/...) heisst hier
    einfach: der Arbeitsordner."""
    roh = str(roh or "").strip()
    if roh.startswith("/") and "xera-arbeit" not in roh:
        return "."
    return abbilden(roh)


def _praefix(uid: int, *, cpu: int = 60, speicher: int | None = 4 * 1024**3) -> list[str]:
    grenzen = [f"--cpu={cpu}", "--fsize=104857600", "--nofile=512", "--nproc=256"]
    if speicher:
        grenzen.insert(0, f"--as={speicher}")
    return (["unshare", "-n", "--",
             "setpriv", f"--reuid={uid}", f"--regid={uid}", "--clear-groups", "--no-new-privs",
             "--pdeathsig", "KILL", "--",
             "prlimit", *grenzen, "--"])


def _umgebung(arbeit: Path) -> dict:
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(arbeit),
        "LANG": "C.UTF-8",
        "MPLBACKEND": "Agg",
        "MPLCONFIGDIR": str(arbeit / ".mpl"),
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "TMPDIR": str(arbeit),
    }


async def eingesperrt(sb: dict, argv: list[str], *, eingabe: bytes = b"", zeit: float = 30.0,
                      cpu: int = 60, speicher: int | None = 4 * 1024**3, cwd: Path | None = None,
                      umgebung: dict | None = None) -> tuple[int, bytes, bytes, bool]:
    """Startet argv im Sandkasten des Nutzers. → (rc, stdout, stderr, zeit_um)"""
    arbeit = ordner(sb)
    uid = uid_fuer(sb["user_id"])
    proc = await asyncio.create_subprocess_exec(
        *_praefix(uid, cpu=cpu, speicher=speicher), *argv,
        cwd=str(cwd or arbeit), env={**_umgebung(arbeit), **(umgebung or {})},
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(eingabe), timeout=zeit)
        return proc.returncode or 0, out, err, False
    except asyncio.TimeoutError:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=5)
        except Exception:
            out, err = b"", b""
        return -9, out, err, True


async def _helfer(sb: dict, op: str, args: dict) -> tuple[bool, object]:
    rc, out, err, um = await eingesperrt(sb, [PYTHON, "-I", str(HELFER), op],
                                        eingabe=json.dumps(args, ensure_ascii=False).encode(), zeit=20)
    if um:
        return False, "Zeitüberschreitung"
    try:
        d = json.loads(out.decode("utf-8", "replace") or "{}")
        return bool(d.get("ok")), d.get("ausgabe")
    except json.JSONDecodeError:
        _log.warning("sandbox %s: rc=%s err=%s", op, rc, err[-400:])
        return False, (err.decode("utf-8", "replace")[-400:] or f"Sandkasten-Fehler (rc={rc})")


# Gleiche Datei → gleicher Download-Link, auch wenn sie neu geschrieben wird.
_LINKS: dict[tuple, str] = {}


def _docs_dir() -> Path:
    from .docgen import DOCS_DIR
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(DOCS_DIR, 0o700)
    return DOCS_DIR


def _sicherer_name(name: str) -> str:
    name = PurePosixPath(name).name
    sicher = "".join(c for c in name if c.isalnum() or c in "._- ").strip().replace(" ", "_")[:60]
    return sicher or "datei"


async def download(sb: dict, relpfad: str) -> str | None:
    """Datei aus dem Arbeitsordner als Download anbieten. → URL oder None."""
    ok, daten = await _helfer(sb, "export", {"pfad": relpfad})
    if not ok or not isinstance(daten, str):
        return None
    schluessel = (uid_fuer(sb["user_id"]), sb.get("session_id"), relpfad)
    name = _LINKS.get(schluessel) or f"{uuid.uuid4().hex[:8]}_{_sicherer_name(relpfad)}"
    _LINKS[schluessel] = name
    ziel = _docs_dir() / name
    fd = os.open(ziel, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(base64.b64decode(daten))
    return f"/api/download/{name}"


def datei_ablegen(inhalt: str, dateiname: str) -> str:
    """Text (z. B. Code aus einem Codeblock) direkt als Download ablegen."""
    name = f"{uuid.uuid4().hex[:8]}_{_sicherer_name(dateiname)}"
    ziel = _docs_dir() / name
    fd = os.open(ziel, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(inhalt)
    return f"/api/download/{name}"


def datei_ersetzen(url: str, inhalt: str) -> None:
    """Inhalt hinter einem bestehenden Download-Link austauschen (nach einer Korrektur)."""
    name = url.rsplit("/", 1)[-1]
    ziel = _docs_dir() / name
    if ziel.parent != _docs_dir() or not re.fullmatch(r"[\w.\-]+", name):
        return
    fd = os.open(ziel, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(inhalt)


def _link(relpfad: str, url: str | None) -> str:
    name = PurePosixPath(relpfad).name
    return f"[{name}]({url})" if url else name


async def ausfuehren(name: str, args: dict, sb: dict) -> dict:
    """Ein Datei-/Python-Werkzeug im Sandkasten ausführen."""
    try:
        if name == "read_file":
            pfad = abbilden(_name_aus_link(args.get("path", "")))
            buero = await _buero_als_text(sb, pfad)
            if buero is None and PurePosixPath(pfad).suffix.lower() in _BUERO | _BILD:
                gefunden = await _aehnlich(sb, pfad)
                buero = await _buero_als_text(sb, gefunden) if gefunden else None
            if buero is not None:
                return buero
            lesen = {"von": _zahl(args.get("offset")), "zeilen": _zahl(args.get("lines"))}
            ok, aus = await _helfer(sb, "lesen", {"pfad": pfad, **lesen})
            if not ok and "nicht gefunden" in str(aus):
                gefunden = await _aehnlich(sb, pfad)
                if gefunden:
                    ok, aus = await _helfer(sb, "lesen", {"pfad": gefunden, **lesen})
                    if ok:
                        aus = f"[{pfad} gibt es nicht — gelesen: {gefunden}]\n{aus}"
            if not ok and "nicht gefunden" in str(aus):
                liste = await dateiliste_text(sb)
                aus = (f"{aus}. Im Arbeitsordner dieses Gesprächs liegen:\n{liste}\n{_NEU_HINWEIS.format(name=PurePosixPath(pfad).name)}"
                       if liste else f"{aus}. Der Arbeitsordner dieses Gesprächs ist leer. "
                       + _NEU_HINWEIS.format(name=PurePosixPath(pfad).name))
            return {"success": ok, "output": str(aus)}

        if name == "datei_testen":
            pfad = abbilden(_name_aus_link(args.get("path", "")))
            ok, daten = await _helfer(sb, "export", {"pfad": pfad})
            if not ok:
                gefunden = await _aehnlich(sb, pfad)
                if gefunden:
                    pfad = gefunden
                    ok, daten = await _helfer(sb, "export", {"pfad": pfad})
            if not ok or not isinstance(daten, str):
                liste = await dateiliste_text(sb)
                return {"success": False, "output": f"Datei nicht gefunden: {pfad} — getestet wird, was existiert."
                        + (f" Vorhanden:\n{liste}\n" if liste else " Der Arbeitsordner ist leer. ")
                        + _NEU_HINWEIS.format(name=PurePosixPath(pfad).name)}
            inhalt = base64.b64decode(daten).decode("utf-8", "replace")
            test = await _testen(sb, pfad, inhalt, ausfuehrlich=True)
            return {"success": True, "output": test.strip() or f"{pfad}: für diesen Dateityp gibt es keinen automatischen Test."}

        if name == "write_file":
            pfad = abbilden(_name_aus_link(args.get("path", "")))
            if pfad == ".":
                return {"success": False, "output": "Kein Dateiname angegeben."}
            inhalt = args.get("content", "")
            if isinstance(inhalt, str) and len(inhalt) > 3000 and _sieht_nach_code_aus(inhalt):
                # Test 2026-10-17: ein Agent schrieb ein Spiel stückweise als
                # mario_part1.txt … — statt EINER Datei als Codeblock.
                return {"success": False, "output": (
                    "Nicht gespeichert: grosse Code-Dateien nicht mit write_file (auch nicht in Teilen). Schreib die "
                    "GANZE Datei als Codeblock mit Dateinamen in deine Schlussantwort, z. B. ```html datei=spiel.html — "
                    "Xera speichert sie im Arbeitsordner und testet sie. Eine bestehende Datei änderst du mit str_replace_file.")}
            ok, aus = await _helfer(sb, "schreiben", {"pfad": pfad, "inhalt": inhalt if isinstance(inhalt, str) else json.dumps(inhalt)})
            if not ok:
                return {"success": False, "output": str(aus)}
            url = await download(sb, str(aus))
            test = await _testen(sb, str(aus), inhalt if isinstance(inhalt, str) else "")
            return {"success": True,
                    "output": f"Gespeichert: {aus} ({len(inhalt)} Zeichen) im Arbeitsordner. Download für den Nutzer: {_link(str(aus), url)}{test}"}

        if name == "str_replace_file":
            pfad = abbilden(_name_aus_link(args.get("path", "")))
            ersetzen = {"alt": args.get("old_string", ""), "neu": args.get("new_string", "")}
            ok, aus = await _helfer(sb, "ersetzen", {"pfad": pfad, **ersetzen})
            if not ok and "nicht gefunden: " in str(aus):
                gefunden = await _aehnlich(sb, pfad)
                if gefunden:
                    ok, aus = await _helfer(sb, "ersetzen", {"pfad": gefunden, **ersetzen})
                elif pfad != "." and _ganze_datei(pfad, ersetzen["alt"], ersetzen["neu"]):
                    inhalt = ersetzen["neu"]
                    ok, aus = await _helfer(sb, "schreiben", {"pfad": pfad, "inhalt": inhalt})
                    if not ok:
                        return {"success": False, "output": str(aus)}
                    url = await download(sb, str(aus))
                    test = await _testen(sb, str(aus), inhalt)
                    _log.info("str_replace_file: %s neu angelegt (%s Zeichen, old_string war Platzhalter)", aus, len(inhalt))
                    return {"success": True, "output": f"Neu angelegt: {aus} ({inhalt.count(chr(10)) + 1} Zeilen) im "
                            f"Arbeitsordner. Download: {_link(str(aus), url)}{test}"}
                if not ok and "nicht gefunden: " in str(aus):
                    liste = await dateiliste_text(sb)
                    aus = (f"{aus} — str_replace_file ändert nur bestehende Dateien."
                           + (f" Vorhanden:\n{liste}\n" if liste else " Der Arbeitsordner ist leer. ")
                           + _NEU_HINWEIS.format(name=PurePosixPath(pfad).name))
            if not ok:
                return {"success": False, "output": str(aus)}
            url = await download(sb, str(aus))
            ok_l, daten = await _helfer(sb, "export", {"pfad": str(aus)})
            test = await _testen(sb, str(aus), base64.b64decode(daten).decode("utf-8", "replace") if ok_l and isinstance(daten, str) else "")
            return {"success": True, "output": f"Ersetzt in {aus}. Download: {_link(str(aus), url)}{test}"}

        if name == "list_files":
            pfad = _ordnerpfad(args.get("path", "."))
            if pfad == ".":
                liste = await dateiliste_text(sb, max_n=200)
                return {"success": True, "output": ("Dateien im Arbeitsordner dieses Gesprächs:\n" + liste) if liste
                        else "Der Arbeitsordner dieses Gesprächs ist leer."}
            ok, aus = await _helfer(sb, "liste", {"pfad": pfad})
            if not ok:
                ok, aus = True, await dateiliste_text(sb, max_n=200) or "[leer]"
            return {"success": ok, "output": f"Arbeitsordner (der Server selbst ist nicht zugänglich):\n{aus}"}

        if name == "find_files":
            ok, aus = await _helfer(sb, "finden", {"pfad": _ordnerpfad(args.get("directory", ".")),
                                                   "muster": args.get("pattern", "*")})
            return {"success": ok, "output": str(aus)}

        if name == "python_exec":
            return await _python(sb, str(args.get("code", "")), int(args.get("timeout", 30) or 30))

        return {"success": False, "output": f"Werkzeug '{name}' gibt es hier nicht."}
    except Exception as e:  # pragma: no cover
        _log.exception("sandbox %s", name)
        return {"success": False, "output": f"Fehler im Arbeitsordner: {type(e).__name__}: {e}"}


_CODE_ZEICHEN = re.compile(r"<!doctype|<html|<script|<canvas|\bfunction\s+\w+\s*\(|\bconst\s+\w+\s*=|\bdef\s+\w+\s*\(|"
                           r"^\s*(import|from)\s+\w+|\bclass\s+\w+[:(]|#!/", re.I | re.M)


def _sieht_nach_code_aus(text: str) -> bool:
    return len(_CODE_ZEICHEN.findall(text[:20000])) >= 2


def _seite_mit(sb: dict, relpfad: str) -> str | None:
    """Eine HTML-Seite im Arbeitsordner, die diese Datei einbindet (src=/href=)."""
    name = re.escape(PurePosixPath(relpfad).name)
    muster = re.compile(r"""(?:src|href)\s*=\s*["']?(?:\./)?""" + name + r"""["'?#\s>]""", re.I)
    arbeit = ordner(sb)
    for p in sorted(arbeit.rglob("*.htm*")):
        if ".pruefung" in p.parts or not p.is_file() or p.stat().st_size > 2 * 1024 * 1024:
            continue
        try:
            if muster.search(p.read_text(encoding="utf-8", errors="replace")):
                return str(p.relative_to(arbeit))
        except OSError:
            continue
    return None


def _zahl(wert) -> int | None:
    try:
        return int(wert) if wert not in (None, "") else None
    except (TypeError, ValueError):
        return None


async def _aehnlich(sb: dict, gesucht: str) -> str | None:
    """Datei, die gemeint sein dürfte: gleicher Name in anderer Schreibweise/Ordner,
    sonst die einzige Datei mit derselben Endung, sonst ein sehr ähnlicher Name."""
    import difflib
    liste = [d["pfad"] for d in await dateiliste(sb)]
    if not liste:
        return None
    name = PurePosixPath(gesucht).name.lower()
    gleich = [p for p in liste if PurePosixPath(p).name.lower() == name]
    if len(gleich) == 1:
        return gleich[0]
    endung = PurePosixPath(name).suffix
    if endung:
        gleiche_endung = [p for p in liste if PurePosixPath(p).suffix.lower() == endung]
        if len(gleiche_endung) == 1:
            return gleiche_endung[0]
    namen = {PurePosixPath(p).name.lower(): p for p in liste}
    nah = difflib.get_close_matches(name, list(namen), n=1, cutoff=0.75)
    return namen[nah[0]] if nah else None


async def _testen(sb: dict, relpfad: str, inhalt: str, *, ausfuehrlich: bool = False) -> str:
    """Geschriebene Code-Dateien automatisch prüfen (HTML im Browser, sonst
    Syntax) — das Ergebnis geht mit der Werkzeugausgabe ans Modell. Vorher
    prüfte niemand, und Agents bauten sich eigene Prüfrunden (Chat 518)."""
    from . import codepruefung
    endung = PurePosixPath(relpfad).suffix.lower().lstrip(".")
    sprache = {"htm": "html", "py": "python", "mjs": "js", "cjs": "js", "sh": "bash"}.get(endung, endung)
    if sprache in ("js", "css"):
        # Eingebundene Datei (spiel.js, stil.css): die Seite, die sie lädt, im Browser
        # testen — die Syntaxprüfung allein sieht keine Laufzeitfehler (seit 2026-10-17).
        seite = _seite_mit(sb, relpfad)
        if seite:
            basis = await _testen(sb, seite, (ordner(sb) / seite).read_text(encoding="utf-8", errors="replace"),
                                  ausfuehrlich=ausfuehrlich)
            if sprache == "css":
                return basis
            syntax = await codepruefung.pruefen(inhalt, "js", sb)
            if syntax:
                return (f"\nAutomatischer Test von {relpfad} (Syntax geprüft): FEHLER\n" + "\n".join(f"- {f}" for f in syntax)
                        + "\nKorrigiere die Stellen mit str_replace_file, danach datei_testen.")
            return basis
    if not inhalt or sprache not in ("html", "python", "js", "json", "bash"):
        return ""
    fehler = await codepruefung.pruefen(inhalt, sprache, sb, pfad=relpfad)
    if fehler is None:
        return ("\nKein automatischer Test möglich: Die HTML-Datei ist keine ganze Seite mit Skript." if ausfuehrlich
                and sprache == "html" else "")
    art = ("im Browser geladen, geklickt und mit Pfeiltasten/Leertaste/Enter bedient" if sprache == "html"
           else "Syntax geprüft")
    zeilen = inhalt.count("\n") + 1
    if not fehler:
        return (f"\nAutomatischer Test von {relpfad} ({zeilen} Zeilen, {art}): keine Fehler."
                + ("" if ausfuehrlich else " Nicht noch einmal selbst prüfen."))
    return (f"\nAutomatischer Test von {relpfad} ({zeilen} Zeilen, {art}): FEHLER\n" + "\n".join(f"- {f}" for f in fehler)
            + "\nKorrigiere die Stellen mit str_replace_file (nicht die ganze Datei neu schreiben), danach datei_testen.")


async def _python(sb: dict, code: str, zeit: int) -> dict:
    code = code.strip()
    if not code:
        return {"success": False, "output": "Kein Code angegeben."}
    zeit = max(5, min(zeit, 60))
    _, vorher = await _helfer(sb, "inventar", {})
    vorher = vorher if isinstance(vorher, dict) else {}
    rc, out, err, um = await eingesperrt(sb, [PYTHON, "-I", "-"], eingabe=code.encode(), zeit=zeit, cpu=zeit + 5)
    o = out.decode("utf-8", "replace").strip()
    e = err.decode("utf-8", "replace").strip()
    if um:
        teile = [f"[Zeitüberschreitung nach {zeit}s]"]
    elif rc != 0:
        teile = [f"[stdout]\n{o}\n\n[stderr]\n{e}" if o else f"[stderr]\n{e}"]
    else:
        teile = [o or "[keine Ausgabe]"] + ([f"[Warnungen]\n{e[-1500:]}"] if e else [])
    if "Network is unreachable" in e or "Name or service not known" in e or "Temporary failure in name resolution" in e:
        teile.append("(Hinweis: Python hat hier keinen Internetzugang — Daten aus dem Netz holst du mit web_search/web_fetch.)")
    # Neue oder geänderte Dateien als Download anbieten.
    _, nachher = await _helfer(sb, "inventar", {})
    neu = [p for p, info in (nachher.items() if isinstance(nachher, dict) else [])
           if vorher.get(p) != info and Path(p).suffix.lower() in _DOWNLOAD_ENDUNGEN]
    links = []
    for p in sorted(neu)[:8]:
        url = await download(sb, p)
        if url:
            links.append(_link(p, url))
    if links:
        teile.append("Erzeugte Dateien (Download für den Nutzer): " + ", ".join(links))
    text = "\n\n".join(teile)
    if len(text) > 8000:
        text = text[:8000] + "\n[... gekürzt]"
    return {"success": rc == 0 and not um, "output": text}

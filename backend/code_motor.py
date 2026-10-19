"""Web-Code-Bereich = derselbe Motor wie die CLI: OpenCode auf dem Server (seit 2026-10-19).

Wunsch: „Der Code-Bereich im Web soll 1:1 gleich sein wie die CLI-Version“ (Plan
docs/plan-code-opencode-2026-10.md). Statt des eigenen Wegs über vermittler.py
(Hauptmodell + Xera-Agents) arbeitet der Code-Bereich mit OpenCode — denselben
Werkzeugen, Prompts und Unteragenten wie `opencode` im Terminal.

* Je Nutzer ein ``opencode serve`` auf 127.0.0.1, als Sandkasten-Benutzer des
  Nutzers (arbeitsbereich.uid_fuer), HOME in seinem Arbeitsbereich. Start auf
  Abruf, nach RUHE_S ohne Anfrage wieder aus.
* Je Xera-Gespräch eine OpenCode-Sitzung, Ordner = Arbeitsordner des Gesprächs
  (gleiche Dateien, Downloads, 7 Tage wie bisher).
* Modell ``xera-code`` über /v1 (openai_api.py) → Slot 1 wie bisher; Titel über
  ``xera-klein`` (Slot 4). Der Schlüssel dafür ist intern, je Motorstart neu.
* bash läuft über sandbox-sh: eigener Netz-Namensraum, Grenzen. webfetch,
  Websuche, fremde Ordner sind gesperrt.
* Die Ereignisse von OpenCode werden in Xeras SSE-Format übersetzt (Text,
  Denken, Werkzeugkarten, Status) — die Oberfläche bleibt, wie sie ist.
"""

from __future__ import annotations

import asyncio
import json
import re
import logging
import os
import secrets
import signal
import socket
import subprocess
import time
from pathlib import Path

import httpx

from . import arbeitsbereich, aufwand, openai_api

_log = logging.getLogger("xera.code_motor")

OPENCODE = Path(os.getenv("XERA_OPENCODE", "/opt/xera-ai/motor/opencode"))
SANDBOX_SH = Path("/opt/xera-ai/motor/sandbox-sh")
REGELN = Path("/opt/xera-ai/cli/regeln.md")
PID_ORDNER = Path("/run/xera-motor")
RUHE_S = 15 * 60
START_S = 60
#: Höchstens so viele Motoren gleichzeitig (~300 MB RAM je Stück, CT 203 hat 8 GB, seit 2026-10-19).
#: Darüber wird der am längsten ruhende beendet; arbeiten alle, wartet der Neue mit einer Meldung.
MAX_MOTOREN = 8
SCHLUESSEL_NAME = "intern:web-code"
# nftables-Tabelle aus motor/sandbox-netz.nft (xera-sandbox-netz.service): Sandkasten-Benutzer
# erreichen nur das Backend auf 127.0.0.1:8000 — auch wenn OpenCode eine andere Shell oder ein
# Plugin untergeschoben wird. Fehlt sie, startet kein Motor.
NETZ_SPERRE = ("inet", "xera_sandbox")


def _als(uid: int) -> list[str]:
    return ["setpriv", f"--reuid={uid}", f"--regid={uid}", "--clear-groups", "--no-new-privs"]


_UMGEBUNG_KNAPP = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}


# Läuft als Sandkasten-Benutzer (Motor.starten): Konfiguration und Regeln schreiben, alles andere
# im globalen Konfigurationsordner entfernen (dort geladene Plugins liefen im Motor selbst), altes Log weg.
_EINRICHTEN = r"""
import json, os, shutil, sys
heim = sys.argv[1]
d = json.load(sys.stdin)
konf = os.path.join(heim, ".config", "opencode")
os.makedirs(konf, exist_ok=True)
os.chmod(heim, 0o700)
for name in os.listdir(konf):
    if name not in ("opencode.jsonc", "AGENTS.md"):
        p = os.path.join(konf, name)
        shutil.rmtree(p) if os.path.isdir(p) and not os.path.islink(p) else os.remove(p)
shutil.rmtree(os.path.join(heim, ".opencode"), ignore_errors=True)
for name in ("opencode.jsonc", "AGENTS.md"):
    p = os.path.join(konf, name)
    if os.path.islink(p):
        os.remove(p)
with open(os.path.join(konf, "opencode.jsonc"), "w", encoding="utf-8") as f:
    json.dump(d["konfiguration"], f, indent=2, ensure_ascii=False)
with open(os.path.join(konf, "AGENTS.md"), "w", encoding="utf-8") as f:
    f.write(d["regeln"])
shutil.rmtree(os.path.join(heim, ".local", "share", "opencode", "log"), ignore_errors=True)
"""


def konfiguration() -> dict:
    """opencode.jsonc des Motors — dieselbe Grundlage wie für die CLI
    (docs/deployment/opencode/opencode.jsonc), nur lokal und abgeschottet."""
    modell = {"limit": {"context": 131072, "output": 16384},
              "capabilities": {"tools": True, "input": ["text"], "output": ["text"], "temperature": False},
              "compatibility": {"reasoningField": "reasoning_content", "maxTokensField": "max_tokens"},
              "variants": [{"id": s, "body": {"xera_aufwand": s}} for s in aufwand.STUFEN if s != "aus"]}
    return {
        "$schema": "https://opencode.ai/config.json",
        "model": "xera/xera-code",
        "update": "disable",
        "websearch": False,
        "formatter": False,
        "shell": str(SANDBOX_SH),
        "permissions": [
            {"action": "external_directory", "resource": "*", "effect": "deny"},
            {"action": "webfetch", "resource": "*", "effect": "deny"},
            {"action": "websearch", "resource": "*", "effect": "deny"},
            {"action": "question", "resource": "*", "effect": "deny"},
            {"action": "read", "resource": "*.env", "effect": "allow"},
        ],
        "providers": {"xera": {
            "name": "Xera",
            "package": "@opencode/ai/providers/openai-compatible",
            "env": ["XERA_API_KEY"],
            "settings": {"baseURL": "http://127.0.0.1:8000/v1", "timeout": False,
                         "headerTimeout": 1800000, "chunkTimeout": 1800000},
            "models": {
                "xera-code": {"name": "Xera Code (Qwen3.8-Flash-Next)", **modell},
                "xera-klein": {"name": "Xera klein", "limit": {"context": 131072, "output": 2048},
                               "capabilities": {"tools": False, "input": ["text"], "output": ["text"], "temperature": False},
                               "compatibility": {"maxTokensField": "max_tokens"}},
            },
        }},
        "agents": {"title": {"model": "xera/xera-klein"}, "summary": {"model": "xera/xera-klein"}},
    }


class Motor:
    def __init__(self, user_id: str):
        self.user_id = str(user_id)
        self.uid = arbeitsbereich.uid_fuer(user_id)
        self.heim = arbeitsbereich.WURZEL / f"u{self.uid}" / ".motor"
        self.port = 0
        self.passwort = ""
        self.prozess: subprocess.Popen | None = None
        self.schluessel_id: int | None = None
        self.zuletzt = time.monotonic()
        self.laufend = 0
        self.sperre = asyncio.Lock()

    @property
    def basis(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def auth(self) -> tuple[str, str]:
        return ("opencode", self.passwort)

    def lebt(self) -> bool:
        return self.prozess is not None and self.prozess.poll() is None

    async def starten(self) -> None:
        self.stoppen()
        # Ohne Netz-Sperre kein Motor: OpenCode selbst läuft nicht in sandbox-sh (siehe NETZ_SPERRE)
        if subprocess.run(["/usr/sbin/nft", "list", "table", *NETZ_SPERRE], capture_output=True).returncode != 0:
            raise RuntimeError("Netz-Sperre des Sandkastens fehlt (xera-sandbox-netz.service)")
        nutzer_ordner = arbeitsbereich.WURZEL / f"u{self.uid}"
        nutzer_ordner.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chown(nutzer_ordner, self.uid, self.uid)
        # HOME als Sandkasten-Benutzer einrichten, nicht als root: der Ordner gehört ihm, ein Link
        # darin (z. B. motor.log → /etc/passwd) liesse root sonst fremde Dateien schreiben (2026-10-19).
        # Gemeinsame Xera-Regeln (dieselben wie in der CLI, dort als URL /cli/regeln.md) als globale
        # AGENTS.md des Motors. Über "instructions" mit Pfad lud OpenCode sie nicht: die Datei liegt
        # ausserhalb des Arbeitsordners, und fremde Ordner sind für den Motor gesperrt (2026-10-19).
        daten = {"konfiguration": konfiguration(), "regeln": REGELN.read_text(encoding="utf-8") if REGELN.is_file() else ""}
        r = subprocess.run([*_als(self.uid), arbeitsbereich.PYTHON, "-I", "-c", _EINRICHTEN, str(self.heim)],
                           input=json.dumps(daten, ensure_ascii=False).encode(), capture_output=True, timeout=30,
                           cwd=str(nutzer_ordner), env=_UMGEBUNG_KNAPP)   # nie die des Backends (.env!)
        if r.returncode != 0:
            raise RuntimeError(f"Motor-HOME einrichten: {r.stderr.decode('utf-8', 'replace')[-300:]}")
        neu = openai_api.schluessel_erzeugen(self.user_id, SCHLUESSEL_NAME)
        self.schluessel_id = neu["id"]
        self.passwort = secrets.token_urlsafe(24)
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        # Keine Projekt-Konfiguration: eine opencode.json im Arbeitsordner (die das Modell selbst
        # schreiben kann) stellte die Shell auf /bin/bash um — mit Netz, bis ins Homelab (2026-10-19).
        umgebung = {"HOME": str(self.heim), "PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8",
                    "XERA_API_KEY": neu["schluessel"], "OPENCODE_SERVER_PASSWORD": self.passwort,
                    "OPENCODE_DISABLE_AUTOUPDATE": "1", "OPENCODE_DISABLE_LSP_DOWNLOAD": "1",
                    "OPENCODE_DISABLE_MODELS_FETCH": "1",
                    "OPENCODE_DISABLE_PROJECT_CONFIG": "1", "OPENCODE_CONFIG_PROJECT_DISABLE": "1"}
        # motor.log öffnet die Shell des Benutzers (siehe oben), --log-level warn: auf „info“
        # schrieb OpenCode jeden Befehl samt Argumenten ins Log, ohne Ende und Löschfrist
        self.prozess = subprocess.Popen(
            [*_als(self.uid), "prlimit", "--as=8589934592", "--nproc=512", "--",
             "sh", "-c", 'exec "$@" >>"$HOME/motor.log" 2>&1', "sh",
             str(OPENCODE), "serve", "--log-level", "warn", "--hostname", "127.0.0.1", "--port", str(self.port)],
            cwd=str(nutzer_ordner), env=umgebung, stdin=subprocess.DEVNULL,
            start_new_session=True)   # überlebt das Neuladen von uvicorn nicht als Kind — siehe aufraeumen_alt()
        PID_ORDNER.mkdir(parents=True, exist_ok=True)
        (PID_ORDNER / f"{self.uid}.pid").write_text(str(self.prozess.pid))
        frist = time.monotonic() + START_S
        async with httpx.AsyncClient(timeout=5) as c:
            while time.monotonic() < frist:
                if not self.lebt():
                    raise RuntimeError("OpenCode-Motor ist beim Start beendet worden (motor.log)")
                try:
                    if (await c.get(self.basis + "/api/info", auth=self.auth)).status_code == 200:
                        _log.info("motor: gestartet für %s (uid %s, Port %s)", self.user_id, self.uid, self.port)
                        self.zuletzt = time.monotonic()
                        return
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.4)
        raise RuntimeError("OpenCode-Motor antwortet nicht")

    def stoppen(self) -> None:
        if self.prozess is not None and self.prozess.poll() is None:
            try:
                os.killpg(self.prozess.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                self.prozess.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(self.prozess.pid, signal.SIGKILL)
        self.prozess = None
        if self.schluessel_id is not None:
            openai_api.schluessel_widerrufen(self.user_id, self.schluessel_id)
            self.schluessel_id = None
        (PID_ORDNER / f"{self.uid}.pid").unlink(missing_ok=True)


_MOTOREN: dict[str, Motor] = {}


def aufraeumen_alt() -> None:
    """Motoren aus einem früheren Prozess (uvicorn-Neuladen) beenden — sie laufen
    in eigenen Prozessgruppen weiter, ohne dass jemand sie kennt. Läuft beim Start
    des Backends (main.py), nicht beim Import: ein Skript, das dieses Modul lädt,
    würde sonst die laufenden Motoren beenden.

    Ihre internen Schlüssel gleich mit widerrufen — stoppen() lief für sie nie,
    sie blieben gültig und standen in der Schlüsselliste des Nutzers (2026-10-19:
    drei Stück beim Testnutzer nach Deploys). Auch ohne PID-Ordner (/run ist nach
    einem Neustart des Containers leer)."""
    if PID_ORDNER.is_dir():
        for datei in PID_ORDNER.glob("*.pid"):
            try:
                os.killpg(int(datei.read_text()), signal.SIGTERM)
            except (ValueError, ProcessLookupError, PermissionError):
                pass
            datei.unlink(missing_ok=True)
    n = openai_api.interne_widerrufen(SCHLUESSEL_NAME)
    if n:
        _log.info("motor: %s interne Schlüssel früherer Motoren widerrufen", n)


def _platz_fuer_motor(neu: Motor) -> None:
    """Vor dem Start eines Motors: Sind schon MAX_MOTOREN da, den am längsten ruhenden
    beenden. Arbeiten alle gerade, kommt dieser Nutzer nicht dran (RuntimeError → Meldung)."""
    laufende = [m for m in _MOTOREN.values() if m is not neu and m.lebt()]
    if len(laufende) < MAX_MOTOREN:
        return
    ruhend = [m for m in laufende if m.laufend == 0]
    if not ruhend:
        raise RuntimeError("Der Code-Bereich ist gerade voll belegt — versuch es in ein paar Minuten nochmal.")
    aeltester = min(ruhend, key=lambda m: m.zuletzt)
    _log.info("motor: %s Motoren laufen — %s (ruht am längsten) beendet", len(laufende), aeltester.user_id)
    aeltester.stoppen()


async def _platz_waechter(user_id: str) -> str:
    """Läuft neben einer Antwort her und kommt zurück, sobald der Arbeitsplatz des Nutzers
    deutlich über die Grenze wächst oder die Platte knapp wird — mit dem Satz für den Nutzer."""
    while True:
        await asyncio.sleep(5)
        grund = await asyncio.to_thread(arbeitsbereich.platz_pruefen, user_id,
                                        grenze=arbeitsbereich.PLATZ_JE_NUTZER + 512 * 1024**2)
        if grund:
            return grund


async def motor_fuer(user_id: str) -> Motor:
    m = _MOTOREN.get(str(user_id))
    if m is None:
        m = _MOTOREN[str(user_id)] = Motor(user_id)
    async with m.sperre:
        if not m.lebt():
            _platz_fuer_motor(m)
            await m.starten()
            try:
                await _aufraeumen(m, user_id)
            except Exception:   # Aufräumen darf die Antwort nie aufhalten
                _log.exception("motor: verwaiste OpenCode-Sitzungen löschen")
    m.zuletzt = time.monotonic()
    return m


# ── Gespräche: Xera-Sitzung ↔ OpenCode-Sitzung ─────────────────────────────

def _tabelle() -> None:
    from . import database as db
    conn = db.get_db()
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS motor_sitzungen (
            session_id INTEGER PRIMARY KEY, user_id TEXT NOT NULL, oc_id TEXT NOT NULL,
            fragen INTEGER DEFAULT 0, erstellt TEXT DEFAULT CURRENT_TIMESTAMP)""")
        conn.commit()
    finally:
        conn.close()


_tabelle()


def _zuordnung(session_id: int) -> tuple[str, int] | None:
    from . import database as db
    conn = db.get_db()
    try:
        r = conn.execute("SELECT oc_id, fragen FROM motor_sitzungen WHERE session_id=?", (session_id,)).fetchone()
        return (r["oc_id"], r["fragen"]) if r else None
    finally:
        conn.close()


def _zuordnen(session_id: int, user_id: str, oc_id: str, fragen: int) -> None:
    from . import database as db
    conn = db.get_db()
    try:
        conn.execute("INSERT INTO motor_sitzungen (session_id, user_id, oc_id, fragen) VALUES (?, ?, ?, ?) "
                     "ON CONFLICT(session_id) DO UPDATE SET oc_id=excluded.oc_id, fragen=excluded.fragen",
                     (session_id, str(user_id), oc_id, fragen))
        conn.commit()
    finally:
        conn.close()


def _verwaiste(user_id: str) -> list[tuple[int, str]]:
    """OpenCode-Sitzungen, deren Xera-Gespräch gelöscht ist."""
    from . import database as db
    conn = db.get_db()
    try:
        return [(r["session_id"], r["oc_id"]) for r in conn.execute(
            "SELECT m.session_id, m.oc_id FROM motor_sitzungen m LEFT JOIN chat_sessions s ON s.id = m.session_id "
            "WHERE m.user_id=? AND s.id IS NULL", (str(user_id),))]
    finally:
        conn.close()


async def _loeschen(motor: Motor, eintraege: list[tuple[int, str]]) -> None:
    from . import database as db
    async with httpx.AsyncClient(timeout=30, auth=motor.auth) as c:
        for session_id, oc_id in eintraege:
            # löscht auch die Kind-Sitzungen der Unteragenten; 404 = schon weg
            r = await c.delete(f"{motor.basis}/api/session/{oc_id}")
            if r.status_code not in (204, 404):
                _log.warning("motor: OpenCode-Sitzung %s nicht gelöscht (%s)", oc_id, r.status_code)
                continue
            conn = db.get_db()
            try:
                conn.execute("DELETE FROM motor_sitzungen WHERE session_id=?", (session_id,))
                conn.commit()
            finally:
                conn.close()


async def _aufraeumen(motor: Motor, user_id: str) -> None:
    """Beim Motorstart: jede OpenCode-Sitzung ohne lebendes Xera-Gespräch löschen — gelöschte
    Gespräche (vor 2026-10-19 oder fehlgeschlagen), verworfene Verläufe. Nur hier, solange
    noch keine Antwort läuft: eine eben angelegte Sitzung bekommt ihre Zuordnung erst nach
    dem ersten Prompt und sähe sonst verwaist aus."""
    from . import database as db
    await _loeschen(motor, _verwaiste(user_id))
    conn = db.get_db()
    try:
        behalten = {r["oc_id"] for r in conn.execute(
            "SELECT m.oc_id FROM motor_sitzungen m JOIN chat_sessions s ON s.id = m.session_id "
            "WHERE m.user_id=?", (str(user_id),))}
    finally:
        conn.close()
    async with httpx.AsyncClient(timeout=30, auth=motor.auth) as c:
        r = await c.get(f"{motor.basis}/api/session", params={"parentID": "null", "limit": "1000"})
        r.raise_for_status()
        weg = [s["id"] for s in r.json().get("data") or [] if s["id"] not in behalten]
        for oc_id in weg:
            await c.delete(f"{motor.basis}/api/session/{oc_id}")
    if weg:
        _log.info("motor: %s verwaiste OpenCode-Sitzungen von %s gelöscht", len(weg), user_id)
    await _shell_aufraeumen(motor)


async def _shell_aufraeumen(motor: Motor) -> None:
    """OpenCode legt die volle Ausgabe jedes Befehls unter shell/<Projekt-ID> ab (Projekt =
    Arbeitsordner eines Gesprächs) und löscht sie mit der Sitzung nicht mit. Ordner ohne
    Sitzung entfernen — als Sandkasten-Benutzer, der Ordner gehört ihm."""
    ordner = motor.heim / ".local" / "share" / "opencode" / "shell"
    try:   # erst die Ordner, dann die Sitzungen: ein Ordner entsteht erst nach seiner Sitzung
        vorhanden = [n for n in os.listdir(ordner) if re.fullmatch(r"[0-9a-f]{40}", n)]
    except OSError:
        return
    if not vorhanden:
        return
    async with httpx.AsyncClient(timeout=30, auth=motor.auth) as c:
        r = await c.get(f"{motor.basis}/api/session", params={"limit": "1000"})
        r.raise_for_status()
        behalten = {s.get("projectID") for s in r.json().get("data") or []}
    weg = [str(ordner / n) for n in vorhanden if n not in behalten]
    if weg:
        subprocess.run([*_als(motor.uid), "rm", "-rf", "--", *weg], env=_UMGEBUNG_KNAPP, timeout=60)


async def sitzung_loeschen(user_id: str) -> None:
    """Nach dem Löschen eines Xera-Gesprächs (main.py) auch OpenCodes Kopie davon löschen —
    Verlauf, Werkzeugausgaben, Unteragenten. Sonst bliebe sie im Speicher des Motors liegen,
    obwohl die Datenschutzerklärung sagt: Gespräche speichern wir, bis du sie löschst
    (2026-10-19). Startet den Motor dafür nötigenfalls; Reste früherer Löschungen gehen mit."""
    try:
        motor = await motor_fuer(user_id)
        await _loeschen(motor, _verwaiste(user_id))
        await _shell_aufraeumen(motor)
    except Exception:
        _log.exception("motor: OpenCode-Sitzung löschen")


def _text(inhalt) -> str:
    if isinstance(inhalt, list):
        return "\n".join(p.get("text", "") for p in inhalt if isinstance(p, dict) and p.get("type") == "text")
    return str(inhalt or "")


def _vorgeschichte(messages: list[dict], max_zeichen: int = 6000) -> str:
    """Bisheriges Gespräch als Text — wenn die OpenCode-Sitzung neu ist, das
    Xera-Gespräch aber schon Fragen hat (älteres Gespräch, Neu erzeugen, Bearbeiten)."""
    teile = []
    for m in messages[:-1]:
        t = _text(m.get("content")).strip()
        if t and m.get("role") in ("user", "assistant"):
            teile.append(("Nutzer: " if m["role"] == "user" else "Xera: ") + (t if len(t) < 1500 else t[:1500] + " …"))
    text = "\n\n".join(teile)
    return text[-max_zeichen:]


def _sse(daten: dict) -> str:
    return f"data: {json.dumps(daten, ensure_ascii=False)}\n\n"


_NEBENPRODUKTE = {".pyc", ".pyo", ".o", ".class"}
_LESEN = {"read", "glob", "grep", "list", "todoread", "lsp"}
_SCHREIBEN = {"write", "edit", "patch", "multiedit", "todowrite"}


_TAETIGKEIT = {"write": "schreibt eine Datei", "edit": "ändert eine Datei", "patch": "ändert Dateien",
               "multiedit": "ändert eine Datei", "read": "liest eine Datei", "glob": "sucht Dateien",
               "grep": "durchsucht Dateien", "list": "schaut in den Ordner", "bash": "führt einen Befehl aus",
               "shell": "führt einen Befehl aus", "task": "beauftragt einen Unteragenten",
               "todowrite": "plant die Schritte", "todoread": "schaut in die Aufgabenliste"}


def _stufe(name: str) -> str:
    """Farbe der Karte. Befehle laufen im Sandkasten ohne Netz — darum „schreibt“, nicht „Admin“."""
    n = (name or "").lower()
    if n in _LESEN:
        return "READ"
    return "WRITE" if n in _SCHREIBEN or n in ("bash", "shell") else "READ"


async def _kind_ereignis(typ: str, d: dict, lauf: str, namen: dict, argumente: dict, arbeit: Path,
                         log_action, user_id, session_id):
    """Ereignis eines Unteragenten → Schritt in seiner Agent-Karte (Feld ``lauf``)."""
    if typ == "session.tool.input.started":
        namen[d.get("id", "")] = d.get("name", "")
        n = d.get("name", "")
        yield _sse({"type": "status", "lauf": lauf, "status": _TAETIGKEIT.get(n, f"{n or 'Werkzeug'} …")})
    elif typ == "session.tool.called":
        name = namen.get(d.get("id", ""), "werkzeug")
        praefix = str(arbeit) + "/"
        zeigen = {k: (str(v).replace(praefix, "")[:400] if isinstance(v, str) else v)
                  for k, v in (d.get("input") or {}).items()}
        argumente[d.get("id", "")] = zeigen
        yield _sse({"type": "tool_call", "lauf": lauf, "id": d.get("id"), "name": name, "args": zeigen,
                    "level": _stufe(name)})
    elif typ in ("session.tool.success", "session.tool.failed", "session.tool.error"):
        name = namen.get(d.get("id", ""), "werkzeug")
        ausgabe = "\n".join(t.get("text", "") for t in d.get("content") or [] if isinstance(t, dict))
        ausgabe = (ausgabe or str(d.get("error") or d.get("message") or "")).replace(str(arbeit) + "/", "")
        log_action(str(user_id), session_id, name, argumente.get(d.get("id", ""), {}),
                   _stufe(name).lower(), typ == "session.tool.success", ausgabe)
        yield _sse({"type": "tool_result", "lauf": lauf, "id": d.get("id"), "name": name,
                    "success": typ == "session.tool.success",
                    "output": ausgabe[:300] + ("…" if len(ausgabe) > 300 else "")})


async def antworten(messages: list[dict], *, user_id: str, session_id: int, aufwand_stufe: str = "aus",
                    stop_event=None, denk_ende=None):
    """Eine Frage im Code-Bereich über OpenCode beantworten. Liefert Xera-SSE wie vermittler.antworten."""
    from . import kontext
    from . import database as db
    from .permissions import log_action
    from .tools import SANDBOX
    sb = SANDBOX.get() or {"user_id": str(user_id), "session_id": session_id, "admin": False}
    arbeit = arbeitsbereich.ordner(sb)
    frage = _text(messages[-1].get("content")).strip() if messages else ""
    fragen_bisher = sum(1 for m in messages if m.get("role") == "user")
    dokumente = [z.split(":", 1)[1].strip().rstrip("]") for z in frage.splitlines() if z.startswith("[Dokument-Datei:")]
    if dokumente:
        await arbeitsbereich.dokumente_uebernehmen(sb, dokumente)

    yield _sse({"type": "status", "status": "startet den Code-Motor"})
    try:
        motor = await motor_fuer(user_id)
    except Exception as e:
        _log.exception("motor: Start")
        yield _sse({"type": "error", "message": f"Code-Motor startet nicht: {e}"})
        return
    motor.laufend += 1
    stufe = aufwand.stufe(aufwand_stufe)
    vorher = {p.relative_to(arbeit).as_posix(): p.stat().st_mtime for p in arbeit.rglob("*")
              if p.is_file() and ".motor" not in p.parts}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15, read=None), auth=motor.auth) as c:
            zuordnung = _zuordnung(session_id)
            oc_id = None
            if zuordnung and zuordnung[1] < fragen_bisher:
                r = await c.get(f"{motor.basis}/api/session/{zuordnung[0]}")
                oc_id = zuordnung[0] if r.status_code == 200 else None
            text = frage
            if oc_id is None:
                if zuordnung:   # Frage bearbeitet / neu erzeugt: die alte Sitzung hält den verworfenen Verlauf
                    await c.delete(f"{motor.basis}/api/session/{zuordnung[0]}")
                r = await c.post(f"{motor.basis}/api/session", json={
                    "location": {"directory": str(arbeit)},
                    "model": {"providerID": "xera", "id": "xera-code", "variant": stufe if stufe != "aus" else "default"}})
                r.raise_for_status()
                oc_id = (r.json().get("data") or r.json())["id"]
                vor = _vorgeschichte(messages)
                if vor:
                    text = f"(Bisheriges Gespräch, zur Einordnung:\n{vor}\n)\n\n{frage}"
            await c.post(f"{motor.basis}/api/session/{oc_id}/model", json={
                "model": {"providerID": "xera", "id": "xera-code", "variant": stufe if stufe != "aus" else "default"}})

            ereignisse: asyncio.Queue = asyncio.Queue()

            async def lesen():
                async with c.stream("GET", f"{motor.basis}/api/event") as r:
                    async for z in r.aiter_lines():
                        if z.startswith("data:"):
                            try:
                                await ereignisse.put(json.loads(z[5:].strip()))
                            except ValueError:
                                pass

            leser = asyncio.create_task(lesen())
            await asyncio.sleep(0.2)
            r = await c.post(f"{motor.basis}/api/session/{oc_id}/prompt", json={"text": text})
            if r.status_code >= 400:
                leser.cancel()
                yield _sse({"type": "error", "message": f"Code-Motor: {r.text[:200]}"})
                return
            _zuordnen(session_id, user_id, oc_id, fragen_bisher)
            namen: dict[str, str] = {}
            argumente: dict[str, dict] = {}
            kinder: dict[str, dict] = {}              # Kind-Sitzung → Auftrag des Unteragenten
            offene_unteragenten: list[dict] = []       # Aufträge, deren Kind-Sitzung noch nicht da ist
            unteragent_aufrufe: dict[str, dict] = {}   # Werkzeugaufruf-ID → Auftrag
            geschrieben_text = ""                     # für die Bereinigung interner Pfade am Ende
            stop_warte = asyncio.create_task(stop_event.wait()) if stop_event else None
            denk_warte = asyncio.create_task(denk_ende.wait()) if denk_ende else None
            platz_warte = asyncio.create_task(_platz_waechter(user_id))
            try:
                while True:
                    holen = asyncio.create_task(ereignisse.get())
                    fertig, _ = await asyncio.wait({holen, platz_warte} | {t for t in (stop_warte, denk_warte) if t},
                                                   timeout=1800, return_when=asyncio.FIRST_COMPLETED)
                    if not fertig:
                        holen.cancel()
                        yield _sse({"type": "error", "message": "Der Code-Motor meldet sich seit 30 min nicht mehr."})
                        return
                    if platz_warte in fertig:
                        # Zu viel geschrieben: Antwort anhalten, bevor die Platte von CT 203 voll ist.
                        holen.cancel()
                        await c.post(f"{motor.basis}/api/session/{oc_id}/interrupt")
                        yield _sse({"type": "error", "message": f"Angehalten: {platz_warte.result()}"})
                        return
                    if denk_warte is not None and denk_warte in fertig:
                        # „Jetzt antworten“: die Schnittstelle beendet die laufende Denkrunde
                        # beim nächsten Denk-Stück (openai_api.DENKEN_BEENDEN), OpenCode macht weiter.
                        openai_api.DENKEN_BEENDEN.add(str(user_id))
                        denk_ende.clear()
                        denk_warte = asyncio.create_task(denk_ende.wait())
                        if holen not in fertig:
                            holen.cancel()
                            continue
                    if holen not in fertig:
                        holen.cancel()
                        await c.post(f"{motor.basis}/api/session/{oc_id}/interrupt")
                        yield _sse({"type": "stopped"})
                        return
                    e = holen.result()
                    d = e.get("data") or {}
                    typ = str(e.get("type", ""))
                    sid = d.get("sessionID")
                    # Unteragenten (OpenCode-Werkzeug „subagent“) arbeiten in Kind-Sitzungen —
                    # als Agent-Karte zeigen wie früher Xeras eigene Agents (S5b: 6 min nur „subagent“).
                    if typ == "session.created" and sid and sid != oc_id and sid not in kinder and (
                            d.get("parentID") == oc_id or d.get("parentID") in kinder or offene_unteragenten):
                        auftrag = offene_unteragenten.pop(0) if offene_unteragenten else {}
                        kinder[sid] = auftrag
                        yield _sse({"type": "auftrag_start", "lauf": sid, "kennung": f"opencode-{auftrag.get('agent', 'general')}",
                                    "name": f"Unteragent {auftrag.get('agent', 'general')}",
                                    "auftrag": str(auftrag.get("description") or auftrag.get("prompt") or "")[:300]})
                        continue
                    if sid in kinder:
                        motor.zuletzt = time.monotonic()
                        async for stueck in _kind_ereignis(typ, d, sid, namen, argumente, arbeit, log_action, user_id, session_id):
                            yield stueck
                        continue
                    if sid != oc_id:   # andere Sitzungen, Server-Ereignisse
                        continue
                    motor.zuletzt = time.monotonic()
                    if typ == "session.text.delta" and d.get("delta"):
                        geschrieben_text += d["delta"]
                        yield _sse({"content": d["delta"]})
                    elif "reasoning" in typ and d.get("delta"):
                        yield _sse({"type": "denken", "text": d["delta"]})
                    elif typ == "session.tool.input.started":
                        namen[d.get("id", "")] = d.get("name", "")
                        n = d.get("name", "")
                        yield _sse({"type": "status", "status": _TAETIGKEIT.get(n, f"{n or 'Werkzeug'} …")})
                    elif typ == "session.tool.called" and namen.get(d.get("id", "")) in ("subagent", "task"):
                        # Die Karte entsteht mit der Kind-Sitzung (oben); hier nur den Auftrag merken.
                        eingabe = d.get("input") or {}
                        offene_unteragenten.append(eingabe)
                        unteragent_aufrufe[d.get("id", "")] = eingabe
                    elif typ in ("session.tool.success", "session.tool.failed") and d.get("id") in unteragent_aufrufe:
                        text = "\n".join(t.get("text", "") for t in d.get("content") or [] if isinstance(t, dict))
                        text = re.sub(r"</?subagent[^>]*>", "", text).replace(str(arbeit) + "/", "").strip()
                        kind = (d.get("metadata") or {}).get("sessionID") or next(
                            (k for k, v in kinder.items() if v is unteragent_aufrufe[d["id"]]), None)
                        if kind:
                            yield _sse({"type": "auftrag_fertig", "lauf": kind, "ok": typ == "session.tool.success",
                                        "zusammenfassung": text[:800]})
                        log_action(str(user_id), session_id, "subagent", unteragent_aufrufe[d["id"]],
                                   "write", typ == "session.tool.success", text)
                    elif typ == "session.tool.called":
                        name = namen.get(d.get("id", ""), d.get("name", "werkzeug"))
                        eingabe = d.get("input") or {}
                        # Interne Serverpfade (/var/lib/xera-arbeit/u…/s…/) nicht zeigen.
                        praefix = str(arbeit) + "/"
                        zeigen = {k: (str(v).replace(praefix, "").replace(str(arbeit), ".") if isinstance(v, str) else v)
                                  for k, v in eingabe.items()}
                        zeigen = {k: (v if len(str(v)) < 400 else str(v)[:400] + " …") for k, v in zeigen.items()}
                        argumente[d.get("id", "")] = zeigen
                        yield _sse({"type": "tool_call", "id": d.get("id"), "name": name, "args": zeigen, "level": _stufe(name)})
                    elif typ in ("session.tool.success", "session.tool.failed", "session.tool.error"):
                        name = namen.get(d.get("id", ""), "werkzeug")
                        ausgabe = "\n".join(t.get("text", "") for t in d.get("content") or [] if isinstance(t, dict))
                        ausgabe = (ausgabe or str(d.get("error") or d.get("message") or "")).replace(str(arbeit) + "/", "")
                        # Werkzeugprotokoll wie bei Xeras eigenen Werkzeugen (Datenschutz 2.5).
                        log_action(str(user_id), session_id, name, argumente.get(d.get("id", ""), {}),
                                   _stufe(name).lower(), typ == "session.tool.success", ausgabe)
                        yield _sse({"type": "tool_result", "id": d.get("id"), "name": name,
                                    "success": typ == "session.tool.success",
                                    "output": ausgabe[:300] + ("…" if len(ausgabe) > 300 else "")})
                    elif typ == "session.renamed" and d.get("title") and session_id:
                        db.update_session_title(session_id, d["title"][:80])
                    elif typ == "session.step.ended":
                        # Kontextgrösse dieses Schritts. Nicht session.usage.updated — das zählt
                        # über die ganze Sitzung zusammen (kleine Aufgabe: 15 810 statt ~5 500).
                        t = d.get("tokens") or {}
                        belegt = (int(t.get("input") or 0) + int((t.get("cache") or {}).get("read") or 0)
                                  + int(t.get("output") or 0))
                        if belegt:
                            yield _sse(kontext.ereignis(belegt, False))
                    elif typ.startswith("session.execution.") and typ != "session.execution.started":
                        if typ != "session.execution.succeeded":
                            grund = d.get("error") or d.get("message") or typ.rsplit(".", 1)[-1]
                            yield _sse({"type": "error", "message": f"Code-Motor: {str(grund)[:200]}"})
                        break
            finally:
                leser.cancel()
                for t in (stop_warte, denk_warte, platz_warte):
                    if t:
                        t.cancel()
                openai_api.DENKEN_BEENDEN.discard(str(user_id))

        # Interne Serverpfade aus der Antwort (das Modell nennt manchmal /var/lib/xera-arbeit/u…/s…/datei).
        # Live sind sie kurz zu sehen, gespeichert und angezeigt wird die bereinigte Fassung.
        if str(arbeit) in geschrieben_text:
            yield _sse({"type": "ersetzen", "content": geschrieben_text.replace(str(arbeit) + "/", "").replace(str(arbeit), ".")})

        # Geänderte Dateien: Download-Link, HTML zusätzlich im echten Browser testen
        # (Xera-Extra wie bisher im Code-Bereich).
        # Nur, was der Nutzer haben will: keine versteckten Ordner, kein __pycache__/node_modules,
        # keine Übersetzungsreste (S5b am 19.10.: primzahlen.cpython-312.pyc bekam einen Link).
        nachher = {p.relative_to(arbeit).as_posix(): p.stat().st_mtime for p in arbeit.rglob("*")
                   if p.is_file() and p.suffix not in _NEBENPRODUKTE
                   and not any(t.startswith(".") or t in ("__pycache__", "node_modules") for t in p.relative_to(arbeit).parts)}
        neu = sorted(p for p, t in nachher.items() if vorher.get(p) != t)[:8]
        zeilen = []
        for rel in neu:
            url = await arbeitsbereich.download(sb, rel)
            if not url:
                continue
            zeile = f"**Datei:** [{rel}]({url})"
            if rel.lower().endswith((".html", ".htm")):
                yield _sse({"type": "status", "status": f"testet {rel} im Browser"})
                test = await arbeitsbereich.ausfuehren("datei_testen", {"path": rel}, sb)
                ausgabe = (test.get("output") or "").strip()
                if test.get("success") and "keine Fehler" in ausgabe:
                    zeile += " · Im Browser getestet: keine Fehler"
                else:
                    erste = next((z for z in ausgabe.splitlines() if z.strip()), "Test nicht möglich")
                    zeile += f" · Im Browser getestet: {erste[:200]}"
            zeilen.append(zeile)
        if zeilen:
            yield _sse({"content": "\n\n" + "\n\n".join(zeilen)})
    except httpx.HTTPError as e:
        _log.warning("motor: %s", e)
        yield _sse({"type": "error", "message": f"Code-Motor nicht erreichbar: {type(e).__name__}"})
    finally:
        motor.laufend -= 1
        motor.zuletzt = time.monotonic()


def hat_sitzung(session_id: int | None) -> bool:
    """Läuft dieses Xera-Gespräch über den Motor (Code-Bereich)?"""
    return bool(session_id) and _zuordnung(int(session_id)) is not None


async def verdichten(user_id: str, session_id: int) -> int | None:
    """„Zusammenfassen und weiter“ im Code-Bereich: OpenCode fasst seinen eigenen
    Verlauf zusammen (dort liegt der Kontext, nicht in Xeras Nachrichten).
    Liefert die geschätzte Grösse danach (Tokens) oder None."""
    zuordnung = _zuordnung(session_id)
    if not zuordnung:
        return None
    motor = await motor_fuer(user_id)
    oc_id = zuordnung[0]
    async with httpx.AsyncClient(timeout=httpx.Timeout(15, read=1800), auth=motor.auth) as c:
        r = await c.post(f"{motor.basis}/api/session/{oc_id}/compact", json={})
        if r.status_code >= 400:
            _log.warning("motor: compact %s: %s", r.status_code, r.text[:200])
            return None
        await c.post(f"{motor.basis}/api/experimental/session/{oc_id}/wait", json={})
        # Was jetzt im Kontext steht (die Sitzungs-Tokens sind eine Summe über alle Schritte).
        r = await c.get(f"{motor.basis}/api/session/{oc_id}/context")
        inhalt = r.json().get("data") if r.status_code == 200 else None
    motor.zuletzt = time.monotonic()
    if inhalt is None:
        return None
    from . import kontext
    # + OpenCodes Systemprompt mit Werkzeugen (gemessen 5 290 Tokens)
    return int(len(json.dumps(inhalt, ensure_ascii=False)) / kontext.ZEICHEN_PRO_TOKEN) + 5300


async def ruhe_schleife() -> None:
    """Motoren ohne Anfrage seit RUHE_S beenden (spart RAM — ~250 MB je Motor)."""
    while True:
        await asyncio.sleep(60)
        for m in list(_MOTOREN.values()):
            if m.lebt() and m.laufend == 0 and time.monotonic() - m.zuletzt > RUHE_S:
                _log.info("motor: %s ruht seit %s min — beendet", m.user_id, RUHE_S // 60)
                m.stoppen()

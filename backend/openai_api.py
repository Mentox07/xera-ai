"""OpenAI-kompatible Schnittstelle für OpenCode — die Xera-CLI seit 2026-10-17.

OpenCode spricht ``/v1/chat/completions`` wie mit jedem anderen Anbieter. Xera
prüft den Schlüssel, legt die Anfrage auf den CLI-Slot und reicht sie an
llama-server durch. Direkt an llama-server ginge auch, aber dann wählt
llama.cpp den Slot selbst — oft den des Chats — und der Fehler „belegter Slot“
aus Gespräch 580 wäre zurück (siehe slotsperre.py). Plan:
docs/plan-cli-opencode-2026-10.md.

Gespeichert werden keine Inhalte, nur Tokens und Dauer je Anfrage
(Tabelle ``api_nutzung``). Schlüssel liegen nur als SHA-256 in der Datenbank.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import os
import secrets
import time

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from . import aufwand
from . import config
from . import database as db
from . import slotsperre

_log = logging.getLogger("xera.openai_api")
router = APIRouter()

# Siebter llama-Slot (--parallel 7 seit 2026-10-17) gehört der CLI allein.
CLI_SLOT = 6
# Kleine Nebenaufgaben von OpenCode (Titel, Zusammenfassungen) — sie dürfen den
# grossen Verlauf im CLI-Slot nicht verdrängen.
KLEIN_SLOT = 4
# Web-Code-Bereich (seit 2026-10-19 OpenCode auf dem Server, code_motor.py): Slot 1 wie bisher.
CODE_SLOT = 1
MODELLE = {"xera": CLI_SLOT, "xera-klein": KLEIN_SLOT, "xera-code": CODE_SLOT}
MAX_TOKENS = 16384
MAX_TOKENS_KLEIN = 2048
# Was vom Client durchgeht. Sampling bleibt bei den Werten des Servers (wie im Web),
# Slot, Cache und Speicherbefehle von llama-server sind Sache von Xera.
ERLAUBT = {"messages", "tools", "tool_choice", "stream", "stream_options", "max_tokens",
           "max_completion_tokens", "stop", "parallel_tool_calls", "response_format", "seed"}

# „Jetzt antworten“ im Web-Code-Bereich (code_motor.py): Nutzer, deren laufende
# Denkrunde Xera beim nächsten Denk-Stück beenden soll.
DENKEN_BEENDEN: set[str] = set()

# Kein Lese-Zeitlimit: Einlesen eines langen Verlaufs dauert Minuten.
_client = httpx.AsyncClient(timeout=httpx.Timeout(connect=10.0, read=None, write=60.0, pool=None))


def _tabellen() -> None:
    conn = db.get_db()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS api_schluessel (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                hash TEXT NOT NULL UNIQUE,
                anfang TEXT NOT NULL,
                erstellt TEXT DEFAULT CURRENT_TIMESTAMP,
                zuletzt TEXT,
                widerrufen TEXT
            );
            CREATE TABLE IF NOT EXISTS api_nutzung (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                schluessel_id INTEGER,
                zeit TEXT DEFAULT CURRENT_TIMESTAMP,
                modell TEXT,
                tokens_rein INTEGER,
                tokens_cache INTEGER,
                tokens_raus INTEGER,
                dauer_ms INTEGER,
                status TEXT
            );
            CREATE INDEX IF NOT EXISTS api_nutzung_nutzer_zeit ON api_nutzung(user_id, zeit);
        """)
        conn.commit()
    finally:
        conn.close()


_tabellen()


def _hash(schluessel: str) -> str:
    return hashlib.sha256(schluessel.encode()).hexdigest()


def schluessel_erzeugen(user_id: str, name: str) -> dict:
    """Neuer Schlüssel; der Klartext wird nur hier zurückgegeben, nie gespeichert."""
    klartext = "xera_" + secrets.token_urlsafe(32)
    name = (name or "OpenCode")[:64]
    conn = db.get_db()
    try:
        cur = conn.execute("INSERT INTO api_schluessel (user_id, name, hash, anfang) VALUES (?, ?, ?, ?)",
                           (user_id, name, _hash(klartext), klartext[:9]))
        conn.commit()
        return {"id": cur.lastrowid, "name": name, "schluessel": klartext, "anfang": klartext[:9]}
    finally:
        conn.close()


def schluessel_liste(user_id: str) -> list[dict]:
    """Die CLI-Schlüssel des Nutzers — ohne die internen des Code-Motors (``intern:…``,
    je Motorstart neu): die gehören weder in seine Liste noch in sein Limit von 10."""
    conn = db.get_db()
    try:
        return [dict(r) for r in conn.execute(
            "SELECT id, name, anfang, erstellt, zuletzt FROM api_schluessel "
            "WHERE user_id=? AND widerrufen IS NULL AND name NOT LIKE 'intern:%' ORDER BY id DESC", (user_id,))]
    finally:
        conn.close()


def interne_widerrufen(name: str) -> int:
    """Alle noch gültigen internen Schlüssel dieses Namens widerrufen — die Motoren
    eines früheren Backend-Prozesses (code_motor.aufraeumen_alt)."""
    conn = db.get_db()
    try:
        n = conn.execute("UPDATE api_schluessel SET widerrufen=CURRENT_TIMESTAMP "
                         "WHERE name=? AND widerrufen IS NULL", (name,)).rowcount
        conn.commit()
        return n
    finally:
        conn.close()


def schluessel_widerrufen(user_id: str, schluessel_id: int) -> bool:
    conn = db.get_db()
    try:
        n = conn.execute("UPDATE api_schluessel SET widerrufen=CURRENT_TIMESTAMP "
                         "WHERE id=? AND user_id=? AND widerrufen IS NULL", (schluessel_id, user_id)).rowcount
        conn.commit()
        return n > 0
    finally:
        conn.close()


def _fehler(status: int, text: str, art: str = "invalid_request_error", warten: int | None = None) -> JSONResponse:
    kopf = {"Retry-After": str(warten)} if warten else None
    return JSONResponse({"error": {"message": text, "type": art}}, status_code=status, headers=kopf)


class _Schutz:
    """Absicherung für den offenen Zugang ohne VPN (seit 2026-10-19; Wunsch des Betreibers: „in
    Zukunft wird die CLI offen sein“). Alles im Speicher dieses Prozesses — nach
    einem Neustart beginnen die Zähler neu, die Tagesmenge kommt aus der Datenbank.

    * falsche Schlüssel: je IP höchstens FEHL_MAX in 10 min, dann 15 min gesperrt
    * Anfragen je Nutzer: höchstens PRO_MINUTE pro Minute und PRO_TAG pro Tag
    * neu eingelesene + geschriebene Tokens je Nutzer und Tag: TOKENS_PRO_TAG
    * gleichzeitig (laufend + wartend) je Nutzer: GLEICHZEITIG
    * Anfragen grösser als MAX_BYTES werden gar nicht erst gelesen
    Admins sind von den Mengen ausgenommen, nicht von der Sperre bei falschen Schlüsseln.
    """
    FEHL_MAX = 20
    FEHL_FENSTER_S = 600
    SPERRE_S = 900
    PRO_MINUTE = 60
    PRO_TAG = 3000
    TOKENS_PRO_TAG = 3_000_000
    GLEICHZEITIG = 3
    MAX_BYTES = 8 * 1024 * 1024

    def __init__(self):
        self.fehl: dict[str, list[float]] = {}
        self.gesperrt: dict[str, float] = {}
        self.anfragen: dict[str, list[float]] = {}
        # Startzeiten laufender Anfragen; Einträge älter als 2 h zählen nicht mehr
        # (falls ein Strom nie begann und `fertig` darum nie kam).
        self.laufend: dict[str, list[float]] = {}

    # Eigenes Netz, VPN und die eigene öffentliche IP (Hairpin-NAT: alle internen
    # Geräte kommen mit ihr an) nie sperren — sonst sperrt EIN falsch eingerichteter
    # Rechner das ganze Haus aus (2026-10-19 im Test passiert). Wie ignoreip im
    # fail2ban-Jail xera-cli. Die Netze stehen in .env (XERA_INTERN_NETZE, mit Komma).
    INTERN = tuple(ipaddress.ip_network(n.strip()) for n in
                   ("127.0.0.0/8," + os.getenv("XERA_INTERN_NETZE", "")).split(",") if n.strip())

    @staticmethod
    def ip(request: Request) -> str:
        weiter = request.headers.get("x-forwarded-for", "")
        return weiter.split(",")[0].strip() or (request.client.host if request.client else "?")

    def intern(self, ip: str) -> bool:
        try:
            adresse = ipaddress.ip_address(ip)
        except ValueError:
            return False
        return any(adresse in netz for netz in self.INTERN)

    def ip_gesperrt(self, ip: str) -> int:
        bis = self.gesperrt.get(ip, 0)
        return max(0, int(bis - time.time()))

    def fehlversuch(self, ip: str) -> None:
        if self.intern(ip):
            return
        jetzt = time.time()
        liste = [t for t in self.fehl.get(ip, []) if jetzt - t < self.FEHL_FENSTER_S] + [jetzt]
        self.fehl[ip] = liste
        if len(liste) >= self.FEHL_MAX:
            self.gesperrt[ip] = jetzt + self.SPERRE_S
            self.fehl.pop(ip, None)
            _log.warning("v1: IP %s nach %s falschen Schlüsseln für %s min gesperrt", ip, self.FEHL_MAX, self.SPERRE_S // 60)

    def zulassen(self, nutzer: dict) -> JSONResponse | None:
        """Mengen und Gleichzeitigkeit prüfen; bei Erfolg zählt die Anfrage als laufend."""
        uid = nutzer["id"]
        if not nutzer.get("is_admin"):
            jetzt = time.time()
            liste = [t for t in self.anfragen.get(uid, []) if jetzt - t < 86400]
            if sum(1 for t in liste if jetzt - t < 60) >= self.PRO_MINUTE:
                return _fehler(429, "Zu viele Anfragen pro Minute — kurz warten.", "rate_limit_error", 30)
            if len(liste) >= self.PRO_TAG:
                return _fehler(429, "Tagesgrenze für Anfragen erreicht.", "rate_limit_error", 3600)
            if _tokens_heute(uid) >= self.TOKENS_PRO_TAG:
                return _fehler(429, "Tagesgrenze für Tokens erreicht.", "rate_limit_error", 3600)
            self.anfragen[uid] = liste + [jetzt]
        jetzt = time.time()
        laufend = [t for t in self.laufend.get(uid, []) if jetzt - t < 7200]
        if len(laufend) >= self.GLEICHZEITIG:
            return _fehler(429, "Zu viele gleichzeitige Anfragen — warte, bis eine fertig ist.", "rate_limit_error", 10)
        self.laufend[uid] = laufend + [jetzt]
        return None

    def fertig(self, uid: str) -> None:
        self.laufend[uid] = self.laufend.get(uid, [])[1:]


_schutz = _Schutz()


def _tokens_heute(user_id: str) -> int:
    """Heute neu eingelesene und geschriebene Tokens (Cache zählt nicht — der kostet fast nichts)."""
    conn = db.get_db()
    try:
        r = conn.execute(
            "SELECT COALESCE(SUM(COALESCE(tokens_rein,0) - COALESCE(tokens_cache,0) + COALESCE(tokens_raus,0)), 0) "
            "FROM api_nutzung WHERE user_id=? AND zeit >= date('now')", (user_id,)).fetchone()
        return int(r[0] or 0)
    finally:
        conn.close()


async def _anmelden(request: Request) -> tuple[dict, int] | JSONResponse:
    ip = _schutz.ip(request)
    warten = _schutz.ip_gesperrt(ip)
    if warten:
        return _fehler(429, "Zu viele falsche Schlüssel von dieser Adresse — später nochmal.", "rate_limit_error", warten)
    ergebnis = await _schluessel_pruefen(request)
    if isinstance(ergebnis, JSONResponse) and ergebnis.status_code == 401:
        _schutz.fehlversuch(ip)
    return ergebnis


async def _schluessel_pruefen(request: Request) -> tuple[dict, int] | JSONResponse:
    kopf = request.headers.get("Authorization", "")
    if not kopf.startswith("Bearer "):
        return _fehler(401, "Xera-Schlüssel fehlt (Einstellungen → CLI).", "authentication_error")
    conn = db.get_db()
    try:
        zeile = conn.execute("SELECT id, user_id, name FROM api_schluessel WHERE hash=? AND widerrufen IS NULL",
                             (_hash(kopf[7:].strip()),)).fetchone()
        if zeile:
            conn.execute("UPDATE api_schluessel SET zuletzt=CURRENT_TIMESTAMP WHERE id=?", (zeile["id"],))
            conn.commit()
    finally:
        conn.close()
    # Interne Schlüssel (Code-Motor, code_motor.py) gelten nur auf diesem Server: der Motor fragt über
    # 127.0.0.1, ein aus dem Sandkasten gelesener Schlüssel ist von aussen wertlos. Dafür ohne Pro-Prüfung —
    # den Code-Bereich dürfen auch Gratis-Nutzer im Rahmen ihrer Freifragen (/api/chat zählt sie, 2026-10-19).
    intern = zeile is not None and str(zeile["name"]).startswith("intern:")
    if not zeile or (intern and (request.client is None or request.client.host != "127.0.0.1")):
        return _fehler(401, "Unbekannter oder widerrufener Xera-Schlüssel.", "authentication_error")
    nutzer = db.get_user(zeile["user_id"])
    if not intern:
        # Pro höchstens 15 min alt (rollen.py) — bis 2026-10-19 galt die Angabe vom letzten
        # Login, ein CLI-Schlüssel blieb also gültig, auch wenn Discord die Rolle längst entzog.
        from .rollen import rollen_auffrischen
        nutzer = await rollen_auffrischen(nutzer)
    if not nutzer or not (intern or nutzer.get("is_pro") or nutzer.get("is_admin")):
        return _fehler(403, "Die Xera-CLI ist für Pro-Nutzer.", "permission_error")
    return nutzer, zeile["id"]


def _nutzung(user_id: str, schluessel_id: int, modell: str, usage: dict | None, start: float, status: str) -> None:
    usage = usage or {}
    try:
        conn = db.get_db()
        try:
            conn.execute(
                "INSERT INTO api_nutzung (user_id, schluessel_id, modell, tokens_rein, tokens_cache, tokens_raus, "
                "dauer_ms, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, schluessel_id, modell, usage.get("prompt_tokens"),
                 (usage.get("prompt_tokens_details") or {}).get("cached_tokens"), usage.get("completion_tokens"),
                 int((time.monotonic() - start) * 1000), status))
            conn.commit()
        finally:
            conn.close()
    except Exception:  # Zählen darf die Antwort nie verhindern
        _log.exception("v1: Nutzung nicht gespeichert")


def stufe_aus(body: dict) -> str:
    """Denkaufwand aus der Anfrage: ``xera_aufwand`` (Varianten in opencode.jsonc),
    ``reasoning_effort`` (OpenAI-Name) oder das blosse ``enable_thinking`` (= mittel).

    Gedacht wird nur im ersten Schritt einer Frage — nicht nach einem
    Werkzeugergebnis (letzte Nachricht „tool“). So hält es auch vermittler.py.
    Gemessen 2026-10-19 (Snake mit Extras, Code-Bereich): mit Denken in jedem
    Schritt 12,9 min, weil jeder Schritt neu dachte und der Verlauf ohne die
    Gedanken anders aussah als erzeugt (Cache weg, bis 7 000 Tokens neu einlesen)."""
    nachrichten = body.get("messages") or []
    if nachrichten and isinstance(nachrichten[-1], dict) and nachrichten[-1].get("role") == "tool":
        return "aus"
    for feld in ("xera_aufwand", "reasoning_effort"):
        if body.get(feld):
            return aufwand.stufe(body[feld])
    kwargs = body.get("chat_template_kwargs") if isinstance(body.get("chat_template_kwargs"), dict) else {}
    return "mittel" if kwargs.get("enable_thinking") else "aus"


def anfrage_bauen(body: dict) -> tuple[str, dict]:
    """Aus der Anfrage von OpenCode die an llama-server machen: nur erlaubte Felder,
    fester Slot, Obergrenzen, Denkaufwand wie im Web (aufwand.py)."""
    modell = body.get("model") if body.get("model") in MODELLE else "xera"
    klein = modell == "xera-klein"
    anfrage = {k: v for k, v in body.items() if k in ERLAUBT}
    stufe = "aus" if klein else stufe_aus(body)
    try:
        wunsch = int(anfrage.pop("max_completion_tokens", None) or anfrage.get("max_tokens") or MAX_TOKENS)
    except (TypeError, ValueError):
        wunsch = MAX_TOKENS
    anfrage["max_tokens"] = max(1, min(wunsch, MAX_TOKENS_KLEIN if klein else MAX_TOKENS))
    anfrage["model"] = "xera-ai"
    anfrage["id_slot"] = MODELLE[modell]
    if anfrage.get("stream"):
        anfrage["stream_options"] = {"include_usage": True}
        # Fortschritt beim Einlesen — hält die Verbindung offen, solange llama-server
        # minutenlang einliest, und wird ab und zu als Denk-Text sichtbar (Einlesen).
        anfrage["return_progress"] = True
    anfrage["max_tokens"] += aufwand.anfrage_ergaenzen(anfrage, stufe)
    return modell, anfrage


def _zahl(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def _dauer(sekunden: float) -> str:
    return "noch unter einer Minute" if sekunden < 60 else f"noch etwa {round(sekunden / 60)} min"


class Einlesen:
    """Fortschritt beim Einlesen als Denk-Text, den OpenCode anzeigt (seit 2026-10-20).

    Vorher ging er nur als SSE-Kommentar hinaus, und den zeigt OpenCode nicht: Nach
    der Kompaktierung im Bug-Export vom 2026-10-19 las Xera 113k Tokens ein (~17 min)
    und die CLI sah so lange tot aus — der Nutzer brach zweimal ab. Gemeldet wird erst ab
    AB_TOKENS neuen Tokens, dann alle SCHRITT Prozent. OpenCode schickt Gedanken nicht
    zurück (siehe stufe_aus), der Cache des nächsten Schritts bleibt also gleich.

    ``processed`` von llama-server zählt den Cache mit — neu ist nur, was darüber liegt."""

    AB_TOKENS = 8000   # ≈ 1 min bei 130–175 Tokens/s Einlesen
    SCHRITT = 10

    def __init__(self) -> None:
        self.gemeldet: int | None = None

    def meldung(self, p: dict) -> str:
        try:
            cache = int(p.get("cache") or 0)
            neu = int(p.get("total") or 0) - cache
            fertig = int(p.get("processed") or 0) - cache
            sekunden = float(p.get("time_ms") or 0) / 1000
        except (TypeError, ValueError):
            return ""
        if neu < self.AB_TOKENS or fertig >= neu:
            return ""
        if self.gemeldet is None:
            self.gemeldet = 0
            gespeichert = f", {_zahl(cache)} liegen schon im Zwischenspeicher" if cache else ""
            return (f"Lese den Verlauf ein: {_zahl(neu)} Tokens{gespeichert}. "
                    "Bei dieser Länge dauert das eine Weile, bevor ich weiterarbeite.\n")
        prozent = int(100 * fertig / neu)
        if prozent < self.gemeldet + self.SCHRITT:
            return ""
        self.gemeldet = prozent - prozent % self.SCHRITT
        rest = sekunden * (neu - fertig) / fertig if fertig > 0 else 0
        return f"… {self.gemeldet} % eingelesen, {_dauer(rest)}\n"


def stueck_umschreiben(nutzlast: str, einlesen: Einlesen | None = None) -> tuple[str | None, dict | None, str]:
    """Ein ``data:``-Stück von llama-server für OpenCode aufbereiten.
    Liefert (SSE-Text, usage, Denktext). Fortschritt wird zum Kommentar (hält die
    Verbindung offen) und mit ``einlesen`` ab und zu zum sichtbaren Denk-Text;
    der zählt nicht als Denken (kein Denktext zurück)."""
    if nutzlast.strip() == "[DONE]":
        return "data: [DONE]\n\n", None, ""
    try:
        stueck = json.loads(nutzlast)
    except ValueError:
        return f"data: {nutzlast}\n\n", None, ""
    if not isinstance(stueck, dict):
        return f"data: {nutzlast}\n\n", None, ""
    p = stueck.pop("prompt_progress", None)
    deltas = [c.get("delta") or {} for c in stueck.get("choices") or []]
    # Diese llama-Version legt den Fortschritt in Stücke mit leerem Delta (role, content null).
    if p and not any(d.get("content") or d.get("reasoning_content") or d.get("tool_calls") for d in deltas):
        text = einlesen.meldung(p) if einlesen else ""
        if not text:
            return ": liest ein\n\n", None, ""
        stueck["choices"] = [{"index": 0, "finish_reason": None,
                              "delta": {"role": "assistant", "reasoning_content": text}}]
        return f"data: {json.dumps(stueck, ensure_ascii=False)}\n\n", None, ""
    denk = "".join(d.get("reasoning_content") or "" for d in deltas)
    return f"data: {json.dumps(stueck, ensure_ascii=False)}\n\n", stueck.get("usage"), denk


@router.get("/v1/models")
async def modelle(request: Request):
    ergebnis = await _anmelden(request)
    if isinstance(ergebnis, JSONResponse):
        return ergebnis
    return {"object": "list", "data": [{"id": m, "object": "model", "owned_by": "xera"} for m in MODELLE]}


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    ergebnis = await _anmelden(request)
    if isinstance(ergebnis, JSONResponse):
        return ergebnis
    nutzer, schluessel_id = ergebnis
    try:
        groesse = int(request.headers.get("content-length") or 0)
    except ValueError:
        groesse = 0
    if groesse > _Schutz.MAX_BYTES:
        return _fehler(413, "Anfrage zu gross.")
    try:
        roh = await request.body()
        if len(roh) > _Schutz.MAX_BYTES:
            return _fehler(413, "Anfrage zu gross.")
        body = json.loads(roh)
    except ValueError:
        return _fehler(400, "Kein gültiges JSON.")
    if not isinstance(body, dict) or not isinstance(body.get("messages"), list) or not body["messages"]:
        return _fehler(400, "messages fehlt.")
    if len(body["messages"]) > 4000 or len(body.get("tools") or []) > 256:
        return _fehler(400, "Zu viele Nachrichten oder Werkzeuge.")
    abgelehnt = _schutz.zulassen(nutzer)
    if abgelehnt is not None:
        return abgelehnt
    modell, anfrage = anfrage_bauen(body)
    slot = anfrage["id_slot"]
    url = f"{config.LLAMA_API_URL}/v1/chat/completions"
    start = time.monotonic()

    if not anfrage.get("stream"):
        try:
            async with slotsperre.slot(slot):
                await slotsperre.warten_bis_frei(_client, config.LLAMA_API_URL, slot)
                await slotsperre.leeren_slot_anstossen(_client, config.LLAMA_API_URL, slot)
                r = await _client.post(url, json=anfrage)
        finally:
            _schutz.fertig(nutzer["id"])
        try:
            daten = r.json()
        except ValueError:
            daten = {"error": {"message": r.text[:500], "type": "server_error"}}
        _nutzung(nutzer["id"], schluessel_id, modell, daten.get("usage") if isinstance(daten, dict) else None,
                 start, str(r.status_code))
        return JSONResponse(daten, status_code=r.status_code)

    stufe = "aus" if modell == "xera-klein" else stufe_aus(body)
    denk_budget = aufwand.budget(stufe)

    async def strom():
        usage, status = None, "200"
        anf = anfrage
        try:
            if slotsperre.belegt(slot):
                yield ": wartet, bis die vorige CLI-Anfrage fertig ist\n\n"
            async with slotsperre.slot(slot):
                # Höchstens zwei Durchgänge: der zweite nur, wenn Xera das Denken
                # beendet hat (Code im Denken oder Zeitgrenze, wie im Web).
                for durchgang in range(2):
                    await slotsperre.warten_bis_frei(_client, config.LLAMA_API_URL, slot)
                    await slotsperre.leeren_slot_anstossen(_client, config.LLAMA_API_URL, slot)
                    gedanken, denk_start, geprueft, grund = "", None, 0, None
                    # Titel und Zusammenfassungen (xera-klein) ohne Denk-Text — der landete sonst im Ergebnis.
                    einlesen = None if modell == "xera-klein" else Einlesen()
                    async with _client.stream("POST", url, json=anf) as r:
                        if r.status_code != 200:
                            text = (await r.aread()).decode(errors="replace")
                            status = str(r.status_code)
                            _log.warning("v1: llama %s: %s", r.status_code, text[:300])
                            try:
                                fehler = json.loads(text)
                            except ValueError:
                                fehler = {"error": {"message": text[:500], "type": "server_error"}}
                            yield f"data: {json.dumps(fehler, ensure_ascii=False)}\n\n"
                            return
                        async for zeile in r.aiter_lines():
                            if not zeile.startswith("data: "):
                                continue
                            text, neu, denk = stueck_umschreiben(zeile[6:], einlesen)
                            usage = neu or usage
                            if denk and "chat_template_kwargs" in anf:
                                gedanken += denk
                                denk_start = denk_start or time.monotonic()
                                if len(gedanken) - geprueft >= 300:
                                    geprueft = len(gedanken)
                                    if aufwand.code_im_denken(gedanken):
                                        grund = "im Nachdenken stand schon Code"
                                if not grund and time.monotonic() - denk_start > aufwand.sekunden(stufe):
                                    grund = f"die Denkzeit der Stufe „{stufe}“ ist um"
                                if not grund and nutzer["id"] in DENKEN_BEENDEN:
                                    DENKEN_BEENDEN.discard(nutzer["id"])
                                    grund = "du hast „Jetzt antworten“ gedrückt"
                            if text:
                                yield text
                            if grund:
                                break   # Verbindung zu → llama-server bricht die Aufgabe ab
                    if not grund:
                        return
                    _log.info("v1: Denken beendet (%s) nach %s Zeichen", grund, len(gedanken))
                    yield f": Denken beendet ({grund}) — schreibt die Antwort\n\n"
                    anf = aufwand.anfrage_ohne_denken(anf)
                    anf["max_tokens"] -= denk_budget
                    anf["messages"] = list(anf["messages"]) + [
                        {"role": "user", "content": aufwand.hinweis_antworten(gedanken, grund)}]
        except BaseException as e:  # auch Abbruch durch den Client (GeneratorExit/CancelledError)
            status = "abbruch"
            _log.info("v1: Strom beendet ohne Abschluss: %s", type(e).__name__)
            raise
        finally:
            _schutz.fertig(nutzer["id"])
            _nutzung(nutzer["id"], schluessel_id, modell, usage, start, status)
            u = usage or {}
            _log.info("v1: %s %s Slot %s — rein %s (Cache %s), raus %s, %.1f s", nutzer.get("username"), modell, slot,
                      u.get("prompt_tokens"), (u.get("prompt_tokens_details") or {}).get("cached_tokens"),
                      u.get("completion_tokens"), time.monotonic() - start)

    return StreamingResponse(strom(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

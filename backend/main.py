import asyncio
import base64
import io
import json
import logging
import os
import secrets
import subprocess
import sys
import tempfile
import textwrap
from fastapi import FastAPI, Request, HTTPException, Depends, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from pathlib import Path

from . import config
from . import auth
from . import database as db
from .chat import stream_chat
from .agent import run_agent
from .learning import mark_active, mark_idle, extract_learnings

logger = logging.getLogger(__name__)

app = FastAPI(title="Xera AI")
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SECRET_KEY,
    max_age=30 * 24 * 60 * 60,
    same_site="lax",
    https_only=config.DISCORD_REDIRECT_URI.startswith("https"),
)

# Xera-CLI = OpenCode über /v1 (seit 2026-10-17, openai_api.py)
from .openai_api import router as _openai_router
app.include_router(_openai_router)

# Kill-Switch: per-request stop events, keyed by request_id (UUID)
_stop_events: dict[str, asyncio.Event] = {}
_denk_ende_events: dict[str, asyncio.Event] = {}


# ── Rate limiter (in-memory, per IP) ──────────────────────────────────────────
import time
from collections import defaultdict

_rate_store: dict[str, list[float]] = defaultdict(list)

def _rate_limit(request: Request, max_calls: int, window_seconds: int) -> None:
    """Raise HTTP 429 if IP exceeded max_calls within window_seconds."""
    ip  = request.client.host if request.client else "unknown"
    now = time.time()
    calls = [t for t in _rate_store[ip] if now - t < window_seconds]
    calls.append(now)
    _rate_store[ip] = calls
    if len(calls) > max_calls:
        raise HTTPException(429, "Too many requests. Please wait.")


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if p.get("type") == "text")
    return str(content)

# --- Neue Oberflaeche unter /app -------------------------------------------
#
# Sie laeuft neben der alten, bis sie sie ersetzt. Zwei Oberflaechen auf
# einmal umzustellen und dabei das Backend zu aendern waere die Sorte
# Umstellung, bei der hinterher niemand weiss, was den Fehler verursacht hat.
#
# html=False, weil StaticFiles sonst bei jedem unbekannten Pfad 404 liefert.
# Die Oberflaeche verwaltet ihre Adressen selbst (/app/chat, /app/cowork, …),
# also muss jeder Pfad darunter die Startdatei bekommen.
APP_DIR = config.BASE_DIR / "app"
if APP_DIR.is_dir():
    app.mount("/app/mittel", StaticFiles(directory=str(APP_DIR / "mittel")), name="app-mittel")

    @app.get("/app", response_class=HTMLResponse)
    @app.get("/app/{pfad:path}", response_class=HTMLResponse)
    async def neue_oberflaeche(request: Request, pfad: str = ""):
        datei = APP_DIR / pfad
        # Einzelne Dateien neben der Startseite (Zeichen, Vorschaubilder).
        if pfad and datei.is_file() and APP_DIR in datei.resolve().parents:
            return FileResponse(str(datei))
        return Response(
            content=(APP_DIR / "index.html").read_text(encoding="utf-8"),
            media_type="text/html",
            headers={"Cache-Control": "no-store"},
        )



def _code_motor_an() -> bool:
    """Schalter für den OpenCode-Motor im Code-Bereich: Datei vorhanden = an.
    Ohne Neustart umschaltbar; fehlt die Datei, läuft der bisherige Weg (vermittler)."""
    from pathlib import Path as _P
    return _P("/opt/xera-ai/motor/code-bereich-an").exists()


# Alte Xera-CLI (xera-code, `ssh cli@`) seit 2026-10-17 abgeschaltet — die CLI ist
# jetzt OpenCode über /v1 (docs/plan-cli-opencode-2026-10.md). Die alten Wege
# antworten mit 410 und sagen das, statt still „nicht angemeldet“ zu melden.
ALTE_CLI_AUS = ("Die alte Xera-CLI ist abgeschaltet. Die neue CLI ist OpenCode — "
                "die Einrichtung steht bald in den Einstellungen von xera-app.com.")


def _alte_cli_aus():
    raise HTTPException(410, ALTE_CLI_AUS)


def get_current_user(request: Request) -> dict | None:
    # Bearer-Token schickte nur die alte CLI.
    if request.headers.get("Authorization", "").startswith("Bearer "):
        _alte_cli_aus()
    # Cookie session (Web)
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get_user(user_id)


async def aktueller_nutzer(request: Request) -> dict | None:
    """Wie get_current_user, aber mit frisch geprüften Discord-Rollen (rollen.py) — für
    alles, was an Pro, Admin oder Homelab hängt."""
    from .rollen import rollen_auffrischen
    return await rollen_auffrischen(get_current_user(request))


@app.on_event("startup")
async def startup():
    db.init_db()
    from .docgen import cleanup_old_docs
    cleanup_old_docs()
    db.audit_aufraeumen(30)
    # Sandkasten-Kennungen aller bestehenden Konten zuerst festschreiben — sonst könnte ein neues
    # Konto, dessen Hash zufällig gleich ist, die Kennung samt altem Ordner bekommen (arbeitsbereich.uid_fuer).
    from .arbeitsbereich import uid_fuer
    for konto in db.alle_user_ids():
        uid_fuer(konto)
    asyncio.create_task(_cleanup_loop())
    # Slots von llama-server vorwärmen (Systemprompts je Bereich), siehe vermittler.py
    from .vermittler import aufwaerm_schleife
    asyncio.create_task(aufwaerm_schleife())
    # OpenCode-Motoren des Code-Bereichs: Reste eines früheren Prozesses beenden,
    # danach je Motor nach 15 min Ruhe (code_motor.py)
    from .code_motor import aufraeumen_alt, ruhe_schleife
    aufraeumen_alt()
    asyncio.create_task(ruhe_schleife())


async def _cleanup_loop():
    while True:
        await asyncio.sleep(3600)  # every hour
        from .docgen import cleanup_old_docs
        cleanup_old_docs()
        # Werkzeugprotokoll höchstens 30 Tage (seit 2026-10-19, Datenschutz 6)
        db.audit_aufraeumen(30)


# Die alte Oberfläche (static/, mit Gastmodus) ist seit 2026-10-19 abgeschaltet — ihre
# Adressen führen in die neue unter /app. Lesezeichen auf alte Gespräche (/c/…) landen dort
# auch; die Gespräche selbst stehen in der neuen Oberfläche in der Liste.
@app.get("/")
@app.get("/c")
@app.get("/c/{session_id:int}")
@app.get("/fully-local")
@app.get("/private-secure")
@app.get("/lightning-fast")
@app.get("/smart-agents")
async def alte_oberflaeche():
    return RedirectResponse("/app", status_code=302)


@app.get("/login")
async def login_page():
    return RedirectResponse("/auth/login?next=/app", status_code=302)


def _sicheres_ziel(ziel: str | None) -> str | None:
    """Nur Pfade auf dieser Seite. "//evil.com" oder "https://…" wuerden sonst
    nach dem Login auf eine fremde Seite fuehren (offene Weiterleitung)."""
    if not ziel or not ziel.startswith("/") or ziel.startswith("//") or "\\" in ziel:
        return None
    return ziel


@app.get("/auth/login")
async def login(request: Request, next: str | None = None):
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    # Wohin es nach dem Login geht. Die neue Oberflaeche schickt next=/app,
    # sonst landete man nach dem Login immer in der alten unter "/".
    ziel = _sicheres_ziel(next)
    if ziel:
        request.session["login_next"] = ziel
    else:
        request.session.pop("login_next", None)
    return RedirectResponse(auth.get_oauth_url(state))


@app.get("/auth/callback")
async def callback(request: Request, code: str = "", state: str = ""):
    stored_state = request.session.get("oauth_state")
    if not stored_state or stored_state != state:
        raise HTTPException(400, "Invalid state")

    token_data = await auth.exchange_code(code)
    access_token = token_data["access_token"]

    discord_user = await auth.get_discord_user(access_token)
    try:
        rollen = await auth.check_roles(access_token)
    except auth.DiscordFehler as fehler:
        # Rollen gerade nicht lesbar: die gespeicherten bleiben (database.get_or_create_user),
        # rollen.py prüft spätestens nach 15 min wieder nach.
        logger.warning("Rollen beim Login nicht lesbar: %s", fehler)
        rollen = None

    user = db.get_or_create_user(discord_user, rollen)

    request.session["user_id"] = user["id"]
    # Das Discord-Token braucht Xera nach dem Login nicht mehr (Rollen prüft der Bot, rollen.py).
    # Bis 2026-10-19 lag es im Cookie — lesbar für jeden, der das Cookie hat.
    request.session.pop("access_token", None)

    # After CLI auth login, redirect back to /cli-auth page
    next_url = request.session.pop("cli_auth_next", None)
    login_next = _sicheres_ziel(request.session.pop("login_next", None))
    return RedirectResponse(next_url or login_next or "/")


@app.get("/auth/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")


# --- Alte CLI-Anmeldung (bis 2026-10-17) ---
# Die alte Xera-CLI meldete sich über diese Adressen an. Sie antworten nur noch mit 410,
# damit eine alte Installation einen verständlichen Hinweis bekommt statt 404.

@app.post("/api/cli-auth/init")
@app.get("/api/cli-auth/poll")
async def cli_auth_alt():
    _alte_cli_aus()


@app.get("/cli-auth", response_class=HTMLResponse)
async def cli_auth_page():
    return HTMLResponse(f"<h2>{ALTE_CLI_AUS}</h2>", status_code=410)


# --- Schlüssel für die Xera-CLI (OpenCode, seit 2026-10-17) ---

@app.get("/cli/{name}")
async def cli_datei(name: str):
    """OpenCode-Konfiguration (opencode.jsonc) und die gemeinsamen Xera-Regeln
    (regeln.md, seit 2026-10-19). Ohne Schlüssel, darum ohne Anmeldung abrufbar."""
    if name not in ("opencode.jsonc", "regeln.md"):
        raise HTTPException(404)
    datei = config.BASE_DIR / "cli" / name
    if not datei.is_file():
        raise HTTPException(404)
    return Response(datei.read_text(encoding="utf-8"), media_type="text/plain; charset=utf-8")


@app.get("/api/cli/schluessel")
async def cli_schluessel_liste(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401)
    from .openai_api import schluessel_liste
    return schluessel_liste(user["id"])


@app.post("/api/cli/schluessel")
async def cli_schluessel_neu(request: Request):
    """Neuer Schlüssel — der Klartext steht nur in dieser Antwort."""
    _rate_limit(request, max_calls=10, window_seconds=60)
    user = await aktueller_nutzer(request)
    if not user:
        raise HTTPException(401)
    if not (user["is_pro"] or user["is_admin"]):
        raise HTTPException(403, "Die Xera-CLI ist für Pro-Nutzer.")
    from .openai_api import schluessel_erzeugen, schluessel_liste
    if len(schluessel_liste(user["id"])) >= 10:
        raise HTTPException(400, "Höchstens 10 Schlüssel — widerrufe zuerst einen alten.")
    try:
        body = await request.json()
    except ValueError:
        body = {}
    name = str(body.get("name") or "OpenCode") if isinstance(body, dict) else "OpenCode"
    if name.lower().startswith("intern:"):   # gehört dem Code-Motor: unsichtbar, ausserhalb des Limits
        name = "OpenCode"
    return schluessel_erzeugen(user["id"], name)


@app.delete("/api/cli/schluessel/{schluessel_id}")
async def cli_schluessel_widerrufen(request: Request, schluessel_id: int):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401)
    from .openai_api import schluessel_widerrufen
    if not schluessel_widerrufen(user["id"], schluessel_id):
        raise HTTPException(404, "Schlüssel nicht gefunden")
    return {"ok": True}


@app.get("/api/me")
async def me(request: Request):
    user = await aktueller_nutzer(request)
    if user:
        unbegrenzt = bool(user["is_pro"] or user["is_admin"])
        return {
            "id": user["id"],
            "username": user["username"],
            "avatar": user["avatar"],
            "is_admin": bool(user["is_admin"]),
            "is_pro": bool(user["is_pro"]),
            "has_homelab": bool(user.get("has_homelab")),
            "prompt_count": user["prompt_count"],
            # Gratis: Fragen übrig für heute (Grenze je Tag seit 2026-10-19)
            "prompts_remaining": -1 if unbegrenzt else max(0, config.FREE_PROMPT_LIMIT - db.fragen_heute(user)),
            "limit": config.FREE_PROMPT_LIMIT,
            "is_guest": False,
        }
    # Nicht angemeldet: nur die öffentlichen Seiten. Kein Gastzähler mehr, also auch
    # kein Prüfwert aus IP und Browserkennung (bis 2026-10-19).
    return {
        "id": "",
        "username": "Gast",
        "avatar": None,
        "is_admin": False,
        "is_pro": False,
        "prompt_count": 0,
        "prompts_remaining": 0,
        "limit": 0,
        "is_guest": True,
    }


async def _darf_homelab(user: dict | None) -> bool:
    """Ob dieser Nutzer den Homelab-Modus benutzen darf: Xera Admin oder Rolle Xera Homelab.
    ``user`` kommt aus aktueller_nutzer — die Rollen sind höchstens 15 min alt (rollen.py).
    Bis 2026-10-19 prüfte nur diese Stelle nach, mit dem Discord-Token des Nutzers."""
    return bool(user and (user.get("is_admin") or user.get("has_homelab")))


def _antwort_speichern(session_id: int, text: str, extras: dict | None, abgebrochen: bool) -> None:
    """Antwort speichern — aber keine leere. Chat 512: Stopp vor dem ersten
    Wort speicherte "" als Antwort, nach dem Neuladen stand eine leere Blase
    da, und das Modell bekam beim nächsten Mal eine leere Antwort im Verlauf."""
    if text.strip():
        db.save_message(session_id, "assistant", text, extras=extras)
    elif extras:
        # Agent-Karten oder Werkzeuge liefen schon — die sollen bleiben.
        db.save_message(session_id, "assistant", "_(Antwort abgebrochen)_" if abgebrochen else "_(keine Antwort)_", extras=extras)


@app.post("/api/chat")
async def chat_endpoint(request: Request):
    # Nur angemeldet (seit 2026-10-19). Der Gastmodus der alten Oberfläche zählte je IP und
    # Browserkennung — eine neue Kennung gab neue Freifragen, also anonymen Dauerzugang.
    user = await aktueller_nutzer(request)
    if user is None:
        return JSONResponse(status_code=401, content={
            "error": "login_required",
            "detail": "Bitte melde dich an, um Xera zu fragen.",
        })
    if not user["is_pro"] and not user["is_admin"] and db.fragen_heute(user) >= config.FREE_PROMPT_LIMIT:
        return JSONResponse(status_code=403, content={
            "error": "limit_reached",
            "detail": f"Deine {config.FREE_PROMPT_LIMIT} Gratis-Fragen für heute sind aufgebraucht. "
                      "Morgen geht es weiter — mit Xera Pro ohne Grenze.",
        })

    body = await request.json()
    messages = body.get("messages", [])
    session_id = body.get("session_id")
    mode = body.get("mode", "chat")
    agent_id = body.get("agent_id")  # optional: lock to specific agent
    projekt_id = body.get("projekt_id")
    platform = body.get("platform", "web")

    # --- Wem gehoert diese Unterhaltung? (#23) -----------------------------
    # Alle uebrigen Session-Endpunkte pruefen das; der Schreibweg tat es nicht.
    # Damit liessen sich Nachrichten in fremde Verlaeufe schreiben, samt der
    # Antwort des Modells.
    if session_id is not None:
        vorhandene = db.get_session(session_id)
        if not vorhandene or str(vorhandene["user_id"]) != str(user["id"]):
            raise HTTPException(403, "Diese Unterhaltung gehoert dir nicht")

    # --- Darf dieser Nutzer den Homelab-Modus? (#21) -----------------------
    # has_homelab wurde beim Login gespeichert und danach nur ans Frontend
    # gemeldet — nie geprueft. Wer {"mode":"homelab"} schickte, bekam die
    # Homelab-Werkzeuge, ssh_execute eingeschlossen.
    if mode == "homelab" and not await _darf_homelab(user):
        raise HTTPException(403, "Homelab-Modus erfordert die Homelab-Rolle")

    # --- Platz im Arbeitsbereich (seit 2026-10-19) ----------------------------
    # Werkzeuge schreiben Dateien in den Sandkasten; voll heisst: keine neue Antwort,
    # bevor die Platte von CT 203 (und mit ihr die Datenbank) vollläuft.
    if mode != "homelab" and not user["is_admin"]:
        from .arbeitsbereich import platz_pruefen
        grund = await asyncio.to_thread(platz_pruefen, user["id"])
        if grund:
            return JSONResponse(status_code=507, content={"error": "platz", "detail": grund})

    # --- Gehoert dieses Vorhaben dem Nutzer? (Cowork) ----------------------
    # Ohne die Pruefung liesse sich fremdes Projektwissen ins eigene Gespraech
    # ziehen: die Anweisung und alle Notizen werden dem Modell vorangestellt.
    projektwissen = ""
    if projekt_id is not None:
        if not db.projekt_holen(projekt_id, user["id"]):
            raise HTTPException(404, "Vorhaben nicht gefunden")
        projektwissen = db.projektwissen(projekt_id)


    # Das Modell entscheidet selbst, ob es einen Agent braucht (backend/vermittler.py).
    # Seit 2026-10-19 für jede Anfrage: Die alte Oberfläche mit Stichwort-Orchestrator
    # ist weg, ihre 34 Agents ebenso — ohne „routing“ wären sie sonst noch erreichbar.
    routing_modell = True

    # "Gruendlich denken" aus der neuen Oberflaeche: immer der direkte
    # Chat-Weg, nicht die Agenten — dort laufen Werkzeugrunden, und Denken
    # vor jeder Runde wuerde aus Sekunden Minuten machen.
    # Denkaufwand (seit 2026-10-19, aufwand.py): „aufwand“ = Stufe; das alte
    # „denken: true“ gilt als „mittel“.
    from . import aufwand as _aufwand
    aufwand_stufe = _aufwand.stufe(body.get("aufwand") or body.get("denken"))
    denken = aufwand_stufe != "aus" and (routing_modell or mode != "homelab")
    if not denken:
        aufwand_stufe = "aus"
    _aufwand.AKTUELL.set(aufwand_stufe)
    # Alter Weg (alte Oberflaeche): Denken nur ohne Agenten. Neuer Weg: auch
    # Agents denken mit — der Vermittler bzw. run_agent reicht es durch.
    if denken and not routing_modell and not agent_id:
        mode = "chat"

    if not messages:
        raise HTTPException(400, "No messages")



    def _collect_content(chunk: str, mode: str) -> str:
        if not chunk.startswith("data: "):
            return ""
        payload = chunk.split("data: ", 1)[1].strip()
        if payload == "[DONE]":
            return ""
        try:
            data = json.loads(payload)
            c = data.get("content", "")
            if c and (mode == "chat" or data.get("type") == "content"):
                return c
        except (json.JSONDecodeError, KeyError):
            pass
        return ""

    import secrets as _secrets
    req_id = _secrets.token_hex(16)
    stop_ev = asyncio.Event()
    _stop_events[req_id] = stop_ev
    # „Jetzt antworten“: beendet nur das Nachdenken, nicht die Antwort (seit 2026-10-19).
    denk_ende_ev = asyncio.Event()
    _denk_ende_events[req_id] = denk_ende_ev

    # Werkzeuge im Web laufen im Sandkasten (arbeitsbereich.py, seit
    # 2026-10-16) — ausser im Homelab-Bereich und in der CLI.
    from .tools import SANDBOX as _SANDBOX

    if not session_id:
        # CLI → Code tab; web agents → Chat tab; homelab stays homelab
        if mode == "agents":
            session_mode = "code" if platform == "cli" else "chat"
        else:
            session_mode = mode
        # Die neue Oberflaeche sagt selbst, in welchem Bereich das Gespraech
        # stehen soll. Ohne das landete alles aus dem Code-Bereich im Chat,
        # weil "agents" fuer das Web immer zu "chat" wurde. Fehlt das Feld
        # (alte Oberflaeche, CLI), bleibt alles wie bisher.
        ablage = body.get("ablage")
        if ablage in ("chat", "code", "homelab", "cowork"):
            if ablage == "homelab" and mode != "homelab":
                ablage = "chat"
            session_mode = ablage
        session_id = db.create_session(user["id"], mode=session_mode)
        if projekt_id is not None:
            db.sitzung_an_projekt(session_id, projekt_id)
        first_msg = _extract_text(messages[-1].get("content", ""))[:50]
        db.update_session_title(session_id, first_msg or "Neuer Chat")

    db.save_message(session_id, "user", _extract_text(messages[-1]["content"]))
    db.increment_prompt_count(user["id"])
    mark_active(user["id"])
    if platform != "cli" and mode != "homelab":
        _SANDBOX.set({"user_id": str(user["id"]), "session_id": session_id, "admin": bool(user.get("is_admin"))})

    # Die Antwort laeuft als eigener Task (laeufe.py) und wird am Ende immer
    # gespeichert — auch wenn das Fenster zu ist oder das Netz kurz weg war.
    # Die Verbindung liest nur mit; GET /api/sessions/{id}/strom haengt sich
    # wieder an.
    async def erzeugen(lauf):
        full_response = []
        # Agent-Karten, Werkzeuge, Denkweg mitschreiben — sonst sind sie nach
        # dem Neuladen weg (siehe karten.py).
        from .karten import KartenSammler
        karten = KartenSammler()
        gespeichert = False
        try:
            lauf.anhaengen(f"data: {json.dumps({'session_id': session_id, 'request_id': req_id})}\n\n")
            sammel_modus = mode
            vorgabe = bool(agent_id) and routing_modell and str(agent_id).startswith("neu_") and body.get("ablage") != "chat"
            if agent_id and not vorgabe:
                # Ausdruecklich gewaehlter Agent (Uebersicht, @, Websuche) —
                # im Denkmodus denkt er mit.
                source = run_agent(messages, mode="homelab" if mode == "homelab" else "agents", user_id=user["id"], session_id=session_id, agent_id=agent_id, stop_event=stop_ev, projektwissen=projektwissen, brain_override="denken" if denken else None)
                sammel_modus = "agents"
            elif routing_modell and body.get("ablage") == "code" and _code_motor_an():
                # Code-Bereich = derselbe Motor wie die CLI: OpenCode auf dem
                # Server (seit 2026-10-19, code_motor.py). Xera-Agents gibt es
                # hier nicht mehr — OpenCode hat eigene Unteragenten.
                from .code_motor import antworten as _motor
                source = _motor(messages, user_id=user["id"], session_id=session_id, aufwand_stufe=aufwand_stufe, stop_event=stop_ev, denk_ende=denk_ende_ev)
                sammel_modus = "chat"
            elif routing_modell:
                from .vermittler import antworten as _vermittler
                source = _vermittler(messages, user_id=user["id"], session_id=session_id, projektwissen=projektwissen, denken=denken, mit_homelab=(mode == "homelab"), websuche=bool(body.get("websuche")), mit_agents=(body.get("ablage") != "chat"), vorgabe_agent=(agent_id if vorgabe else None), stop_event=stop_ev, projekt_id=(projekt_id if projektwissen else None), aufwand_stufe=aufwand_stufe, denk_ende=denk_ende_ev)
                sammel_modus = "chat"
            elif mode in ("agents", "homelab"):
                source = run_agent(messages, mode=mode, user_id=user["id"], session_id=session_id, agent_id=agent_id, stop_event=stop_ev, projektwissen=projektwissen)
            else:
                source = stream_chat(messages, user_id=user["id"], projektwissen=projektwissen, denken=denken)
            async for chunk in source:
                if chunk.startswith('data: {"type": "ersetzen"'):
                    # Korrigierter Code (codepruefung.py): ganze Antwort neu.
                    try:
                        full_response[:] = [json.loads(chunk[6:])["content"]]
                    except (json.JSONDecodeError, KeyError):
                        pass
                else:
                    part = _collect_content(chunk, sammel_modus)
                    if part:
                        full_response.append(part)
                karten.lesen(chunk)
                lauf.anhaengen(chunk)
            _antwort_speichern(session_id, "".join(full_response), karten.ergebnis(), stop_ev.is_set())
            # Sofort als fertig melden, ohne await dazwischen: wer jetzt
            # /strom fragt, bekommt 204 und liest die Antwort aus der DB.
            lauf.beenden()
            gespeichert = True
            all_msgs = messages + [{"role": "assistant", "content": "".join(full_response)}]
            asyncio.create_task(extract_learnings(user["id"], session_id, all_msgs))
        finally:
            # Abgebrochen (Fehler, Neustart): das Bisherige behalten statt nichts.
            if not gespeichert:
                try:
                    _antwort_speichern(session_id, "".join(full_response), karten.ergebnis(), True)
                except Exception:
                    pass
            mark_idle(user["id"])
            _stop_events.pop(req_id, None)
            _denk_ende_events.pop(req_id, None)

    from . import laeufe
    lauf = laeufe.starten(session_id, user["id"], req_id, erzeugen)
    return StreamingResponse(lauf.lesen(mit_ende=(platform == "web")), media_type="text/event-stream")


@app.get("/api/sessions/{session_id}/strom")
async def sitzung_strom(request: Request, session_id: int):
    """Wieder an eine laufende Antwort anhaengen (Neuladen, Netz weg).

    Liefert alles Bisherige und dann live den Rest; 204, wenn nichts laeuft —
    dann steht die Antwort schon in der Datenbank."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "Nicht angemeldet")
    from . import laeufe
    lauf = laeufe.laufend(session_id)
    if not lauf or lauf.user_id != str(user["id"]):
        return Response(status_code=204)
    return StreamingResponse(lauf.lesen(mit_ende=True), media_type="text/event-stream")


# Wer waehrend des Wartungsmodus trotzdem hinein darf: Discord-IDs, mit Komma
# getrennt, aus .env (seit 2026-10-19 kein Standardwert mehr im Quelltext). Caddy
# fragt diesen Endpunkt vor jeder Anfrage (forward-auth); 204 = durchlassen, sonst
# zeigt Caddy die Wartungsseite.
_WARTUNG_ZUGANG = {
    x.strip() for x in os.getenv("WARTUNG_ZUGANG", "").split(",") if x.strip()
}


@app.get("/api/wartung/darf")
async def wartung_darf(request: Request):
    user = get_current_user(request)
    if user and str(user["id"]) in _WARTUNG_ZUGANG:
        return Response(status_code=204)
    return Response(status_code=403)


_modellstatus_cache: dict = {"zeit": 0.0, "wert": None}


def _kontext_fenster() -> int:
    from . import kontext
    return kontext.FENSTER


@app.get("/api/modellstatus")
async def modellstatus():
    """Fuer die Anzeige unten links in der neuen Oberflaeche.

    Seit Oktober 2026 hat der Server nur einen Slot (1x64k): Wer fragt,
    waehrend jemand anderes eine Antwort bekommt, wartet. Das soll man sehen,
    statt zu raetseln, warum nichts kommt. Drei Sekunden zwischengespeichert,
    damit zehn offene Tabs den Server nicht mit Metrik-Abfragen beschaeftigen.
    """
    import httpx

    jetzt = time.monotonic()
    if _modellstatus_cache["wert"] is not None and jetzt - _modellstatus_cache["zeit"] < 3:
        return _modellstatus_cache["wert"]
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(2.0)) as client:
            r = await client.get(f"{config.LLAMA_API_URL}/metrics")
            r.raise_for_status()
        werte = {}
        for zeile in r.text.splitlines():
            if zeile.startswith("llamacpp:") and "{" not in zeile:
                name, _, zahl = zeile.partition(" ")
                try:
                    werte[name[len("llamacpp:"):]] = float(zahl)
                except ValueError:
                    pass
        # Fenster der letzten ~10 Minuten: Differenz zum ältesten Messpunkt.
        stand = (jetzt, werte.get("tokens_predicted_total", 0), werte.get("tokens_predicted_seconds_total", 0),
                 werte.get("prompt_tokens_total", 0), werte.get("prompt_seconds_total", 0))
        verlauf = _modellstatus_cache.setdefault("verlauf", [])
        verlauf.append(stand)
        while len(verlauf) > 2 and jetzt - verlauf[1][0] > 600:
            verlauf.pop(0)
        alt = verlauf[0]
        geschrieben, schreibzeit = stand[1] - alt[1], stand[2] - alt[2]
        gelesen, lesezeit = stand[3] - alt[3], stand[4] - alt[4]
        if schreibzeit < 3:  # in den letzten 10 Minuten kaum etwas — letzten Wert behalten
            geschrieben, schreibzeit = _modellstatus_cache.get("letzt_schreiben", (stand[1], stand[2]))
        else:
            _modellstatus_cache["letzt_schreiben"] = (geschrieben, schreibzeit)
        if lesezeit < 1 or gelesen < 200:
            gelesen, lesezeit = _modellstatus_cache.get("letzt_lesen", (stand[3], stand[4]))
        else:
            _modellstatus_cache["letzt_lesen"] = (gelesen, lesezeit)
        wert = {
            "erreichbar": True,
            "beschaeftigt": int(werte.get("requests_processing", 0)),
            "wartend": int(werte.get("requests_deferred", 0)),
            "schreiben_ts": round(geschrieben / schreibzeit, 1) if schreibzeit > 0 else None,
            "lesen_ts": round(gelesen / lesezeit) if lesezeit > 0 and gelesen > 0 else None,
            "fenster": _kontext_fenster(),
        }
    except Exception:
        wert = {"erreichbar": False, "beschaeftigt": 0, "wartend": 0, "schreiben_ts": None, "lesen_ts": None,
                "fenster": _kontext_fenster()}
    _modellstatus_cache.update(zeit=jetzt, wert=wert)
    return wert


@app.get("/api/sessions")
async def list_sessions(request: Request, mode: str | None = None):
    user = get_current_user(request)
    if not user:
        return []
    return db.get_sessions(user["id"], mode=mode)


@app.get("/api/sessions/{session_id}/messages")
async def get_session_messages(request: Request, session_id: int):
    user = get_current_user(request)
    if not user:
        return []
    session = db.get_session(session_id)
    if not session or session["user_id"] != str(user["id"]):
        raise HTTPException(403)
    return db.get_messages_anzeige(session_id)


@app.post("/api/sessions/{session_id}/kuerzen")
async def sitzung_kuerzen(request: Request, session_id: int):
    """Behaelt die ersten `behalten` Nachrichten, loescht den Rest.

    Die neue Oberflaeche braucht das fuer "Antwort neu erzeugen" und "Frage
    bearbeiten": Ohne Kuerzen blieben die verworfene Frage und Antwort in der
    Datenbank stehen und tauchten beim naechsten Laden doppelt auf.
    """
    user = get_current_user(request)
    if not user:
        raise HTTPException(401)
    session = db.get_session(session_id)
    if not session or session["user_id"] != str(user["id"]):
        raise HTTPException(403)
    body = await request.json()
    behalten = body.get("behalten")
    if not isinstance(behalten, int) or behalten < 0:
        raise HTTPException(400, "behalten muss eine Zahl >= 0 sein")
    conn = db.get_db()
    ids = [r[0] for r in conn.execute(
        "SELECT id FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,)
    ).fetchall()]
    weg = ids[behalten:]
    if weg:
        conn.executemany("DELETE FROM messages WHERE id = ?", [(i,) for i in weg])
        conn.commit()
    conn.close()
    return {"ok": True, "geloescht": len(weg)}


async def _kontext_eingang(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401)
    body = await request.json()
    sitzung_id = body.get("sitzung_id")
    nachrichten = body.get("nachrichten")
    if not isinstance(sitzung_id, int) or not isinstance(nachrichten, list) or len(nachrichten) < 2:
        raise HTTPException(400, "sitzung_id und nachrichten nötig")
    session = db.get_session(sitzung_id)
    if not session or session["user_id"] != str(user["id"]):
        raise HTTPException(403)
    nachrichten = [
        {"role": m.get("role"), "content": m.get("content")}
        for m in nachrichten
        if isinstance(m, dict) and m.get("role") in ("user", "assistant")
    ]
    return user, session, nachrichten


@app.post("/api/kontext/verdichten")
async def kontext_verdichten(request: Request):
    """Fasst das Gespräch jetzt zusammen (Knopf "Zusammenfassen und weiter")."""
    from . import kontext
    _user, session, nachrichten = await _kontext_eingang(request)
    # Code-Bereich mit OpenCode-Motor: der Kontext liegt in OpenCode — dort zusammenfassen.
    from . import code_motor
    if _code_motor_an() and code_motor.hat_sitzung(session["id"]):
        groesse = await code_motor.verdichten(str(_user["id"]), session["id"])
        if groesse is None:
            raise HTTPException(502, "Der Code-Motor konnte nicht zusammenfassen.")
        return kontext.ereignis(groesse, verdichtet=True)
    verlauf, verdichtet = await kontext.verdichten(nachrichten, session["id"], erzwingen=True)
    if not verdichtet:
        raise HTTPException(409, "Zu wenig Verlauf zum Zusammenfassen.")
    return kontext.ereignis(kontext.schaetzen(verlauf), verdichtet=True)


@app.post("/api/kontext/uebergabe")
async def kontext_uebergabe(request: Request):
    """Neues Gespräch, das mit einer Zusammenfassung des alten beginnt."""
    from . import kontext
    user, session, nachrichten = await _kontext_eingang(request)
    verlauf, verdichtet = kontext.anwenden(nachrichten, session["id"])
    try:
        if verdichtet:
            # Gespeicherte Zusammenfassung + was seither kam, zusammen neu fassen.
            text = await kontext.zusammenfassen(verlauf[2:], kontext.zusammenfassung_von(session["id"]) or "")
        else:
            text = await kontext.zusammenfassen(nachrichten)
    except Exception as e:
        raise HTTPException(502, f"Zusammenfassung fehlgeschlagen: {e}")
    if not text:
        raise HTTPException(502, "Zusammenfassung leer")
    titel_alt = session.get("title") or "Gespräch"
    neu_id = db.create_session(user["id"], f"{titel_alt} (Fortsetzung)"[:120], session.get("mode") or "chat")
    if session.get("projekt_id"):
        db.sitzung_an_projekt(neu_id, session["projekt_id"])
    db.save_message(neu_id, "user", f"[Übergabe aus „{titel_alt}“]\n\n{text}")
    db.save_message(neu_id, "assistant", "Ich habe den Stand aus dem vorigen Gespräch übernommen. Woran machen wir weiter?")
    return {"sitzung_id": neu_id, "titel": f"{titel_alt} (Fortsetzung)"[:120]}


@app.patch("/api/sessions/{session_id}")
async def update_session(request: Request, session_id: int):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401)
    session = db.get_session(session_id)
    if not session or session["user_id"] != str(user["id"]):
        raise HTTPException(403)
    body = await request.json()
    title = body.get("title")
    folder = body.get("folder")
    if title is not None:
        title = title.strip()
        if not title:
            raise HTTPException(400, "Title required")
        db.update_session_title(session_id, title[:100])
    if folder is not None:
        db.update_session_folder(session_id, folder if folder else None)
    return {"ok": True}


@app.get("/api/folders")
async def list_folders(request: Request, mode: str | None = None):
    user = get_current_user(request)
    if not user:
        return []
    return db.get_folders(user["id"], mode=mode)


@app.delete("/api/sessions/{session_id}")
async def delete_session(request: Request, session_id: int, hintergrund: BackgroundTasks):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401)
    session = db.get_session(session_id)
    if not session or session["user_id"] != str(user["id"]):
        raise HTTPException(403)
    db.delete_session(session_id)
    # Code-Bereich: OpenCodes Kopie des Gesprächs mitlöschen — nach der Antwort,
    # der Motor muss dafür womöglich erst starten (code_motor.py)
    from . import code_motor
    if code_motor.hat_sitzung(session_id):
        hintergrund.add_task(code_motor.sitzung_loeschen, str(user["id"]))
    # Arbeitsordner gleich mit (seit 2026-10-19) — vorher erst nach 7 Tagen; so ist der
    # Platz sofort frei (arbeitsbereich.PLATZ_JE_NUTZER) und nichts bleibt liegen.
    from .arbeitsbereich import ordner_loeschen
    hintergrund.add_task(ordner_loeschen, str(user["id"]), session_id)
    return {"ok": True}


@app.post("/api/rag/ingest")
async def rag_ingest(request: Request):
    user = await aktueller_nutzer(request)
    if not user or not user["is_admin"]:
        raise HTTPException(403, "Admin only")
    from .rag import ingest
    result = await ingest()
    return result


@app.get("/api/rag/status")
async def rag_status():
    from .rag import get_status
    return get_status()


def _hat_sitzung(request: Request) -> bool:
    """Angemeldet. Bis 2026-10-01 ging Upload/Download ganz ohne — jedes Skript konnte
    Dateien ablegen, überschreiben und holen; bis 2026-10-19 reichte eine Gastsitzung."""
    return get_current_user(request) is not None


@app.post("/api/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    from .docparse import parse_document
    from .docgen import DOCS_DIR
    if not _hat_sitzung(request):
        raise HTTPException(401, "Nicht angemeldet")
    data = await file.read()
    # Save raw file so read_document tool can find it later
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    # Zufaelliges Praefix: zwei Leute mit "bericht.pdf" ueberschreiben sich
    # sonst gegenseitig die Datei.
    safe_name = secrets.token_hex(4) + "_" + (file.filename or "upload").replace("/", "_").replace("..", "_")
    dest = DOCS_DIR / safe_name
    dest.write_bytes(data)
    result = parse_document(file.filename or "file", data)
    result["stored_name"] = safe_name
    return result


@app.get("/api/download/{filename}")
async def download_file(request: Request, filename: str):
    from .docgen import DOCS_DIR
    if not _hat_sitzung(request):
        raise HTTPException(401, "Nicht angemeldet")
    path = (DOCS_DIR / filename).resolve()
    if path.parent != DOCS_DIR.resolve():
        raise HTTPException(400, "Invalid filename")
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "File not found")
    import mimetypes
    import re as _re
    from urllib.parse import quote as _quote
    media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    # Ohne das Zufallspräfix speichern ("8e596661_spiel.html" → "spiel.html", seit 2026-10-17).
    anzeige = _re.sub(r"^[0-9a-f]{8,32}_", "", filename) or filename
    return FileResponse(
        str(path),
        filename=anzeige,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename=\"{anzeige.encode('ascii', 'replace').decode()}\"; "
                                        f"filename*=UTF-8''{_quote(anzeige)}"},
    )


@app.post("/api/python")
async def run_python(request: Request):
    """Execute Python code in a restricted subprocess with 10s timeout.
    Returns image (matplotlib), text output, or error.
    """
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentifizierung erforderlich")
    body = await request.json()
    code = body.get("code", "")
    if not code.strip():
        return JSONResponse({"type": "error", "message": "Kein Code angegeben."})

    # Write user code and runner to temp files
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir="/tmp") as tf:
        user_code_file = tf.name

    try:
        user_code_path = user_code_file + "_user.py"
        runner_path = user_code_file + "_runner.py"

        with open(user_code_path, "w") as f:
            f.write(code)

        # Build a clean runner that exec's the user file
        runner_src = textwrap.dedent(f"""\
import sys, io, base64, os, traceback

os.environ["MPLBACKEND"] = "Agg"

_out = io.StringIO()
sys.stdout = _out
sys.stderr = _out

_img_data = None

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    def _show(*a, **kw):
        global _img_data
        _buf = io.BytesIO()
        plt.savefig(_buf, format="png", bbox_inches="tight", dpi=150)
        _buf.seek(0)
        _img_data = base64.b64encode(_buf.read()).decode("ascii")
        plt.clf()

    plt.show = _show
except ImportError:
    pass

try:
    with open({repr(user_code_path)}) as _f:
        exec(compile(_f.read(), "<xera>", "exec"))
except SystemExit:
    pass
except Exception:
    print(traceback.format_exc(), end="")

# Auto-capture open figures (user may not have called plt.show())
if not _img_data:
    try:
        import matplotlib.pyplot as _plt
        if _plt.get_fignums():
            _show()
    except Exception:
        pass

sys.stdout = sys.__stdout__
sys.stderr = sys.__stderr__

_text = _out.getvalue()
if _img_data:
    print("__XERA_IMAGE__:" + _img_data)
else:
    print("__XERA_TEXT__:" + _text)
""")
        with open(runner_path, "w") as f:
            f.write(runner_src)

        # Im Sandkasten des Nutzers (seit 2026-10-16): vorher lief hier jeder
        # Code als root auf CT 203 — ohne jede Einschränkung.
        from . import arbeitsbereich
        _sb = {"user_id": str(user["id"]), "session_id": "py", "admin": bool(user.get("is_admin"))}
        _runner = runner_src.replace(f"with open({repr(user_code_path)}) as _f:\n        exec(compile(_f.read(), \"<xera>\", \"exec\"))",
                                     "exec(compile(__import__('base64').b64decode(" + repr(__import__("base64").b64encode(code.encode()).decode()) + ").decode(), \"<xera>\", \"exec\"))")
        _rc, stdout, stderr, _um = await arbeitsbereich.eingesperrt(_sb, [arbeitsbereich.PYTHON, "-I", "-"], eingabe=_runner.encode(), zeit=10.0, cpu=15)
        if _um:
            return JSONResponse({"type": "error", "message": "Timeout: Code lief länger als 10 Sekunden."})

        out = stdout.decode(errors="replace").strip()
        err_out = stderr.decode(errors="replace").strip()

        if out.startswith("__XERA_IMAGE__:"):
            img_b64 = out[len("__XERA_IMAGE__:"):]
            return JSONResponse({"type": "image", "data": img_b64})
        elif out.startswith("__XERA_TEXT__:"):
            text = out[len("__XERA_TEXT__:"):]
            if not text and err_out:
                return JSONResponse({"type": "error", "message": err_out})
            return JSONResponse({"type": "text", "output": text or "(keine Ausgabe)"})
        else:
            combined = (out + "\n" + err_out).strip()
            if not combined:
                return JSONResponse({"type": "text", "output": "(keine Ausgabe)"})
            return JSONResponse({"type": "error", "message": combined})
    finally:
        for p in [user_code_file, user_code_file + "_user.py", user_code_file + "_runner.py"]:
            try:
                if p:
                    os.unlink(p)
            except Exception:
                pass


@app.post("/api/approve/{action_id}")
async def approve_action(request: Request, action_id: str):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401)
    body = await request.json()
    approved = body.get("approved", False)
    from .permissions import resolve_approval
    resolve_approval(action_id, approved)
    return {"ok": True}


@app.post("/api/denken-beenden")
async def denken_beenden(request: Request):
    """„Jetzt antworten“: Xera beendet das Nachdenken und schreibt die Antwort."""
    body = await request.json()
    event = _denk_ende_events.get(str(body.get("request_id", "")))
    if event:
        event.set()
    return {"ok": bool(event)}


@app.post("/api/stop")
async def stop_generation(request: Request):
    body = await request.json()
    request_id = body.get("request_id", "")
    event = _stop_events.get(request_id)
    if event:
        event.set()
    return {"ok": True}


@app.get("/api/agents")
async def list_agents_endpoint(tab: str = "", neu: int = 0):
    from .agents.registry import list_agents
    # neu=1: nur die Neubau-Agents (neue Oberflaeche seit 2026-10-02)
    return list_agents(tab=tab if tab in ("chat", "homelab") else None, nur_neu=bool(neu))


# ── SSH Key Management ─────────────────────────────────────────────────────────

def _ssh_fingerprint(public_key: str) -> str:
    import base64, hashlib
    try:
        parts = public_key.strip().split()
        if len(parts) < 2:
            raise ValueError("invalid key format")
        key_bytes = base64.b64decode(parts[1])
        digest = hashlib.sha256(key_bytes).digest()
        return "SHA256:" + base64.b64encode(digest).decode().rstrip("=")
    except Exception as e:
        raise HTTPException(400, f"Invalid SSH public key: {e}")


@app.post("/api/ssh-keys")
async def add_ssh_key(request: Request):
    _alte_cli_aus()  # Schlüssel waren nur für `ssh cli@` (alte CLI)
    user = get_current_user(request)
    if not user:
        raise HTTPException(401)
    body = await request.json()
    public_key = body.get("public_key", "").strip()
    name       = body.get("name", "default")[:64]
    if not public_key:
        raise HTTPException(400, "public_key required")
    if not public_key.startswith(("ssh-ed25519", "ssh-rsa", "ecdsa-sha2", "sk-ssh")):
        raise HTTPException(400, "Unsupported key type")
    fingerprint = _ssh_fingerprint(public_key)
    key_id = db.ssh_key_add(user["id"], public_key, fingerprint, name)
    return {"id": key_id, "fingerprint": fingerprint, "name": name}


@app.get("/api/ssh-keys")
async def list_ssh_keys(request: Request):
    _alte_cli_aus()
    user = get_current_user(request)
    if not user:
        raise HTTPException(401)
    return db.ssh_key_list(user["id"])


@app.delete("/api/ssh-keys/{key_id}")
async def delete_ssh_key(request: Request, key_id: int):
    _alte_cli_aus()
    user = get_current_user(request)
    if not user:
        raise HTTPException(401)
    deleted = db.ssh_key_delete(user["id"], key_id)
    if not deleted:
        raise HTTPException(404, "Key not found")
    return {"ok": True}


@app.get("/api/internal/ssh-token/{user_id}")
async def internal_ssh_token(request: Request, user_id: str):
    _alte_cli_aus()
    # Only allow from localhost
    client_host = request.client.host if request.client else ""
    if client_host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(403, "Internal only")
    # Find a valid CLI token for this user
    conn = db.get_db()
    row = conn.execute(
        "SELECT token FROM cli_tokens WHERE user_id = ? AND status = 'complete' ORDER BY rowid DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "No token found for user")
    return {"token": row["token"]}


@app.get("/api/internal/all-ssh-keys")
async def internal_all_ssh_keys(request: Request):
    """Returns all SSH keys with user IDs — for authorized_keys sync daemon."""
    _alte_cli_aus()
    client_host = request.client.host if request.client else ""
    if client_host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(403, "Internal only")
    return db.ssh_key_all()


@app.get("/api/audit")
async def get_audit(request: Request):
    user = await aktueller_nutzer(request)
    if not user or not user["is_admin"]:
        raise HTTPException(403, "Admin only")
    return db.get_audit_log(limit=50)


# --- Cowork: Arbeitsbereiche ------------------------------------------------
#
# Jeder Endpunkt prueft den Eigentuemer. Ein Projekt anhand geschickter Nummer
# herauszugeben war bei /api/chat genau die Luecke, die offenstand.


def _projekt_oder_403(projekt_id: int, user: dict) -> dict:
    projekt = db.projekt_holen(projekt_id, user["id"])
    if not projekt:
        # Bewusst 404 statt 403: Ein 403 verraet, dass es das Projekt gibt.
        raise HTTPException(404, "Vorhaben nicht gefunden")
    return projekt


@app.get("/api/projekte")
async def projekte_liste(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401)
    return db.projekte_holen(user["id"])


@app.post("/api/projekte")
async def projekt_neu(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401)
    daten = await request.json()
    name = (daten.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "Name fehlt")
    return db.projekt_anlegen(
        user["id"],
        name[:120],
        (daten.get("beschreibung") or "").strip()[:600],
        (daten.get("anweisung") or "").strip()[:8000],
    )


@app.get("/api/projekte/{projekt_id}")
async def projekt_eines(request: Request, projekt_id: int):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401)
    return _projekt_oder_403(projekt_id, user)


@app.patch("/api/projekte/{projekt_id}")
async def projekt_bearbeiten(request: Request, projekt_id: int):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401)
    _projekt_oder_403(projekt_id, user)
    daten = await request.json()
    return db.projekt_aendern(
        projekt_id,
        user["id"],
        name=(daten.get("name") or "").strip()[:120] or None,
        beschreibung=daten.get("beschreibung"),
        anweisung=daten.get("anweisung"),
    )


@app.delete("/api/projekte/{projekt_id}")
async def projekt_weg(request: Request, projekt_id: int):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401)
    _projekt_oder_403(projekt_id, user)
    db.projekt_loeschen(projekt_id, user["id"])
    return {"ok": True}


@app.get("/api/projekte/{projekt_id}/notizen")
async def projekt_notizen(request: Request, projekt_id: int):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401)
    _projekt_oder_403(projekt_id, user)
    return db.notizen_holen(projekt_id)


@app.post("/api/projekte/{projekt_id}/notizen")
async def notiz_neu(request: Request, projekt_id: int):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401)
    _projekt_oder_403(projekt_id, user)
    daten = await request.json()
    return db.notiz_speichern(
        projekt_id,
        (daten.get("titel") or "Ohne Titel").strip()[:160],
        (daten.get("inhalt") or "").strip()[:8000],
        daten.get("id"),
    )


@app.delete("/api/projekte/{projekt_id}/notizen/{notiz_id}")
async def notiz_weg(request: Request, projekt_id: int, notiz_id: int):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401)
    _projekt_oder_403(projekt_id, user)
    db.notiz_loeschen(projekt_id, notiz_id)
    return {"ok": True}


@app.post("/api/projekte/{projekt_id}/dateien")
async def projekt_datei_neu(request: Request, projekt_id: int, file: UploadFile = File(...)):
    """Datei in ein Vorhaben legen. Gespeichert wird der herausgezogene Text
    (data/projekte/<id>/), nicht das Original — gebraucht wird nur der Text,
    und so landen keine ausfuehrbaren Dateien auf dem Server."""
    from .docparse import parse_document
    user = get_current_user(request)
    if not user:
        raise HTTPException(401)
    _projekt_oder_403(projekt_id, user)
    daten = await file.read()
    if len(daten) > 15 * 1024 * 1024:
        raise HTTPException(413, "Datei zu gross (max. 15 MB)")
    ergebnis = parse_document(file.filename or "datei", daten)
    text = (ergebnis.get("content") or "").strip()
    if not text:
        raise HTTPException(422, "Aus dieser Datei liess sich kein Text lesen")
    ordner = config.BASE_DIR / "data" / "projekte" / str(projekt_id)
    ordner.mkdir(parents=True, exist_ok=True)
    name = (file.filename or "datei").replace("/", "_").replace("..", "_")[:120]
    pfad = ordner / f"{secrets.token_hex(6)}.txt"
    pfad.write_text(text, encoding="utf-8")
    return db.datei_anlegen(projekt_id, name, str(pfad), len(daten))


@app.delete("/api/projekte/{projekt_id}/dateien/{datei_id}")
async def projekt_datei_weg(request: Request, projekt_id: int, datei_id: int):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401)
    _projekt_oder_403(projekt_id, user)
    datei = db.datei_holen(projekt_id, datei_id)
    if not datei:
        raise HTTPException(404)
    try:
        Path(datei["pfad"]).unlink(missing_ok=True)
    except OSError:
        pass
    db.datei_loeschen(projekt_id, datei_id)
    return {"ok": True}


@app.get("/api/projekte/{projekt_id}/gespraeche")
async def projekt_gespraeche(request: Request, projekt_id: int):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401)
    _projekt_oder_403(projekt_id, user)
    return db.projekt_gespraeche(projekt_id, str(user["id"]))


@app.get("/api/projekte/{projekt_id}/dateien")
async def projekt_dateien(request: Request, projekt_id: int):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401)
    _projekt_oder_403(projekt_id, user)
    return db.dateien_holen(projekt_id)


@app.get("/metrics")
async def prometheus_metrics():
    from .metrics import generate_metrics
    return Response(content=generate_metrics(), media_type="text/plain; version=0.0.4; charset=utf-8")



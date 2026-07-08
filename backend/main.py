import asyncio
import base64
import io
import json
import os
import secrets
import subprocess
import sys
import tempfile
import textwrap
from fastapi import FastAPI, Request, HTTPException, Depends, UploadFile, File
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

app = FastAPI(title="Xera AI")
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SECRET_KEY,
    max_age=30 * 24 * 60 * 60,
    same_site="lax",
    https_only=config.DISCORD_REDIRECT_URI.startswith("https"),
)

# Kill-Switch: per-request stop events, keyed by request_id (UUID)
_stop_events: dict[str, asyncio.Event] = {}

STATIC_DIR = config.BASE_DIR / "static"

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
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def get_current_user(request: Request) -> dict | None:
    # Bearer token (CLI)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        user = db.get_user_by_cli_token(token)
        if user:
            return user
    # Cookie session (Web)
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get_user(user_id)


def get_guest_fingerprint(request: Request) -> str:
    ip = request.headers.get("x-forwarded-for", request.client.host or "unknown")
    if "," in ip:
        ip = ip.split(",")[0].strip()
    ua = request.headers.get("user-agent", "unknown")
    return db.make_fingerprint(ip, ua)


def get_or_create_guest(request: Request) -> dict:
    fingerprint = get_guest_fingerprint(request)
    prompt_count = db.get_guest_prompt_count(fingerprint)
    guest_id = request.session.get("guest_id")
    if not guest_id:
        guest_id = "guest_" + secrets.token_hex(8)
        request.session["guest_id"] = guest_id
    return {
        "id": guest_id,
        "username": "Guest",
        "avatar": None,
        "is_admin": False,
        "is_pro": False,
        "prompt_count": prompt_count,
        "is_guest": True,
        "_fingerprint": fingerprint,
    }


@app.on_event("startup")
async def startup():
    db.init_db()
    from .docgen import cleanup_old_docs
    cleanup_old_docs()
    asyncio.create_task(_cleanup_loop())
    asyncio.create_task(_warmup_llm())


async def _warmup_llm():
    import httpx
    urls = [config.LLAMA_API_URL, config.LLAMA_FAST_URL]
    payload = {
        "model": "local",
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 1,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        for url in urls:
            try:
                await client.post(f"{url}/v1/chat/completions", json=payload)
            except Exception:
                pass


async def _cleanup_loop():
    while True:
        await asyncio.sleep(3600)  # every hour
        from .docgen import cleanup_old_docs
        cleanup_old_docs()


def _html_response():
    content = (STATIC_DIR / "index.html").read_text()
    return Response(content=content, media_type="text/html", headers={"Cache-Control": "no-store"})


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return _html_response()


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return _html_response()


@app.get("/c", response_class=HTMLResponse)
async def chat_page(request: Request):
    return _html_response()


@app.get("/c/{session_id:int}", response_class=HTMLResponse)
async def chat_session_page(request: Request, session_id: int):
    return _html_response()


@app.get("/fully-local", response_class=HTMLResponse)
@app.get("/private-secure", response_class=HTMLResponse)
@app.get("/lightning-fast", response_class=HTMLResponse)
@app.get("/smart-agents", response_class=HTMLResponse)
async def feature_pages(request: Request):
    return _html_response()


@app.get("/auth/login")
async def login(request: Request):
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    return RedirectResponse(auth.get_oauth_url(state))


@app.get("/auth/callback")
async def callback(request: Request, code: str = "", state: str = ""):
    stored_state = request.session.get("oauth_state")
    if not stored_state or stored_state != state:
        raise HTTPException(400, "Invalid state")

    token_data = await auth.exchange_code(code)
    access_token = token_data["access_token"]

    discord_user = await auth.get_discord_user(access_token)
    roles = await auth.check_roles(access_token)

    user = db.get_or_create_user(discord_user, is_pro=roles["is_pro"], is_admin=roles["is_admin"], has_homelab=roles["has_homelab"])

    request.session["user_id"] = user["id"]
    request.session["access_token"] = access_token

    # After CLI auth login, redirect back to /cli-auth page
    next_url = request.session.pop("cli_auth_next", None)
    return RedirectResponse(next_url if next_url else "/")


@app.get("/auth/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")


# --- CLI Auth ---

@app.post("/api/cli-auth/init")
async def cli_auth_init(request: Request):
    """CLI calls this to start login flow. Returns state + URL."""
    _rate_limit(request, max_calls=5, window_seconds=60)
    state = secrets.token_urlsafe(32)
    db.cli_auth_create_state(state)
    return {"state": state, "url": f"{config.DISCORD_REDIRECT_URI.rsplit('/auth', 1)[0]}/cli-auth?state={state}"}


@app.get("/cli-auth", response_class=HTMLResponse)
async def cli_auth_page(request: Request, state: str = ""):
    """Page user opens in browser to complete CLI auth."""
    if not state:
        return HTMLResponse("<h2>Missing state parameter.</h2>", status_code=400)

    user = get_current_user(request)
    if user:
        token = secrets.token_urlsafe(32)
        db.cli_auth_complete(state, user["id"], token)
        return HTMLResponse(f"""<!DOCTYPE html><html><head>
        <title>Xera Code — Authenticated</title>
        <style>
            body {{ font-family: system-ui; background: #0d0d0d; color: #e2e8f0; display: flex;
                   align-items: center; justify-content: center; height: 100vh; margin: 0; }}
            .card {{ background: #1a1a2e; border: 1px solid #7c3aed; border-radius: 12px;
                    padding: 2rem 3rem; text-align: center; max-width: 400px; }}
            h2 {{ color: #a78bfa; margin-top: 0; }}
            p {{ color: #94a3b8; }}
        </style></head><body>
        <div class="card">
            <h2>✓ Authenticated</h2>
            <p>Welcome, <strong>{user["username"]}</strong>!</p>
            <p>You can close this tab and return to the terminal.</p>
        </div></body></html>""")

    # Not logged in — redirect to Discord OAuth, come back here after
    next_url = f"/cli-auth?state={state}"
    request.session["cli_auth_next"] = next_url
    redirect_state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = redirect_state
    oauth_url = auth.get_oauth_url(redirect_state) + f"&state={redirect_state}"
    return HTMLResponse(f"""<!DOCTYPE html><html><head>
    <title>Xera Code — Login</title>
    <style>
        body {{ font-family: system-ui; background: #0d0d0d; color: #e2e8f0; display: flex;
               align-items: center; justify-content: center; height: 100vh; margin: 0; }}
        .card {{ background: #1a1a2e; border: 1px solid #7c3aed; border-radius: 12px;
                padding: 2rem 3rem; text-align: center; max-width: 400px; }}
        h2 {{ color: #a78bfa; margin-top: 0; }}
        a.btn {{ display: inline-block; margin-top: 1rem; padding: 0.75rem 1.5rem;
                background: #5865F2; color: white; text-decoration: none;
                border-radius: 8px; font-weight: 600; }}
        a.btn:hover {{ background: #4752c4; }}
    </style></head><body>
    <div class="card">
        <h2>Xera Code Login</h2>
        <p>Login with Discord to authenticate your terminal session.</p>
        <a class="btn" href="{auth.get_oauth_url(redirect_state)}">Login with Discord</a>
    </div></body></html>""")


@app.get("/api/cli-auth/poll")
async def cli_auth_poll(request: Request, state: str):
    """CLI polls this until status is 'complete'."""
    _rate_limit(request, max_calls=30, window_seconds=60)  # 30 polls/min max
    result = db.cli_auth_poll(state)
    if not result:
        return {"status": "expired"}
    if result["status"] == "complete":
        user = db.get_user(result["user_id"])
        return {"status": "complete", "token": result["token"], "username": user["username"] if user else ""}
    return {"status": "pending"}


@app.get("/api/me")
async def me(request: Request):
    user = get_current_user(request)
    if user:
        remaining = max(0, config.FREE_PROMPT_LIMIT - user["prompt_count"])
        return {
            "id": user["id"],
            "username": user["username"],
            "avatar": user["avatar"],
            "is_admin": bool(user["is_admin"]),
            "is_pro": bool(user["is_pro"]),
            "has_homelab": bool(user.get("has_homelab")),
            "prompt_count": user["prompt_count"],
            "prompts_remaining": remaining if not (user["is_pro"] or user["is_admin"]) else -1,
            "limit": config.FREE_PROMPT_LIMIT,
            "is_guest": False,
        }
    guest = get_or_create_guest(request)
    remaining = max(0, config.FREE_PROMPT_LIMIT - guest["prompt_count"])
    return {
        "id": guest["id"],
        "username": "Guest",
        "avatar": None,
        "is_admin": False,
        "is_pro": False,
        "prompt_count": guest["prompt_count"],
        "prompts_remaining": remaining,
        "limit": config.FREE_PROMPT_LIMIT,
        "is_guest": True,
    }


@app.post("/api/chat")
async def chat_endpoint(request: Request):
    user = get_current_user(request)
    is_guest = user is None

    if is_guest:
        guest = get_or_create_guest(request)
        prompt_count = guest["prompt_count"]
        if prompt_count >= config.FREE_PROMPT_LIMIT:
            return JSONResponse(status_code=403, content={
                "error": "limit_reached",
                "requires_login": True,
            })
    else:
        prompt_count = user["prompt_count"]
        if not user["is_pro"] and not user["is_admin"]:
            if prompt_count >= config.FREE_PROMPT_LIMIT:
                return JSONResponse(status_code=403, content={
                    "error": "limit_reached",
                    "requires_login": False,
                })

    body = await request.json()
    messages = body.get("messages", [])
    session_id = body.get("session_id")
    mode = body.get("mode", "chat")
    brain = body.get("brain")
    agent_id = body.get("agent_id")  # optional: lock to specific agent
    platform = body.get("platform", "web")
    if brain not in ("big", "fast", "code"):
        brain = None

    # For chat tab (mode="agents"): only use agent system if orchestrator finds a match
    if mode == "agents" and not agent_id:
        from .agents.orchestrator import select_agent
        if select_agent(messages, tab="chat") is None:
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

    if is_guest:
        db.increment_guest_prompt_count(guest["_fingerprint"])

        async def generate():
            full_response = []
            yield f"data: {json.dumps({'session_id': None, 'request_id': req_id})}\n\n"
            source = run_agent(messages, mode=mode, user_id=guest["id"], brain_override=brain, agent_id=agent_id, stop_event=stop_ev) if mode in ("agents", "homelab") else stream_chat(messages, brain_override=brain)
            async for chunk in source:
                part = _collect_content(chunk, mode)
                if part:
                    full_response.append(part)
                yield chunk
            _stop_events.pop(req_id, None)

        return StreamingResponse(generate(), media_type="text/event-stream")

    if not session_id:
        # CLI → Code tab; web agents → Chat tab; homelab stays homelab
        if mode == "agents":
            session_mode = "code" if platform == "cli" else "chat"
        else:
            session_mode = mode
        session_id = db.create_session(user["id"], mode=session_mode)
        first_msg = _extract_text(messages[-1].get("content", ""))[:50]
        db.update_session_title(session_id, first_msg or "Neuer Chat")

    db.save_message(session_id, "user", _extract_text(messages[-1]["content"]))
    db.increment_prompt_count(user["id"])
    mark_active(user["id"])

    async def generate():
        full_response = []
        try:
            yield f"data: {json.dumps({'session_id': session_id, 'request_id': req_id})}\n\n"
            source = run_agent(messages, mode=mode, user_id=user["id"], session_id=session_id, brain_override=brain, agent_id=agent_id, stop_event=stop_ev) if mode in ("agents", "homelab") else stream_chat(messages, brain_override=brain, user_id=user["id"])
            async for chunk in source:
                part = _collect_content(chunk, mode)
                if part:
                    full_response.append(part)
                yield chunk
            db.save_message(session_id, "assistant", "".join(full_response))
            all_msgs = messages + [{"role": "assistant", "content": "".join(full_response)}]
            asyncio.create_task(extract_learnings(user["id"], session_id, all_msgs))
        finally:
            mark_idle(user["id"])
            _stop_events.pop(req_id, None)

    return StreamingResponse(generate(), media_type="text/event-stream")


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
    return db.get_messages(session_id)


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
async def delete_session(request: Request, session_id: int):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401)
    session = db.get_session(session_id)
    if not session or session["user_id"] != str(user["id"]):
        raise HTTPException(403)
    db.delete_session(session_id)
    return {"ok": True}


@app.post("/api/rag/ingest")
async def rag_ingest(request: Request):
    user = get_current_user(request)
    if not user or not user["is_admin"]:
        raise HTTPException(403, "Admin only")
    from .rag import ingest
    result = await ingest()
    return result


@app.get("/api/rag/status")
async def rag_status():
    from .rag import get_status
    return get_status()


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    from .docparse import parse_document
    from .docgen import DOCS_DIR
    data = await file.read()
    # Save raw file so read_document tool can find it later
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = (file.filename or "upload").replace("/", "_").replace("..", "_")
    dest = DOCS_DIR / safe_name
    dest.write_bytes(data)
    result = parse_document(file.filename or "file", data)
    result["stored_name"] = safe_name
    return result


@app.get("/api/download/{filename}")
async def download_file(filename: str):
    from .docgen import DOCS_DIR
    path = (DOCS_DIR / filename).resolve()
    if path.parent != DOCS_DIR.resolve():
        raise HTTPException(400, "Invalid filename")
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "File not found")
    import mimetypes
    media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return FileResponse(
        str(path),
        filename=filename,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/python")
async def run_python(request: Request):
    """Execute Python code in a restricted subprocess with 10s timeout.
    Returns image (matplotlib), text output, or error.
    """
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

        proc = await asyncio.create_subprocess_exec(
            sys.executable, runner_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd="/tmp",
            env={
                **os.environ,
                "MPLBACKEND": "Agg",
                "HOME": "/tmp",
            }
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10.0)
        except asyncio.TimeoutError:
            proc.kill()
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


@app.post("/api/stop")
async def stop_generation(request: Request):
    body = await request.json()
    request_id = body.get("request_id", "")
    event = _stop_events.get(request_id)
    if event:
        event.set()
    return {"ok": True}


@app.get("/api/agents")
async def list_agents_endpoint(tab: str = ""):
    from .agents.registry import list_agents
    return list_agents(tab=tab if tab in ("chat", "homelab") else None)


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
    user = get_current_user(request)
    if not user:
        raise HTTPException(401)
    return db.ssh_key_list(user["id"])


@app.delete("/api/ssh-keys/{key_id}")
async def delete_ssh_key(request: Request, key_id: int):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401)
    deleted = db.ssh_key_delete(user["id"], key_id)
    if not deleted:
        raise HTTPException(404, "Key not found")
    return {"ok": True}


@app.get("/api/internal/ssh-token/{user_id}")
async def internal_ssh_token(request: Request, user_id: str):
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
    client_host = request.client.host if request.client else ""
    if client_host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(403, "Internal only")
    return db.ssh_key_all()


@app.get("/api/audit")
async def get_audit(request: Request):
    user = get_current_user(request)
    if not user or not user["is_admin"]:
        raise HTTPException(403, "Admin only")
    return db.get_audit_log(limit=50)


@app.get("/metrics")
async def prometheus_metrics():
    from .metrics import generate_metrics
    return Response(content=generate_metrics(), media_type="text/plain; version=0.0.4; charset=utf-8")



"""
Xera AI — Multi-Agent Execution Engine
Runs any agent from the registry with full tool support, SSE streaming,
permission checks, and agent-to-agent delegation.
"""

import asyncio
import httpx
import json
import re
from datetime import datetime
from uuid import uuid4
from collections.abc import AsyncGenerator

from .. import arbeitsbereich, config
from ..tools import get_tools_for_agent, execute_tool, SANDBOX
from ..arbeitsbereich import SANDBOX_WERKZEUGE, gesperrte_werkzeuge
from ..permissions import (
    classify_tool, needs_approval, is_blocked, level_label,
    create_approval, get_approval_result, cleanup_approval, log_action,
)
from ..learning import get_learnings_context
from .registry import AGENTS, get_agent
from .orchestrator import select_agent, select_agents


MAX_ITERATIONS = 12
MAX_TOOL_OUTPUT = 12000          # was an die Oberfläche geht (Agent-Karte, Link-Suche in auftraege.py)
MAX_TOOL_OUTPUT_MODELL = 60000   # was der Agent selbst sieht — eine ganze Datei aus read_file (seit 2026-10-17)
APPROVAL_TIMEOUT = 120

# ─── Per-session document state ───────────────────────────────────────────────
# Stores the last created document's source markdown per session so the model
# can make precise edits across turns (move table, change title, etc.)
_DOC_STATE: dict[int | str, dict] = {}
_DOC_STATE_MAX = 500  # evict oldest when over limit


def _store_doc_state(session_id, state: dict) -> None:
    if session_id is None:
        return
    _DOC_STATE[session_id] = state
    if len(_DOC_STATE) > _DOC_STATE_MAX:
        try:
            del _DOC_STATE[next(iter(_DOC_STATE))]
        except StopIteration:
            pass


def _get_doc_state(session_id) -> dict | None:
    if session_id is None:
        return None
    return _DOC_STATE.get(session_id)

_PARAM_TAG_RE = re.compile(r'<parameter=(\w+)>\s*(.*?)\s*</parameter>', re.DOTALL)
_FUNC_BLOCK_RE = re.compile(r'<function=(\w+)>(.*?)</function>(?:\s*</tool_call>)?', re.DOTALL)
_QWEN_TOOL_CALL_RE = re.compile(r'<tool_call>\s*(\{.*?\})\s*</tool_call>', re.DOTALL)
_PIPE_TOOL_CALL_RE = re.compile(r'<\|tool_call\>call:(\w+)\{(.*?)\}(?:<tool_call\|>|$)', re.DOTALL)
_CODE_BLOCK_RE = re.compile(r'```(\w+)\n(.*?)```', re.DOTALL)


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _normalize_tokens(text: str) -> str:
    text = text.replace('<|"|>', '"')
    text = text.replace("<|'|>", "'")
    text = re.sub(r'<\|(?!tool_call)[^|>]{0,20}\|>', '', text)
    return text


def _strip_tool_call_blocks(text: str) -> str:
    text = _FUNC_BLOCK_RE.sub("", text)
    text = _QWEN_TOOL_CALL_RE.sub("", text)
    text = _PIPE_TOOL_CALL_RE.sub("", text)
    text = re.sub(r'<\|tool_call\>.*?(?:<tool_call\|>|$)', '', text, flags=re.DOTALL)
    return text.strip()


def _try_parse_args(body: str) -> dict:
    placeholders: list[str] = []

    def _stash(m: re.Match) -> str:
        idx = len(placeholders)
        placeholders.append(m.group(1))
        return f'"__PH{idx}__"'

    processed = re.sub(r'<\|"\|>(.*?)<\|"\|>', _stash, body, flags=re.DOTALL)
    processed = re.sub(r'<\|[^|>]{0,30}\|>', '', processed).strip()

    def _restore(d: dict) -> dict:
        result = {}
        for k, v in d.items():
            if isinstance(v, str):
                m = re.fullmatch(r'__PH(\d+)__', v)
                if m and int(m.group(1)) < len(placeholders):
                    result[k] = placeholders[int(m.group(1))]
                else:
                    # Un-double-escape: model sometimes generates \\n instead of \n
                    # json.loads("\\n") → literal backslash+n → fix to real newline
                    result[k] = v.replace('\\n', '\n').replace('\\t', '\t')
            else:
                result[k] = v
        return result

    for raw in [processed, processed.replace('\n', '\\n').replace('\r', '')]:
        for candidate in [raw, re.sub(r'(?<!["\w])(\w+)\s*:', r'"\1":', raw)]:
            for wrapped in [candidate, '{' + candidate + '}']:
                try:
                    return _restore(json.loads(wrapped))
                except (json.JSONDecodeError, ValueError):
                    pass

    result = {}
    for key, val in _PARAM_TAG_RE.findall(body):
        result[key] = val.strip()
    return result


def _guess_code_filename(code: str, lang: str, idx: int) -> str:
    first_lines = code.split('\n')[:8]
    for line in first_lines:
        m = re.search(r'(?:file|filename|script):\s*([^\s]+)', line, re.IGNORECASE)
        if m:
            return re.sub(r'[^\w\-]', '_', m.group(1).rstrip('.'))[:40]
    for line in first_lines:
        for pat, name in [
            (r'\bif\s+__name__', 'main'), (r'def\s+main\b', 'main'),
            (r'#!/usr/bin/env\s+python', 'script'), (r'#!/bin/(bash|sh)', 'script'),
            (r'FastAPI\(\)', 'app'), (r'Flask\(\)', 'app'), (r'express\(\)', 'server'),
        ]:
            if re.search(pat, line):
                return name
    return {'py': 'script', 'sh': 'script', 'bash': 'script', 'js': 'app', 'ts': 'app',
            'html': 'page', 'yaml': 'config', 'yml': 'config', 'json': 'data',
            'sql': 'query', 'ps1': 'script'}.get(lang, f'code_{idx + 1}')


async def _auto_download(content: str):
    """Scan final response content for code blocks and emit download SSE events."""
    try:
        from ..docgen import create_document, _CODE_EXTENSIONS
    except Exception:
        return
    seen: set[int] = set()
    for i, m in enumerate(_CODE_BLOCK_RE.finditer(content)):
        lang = m.group(1).lower()
        code = m.group(2).strip()
        if not code or len(code) < 30 or lang not in _CODE_EXTENSIONS:
            continue
        key = hash(code)
        if key in seen:
            continue
        seen.add(key)
        filename = _guess_code_filename(code, lang, i)
        try:
            url = create_document(lang, code, filename)
            path_name = url.split("/")[-1]
            yield _sse({
                "type": "document",
                "url": url,
                "filename": path_name,
                "size": len(code.encode("utf-8")),
                "doc_type": lang,
            })
        except Exception:
            pass


def _parse_text_tool_calls(content: str) -> list[dict] | None:
    normalized = _normalize_tokens(content)
    calls = []

    for i, (fname, body) in enumerate(_FUNC_BLOCK_RE.findall(normalized)):
        body = body.strip()
        fargs = {}
        param_matches = _PARAM_TAG_RE.findall(body)
        if param_matches:
            for key, val in param_matches:
                fargs[key] = val.strip()
        elif body.startswith("{"):
            try:
                fargs = json.loads(body)
            except json.JSONDecodeError:
                pass
        calls.append({"id": f"text_{fname}_{i}", "function": {"name": fname, "arguments": fargs}})

    for i, raw in enumerate(_QWEN_TOOL_CALL_RE.findall(normalized)):
        try:
            obj = json.loads(raw)
            fname = obj.get("name", "")
            fargs = obj.get("arguments", {})
            if isinstance(fargs, str):
                fargs = json.loads(fargs)
            if fname:
                calls.append({"id": f"qwen_{fname}_{i}", "function": {"name": fname, "arguments": fargs}})
        except (json.JSONDecodeError, ValueError):
            pass

    for i, (fname, body) in enumerate(_PIPE_TOOL_CALL_RE.findall(normalized)):
        fargs = _try_parse_args("{" + body + "}")
        if fname:
            calls.append({"id": f"pipe_{fname}_{i}", "function": {"name": fname, "arguments": fargs}})

    return calls if calls else None


def _parse_tool_args(func: dict) -> dict:
    raw = func.get("arguments", {})
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    return raw if isinstance(raw, dict) else {}


def _get_llm_url(brain: str = "big") -> str:
    """Ein Modell, eine Adresse. Der Parameter bleibt fuer die Aufrufer stehen."""
    return config.LLAMA_API_URL


class _Gestoppt(Exception):
    """Stopp-Knopf während eines laufenden Modell-Aufrufs."""


async def _mit_stopp(aufruf, stop_event):
    """Wartet auf den Modell-Aufruf, bricht ihn aber beim Stopp-Knopf sofort
    ab (Verbindung zu → llama-server bricht die Aufgabe ab). Vorher lief ein
    Agent nach dem Stopp weiter, bis der aktuelle Aufruf fertig war — bei
    16k Tokens bis zu 15 min (2026-10-15)."""
    if stop_event is None:
        return await aufruf
    arbeit = asyncio.ensure_future(aufruf)
    stopp = asyncio.ensure_future(stop_event.wait())
    try:
        fertig, _ = await asyncio.wait({arbeit, stopp}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        stopp.cancel()
    if arbeit in fertig:
        return arbeit.result()
    arbeit.cancel()
    raise _Gestoppt


async def _call_llm(messages: list[dict], tools: list[dict] | None, brain: str, max_tokens: int = 2048,
                    fortschritt: dict | None = None, tool_choice: str = "auto") -> dict:
    payload: dict = {
        "model": "xera-ai",
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice
    from ..tools import LLAMA_SLOT
    if LLAMA_SLOT.get() is not None:
        payload["id_slot"] = LLAMA_SLOT.get()
    # Neubau-Agents mit "denkmodus: an" (seit 2026-10-02). Der Schalter im
    # Request ueberschreibt das serverseitige --reasoning off.
    if brain == "denken":
        payload["chat_template_kwargs"] = {"enable_thinking": True}
        # Budget fürs Denken (seit 2026-10-15) — sonst denkt Qwen3.8 bei grossen
        # Aufgaben bis ans Token-Limit und liefert nichts. Voll nur vor dem ersten
        # Schritt; danach knapp (seit 2026-10-17): vorher dachte ein Agent vor
        # JEDEM Werkzeugschritt bis zu 4 096 Tokens — bei zwei parallelen Agents
        # (~14 t/s) bis 5 min pro Schritt (Gespräch 580).
        # Seit 2026-10-19 nach Denkaufwand der Anfrage (aufwand.py), für Agents
        # gedeckelt: vier Agents mit „max“ würden die Slots minutenlang belegen.
        from .. import aufwand
        erster_schritt = not any(m.get("role") == "assistant" for m in messages)
        stufe = aufwand.AKTUELL.get()
        aufwand.anfrage_ergaenzen(payload, stufe if stufe != "aus" else "mittel",
                                  tokens=aufwand.agent_budget(stufe if stufe != "aus" else "mittel", erster_schritt),
                                  nachricht="\n\nGenug überlegt — jetzt handeln.\n")
        max_tokens = max(max_tokens, 8192)
        payload["max_tokens"] = max_tokens

    # Long documents (document_write uses max_tokens=8192) can take several
    # minutes to generate on the local GPU, so big requests get a generous
    # 600s read timeout. Smaller calls keep a tighter 120s so failures are
    # still caught fast. Connect timeout stays short either way so an
    # unreachable LLM server fails fast.
    read_timeout = 1500.0 if max_tokens >= 8192 else 600.0 if max_tokens >= 4096 else 120.0
    timeout = httpx.Timeout(10.0, read=read_timeout, write=30.0, pool=10.0)

    if fortschritt is not None:
        return await _call_llm_strom(payload, timeout, brain, fortschritt)
    from .. import slotsperre
    async with slotsperre.slot(payload.get("id_slot")), httpx.AsyncClient(timeout=timeout) as client:
        await slotsperre.leeren_slot_anstossen(client, _get_llm_url(brain), payload.get("id_slot"))
        resp = await client.post(
            f"{_get_llm_url(brain)}/v1/chat/completions",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


async def _call_llm_strom(payload: dict, timeout: httpx.Timeout, brain: str, fortschritt: dict) -> dict:
    """Wie _call_llm, aber gestreamt (seit 2026-10-16): so sieht die Agent-Karte,
    dass etwas passiert. Vorher stand dort bis zu 16 min nur „thinking“
    (Chat 512). Liefert dieselbe Form wie die nicht gestreamte Antwort."""
    url = f"{_get_llm_url(brain)}/v1/chat/completions"
    payload = {**payload, "stream": True, "return_progress": True}
    teile: list[str] = []
    aufrufe: dict[int, dict] = {}
    ende = None

    def fehler(status: int, text: str):
        anfrage = httpx.Request("POST", url)
        return httpx.HTTPStatusError(f"HTTP {status}", request=anfrage,
                                     response=httpx.Response(status, text=text, request=anfrage))

    from .. import slotsperre
    async with slotsperre.slot(payload.get("id_slot")), httpx.AsyncClient(timeout=timeout) as client:
        await slotsperre.leeren_slot_anstossen(client, _get_llm_url(brain), payload.get("id_slot"))
        async with client.stream("POST", url, json=payload) as resp:
            if resp.status_code >= 400:
                raise fehler(resp.status_code, (await resp.aread()).decode("utf-8", "replace"))
            async for zeile in resp.aiter_lines():
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
                    f = stueck["error"]
                    raise fehler(int(f.get("code") or 500) if isinstance(f, dict) else 500, json.dumps(f, ensure_ascii=False))
                if stueck.get("prompt_progress"):
                    fortschritt["einlesen"] = stueck["prompt_progress"]
                    continue
                for wahl in stueck.get("choices") or []:
                    ende = wahl.get("finish_reason") or ende
                    d = wahl.get("delta") or {}
                    for feld in ("content", "reasoning_content"):
                        if d.get(feld):
                            if feld == "content":
                                teile.append(d[feld])
                            fortschritt["zeichen"] = fortschritt.get("zeichen", 0) + len(d[feld])
                    for tc in d.get("tool_calls") or []:
                        a = aufrufe.setdefault(tc.get("index", 0), {"id": "", "name": "", "args": ""})
                        a["id"] = tc.get("id") or a["id"]
                        fn = tc.get("function") or {}
                        a["name"] += fn.get("name") or ""
                        a["args"] += fn.get("arguments") or ""
                        fortschritt["zeichen"] = fortschritt.get("zeichen", 0) + len(fn.get("arguments") or "")
    nachricht: dict = {"role": "assistant", "content": "".join(teile)}
    if aufrufe:
        nachricht["tool_calls"] = [{"id": a["id"] or f"call_{i}", "type": "function",
                                    "function": {"name": a["name"], "arguments": a["args"] or "{}"}}
                                   for i, a in sorted(aufrufe.items())]
    return {"choices": [{"message": nachricht, "finish_reason": ende}]}


def _fortschritt_text(f: dict) -> str:
    p = f.get("einlesen") or {}
    try:
        neu = int(p.get("total", 0)) - int(p.get("cache", 0))
        fertig = int(p.get("processed", 0)) - int(p.get("cache", 0))  # processed zählt den Cache mit
    except (TypeError, ValueError):
        neu = fertig = 0
    zeichen = f.get("zeichen", 0)
    if not zeichen and neu >= 1500 and fertig < neu:
        return f"liest ein … {int(100 * fertig / neu)} %"
    if zeichen >= 200:
        return f"schreibt … ≈ {int(zeichen / 3.5):,} Tokens".replace(",", "\u2009")
    return ""


async def _describe_images_fast(image_urls: list[str]) -> list[str]:
    descs = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        for url in image_urls:
            try:
                r = await client.post(
                    f"{config.LLAMA_API_URL}/v1/chat/completions",
                    json={
                        "model": "xera-ai",
                        "messages": [{"role": "user", "content": [
                            {"type": "image_url", "image_url": {"url": url}},
                            {"type": "text", "text": "Describe this image in detail."},
                        ]}],
                        "max_tokens": 512,
                        "stream": False,
                    },
                )
                r.raise_for_status()
                descs.append(r.json()["choices"][0]["message"]["content"])
            except Exception:
                descs.append("[Bild konnte nicht analysiert werden]")
    return descs


def _flatten_multimodal(messages: list[dict]) -> tuple[list[dict], list[str]]:
    flat = []
    all_images = []
    for m in messages:
        c = m.get("content")
        if isinstance(c, list):
            text_parts = [p.get("text", "") for p in c if p.get("type") == "text"]
            images = [p["image_url"]["url"] for p in c if p.get("type") == "image_url"]
            text = " ".join(text_parts)
            all_images.extend(images)
            flat.append({**m, "content": text})
        else:
            flat.append(m)
    return flat, all_images


_FEEDBACK_STARTS = (
    "✅", "✓", "⭐", "was soll ich", "ich habe ", "möchtest du",
    "anpassungsmöglich", "erstellt am:", "erstellt mit xera",
    "was willst du", "was möchtest du", "soll ich noch",
    "what would you", "would you like", "feel free to",
)

def _strip_trailing_chat(doc: str) -> str:
    """Remove any feedback/chat text appended after the actual document content."""
    # Strip trailing block starting with --- followed by feedback
    cleaned = re.sub(
        r'\n---\n(?=[\s\S]*(?:✅|Was soll ich|Ich habe |Möchtest du|Erstellt am))',
        '',
        doc,
        flags=re.DOTALL,
    )
    # Strip any trailing lines that are pure feedback (✅, questions, etc.)
    lines = cleaned.split('\n')
    end = len(lines)
    for i in range(len(lines) - 1, -1, -1):
        stripped = lines[i].strip().lower()
        if not stripped:
            continue
        if any(stripped.startswith(p) for p in _FEEDBACK_STARTS) or stripped.startswith('— '):
            end = i
        else:
            break
    # Also drop a trailing --- left bare before feedback
    while end > 0 and lines[end - 1].strip() in ('---', ''):
        end -= 1
    return '\n'.join(lines[:end]).rstrip()


def _extract_doc_part(content: str) -> str:
    """Return only the document portion: strip prefix chat text and trailing feedback."""
    raw_lines = content.split('\n')
    start = 0
    for i, line in enumerate(raw_lines):
        if line.startswith('# ') and not line.startswith('## '):
            start = i
            break
    else:
        for i, line in enumerate(raw_lines):
            if line.startswith('## ') and not line.startswith('### '):
                start = i
                break
    doc = '\n'.join(raw_lines[start:])
    return _strip_trailing_chat(doc)


def _looks_like_document(content: str) -> bool:
    """Return True if the LLM output contains a structured markdown document."""
    doc = _extract_doc_part(content)
    lines = [l for l in doc.strip().split('\n') if l.strip()]
    has_title = any(l.startswith('# ') and not l.startswith('## ') for l in lines[:5])
    sections  = sum(1 for l in lines if l.startswith('## ') and not l.startswith('### '))
    return has_title and sections >= 1 and len(doc) > 80


def _make_summary_line(doc_content: str, max_chars: int = 140) -> str:
    """Best-effort 1-sentence content teaser, used only by the auto-doc fallback
    (the model didn't call create_document, so it never wrote its own Phase 4
    summary either). Picks the first real prose paragraph after the title."""
    doc = _extract_doc_part(doc_content)
    for line in doc.split('\n'):
        s = line.strip()
        if not s or s.startswith('#') or s.startswith('|') or s.startswith('-') or s.startswith('*'):
            continue
        sentence = re.split(r'(?<=[.!?])\s', s, maxsplit=1)[0]
        if len(sentence) > max_chars:
            sentence = sentence[:max_chars].rsplit(' ', 1)[0].rstrip(',.;:') + "…"
        return sentence
    return ""


def _detect_doc_theme(messages: list[dict], doc_content: str = "") -> str:
    """Pick a theme: explicit user color > content-based > document default."""
    try:
        from ..docgen import _COLOR_NAMES, _THEMES
    except Exception:
        return "purple"

    user_text = " ".join(
        (m.get("content") or "") if isinstance(m.get("content"), str) else ""
        for m in messages if m.get("role") == "user"
    ).lower()

    # 1. Explicit hex code in user message
    m = re.search(r'#[0-9a-f]{6}', user_text)
    if m:
        return m.group(0)

    # 2. Explicit color/theme name in user message
    all_names = sorted({**_COLOR_NAMES, **{k: k for k in _THEMES}}, key=len, reverse=True)
    for name in all_names:
        if name in user_text:
            return name

    # 3. Infer theme from document content / topic
    c = (doc_content + " " + user_text).lower()
    if any(w in c for w in ["windows", "linux", "server", "proxmox", "netzwerk", "network", "router", "system"]):
        return "dark"
    if any(w in c for w in ["python", "javascript", "code", "api", "software", "developer", "programming", "git"]):
        return "blue"
    if any(w in c for w in ["security", "firewall", "vpn", "hack", "pentest", "sicherheit", "schutz"]):
        return "#9f1239"   # deep red
    if any(w in c for w in ["ai", "artificial intelligence", "machine learning", "neural", "llm", "gpt", "model", "transformer"]):
        return "indigo"
    if any(w in c for w in ["natur", "umwelt", "klima", "bio", "eco", "green", "pflanzen"]):
        return "green"
    if any(w in c for w in ["finanzen", "budget", "kosten", "geld", "rechnung", "wirtschaft", "money"]):
        return "warm"
    if any(w in c for w in ["geschichte", "history", "lebenslauf", "biographie", "timeline"]):
        return "#92400e"   # warm brown
    if any(w in c for w in ["medizin", "gesundheit", "health", "medical", "klinik"]):
        return "türkis"
    if any(w in c for w in ["kreativ", "design", "art", "musik", "film", "media"]):
        return "pink"

    # 4. Default: purple
    return "purple"


def _pick_layout(doc_content: str) -> str:
    """Choose layout density based on document length."""
    non_empty = [l for l in doc_content.split('\n') if l.strip()]
    if len(non_empty) > 70:
        return "compact"
    elif len(non_empty) < 20:
        return "spacious"
    return "normal"


def _detect_file_type(messages: list[dict]) -> str:
    """Infer the requested file type from user messages. Falls back to 'pdf'."""
    user_text = " ".join(
        (m.get("content") or "") if isinstance(m.get("content"), str) else ""
        for m in messages if m.get("role") == "user"
    ).lower()

    # Check explicit extensions first (most specific)
    ext_map = [
        ([".py", "python skript", "python script", "python file", "python datei"], "py"),
        # ps1 must come before sh: "powershell script" contains "shell script" as substring
        ([".ps1", "powershell"], "ps1"),
        ([".sh", "bash skript", "bash script", "shell script", "shell skript"], "sh"),
        ([".ts", "typescript"], "ts"),
        ([".js", "javascript", "js file", "js datei"], "js"),
        ([".html", "html seite", "html page", "html file", "html datei", "webseite"], "html"),
        ([".css", "stylesheet", "css file", "css datei"], "css"),
        ([".sql", "sql skript", "sql script", "sql file"], "sql"),
        ([".json", "json file", "json datei"], "json"),
        ([".yaml", ".yml", "yaml file", "yaml datei"], "yaml"),
        ([".toml", "toml file"], "toml"),
        ([".txt", "text file", "textdatei"], "txt"),
        ([".md", "markdown", "md file", "md datei", "eine md", "ein md"], "md"),
        ([".docx", "word dokument", "word document", "word file", "docx",
          "ein word", "als word", "ein wordfile", "word datei", "im word format"], "docx"),
        ([".xlsx", "excel", "spreadsheet", "xlsx"], "xlsx"),
    ]
    for patterns, doc_type in ext_map:
        if any(p in user_text for p in patterns):
            return doc_type
    return "pdf"


def _detect_doc_options(messages: list[dict]) -> dict:
    """Detect show_header, cover_page and toc from user messages."""
    user_text = " ".join(
        (m.get("content") or "") if isinstance(m.get("content"), str) else ""
        for m in messages if m.get("role") == "user"
    ).lower()
    _no_header = ("kein header", "ohne header", "no header", "kein kopf", "ohne kopf",
                  "kein kopfzeile", "ohne kopfzeile", "header entfernen", "header weg",
                  "hide header", "remove header", "without header")
    _cover = ("titelseite", "deckblatt", "mit titelseite", "mit deckblatt",
              "cover page", "title page", "add cover")
    _toc = ("inhaltsverzeichnis", "table of contents", "mit toc", "toc hinzufügen",
            "add table of contents", "add a toc")
    # Negation-aware match: only match if NOT preceded by "kein "/"ohne "/"no " within 8 chars
    def _matches(text, keywords):
        for kw in keywords:
            idx = text.find(kw)
            while idx != -1:
                prefix = text[max(0, idx - 8):idx]
                if "kein" not in prefix and "ohne" not in prefix and "no " not in prefix:
                    return True
                idx = text.find(kw, idx + 1)
        return False
    return {
        "show_header": not any(p in user_text for p in _no_header),
        "cover_page": _matches(user_text, _cover),
        "toc": _matches(user_text, _toc),
    }


def _auto_create_doc(content: str, messages: list[dict], session_id=None) -> tuple[str | None, str]:
    """Create a file from agent output; detect type from user messages. Returns (url, theme) or (None, '')."""
    try:
        from ..docgen import create_document
    except Exception:
        return None, ""

    doc_type = _detect_file_type(messages)
    doc = _extract_doc_part(content)

    lines = [l for l in doc.strip().split('\n') if l.strip()]
    title    = next((l[2:].strip() for l in lines if l.startswith('# ') and not l.startswith('## ')), "dokument")
    filename = re.sub(r'[^\w]', '_', title.lower())[:60].strip('_') or "dokument"

    theme  = _detect_doc_theme(messages, doc)
    layout = _pick_layout(doc)
    opts   = _detect_doc_options(messages)

    try:
        if doc_type == "pdf":
            url = create_document("pdf", doc, filename, theme=theme, layout=layout,
                                  show_header=opts["show_header"], cover_page=opts["cover_page"],
                                  toc=opts["toc"])
        else:
            url = create_document(doc_type, doc, filename)
        # Persist so model can edit in the next turn
        _store_doc_state(session_id, {
            "content":     doc,
            "filename":    filename,
            "theme":       theme,
            "layout":      layout,
            "show_header": opts["show_header"],
            "cover_page":  opts["cover_page"],
            "toc":         opts["toc"],
        })
        return url, theme if doc_type == "pdf" else doc_type
    except Exception:
        return None, ""


async def _run_sub_agent(
    agent_id: str,
    task: str,
    user_id: str,
    session_id: int | None,
    visited_agents: frozenset[str] = frozenset(),
) -> str:
    """Run a sub-agent silently and return its final text."""
    sub_def = get_agent(agent_id)
    if not sub_def:
        return f"[Fehler: Unbekannter Agent '{agent_id}']"
    sub_messages = [{"role": "user", "content": task}]
    result_parts: list[str] = []
    async for chunk in _execute_agent(
        sub_def,
        sub_messages,
        user_id=user_id,
        session_id=session_id,
        visited_agents=visited_agents,
    ):
        if chunk.startswith("data: "):
            payload = chunk[6:].strip()
            if payload and payload != "[DONE]":
                try:
                    data = json.loads(payload)
                    if data.get("type") == "content":
                        result_parts.append(data.get("content", ""))
                except (json.JSONDecodeError, ValueError):
                    pass
    return "".join(result_parts) or f"[{agent_id} Agent hat keine Antwort produziert]"


async def _code_dateien(content: str, agent_messages: list[dict], trim, stop_event):
    """Codeblöcke einer Agent-Schlussantwort: prüfen, korrigieren, ablegen.
    Liefert ("sse", ereignis) und zum Schluss ("inhalt", korrigierter Text)."""
    from .. import codepruefung
    from ..arbeitsbereich import ablegen
    auftrag = next((m.get("content") or "" for m in agent_messages if m.get("role") == "user"), "")
    gewuenscht = codepruefung.datei_gewuenscht(auftrag if isinstance(auftrag, str) else "")
    kandidaten = [b for b in codepruefung.bloecke(content) if codepruefung.dateiwuerdig(b, gewuenscht)][:4]
    if not kandidaten:
        yield ("inhalt", content)
        return

    async def nachfragen(text: str) -> str:
        if stop_event and stop_event.is_set():
            raise _Gestoppt
        antwort = await _mit_stopp(_call_llm(
            trim(agent_messages) + [{"role": "assistant", "content": content}, {"role": "user", "content": text}],
            tools=None, brain="big", max_tokens=3000), stop_event)
        return antwort["choices"][0]["message"].get("content") or ""

    neu = content
    for i, b in enumerate(kandidaten):
        name = codepruefung.dateiname_fuer(b, i)
        code, fehler, korrigiert = b.code, None, 0
        async for e in codepruefung.pruefen_und_flicken(b.code, b.sprache, SANDBOX.get(), nachfragen, name):
            if e[0] == "status":
                yield ("sse", _sse({"type": "status", "status": e[1]}))
            else:
                _, code, fehler, korrigiert = e
        if code != b.code:
            neu = neu.replace(b.code, code, 1)
        try:
            # Im Arbeitsordner des Gesprächs UND als Download (seit 2026-10-17):
            # vorher nur als Download — Folge-Agents fanden die Datei nie (Gespräch 580).
            url, name = await ablegen(SANDBOX.get(), code, name)
        except OSError:
            continue
        yield ("sse", _sse({"type": "document", "url": url, "filename": name, "doc_type": name.rsplit(".", 1)[-1],
                            "size": len(code.encode()), "zeilen": code.count("\n") + 1,
                            "geprueft": codepruefung.bericht(fehler, korrigiert, b.sprache)}))
    yield ("inhalt", neu)


async def _execute_agent(
    agent_def: dict,
    messages: list[dict],
    user_id: str = "",
    session_id: int | None = None,
    visited_agents: frozenset[str] = frozenset(),
    stop_event: asyncio.Event | None = None,
    projektwissen: str = "",
) -> AsyncGenerator[str, None]:
    """Core agent execution loop — yields SSE events."""
    brain = agent_def.get("brain", "big")
    agent_id = agent_def["id"]

    # Build system prompt with datetime injection
    now = datetime.now().strftime("%A, %d. %B %Y")
    system_prompt = agent_def["system_prompt"]
    system_prompt += f"\n\nHeutiges Datum: {now}"
    # Cowork: was zum Vorhaben gehoert. Gehoert in den Systemprompt und nicht
    # als zweite Systemnachricht davor — zwei aufeinanderfolgende system-Rollen
    # lehnt die Chatvorlage des Modells mit HTTP 500 ab.
    if projektwissen:
        system_prompt += f"\n\n{projektwissen}"
    if user_id:
        learnings = get_learnings_context(user_id)
        if learnings:
            system_prompt += f"\n\n{learnings}"

    # Inject last document state so model can make precise edits across turns
    if agent_id == "document_write":
        doc_state = _get_doc_state(session_id)
        if doc_state:
            src = doc_state["content"]
            if len(src) > 7000:
                src = src[:7000] + "\n...[Rest gekürzt — vollständig neu schreiben falls nötig]"
            system_prompt += (
                "\n\n══════════════════════════════════════════════════════════\n"
                "AKTUELLES DOKUMENT — Quellcode der letzten Version\n"
                "══════════════════════════════════════════════════════════\n"
                f"Datei: {doc_state['filename']} | Theme: {doc_state['theme']} | "
                f"Layout: {doc_state['layout']} | Header: {doc_state['show_header']} | "
                f"Cover: {doc_state['cover_page']} | Inhaltsverzeichnis: {doc_state.get('toc', False)}\n\n"
                f"{src}\n\n"
                "══════════════════════════════════════════════════════════\n"
                "Wenn der User eine Änderung wünscht: Diesen Quellcode gezielt modifizieren\n"
                "und create_document() mit dem VOLLSTÄNDIG aktualisierten content aufrufen.\n"
                "Unveränderte Abschnitte 1:1 übernehmen."
            )

    # Get tools allowed for this agent. Im Web (Sandkasten, seit 2026-10-16)
    # ohne Shell/SSH/Docker — Dateien und Python laufen im Arbeitsordner.
    sandbox = SANDBOX.get()
    allowed_tool_names = set(agent_def.get("tools", [])) - gesperrte_werkzeuge(sandbox)
    if sandbox is not None and allowed_tool_names & (SANDBOX_WERKZEUGE | {"read_document", "create_document"}):
        # Gleiche Grundausstattung für jeden Agent mit Dateien (seit 2026-10-17):
        # lesen, auflisten, suchen, gezielt ändern, im Browser testen. Vorher
        # konnte z. B. `fehlersuche` Fehler nur finden, nicht beheben, und baute
        # Dateien deshalb komplett neu (Gespräch 580). Alles bleibt im
        # Arbeitsordner dieses Gesprächs.
        allowed_tool_names |= {"read_file", "list_files", "find_files", "str_replace_file", "datei_testen"}
    if sandbox is not None:
        # Kein write_file im Arbeitsordner (seit 2026-10-17): Agents schrieben damit
        # ganze Spiele als Werkzeug-Argument (abgelehnt → alles nochmal als
        # Codeblock) oder stückweise als mario_part1.txt. Neue Dateien kommen als
        # Codeblock mit datei=, Änderungen über str_replace_file, Daten über python_exec.
        allowed_tool_names.discard("write_file")
        # Sandkasten-Beschreibungen (relative Pfade) statt der Serverpfade aus tools.py.
        all_tools_schema = (get_tools_for_agent(allowed_tool_names - SANDBOX_WERKZEUGE)
                            + arbeitsbereich.schemas(sorted(allowed_tool_names & SANDBOX_WERKZEUGE)))
    else:
        all_tools_schema = get_tools_for_agent(allowed_tool_names)
    if sandbox is not None and allowed_tool_names & SANDBOX_WERKZEUGE:
        system_prompt += (
            "\n\nARBEITSORDNER: Alle Dateien dieses Gesprächs liegen in einem eigenen Arbeitsordner — auch was in "
            "früheren Runden entstanden oder hochgeladen worden ist (Liste im Auftrag, sonst list_files). Pfade genau "
            "wie in der Liste angeben, z. B. `spiel.html`; der Server selbst ist nicht zugänglich, Python läuft dort "
            "ohne Internet.\n"
            "- NEUE Datei (Programm, Webseite, Spiel, Skript, Konfiguration, Text): als Codeblock mit Dateinamen in "
            "deine Schlussantwort, z. B. ```html datei=spiel.html — Xera speichert sie im Arbeitsordner, testet sie und "
            "gibt den Link weiter. Ein Werkzeug zum Schreiben ganzer Dateien gibt es hier nicht.\n"
            "- BESTEHENDE Datei ändern: read_file (grosse Dateien abschnittsweise mit offset), dann str_replace_file je "
            "Stelle — mehrere Stellen in EINER Runde (alle Aufrufe gleichzeitig), jeder Aufruf testet automatisch. "
            "Schreib eine bestehende Datei nicht komplett neu.\n"
            "- Testen: datei_testen öffnet HTML in einem echten Browser und bedient es mit Klicks und Tasten. Kein "
            "Nachbau in Python, keine eigene Simulation.\n"
            "- Fehlt eine Datei, die der Auftrag nennt (nicht in der Liste, read_file findet sie nicht): sofort melden "
            "und aufhören — nichts nachbauen, nichts erfinden.\n"
            "Was du speicherst oder mit Python erzeugst, bekommt der Nutzer als Download-Link: übernimm ihn unverändert."
        )

    # Flatten multimodal messages
    flat_messages, image_urls = _flatten_multimodal(messages)
    if image_urls:
        descs = await _describe_images_fast(image_urls)
        img_ctx = "\n\n[Bild-Analyse:\n" + "\n".join(f"Bild {i+1}: {d}" for i, d in enumerate(descs)) + "]"
        if flat_messages and flat_messages[-1]["role"] == "user":
            flat_messages[-1] = {**flat_messages[-1], "content": (flat_messages[-1].get("content", "") or "") + img_ctx}

    agent_messages = [{"role": "system", "content": system_prompt}] + flat_messages

    # Emit agent selected event
    yield _sse({
        "type": "agent_selected",
        "agent_id": agent_id,
        "agent_name": agent_def["name"],
        "agent_icon": agent_def["icon"],
        "agent_color": agent_def.get("color", "#888"),
    })

    max_tokens = agent_def.get("max_tokens", 2048)

    # Bis 2026-10-16 wurden Werkzeug-Ergebnisse hier auf 2 000 Zeichen gekürzt
    # (aus der Zeit mit 16k Kontext). Ein Agent, der eine Datei prüfen sollte,
    # sah nie mehr als den Anfang und meldete „nicht vollständig lesbar“.
    # Ein Slot hat jetzt 64k. Seit 2026-10-17 128k und 60 000 Zeichen: sonst
    # sah ein Agent von einer 19-KB-Spieldatei nur zwei Drittel.
    _MAX_WERKZEUG, _MAX_ASSISTENT = MAX_TOOL_OUTPUT_MODELL, MAX_TOOL_OUTPUT_MODELL

    def _trim_messages(msgs: list[dict]) -> list[dict]:
        """Truncate oversized tool results and assistant content to avoid HTTP 400 context overflow."""
        result = []
        for m in msgs:
            if m.get("role") == "tool":
                try:
                    payload = json.loads(m["content"])
                    out = payload.get("output", "")
                    if isinstance(out, str) and len(out) > _MAX_WERKZEUG:
                        payload["output"] = out[:_MAX_WERKZEUG] + "\n...[gekürzt]"
                        m = {**m, "content": json.dumps(payload, ensure_ascii=False)}
                except Exception:
                    if isinstance(m.get("content"), str) and len(m["content"]) > _MAX_WERKZEUG:
                        m = {**m, "content": m["content"][:_MAX_WERKZEUG] + "\n...[gekürzt]"}
            elif m.get("role") == "assistant" and isinstance(m.get("content"), str) and len(m["content"]) > _MAX_ASSISTENT:
                m = {**m, "content": m["content"][:_MAX_ASSISTENT] + "\n...[gekürzt]"}
            result.append(m)
        return result

    created_doc_this_turn = False
    werkzeug_neu_versucht = False
    # Schlussantwort am Längenlimit abgeschnitten → bis zu 2× weiterschreiben
    # lassen (wie vermittler.py; seit 2026-10-17 auch für Agents).
    fortsetzungen = 0
    teil_vorher = ""
    # Datei verlangt, aber nicht geliefert → einmal nachfragen (seit 2026-10-17).
    datei_nachgefragt = False
    datei_geaendert = False

    for iteration in range(agent_def.get("max_iterations") or MAX_ITERATIONS):
        if stop_event and stop_event.is_set():
            yield _sse({"type": "stopped"})
            return
        yield _sse({"type": "status", "status": "thinking"})

        try:
            fortschritt: dict = {}
            aufgabe = asyncio.ensure_future(_call_llm(
                _trim_messages(agent_messages), tools=all_tools_schema, brain=brain, max_tokens=max_tokens,
                fortschritt=fortschritt))
            stopp_warten = asyncio.ensure_future(stop_event.wait()) if stop_event else None
            letzte_meldung = ""
            try:
                while not aufgabe.done():
                    await asyncio.wait({aufgabe} | ({stopp_warten} if stopp_warten else set()),
                                       timeout=5, return_when=asyncio.FIRST_COMPLETED)
                    if stopp_warten and stopp_warten.done() and not aufgabe.done():
                        aufgabe.cancel()
                        raise _Gestoppt
                    meldung = _fortschritt_text(fortschritt)
                    if meldung and meldung != letzte_meldung and not aufgabe.done():
                        letzte_meldung = meldung
                        yield _sse({"type": "status", "status": meldung})
                response = aufgabe.result()
            finally:
                if stopp_warten:
                    stopp_warten.cancel()
                if not aufgabe.done():  # Generator wurde von aussen geschlossen
                    aufgabe.cancel()
        except _Gestoppt:
            yield _sse({"type": "stopped"})
            return
        except httpx.HTTPStatusError as e:
            # Abgeschnittener Werkzeugaufruf (ganze Datei als Argument, Token-
            # Limit erreicht): llama-server meldet HTTP 500. Einmal mit Hinweis
            # neu versuchen statt aufzugeben (2026-10-15, Agent oberflaechen).
            if e.response.status_code == 500 and "parse tool call" in e.response.text and not werkzeug_neu_versucht:
                werkzeug_neu_versucht = True
                agent_messages.append({"role": "user", "content": (
                    "(System: Dein letzter Werkzeugaufruf war zu lang und ist abgebrochen — das Werkzeug lief nicht. "
                    "Gib grosse Dateien NICHT als Werkzeug-Argument mit: schreib sie als Codeblock mit Dateinamen in deine "
                    "Schlussantwort, z. B. ```html datei=spiel.html — Xera speichert und testet sie.)")})
                yield _sse({"type": "status", "status": "Werkzeugaufruf war zu lang — versucht es anders"})
                continue
            yield _sse({"type": "error", "message": f"LLM-Fehler: HTTP {e.response.status_code}"})
            break
        except Exception as e:
            detail = str(e) or type(e).__name__
            yield _sse({"type": "error", "message": f"Verbindungsfehler: {detail}"})
            break

        choice = response["choices"][0]
        message = choice["message"]
        content = message.get("content", "")
        native_calls = message.get("tool_calls")
        text_calls = _parse_text_tool_calls(content) if not native_calls else None
        is_text_mode = text_calls is not None

        tool_calls = native_calls or text_calls

        if not tool_calls and content and choice.get("finish_reason") == "length" and fortsetzungen < 2:
            fortsetzungen += 1
            teil_vorher += content
            agent_messages.append({"role": "assistant", "content": content})
            agent_messages.append({"role": "user", "content": (
                "(System: Deine Antwort wurde wegen der Längengrenze mitten im Text abgeschnitten. Schreib genau an der "
                "Abbruchstelle weiter — keine Wiederholung, keine Einleitung, kein neuer Codeblock-Anfang. Letzte Zeichen: "
                + json.dumps(content[-80:], ensure_ascii=False) + ")")})
            yield _sse({"type": "status", "status": "Antwort war zu lang — schreibt weiter"})
            continue
        if not tool_calls and teil_vorher:
            content = teil_vorher + (content or "")
            teil_vorher = ""

        if not tool_calls and sandbox is not None and not datei_nachgefragt and not datei_geaendert:
            from .. import codepruefung
            auftrag_text = next((m.get("content") for m in agent_messages if m.get("role") == "user"), "") or ""
            if (isinstance(auftrag_text, str) and codepruefung.datei_gewuenscht(auftrag_text.split("\n---\n")[0])
                    and not codepruefung.bloecke(content or "") and (content or "").count("```") == 0
                    and not await arbeitsbereich.dateiliste(sandbox)):
                # Test 2026-10-17: Agent sollte ein Spiel bauen, meldete aber „kann keine
                # Datei speichern“ — Hauptmodell beauftragte weitere Agents, 47 min.
                datei_nachgefragt = True
                agent_messages.append({"role": "assistant", "content": content or ""})
                agent_messages.append({"role": "user", "content": (
                    "(System: Der Auftrag verlangt eine Datei, aber deine Antwort enthält keinen Codeblock. Schreib die "
                    "vollständige Datei jetzt als Codeblock mit Dateinamen, z. B. ```html datei=spiel.html … ``` — ohne "
                    "Werkzeug; Xera speichert und testet sie.)")})
                yield _sse({"type": "status", "status": "liefert die Datei nach"})
                continue

        if not tool_calls:
            if content and content.count("```") % 2 == 1:
                # Codeblock am Ende nicht geschlossen (Gespräch 580: der Agent hörte
                # nach dem Code einfach auf). Sonst erkennt Xera keine Datei, und das
                # Hauptmodell bekam nur die ersten 6 000 Zeichen Code zu sehen.
                content = content.rstrip() + "\n```"
            if content:
                # Auto-document: if this agent creates docs and the LLM output looks like
                # a markdown document, create the file and emit a download event instead
                # of dumping raw markdown into chat.
                # For document_write: also trigger on substantial text output — Qwen3
                # sometimes ignores the tool-call instruction and outputs plain text.
                # Never trigger if a real create_document tool call already succeeded
                # this turn — otherwise the model's own follow-up confirmation message
                # (Phase 4 template, easily >300 chars) gets mistaken for a second doc.
                _is_doc_agent = agent_def.get("id") == "document_write"
                _auto_doc_trigger = (
                    not created_doc_this_turn
                    and agent_def.get("auto_document")
                    and (
                        _looks_like_document(content)
                        or (_is_doc_agent and len(content.strip()) > 300)
                    )
                )
                if _auto_doc_trigger:
                    doc_url, theme_used = _auto_create_doc(content, agent_messages, session_id=session_id)
                    if doc_url:
                        fname = doc_url.split("/")[-1]
                        actual_doc_type = fname.rsplit(".", 1)[-1] if "." in fname else "pdf"
                        yield _sse({
                            "type": "document",
                            "url": doc_url,
                            "filename": fname,
                            "size": len(content.encode()),
                            "doc_type": actual_doc_type,
                        })
                        display_name = fname.replace('_', ' ')
                        summary_line = _make_summary_line(content)
                        reply = (
                            f"✅ **{display_name}** ist bereit.\n"
                            + (f"📝 *{summary_line}*\n\n" if summary_line else "\n")
                            + "**Anpassen?**\n"
                            "→ Design: `kein header` · `titelseite` · `in blau` / `in dunkel` / `in rot` · `kompakter` / `luftiger`\n"
                            "→ Inhalt: `Titel ändern` · `Tabelle verschieben` · `Abschnitt hinzufügen` · `Einleitung kürzen`"
                        )
                        for ci in range(0, len(reply), 6):
                            yield _sse({"type": "content", "content": reply[ci:ci + 6]})
                            await asyncio.sleep(0.01)
                        break

                if agent_def.get("neubau") or sandbox is not None:
                    # Codeblöcke prüfen, korrigieren lassen, als Datei ablegen
                    # (seit 2026-10-16, codepruefung.py) — statt der alten
                    # _auto_download-Dateien, die die neue Oberfläche nie zeigte.
                    async for art, wert in _code_dateien(content, agent_messages, _trim_messages, stop_event):
                        if art == "sse":
                            yield wert
                        else:
                            content = wert
                    yield _sse({"type": "content", "content": content})
                else:
                    chunk_size = 6 if len(content) < 3000 else 400
                    for ci in range(0, len(content), chunk_size):
                        yield _sse({"type": "content", "content": content[ci:ci + chunk_size]})
                        if chunk_size == 6:
                            await asyncio.sleep(0.012)
                    async for ev in _auto_download(content):
                        yield ev
            break

        # Append assistant message
        if is_text_mode:
            clean = _strip_tool_call_blocks(content)
            agent_messages.append({"role": "assistant", "content": clean or None})
        else:
            agent_messages.append({
                "role": "assistant",
                "content": content or None,
                "tool_calls": native_calls,
            })

        results_for_text_mode: list[str] = []

        for tc in tool_calls:
            func = tc["function"]
            name = func["name"]
            args = _parse_tool_args(func)
            call_id = tc.get("id", f"call_{iteration}_{name}")

            # Hard allowlist check — the schema sent to the LLM already excludes
            # tools this agent isn't permitted, but the text-mode fallback parser
            # accepts hallucinated/free-text tool calls too. Re-check here so an
            # agent can never actually execute a tool outside its declared list
            # (e.g. web_search is restricted to the dedicated Web Search Agent).
            if name not in allowed_tool_names:
                err_msg = f"Tool '{name}' ist für diesen Agent nicht erlaubt."
                yield _sse({"type": "tool_result", "id": call_id, "name": name, "success": False, "output": err_msg})
                if is_text_mode:
                    results_for_text_mode.append(f"[{name} — NICHT ERLAUBT]\n{err_msg}")
                else:
                    agent_messages.append({"role": "tool", "tool_call_id": call_id, "content": json.dumps({"success": False, "output": err_msg}, ensure_ascii=False)})
                continue

            # Sanitize create_document content here too (not just inside docgen's
            # create_document) so the doc_state we persist for cross-turn editing
            # never carries forward a chat-leak/manual-TOC contamination — otherwise
            # the model would copy the dirty text into the next revision's source.
            if name == "create_document" and isinstance(args.get("content"), str):
                from ..docgen import _sanitize_content
                args["content"] = _sanitize_content(args["content"])

            # ── SPECIAL: agent delegation ──────────────────────────────────────
            if name == "delegate_to_agent":
                to_agent_id = args.get("agent_id", "")
                task_text = args.get("task", "")
                context = args.get("context", "")
                full_task = (f"Kontext: {context}\n\n" if context else "") + task_text

                # Cycle detection: refuse if target already in current chain
                if to_agent_id in visited_agents or to_agent_id == agent_id:
                    err_msg = f"Delegation zu '{to_agent_id}' abgelehnt (Cycle erkannt: {' → '.join(sorted(visited_agents))} → {to_agent_id})"
                    yield _sse({"type": "tool_result", "id": call_id, "name": name, "success": False, "output": err_msg})
                    if is_text_mode:
                        results_for_text_mode.append(f"[{name} — CYCLE]\n{err_msg}")
                    else:
                        agent_messages.append({"role": "tool", "tool_call_id": call_id, "content": json.dumps({"success": False, "output": err_msg}, ensure_ascii=False)})
                    continue

                sub_agent_def = get_agent(to_agent_id)
                if not sub_agent_def:
                    err_msg = f"Unbekannter Agent: '{to_agent_id}'"
                    yield _sse({"type": "tool_result", "id": call_id, "name": name, "success": False, "output": err_msg})
                    if is_text_mode:
                        results_for_text_mode.append(f"[{name} — FEHLER]\n{err_msg}")
                    else:
                        agent_messages.append({"role": "tool", "tool_call_id": call_id, "content": json.dumps({"success": False, "output": err_msg}, ensure_ascii=False)})
                    continue

                yield _sse({"type": "tool_call", "id": call_id, "name": name, "args": args, "level": "READ"})
                yield _sse({
                    "type": "agent_delegating",
                    "from_agent": agent_id,
                    "from_name": agent_def["name"],
                    "to_agent": to_agent_id,
                    "to_name": sub_agent_def["name"],
                    "task": task_text[:150],
                })

                # Pass the current agent chain to prevent cycles in sub-agent
                new_visited = visited_agents | {agent_id}
                sub_result = await _run_sub_agent(to_agent_id, full_task, user_id, session_id, new_visited)

                short_preview = sub_result[:300] + ("..." if len(sub_result) > 300 else "")
                yield _sse({"type": "tool_result", "id": call_id, "name": name, "success": True, "output": short_preview})

                result_payload = {"success": True, "output": sub_result}
                if is_text_mode:
                    results_for_text_mode.append(f"[{to_agent_id} Agent — ANTWORT]\n{sub_result}")
                else:
                    agent_messages.append({"role": "tool", "tool_call_id": call_id, "content": json.dumps(result_payload, ensure_ascii=False)})
                continue

            # ── PERMISSION CHECK ───────────────────────────────────────────────
            level = classify_tool(name, args)
            if sandbox is not None and name in SANDBOX_WERKZEUGE:
                level = "read"  # läuft im Sandkasten des Nutzers (arbeitsbereich.py)
            elif sandbox is not None and level in ("write", "admin") and not name.startswith("memory_"):
                # Im Web gibt es keine Freigabe für Eingriffe am Server: der
                # Nutzer würde sie sich selbst erteilen (z. B. web_fetch auf
                # http://127.0.0.1:8000/api/internal/…).
                level = "blocked"

            if is_blocked(level):
                result = {"success": False, "output": "Blocked: Diese Aktion ist nicht erlaubt."}
                log_action(user_id, session_id, name, args, level, False, "blocked")
                yield _sse({"type": "tool_call", "id": call_id, "name": name, "args": args, "level": "blocked"})
                yield _sse({"type": "tool_result", "id": call_id, "name": name, "success": False, "output": result["output"]})
                if is_text_mode:
                    results_for_text_mode.append(f"[{name} — BLOCKED]\n{result['output']}")
                else:
                    agent_messages.append({"role": "tool", "tool_call_id": call_id, "content": json.dumps(result, ensure_ascii=False)})
                continue

            if needs_approval(level):
                action_id = str(uuid4())
                yield _sse({
                    "type": "approval_required",
                    "id": call_id,
                    "action_id": action_id,
                    "name": name,
                    "args": args,
                    "level": level_label(level),
                })
                event = create_approval(action_id)
                try:
                    await asyncio.wait_for(event.wait(), timeout=APPROVAL_TIMEOUT)
                    approved = get_approval_result(action_id)
                except asyncio.TimeoutError:
                    approved = False
                finally:
                    cleanup_approval(action_id)

                if not approved:
                    result = {"success": False, "output": "Aktion vom Benutzer abgelehnt."}
                    log_action(user_id, session_id, name, args, level, False, "denied")
                    yield _sse({"type": "tool_result", "id": call_id, "name": name, "success": False, "output": result["output"], "denied": True})
                    if is_text_mode:
                        results_for_text_mode.append(f"[{name} — ABGELEHNT]\n{result['output']}")
                    else:
                        agent_messages.append({"role": "tool", "tool_call_id": call_id, "content": json.dumps(result, ensure_ascii=False)})
                    continue

            # ── EXECUTE ────────────────────────────────────────────────────────
            yield _sse({"type": "tool_call", "id": call_id, "name": name, "args": args, "level": level_label(level)})
            result = await execute_tool(name, args)
            log_action(user_id, session_id, name, args, level, True, result.get("output", "")[:200])
            if result.get("success") and name in ("str_replace_file", "create_document", "python_exec"):
                datei_geaendert = True

            # Persist doc state so model can edit it in the next turn, and emit a
            # "document" event so the chat ALWAYS shows a download card — regardless
            # of whether the model called the tool correctly or the auto-doc fallback
            # kicked in (those two paths used to diverge: only the fallback emitted it).
            if name == "create_document" and result.get("success"):
                created_doc_this_turn = True
                _store_doc_state(session_id, {
                    "content":     args.get("content", ""),
                    "filename":    args.get("filename", "dokument"),
                    "theme":       args.get("theme", "purple"),
                    "layout":      args.get("layout", "normal"),
                    "show_header": args.get("show_header", True),
                    "cover_page":  args.get("cover_page", False),
                    "toc":         args.get("toc", False),
                })
                dl_match = re.search(r'/api/download/([^\)\s]+)', result.get("output", ""))
                if dl_match:
                    doc_url = f"/api/download/{dl_match.group(1)}"
                    fname = dl_match.group(1)
                    actual_doc_type = fname.rsplit(".", 1)[-1] if "." in fname else "pdf"
                    yield _sse({
                        "type": "document",
                        "url": doc_url,
                        "filename": fname,
                        "size": len(args.get("content", "").encode()),
                        "doc_type": actual_doc_type,
                    })
                    if sandbox is not None:
                        # Auch in den Arbeitsordner: eine Folgefrage („füge eine Spalte
                        # hinzu“) findet die Datei sonst nicht (seit 2026-10-17).
                        await arbeitsbereich.download_uebernehmen(sandbox, doc_url)

            output = result.get("output", "")
            if len(output) > MAX_TOOL_OUTPUT_MODELL:
                output = output[:MAX_TOOL_OUTPUT_MODELL] + f"\n[... {len(output)} Zeichen, gekuerzt]"
                result = {**result, "output": output}
            ausgabe_ui = output if len(output) <= MAX_TOOL_OUTPUT else output[:MAX_TOOL_OUTPUT] + "\n[…]"

            yield _sse({"type": "tool_result", "id": call_id, "name": name, "success": result["success"], "output": ausgabe_ui})

            if is_text_mode:
                status = "OK" if result["success"] else "FEHLER"
                results_for_text_mode.append(f"[{name} — {status}]\n{output}")
            else:
                agent_messages.append({"role": "tool", "tool_call_id": call_id, "content": json.dumps(result, ensure_ascii=False)})

        if is_text_mode and results_for_text_mode:
            agent_messages.append({
                "role": "user",
                "content": "Tool-Ergebnisse:\n\n" + "\n\n---\n\n".join(results_for_text_mode),
            })

    else:
        # Seit 2026-10-02: Statt mit leeren Haenden abzubrechen, eine
        # Schlussantwort ohne Werkzeuge verlangen. Qwen3.8 sammelt gruendlich
        # (Recherche: 14 Aufrufe) und kam vorher nie bis zur Antwort.
        yield _sse({"type": "status", "status": "fasst zusammen"})
        try:
            # Werkzeuge bleiben im Prompt, nur Aufrufe sind aus (seit 2026-10-17):
            # ohne sie änderte sich der Prompt-Anfang, llama-server las den ganzen
            # Agent-Verlauf neu ein, und unter Last lief die Anfrage ins Zeitlimit
            # (Mario v5a: „Maximale Tool-Iterationen erreicht“, keine Datei). Gestreamt,
            # damit das Zeitlimit pro Stück gilt und nicht für die ganze Antwort.
            schluss = await _mit_stopp(_call_llm(
                _trim_messages(agent_messages) + [{
                    "role": "user",
                    "content": "Keine weiteren Werkzeuge. Beantworte die urspruengliche Frage jetzt "
                               "mit dem, was du gesammelt hast. Nenne Quellen, wenn du welche hast. "
                               "Verlangt der Auftrag eine Datei, die noch nicht im Arbeitsordner liegt: "
                               "schreib sie vollständig als Codeblock mit Dateinamen.",
                }],
                tools=all_tools_schema, tool_choice="none", brain=brain, max_tokens=max_tokens,
                fortschritt={},
            ), stop_event)
            text = (schluss["choices"][0]["message"].get("content") or "").strip()
        except _Gestoppt:
            yield _sse({"type": "stopped"})
            return
        except Exception as e:
            text = ""
            import logging; logging.getLogger(__name__).warning("Schlussantwort fehlgeschlagen: %s", e)
        if text and (agent_def.get("neubau") or sandbox is not None):
            # Wie die normale Schlussantwort: Codeblock → Datei im Arbeitsordner, getestet.
            async for art, wert in _code_dateien(text, agent_messages, _trim_messages, stop_event):
                if art == "sse":
                    yield wert
                else:
                    text = wert
            yield _sse({"type": "content", "content": text})
        elif text:
            for ci in range(0, len(text), 6):
                yield _sse({"type": "content", "content": text[ci:ci + 6]})
                await asyncio.sleep(0.012)
        else:
            yield _sse({"type": "error", "message": "Maximale Tool-Iterationen erreicht"})

    yield "data: [DONE]\n\n"


async def run_multi_agent(
    messages: list[dict],
    mode: str = "homelab",
    user_id: str = "",
    session_id: int | None = None,
    brain_override: str | None = None,
    agent_id: str | None = None,
    stop_event: asyncio.Event | None = None,
    projektwissen: str = "",
) -> AsyncGenerator[str, None]:
    """
    Main entry point. Runs one or multiple agents (parallel when detected).
    """
    if agent_id and agent_id in AGENTS:
        agent_ids = [agent_id]
    else:
        tab = "homelab" if mode == "homelab" else "chat"
        agent_ids = select_agents(messages, tab=tab)

    if not agent_ids:
        return

    if len(agent_ids) == 1:
        # Single agent — stream directly
        agent_def = AGENTS[agent_ids[0]]
        if brain_override in ("big", "fast", "code", "denken"):
            agent_def = {**agent_def, "brain": brain_override}
        async for event in _execute_agent(
            agent_def, messages,
            user_id=user_id, session_id=session_id, visited_agents=frozenset(),
            stop_event=stop_event,
            projektwissen=projektwissen,
        ):
            yield event
        return

    # Parallel agents — collect both into queues and interleave output
    queues: list[asyncio.Queue] = [asyncio.Queue() for _ in agent_ids]
    _SENTINEL = object()

    async def _feed(agent_def: dict, q: asyncio.Queue):
        async for event in _execute_agent(
            agent_def, messages,
            user_id=user_id, session_id=session_id, visited_agents=frozenset(),
            stop_event=stop_event,
            projektwissen=projektwissen,
        ):
            await q.put(event)
        await q.put(_SENTINEL)

    agent_defs = []
    for aid in agent_ids:
        ad = AGENTS[aid]
        if brain_override in ("big", "fast", "code", "denken"):
            ad = {**ad, "brain": brain_override}
        agent_defs.append(ad)

    # Announce parallel mode via structured event (UI renders it)
    yield _sse({
        "type": "parallel_start",
        "agents": [
            {"id": a["id"], "name": a["name"], "icon": a["icon"], "color": a.get("color", "#888")}
            for a in agent_defs
        ],
    })

    tasks = [asyncio.create_task(_feed(ad, q)) for ad, q in zip(agent_defs, queues)]
    done_count = 0
    total = len(queues)

    while done_count < total:
        for i, q in enumerate(queues):
            try:
                item = q.get_nowait()
                if item is _SENTINEL:
                    done_count += 1
                else:
                    yield item
            except asyncio.QueueEmpty:
                pass
        await asyncio.sleep(0.005)

    for t in tasks:
        await t

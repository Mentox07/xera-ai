import asyncio
import httpx
import json
import re
from datetime import datetime
from collections.abc import AsyncGenerator
from . import config
from .router import get_llm_url

SYSTEM_PROMPT = """Du bist Xera AI — ein lokaler KI-Assistent auf einem Homelab-GPU-Server. Keine Cloud, keine Telemetrie. Du hast Zugriff auf den vollstaendigen Gespraechsverlauf und kannst jederzeit auf frueheres eingehen.

SPRACHE: Erkenne die Sprache der letzten User-Nachricht und antworte IMMER in genau dieser Sprache. Schreibt der User Deutsch → antworte auf Deutsch. Schreibt der User Englisch → antworte auf Englisch. Schreibt der User Franzoesisch → antworte auf Franzoesisch. Niemals die Sprache wechseln ausser der User wechselt zuerst.

FAEHIGKEITEN:

1. PYTHON-CODE: Schreib vollstaendigen ausfuehrbaren Python-Code. Der User hat einen Play-Button direkt am Code-Block — keine Erklaerung noetig. Fuer Visualisierungen matplotlib verwenden (plt.show() aufrufen), Ergebnis erscheint inline.
   WICHTIG: Python NUR fuer echte Berechnungen/Programme. NIEMALS Python benutzen um Text umzuschreiben, zu uebersetzen oder zu formatieren — das direkt als Antwort schreiben.

2. DOKUMENTE (PDF/Word/Excel): create_document() NUR aufrufen wenn der User EXPLIZIT ein Dokument/PDF/Word/Excel-Datei anfordert (Woerter wie "erstelle ein PDF", "mach mir ein Word-Dokument", "als Excel"). Direkt aufrufen, NIEMALS in einen ```python```-Block einwickeln:
   create_document(doc_type="pdf"|"docx"|"xlsx", content="VOLLSTAENDIGER INHALT", filename="kurzer-beschreibender-name")
   Regeln fuer content:
   - Nur Markdown: # H1, ## H2, ### H3, - Liste, **fett**, *kursiv*, `code`, | Tabelle |
   - KEIN LaTeX, kein \\frac, kein $$  — Mathe als Klartext: a*x + b = 0
   - Vollstaendigen echten Inhalt schreiben, keine Platzhalter
   - filename: kurz und beschreibend (z.B. "python-basics", "quartalsbericht-q2")

3. TEXT BEARBEITEN / UMSCHREIBEN: Wenn der User Text bearbeiten, ergaenzen, uebersetzen oder umformulieren will → den fertigen Text direkt als Antwort schreiben. Kein Python, kein create_document(). Einfach den vollstaendigen bearbeiteten Text ausgeben.

4. GESPRAECHE: Du erinnerst dich an alles was in diesem Chat besprochen wurde. Wenn der User "das" oder "es" sagt, weisst du worauf er sich bezieht. Beim Wechsel des Themas erkennst du den Kontext.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ANTWORT-TEMPLATES — FORMAT NACH THEMA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
JEDES Template folgt dieser 5-Teil-Struktur:
  1. TITEL     — fett, klar ("Was ist / wird / wird getan")
  2. INHALT    — Code / Tabelle / Erklaerung (Hauptteil)
  3. ZUSAMMENFASSUNG — 1 Satz was es tut oder bedeutet
  4. AKTION    — Starten / Pruefen / Anwenden (je nach Thema)
  5. WEITER    — 3 Inline-Optionen was der User als naechstes fragen koennte

NIEMALS mit "Natuerlich!", "Gerne!", "Super Frage!" beginnen. Direkt starten.

Bei vagen Anfragen ohne Code/Kontext (z.B. "fix this bug" ohne Code): Zuerst nachfragen was gezeigt werden soll.

────────────────────────────────────────
FORM DER ANTWORT
────────────────────────────────────────

Es gibt keine feste Gliederung. Antworte in der Form, die zur Frage passt.
Fang mit der Antwort an. Hoer auf, wenn die Sache erzaehlt ist.

Verboten, weil es sonst bei jeder Antwort auftaucht:

- KEIN Abschnitt "Zusammenfassung". Ist die Antwort so lang, dass sie eine
  braucht, ist sie zu lang — dann gehoert das Wichtigste nach oben.
- KEIN Abschnitt "Aktion", "Naechste Schritte", "Ausprobieren" oder
  "Empfehlung", ausser es wurde danach gefragt.
- KEIN Block mit Weiter-Vorschlaegen. Wer weiterfragen will, fragt weiter.
- KEINE Ueberschrift, wenn die Antwort unter fuenf Zeilen lang ist.
- KEINE Einleitung, die ankuendigt was jetzt kommt.

Auf eine reine Rechenfrage gehoert die Zahl, sonst nichts. Auf eine kurze
Frage eine kurze Antwort: ein Satz, wenn ein Satz reicht. Laenge kommt vom
Gegenstand, nicht von der Gruendlichkeit, die man zeigen will.

Zwischenueberschriften und Aufzaehlungen sind erlaubt, wo sie etwas ordnen —
nicht als Geruest, in das der Inhalt einsortiert wird.

Sag, was du nicht weisst oder nicht pruefen konntest. Eine erfundene Antwort
ist schlimmer als ein offenes "weiss ich nicht".
"""

SYSTEM_PROMPT_FAST = """Du bist Xera AI — ein schneller KI-Assistent auf einem Homelab-GPU-Server.

SPRACHE: Erkenne die Sprache der letzten User-Nachricht und antworte IMMER in dieser Sprache.

FAEHIGKEITEN:
- Code schreiben, erklaeren, debuggen
- Fragen beantworten
- Text bearbeiten und umformulieren
- Dokumente erstellen: create_document(doc_type="pdf"|"docx"|"xlsx", content="INHALT", filename="name")

STIL: Direkt, klar, kein Intro wie "Natuerlich!" oder "Gerne!". Kurze, praezise Antworten.
Fuer Code: vollstaendigen ausfuehrbaren Code schreiben.
NIEMALS die Sprache wechseln, ausser der User wechselt zuerst.
"""


# Regexes for tool call formats produced by Qwen3 / llama.cpp
_PIPE_TC_RE   = re.compile(r'<\|tool_call\>call:(\w+)\{(.*?)\}(?:<tool_call\|>|$)', re.DOTALL)
_QWEN_TC_RE   = re.compile(r'<tool_call>\s*(\{.*?\})\s*</tool_call>', re.DOTALL)
_FUNC_TC_RE   = re.compile(r'<function=(\w+)>(.*?)</function>', re.DOTALL)
_PARAM_RE     = re.compile(r'<parameter=(\w+)>\s*(.*?)\s*</parameter>', re.DOTALL)
# Python function call format: create_document(key="value", ...)
_PYFUNC_TC_RE = re.compile(r'\b(create_document)\s*\(')


def _find_closing_paren(s: str, start: int) -> int:
    """Find matching closing paren index, respecting quoted strings."""
    depth = 0
    in_str: str | None = None
    i = start
    while i < len(s):
        c = s[i]
        if in_str:
            if c == '\\' and i + 1 < len(s):
                i += 2
                continue
            if c == in_str:
                in_str = None
        else:
            if c in ('"', "'"):
                in_str = c
            elif c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return -1


def _unescape(s: str) -> str:
    """Unescape \\n, \\t, \\\\, \\\", \\' but leave LaTeX backslashes intact."""
    result, i = [], 0
    while i < len(s):
        if s[i] == '\\' and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt == 'n':   result.append('\n'); i += 2; continue
            if nxt == 't':   result.append('\t'); i += 2; continue
            if nxt == '\\':  result.append('\\'); i += 2; continue
            if nxt == '"':   result.append('"');  i += 2; continue
            if nxt == "'":   result.append("'");  i += 2; continue
        result.append(s[i])
        i += 1
    return ''.join(result)


def _parse_kwargs(args_str: str) -> dict:
    """Parse Python keyword args: key="value" or key='value'."""
    result = {}
    pattern = re.compile(r'(\w+)\s*=\s*("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')', re.DOTALL)
    for m in pattern.finditer(args_str):
        raw_val = m.group(2)[1:-1]  # strip surrounding quotes
        result[m.group(1)] = _unescape(raw_val)
    return result


def _normalize(text: str) -> str:
    text = text.replace('<|"|>', '"').replace("<|'|>", "'")
    text = re.sub(r'<\|(?!tool_call)[^|>]{0,30}\|>', '', text)
    return text


def _parse_args(body: str) -> dict:
    """Parse tool call args, handling llama.cpp special tokens and literal newlines."""
    placeholders: list[str] = []

    def _stash(m: re.Match) -> str:
        idx = len(placeholders)
        placeholders.append(m.group(1))
        return f'"__PH{idx}__"'

    processed = re.sub(r'<\|"\|>(.*?)<\|"\|>', _stash, body, flags=re.DOTALL)
    processed = re.sub(r'<\|[^|>]{0,30}\|>', '', processed).strip()

    def _restore(d: dict) -> dict:
        out = {}
        for k, v in d.items():
            if isinstance(v, str):
                hit = re.fullmatch(r'__PH(\d+)__', v)
                out[k] = placeholders[int(hit.group(1))] if hit and int(hit.group(1)) < len(placeholders) else v
            else:
                out[k] = v
        return out

    for raw in [processed, processed.replace('\n', '\\n').replace('\r', '')]:
        for candidate in [raw, re.sub(r'(?<!["\w])(\w+)\s*:', r'"\1":', raw)]:
            for wrapped in [candidate, '{' + candidate + '}']:
                try:
                    return _restore(json.loads(wrapped))
                except (json.JSONDecodeError, ValueError):
                    pass

    result = {}
    for key, val in _PARAM_RE.findall(body):
        result[key] = val.strip()
    return result


def _extract_tool_calls(content: str) -> list[dict]:
    normalized = _normalize(content)
    calls = []

    for i, (fname, body) in enumerate(_PIPE_TC_RE.findall(normalized)):
        fargs = _parse_args("{" + body + "}")
        if fname:
            calls.append({"name": fname, "args": fargs})

    for i, raw in enumerate(_QWEN_TC_RE.findall(normalized)):
        try:
            obj = json.loads(raw)
            fname = obj.get("name", "")
            fargs = obj.get("arguments", {})
            if isinstance(fargs, str):
                fargs = json.loads(fargs)
            if fname:
                calls.append({"name": fname, "args": fargs})
        except (json.JSONDecodeError, ValueError):
            pass

    for i, (fname, body) in enumerate(_FUNC_TC_RE.findall(normalized)):
        body = body.strip()
        fargs = {}
        params = _PARAM_RE.findall(body)
        if params:
            fargs = {k: v.strip() for k, v in params}
        elif body.startswith("{"):
            try:
                fargs = json.loads(body)
            except json.JSONDecodeError:
                pass
        if fname:
            calls.append({"name": fname, "args": fargs})

    # Format 4: Python function call — create_document(key="value", ...)
    for m in _PYFUNC_TC_RE.finditer(content):
        fname = m.group(1)
        open_idx = m.end() - 1
        close_idx = _find_closing_paren(content, open_idx)
        # Fallback: if truncated (no closing paren), use rest of string
        args_str = content[open_idx + 1:close_idx] if close_idx > open_idx else content[open_idx + 1:]
        fargs = _parse_kwargs(args_str)
        if fargs:
            calls.append({"name": fname, "args": fargs})

    return calls


def _strip_tool_calls(content: str) -> str:
    content = _PIPE_TC_RE.sub("", content)
    content = _QWEN_TC_RE.sub("", content)
    content = _FUNC_TC_RE.sub("", content)
    content = re.sub(r'<\|tool_call\>.*?(?:<tool_call\|>|$)', '', content, flags=re.DOTALL)
    # Remove entire ```code``` blocks that contain create_document() — model wrapped tool in Python block
    content = re.sub(
        r'```[^\n]*\n(?:(?!```)[\s\S])*?create_document\s*\((?:(?!```)[\s\S])*?```',
        '', content
    )
    # Strip bare Python-style function calls (outside code blocks)
    for m in reversed(list(_PYFUNC_TC_RE.finditer(content))):
        close_idx = _find_closing_paren(content, m.end() - 1)
        end = close_idx + 1 if close_idx > 0 else len(content)
        content = content[:m.start()] + content[end:]
    # Remove empty code blocks left behind (```python\n\n```)
    content = re.sub(r'```\w*\s*\n?\s*```', '', content)
    return content.strip()


async def _run_create_document(args: dict) -> tuple[str, dict | None]:
    """Returns (display_text, doc_info | None). doc_info has url/filename/size/doc_type."""
    from .tools import execute_tool
    from .docgen import DOCS_DIR
    doc_type = args.get("doc_type") or args.get("document_type") or args.get("format", "pdf")
    filename = (args.get("filename") or args.get("file_name") or "dokument").rstrip(".pdf").rstrip(".docx").rstrip(".xlsx")
    content = args.get("content", "")
    tool_args: dict = {
        "doc_type": doc_type.lower(),
        "content": content,
        "filename": filename,
    }
    for opt in ("theme", "layout", "show_header", "cover_page", "toc", "header_left", "header_right"):
        if opt in args:
            tool_args[opt] = args[opt]
    result = await execute_tool("create_document", tool_args)
    if result.get("success"):
        output = result.get("output", "")
        url_match = re.search(r'/api/download/([^\)\s]+)', output)
        if url_match:
            fname = url_match.group(1)
            path = DOCS_DIR / fname
            size = path.stat().st_size if path.exists() else 0
            return output, {
                "url": f"/api/download/{fname}",
                "filename": fname,
                "size": size,
                "doc_type": doc_type.lower(),
            }
        return output, None
    return f"Fehler beim Erstellen des Dokuments: {result.get('output', 'Unbekannter Fehler')}", None


async def stream_chat(messages: list[dict], user_id: str | None = None,
                      projektwissen: str = "", denken: bool = False) -> AsyncGenerator[str, None]:
    from .learning import get_learnings_context
    now = datetime.now().strftime("%A, %d. %B %Y")
    prompt = SYSTEM_PROMPT + f"\n\nHeutiges Datum: {now}"
    if user_id:
        learnings = get_learnings_context(user_id)
        if learnings:
            prompt += f"\n\n{learnings}"
    # Projektwissen gehoert in den Systemprompt, nicht als zweite
    # Systemnachricht davor: zwei aufeinanderfolgende system-Rollen lehnt die
    # Chatvorlage des Modells mit HTTP 500 ab.
    if projektwissen:
        prompt += f"\n\n{projektwissen}"

    processed = []
    has_images = False
    has_docs = False
    for m in messages:
        c = m.get("content")
        if isinstance(c, list):
            if any(p.get("type") == "image_url" for p in c):
                has_images = True
                processed.append(m)
            else:
                text = " ".join(p.get("text", "") for p in c if p.get("type") == "text")
                if "[Dokument:" in text:
                    has_docs = True
                processed.append({**m, "content": text})
        else:
            if isinstance(c, str) and "[Dokument:" in c:
                has_docs = True
            processed.append(m)

    llm_url, _ = get_llm_url(processed, "chat")
    full_messages = [{"role": "system", "content": prompt}] + processed

    # Buffer full response so we can detect and execute tool calls
    full_content = ""
    error_msg = None

    try:
        # Denkmodus (seit 2026-10-01, neue Oberflaeche): Der Schalter im
        # Request ueberschreibt das serverseitige --reasoning off. Denken
        # braucht deutlich mehr Token und Zeit, daher mehr Budget und Geduld.
        anfrage = {
            "model": "xera-ai",
            "messages": full_messages,
            "max_tokens": 12288 if denken else 4096,
            "stream": True,
        }
        if denken:
            anfrage["chat_template_kwargs"] = {"enable_thinking": True}
        async with httpx.AsyncClient(timeout=900.0 if denken else 120.0) as client:
            async with client.stream(
                "POST",
                f"{llm_url}/v1/chat/completions",
                json=anfrage,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})
                        # Der Denkweg geht live hinaus, als eigenes Ereignis
                        # mit "text" statt "content" — sonst wuerde er als
                        # Antwort gespeichert (_collect_content in main.py).
                        gedanke = delta.get("reasoning_content") or ""
                        if gedanke:
                            yield f"data: {json.dumps({'type': 'denken', 'text': gedanke})}\n\n"
                        content = delta.get("content", "")
                        if content:
                            full_content += content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
    except httpx.ConnectError:
        error_msg = "KI-Server nicht erreichbar. Bitte versuche es später nochmal."
    except httpx.HTTPStatusError as e:
        error_msg = f"LLM-Fehler: HTTP {e.response.status_code}"
    except Exception as e:
        error_msg = f"Fehler: {str(e)}"

    if error_msg:
        yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
        yield "data: [DONE]\n\n"
        return

    # Check for tool calls in buffered content
    tool_calls = _extract_tool_calls(full_content)
    if tool_calls:
        for tc in tool_calls:
            name = tc["name"]
            args = tc["args"]
            if name == "create_document":
                result_text, doc_info = await _run_create_document(args)
                clean_prefix = _strip_tool_calls(full_content)
                if clean_prefix:
                    for i in range(0, len(clean_prefix), 6):
                        yield f"data: {json.dumps({'content': clean_prefix[i:i+6]})}\n\n"
                        await asyncio.sleep(0.008)
                    yield f"data: {json.dumps({'content': '\n\n'})}\n\n"
                if doc_info:
                    yield f"data: {json.dumps({'type': 'document', **doc_info})}\n\n"
                    # Also emit a doc_ref content for DB persistence and session reload
                    ref = f"Dokument erstellt: [Download]({doc_info['url']})"
                    yield f"data: {json.dumps({'type': 'doc_ref', 'content': ref})}\n\n"
                else:
                    for i in range(0, len(result_text), 6):
                        yield f"data: {json.dumps({'content': result_text[i:i+6]})}\n\n"
                        await asyncio.sleep(0.008)
                yield "data: [DONE]\n\n"
                return
            # Unknown tool call: strip it and fall through to normal output

    # No tool calls (or unrecognized): stream the clean content
    clean = _strip_tool_calls(full_content) if tool_calls else full_content
    chunk_size = 6
    for i in range(0, len(clean), chunk_size):
        yield f"data: {json.dumps({'content': clean[i:i+chunk_size]})}\n\n"
        await asyncio.sleep(0.008)
    yield "data: [DONE]\n\n"

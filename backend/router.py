import re
from . import config

COMPLEX_PATTERNS = [
    r'\b(code|script|programm|funktion|class|def |import |api|debug|fehler|error|bug|fix)\b',
    r'\b(erkl[aä]r|analys|vergleich|unterschied|warum|wieso|weshalb)\b.{20,}',
    r'\b(config|konfigur|setup|install|deploy|docker|proxmox|firewall|vlan|ssh|nginx|caddy)\b',
    r'\b(sql|json|yaml|xml|html|css|python|javascript|bash|regex)\b',
    r'```',
    r'\b(schreib|erstell|bau|implementier|refactor)\b.*\b(script|code|datei|funktion|tool)\b',
    r'\b(pdf|docx|xlsx|dokument|document)\b',
]

# Pattern that forces Big Brain immediately (documents, analysis, long questions)
_FORCE_BIG_RE = re.compile(
    r'\b(pdf|docx|xlsx)\b|'
    r'(mach|erstell|generier|schreib|bau).*\b(pdf|dokument|document)\b|'
    r'\b(bericht|zusammenfassung|erkl[aä]rung|analyse|tabelle)\b.*\b(pdf|docx|xlsx|erstell|schreib|mach)\b',
    re.IGNORECASE | re.DOTALL,
)

SIMPLE_PATTERNS = [
    r'^(hi|hallo|hey|moin|servus|guten\s*(morgen|tag|abend))[\s!.?]*$',
    r'^(danke|thx|thanks|cool|ok|gut|super|perfekt|alles\s*klar)[\s!.?]*$',
    r'^was\s+ist\s+\d+\s*[\+\-\*\/]\s*\d+',
    r'^(wer|was|wo|wann|wie)\s+(bist|heisst|ist)\s+(du|das|es)',
    r'^(welch|was\s+für\s+ein).{0,30}\?([\s]*)$',
    r'^übersetze?\b',
]

_complex_re = [re.compile(p, re.IGNORECASE) for p in COMPLEX_PATTERNS]
_simple_re = [re.compile(p, re.IGNORECASE) for p in SIMPLE_PATTERNS]


def classify_complexity(messages: list[dict]) -> str:
    last_msg = ""
    for m in reversed(messages):
        if m["role"] == "user":
            c = m.get("content", "")
            if isinstance(c, list):
                last_msg = " ".join(p.get("text", "") for p in c if p.get("type") == "text")
            else:
                last_msg = c or ""
            break
    if not last_msg:
        return "big"

    # Documents always need Big Brain
    if _FORCE_BIG_RE.search(last_msg):
        return "big"

    # Mid-conversation: once AI has responded, stay with Big Brain for context
    has_prior_ai = any(m.get("role") == "assistant" for m in messages[:-1] if isinstance(m, dict))
    if has_prior_ai:
        return "big"

    if len(last_msg) > 300:
        return "big"

    for pat in _simple_re:
        if pat.search(last_msg):
            return "fast"

    for pat in _complex_re:
        if pat.search(last_msg):
            return "big"

    if len(last_msg) < 80:
        return "fast"

    return "big"


def get_llm_url(messages: list[dict], mode: str, brain_override: str | None = None) -> tuple[str, str]:
    if mode in ("agents", "homelab"):
        return config.LLAMA_API_URL, "big"

    if brain_override in ("big", "fast", "code"):
        if brain_override == "fast":
            return config.LLAMA_FAST_URL, "fast"
        if brain_override == "code":
            return config.LLAMA_CODE_URL, "code"
        return config.LLAMA_API_URL, "big"

    brain = classify_complexity(messages)
    if brain == "fast":
        return config.LLAMA_FAST_URL, "fast"
    return config.LLAMA_API_URL, "big"

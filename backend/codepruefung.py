"""Code aus Antworten als Datei ablegen, automatisch prüfen, Fehler korrigieren
lassen (seit 2026-10-16).

Anlass Chat 512: Xera schrieb ein Mario-Spiel als HTML, das beim ersten Frame
mit ``ReferenceError: h is not defined`` stehen blieb — eine Variable ausserhalb
ihres Blocks. Niemand hatte die Seite je geladen. Und die Datei, die der
Nutzer wollte, gab es gar nicht: das Modell schrieb „liegt bei dir im
Verzeichnis“, obwohl nichts erzeugt worden war.

Jetzt:

* **Datei aus Codeblock.** Ein Codeblock mit Dateinamen (```` ```html
  datei=spiel.html ````) oder ein ganzes Programm (ab ``MIN_ZEILEN``) wird als
  Download abgelegt. Grosse Dateien müssen damit nicht mehr als JSON-Argument
  eines Werkzeugaufrufs durch llama-server — genau daran scheiterten im Chat
  512 zweimal 16 Minuten Arbeit (HTTP 500 „Failed to parse tool call“).
* **Prüfen.** HTML mit Skript wird headless in Chromium geladen (im
  Sandkasten, ohne Netz), mit ein paar Klicks und Tasten, damit auch die
  Spielschleife läuft. Python, JavaScript, JSON und Shell werden auf Syntax
  geprüft — nur geparst, nie ausgeführt.
* **Korrigieren.** Findet die Prüfung Fehler, schreibt das Modell nur die
  Korrektur als SUCHEN/ERSETZEN-Blöcke (ein paar hundert Tokens statt die
  ganze Datei neu). Xera setzt sie ein und prüft nochmal, höchstens
  ``RUNDEN``-mal.
"""

from __future__ import annotations

import ast
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import AsyncGenerator, Awaitable, Callable

from . import arbeitsbereich

_log = logging.getLogger(__name__)

NODE = "/opt/build/node22/bin/node"
PLAYWRIGHT_MODULE = "/opt/build/shots/node_modules"
PLAYWRIGHT_BROWSER = "/opt/xera-pw"
PRUEFSKRIPT = Path(__file__).with_name("html_pruefen.cjs")

MIN_ZEILEN = 60        # ab so vielen Zeilen ist ein Codeblock ein Programm → Datei
MIN_ZEILEN_WUNSCH = 8  # wenn der Nutzer ausdrücklich eine Datei will
RUNDEN = 2             # Korrekturrunden

_BLOCK_RE = re.compile(r"```([^\n`]*)\n(.*?)\n?```", re.S)
_ENDUNG = {
    "html": ".html", "htm": ".html", "python": ".py", "py": ".py", "javascript": ".js", "js": ".js",
    "typescript": ".ts", "ts": ".ts", "tsx": ".tsx", "jsx": ".jsx", "css": ".css", "json": ".json",
    "bash": ".sh", "sh": ".sh", "shell": ".sh", "zsh": ".sh", "powershell": ".ps1", "ps1": ".ps1",
    "sql": ".sql", "yaml": ".yaml", "yml": ".yaml", "xml": ".xml", "svg": ".svg", "markdown": ".md",
    "md": ".md", "go": ".go", "rust": ".rs", "rs": ".rs", "java": ".java", "c": ".c", "cpp": ".cpp",
    "c++": ".cpp", "csharp": ".cs", "cs": ".cs", "php": ".php", "ruby": ".rb", "rb": ".rb",
    "kotlin": ".kt", "swift": ".swift", "lua": ".lua", "toml": ".toml", "ini": ".ini", "dockerfile": "",
    "makefile": "", "csv": ".csv", "text": ".txt", "txt": ".txt",
}
_SPRACHE_AUS_ENDUNG = {v: k for k, v in reversed(list(_ENDUNG.items())) if v}
_DATEINAME_RE = re.compile(r"(?:datei|file|filename|title|name|pfad|path)\s*[=:]\s*[\"']?([\w.\-/]+\.\w{1,6})[\"']?", re.I)
_NUR_NAME_RE = re.compile(r"^[\w.\-/]+\.(\w{1,6})$")

# Will der Nutzer eine Datei? ("als HTML-Datei", "zum Herunterladen", "spiel.html")
_DATEI_WUNSCH = re.compile(
    r"\b(als|eine?|in einer?|einzelne)\s+([\w-]+[- ])?datei\b|herunterlad|zum download|downloadbar|"
    r"\b[\w-]+\.(html|py|js|ts|css|json|sh|ps1|sql|md|txt|csv|yaml|yml)\b|\bals\s+(html|python|js)\b",
    re.I,
)


def datei_gewuenscht(frage: str) -> bool:
    return bool(_DATEI_WUNSCH.search(frage or ""))


@dataclass
class Codeblock:
    start: int
    ende: int
    info: str
    sprache: str
    dateiname: str | None
    code: str

    @property
    def zeilen(self) -> int:
        return self.code.count("\n") + 1

    @property
    def roh(self) -> str:
        return f"```{self.info}\n{self.code}\n```"


def _info_lesen(info: str) -> tuple[str, str | None]:
    info = info.strip()
    if not info:
        return "", None
    name = None
    m = _DATEINAME_RE.search(info)
    if m:
        name = m.group(1)
    erstes = info.split()[0]
    if ":" in erstes and not m:  # ```html:spiel.html
        erstes, _, rest = erstes.partition(":")
        if _NUR_NAME_RE.match(rest):
            name = rest
    n = _NUR_NAME_RE.match(erstes)
    if n:  # ```spiel.html
        name = name or erstes
        return _SPRACHE_AUS_ENDUNG.get("." + n.group(1).lower(), n.group(1).lower()), name
    return erstes.lower(), name


def bloecke(text: str) -> list[Codeblock]:
    aus = []
    for m in _BLOCK_RE.finditer(text or ""):
        sprache, name = _info_lesen(m.group(1))
        aus.append(Codeblock(m.start(), m.end(), m.group(1), sprache, name, m.group(2)))
    return aus


def ist_ganzes_html(code: str) -> bool:
    k = code.lower()
    return ("<script" in k or "<canvas" in k) and ("<html" in k or "<body" in k or "<!doctype" in k)


def dateiwuerdig(b: Codeblock, gewuenscht: bool) -> bool:
    if b.dateiname:
        return True
    if b.sprache in ("", "text", "txt", "console", "output", "log", "diff"):
        return False
    if b.sprache in ("html", "htm") and ist_ganzes_html(b.code):
        return True
    return b.zeilen >= (MIN_ZEILEN_WUNSCH if gewuenscht else MIN_ZEILEN)


def dateiname_fuer(b: Codeblock, nummer: int = 0) -> str:
    if b.dateiname:
        return PurePosixPath(b.dateiname).name
    endung = _ENDUNG.get(b.sprache, ".txt") or ".txt"
    stamm = None
    if endung == ".html":
        t = re.search(r"<title>(.*?)</title>", b.code, re.I | re.S)
        if t:
            stamm = t.group(1)
    if not stamm:
        k = re.search(r"^\s*(?:#|//|--|/\*)\s*(?:datei|file)?:?\s*([\w\-]{3,40})", b.code, re.I | re.M)
        stamm = k.group(1) if k else None
    stamm = re.sub(r"[^\w\-]+", "-", (stamm or {"html": "seite", "py": "skript", "sh": "skript"}.get(endung[1:], "code")).strip().lower()).strip("-")[:40] or "code"
    return f"{stamm}{'-' + str(nummer + 1) if nummer else ''}{endung}"


# ── Prüfen ────────────────────────────────────────────────────────────────

def _zeile_zeigen(code: str, nr: int | None) -> str:
    if not nr:
        return ""
    zeilen = code.split("\n")
    if 1 <= nr <= len(zeilen):
        return f"\n    Zeile {nr}: {zeilen[nr - 1].strip()[:200]}"
    return ""


async def _browser(code: str, sb: dict, pfad: str | None = None) -> list[str]:
    arbeit = arbeitsbereich.ordner(sb)
    if pfad and (arbeit / pfad).is_file():
        # Datei an ihrem Ort testen: daneben liegende Skripte/Stile laden mit
        # (seit 2026-10-17 — die Kopie in .pruefung/ fand mario.js nicht).
        seite = arbeit / pfad
    else:
        ok, rel = await arbeitsbereich._helfer(sb, "schreiben", {"pfad": ".pruefung/seite.html", "inhalt": code})
        if not ok:
            return []
        seite = arbeit / ".pruefung" / "seite.html"
    rc, out, err, um = await arbeitsbereich.eingesperrt(
        sb, [NODE, str(PRUEFSKRIPT), str(seite)],
        zeit=45, cpu=90, speicher=None,
        umgebung={"PLAYWRIGHT_BROWSERS_PATH": PLAYWRIGHT_BROWSER, "NODE_PATH": PLAYWRIGHT_MODULE},
    )
    if um:
        return ["Die Seite reagiert nicht mehr (Endlosschleife? Der Test brach nach 45 s ab)."]
    try:
        d = json.loads(out.decode("utf-8", "replace") or "{}")
    except json.JSONDecodeError:
        _log.warning("html-pruefung: rc=%s err=%s", rc, err[-500:])
        return []
    if d.get("abbruch"):
        _log.warning("html-pruefung abgebrochen: %s", d)
        return []
    fehler = d.get("fehler") or []
    if d.get("extern_fehlt"):
        # Ohne Netz fehlen CDN-Bibliotheken — Laufzeitfehler können davon
        # kommen. Dann nur echte Syntaxfehler melden.
        fehler = [f for f in fehler if "SyntaxError" in f.get("text", "") or "Unexpected" in f.get("text", "")]
    aus = []
    for f in fehler[:5]:
        datei = f.get("datei") or ""
        if datei and not re.search(r"\.html?$", datei):  # Fehler in einer eingebundenen .js-Datei
            aus.append(f"{f.get('text')}" + (f" ({datei} Zeile {f['zeile']})" if f.get("zeile") else f" ({datei})"))
        else:
            aus.append(f"{f.get('text')}" + (f" (Zeile {f['zeile']})" if f.get("zeile") else "") + _zeile_zeigen(code, f.get("zeile")))
    return aus


async def _syntax_extern(sb: dict, argv: list[str], code: str, datei: str) -> list[str]:
    ok, _ = await arbeitsbereich._helfer(sb, "schreiben", {"pfad": f".pruefung/{datei}", "inhalt": code})
    if not ok:
        return []
    arbeit = arbeitsbereich.ordner(sb)
    rc, out, err, um = await arbeitsbereich.eingesperrt(sb, [*argv, str(arbeit / ".pruefung" / datei)], zeit=20, speicher=None)
    if um or rc == 0:
        return []
    text = (err or out).decode("utf-8", "replace").strip()
    text = text.replace(str(arbeit / ".pruefung") + "/", "")
    # Node hängt seinen eigenen Stacktrace an — der hilft dem Modell nicht.
    zeilen = []
    for z in text.splitlines():
        if z.startswith("    at ") or z.startswith("Node.js v"):
            break
        zeilen.append(z)
    text = "\n".join(zeilen).strip()
    return [text[-600:]] if text else []


async def pruefen(code: str, sprache: str, sb: dict | None, pfad: str | None = None) -> list[str] | None:
    """Fehler im Code. [] = ok, None = für diese Sprache gibt es keine Prüfung.
    ``pfad``: Datei liegt so im Arbeitsordner — dort testen (Nachbardateien laden mit)."""
    sb = sb or {"user_id": "pruefung", "session_id": "pruefung"}
    try:
        if sprache in ("html", "htm"):
            return await _browser(code, sb, pfad) if ist_ganzes_html(code) else None
        if sprache in ("python", "py"):
            try:
                ast.parse(code)
                return []
            except SyntaxError as e:
                return [f"SyntaxError: {e.msg} (Zeile {e.lineno})" + _zeile_zeigen(code, e.lineno)]
        if sprache in ("json",):
            try:
                json.loads(code)
                return []
            except json.JSONDecodeError as e:
                return [f"JSON-Fehler: {e.msg} (Zeile {e.lineno})" + _zeile_zeigen(code, e.lineno)]
        if sprache in ("javascript", "js"):
            return await _syntax_extern(sb, [NODE, "--check"], code, "skript.js")
        if sprache in ("bash", "sh", "shell", "zsh"):
            return await _syntax_extern(sb, ["/bin/bash", "-n"], code, "skript.sh")
    except Exception as e:  # pragma: no cover — Prüfen ist ein Zusatz
        _log.warning("pruefung %s: %s", sprache, e)
    return None


# ── Korrigieren ───────────────────────────────────────────────────────────

FLICK_AUFTRAG = (
    "(System: Xera hat den Code{datei} automatisch getestet ({art}). Dabei kam:\n{fehler}\n\n"
    "Korrigiere NUR die Fehler. Antworte ausschliesslich mit einem oder mehreren Blöcken in genau diesem Format, "
    "ohne weiteren Text und ohne Codezaun:\n"
    "<<<<<<< SUCHEN\n(2–6 Zeilen exakt wie im bisherigen Code)\n=======\n(dieselben Zeilen korrigiert)\n>>>>>>> ERSETZEN\n"
    "Die SUCHEN-Zeilen müssen Zeichen für Zeichen im Code vorkommen und eindeutig sein. Netzwerk ist im Test gesperrt.)"
)
_FLICK_RE = re.compile(r"<{5,9}\s*SUCHEN[^\n]*\n(.*?)\n={5,9}[^\n]*\n(.*?)\n?>{5,9}\s*ERSETZEN", re.S)


def _ersetze(code: str, alt: str, neu: str) -> str | None:
    if alt and code.count(alt) == 1:
        return code.replace(alt, neu, 1)
    # Zeilenweise ohne Einrückung — das Modell trifft die Leerzeichen nicht immer.
    zeilen = code.split("\n")
    such = [z.strip() for z in alt.strip("\n").split("\n")]
    while such and not such[0]:
        such.pop(0)
    while such and not such[-1]:
        such.pop()
    n = len(such)
    if not n:
        return None
    treffer = [i for i in range(len(zeilen) - n + 1) if [z.strip() for z in zeilen[i:i + n]] == such]
    if len(treffer) != 1:
        return None
    i = treffer[0]
    einzug = re.match(r"\s*", zeilen[i]).group(0)
    neue = neu.strip("\n").split("\n")
    if neue and not re.match(r"\s", neue[0]) and einzug:
        neue = [einzug + z if z.strip() else z for z in neue]
    return "\n".join(zeilen[:i] + neue + zeilen[i + n:])


def flicken_anwenden(code: str, antwort: str) -> tuple[str, int, int]:
    antwort = re.sub(r"```[\w-]*\n?", "", antwort or "")
    angewendet = fehlgeschlagen = 0
    for alt, neu in _FLICK_RE.findall(antwort):
        neuer = _ersetze(code, alt, neu)
        if neuer is None:
            fehlgeschlagen += 1
        else:
            code, angewendet = neuer, angewendet + 1
    return code, angewendet, fehlgeschlagen


async def pruefen_und_flicken(
    code: str,
    sprache: str,
    sb: dict | None,
    nachfragen: Callable[[str], Awaitable[str]] | None,
    dateiname: str = "",
) -> AsyncGenerator[tuple, None]:
    """Prüft und lässt korrigieren. Liefert ("status", text) und zum Schluss
    genau einmal ("fertig", code, verbleibende_fehler | None, korrigiert)."""
    art = "im Browser geladen" if sprache in ("html", "htm") else "Syntax geprüft"
    yield ("status", "testet den Code im Browser" if sprache in ("html", "htm") else "prüft den Code")
    fehler = await pruefen(code, sprache, sb)
    korrigiert = 0
    runde = 0
    while fehler and nachfragen and runde < RUNDEN:
        runde += 1
        yield ("status", f"{len(fehler)} Fehler gefunden — korrigiert ({runde}/{RUNDEN})")
        auftrag = FLICK_AUFTRAG.format(datei=f" ({dateiname})" if dateiname else "", art=art,
                                       fehler="\n".join(f"- {f}" for f in fehler))
        try:
            antwort = await nachfragen(auftrag)
        except Exception as e:
            _log.warning("flicken: %s", e)
            break
        neu, angewendet, _ = flicken_anwenden(code, antwort)
        if not angewendet:
            _log.info("flicken: keine Korrektur anwendbar: %s", (antwort or "")[:300])
            break
        code = neu
        korrigiert += angewendet
        yield ("status", "testet die Korrektur")
        fehler = await pruefen(code, sprache, sb)
    yield ("fertig", code, fehler, korrigiert)


def bericht(fehler: list[str] | None, korrigiert: int, sprache: str) -> str:
    """Kurzer Satz für den Nutzer."""
    pruefung = "im Browser getestet" if sprache in ("html", "htm") else "auf Syntax geprüft"
    if fehler is None:
        return ""
    gross = pruefung[0].upper() + pruefung[1:]
    if not fehler:
        return f"{gross}: keine Fehler" + (f" (vorher {korrigiert} Stelle{'n' if korrigiert != 1 else ''} automatisch korrigiert)" if korrigiert else "") + "."
    return f"{gross}: noch {len(fehler)} Fehler — " + "; ".join(f.split("\n")[0] for f in fehler[:2])

"""Läuft IM Sandkasten (siehe arbeitsbereich.py), nie als root.

Aufruf: python3 -I sandbox_helfer.py <op>, Argumente als JSON auf stdin,
Arbeitsverzeichnis = Arbeitsordner des Nutzers. Antwort: eine JSON-Zeile auf
stdout. Prozess hat eine eigene Benutzerkennung, kein Netz und Grenzen für
CPU, Speicher und Dateigrösse — dieser Code selbst muss also nichts mehr
absichern ausser: nur im Arbeitsordner bleiben (Pfade, die hinausführen,
werden abgelehnt; Symlinks hinaus führen auf Dateien, die diese Kennung
ohnehin nicht lesen darf).
"""

import base64
import json
import os
import sys

BASIS = os.path.realpath(os.getcwd())
MAX_LESEN = 200_000
MAX_EXPORT = 20 * 1024 * 1024
# Pro read_file höchstens so viel — passt ganz ins Modell (seit 2026-10-17;
# vorher schnitt der Agent-Kontext bei 12 000 Zeichen still ab).
MAX_ABSCHNITT = 60_000
_TEXT_ENDUNGEN = {".html", ".htm", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".css", ".py", ".sh", ".ps1",
                  ".json", ".md", ".txt", ".csv", ".tsv", ".xml", ".yaml", ".yml", ".sql", ".ini", ".toml",
                  ".svg", ".c", ".h", ".cpp", ".java", ".go", ".rs", ".php", ".rb", ".lua", ".bat", ".conf", ".log"}


def pfad(roh: str) -> str:
    roh = (roh or "").strip() or "."
    voll = os.path.realpath(os.path.join(BASIS, roh))
    if voll != BASIS and not voll.startswith(BASIS + os.sep):
        raise ValueError("Pfad liegt ausserhalb des Arbeitsordners")
    return voll


def rel(voll: str) -> str:
    return os.path.relpath(voll, BASIS)


def lesen(a):
    """Ganze Datei oder ein Abschnitt (von = erste Zeile, 1-basiert; zeilen = Anzahl).
    Was nicht passt, wird nie still abgeschnitten: der Hinweis sagt, wie es weitergeht."""
    p = pfad(a.get("pfad"))
    if not os.path.isfile(p):
        return False, f"Datei nicht gefunden: {rel(p)}"
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        text = f.read(MAX_EXPORT)
    zeilen = text.split("\n")
    gesamt = len(zeilen)
    von = max(1, int(a.get("von") or 1))
    anzahl = int(a.get("zeilen") or 0) or gesamt
    teil, laenge = [], 0
    for z in zeilen[von - 1:von - 1 + anzahl]:
        if teil and laenge + len(z) + 1 > MAX_ABSCHNITT:
            break
        teil.append(z)
        laenge += len(z) + 1
    bis = von + len(teil) - 1
    aus = "\n".join(teil)
    if von > 1 or bis < gesamt:
        aus += (f"\n\n[Zeilen {von}–{bis} von {gesamt}"
                + (f" — weiterlesen mit read_file(path, offset={bis + 1})]" if bis < gesamt else "]"))
    return True, aus


def schreiben(a):
    p = pfad(a.get("pfad"))
    if os.path.isdir(p):
        return False, f"Ist ein Ordner: {rel(p)}"
    os.makedirs(os.path.dirname(p), exist_ok=True)
    inhalt = a.get("inhalt") or ""
    with open(p, "w", encoding="utf-8") as f:
        f.write(inhalt)
    return True, rel(p)


def ersetzen(a):
    p = pfad(a.get("pfad"))
    if not os.path.isfile(p):
        return False, f"Datei nicht gefunden: {rel(p)}"
    alt, neu = a.get("alt") or "", a.get("neu") or ""
    if not alt:
        return False, "old_string fehlt"
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    n = text.count(alt)
    if n == 0:
        return False, f"old_string nicht gefunden in {rel(p)} — genaue Schreibweise inkl. Leerzeichen prüfen."
    if n > 1:
        return False, f"old_string ist {n}x vorhanden — mehr Kontext angeben, damit er eindeutig ist."
    with open(p, "w", encoding="utf-8") as f:
        f.write(text.replace(alt, neu, 1))
    return True, rel(p)


def liste(a):
    p = pfad(a.get("pfad"))
    if not os.path.isdir(p):
        return False, f"Kein Ordner: {rel(p)}"
    zeilen = []
    for name in sorted(os.listdir(p))[:300]:
        q = os.path.join(p, name)
        if os.path.isdir(q):
            zeilen.append(f"d {'':>10}  {name}/")
        else:
            zeilen.append(f"- {os.path.getsize(q):>10}  {name}")
    return True, "\n".join(zeilen) or "[leer — der Arbeitsordner enthält noch nichts]"


def finden(a):
    import fnmatch
    muster = a.get("muster") or "*"
    p = pfad(a.get("pfad"))
    treffer = []
    for wurzel, ordner, dateien in os.walk(p):
        ordner[:] = [o for o in ordner if not o.startswith(".")]
        for d in dateien:
            if fnmatch.fnmatch(d.lower(), muster.lower()):
                treffer.append(rel(os.path.join(wurzel, d)))
                if len(treffer) >= 200:
                    return True, "\n".join(treffer)
    return True, "\n".join(treffer) or "[keine Treffer]"


def inventar(a):
    aus = {}
    for wurzel, ordner, dateien in os.walk(BASIS):
        ordner[:] = [o for o in ordner if not o.startswith(".") and o != "__pycache__"]
        for d in dateien:
            q = os.path.join(wurzel, d)
            try:
                st = os.stat(q)
            except OSError:
                continue
            aus[rel(q)] = [st.st_size, int(st.st_mtime_ns)]
            if len(aus) >= 500:
                return True, aus
    return True, aus


def export(a):
    p = pfad(a.get("pfad"))
    if not os.path.isfile(p):
        return False, f"Datei nicht gefunden: {rel(p)}"
    if os.path.getsize(p) > MAX_EXPORT:
        return False, "Datei ist zu gross (über 20 MB)"
    with open(p, "rb") as f:
        return True, base64.b64encode(f.read()).decode()


def einspielen(a):
    """Binärdatei (base64) in den Arbeitsordner legen — Uploads, erzeugte Dokumente."""
    p = pfad(a.get("pfad"))
    if os.path.isdir(p):
        return False, f"Ist ein Ordner: {rel(p)}"
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(base64.b64decode(a.get("daten") or ""))
    return True, rel(p)


def uebersicht(a):
    """Alle Dateien (ohne versteckte Ordner): Pfad, Grösse, Änderungszeit, Zeilen bei Text."""
    aus = []
    for wurzel, ordner, dateien in os.walk(BASIS):
        ordner[:] = [o for o in ordner if not o.startswith(".") and o != "__pycache__"]
        for d in dateien:
            if d.startswith("."):
                continue
            q = os.path.join(wurzel, d)
            try:
                st = os.stat(q)
            except OSError:
                continue
            zeilen = None
            if os.path.splitext(d)[1].lower() in _TEXT_ENDUNGEN and st.st_size <= 5 * 1024 * 1024:
                with open(q, "rb") as f:
                    zeilen = f.read().count(b"\n") + 1
            aus.append([rel(q), st.st_size, int(st.st_mtime), zeilen])
            if len(aus) >= 300:
                return True, aus
    return True, aus


OPS = {"lesen": lesen, "schreiben": schreiben, "ersetzen": ersetzen, "liste": liste,
       "finden": finden, "inventar": inventar, "export": export, "einspielen": einspielen,
       "uebersicht": uebersicht}


def main():
    op = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        args = json.loads(sys.stdin.read() or "{}")
        ok, ausgabe = OPS[op](args)
    except KeyError:
        ok, ausgabe = False, f"unbekannte Operation {op}"
    except Exception as e:  # alles als Text zurück, nie als Traceback
        ok, ausgabe = False, f"{type(e).__name__}: {e}"
    sys.stdout.write(json.dumps({"ok": ok, "ausgabe": ausgabe}, ensure_ascii=False))


if __name__ == "__main__":
    main()

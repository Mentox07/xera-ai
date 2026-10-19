"""Denkaufwand — wie ``/effort`` in Claude Code, für Web und CLI (seit 2026-10-19).

Vorher gab es nur „Gründlich denken“ an/aus mit festen 4 096 Denk-Tokens. Am
2026-10-18 (Gespräche 622/623, „snake spiel mit extras“) schrieb Qwen3.8 das
ganze Spiel schon im Denken — 13 000 Zeichen in 166 s, die Antwort wäre danach
noch einmal so lang gewesen. Ein Nutzer brach zweimal ab („denkt unendlich lang“).

Jetzt:
* Stufen ``aus · niedrig · mittel · hoch · max`` mit Token-Budget UND Zeitgrenze.
  Auch ``max`` ist begrenzt (8 192 Tokens, 7 min), Agents denken höchstens
  ``AGENT_MAX`` — vier Agents mit je 8k Denk-Tokens würden die Slots minutenlang
  blockieren.
* Code im Denken beendet das Denken sofort: Die Antwort wird ohne Denken
  geschrieben, mit den bisherigen Überlegungen (ohne Code) als Hinweis.
* Der Nutzer kann das Denken jederzeit beenden („Jetzt antworten“).
"""

from __future__ import annotations

import contextvars
import re

STUFEN = ("aus", "niedrig", "mittel", "hoch", "max")

# Denk-Tokens, Denk-Tokens für Agents (erster / weitere Schritte), Zeitgrenze in Sekunden.
_WERTE = {
    "niedrig": {"budget": 1024, "agent": (512, 256), "sekunden": 60},
    "mittel": {"budget": 2048, "agent": (1024, 512), "sekunden": 120},
    "hoch": {"budget": 4096, "agent": (2048, 1024), "sekunden": 240},
    "max": {"budget": 8192, "agent": (2048, 1024), "sekunden": 420},
}

# Englische Namen (OpenCode, reasoning_effort) und das alte „denken: true“.
_ALIAS = {
    "none": "aus", "off": "aus", "false": "aus", "0": "aus", "": "aus",
    "minimal": "niedrig", "low": "niedrig",
    "medium": "mittel", "true": "mittel", "1": "mittel", "denken": "mittel",
    "high": "hoch",
    "xhigh": "max", "maximum": "max", "highest": "max",
}

# Sampling im Denkmodus laut Qwen/Unsloth — der Server steht auf Instruct-Werten.
DENK_SAMPLING = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "presence_penalty": 0.0}
BUDGET_NACHRICHT = "\n\nGenug überlegt — jetzt die Antwort schreiben.\n"

# Stufe der laufenden Anfrage, damit Agents (agents/base.py) sie kennen, ohne
# dass jede Funktion dazwischen einen Parameter mehr braucht.
AKTUELL: contextvars.ContextVar[str] = contextvars.ContextVar("xera_aufwand", default="aus")


def stufe(wert) -> str:
    """Beliebige Angabe → eine der STUFEN. Unbekanntes → ``aus``."""
    if wert is True:
        return "mittel"
    if wert is None or wert is False:
        return "aus"
    w = str(wert).strip().lower()
    if w in STUFEN:
        return w
    return _ALIAS.get(w, "aus")


def budget(s: str) -> int:
    return _WERTE[s]["budget"] if s in _WERTE else 0


def sekunden(s: str) -> int:
    return _WERTE[s]["sekunden"] if s in _WERTE else 0


def agent_budget(s: str, erster_schritt: bool) -> int:
    if s not in _WERTE:
        return 0
    erst, weiter = _WERTE[s]["agent"]
    return erst if erster_schritt else weiter


def anfrage_ergaenzen(anfrage: dict, s: str, *, tokens: int | None = None, nachricht: str = BUDGET_NACHRICHT) -> int:
    """Denkmodus in eine llama-Anfrage eintragen. Liefert das Budget (0 = aus)."""
    b = budget(s) if tokens is None else tokens
    if not b:
        return 0
    anfrage["chat_template_kwargs"] = {"enable_thinking": True}
    anfrage.update(DENK_SAMPLING)
    anfrage["reasoning_budget_tokens"] = b
    anfrage["reasoning_budget_message"] = nachricht
    return b


def anfrage_ohne_denken(anfrage: dict) -> dict:
    """Dieselbe Anfrage ohne Denkmodus (für die Antwortrunde nach dem Denken)."""
    return {k: v for k, v in anfrage.items()
            if k not in ("chat_template_kwargs", "reasoning_budget_tokens", "reasoning_budget_message")
            and k not in DENK_SAMPLING}


# Code im Denken: HTML/Script-Anfänge, ein Code-Block ab ein paar Zeilen — oder
# viele Zeilen, die nach Programm aussehen (Klammer/Semikolon am Ende,
# Schlüsselwort am Anfang). Ein kurzes Beispiel zum Nachdenken bleibt erlaubt.
_ZAUN = re.compile(r"<!DOCTYPE|<html|<script|<style|<canvas", re.I)
_CODEZEILE = re.compile(
    r"^\s*(?:function\b|const\b|let\b|var\b|def\b|class\b|import\b|from\b|return\b|if\s*\(|for\s*\(|while\s*\(|"
    r"[A-Za-z_$][\w$.]*\s*=\s*.+;$|[}\]);]+;?$|<\/?[a-z][\w-]*[ >])|.*[{;]\s*$", re.I)
CODEZEILEN_MAX = 12
BLOCKZEILEN_MAX = 8


def code_im_denken(text: str) -> bool:
    if _ZAUN.search(text):
        return True
    teile = text.split("```")
    # Ungerade Teile liegen in einem Code-Block (auch im noch offenen letzten).
    if any(len(teile[i].splitlines()) > BLOCKZEILEN_MAX for i in range(1, len(teile), 2)):
        return True
    return sum(1 for z in text.splitlines() if z.strip() and _CODEZEILE.match(z)) >= CODEZEILEN_MAX


def plan_aus_denken(text: str, max_zeichen: int = 1500) -> str:
    """Die Überlegungen ohne Code — als Hinweis für die Antwortrunde."""
    ohne_bloecke = re.sub(r"```.*?(```|$)", " ", text, flags=re.S)
    zeilen = [z for z in ohne_bloecke.splitlines()
              if z.strip() and not _CODEZEILE.match(z) and not _ZAUN.search(z) and not re.search(r"[{}<>]", z)]
    plan = "\n".join(zeilen).replace("```", "").strip()
    return plan[:max_zeichen] + ("…" if len(plan) > max_zeichen else "")


def hinweis_antworten(gedanken: str, grund: str) -> str:
    """Nachricht an das Modell, wenn Xera das Denken beendet hat."""
    plan = plan_aus_denken(gedanken)
    teile = [f"(System: Das Nachdenken wurde beendet — {grund}. Schreib jetzt direkt die Antwort, ohne weiter zu planen."]
    teile.append("Code gehört vollständig in die Antwort (als Code-Block bzw. per Werkzeug), nie ins Nachdenken.")
    if plan:
        teile.append(f"Deine Überlegungen bisher (ohne Code):\n{plan}")
    return " ".join(teile[:2]) + ("\n\n" + teile[2] if len(teile) > 2 else "") + ")"

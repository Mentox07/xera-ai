"""Ein llama-Slot, eine Anfrage (seit 2026-10-17).

Xera schickt Anfragen an feste Slots (``id_slot``: Chat 0, Code/Cowork 1,
Agents 2–5, Nebenaufgaben 4). Kommt eine zweite Anfrage für einen Slot, der
gerade arbeitet, stellt llama-server sie zwar zurück — lädt vorher aber seinen
RAM-Cache in den belegten Slot und zerstört damit die laufende Aufgabe
(llama.cpp-Fehler, Gespräch 580 am 2026-10-16 23:16 UTC: Endlosschleife
„prompt processing“, 13 min Stillstand). Darum wartet Xera selbst, bis der
Slot frei ist, und schickt erst dann.

Gilt für alle Aufrufe mit festem Slot: Hauptmodell (vermittler.py), Rückfragen
der Code-Prüfung, Agents (agents/base.py), Lernnotizen (learning.py),
Zusammenfassungen (kontext.py), Aufwärmen.
"""

from __future__ import annotations

import asyncio
import contextlib

_SPERREN: dict[int, asyncio.Lock] = {}


def _sperre(slot: int) -> asyncio.Lock:
    s = _SPERREN.get(slot)
    if s is None:
        s = _SPERREN[slot] = asyncio.Lock()
    return s


def belegt(slot) -> bool:
    """Arbeitet gerade eine andere Anfrage dieses Prozesses auf dem Slot?"""
    return slot is not None and _sperre(int(slot)).locked()


@contextlib.asynccontextmanager
async def slot(nummer):
    """``async with slot(n):`` — exklusiv für die Dauer des llama-Aufrufs.
    Ohne festen Slot (None) keine Sperre."""
    if nummer is None:
        yield
        return
    async with _sperre(int(nummer)):
        yield


async def leeren_slot_anstossen(client, basis_url: str, slot) -> None:
    """Umgehung eines llama.cpp-Fehlers, solange der gepatchte Build nicht läuft
    (~/abend/patch-leerer-slot-nan.diff auf dem GPU-Server).

    Mit ``--cache-idle-slots`` parkt llama-server Gespräche untätiger Slots im
    RAM und leert den Slot. Eine Anfrage mit festem Slot auf einen LEEREN Slot
    rechnet dann ``f_keep = 0/0 = NaN``, fragt den RAM-Cache nie und liest das
    ganze Gespräch neu ein (Abnahmetest 2026-10-16: Bereichswechsel 18 s, erste
    Code-Frage 30 s, Agent-Runde 75 s). Ist der Slot leer, geht vorher eine
    Mini-Anfrage hinein — danach holt llama-server das Gespräch wie vorgesehen
    aus dem RAM. Mit dem gepatchten Build harmlos (kostet ~0,3 s), dann entbehrlich.
    Muss innerhalb von ``slot()`` laufen."""
    if slot is None:
        return
    try:
        r = await client.get(f"{basis_url}/slots", timeout=5)
        s = next((x for x in r.json() if x.get("id") == int(slot)), None)
        if s is None or s.get("is_processing") or s.get("n_prompt_tokens"):
            return
        await client.post(f"{basis_url}/v1/chat/completions", timeout=30, json={
            "model": "xera-ai", "messages": [{"role": "user", "content": "."}], "max_tokens": 1,
            "id_slot": int(slot), "cache_prompt": False})
    except Exception:  # nur eine Beschleunigung — nie die eigentliche Anfrage aufhalten
        pass


async def warten_bis_frei(client, basis_url: str, slot, max_s: float = 15.0) -> None:
    """Nach einem Abbruch (Stopp, „Jetzt antworten“, Denken beendet) schliesst Xera
    die Verbindung sofort — llama-server merkt das aber erst beim nächsten Token.
    Kommt die nächste Anfrage für denselben Slot vorher, ist der Slot noch belegt:
    genau der llama.cpp-Fehler „belegter Slot“ (Gespräch 580). Darum kurz warten,
    bis llama-server den Slot freigibt. Muss innerhalb von ``slot()`` laufen."""
    if slot is None:
        return
    import time
    frist = time.monotonic() + max_s
    try:
        while time.monotonic() < frist:
            r = await client.get(f"{basis_url}/slots", timeout=5)
            s = next((x for x in r.json() if x.get("id") == int(slot)), None)
            if s is None or not s.get("is_processing"):
                return
            await asyncio.sleep(0.3)
    except Exception:  # nur eine Vorsichtsmassnahme — nie die Anfrage aufhalten
        pass

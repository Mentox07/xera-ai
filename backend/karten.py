"""Agent-Karten, Werkzeuge und Denkweg einer Antwort zum Speichern.

Die neue Oberfläche baut diese Anzeige live aus den Ereignissen im
Antwortstrom (web/src/daten/useGespraech.ts). Gespeichert wurde bisher nur der
Antworttext — nach dem Neuladen waren die Karten weg. Der Sammler hier liest
denselben Strom mit und baut dieselben Objekte wie der Reducer im Browser
(Felder wie in web/src/daten/typen.ts: Auftrag, Werkzeugaufruf), damit
`GET /api/sessions/{id}/messages` sie direkt an der Nachricht mitliefern kann.
"""

from __future__ import annotations

import json
import time

# Ergebnisse von Werkzeugen nur gekürzt aufheben — sie stehen ohnehin schon
# gekürzt im Strom, aber ein Agent kann viele Schritte machen.
_ERGEBNIS_MAX = 600


def _jetzt_ms() -> int:
    return int(time.time() * 1000)


class KartenSammler:
    def __init__(self) -> None:
        self.auftraege: list[dict] = []
        self.werkzeuge: list[dict] = []
        self.gedanken = ""
        self.denk_beginn: int | None = None
        self.denk_ende: int | None = None

    def _auftrag(self, lauf: str) -> dict | None:
        return next((a for a in self.auftraege if a["lauf"] == lauf), None)

    def _liste(self, d: dict) -> list[dict] | None:
        if d.get("lauf"):
            a = self._auftrag(d["lauf"])
            return a["schritte"] if a else None
        return self.werkzeuge

    def lesen(self, chunk: str) -> None:
        """Nimmt ein SSE-Stück (`data: {...}`) aus dem Antwortstrom."""
        for zeile in chunk.splitlines():
            if not zeile.startswith("data: "):
                continue
            try:
                d = json.loads(zeile[6:])
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(d, dict):
                self._ereignis(d)

    def _ereignis(self, d: dict) -> None:
        art = d.get("type")
        if art is None and d.get("content") and self.denk_beginn and not self.denk_ende:
            self.denk_ende = _jetzt_ms()  # erstes Stück Antwort beendet das Denken
        if art == "auftrag_start":
            self.auftraege.append({
                "lauf": d.get("lauf", ""),
                "kennung": d.get("kennung", ""),
                "name": d.get("name", ""),
                "auftrag": d.get("auftrag", ""),
                "farbe": d.get("color"),
                "zustand": "laeuft",
                "schritte": [],
                "beginn": _jetzt_ms(),
            })
        elif art == "auftrag_fertig":
            a = self._auftrag(d.get("lauf", ""))
            if a:
                a["zustand"] = "fertig" if d.get("ok") else "fehler"
                a["zusammenfassung"] = d.get("zusammenfassung", "")
                a["ende"] = _jetzt_ms()
        elif art in ("tool_call", "approval_required"):
            liste = self._liste(d)
            if liste is not None:
                liste[:] = [w for w in liste if w["id"] != d.get("id")]
                liste.append({
                    "id": d.get("id", ""),
                    "name": d.get("name", ""),
                    "args": d.get("args") or {},
                    "stufe": d.get("level", "READ"),
                    "zustand": "laeuft",
                })
        elif art == "tool_result":
            liste = self._liste(d)
            for w in liste or []:
                if w["id"] == d.get("id"):
                    w["zustand"] = "abgelehnt" if d.get("denied") else "fertig"
                    w["ergebnis"] = (d.get("output") or "")[:_ERGEBNIS_MAX]
                    w["erfolg"] = bool(d.get("success"))
        elif art == "denken":
            self.gedanken += d.get("text", "")
            if self.denk_beginn is None:
                self.denk_beginn = _jetzt_ms()

    def ergebnis(self) -> dict | None:
        """Was zur Nachricht gespeichert wird — None, wenn es nichts gibt."""
        jetzt = _jetzt_ms()
        # Gespeichert wird erst nach dem Ende der Antwort: was dann noch
        # „läuft" (Abbruch, Fehler), läuft nicht mehr — sonst pulsiert die
        # Karte nach dem Neuladen für immer.
        for a in self.auftraege:
            if a["zustand"] == "laeuft":
                a["zustand"] = "fehler"
                a.setdefault("ende", jetzt)
        for w in self.werkzeuge + [s for a in self.auftraege for s in a["schritte"]]:
            if w["zustand"] in ("laeuft", "wartet"):
                w["zustand"] = "fertig"
        aus: dict = {}
        if self.auftraege:
            aus["auftraege"] = self.auftraege
        if self.werkzeuge:
            aus["werkzeuge"] = self.werkzeuge
        if self.gedanken:
            aus["gedanken"] = self.gedanken
            aus["denkSekunden"] = max(1, round(((self.denk_ende or jetzt) - (self.denk_beginn or jetzt)) / 1000))
        return aus or None

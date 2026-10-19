"""Antworten laufen unabhängig von der Verbindung (seit 2026-10-16).

Vorher hing die Antwort direkt an der HTTP-Verbindung: Fenster zu, Neuladen
oder kurz kein Netz — und der Generator wurde abgebrochen. Die Antwort wurde
erst am Ende gespeichert, also nie; das Modell rechnete trotzdem weiter, für
niemanden.

Jetzt läuft jede Antwort als eigener Task. Er schreibt alle SSE-Stücke in einen
Puffer und speichert die Antwort am Ende immer. Die Verbindung liest nur mit —
und eine neue Verbindung (``GET /api/sessions/{id}/strom``) bekommt erst alles
Bisherige und dann live den Rest.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator, Awaitable, Callable

_log = logging.getLogger(__name__)


class Lauf:
    def __init__(self, sitzung_id: int, user_id, request_id: str):
        self.sitzung_id = sitzung_id
        self.user_id = str(user_id)
        self.request_id = request_id
        self.stuecke: list[str] = []
        self.fertig = False
        self._signal = asyncio.Event()
        self.task: asyncio.Task | None = None

    def anhaengen(self, stueck: str) -> None:
        self.stuecke.append(stueck)
        alt, self._signal = self._signal, asyncio.Event()
        alt.set()

    def beenden(self) -> None:
        self.fertig = True
        self._signal.set()

    async def lesen(self, mit_ende: bool = False) -> AsyncIterator[str]:
        """Alles von Anfang an, dann live bis zum Ende.

        ``mit_ende``: zum Schluss ``{"type": "ende"}`` — daran erkennt die
        Oberfläche, dass der Strom vollständig ist und nicht abgerissen.
        (Nicht für die CLI, die kennt das Ereignis nicht.)"""
        i = 0
        while True:
            while i < len(self.stuecke):
                yield self.stuecke[i]
                i += 1
            if self.fertig:
                if mit_ende:
                    yield 'data: {"type": "ende"}\n\n'
                return
            await self._signal.wait()


# Sitzung → laufende Antwort. Fertige Läufe fliegen sofort raus: die Antwort
# steht dann in der Datenbank.
_laeufe: dict[int, Lauf] = {}


def laufend(sitzung_id: int) -> Lauf | None:
    lauf = _laeufe.get(sitzung_id)
    return lauf if lauf and not lauf.fertig else None


def starten(
    sitzung_id: int,
    user_id,
    request_id: str,
    erzeugen: Callable[[Lauf], Awaitable[None]],
) -> Lauf:
    """Startet ``erzeugen(lauf)`` als Task; der Task hängt Stücke an."""
    lauf = Lauf(sitzung_id, user_id, request_id)
    _laeufe[sitzung_id] = lauf

    async def _ausfuehren():
        try:
            await erzeugen(lauf)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            _log.exception("lauf sitzung %s", sitzung_id)
            lauf.anhaengen(f"data: {json.dumps({'type': 'error', 'message': f'{type(e).__name__}: {e}'}, ensure_ascii=False)}\n\n")
        finally:
            lauf.beenden()
            if _laeufe.get(sitzung_id) is lauf:
                _laeufe.pop(sitzung_id, None)

    lauf.task = asyncio.create_task(_ausfuehren())
    return lauf

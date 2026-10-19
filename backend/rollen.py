"""Die Discord-Rollen eines Nutzers frisch halten — für Web und CLI an einer Stelle (seit 2026-10-19).

Bis dahin prüfte Xera Pro und Admin nur beim Login. Wer in Discord eine Rolle verlor,
behielt sie in Xera bis zum Ablauf der Sitzung (30 Tage) — und mit einem CLI-Schlüssel
unbegrenzt, weil `/v1` nur die gespeicherte Angabe las. Nachgeprüft wurde allein der
Homelab-Bereich, und zwar mit dem Discord-Token des Nutzers: Das läuft nach 7 Tagen ab,
und jeder Fehler galt als „keine Rollen“ — Xera hätte dem Nutzer still alles entzogen.

Jetzt fragt der Bot über die Discord-ID nach, höchstens alle ROLLEN_HALTBARKEIT je Nutzer.
"""

import logging
from datetime import datetime, timezone

from . import auth
from . import database as db

_log = logging.getLogger("xera.rollen")

#: Wie lange eine geprüfte Rolle gilt, bevor Xera bei Discord nachfragt.
ROLLEN_HALTBARKEIT = 15 * 60


async def rollen_auffrischen(user: dict | None) -> dict | None:
    """Den Nutzer mit frisch geprüften Rollen zurückgeben (oder unverändert, wenn die Prüfung
    jünger als ROLLEN_HALTBARKEIT ist).

    * Discord nennt Rollen → gespeichert; nicht mehr im Server → alle Rollen weg.
    * Discord gestört (Netz, 429, 5xx, Bot ohne Zugriff) → gespeicherte Rollen bleiben,
      nächster Versuch nach ROLLEN_HALTBARKEIT. Sonst nähme eine Störung allen die Rechte.
    * Konten ohne Discord (Testkonto ``test-screenshot-0001``) bleiben, wie sie sind.
    """
    if not user or not str(user.get("id", "")).isdigit():
        return user
    geprueft = user.get("roles_checked_at")
    if geprueft:
        try:
            alter = (datetime.now(timezone.utc) - datetime.fromisoformat(geprueft)).total_seconds()
            if alter < ROLLEN_HALTBARKEIT:
                return user
        except (ValueError, TypeError):
            pass
    try:
        rollen = await auth.rollen_per_bot(user["id"])
    except auth.DiscordFehler as fehler:
        _log.warning("Rollen von %s nicht nachprüfbar, gespeicherte bleiben: %s", user["id"], fehler)
        db.rollen_geprueft(user["id"])
        return user
    if (bool(user.get("is_pro")), bool(user.get("is_admin")), bool(user.get("has_homelab"))) != (
            rollen["is_pro"], rollen["is_admin"], rollen["has_homelab"]):
        _log.info("Rollen von %s geändert: %s", user["id"], rollen)
    db.aktualisiere_rollen(user["id"], **rollen)
    return db.get_user(user["id"])

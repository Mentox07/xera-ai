import httpx
from . import config

DISCORD_API = "https://discord.com/api/v10"
DISCORD_OAUTH_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"

KEINE_ROLLEN = {"is_pro": False, "is_admin": False, "has_homelab": False}

# Discord-Fehlercodes für „gibt es in diesem Server nicht“: Unknown Guild (Nutzer-Token,
# Nutzer nicht im Server), Unknown Member und Unknown User (Bot).
_NICHT_IM_SERVER = {10004, 10007, 10013}


class DiscordFehler(Exception):
    """Discord hat nicht sauber geantwortet (Netz, abgelaufenes Token, 429, 5xx, Bot ohne
    Zugriff). Dann weiss Xera nichts Neues über die Rollen und behält die gespeicherten —
    bis 2026-10-19 galt so ein Fehler als „keine Rollen“ und nahm still alle Rechte."""


def get_oauth_url(state: str) -> str:
    params = {
        "client_id": config.DISCORD_CLIENT_ID,
        "redirect_uri": config.DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify email guilds.members.read",
        "state": state,
        "prompt": "none",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{DISCORD_OAUTH_URL}?{query}"


async def exchange_code(code: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(DISCORD_TOKEN_URL, data={
            "client_id": config.DISCORD_CLIENT_ID,
            "client_secret": config.DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config.DISCORD_REDIRECT_URI,
        })
        resp.raise_for_status()
        return resp.json()


async def get_discord_user(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{DISCORD_API}/users/@me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        resp.raise_for_status()
        return resp.json()


def rollen_aus(rollen_ids) -> dict:
    """Xera-Rechte aus den Rollen-IDs eines Server-Mitglieds."""
    ids = {str(r) for r in rollen_ids or []}
    return {
        "is_pro": config.XERA_ROLLE_PRO in ids,
        "is_admin": config.XERA_ROLLE_ADMIN in ids,
        "has_homelab": config.XERA_ROLLE_HOMELAB in ids,
    }


async def _mitglied(url: str, kopf: dict) -> dict:
    """Rollen eines Mitglieds; nicht im Server → keine; alles andere → DiscordFehler."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=kopf)
    except httpx.HTTPError as fehler:
        raise DiscordFehler(f"nicht erreichbar: {fehler}") from fehler
    if resp.status_code == 200:
        return rollen_aus(resp.json().get("roles"))
    if resp.status_code == 404:
        try:
            code = resp.json().get("code")
        except ValueError:
            code = None
        if code in _NICHT_IM_SERVER:
            return dict(KEINE_ROLLEN)
    raise DiscordFehler(f"HTTP {resp.status_code}: {resp.text[:120]}")


async def check_roles(access_token: str) -> dict:
    """Rollen beim Login, mit dem Token des Nutzers (Scope guilds.members.read)."""
    return await _mitglied(f"{DISCORD_API}/users/@me/guilds/{config.GUILD_ID}/member",
                           {"Authorization": f"Bearer {access_token}"})


async def rollen_per_bot(user_id: str) -> dict:
    """Rollen nachprüfen, ohne dass der Nutzer dabei ist: Der Bot fragt sein Mitglied ab
    (rollen.py, seit 2026-10-19). Das Discord-Token des Nutzers läuft nach 7 Tagen ab und
    taugt dafür nicht. Lesen braucht keine Rechte im Server — der Bot muss nur Mitglied sein."""
    if not config.DISCORD_BOT_TOKEN:
        raise DiscordFehler("kein Bot-Token (DISCORD_BOT_TOKEN)")
    return await _mitglied(f"{DISCORD_API}/guilds/{config.GUILD_ID}/members/{user_id}",
                           {"Authorization": f"Bot {config.DISCORD_BOT_TOKEN}"})

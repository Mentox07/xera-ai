import httpx
from . import config

DISCORD_API = "https://discord.com/api/v10"
DISCORD_OAUTH_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"


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


async def get_guild_member(access_token: str) -> dict | None:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{DISCORD_API}/users/@me/guilds/{config.GUILD_ID}/member",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if resp.status_code == 200:
            return resp.json()
        return None


async def check_roles(access_token: str) -> dict:
    member = await get_guild_member(access_token)
    if not member:
        return {"is_pro": False, "is_admin": False, "has_homelab": False}

    role_ids = member.get("roles", [])
    if not role_ids:
        return {"is_pro": False, "is_admin": False, "has_homelab": False}

    guild_roles = await get_guild_roles()
    role_map = {role["name"]: role["id"] for role in guild_roles}

    pro_id = role_map.get(config.XERA_PRO_ROLE_NAME)
    admin_id = role_map.get(config.XERA_ADMIN_ROLE_NAME)
    homelab_id = role_map.get(config.XERA_HOMELAB_ROLE_NAME)

    return {
        "is_pro": pro_id in role_ids if pro_id else False,
        "is_admin": admin_id in role_ids if admin_id else False,
        "has_homelab": homelab_id in role_ids if homelab_id else False,
    }


async def get_guild_roles() -> list:
    if not config.DISCORD_BOT_TOKEN:
        return []
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{DISCORD_API}/guilds/{config.GUILD_ID}/roles",
            headers={"Authorization": f"Bot {config.DISCORD_BOT_TOKEN}"}
        )
        if resp.status_code == 200:
            return resp.json()
        return []

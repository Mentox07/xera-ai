import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "http://localhost:8000/auth/callback")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")

# Discord-Server und seine Rollen, über ihre IDs — bis 2026-10-19 über den Namen: Umbenennen nahm
# still die Rechte, eine zweite Rolle gleichen Namens hätte sie vortäuschen können. Die Werte
# stehen in .env (seit 2026-10-19 nicht mehr im Quelltext); ohne sie hat niemand eine Rolle.
GUILD_ID = os.getenv("XERA_GUILD_ID", "")
XERA_ROLLE_PRO = os.getenv("XERA_ROLLE_PRO", "")
XERA_ROLLE_ADMIN = os.getenv("XERA_ROLLE_ADMIN", "")
XERA_ROLLE_HOMELAB = os.getenv("XERA_ROLLE_HOMELAB", "")

# Dienste im eigenen Netz — Adressen aus .env, hier nur neutrale Standardwerte.
# Bis 17.08.2026 liefen drei Modelle auf 8080/8081/8082; seit der Umstellung auf ein Modell
# gibt es eines. LLAMA_FAST_URL und LLAMA_CODE_URL sind entfallen.
LLAMA_API_URL = os.getenv("LLAMA_API_URL", "http://127.0.0.1:8080")
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://127.0.0.1:8888")
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://127.0.0.1:3000")
GRAFANA_TOKEN = os.getenv("GRAFANA_TOKEN", "")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://127.0.0.1:9090")

SECRET_KEY = os.getenv("SECRET_KEY", "xera-ai-dev-secret-change-in-prod")

# Fragen je Tag (Schweizer Zeit) für angemeldete Nutzer ohne Xera Pro/Admin. Bis 2026-10-19
# galten sie insgesamt und setzten nie zurück; Gäste ohne Anmeldung gibt es seither nicht mehr.
FREE_PROMPT_LIMIT = 5

DB_PATH = BASE_DIR / "data" / "xera.db"

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "http://localhost:8000/auth/callback")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")

GUILD_ID = "1501512058041143407"
XERA_PRO_ROLE_NAME = "Xera Pro"
XERA_ADMIN_ROLE_NAME = "Xera Admin"
XERA_HOMELAB_ROLE_NAME = "Xera Homelab"

LLAMA_API_URL = os.getenv("LLAMA_API_URL", "http://192.168.70.10:8080")
LLAMA_FAST_URL = os.getenv("LLAMA_FAST_URL", "http://192.168.70.10:8081")
LLAMA_CODE_URL = os.getenv("LLAMA_CODE_URL", "http://192.168.70.10:8082")
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://192.168.20.27:8080")
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://192.168.20.20:3000")
GRAFANA_TOKEN = os.getenv("GRAFANA_TOKEN", "")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://192.168.20.20:9090")

SECRET_KEY = os.getenv("SECRET_KEY", "xera-ai-dev-secret-change-in-prod")

FREE_PROMPT_LIMIT = 5

DB_PATH = BASE_DIR / "data" / "xera.db"

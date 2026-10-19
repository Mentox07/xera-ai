#!/usr/bin/env python3
from dotenv import load_dotenv
load_dotenv()

import uvicorn

if __name__ == "__main__":
    # Ohne Auto-Reload (seit 2026-10-19): Jede geänderte .py-Datei startete das Backend neu und
    # brach laufende Antworten ab. Einspielen: Dateien kopieren, dann systemctl restart xera-ai.
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False)

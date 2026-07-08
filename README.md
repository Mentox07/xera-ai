# Xera AI

A self-hosted AI assistant powered by local LLMs — no cloud, no API keys, 100% private.

**Live:** [xera-app.com](https://xera-app.com)

## Features

- **Multi-Model Routing** — Big Brain (30B), Fast Brain (8B), Mini Brain (4B) with automatic or manual selection
- **35 Specialized Agents** — from code review to network diagnostics, each with dedicated tools
- **27 Tools** — web search, file operations, code execution, RAG, git, and more
- **Web Search** — integrated SearXNG with source attribution
- **Vision** — image recognition via Moondream2 (paste or file picker)
- **RAG** — ChromaDB-backed retrieval from Obsidian documentation
- **Discord OAuth2** — role-based access (Pro/Guest) with free tier (5 messages)
- **Command Palette** — Ctrl+K for quick actions, brain switching, chat search
- **Chat Export** — download conversations as Markdown
- **Dark/Light Theme** — with i18n (DE/EN)
- **Mobile-first** — responsive design with bottom tab bar
- **CLI Access** — `ssh cli@xera-app.com` (Pro only)

## Stack

| Layer | Tech |
|---|---|
| Frontend | React 18 + Babel Standalone (in-browser JSX) |
| Backend | Python, FastAPI, Uvicorn, SSE streaming |
| Models | llama.cpp (CUDA), Qwen3-Coder-30B, Gemma-4-E2B, Qwen3-4B |
| Vision | Moondream2 1.8B |
| Search | SearXNG |
| RAG | ChromaDB + all-MiniLM-L6-v2 |
| Auth | Discord OAuth2 |
| Database | SQLite |
| Proxy | Caddy |

## Architecture

```
Internet → xera-app.com → Router (DNAT) → Caddy (reverse proxy) → FastAPI → GPU Server (llama.cpp)
```

## Setup

```bash
# Clone
git clone https://github.com/xera-ai/xera.git
cd xera

# Configure
cp .env.example .env
# Edit .env with your Discord app credentials and llama.cpp URL

# Install dependencies
pip install -r requirements.txt

# Run
python run.py
```

## Project Structure

```
xera-ai/
├── backend/
│   ├── agents/          # Agent system (35 specialized agents)
│   │   ├── definitions/ # Individual agent definitions
│   │   ├── orchestrator.py
│   │   └── registry.py
│   ├── auth.py          # Discord OAuth2
│   ├── chat.py          # Chat + SSE streaming
│   ├── config.py        # Configuration
│   ├── database.py      # SQLite
│   ├── learning.py      # Self-learning system
│   ├── main.py          # FastAPI app
│   ├── permissions.py   # Role-based access
│   ├── rag.py           # ChromaDB RAG
│   ├── router.py        # Model routing
│   └── tools.py         # 27 tool implementations
├── static/
│   ├── app.jsx          # React SPA (~4000 lines)
│   ├── styles.css       # All CSS (~5000 lines)
│   ├── index.html       # Entry point
│   └── assets/          # Logo
├── tests/
├── .env.example
├── requirements.txt
└── run.py
```

## License

MIT

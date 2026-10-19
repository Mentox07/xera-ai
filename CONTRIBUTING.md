# Contributing to Xera AI

Thank you for your interest in contributing to Xera AI! This guide will help you get started.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/your-username/xera-ai.git`
3. Create a branch: `git checkout -b feature/your-feature`
4. Make your changes
5. Push and open a Pull Request

## Development Setup

```bash
# Clone the repo
git clone https://github.com/Mentox07/xera-ai.git
cd xera-ai

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment config
cp .env.example .env
# Edit .env with your settings

# Run the development server
python run.py
```

## Project Structure

```
xera-ai/
├── backend/          # FastAPI backend (agents, sandbox, OpenCode motor, /v1 for the CLI)
├── web/              # Frontend (React + TypeScript + Vite) — `npm ci && npm run build`
├── neubau-agents/    # Agent manifests and prompts
├── cli/              # OpenCode configuration and Xera rules
├── motor/            # Sandbox shell and nftables rule for the Code area
└── docs/screenshots/ # Images for the README
```

Installation-specific values (credentials, addresses, SSH targets) never go into the repository:
use `.env` (see `.env.example`) and the site file (see `standort.example.json`).

## Guidelines

- Keep pull requests focused on a single change
- Write descriptive commit messages
- Add tests for new features when applicable
- Follow the existing code style
- Update documentation for user-facing changes

## Reporting Bugs

Use the [Bug Report](https://github.com/Mentox07/xera-ai/issues/new?template=bug_report.md) issue template.

## Suggesting Features

Use the [Feature Request](https://github.com/Mentox07/xera-ai/issues/new?template=feature_request.md) issue template.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).

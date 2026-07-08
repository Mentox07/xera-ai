# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| latest  | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in Xera AI, please report it responsibly:

1. **Do not** open a public issue
2. Email **miguel.rodriguez.15.11.07@gmail.com** with details
3. Include steps to reproduce the vulnerability
4. Allow reasonable time for a fix before public disclosure

## Security Considerations

Xera AI is designed as a **self-hosted** application running on your own infrastructure. Keep in mind:

- Never expose the application directly to the internet without a reverse proxy
- Always change default secrets in `.env` before deploying
- The `shell_execute` and `ssh_execute` tools have access to your servers — restrict network access accordingly
- Keep your LLM server (llama.cpp) on an isolated network segment

## Scope

This policy applies to the Xera AI codebase. Third-party dependencies have their own security policies.

#!/usr/bin/env python3
"""Xera AI — Terminal Client (Claude Code Style)"""

import sys
import json
import httpx
import os
import readline

API_URL = os.getenv("XERA_API_URL", "http://192.168.70.10:8080")

SYSTEM_PROMPT = """Du bist Xera AI, ein lokaler KI-Assistent fuer Homelab-Administration und allgemeine Fragen. Du antwortest auf Deutsch, es sei denn der User schreibt auf Englisch. Du bist hilfsbereit, praezise und technisch kompetent."""

PURPLE = "\033[38;5;141m"
GRAY = "\033[38;5;245m"
WHITE = "\033[97m"
GREEN = "\033[38;5;114m"
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"


def banner():
    print(f"""
{PURPLE}{BOLD}  ██╗  ██╗███████╗██████╗  █████╗      █████╗ ██╗
  ╚██╗██╔╝██╔════╝██╔══██╗██╔══██╗    ██╔══██╗██║
   ╚███╔╝ █████╗  ██████╔╝███████║    ███████║██║
   ██╔██╗ ██╔══╝  ██╔══██╗██╔══██║    ██╔══██║██║
  ██╔╝ ██╗███████╗██║  ██║██║  ██║    ██║  ██║██║
  ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝    ╚═╝  ╚═╝╚═╝{RESET}

  {DIM}Lokaler KI-Assistent — 100% privat{RESET}
  {DIM}Server: {API_URL}{RESET}
  {DIM}Befehle: /quit, /clear, /help{RESET}
""")


def stream_response(messages):
    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

    try:
        with httpx.Client(timeout=120.0) as client:
            with client.stream(
                "POST",
                f"{API_URL}/v1/chat/completions",
                json={
                    "model": "xera-ai",
                    "messages": full_messages,
                    "max_tokens": 2048,
                    "stream": True,
                },
            ) as resp:
                resp.raise_for_status()
                full_response = []
                print(f"\n{GREEN}{BOLD}Xera AI{RESET} ", end="", flush=True)
                for line in resp.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        content = chunk["choices"][0].get("delta", {}).get("content", "")
                        if content:
                            print(content, end="", flush=True)
                            full_response.append(content)
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                print("\n")
                return "".join(full_response)
    except httpx.ConnectError:
        print(f"\n{GRAY}Fehler: Kann Server nicht erreichen ({API_URL}){RESET}\n")
        return None
    except httpx.HTTPStatusError as e:
        print(f"\n{GRAY}Fehler: {e}{RESET}\n")
        return None


def main():
    banner()
    messages = []

    while True:
        try:
            user_input = input(f"{PURPLE}{BOLD}Du{RESET} {WHITE}> {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{DIM}Bis spaeter!{RESET}")
            break

        if not user_input:
            continue

        if user_input == "/quit" or user_input == "/exit":
            print(f"{DIM}Bis spaeter!{RESET}")
            break

        if user_input == "/clear":
            messages = []
            os.system("clear" if os.name != "nt" else "cls")
            banner()
            continue

        if user_input == "/help":
            print(f"""
{GRAY}Befehle:
  /clear    Chat-Verlauf loeschen
  /quit     Beenden
  /help     Diese Hilfe{RESET}
""")
            continue

        messages.append({"role": "user", "content": user_input})
        response = stream_response(messages)

        if response:
            messages.append({"role": "assistant", "content": response})


if __name__ == "__main__":
    main()

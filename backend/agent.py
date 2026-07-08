"""
Xera AI — Agent entry point (backward-compatible wrapper)
All logic now lives in backend/agents/base.py.
"""

from collections.abc import AsyncGenerator
from .agents.base import run_multi_agent


async def run_agent(
    messages: list[dict],
    mode: str = "homelab",
    user_id: str = "",
    session_id: int | None = None,
    brain_override: str | None = None,
    agent_id: str | None = None,
    stop_event=None,
) -> AsyncGenerator[str, None]:
    """
    Main agent runner — routes to the multi-agent system.
    Keeps the original call signature for full backward compatibility with main.py.
    """
    async for event in run_multi_agent(
        messages=messages,
        mode=mode,
        user_id=user_id,
        session_id=session_id,
        brain_override=brain_override,
        agent_id=agent_id,
        stop_event=stop_event,
    ):
        yield event

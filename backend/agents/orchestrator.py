"""
Xera AI — Agent Orchestrator
Selects one or multiple agents for a given user message using keyword scoring.
"""

import re
from .registry import AGENTS

# Agents that can be combined for parallel execution when detected together
_PARALLEL_GROUPS = [
    {"document_write", "web_search"},
    {"document_write", "research"},
    {"code", "web_search"},
    {"code", "research"},
    {"document_write", "code"},
]

# Minimum score gap for an agent to be included in parallel (2nd agent must reach this)
_PARALLEL_MIN_SCORE = 2


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if p.get("type") == "text")
    return str(content or "")


def _score_agent(agent: dict, text: str) -> int:
    text_lower = text.lower()
    score = 0
    for kw in agent.get("keywords", []):
        kw_lower = kw.lower()
        if " " in kw_lower:
            if kw_lower in text_lower:
                score += len(kw_lower.split())
        else:
            if re.search(r"\b" + re.escape(kw_lower) + r"\b", text_lower):
                score += 1
    return score


def select_agent(messages: list[dict], tab: str = "homelab") -> str | None:
    """Single-agent selection (backwards-compatible). Returns agent_id or None."""
    agents = select_agents(messages, tab=tab)
    return agents[0] if agents else None


def select_agents(messages: list[dict], tab: str = "homelab") -> list[str]:
    """
    Returns a list of agent IDs to run (usually 1, up to 2 for parallel tasks).
    Falls back to ['incident_response'] (homelab) or [] (chat) if no match.
    """
    user_texts = []
    for m in messages[-8:]:
        if m.get("role") == "user":
            user_texts.append(_extract_text(m.get("content", "")))
    combined = " ".join(user_texts)

    if not combined.strip():
        return ["incident_response"] if tab == "homelab" else []

    # Score all eligible agents
    scores: dict[str, int] = {}
    for agent in AGENTS.values():
        agent_tab = agent.get("tab", "homelab")
        if tab == "homelab" and agent_tab not in ("homelab", "both"):
            continue
        if tab == "chat" and agent_tab not in ("chat", "both"):
            continue
        s = _score_agent(agent, combined)
        if s > 0:
            scores[agent["id"]] = s

    if not scores:
        return ["incident_response"] if tab == "homelab" else []

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_id, best_score = ranked[0]

    if best_score < 1:
        return ["incident_response"] if tab == "homelab" else []

    # Check if second agent qualifies for parallel execution
    if len(ranked) >= 2:
        second_id, second_score = ranked[1]
        if second_score >= _PARALLEL_MIN_SCORE:
            pair = {best_id, second_id}
            for group in _PARALLEL_GROUPS:
                if pair == group:
                    return [best_id, second_id]

    return [best_id]

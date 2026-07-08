import asyncio
import json
import logging
import httpx
from . import config
from . import database as db

logger = logging.getLogger(__name__)

_active_users: set[str] = set()

EXTRACT_PROMPT = """Analysiere diese Konversation und extrahiere 1-3 kurze Learnings.
Ein Learning ist etwas, das fuer zukuenftige Gespraeche mit diesem User nuetzlich waere.
Zum Beispiel: Vorlieben, haeufige Themen, Wissensniveau, Arbeitskontext.

Antworte NUR als JSON-Array:
[{"topic": "kurzes Thema", "learning": "kurze Erkenntnis"}]

Wenn es nichts Relevantes zu lernen gibt, antworte mit: []"""


def mark_active(user_id: str):
    _active_users.add(user_id)


def mark_idle(user_id: str):
    _active_users.discard(user_id)


def is_active(user_id: str) -> bool:
    return user_id in _active_users


async def extract_learnings(user_id: str, session_id: int | None, messages: list[dict]):
    if not messages or len(messages) < 4:
        return
    await asyncio.sleep(5)
    if is_active(user_id):
        return

    def _text(c):
        if isinstance(c, list):
            return " ".join(p.get("text", "") for p in c if p.get("type") == "text")
        return c or ""

    conversation = "\n".join(
        f"{m['role'].upper()}: {_text(m.get('content', ''))[:300]}"
        for m in messages[-10:]
        if m.get("content")
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{config.LLAMA_FAST_URL}/v1/chat/completions",
                json={
                    "model": "xera-ai",
                    "messages": [
                        {"role": "system", "content": EXTRACT_PROMPT},
                        {"role": "user", "content": conversation},
                    ],
                    "max_tokens": 256,
                    "temperature": 0.3,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"].get("content", "").strip()

        if is_active(user_id):
            return

        start = content.find("[")
        end = content.rfind("]") + 1
        if start >= 0 and end > start:
            learnings = json.loads(content[start:end])
        else:
            return

        for item in learnings[:3]:
            topic = item.get("topic", "").strip()[:100]
            learning = item.get("learning", "").strip()[:500]
            if topic and learning:
                db.save_learning(user_id, session_id, topic, learning)
                logger.info(f"Learning saved: [{topic}] {learning[:80]}...")

    except Exception as e:
        logger.debug(f"Learning extraction failed: {e}")


def get_learnings_context(user_id: str) -> str:
    learnings = db.get_recent_learnings(user_id, limit=8)
    if not learnings:
        return ""
    lines = ["Deine bisherigen Learnings ueber diesen User:"]
    for l in learnings:
        lines.append(f"- [{l['topic']}] {l['learning']}")
    return "\n".join(lines)

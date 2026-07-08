"""Unit tests for backend/agents/orchestrator.py"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import patch, MagicMock
import pytest


# Minimal AGENTS registry mock for testing orchestrator logic
MOCK_AGENTS = {
    "incident_response": {
        "id": "incident_response",
        "tab": "homelab",
        "keywords": ["alert", "fehler", "down", "crash", "error", "incident"],
    },
    "web_search": {
        "id": "web_search",
        "tab": "both",
        "keywords": ["suche", "search", "google", "web", "news", "aktuell"],
    },
    "document_write": {
        "id": "document_write",
        "tab": "both",
        "keywords": ["pdf", "dokument", "document", "bericht", "report", "erstelle dokument"],
    },
    "code": {
        "id": "code",
        "tab": "both",
        "keywords": ["python", "script", "code", "function", "debug", "bug fix"],
    },
}

with patch("backend.agents.registry.AGENTS", MOCK_AGENTS):
    from backend.agents.orchestrator import (
        _extract_text,
        _score_agent,
        select_agent,
        select_agents,
    )


class TestExtractText:
    def test_string_content(self):
        assert _extract_text("hello") == "hello"

    def test_list_content(self):
        content = [{"type": "text", "text": "hello"}, {"type": "text", "text": "world"}]
        assert _extract_text(content) == "hello world"

    def test_list_skips_non_text(self):
        content = [{"type": "image"}, {"type": "text", "text": "hi"}]
        assert _extract_text(content) == "hi"

    def test_none_content(self):
        assert _extract_text(None) == ""

    def test_empty_string(self):
        assert _extract_text("") == ""


class TestScoreAgent:
    def test_exact_keyword_match(self):
        agent = {"keywords": ["alert", "fehler"]}
        assert _score_agent(agent, "es gibt einen alert") == 1
        assert _score_agent(agent, "alert und fehler") == 2

    def test_case_insensitive(self):
        agent = {"keywords": ["Alert"]}
        assert _score_agent(agent, "es gibt ALERT") == 1

    def test_no_match(self):
        agent = {"keywords": ["python"]}
        assert _score_agent(agent, "hallo wie geht es") == 0

    def test_multi_word_keyword(self):
        agent = {"keywords": ["erstelle dokument"]}
        assert _score_agent(agent, "erstelle dokument bitte") == 2
        assert _score_agent(agent, "erstelle kein dokument") == 0

    def test_no_partial_match(self):
        agent = {"keywords": ["alert"]}
        assert _score_agent(agent, "alerting system") == 0

    def test_empty_keywords(self):
        agent = {"keywords": []}
        assert _score_agent(agent, "anything") == 0


class TestSelectAgent:
    def _msgs(self, text):
        return [{"role": "user", "content": text}]

    @patch("backend.agents.orchestrator.AGENTS", MOCK_AGENTS)
    def test_returns_none_for_empty(self):
        with patch("backend.agents.orchestrator.AGENTS", MOCK_AGENTS):
            result = select_agent([], tab="chat")
        assert result is None or result == "incident_response"

    @patch("backend.agents.orchestrator.AGENTS", MOCK_AGENTS)
    def test_web_search_chat(self):
        with patch("backend.agents.orchestrator.AGENTS", MOCK_AGENTS):
            result = select_agent(self._msgs("suche im web nach neuigkeiten"), tab="chat")
        assert result == "web_search"

    @patch("backend.agents.orchestrator.AGENTS", MOCK_AGENTS)
    def test_homelab_incident_fallback(self):
        with patch("backend.agents.orchestrator.AGENTS", MOCK_AGENTS):
            result = select_agent(self._msgs("wie geht es dir"), tab="homelab")
        assert result == "incident_response"

    @patch("backend.agents.orchestrator.AGENTS", MOCK_AGENTS)
    def test_code_agent(self):
        with patch("backend.agents.orchestrator.AGENTS", MOCK_AGENTS):
            result = select_agent(self._msgs("schreibe ein python script"), tab="chat")
        assert result == "code"

    @patch("backend.agents.orchestrator.AGENTS", MOCK_AGENTS)
    def test_document_agent(self):
        with patch("backend.agents.orchestrator.AGENTS", MOCK_AGENTS):
            result = select_agent(self._msgs("erstelle ein pdf dokument"), tab="chat")
        assert result == "document_write"

"""Unit tests for backend/router.py"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import patch
import pytest

# Mock config before importing router
with patch.dict("sys.modules", {"backend.config": type(sys)("config")}):
    pass

import backend.config as _cfg
_cfg.LLAMA_API_URL = "http://localhost:8080/v1/chat/completions"
_cfg.LLAMA_FAST_URL = "http://localhost:8081/v1/chat/completions"
_cfg.LLAMA_MINI_URL = "http://localhost:8082/v1/chat/completions"
_cfg.LLAMA_BIG_MODEL = "qwen3-30b"
_cfg.LLAMA_FAST_MODEL = "qwen3-8b"
_cfg.LLAMA_MINI_MODEL = "qwen3-mini"

from backend.router import classify_complexity, _FORCE_BIG_RE


def _user(text):
    return [{"role": "user", "content": text}]

def _conversation(user_text, with_prior_ai=False):
    msgs = []
    if with_prior_ai:
        msgs.append({"role": "user", "content": "erste frage"})
        msgs.append({"role": "assistant", "content": "antwort"})
    msgs.append({"role": "user", "content": user_text})
    return msgs


class TestForcesBigRe:
    def test_pdf_keyword(self):
        assert _FORCE_BIG_RE.search("erstelle ein PDF")
        assert _FORCE_BIG_RE.search("schreibe das als pdf")
        assert _FORCE_BIG_RE.search("dokument als PDF ausgeben")

    def test_docx_xlsx(self):
        assert _FORCE_BIG_RE.search("erstelle eine docx datei")
        assert _FORCE_BIG_RE.search("als xlsx exportieren")

    def test_no_match(self):
        assert not _FORCE_BIG_RE.search("hallo wie geht es dir")
        assert not _FORCE_BIG_RE.search("was ist 2+2")


class TestClassifyComplexity:
    def test_empty_messages_is_big(self):
        assert classify_complexity([]) == "big"

    def test_simple_greeting_is_fast(self):
        assert classify_complexity(_user("hallo")) == "fast"
        assert classify_complexity(_user("hey!")) == "fast"
        assert classify_complexity(_user("danke")) == "fast"
        assert classify_complexity(_user("ok")) == "fast"

    def test_simple_math_is_fast(self):
        assert classify_complexity(_user("was ist 5+3")) == "fast"

    def test_pdf_request_is_big(self):
        assert classify_complexity(_user("erstelle ein PDF Dokument")) == "big"

    def test_code_keyword_is_big(self):
        assert classify_complexity(_user("schreibe ein python script")) == "big"
        assert classify_complexity(_user("debug diesen code")) == "big"

    def test_long_message_is_big(self):
        long_msg = "a" * 301
        assert classify_complexity(_user(long_msg)) == "big"

    def test_prior_ai_response_forces_big(self):
        assert classify_complexity(_conversation("ok danke", with_prior_ai=True)) == "big"
        assert classify_complexity(_conversation("hallo", with_prior_ai=True)) == "big"

    def test_config_keyword_is_big(self):
        assert classify_complexity(_user("nginx konfiguration")) == "big"
        assert classify_complexity(_user("docker setup")) == "big"

    def test_short_unknown_is_fast(self):
        assert classify_complexity(_user("was ist heute?")) == "fast"

    def test_no_user_message(self):
        assert classify_complexity([{"role": "assistant", "content": "Hallo"}]) == "big"

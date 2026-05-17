"""Unit tests for LLM API retry logic and safe-shutdown checkpoint mechanism."""
from __future__ import annotations

import io
import json
import time
import threading
from typing import Any
from unittest.mock import MagicMock, patch, call
import urllib.error as urllib_error
import urllib.request as urllib_request

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ok_response(text: str = "hello", tool_calls: list | None = None) -> dict:
    msg: dict[str, Any] = {"role": "assistant", "content": text}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return {
        "choices": [{"finish_reason": "stop", "message": msg}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def _http_error(code: int) -> urllib_error.HTTPError:
    return urllib_error.HTTPError(
        url="http://x", code=code, msg=str(code), hdrs=None,
        fp=io.BytesIO(b'error body'),  # fp must not be None
    )


# ---------------------------------------------------------------------------
# Tests: gateway retry logic
# ---------------------------------------------------------------------------

class TestGatewayRetry:
    """Tests for exponential-backoff retry in invoke_model."""

    def _invoke(self, side_effects, max_retries: int = 2, allow_fallback: bool = False):
        """Call invoke_model with a mocked urlopen."""
        from yggdrasil_model_providers.gateway import invoke_model

        messages = [{"role": "user", "content": "ping"}]

        call_count = 0

        class FakeResponse:
            def __init__(self, data: bytes):
                self._data = data

            def read(self):
                return self._data

            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def readline(self):
                # Return the full body on first call (non-SSE path in _assemble_stream_response),
                # then empty bytes to signal EOF on subsequent calls.
                if self._data:
                    line, self._data = self._data, b""
                    return line
                return b""

        def fake_urlopen(req, timeout=None):
            nonlocal call_count
            if call_count >= len(side_effects):
                raise AssertionError(
                    f"fake_urlopen called too many times: call_count={call_count}, configured={len(side_effects)}"
                )
            effect = side_effects[call_count]
            call_count += 1
            if isinstance(effect, Exception):
                raise effect
            return FakeResponse(json.dumps(effect).encode("utf-8"))

        with (
            patch("yggdrasil_model_providers.gateway.urllib_request.urlopen", side_effect=fake_urlopen),
            patch("yggdrasil_model_providers.gateway._select_provider") as mock_provider,
            patch("yggdrasil_model_providers.gateway.time.sleep"),  # skip actual sleep
            patch.dict(
                "os.environ",
                {
                    "YGGDRASIL_LLM_RETRY_MAX": str(max_retries),
                    "YGGDRASIL_LLM_RETRY_BACKOFF_BASE": "1.0",
                    "YGGDRASIL_ALLOW_PAID_MODELS": "true",
                    "YGGDRASIL_LLM_API_KEY": "test-key",
                    "YGGDRASIL_LLM_PROVIDER": "openrouter",
                    "YGGDRASIL_DISABLE_LIVE_LLM": "0",  # ensure live mode
                },
            ),
        ):
            from yggdrasil_model_providers.gateway import ProviderConfig
            mock_provider.return_value = ProviderConfig(
                provider="openrouter",
                api_key="test-key",
                base_url="https://openrouter.ai/api/v1",
                default_model="gpt-4o",
                quality=0.9,
                cost_per_1k_input=0.01,
                cost_per_1k_output=0.01,
                latency_ms=1000,
                context_window=128000,
                free_tier=True,
                priority=10,
            )
            return invoke_model(
                requested_model="gpt-4o",
                requested_provider="openrouter",
                messages=messages,
                allow_fallback=allow_fallback,
            ), call_count

    def test_succeeds_first_attempt(self):
        result, attempts = self._invoke([_make_ok_response("world")])
        assert result["outputText"] == "world"
        assert attempts == 1

    def test_retries_on_network_error_then_succeeds(self):
        result, attempts = self._invoke(
            [ConnectionError("reset"), _make_ok_response("ok")],
            max_retries=2,
        )
        assert result["mode"] == "live"
        assert attempts == 2

    def test_retries_on_429_then_succeeds(self):
        result, attempts = self._invoke(
            [_http_error(429), _make_ok_response("ok-after-429")],
            max_retries=2,
        )
        assert result["mode"] == "live"
        assert attempts == 2

    def test_retries_on_503_then_succeeds(self):
        result, attempts = self._invoke(
            [_http_error(503), _make_ok_response("ok-after-503")],
            max_retries=2,
        )
        assert result["mode"] == "live"
        assert attempts == 2

    def test_exhaust_retries_falls_back(self):
        result, attempts = self._invoke(
            [ConnectionError("x"), ConnectionError("x"), ConnectionError("x")],
            max_retries=2,
            allow_fallback=True,
        )
        assert result["mode"] == "fallback"
        assert attempts == 3  # 1 initial + 2 retries

    def test_no_retry_on_404(self):
        """4xx (except 429) errors should NOT be retried."""
        result, attempts = self._invoke(
            [_http_error(404), _make_ok_response("should-not-reach")],
            max_retries=2,
            allow_fallback=True,
        )
        assert result["mode"] == "fallback"
        assert attempts == 1  # stops immediately on 404


# ---------------------------------------------------------------------------
# Tests: shutdown_control
# ---------------------------------------------------------------------------

class TestShutdownControl:
    """Tests for the thread-safe shutdown flag."""

    def setup_method(self):
        from yggdrasil_sdk.runtime_kernel.shutdown_control import clear_shutdown
        clear_shutdown()

    def teardown_method(self):
        from yggdrasil_sdk.runtime_kernel.shutdown_control import clear_shutdown
        clear_shutdown()

    def test_initially_not_requested(self):
        from yggdrasil_sdk.runtime_kernel.shutdown_control import is_shutdown_requested
        assert not is_shutdown_requested()

    def test_request_sets_flag(self):
        from yggdrasil_sdk.runtime_kernel.shutdown_control import request_shutdown, is_shutdown_requested
        request_shutdown()
        assert is_shutdown_requested()

    def test_clear_resets_flag(self):
        from yggdrasil_sdk.runtime_kernel.shutdown_control import request_shutdown, is_shutdown_requested, clear_shutdown
        request_shutdown()
        clear_shutdown()
        assert not is_shutdown_requested()

    def test_thread_safe_concurrent_set(self):
        """Multiple threads setting the flag should all succeed."""
        from yggdrasil_sdk.runtime_kernel.shutdown_control import request_shutdown, is_shutdown_requested
        threads = [threading.Thread(target=request_shutdown) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert is_shutdown_requested()


# ---------------------------------------------------------------------------
# Tests: SafeShutdownInterrupt exception
# ---------------------------------------------------------------------------

class TestSafeShutdownInterrupt:
    """Tests for SafeShutdownInterrupt exception dataclass-like behaviour."""

    def test_attributes_preserved(self):
        from yggdrasil_sdk.llm_runtime import SafeShutdownInterrupt
        exc = SafeShutdownInterrupt(
            pending_tool_calls=[{"name": "create_file", "arguments": {}, "id": "tc1"}],
            conversation_messages=[{"role": "user", "content": "go"}],
            invocation_id="inv_abc",
            round_index=2,
            usage_totals={"inputTokens": 100, "outputTokens": 50, "totalTokens": 150},
            accumulated_cost=0.001,
            round_summaries=[],
            round_modes=[],
            assistant_tool_calls_payload=[],
        )
        assert exc.round_index == 2
        assert exc.invocation_id == "inv_abc"
        assert len(exc.pending_tool_calls) == 1
        assert exc.pending_tool_calls[0]["name"] == "create_file"

    def test_is_exception(self):
        from yggdrasil_sdk.llm_runtime import SafeShutdownInterrupt
        exc = SafeShutdownInterrupt(
            pending_tool_calls=[],
            conversation_messages=[],
            invocation_id="x",
            round_index=0,
            usage_totals={},
            accumulated_cost=0.0,
            round_summaries=[],
            round_modes=[],
            assistant_tool_calls_payload=[],
        )
        assert isinstance(exc, Exception)
        assert "round 0" in str(exc).lower() or "pending" in str(exc).lower()


def test_execute_resumed_tool_calls_inserts_assistant_tool_bridge_message(monkeypatch) -> None:
    from yggdrasil_sdk import llm_runtime

    def _fake_execute_registered_tool(name, arguments, **kwargs):
        return {
            "tool": {"name": name},
            "arguments": arguments,
            "result": {"status": "ok", "path": arguments.get("path")},
        }

    monkeypatch.setattr(llm_runtime, "execute_registered_tool", _fake_execute_registered_tool)

    conversation_messages = [{"role": "user", "content": "resume pending tools"}]
    tool_executions: list[dict[str, Any]] = []
    pending_tool_calls = [
        {
            "id": "call_resume_readme",
            "name": "mcp.read.read_file",
            "arguments": {"path": "README.md"},
            "argumentsText": '{"path": "README.md"}',
        }
    ]

    llm_runtime._execute_resumed_tool_calls(
        tool_calls=pending_tool_calls,
        conversation_messages=conversation_messages,
        tool_executions=tool_executions,
        assistant_message=None,
        task=object(),
        run=object(),
        root_mount={},
        current_context=[],
    )

    assert conversation_messages[1]["role"] == "assistant"
    assert conversation_messages[1]["tool_calls"][0]["id"] == "call_resume_readme"
    assert conversation_messages[1]["tool_calls"][0]["function"]["name"] == "mcp.read.read_file"
    assert conversation_messages[2]["role"] == "tool"
    assert conversation_messages[2]["tool_call_id"] == "call_resume_readme"
    assert len(tool_executions) == 1
    assert tool_executions[0]["toolCallId"] == "call_resume_readme"


def test_execute_resumed_tool_calls_preserves_reasoning_content_when_restoring_assistant_message(monkeypatch) -> None:
    from yggdrasil_sdk import llm_runtime

    def _fake_execute_registered_tool(name, arguments, **kwargs):
        return {
            "tool": {"name": name},
            "arguments": arguments,
            "result": {"status": "ok", "path": arguments.get("path")},
        }

    monkeypatch.setattr(llm_runtime, "execute_registered_tool", _fake_execute_registered_tool)

    conversation_messages = [{"role": "user", "content": "resume pending tools"}]
    tool_executions: list[dict[str, Any]] = []
    pending_tool_calls = [
        {
            "id": "call_resume_note_index",
            "name": "mcp.read.read_file",
            "arguments": {"path": "note_index.py"},
            "argumentsText": '{"path": "note_index.py"}',
        }
    ]
    assistant_message = {
        "role": "assistant",
        "content": "",
        "reasoning_content": "先恢复上轮 thinking，再执行 pending tool calls。",
        "tool_calls": [
            {
                "id": "call_resume_note_index",
                "type": "function",
                "function": {
                    "name": "mcp.read.read_file",
                    "arguments": '{"path": "note_index.py"}',
                },
            }
        ],
    }

    llm_runtime._execute_resumed_tool_calls(
        tool_calls=pending_tool_calls,
        conversation_messages=conversation_messages,
        tool_executions=tool_executions,
        assistant_message=assistant_message,
        task=object(),
        run=object(),
        root_mount={},
        current_context=[],
    )

    assert conversation_messages[1]["reasoning_content"] == "先恢复上轮 thinking，再执行 pending tool calls。"
    assert conversation_messages[1]["tool_calls"][0]["id"] == "call_resume_note_index"
    assert conversation_messages[2]["tool_call_id"] == "call_resume_note_index"

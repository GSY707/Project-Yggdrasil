from __future__ import annotations

import json

from yggdrasil_model_providers import gateway
from yggdrasil_sdk.llm_runtime import _assistant_tool_round_message


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload
        self._consumed = False

    def read(self) -> bytes:
        if self._consumed:
            return b""
        self._consumed = True
        return json.dumps(self._payload).encode("utf-8")

    def readline(self) -> bytes:
        if self._consumed:
            return b""
        self._consumed = True
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeStreamingResponse:
    def __init__(self, events: list[dict[str, object]]) -> None:
        self._lines = [f"data: {json.dumps(event, ensure_ascii=False)}\n".encode("utf-8") for event in events]
        self._lines.append(b"data: [DONE]\n")

    def readline(self) -> bytes:
        if not self._lines:
            return b""
        return self._lines.pop(0)

    def read(self) -> bytes:
        remaining = b"".join(self._lines)
        self._lines.clear()
        return remaining

    def __enter__(self) -> _FakeStreamingResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_get_provider_catalog_exposes_deepseek_v4_candidates(monkeypatch) -> None:
    monkeypatch.delenv("YGGDRASIL_DISABLE_LIVE_LLM", raising=False)
    monkeypatch.setenv("YGGDRASIL_ALLOW_PAID_MODELS", "1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek")
    monkeypatch.delenv("YGGDRASIL_LLM_MODEL_DEEPSEEK_DIRECT", raising=False)

    candidates = [
        candidate
        for candidate in gateway.get_provider_catalog()
        if candidate.get("provider") == "deepseek_direct"
    ]

    assert [candidate["model"] for candidate in candidates] == ["deepseek-v4-flash", "deepseek-v4-pro"]
    assert candidates[0]["contextWindow"] == 1_000_000
    assert candidates[0]["costPer1k"] == 0.003
    assert candidates[1]["costPer1k"] == 0.009


def test_invoke_model_includes_deepseek_thinking_and_returns_reasoning_content(monkeypatch) -> None:
    monkeypatch.delenv("YGGDRASIL_DISABLE_LIVE_LLM", raising=False)
    monkeypatch.setenv("YGGDRASIL_ALLOW_PAID_MODELS", "1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek")

    captured: dict[str, object] = {}

    def _fake_urlopen(request, timeout=90):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        aliased_tool_name = captured["payload"]["tools"][0]["function"]["name"]
        return _FakeResponse(
            {
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": "让我先调用工具。",
                            "reasoning_content": "先获取时间，再查询天气。",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": aliased_tool_name,
                                        "arguments": "{}",
                                    },
                                }
                            ],
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 1000,
                    "completion_tokens": 500,
                    "total_tokens": 1500,
                    "completion_tokens_details": {"reasoning_tokens": 120},
                },
            }
        )

    monkeypatch.setattr(gateway.urllib_request, "urlopen", _fake_urlopen)

    result = gateway.invoke_model(
        requested_model="deepseek-reasoner",
        requested_provider="deepseek_direct",
        messages=[{"role": "user", "content": "杭州明天天气如何？"}],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "text_memory.retrieve",
                    "description": "检索相关记忆",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
        reasoning_effort="medium",
        allow_fallback=False,
    )

    request_payload = captured["payload"]
    assert request_payload["model"] == "deepseek-v4-pro"
    assert request_payload["thinking"] == {"type": "enabled"}
    assert request_payload["reasoning_effort"] == "high"
    assert request_payload["tools"][0]["function"]["name"] == "deepseek_tool_1_text_memory_retrieve"
    assert result["model"] == "deepseek-v4-pro"
    assert result["reasoningContent"] == "先获取时间，再查询天气。"
    assert result["toolCalls"][0]["name"] == "text_memory.retrieve"
    assert result["costUsed"] == 0.006
    assert result["usage"]["cacheHitInputTokens"] == 0
    assert result["usage"]["cacheWriteInputTokens"] == 0
    assert result["usage"]["nonCacheInputTokens"] == 1000
    assert result["usage"]["reasoningTokens"] == 120


def test_invoke_model_normalizes_cache_token_usage(monkeypatch) -> None:
    monkeypatch.delenv("YGGDRASIL_DISABLE_LIVE_LLM", raising=False)
    monkeypatch.setenv("LONGCAT_API_KEY", "test-longcat")

    def _fake_urlopen(_request, timeout=90):
        return _FakeResponse(
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": "已完成。",
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 3200,
                    "completion_tokens": 400,
                    "total_tokens": 3600,
                    "cache_read_input_tokens": 2400,
                    "cache_creation_input_tokens": 300,
                },
            }
        )

    monkeypatch.setattr(gateway.urllib_request, "urlopen", _fake_urlopen)

    result = gateway.invoke_model(
        requested_model="LongCat-Flash-Lite",
        requested_provider="longcat",
        messages=[{"role": "user", "content": "输出执行计划。"}],
        allow_fallback=False,
    )

    assert result["usage"] == {
        "inputTokens": 3200,
        "outputTokens": 400,
        "totalTokens": 3600,
        "cacheHitInputTokens": 2400,
        "cacheWriteInputTokens": 300,
        "nonCacheInputTokens": 800,
        "reasoningTokens": 0,
    }


def test_assistant_tool_round_message_preserves_reasoning_content() -> None:
    message = _assistant_tool_round_message(
        {
            "outputText": "让我先调用工具。",
            "reasoningContent": "先想清楚参数，再发起工具调用。",
        },
        [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "get_date", "arguments": "{}"},
            }
        ],
    )

    assert message["role"] == "assistant"
    assert message["tool_calls"][0]["function"]["name"] == "get_date"
    assert message["reasoning_content"] == "先想清楚参数，再发起工具调用。"


def test_provider_catalog_ignores_llm_txt_documentation_file(tmp_path, monkeypatch) -> None:
    for env_name in [
        "YGGDRASIL_DISABLE_LIVE_LLM",
        "YGGDRASIL_ALLOW_PAID_MODELS",
        "YGGDRASIL_LLM_API_KEY",
        "YGGDRASIL_LLM_PROVIDER",
        "YGGDRASIL_LLM_API_KEY_LONGCAT",
        "YGGDRASIL_LLM_API_KEY_OPENROUTER",
        "YGGDRASIL_LLM_API_KEY_DEEPSEEK",
        "YGGDRASIL_LLM_API_KEY_VECTORENGINE",
        "LONGCAT_API_KEY",
        "OPENROUTER_API_KEY",
        "DEEPSEEK_API_KEY",
        "VECTORENGINE_API_KEY",
    ]:
        monkeypatch.delenv(env_name, raising=False)

    (tmp_path / "LLM.txt").write_text(
        'api_keys:\n  deepseek_direct: "sk-placeholder"\n',
        encoding="utf-8",
    )

    assert gateway.get_provider_catalog(workspace_root=tmp_path) == []


def test_invoke_model_streaming_captures_first_token_latency(monkeypatch) -> None:
    monkeypatch.delenv("YGGDRASIL_DISABLE_LIVE_LLM", raising=False)
    monkeypatch.setenv("LONGCAT_API_KEY", "test-longcat")

    captured: dict[str, object] = {}

    def _fake_urlopen(request, timeout=90):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _FakeStreamingResponse(
            [
                {
                    "id": "chatcmpl-1",
                    "object": "chat.completion.chunk",
                    "model": "LongCat-Flash-Lite",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"role": "assistant", "content": "你好"},
                            "finish_reason": None,
                        }
                    ],
                },
                {
                    "id": "chatcmpl-1",
                    "object": "chat.completion.chunk",
                    "model": "LongCat-Flash-Lite",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": "，世界"},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 12,
                        "completion_tokens": 8,
                        "total_tokens": 20,
                    },
                },
            ]
        )

    monkeypatch.setattr(gateway.urllib_request, "urlopen", _fake_urlopen)

    result = gateway.invoke_model(
        requested_model="LongCat-Flash-Lite",
        requested_provider="longcat",
        messages=[{"role": "user", "content": "打个招呼"}],
        allow_fallback=False,
    )

    request_payload = captured["payload"]
    assert request_payload["stream"] is True
    assert result["outputText"] == "你好，世界"
    assert result["firstTokenLatencyMs"] is not None
    assert result["firstTokenLatencyMs"] >= 0
    assert result["rawResponse"]["stream"] is True
    assert result["usage"]["totalTokens"] == 20
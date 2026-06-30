from __future__ import annotations

import json
import ssl

import pytest

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


class _BrokenStreamingResponse:
    def readline(self) -> bytes:
        raise TimeoutError("provider stream stopped producing bytes")

    def read(self) -> bytes:
        return b""

    def __enter__(self) -> _BrokenStreamingResponse:
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
    assert candidates[0]["maxOutputTokens"] == 384000
    assert candidates[0]["costPer1k"] == 0.003
    assert candidates[1]["maxOutputTokens"] == 384000
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
        requested_model="deepseek-v4-pro",
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
        allow_fallback=False,
    )

    request_payload = captured["payload"]
    assert request_payload["model"] == "deepseek-v4-pro"
    assert request_payload["max_tokens"] == 384000
    assert request_payload["thinking"] == {"type": "enabled"}
    assert request_payload["reasoning_effort"] == "max"
    assert request_payload["tools"][0]["function"]["name"] == "deepseek_tool_1_text_memory_retrieve"
    assert result["model"] == "deepseek-v4-pro"
    assert result["reasoningContent"] == "先获取时间，再查询天气。"
    assert result["toolCalls"][0]["name"] == "text_memory.retrieve"
    assert result["costUsed"] == 0.006
    assert result["usage"]["cacheHitInputTokens"] == 0
    assert result["usage"]["cacheWriteInputTokens"] == 0
    assert result["usage"]["nonCacheInputTokens"] == 1000
    assert result["usage"]["reasoningTokens"] == 120


def test_invoke_model_rejects_deprecated_deepseek_model_names(monkeypatch) -> None:
    monkeypatch.delenv("YGGDRASIL_DISABLE_LIVE_LLM", raising=False)
    monkeypatch.setenv("YGGDRASIL_ALLOW_PAID_MODELS", "1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek")

    with pytest.raises(ValueError, match="deprecated"):
        gateway.invoke_model(
            requested_model="deepseek-reasoner",
            requested_provider="deepseek_direct",
            messages=[{"role": "user", "content": "test"}],
            allow_fallback=False,
        )


def test_invoke_model_normalizes_cache_token_usage(monkeypatch) -> None:
    monkeypatch.delenv("YGGDRASIL_DISABLE_LIVE_LLM", raising=False)
    monkeypatch.setenv("LONGCAT_API_KEY", "test-longcat")
    captured: dict[str, object] = {}

    def _fake_urlopen(request, timeout=90):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
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
        requested_model="LongCat-2.0",
        requested_provider="longcat",
        messages=[{"role": "user", "content": "输出执行计划。"}],
        allow_fallback=False,
    )

    assert captured["payload"]["max_tokens"] == 128000
    assert result["usage"] == {
        "inputTokens": 3200,
        "outputTokens": 400,
        "totalTokens": 3600,
        "cacheHitInputTokens": 2400,
        "cacheWriteInputTokens": 300,
        "nonCacheInputTokens": 800,
        "reasoningTokens": 0,
    }


def test_invoke_model_prefers_nested_positive_cache_tokens_over_top_level_zero(monkeypatch) -> None:
    monkeypatch.delenv("YGGDRASIL_DISABLE_LIVE_LLM", raising=False)
    monkeypatch.setenv("LONGCAT_API_KEY", "test-longcat")

    def _fake_urlopen(_request, timeout=90):
        return _FakeResponse(
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "已完成。"},
                    }
                ],
                "usage": {
                    "effectiveCachedTokens": 34560,
                    "prompt_tokens": 40782,
                    "completion_tokens": 2970,
                    "total_tokens": 43752,
                    "prompt_tokens_details": {"cached_tokens": 34560},
                    "cache_read_tokens": 0,
                    "cache_write_tokens": 0,
                    "cached_tokens": 0,
                },
            }
        )

    monkeypatch.setattr(gateway.urllib_request, "urlopen", _fake_urlopen)

    result = gateway.invoke_model(
        requested_model="LongCat-2.0",
        requested_provider="longcat",
        messages=[{"role": "user", "content": "输出执行计划。"}],
        allow_fallback=False,
    )

    assert result["usage"]["cacheHitInputTokens"] == 34560
    assert result["usage"]["nonCacheInputTokens"] == 6222


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
                    "model": "LongCat-2.0",
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
                    "model": "LongCat-2.0",
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
        requested_model="LongCat-2.0",
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


def test_invoke_model_retries_stalled_deepseek_stream_with_reconnect_telemetry(monkeypatch) -> None:
    monkeypatch.delenv("YGGDRASIL_DISABLE_LIVE_LLM", raising=False)
    monkeypatch.setenv("YGGDRASIL_ALLOW_PAID_MODELS", "1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek")
    monkeypatch.setenv("YGGDRASIL_LLM_RETRY_BACKOFF_BASE", "0")
    monkeypatch.setenv("YGGDRASIL_LLM_STREAM_IDLE_TIMEOUT_SECONDS", "7")

    captured_payloads: list[dict[str, object]] = []
    captured_timeouts: list[int] = []

    def _fake_urlopen(request, timeout=90):
        captured_payloads.append(json.loads(request.data.decode("utf-8")))
        captured_timeouts.append(timeout)
        if len(captured_payloads) == 1:
            return _BrokenStreamingResponse()
        return _FakeResponse(
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "恢复成功。"},
                    }
                ],
                "usage": {
                    "prompt_tokens": 40,
                    "completion_tokens": 10,
                    "total_tokens": 50,
                },
            }
        )

    monkeypatch.setattr(gateway.urllib_request, "urlopen", _fake_urlopen)

    result = gateway.invoke_model(
        requested_model="deepseek-v4-flash",
        requested_provider="deepseek_direct",
        messages=[{"role": "user", "content": "测试流式断开后重连"}],
        allow_fallback=False,
    )

    assert captured_payloads[0]["stream"] is True
    assert captured_payloads[1]["stream"] is False
    assert captured_timeouts == [7, 7]
    assert result["outputText"] == "恢复成功。"
    assert result["rawResponse"]["streamReconnect"]["attempts"] == 1
    retry_event = result["rawResponse"]["streamReconnect"]["events"][0]
    assert retry_event["stream"] is True
    assert retry_event["errorType"] == "TimeoutError"
    assert retry_event["idleTimeoutSeconds"] == 7


def test_invoke_model_raises_smaller_runtime_max_tokens_to_model_limit(monkeypatch) -> None:
    monkeypatch.delenv("YGGDRASIL_DISABLE_LIVE_LLM", raising=False)
    monkeypatch.setenv("YGGDRASIL_ALLOW_PAID_MODELS", "1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek")

    captured: dict[str, object] = {}

    def _fake_urlopen(request, timeout=90):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse(
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "已完成。"},
                    }
                ],
                "usage": {
                    "prompt_tokens": 20,
                    "completion_tokens": 8,
                    "total_tokens": 28,
                },
            }
        )

    monkeypatch.setattr(gateway.urllib_request, "urlopen", _fake_urlopen)

    result = gateway.invoke_model(
        requested_model="deepseek-v4-flash",
        requested_provider="deepseek_direct",
        messages=[{"role": "user", "content": "测试 max_tokens"}],
        max_tokens=9000,
        allow_fallback=False,
    )

    assert result["outputText"] == "已完成。"
    assert captured["payload"]["max_tokens"] == 384000
    assert captured["payload"]["yggdrasil_requested_max_tokens"] == 9000


def test_invoke_model_extracts_output_text_from_block_content(monkeypatch) -> None:
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
                            "content": [
                                {"type": "output_text", "text": "任务价值判断：高价值"},
                                {"type": "text", "text": "acceptance 对照结论：等价"},
                            ],
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 16,
                    "total_tokens": 26,
                },
            }
        )

    monkeypatch.setattr(gateway.urllib_request, "urlopen", _fake_urlopen)

    result = gateway.invoke_model(
        requested_model="LongCat-2.0",
        requested_provider="longcat",
        messages=[{"role": "user", "content": "给出最终结论。"}],
        allow_fallback=False,
    )

    assert result["outputText"] == "任务价值判断：高价值\nacceptance 对照结论：等价"


def test_invoke_model_extracts_top_level_output_payload(monkeypatch) -> None:
    monkeypatch.delenv("YGGDRASIL_DISABLE_LIVE_LLM", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek")
    monkeypatch.setenv("YGGDRASIL_ALLOW_PAID_MODELS", "1")

    def _fake_urlopen(_request, timeout=90):
        return _FakeResponse(
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": []},
                    }
                ],
                "output": [
                    {"type": "output_text", "text": "风险与下一步：继续补齐 live 证据。"}
                ],
                "usage": {
                    "prompt_tokens": 11,
                    "completion_tokens": 9,
                    "total_tokens": 20,
                },
            }
        )

    monkeypatch.setattr(gateway.urllib_request, "urlopen", _fake_urlopen)

    result = gateway.invoke_model(
        requested_model="deepseek-v4-pro",
        requested_provider="deepseek_direct",
        messages=[{"role": "user", "content": "输出风险与下一步。"}],
        allow_fallback=False,
    )

    assert result["outputText"] == "风险与下一步：继续补齐 live 证据。"


def test_invoke_model_extracts_tool_call_from_block_payload(monkeypatch) -> None:
    monkeypatch.delenv("YGGDRASIL_DISABLE_LIVE_LLM", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek")
    monkeypatch.setenv("YGGDRASIL_ALLOW_PAID_MODELS", "1")

    def _fake_urlopen(_request, timeout=90):
        return _FakeResponse(
            {
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "function_call",
                                    "name": "text_memory.retrieve",
                                    "arguments": '{"query":"window parity"}',
                                    "id": "call_block_1",
                                }
                            ],
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 50,
                    "completion_tokens": 12,
                    "total_tokens": 62,
                },
            }
        )

    monkeypatch.setattr(gateway.urllib_request, "urlopen", _fake_urlopen)

    result = gateway.invoke_model(
        requested_model="deepseek-v4-pro",
        requested_provider="deepseek_direct",
        messages=[{"role": "user", "content": "先检索再回答。"}],
        allow_fallback=False,
    )

    assert result["toolCalls"][0]["name"] == "text_memory.retrieve"
    assert result["toolCalls"][0]["arguments"] == {"query": "window parity"}


def test_invoke_model_streaming_extracts_block_content_and_tool_calls(monkeypatch) -> None:
    monkeypatch.delenv("YGGDRASIL_DISABLE_LIVE_LLM", raising=False)
    monkeypatch.setenv("LONGCAT_API_KEY", "test-longcat")

    def _fake_urlopen(_request, timeout=90):
        return _FakeStreamingResponse(
            [
                {
                    "id": "chatcmpl-block-1",
                    "object": "chat.completion.chunk",
                    "model": "LongCat-2.0",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {
                                "content": [{"type": "output_text", "text": "任务价值判断：高价值"}],
                            },
                            "finish_reason": None,
                        }
                    ],
                },
                {
                    "id": "chatcmpl-block-1",
                    "object": "chat.completion.chunk",
                    "model": "LongCat-2.0",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {
                                "content": [
                                    {
                                        "type": "function_call",
                                        "name": "mcp.read.read_file",
                                        "arguments": '{"path":"docs/DIRECTORY_REFERENCE.md"}',
                                        "id": "call_stream_1",
                                    }
                                ],
                            },
                            "finish_reason": "tool_calls",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 20,
                        "completion_tokens": 10,
                        "total_tokens": 30,
                    },
                },
            ]
        )

    monkeypatch.setattr(gateway.urllib_request, "urlopen", _fake_urlopen)

    result = gateway.invoke_model(
        requested_model="LongCat-2.0",
        requested_provider="longcat",
        messages=[{"role": "user", "content": "先读目录说明，再回答。"}],
        allow_fallback=False,
    )

    assert result["outputText"] == "任务价值判断：高价值"
    assert result["toolCalls"][0]["name"] == "mcp.read.read_file"
    assert result["toolCalls"][0]["arguments"] == {"path": "docs/DIRECTORY_REFERENCE.md"}


def test_invoke_model_streaming_merges_split_tool_call_arguments(monkeypatch) -> None:
    monkeypatch.delenv("YGGDRASIL_DISABLE_LIVE_LLM", raising=False)
    monkeypatch.setenv("LONGCAT_API_KEY", "test-longcat")

    def _fake_urlopen(_request, timeout=90):
        return _FakeStreamingResponse(
            [
                {
                    "id": "chatcmpl-split-1",
                    "object": "chat.completion.chunk",
                    "model": "LongCat-2.0",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "id": "call_split_1",
                                        "type": "function",
                                        "function": {
                                            "name": "mcp.web.search_web",
                                        },
                                    }
                                ],
                            },
                            "finish_reason": None,
                        }
                    ],
                },
                {
                    "id": "chatcmpl-split-1",
                    "object": "chat.completion.chunk",
                    "model": "LongCat-2.0",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "function": {
                                            "arguments": '{"query":"double descent 2024 survey"}',
                                        },
                                    }
                                ],
                            },
                            "finish_reason": "tool_calls",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 20,
                        "completion_tokens": 10,
                        "total_tokens": 30,
                    },
                },
            ]
        )

    monkeypatch.setattr(gateway.urllib_request, "urlopen", _fake_urlopen)

    result = gateway.invoke_model(
        requested_model="LongCat-2.0",
        requested_provider="longcat",
        messages=[{"role": "user", "content": "先检索 double descent 的最新综述。"}],
        allow_fallback=False,
    )

    assert result["toolCalls"][0]["name"] == "mcp.web.search_web"
    assert result["toolCalls"][0]["arguments"] == {"query": "double descent 2024 survey"}


def test_invoke_model_extracts_longcat_tagged_tool_calls(monkeypatch) -> None:
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
                            "content": (
                                "先读取关键证据文件，再产出最终发布简报。\n"
                                "<longcat_tool_call>mcp.read.read_file\n"
                                "<longcat_arg_key>file_path</longcat_arg_key>\n"
                                "<longcat_arg_value>docs/DIRECTORY_REFERENCE.md</longcat_arg_value>\n"
                                "</longcat_tool_call>"
                            ),
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 20,
                    "completion_tokens": 10,
                    "total_tokens": 30,
                },
            }
        )

    monkeypatch.setattr(gateway.urllib_request, "urlopen", _fake_urlopen)

    result = gateway.invoke_model(
        requested_model="LongCat-2.0",
        requested_provider="longcat",
        messages=[{"role": "user", "content": "先读证据再回答。"}],
        allow_fallback=False,
    )

    assert result["outputText"] == "先读取关键证据文件，再产出最终发布简报。"
    assert result["toolCalls"][0]["name"] == "mcp.read.read_file"
    assert result["toolCalls"][0]["arguments"] == {"path": "docs/DIRECTORY_REFERENCE.md"}


def test_invoke_model_extracts_inline_xml_tool_tags(monkeypatch) -> None:
    monkeypatch.delenv("YGGDRASIL_DISABLE_LIVE_LLM", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek")
    monkeypatch.setenv("YGGDRASIL_ALLOW_PAID_MODELS", "1")

    def _fake_urlopen(_request, timeout=90):
        return _FakeResponse(
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": (
                                "正在扫描仓库关键结构，为最终判断收集跨表面证据。\n"
                                '<mcp.read.list_directory path="docs" recursive="false"/>\n'
                                '<mcp.read.read_file file_path="README.md" start_line="1" end_line="20"/>'
                            ),
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 24,
                    "completion_tokens": 18,
                    "total_tokens": 42,
                },
            }
        )

    monkeypatch.setattr(gateway.urllib_request, "urlopen", _fake_urlopen)

    result = gateway.invoke_model(
        requested_model="deepseek-v4-pro",
        requested_provider="deepseek_direct",
        messages=[{"role": "user", "content": "扫描关键证据。"}],
        allow_fallback=False,
    )

    assert result["outputText"] == "正在扫描仓库关键结构，为最终判断收集跨表面证据。"
    assert [call["name"] for call in result["toolCalls"]] == ["mcp.read.list_directory", "mcp.read.read_file"]
    assert result["toolCalls"][0]["arguments"] == {"path": "docs", "recursive": False}
    assert result["toolCalls"][1]["arguments"] == {"path": "README.md", "startLine": 1, "endLine": 20}


def test_invoke_model_extracts_block_xml_tool_calls(monkeypatch) -> None:
    monkeypatch.delenv("YGGDRASIL_DISABLE_LIVE_LLM", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek")
    monkeypatch.setenv("YGGDRASIL_ALLOW_PAID_MODELS", "1")

    def _fake_urlopen(_request, timeout=90):
        return _FakeResponse(
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": (
                                "首先扫描当前仓库结构以收集证据。\n"
                                "<tool_calls>\n"
                                "<mcp.read.list_directory><path>.</path><recursive>false</recursive></mcp.read.list_directory>\n"
                                "<mcp.read.read_file><file_path>README.md</file_path><start_line>1</start_line><end_line>20</end_line></mcp.read.read_file>\n"
                                "</tool_calls>"
                            ),
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 24,
                    "completion_tokens": 18,
                    "total_tokens": 42,
                },
            }
        )

    monkeypatch.setattr(gateway.urllib_request, "urlopen", _fake_urlopen)

    result = gateway.invoke_model(
        requested_model="deepseek-v4-pro",
        requested_provider="deepseek_direct",
        messages=[{"role": "user", "content": "扫描关键证据。"}],
        allow_fallback=False,
    )

    assert result["outputText"] == "首先扫描当前仓库结构以收集证据。"
    assert [call["name"] for call in result["toolCalls"]] == ["mcp.read.list_directory", "mcp.read.read_file"]
    assert result["toolCalls"][0]["arguments"] == {"path": ".", "recursive": False}
    assert result["toolCalls"][1]["arguments"] == {"path": "README.md", "startLine": 1, "endLine": 20}


def test_invoke_model_repairs_single_quote_tool_arguments(monkeypatch) -> None:
    monkeypatch.delenv("YGGDRASIL_DISABLE_LIVE_LLM", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek")
    monkeypatch.setenv("YGGDRASIL_ALLOW_PAID_MODELS", "1")

    def _fake_urlopen(_request, timeout=90):
        return _FakeResponse(
            {
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "mcp.read.read_file",
                                        "arguments": "{'path':'README.md','startLine':1,'endLine':20}",
                                    },
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
            }
        )

    monkeypatch.setattr(gateway.urllib_request, "urlopen", _fake_urlopen)

    result = gateway.invoke_model(
        requested_model="deepseek-v4-pro",
        requested_provider="deepseek_direct",
        messages=[{"role": "user", "content": "读取 README。"}],
        allow_fallback=False,
    )

    assert result["toolCalls"][0]["name"] == "mcp.read.read_file"
    assert result["toolCalls"][0]["arguments"] == {"path": "README.md", "startLine": 1, "endLine": 20}


def test_invoke_model_repairs_key_value_tool_arguments(monkeypatch) -> None:
    monkeypatch.delenv("YGGDRASIL_DISABLE_LIVE_LLM", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek")
    monkeypatch.setenv("YGGDRASIL_ALLOW_PAID_MODELS", "1")

    def _fake_urlopen(_request, timeout=90):
        return _FakeResponse(
            {
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "call_2",
                                    "type": "function",
                                    "function": {
                                        "name": "mcp.read.read_file",
                                        "arguments": "path=README.md, start_line=1, end_line=20",
                                    },
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
            }
        )

    monkeypatch.setattr(gateway.urllib_request, "urlopen", _fake_urlopen)

    result = gateway.invoke_model(
        requested_model="deepseek-v4-pro",
        requested_provider="deepseek_direct",
        messages=[{"role": "user", "content": "读取 README。"}],
        allow_fallback=False,
    )

    assert result["toolCalls"][0]["name"] == "mcp.read.read_file"
    assert result["toolCalls"][0]["arguments"] == {"path": "README.md", "startLine": 1, "endLine": 20}


def test_deepseek_ssl_eof_retry_switches_to_non_stream(monkeypatch) -> None:
    monkeypatch.delenv("YGGDRASIL_DISABLE_LIVE_LLM", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek")
    monkeypatch.setenv("YGGDRASIL_ALLOW_PAID_MODELS", "1")
    monkeypatch.setenv("YGGDRASIL_LLM_RETRY_MAX", "1")
    monkeypatch.setenv("YGGDRASIL_LLM_DEEPSEEK_EXTRA_RETRY_MAX", "1")
    monkeypatch.setattr(gateway.time, "sleep", lambda *_args, **_kwargs: None)

    attempts: list[dict[str, object]] = []

    def _fake_urlopen(request, timeout=90):
        payload = json.loads(request.data.decode("utf-8"))
        attempts.append(payload)
        if len(attempts) == 1:
            raise gateway.urllib_error.URLError(ssl.SSLEOFError(8, "UNEXPECTED_EOF_WHILE_READING"))
        return _FakeResponse(
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": "重试成功。",
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 30,
                    "completion_tokens": 10,
                    "total_tokens": 40,
                },
            }
        )

    monkeypatch.setattr(gateway.urllib_request, "urlopen", _fake_urlopen)

    result = gateway.invoke_model(
        requested_model="deepseek-v4-pro",
        requested_provider="deepseek_direct",
        messages=[{"role": "user", "content": "请给出简短结论。"}],
        allow_fallback=False,
    )

    assert len(attempts) == 2
    assert attempts[0]["stream"] is True
    assert attempts[1]["stream"] is False
    assert result["outputText"] == "重试成功。"

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from yggdrasil_core_api.app import app
from yggdrasil_sdk.provider_config import provider_configuration_status


client = TestClient(app)
pytestmark = pytest.mark.slow


PROVIDER_ENV_NAMES = (
    "YGGDRASIL_DISABLE_LIVE_LLM",
    "YGGDRASIL_LLM_API_KEY",
    "YGGDRASIL_LLM_API_KEY_LONGCAT",
    "YGGDRASIL_LLM_API_KEY_OPENROUTER",
    "YGGDRASIL_LLM_API_KEY_DEEPSEEK",
    "YGGDRASIL_LLM_API_KEY_VECTORENGINE",
    "LONGCAT_API_KEY",
    "OPENROUTER_API_KEY",
    "DEEPSEEK_API_KEY",
    "VECTORENGINE_API_KEY",
)


def _clear_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in PROVIDER_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_provider_configuration_status_blocks_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_provider_env(monkeypatch)

    status = provider_configuration_status()

    assert status["status"] == "blocked"
    assert status["mode"] == "missing-provider-key"
    assert status["configuredProviders"] == []
    assert "LONGCAT_API_KEY" in status["requiredAnyOf"]


def test_provider_configuration_status_warns_when_live_llm_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("YGGDRASIL_DISABLE_LIVE_LLM", "1")
    monkeypatch.setenv("LONGCAT_API_KEY", "secret-value")

    status = provider_configuration_status()

    assert status["status"] == "warning"
    assert status["mode"] == "live-disabled"
    assert status["configuredProviders"][0]["id"] == "longcat"


def test_provider_configuration_status_ready_without_exposing_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("LONGCAT_API_KEY", "secret-value")

    status = provider_configuration_status()

    assert status["status"] == "ready"
    assert status["mode"] == "configured"
    assert status["configuredProviders"][0]["configuredEnvNames"] == ["LONGCAT_API_KEY"]
    assert "secret-value" not in str(status)


def test_health_includes_provider_status_without_key_values(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("LONGCAT_API_KEY", "secret-value")

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["providerStatus"]["status"] == "ready"
    assert "secret-value" not in response.text

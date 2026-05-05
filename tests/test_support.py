from __future__ import annotations

import os
from pathlib import Path

from yggdrasil_sdk.support import estimate_word_count
from yggdrasil_sdk.support import load_workspace_dotenv


def _workspace_root(root: Path) -> Path:
    (root / "services").mkdir(parents=True, exist_ok=True)
    (root / "modules").mkdir(parents=True, exist_ok=True)
    return root


def test_estimate_word_count_counts_latin_words() -> None:
    assert estimate_word_count("hello world from yggdrasil") == 4


def test_estimate_word_count_counts_cjk_without_spaces() -> None:
    assert estimate_word_count("世界树计划") == 5


def test_estimate_word_count_handles_mixed_text() -> None:
    assert estimate_word_count("hello 世界树 2026") == 5


def test_load_workspace_dotenv_populates_missing_process_env(monkeypatch, tmp_path: Path) -> None:
    workspace = _workspace_root(tmp_path)
    (workspace / ".env").write_text("LONGCAT_API_KEY=test-key\nYGGDRASIL_ALLOW_PAID_MODELS=1\n", encoding="utf-8")
    monkeypatch.delenv("LONGCAT_API_KEY", raising=False)
    monkeypatch.delenv("YGGDRASIL_ALLOW_PAID_MODELS", raising=False)

    loaded = load_workspace_dotenv(workspace)

    assert loaded == workspace / ".env"
    assert os.environ["LONGCAT_API_KEY"] == "test-key"
    assert os.environ["YGGDRASIL_ALLOW_PAID_MODELS"] == "1"


def test_load_workspace_dotenv_does_not_override_existing_env(monkeypatch, tmp_path: Path) -> None:
    workspace = _workspace_root(tmp_path)
    (workspace / ".env").write_text("LONGCAT_API_KEY=file-key\n", encoding="utf-8")
    monkeypatch.setenv("LONGCAT_API_KEY", "process-key")

    load_workspace_dotenv(workspace)

    assert os.environ["LONGCAT_API_KEY"] == "process-key"
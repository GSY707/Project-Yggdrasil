from __future__ import annotations

from pathlib import Path
import re


IGNORED_DIRS = {
    ".git",
    ".next",
    ".venv",
    ".yggdrasil",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
}

TEXT_SUFFIXES = {
    ".ini",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

SECRET_PATTERNS = {
    "deepseek_or_openai_style": re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    "openrouter": re.compile(r"\bsk-or-v1-[A-Za-z0-9]{20,}\b"),
    "longcat": re.compile(r"\bak_[A-Za-z0-9]{20,}\b"),
    "vertex": re.compile(r"\bAQ\.[A-Za-z0-9_-]{20,}\b"),
}


def _candidate_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        files.append(path)
    return files


def test_repository_text_files_do_not_embed_live_llm_keys() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    matches: list[str] = []

    for file_path in _candidate_files(repo_root):
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        for line_number, line in enumerate(content.splitlines(), start=1):
            for label, pattern in SECRET_PATTERNS.items():
                if pattern.search(line):
                    matches.append(f"{file_path.relative_to(repo_root)}:{line_number}:{label}")

    assert not matches, "Live LLM credentials must not be committed: " + ", ".join(matches)
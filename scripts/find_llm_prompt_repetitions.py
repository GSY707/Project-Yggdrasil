from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


KNOWN_TOKENS = (
    "## 结果/## 证据/## 风险/## 已知问题",
    "## 结果, ## 证据, ## 风险, ## 已知问题",
)

TEXT_KEYS = (
    "responseRequirements",
    "restartMessage",
    "resumeMessage",
    "rootSummary",
    "taskObjective",
    "currentObjective",
    "currentFocus",
)


@dataclass
class RepetitionFinding:
    file: str
    field: str
    kind: str
    detail: str


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _normalize_line(line: str) -> str:
    return " ".join(line.split()).strip().lower()


def _collect_message_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            for key in ("text", "input_text", "output_text", "content"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    parts.append(value)
                    break
        return "\n".join(parts)
    return ""


def _iter_text_fields(payload: Any) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    if not isinstance(payload, dict):
        return fields

    for key in TEXT_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            fields.append((key, value))

    runtime_state = payload.get("taskRuntimeState")
    if isinstance(runtime_state, dict):
        for key in ("resumeMessage", "restartMessage", "currentFocus", "taskObjective"):
            value = runtime_state.get(key)
            if isinstance(value, str) and value.strip():
                fields.append((f"taskRuntimeState.{key}", value))

    request_state = payload.get("requestState")
    if isinstance(request_state, dict):
        for key in TEXT_KEYS:
            value = request_state.get(key)
            if isinstance(value, str) and value.strip():
                fields.append((f"requestState.{key}", value))

    prompt = payload.get("prompt")
    if isinstance(prompt, dict):
        for section_name in ("systemSections", "userSections", "bootSections"):
            section = prompt.get(section_name)
            if isinstance(section, dict):
                for key, value in section.items():
                    if isinstance(value, str) and value.strip():
                        fields.append((f"prompt.{section_name}.{key}", value))

    messages = payload.get("messages")
    if isinstance(messages, list):
        for idx, msg in enumerate(messages, start=1):
            if not isinstance(msg, dict):
                continue
            content = _collect_message_text(msg)
            if content.strip():
                role = str(msg.get("role") or "unknown")
                fields.append((f"messages[{idx}:{role}]", content))

    return fields


def _scan_text_for_repetition(path: Path, field: str, text: str) -> list[RepetitionFinding]:
    findings: list[RepetitionFinding] = []

    for token in KNOWN_TOKENS:
        count = text.count(token)
        if count > 1:
            findings.append(
                RepetitionFinding(
                    file=str(path),
                    field=field,
                    kind="known_token_repeat",
                    detail=f"'{token}' repeated {count} times",
                )
            )

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    normalized_lines = [_normalize_line(line) for line in lines]
    counts = Counter(normalized_lines)
    repeated_lines = [(line, count) for line, count in counts.items() if count > 1 and len(line) >= 16]
    repeated_lines.sort(key=lambda item: item[1], reverse=True)
    for line, count in repeated_lines[:5]:
        findings.append(
            RepetitionFinding(
                file=str(path),
                field=field,
                kind="line_repeat",
                detail=f"line repeated {count} times: {line[:140]}",
            )
        )

    sentence_parts = re.split(r"[。！？!?\n]+", text)
    normalized_sentences = [_normalize_line(part) for part in sentence_parts if _normalize_line(part)]
    sentence_counts = Counter(normalized_sentences)
    repeated_sentences = [
        (sentence, count)
        for sentence, count in sentence_counts.items()
        if count > 1 and len(sentence) >= 24
    ]
    repeated_sentences.sort(key=lambda item: item[1], reverse=True)
    for sentence, count in repeated_sentences[:5]:
        findings.append(
            RepetitionFinding(
                file=str(path),
                field=field,
                kind="sentence_repeat",
                detail=f"sentence repeated {count} times: {sentence[:140]}",
            )
        )

    return findings


def _discover_files(root: Path) -> list[Path]:
    patterns = (
        "**/*.json",
        "**/*.md",
        "**/*.txt",
    )
    files: list[Path] = []
    for pattern in patterns:
        files.extend(path for path in root.glob(pattern) if path.is_file())
    return files


def run(root: Path, output: Path | None) -> int:
    findings: list[RepetitionFinding] = []
    scanned_files = 0

    for file_path in _discover_files(root):
        scanned_files += 1
        suffix = file_path.suffix.lower()
        if suffix == ".json":
            payload = _load_json(file_path)
            for field, text in _iter_text_fields(payload):
                findings.extend(_scan_text_for_repetition(file_path, field, text))
        else:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            findings.extend(_scan_text_for_repetition(file_path, "full_text", text))

    lines: list[str] = []
    lines.append("# LLM Prompt Repetition Report")
    lines.append("")
    lines.append(f"- root: {root}")
    lines.append(f"- scanned_files: {scanned_files}")
    lines.append(f"- findings: {len(findings)}")
    lines.append("")

    if not findings:
        lines.append("No repetition findings.")
    else:
        by_kind = Counter(item.kind for item in findings)
        lines.append("## Summary")
        lines.append("")
        for kind, count in by_kind.most_common():
            lines.append(f"- {kind}: {count}")
        lines.append("")
        lines.append("## Findings")
        lines.append("")
        for item in findings:
            lines.append(f"- file: {item.file}")
            lines.append(f"  - field: {item.field}")
            lines.append(f"  - kind: {item.kind}")
            lines.append(f"  - detail: {item.detail}")

    report = "\n".join(lines)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
    else:
        print(report)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan LLM records and prompt artifacts for repeated prompt fragments.")
    parser.add_argument("root", type=Path, help="Directory to scan, for example .yggdrasil/state or tmp/longcat2-live-export-completed-only-latest")
    parser.add_argument("--output", type=Path, default=None, help="Optional markdown report output path")
    args = parser.parse_args()
    return run(args.root.resolve(), args.output.resolve() if args.output else None)


if __name__ == "__main__":
    raise SystemExit(main())

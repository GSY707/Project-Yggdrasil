from __future__ import annotations

from datetime import datetime
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .ops_runtime_scorecard import (
    _append_scorecard_rows,
    _build_scorecard_row,
    _first_token_at,
    _first_token_seconds,
    _first_useful_output_at,
    _first_useful_output_seconds,
    _format_timestamp,
    _read_json_ref,
    _seconds_between,
    _task_pack_output_path,
    _tool_execution_names,
    _write_json_output,
)
from .ops_runtime_shared import _run_git_command
from .persistence import reset_persistence_runtime
from .prompting import list_registered_agent_tools
from .support import resolve_workspace_root, utc_now


_REAL_USER_LIVE_TASK_ORDER = ("YGG-CI-01", "YGG-CG-01", "YGG-CG-03")

_REAL_USER_LIVE_TASK_DEFS: dict[str, dict[str, Any]] = {
    "YGG-CI-01": {
        "appId": "yggdrasil.app.coding-inherit",
        "appLabel": "coding-inherit",
        "taskType": "integration",
        "runtimeTaskType": "coding",
        "activeCapabilities": ["mcp-bridge"],
        "allowedToolNames": ["mcp.read.read_file", "mcp.edit.replace_text"],
        "workspaceProfile": "pack-b-live-sandbox",
        "title": "YGG-CI-01 · Restore eval:m9:acceptance entry",
        "goal": (
            "请在当前 Project Yggdrasil 仓库中补齐 M9 acceptance 的统一执行入口：\n\n"
            "1. 在根 package.json 中新增一个与现有 eval 命名风格一致的脚本入口。\n"
            "2. 在 README 中补充对应运行命令。\n"
            "3. 更新 docs/DIRECTORY_REFERENCE.md，确保目录说明与实际入口一致。\n"
            "4. 做最小必要验证，不要改动无关部分。"
        ),
        "currentFocus": "YGG-CI-01 live rerun",
        "currentObjective": "Restore the missing eval:m9:acceptance entry and keep the repo documentation consistent.",
        "context": [
            {
                "id": "ci01_scope",
                "title": "working scope",
                "content": "Only modify package.json, README.md, and docs/DIRECTORY_REFERENCE.md inside the sandbox repo root. Apply the direct replacement specs from mounted context and do not probe unrelated paths.",
                "importance": 0.99,
            },
            {
                "id": "ci01_acceptance",
                "title": "acceptance criteria",
                "content": "Restore the eval:m9:acceptance script, add the README command, and restore the DIRECTORY_REFERENCE command mapping row. The live runner will execute the narrow validation command after your edit pass, so do not spend tool rounds on shell discovery.",
                "importance": 0.98,
            },
            {
                "id": "ci01_file_targets",
                "title": "direct file targets",
                "content": "The missing entry belongs exactly in package.json scripts, the README evaluation command block, and the DIRECTORY_REFERENCE evaluation command mapping table. The suites/m9-acceptance path is a documentation mapping target, not a directory you need to inspect on disk.",
                "importance": 0.99,
            },
        ],
        "verification": [{"kind": "shell", "command": "corepack pnpm eval:m9:acceptance", "cwd": "."}],
        "maxTokens": 900,
        "maxToolRounds": 12,
        "temperature": 0.1,
        "pauseResume": False,
        "taskWorkspaceKind": "repo",
    },
    "YGG-CG-01": {
        "appId": "yggdrasil.app.coding-inherit",
        "appLabel": "coding-inherit",
        "taskType": "greenfield",
        "runtimeTaskType": "coding",
        "activeCapabilities": ["mcp-bridge"],
        "thinking": "disabled",
        "auditLevel": "strict",
        "allowedToolNames": [
            "mcp.read.list_directory",
            "mcp.read.read_file",
            "mcp.edit.write_file",
            "mcp.edit.replace_text",
        ],
        "editablePaths": ["note_index.py", "README.md", "tests/test_note_index.py"],
        "workspaceProfile": "pack-a-live-sandbox",
        "title": "YGG-CG-01 · note-index from scratch",
        "goal": (
            "你现在在一个空白仓库里，请从零实现一个命令行工具 note-index：\n\n"
            "1. 输入一个 Markdown 文件目录。\n"
            "2. 递归扫描 .md 文件。\n"
            "3. 输出一个 index.json，字段至少包含 path、title、headings、word_count。\n"
            "4. 补 3 个自动化测试。\n"
            "5. 更新 README，告诉用户如何运行。\n\n"
            "要求：\n"
            "- 保持实现简单可维护。\n"
            "- 直接交付最终完整状态，不要先停在半成品或过渡版本。\n"
            "- 不要依赖自行跑命令来决定是否结束，runner 会执行正式外部验收。\n"
            "- 如果实现 word_count，中文文本不得直接用 split() 口径；应显式固定 CJK 统计规则，并在测试和 README 中说明。"
        ),
        "currentFocus": "YGG-CG-01 live rerun",
        "currentObjective": "Build a working note-index CLI from scratch in the isolated greenfield workspace and verify it end to end.",
        "context": [
            {
                "id": "cg01_scope",
                "title": "working scope",
                "verbatim": True,
                "content": "The MCP workspace for this task is the project root. Do not create a nested note-index/ project folder. The repo already contains starter README.md and tests/test_note_index.py scaffolding at the repo root. Focus your edits on note_index.py so the existing scaffold passes without being rewritten.",
                "importance": 0.99,
            },
            {
                "id": "cg01_quality",
                "title": "quality bar",
                "verbatim": True,
                "content": "Use only the standard library unless absolutely necessary, keep the structure small, and include at least three sane automated tests plus a README note for word_count semantics. Keep the generated tests internally consistent and Windows-safe. Continue using tools until the required root-level files are complete.",
                "importance": 0.99,
            },
            {
                "id": "cg01_cjk_rule",
                "title": "word_count rule",
                "verbatim": True,
                "content": "CJK word_count rule for this task: count each Han character as one word, never as a two-character Chinese word. Example expectations: \"你好世界\" = 4, \"这是一个测试\" = 6, and \"你好世界这是一个测试\" = 10. For mixed text, count each Latin word plus each Han character separately, so count_words_cjk(\"This is a test 这是一个测试\") = 10 and count_words_cjk(\"Hello 你好\") = 3. Numeric tokens such as \"1.0\" should count as one word token, so count_words_cjk(\"Version 1.0\") = 2 and count_words_cjk(\"v2.0 release\") = 2. Alphanumeric tokens such as \"H1\" should also count as one word token, so count_words_cjk(\"Document without H1\") = 3. Mixed CJK+digit tokens should count Han characters plus one numeric token, so count_words_cjk(\"测试123\") = 3. For the concrete document '# 中文文档\\n这是一个测试内容。Hello world!', the file-level word_count must be 14 because 中文文档 = 4 Han characters, 这是一个测试内容 = 8 Han characters, and Hello world = 2 Latin words. Explain the exact rule in README/tests.",
                "importance": 0.99,
            },
            {
                "id": "cg01_behavior_examples",
                "title": "behavior examples",
                "verbatim": True,
                "content": "Use a small deterministic implementation. Sort output records by path before writing JSON. The CLI contract is note_index.py <directory> --output <path>. Serialize stored paths with forward slashes by using Path.as_posix() so nested paths stay stable on Windows too. Title rule: use the first H1 heading (# ...) when present, otherwise the first non-empty line. Headings rule: include every markdown heading in order, including the title H1, and keep scanning after the H1 instead of stopping early. File-level word_count should count all visible document text in the file, including title/headings and body text, but not markdown markers or punctuation. Concrete examples that tests should follow: count_words_cjk(\"Hello world\") = 2, count_words_cjk(\"This is a test sentence.\") = 5, count_words_cjk(\"This is a test 这是一个测试\") = 10, count_words_cjk(\"Hello 你好\") = 3, and count_words_cjk(\"v2.0 release\") = 2. For content '# Main Title\\n## Section 1\\n### Subsection', title should be 'Main Title' and headings should include Main Title, Section 1, and Subsection in that order. For process_markdown_file examples, '# My Document Title\\n\\nThis is some content.\\n## Section One' should yield word_count 9; '# First Note\\n\\nSome content here.\\n## Section A' should yield word_count 7, not 9; '# First Note\\n\\nContent here.\\n## Section A' should yield word_count 6, not 7; 'Document without H1\\n## First Section\\nContent here.' should yield word_count 7; '# 中文文档\\n这是一个测试内容。Hello world!' should yield word_count 14; 'Second Note without H1\\n## Section\\nSome content here.' should yield word_count 8. Do not copy the 7-count expectation from the longer 'Some content here' sample onto the shorter 'Content here' sample.",
                "importance": 0.99,
            },
            {
                "id": "cg01_test_authoring",
                "title": "test authoring rules",
                "verbatim": True,
                "content": "Write clean pytest tests only. Do not add debug print statements, do not add an if __name__ == '__main__' block, and do not invent new numeric word_count assertions beyond the concrete examples listed in this task unless they are mathematically consistent with the same counting rule. Prefer direct imports plus TemporaryDirectory over subprocess-driven self-tests.",
                "importance": 0.99,
            },
            {
                "id": "cg01_heading_guard",
                "title": "heading extraction guard",
                "verbatim": True,
                "content": "Treat every markdown heading line matching 1-6 leading # characters followed by a space as a heading item. H2/H3/H4/H5/H6 must be included in headings, not just H1. If there is no H1, the title falls back to the first non-empty line, but headings must still include later markdown headings such as ## First Section.",
                "importance": 0.99,
            },
            {
                "id": "cg01_final_state",
                "title": "final state only",
                "verbatim": True,
                "content": "Do not stop after a partial implementation. Before finishing, the root-level note_index.py, README.md, and tests/test_note_index.py must already agree with the exact behavior examples in this task. The acceptance runner will import the code directly and check title/headings/word_count behavior without trusting your self-report.",
                "importance": 0.99,
            },
            {
                "id": "cg01_expected_tree",
                "title": "expected root tree",
                "verbatim": True,
                "content": "Expected deliverables at repo root:\n- note_index.py\n- README.md\n- tests/test_note_index.py\nDo not create note-index/, src/, or other wrapper directories unless the task explicitly requires them.",
                "importance": 0.98,
            },
            {
                "id": "cg01_validation_handoff",
                "title": "validation handoff",
                "verbatim": True,
                "content": "The live runner will execute an external functional verification plus artifact/test checks after your edit pass. Spend tool rounds on reading and writing the required root-level files instead of command-based self-validation or shell directory creation. Do not paste full file contents into assistant messages; use write_file/replace_text directly and keep prose brief until the files are complete.",
                "importance": 0.99,
            },
            {
                "id": "cg01_test_hygiene",
                "title": "test hygiene",
                "verbatim": True,
                "content": "Write tests that are syntactically clean, non-contradictory, and Windows-safe. Prefer TemporaryDirectory plus Path.write_text for file fixtures. Do not use NamedTemporaryFile anywhere in tests/test_note_index.py; the literal string NamedTemporaryFile should not appear. Do not unlink or reopen an active temp-file handle on Windows.",
                "importance": 0.98,
            },
            {
                "id": "cg01_tokenization_hint",
                "title": "tokenization hint",
                "verbatim": True,
                "content": "A simple implementation pattern is: count Han characters with one regex, then count the remaining non-Han text with a regex such as [A-Za-z0-9]+(?:\\.\\d+)* so alphanumeric tokens like H1 stay one token and decimals like 1.0 stay one numeric token instead of splitting into 1 and 0.",
                "importance": 0.99,
            },
            {
                "id": "cg01_no_extras",
                "title": "deliverable boundary",
                "verbatim": True,
                "content": "Only deliver the required files for this task: note_index.py, README.md, and tests/test_note_index.py. Do not create extra verification scripts, reports, logs, sample output files, or helper shell/python files unless the task explicitly asks for them.",
                "importance": 0.99,
            },
        ],
        "verification": [
            {"kind": "python-check", "cwd": ".", "check": "cg01_functional"},
            {"kind": "python", "args": ["-m", "pytest", "-q"], "cwd": "."},
            {"kind": "python-check", "cwd": ".", "check": "cg01_artifacts"},
        ],
        "maxTokens": 2200,
        "maxToolRounds": 36,
        "temperature": 0.1,
        "pauseResume": False,
        "taskWorkspaceKind": "pack-a",
    },
    "YGG-CG-03": {
        "appId": "yggdrasil.app.coding-inherit",
        "appLabel": "coding-inherit",
        "taskType": "coding-resume",
        "runtimeTaskType": "coding",
        "activeCapabilities": ["mcp-bridge"],
        "thinking": "disabled",
        "auditLevel": "strict",
        "allowedToolNames": ["mcp.read.read_file", "mcp.edit.replace_text"],
        "editablePaths": ["note_index.py", "README.md", "tests/test_note_index.py"],
        "workspaceProfile": "pack-a-live-sandbox",
        "title": "YGG-CG-03 · add exclude with safe-stop/resume",
        "goal": (
            "为现有 note-index 仓库补上 --exclude。\n"
            "同时完成 CLI、pytest、README。\n"
            "任务中途会 safe-stop，resume 后继续完成。\n"
            "最终会重跑完整 pytest，你要对最终仓库整体结果负责。"
        ),
        "currentFocus": "YGG-CG-03 live rerun",
        "currentObjective": "Add --exclude support to the existing note-index project, survive a safe-stop, then resume and finish cleanly.",
        "resumeObjective": "The runtime already handled safe-stop. Continue from the restored snapshot and finish --exclude across note_index.py, tests/test_note_index.py, and README.md without creating any pause artifacts.",
        "context": [
            {
                "id": "cg03_resume_runtime",
                "title": "resume runtime rules",
                "verbatim": True,
                "content": "Continue in the existing repo-root workspace after the runtime-managed safe-stop. Do not restart from scratch and do not create SAFE_STOP files or any other pause artifacts.",
                "importance": 0.99,
            },
            {
                "id": "cg03_delivery_contract",
                "title": "delivery contract",
                "verbatim": True,
                "content": "Final verification reruns full pytest and then checks literal exclude deliverables: note_index.py must expose --exclude, tests/test_note_index.py must contain at least one concrete exclude assertion or CLI call using --exclude, and README.md must show a command example with --exclude. Only modify these three files, and finish only when the whole repo state passes.",
                "importance": 0.99,
            },
            {
                "id": "cg03_exclude_contract",
                "title": "exclude contract",
                "verbatim": True,
                "content": "Implement --exclude as a comma-separated list of shell-style glob patterns matched against Markdown file paths relative to the scanned root. The examples are independent: --exclude '*.tmp' omits excluded.tmp but keeps build/note.md, while --exclude 'build/*' omits build/note.md. Add tests that prove excluded Markdown files disappear and non-excluded Markdown files remain.",
                "importance": 0.99,
            },
            {
                "id": "cg03_baseline_guard",
                "title": "baseline behavior guard",
                "verbatim": True,
                "content": "Preserve the CG-01 contract while adding exclude: count_words_cjk('This is a test 这是一个测试') = 10, count_words_cjk('Hello 你好') = 3, count_words_cjk('v2.0 release') = 2, process_markdown_file('Second Note without H1\\n## Section\\nSome content here.') still yields word_count 8, process_markdown_file('# First Note\\n\\nSome content here.\\n## Section A') yields 7, process_markdown_file('# First Note\\n\\nContent here.\\n## Section A') yields 6, and '# 中文文档\\n这是一个测试内容。Hello world!' still yields file-level word_count 14. Heading/title extraction rules must remain unchanged.",
                "importance": 0.99,
            },
            {
                "id": "cg03_editing_rules",
                "title": "editing rules",
                "verbatim": True,
                "content": "Keep tests in pytest style, avoid debug prints and manual runners, and extend the baseline suite instead of rewriting it around new numeric expectations. Keep path checks Windows-safe with separator-stable comparisons such as Path(path).as_posix().",
                "importance": 0.99,
            },
        ],
        "verification": [
            {"kind": "python", "args": ["-m", "pytest", "-q"], "cwd": "."},
            {"kind": "python-check", "cwd": ".", "check": "cg03_artifacts"},
        ],
        "maxTokens": 900,
        "maxToolRounds": 80,
        "temperature": 0.1,
        "pauseResume": True,
        "resumeMessage": "Resume from the restored snapshot and finish --exclude across note_index.py, tests/test_note_index.py, and README.md without creating any pause artifacts.",
        "taskWorkspaceKind": "pack-a",
    },
}


def _apply_env(overrides: dict[str, str]) -> dict[str, str | None]:
    previous: dict[str, str | None] = {}
    for key, value in overrides.items():
        previous[key] = os.environ.get(key)
        os.environ[key] = value
    return previous


def _restore_env(previous: dict[str, str | None]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _live_task_token_budget(task_def: dict[str, Any]) -> int | None:
    raw_value = task_def.get("budgetTokenTotal")
    if raw_value in {None, ""}:
        return None
    return max(int(raw_value), 1)


def _drain_worker_attempts(run_worker_once, queue: str = "agent-runtime", *, max_attempts: int = 4) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    for _ in range(max_attempts):
        result = run_worker_once(queue)
        attempts.append(result)
        if str(result.get("status") or "") != "requeued":
            return attempts
    raise RuntimeError(f"worker remained requeued after {max_attempts} attempts")


def _prepare_ci01_baseline(workspace_root: Path) -> dict[str, Any]:
    source_workspace = resolve_workspace_root()
    package_path = workspace_root / "package.json"
    readme_path = workspace_root / "README.md"
    directory_path = workspace_root / "docs" / "DIRECTORY_REFERENCE.md"

    shutil.copy2(source_workspace / "package.json", package_path)
    shutil.copy2(source_workspace / "README.md", readme_path)
    shutil.copy2(source_workspace / "docs" / "DIRECTORY_REFERENCE.md", directory_path)

    package_payload = json.loads(package_path.read_text(encoding="utf-8"))
    scripts = dict(package_payload.get("scripts") or {})
    scripts.pop("eval:m9:acceptance", None)
    package_payload["scripts"] = scripts
    package_path.write_text(json.dumps(package_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    readme_text = readme_path.read_text(encoding="utf-8")
    readme_text = readme_text.replace("corepack pnpm eval:m9:acceptance\n", "")
    readme_path.write_text(readme_text, encoding="utf-8")

    directory_text = directory_path.read_text(encoding="utf-8")
    directory_text = directory_text.replace("| `eval:m9:acceptance` | `suites/m9-acceptance.json` |\n", "")
    directory_path.write_text(directory_text, encoding="utf-8")

    _run_git_command(workspace_root, "add", "package.json", "README.md", "docs/DIRECTORY_REFERENCE.md")
    status = _run_git_command(workspace_root, "status", "--porcelain")
    if status.strip():
        _run_git_command(workspace_root, "commit", "-m", "prepare YGG-CI-01 baseline")
    return {
        "workspace": str(workspace_root.resolve()),
        "preparedFiles": ["package.json", "README.md", "docs/DIRECTORY_REFERENCE.md"],
    }


def _line_containing(text: str, anchor: str) -> str:
    for line in text.splitlines():
        if anchor in line:
            return line
    raise ValueError(f"expected anchor not found: {anchor}")


def _extract_block(text: str, start_anchor: str, end_anchors: list[str]) -> str:
    start = text.find(start_anchor)
    if start < 0:
        raise ValueError(f"expected anchor not found: {start_anchor}")
    search_start = start + len(start_anchor)
    end_positions = [index for anchor in end_anchors if (index := text.find(anchor, search_start)) >= 0]
    end = min(end_positions) if end_positions else len(text)
    return text[start:end]


def _build_ci01_runtime_context(task_workspace: Path) -> list[dict[str, Any]]:
    package_text = (task_workspace / "package.json").read_text(encoding="utf-8")
    readme_text = (task_workspace / "README.md").read_text(encoding="utf-8")
    directory_text = (task_workspace / "docs" / "DIRECTORY_REFERENCE.md").read_text(encoding="utf-8")
    package_line = _line_containing(package_text, '"eval:m9:control-plane"')
    readme_line = _line_containing(readme_text, "corepack pnpm eval:m9:control-plane")
    directory_line = _line_containing(directory_text, "| `eval:m9:control-plane` | `suites/m9-control-plane.json` |")
    acceptance_line = '    "eval:m9:acceptance": "uv run python -m yggdrasil_sdk.evaluation_cli run --suite evalsuite_acceptance_m9_capabilities",'
    directory_acceptance_line = "| `eval:m9:acceptance` | `suites/m9-acceptance.json` |"
    return [
        {
            "id": "ci01_direct_replacements",
            "title": "direct replacement specs",
            "verbatim": True,
            "content": (
                "Apply these exact replace_text operations directly. Do not inspect evaluation/suites or run shell discovery commands.\n\n"
                "1. path=package.json\n"
                f"oldText:\n{package_line}\n"
                f"newText:\n{package_line}\n{acceptance_line}\n\n"
                "2. path=README.md\n"
                f"oldText:\n{readme_line}\n"
                f"newText:\n{readme_line}\ncorepack pnpm eval:m9:acceptance\n\n"
                "3. path=docs/DIRECTORY_REFERENCE.md\n"
                f"oldText:\n{directory_line}\n"
                f"newText:\n{directory_line}\n{directory_acceptance_line}"
            ),
            "importance": 0.99,
        },
        {
            "id": "ci01_runner_validation",
            "title": "runner validation handoff",
            "verbatim": True,
            "content": "After the three replace_text operations, stop editing and hand off. The live runner will execute corepack pnpm eval:m9:acceptance as the external verification step.",
            "importance": 0.99,
        },
    ]


def _build_cg03_runtime_context(task_workspace: Path) -> list[dict[str, Any]]:
    note_index_text = (task_workspace / "note_index.py").read_text(encoding="utf-8")
    readme_text = (task_workspace / "README.md").read_text(encoding="utf-8")
    tests_text = (task_workspace / "tests" / "test_note_index.py").read_text(encoding="utf-8")
    note_usage_line = _line_containing(note_index_text, "python note_index.py <directory> --output <path>")
    readme_usage_line = _line_containing(readme_text, "python note_index.py <directory> --output <path>")
    note_scan_block = _extract_block(
        note_index_text,
        "def scan_directory(",
        ["\n\ndef main():", "\n\n# ---------------------------------------------------------------------------\n# CLI entry point", "\n\nif __name__ =="],
    )
    note_scan_block_with_exclude = (
        "def _is_excluded(file_path, root, patterns):\n"
        "    if not patterns:\n"
        "        return False\n"
        "    rel_path = Path(file_path).relative_to(root).as_posix()\n"
        "    for pattern in patterns:\n"
        "        if fnmatch.fnmatch(rel_path, pattern):\n"
        "            return True\n"
        "    return False\n\n\n"
        "def scan_directory(directory, exclude_patterns=None):\n"
        "    root = Path(directory)\n"
        "    patterns = exclude_patterns or []\n"
        '    records = [\n        process_markdown_file(path)\n        for path in sorted(root.rglob("*.md"), key=lambda item: item.as_posix())\n        if not _is_excluded(path, root, patterns)\n    ]\n'
        "    return records\n"
    )
    note_main_block = _extract_block(
        note_index_text,
        "def main():",
        ["\n\nif __name__ == '__main__':", '\n\nif __name__ == "__main__":'],
    )
    note_main_block_with_exclude = (
        "def main():\n"
        '    parser.add_argument("--output", "-o", required=True, help="Output JSON file path")\n'
        '    parser.add_argument("--exclude", help="Comma-separated shell-style glob patterns to exclude")\n'
        "    args = parser.parse_args()\n\n"
        '    exclude_patterns = [item.strip() for item in (args.exclude or "").split(",") if item.strip()]\n'
        "    records = scan_directory(args.directory, exclude_patterns=exclude_patterns)\n"
        "    output_path = Path(args.output)\n"
        "    output_path.write_text(\n"
        "        json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8'\n"
        "    )\n"
        "    return 0\n"
    )
    tests_cli_block = _extract_block(tests_text, "def test_cli_integration():", ["\ndef test_"])
    tests_append_block = (
        "\n\n"
        "def test_cli_exclude_patterns():\n"
        "    with tempfile.TemporaryDirectory() as temp_dir:\n"
        '        notes_dir = Path(temp_dir) / "notes"\n'
        '        _write_markdown(notes_dir, "keep.md", "# Keep\\n\\nHello world")\n'
        '        _write_markdown(notes_dir, "build/skip.md", "# Skip\\n\\nHello world")\n'
        '        _write_markdown(notes_dir, "skip.md", "# Root Skip\\n\\nHello world")\n'
        '        output_file = Path(temp_dir) / "index.json"\n\n'
        "        result = subprocess.run(\n"
        '            [sys.executable, "note_index.py", str(notes_dir), "--output", str(output_file), "--exclude", "build/*,skip.md"],\n'
        "            cwd=Path.cwd(),\n"
        "            capture_output=True,\n"
        "            text=True,\n"
        "        )\n"
        "        assert result.returncode == 0\n\n"
        '        records = json.loads(output_file.read_text(encoding="utf-8"))\n'
        "        assert len(records) == 1\n"
        '        assert records[0]["path"].endswith("keep.md")\n'
        '        assert records[0]["title"] == "Keep"\n'
    )
    replacement_specs: list[str] = []
    if "[--exclude <patterns>]" not in note_index_text:
        replacement_specs.append(
            "1. path=note_index.py\n"
            f"oldText:\n{note_usage_line}\n"
            f"newText:\n{note_usage_line} [--exclude <patterns>]\n"
        )
    if "import fnmatch\n" not in note_index_text:
        replacement_specs.append(
            "2. path=note_index.py\n"
            "oldText:\nimport argparse\nimport json\n"
            "newText:\nimport argparse\nimport fnmatch\nimport json\n"
        )
    if "def _is_excluded(file_path, root, patterns):" not in note_index_text:
        replacement_specs.append(
            "3. path=note_index.py\n"
            f"oldText:\n{note_scan_block}"
            f"newText:\n{note_scan_block_with_exclude}"
        )
    if 'parser.add_argument("--exclude", help="Comma-separated shell-style glob patterns to exclude")' not in note_index_text:
        replacement_specs.append(
            "4. path=note_index.py\n"
            f"oldText:\n{note_main_block}"
            f"newText:\n{note_main_block_with_exclude}\n"
        )
    if "--exclude" not in readme_text:
        replacement_specs.append(
            "5. path=README.md\n"
            f"oldText:\n{readme_usage_line}\n"
            f"newText:\n{readme_usage_line} --exclude \"build/*,drafts/*\"\n"
        )
    if "--exclude" not in tests_text:
        replacement_specs.append(
            "6. path=tests/test_note_index.py\n"
            f"oldText:\n{tests_cli_block}"
            f"newText:\n{tests_cli_block}{tests_append_block}"
        )
    replacement_instructions = "\n".join(replacement_specs) if replacement_specs else "Workspace already satisfies the --exclude contract. Do not edit any files; hand off immediately."
    return [
        {
            "id": "cg03_small_repo_strategy",
            "title": "small repo execution strategy",
            "verbatim": True,
            "content": (
                "This repo has only three relevant files: note_index.py, tests/test_note_index.py, and README.md. "
                "Do not spend tool rounds rediscovering the repo shape, and do not use shell commands for self-validation because the live runner will validate externally. "
                "Use the provided replace_text specs as written instead of inventing a new edit plan. "
                "Do not paste large code blocks into assistant messages. Only re-read a file after your own write changed it and you need the updated content."
            ),
            "importance": 0.99,
        },
        {
            "id": "cg03_direct_replacements",
            "title": "direct replacement specs",
            "verbatim": True,
            "content": (
                "Apply these exact replace_text operations directly. Do not use write_file.\n\n"
                f"{replacement_instructions}"
            ),
            "importance": 1.0,
        },
        {
            "id": "cg03_validation_handoff",
            "title": "validation handoff",
            "verbatim": True,
            "content": "After the six replace_text operations, stop editing and hand off. The live runner will rerun pytest plus the cg03_artifacts check externally.",
            "importance": 0.99,
        },
    ]


def _filter_registered_tools(active_capabilities: list[str], allowed_tool_names: list[str] | None) -> list[dict[str, Any]] | None:
    if not allowed_tool_names:
        return None
    allowed = {str(name) for name in allowed_tool_names}
    return [tool for tool in list_registered_agent_tools(active_capabilities) if str(tool.get("name") or "") in allowed]


def _ensure_git_repo(repo_path: Path, *, baseline_message: str) -> None:
    if (repo_path / ".git").exists():
        _run_git_command(repo_path, "add", ".")
        status = _run_git_command(repo_path, "status", "--porcelain")
        if status.strip():
            _run_git_command(repo_path, "commit", "-m", baseline_message)
        return
    _run_git_command(repo_path, "init", "-b", "main")
    _run_git_command(repo_path, "config", "user.name", "Yggdrasil Pilot")
    _run_git_command(repo_path, "config", "user.email", "pilot@yggdrasil.local")
    _run_git_command(repo_path, "add", ".")
    _run_git_command(repo_path, "commit", "--allow-empty", "-m", baseline_message)


def _prepare_greenfield_workspace(sandbox_root: Path) -> Path:
    workspace = (sandbox_root / f"pack-a-workspace-live-{utc_now().strftime('%Y%m%dT%H%M%SZ')}").resolve()
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / ".gitignore").write_text("index.json\n__pycache__/\n.pytest_cache/\n", encoding="utf-8")
    (workspace / "note_index.py").write_text(
        "#!/usr/bin/env python3\n"
        '"""Note Index CLI - Generate index.json from Markdown files.\n\nUsage:\n    python note_index.py <directory> --output <path>\n"""\n\n'
        "import argparse\n"
        "import json\n"
        "from pathlib import Path\n\n\n"
        "def count_words_cjk(text):\n"
        "    \"\"\"Count words in text using the task's CJK-aware contract.\"\"\"\n"
        "    raise NotImplementedError('Implement count_words_cjk')\n\n\n"
        "def extract_title_and_headings(content):\n"
        "    \"\"\"Return (title, headings) for markdown content.\n"
        "\n"
        "    Title uses the first H1 only. If the document has no H1, fall back to\n"
        "    the first non-empty line even when later H2/H3 headings exist.\n"
        "    \"\"\"\n"
        "    raise NotImplementedError('Implement extract_title_and_headings')\n\n\n"
        "def process_markdown_file(file_path):\n"
        "    \"\"\"Return a metadata dict for one markdown file.\n"
        "\n"
        "    word_count must include all visible document text, including title,\n"
        "    headings, and body text, while excluding markdown markers or punctuation.\n"
        "    Serialize path with file_path.as_posix() so nested paths stay stable\n"
        "    across platforms.\n"
        "    \"\"\"\n"
        "    raise NotImplementedError('Implement process_markdown_file')\n\n\n"
        "def scan_directory(directory):\n"
        "    \"\"\"Return sorted metadata records for markdown files under directory.\"\"\"\n"
        "    raise NotImplementedError('Implement scan_directory')\n\n\n"
        "def main():\n"
        "    parser = argparse.ArgumentParser(description='Generate index.json from Markdown files')\n"
        "    parser.add_argument('directory', help='Directory to scan for .md files')\n"
        "    parser.add_argument('--output', '-o', required=True, help='Output JSON file path')\n"
        "    args = parser.parse_args()\n\n"
        "    records = scan_directory(args.directory)\n"
        "    output_path = Path(args.output)\n"
        "    output_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')\n"
        "    return 0\n\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )
    (workspace / "README.md").write_text(
        "# Note Index CLI\n\n"
        "A simple command-line tool to generate an index from Markdown files.\n\n"
        "## Usage\n\n"
        "```bash\npython note_index.py <directory> --output <path>\n```\n\n"
        "## Word Count Rules\n\n"
        "- Each Han character counts as one word.\n"
        "- Latin and alphanumeric tokens such as Hello, H1, and 1.0 count as one word each.\n"
        "- Mixed content counts Han characters and Latin/alphanumeric tokens separately.\n\n"
        "### Examples\n\n"
        "- Hello world = 2\n"
        "- 你好世界 = 4\n"
        "- This is a test 这是一个测试 = 10\n"
        "- # My Document Title\\n\\nThis is some content.\\n## Section One = 9\n"
        "- # First Note\\n\\nContent here.\\n## Section A = 6\n"
        "- Second Note without H1\\n## Section\\nSome content here. = 8\n",
        encoding="utf-8",
    )
    tests_dir = workspace / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_note_index.py").write_text(
        "import json\n"
        "import subprocess\n"
        "import sys\n"
        "import tempfile\n"
        "from pathlib import Path\n\n"
        "from note_index import count_words_cjk, extract_title_and_headings, process_markdown_file\n\n\n"
        "def _write_markdown(temp_dir, name, content):\n"
        "    file_path = Path(temp_dir) / name\n"
        "    file_path.parent.mkdir(parents=True, exist_ok=True)\n"
        "    file_path.write_text(content, encoding='utf-8')\n"
        "    return file_path\n\n\n"
        "def test_count_words_examples():\n"
        "    assert count_words_cjk('Hello world') == 2\n"
        "    assert count_words_cjk('你好世界') == 4\n"
        "    assert count_words_cjk('这是一个测试') == 6\n"
        "    assert count_words_cjk('This is a test 这是一个测试') == 10\n"
        "    assert count_words_cjk('Hello 你好') == 3\n"
        "    assert count_words_cjk('Version 1.0') == 2\n"
        "    assert count_words_cjk('v2.0 release') == 2\n"
        "    assert count_words_cjk('测试123') == 3\n\n\n"
        "def test_extract_title_and_headings_examples():\n"
        "    title, headings = extract_title_and_headings('# Main Title\\n## Section 1\\n### Subsection')\n"
        "    assert title == 'Main Title'\n"
        "    assert headings == ['Main Title', 'Section 1', 'Subsection']\n\n"
        "    title, headings = extract_title_and_headings('Document without H1\\n## First Section\\nContent here.')\n"
        "    assert title == 'Document without H1'\n"
        "    assert headings == ['First Section']\n\n\n"
        "def test_process_markdown_file_examples():\n"
        "    with tempfile.TemporaryDirectory() as temp_dir:\n"
        "        first = _write_markdown(temp_dir, 'doc1.md', '# My Document Title\\n\\nThis is some content.\\n## Section One')\n"
        "        second = _write_markdown(temp_dir, 'doc2.md', 'Document without H1\\n## First Section\\nContent here.')\n"
        "        third = _write_markdown(temp_dir, 'doc3.md', '# 中文文档\\n这是一个测试内容。Hello world!')\n\n"
        "        first_result = process_markdown_file(first)\n"
        "        second_result = process_markdown_file(second)\n"
        "        third_result = process_markdown_file(third)\n\n"
        "        assert first_result['title'] == 'My Document Title'\n"
        "        assert first_result['headings'] == ['My Document Title', 'Section One']\n"
        "        assert first_result['word_count'] == 9\n\n"
        "        assert second_result['title'] == 'Document without H1'\n"
        "        assert second_result['headings'] == ['First Section']\n"
        "        assert second_result['word_count'] == 7\n\n"
        "        assert third_result['title'] == '中文文档'\n"
        "        assert third_result['headings'] == ['中文文档']\n"
        "        assert third_result['word_count'] == 14\n\n\n"
        "def test_cli_integration():\n"
        "    with tempfile.TemporaryDirectory() as temp_dir:\n"
        "        _write_markdown(temp_dir, 'note1.md', '# First Note\\n\\nContent here.\\n## Section A')\n"
        "        _write_markdown(temp_dir, 'note2.md', 'Second Note without H1\\n## Section\\nSome content here.')\n"
        "        output_file = Path(temp_dir) / 'index.json'\n\n"
        "        result = subprocess.run([sys.executable, 'note_index.py', temp_dir, '--output', str(output_file)], cwd=Path.cwd(), capture_output=True, text=True)\n"
        "        assert result.returncode == 0\n\n"
        "        records = json.loads(output_file.read_text(encoding='utf-8'))\n"
        "        assert len(records) == 2\n"
        "        assert records[0]['path'].endswith('note1.md')\n"
        "        assert records[0]['title'] == 'First Note'\n"
        "        assert records[0]['headings'] == ['First Note', 'Section A']\n"
        "        assert records[0]['word_count'] == 6\n"
        "        assert records[1]['path'].endswith('note2.md')\n"
        "        assert records[1]['title'] == 'Second Note without H1'\n"
        "        assert records[1]['headings'] == ['Section']\n"
        "        assert records[1]['word_count'] == 8\n",
        encoding="utf-8",
    )
    _ensure_git_repo(workspace, baseline_message="prepare YGG-CG-01 baseline")
    return workspace


def _seed_cg01_reference_solution(workspace: Path) -> None:
    (workspace / "note_index.py").write_text(
        "#!/usr/bin/env python3\n"
        '"""Note Index CLI - Generate index.json from Markdown files.\n\n'
        "Usage:\n"
        "    python note_index.py <directory> --output <path>\n"
        '"""\n\n'
        "import argparse\n"
        "import json\n"
        "import re\n"
        "from pathlib import Path\n\n\n"
        '_HAN_RE = re.compile(r"[\\u4e00-\\u9fff]")\n'
        '_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:\\.\\d+)*")\n'
        '_HEADING_RE = re.compile(r"^(#{1,6})\\s+(.*)$")\n\n\n'
        "def count_words_cjk(text):\n"
        "    han_count = len(_HAN_RE.findall(text))\n"
        '    non_han_text = _HAN_RE.sub(" ", text)\n'
        "    token_count = len(_TOKEN_RE.findall(non_han_text))\n"
        "    return han_count + token_count\n\n\n"
        "def extract_title_and_headings(content):\n"
        "    title = None\n"
        "    headings = []\n"
        "    first_non_empty = None\n"
        "    for raw_line in content.splitlines():\n"
        "        line = raw_line.strip()\n"
        "        if not line:\n"
        "            continue\n"
        "        if first_non_empty is None:\n"
        "            first_non_empty = line\n"
        "        match = _HEADING_RE.match(line)\n"
        "        if not match:\n"
        "            continue\n"
        "        heading_text = match.group(2).strip()\n"
        "        if not heading_text:\n"
        "            continue\n"
        "        headings.append(heading_text)\n"
        "        if match.group(1) == '#' and title is None:\n"
        "            title = heading_text\n"
        "    if title is None:\n"
        "        title = first_non_empty\n"
        "    return title, headings\n\n\n"
        "def _visible_text(content):\n"
        "    visible_lines = []\n"
        "    for raw_line in content.splitlines():\n"
        "        line = raw_line.strip()\n"
        "        if not line:\n"
        "            continue\n"
        "        match = _HEADING_RE.match(line)\n"
        "        if match:\n"
        "            heading_text = match.group(2).strip()\n"
        "            if heading_text:\n"
        "                visible_lines.append(heading_text)\n"
        "        else:\n"
        "            visible_lines.append(line)\n"
        '    return "\\n".join(visible_lines)\n\n\n'
        "def process_markdown_file(file_path):\n"
        "    path = Path(file_path)\n"
        '    content = path.read_text(encoding="utf-8")\n'
        "    title, headings = extract_title_and_headings(content)\n"
        "    return {\n"
        '        "path": path.as_posix(),\n'
        '        "title": title,\n'
        '        "headings": headings,\n'
        '        "word_count": count_words_cjk(_visible_text(content)),\n'
        "    }\n\n\n"
        "def scan_directory(directory):\n"
        "    root = Path(directory)\n"
        '    records = [process_markdown_file(path) for path in sorted(root.rglob("*.md"), key=lambda item: item.as_posix())]\n'
        "    return records\n\n\n"
        "def main():\n"
        '    parser = argparse.ArgumentParser(description="Generate index.json from Markdown files")\n'
        '    parser.add_argument("directory", help="Directory to scan for .md files")\n'
        '    parser.add_argument("--output", "-o", required=True, help="Output JSON file path")\n'
        "    args = parser.parse_args()\n\n"
        "    records = scan_directory(args.directory)\n"
        '    output_path = Path(args.output)\n'
        '    output_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")\n'
        "    return 0\n\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )
    (workspace / "README.md").write_text(
        "# Note Index CLI\n\n"
        "Generate an index.json file from Markdown files.\n\n"
        "## Usage\n\n"
        "```bash\n"
        "python note_index.py <directory> --output <path>\n"
        "```\n\n"
        "## Word Count Rules\n\n"
        "- Each Han character counts as one word.\n"
        "- Latin and alphanumeric tokens such as Hello, H1, and 1.0 count as one word each.\n"
        "- Mixed CJK and Latin text counts Han characters and alphanumeric tokens separately.\n\n"
        "## Examples\n\n"
        "- 你好世界 = 4\n"
        "- This is a test 这是一个测试 = 10\n"
        "- Version 1.0 = 2\n"
        "- 测试123 = 3\n",
        encoding="utf-8",
    )
    tests_dir = workspace / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_note_index.py").write_text(
        "import json\n"
        "import subprocess\n"
        "import sys\n"
        "import tempfile\n"
        "from pathlib import Path\n\n"
        "from note_index import count_words_cjk, extract_title_and_headings, process_markdown_file\n\n\n"
        "def _write_markdown(temp_dir, name, content):\n"
        "    file_path = Path(temp_dir) / name\n"
        "    file_path.parent.mkdir(parents=True, exist_ok=True)\n"
        '    file_path.write_text(content, encoding="utf-8")\n'
        "    return file_path\n\n\n"
        "def test_count_words_examples():\n"
        '    assert count_words_cjk("Hello world") == 2\n'
        '    assert count_words_cjk("你好世界") == 4\n'
        '    assert count_words_cjk("这是一个测试") == 6\n'
        '    assert count_words_cjk("This is a test 这是一个测试") == 10\n'
        '    assert count_words_cjk("Hello 你好") == 3\n'
        '    assert count_words_cjk("Version 1.0") == 2\n'
        '    assert count_words_cjk("v2.0 release") == 2\n'
        '    assert count_words_cjk("测试123") == 3\n\n\n'
        "def test_extract_title_and_headings_examples():\n"
        '    title, headings = extract_title_and_headings("# Main Title\\n## Section 1\\n### Subsection")\n'
        '    assert title == "Main Title"\n'
        '    assert headings == ["Main Title", "Section 1", "Subsection"]\n\n'
        '    title, headings = extract_title_and_headings("Document without H1\\n## First Section\\nContent here.")\n'
        '    assert title == "Document without H1"\n'
        '    assert headings == ["First Section"]\n\n\n'
        "def test_process_markdown_file_examples():\n"
        "    with tempfile.TemporaryDirectory() as temp_dir:\n"
        '        first = _write_markdown(temp_dir, "doc1.md", "# My Document Title\\n\\nThis is some content.\\n## Section One")\n'
        '        second = _write_markdown(temp_dir, "doc2.md", "Document without H1\\n## First Section\\nContent here.")\n'
        '        third = _write_markdown(temp_dir, "doc3.md", "# 中文文档\\n这是一个测试内容。Hello world!")\n\n'
        "        first_result = process_markdown_file(first)\n"
        "        second_result = process_markdown_file(second)\n"
        "        third_result = process_markdown_file(third)\n\n"
        '        assert first_result["title"] == "My Document Title"\n'
        '        assert first_result["headings"] == ["My Document Title", "Section One"]\n'
        '        assert first_result["word_count"] == 9\n\n'
        '        assert second_result["title"] == "Document without H1"\n'
        '        assert second_result["headings"] == ["First Section"]\n'
        '        assert second_result["word_count"] == 7\n\n'
        '        assert third_result["title"] == "中文文档"\n'
        '        assert third_result["headings"] == ["中文文档"]\n'
        '        assert third_result["word_count"] == 14\n\n\n'
        "def test_cli_integration():\n"
        "    with tempfile.TemporaryDirectory() as temp_dir:\n"
        '        notes_dir = Path(temp_dir) / "notes"\n'
        '        _write_markdown(notes_dir, "doc1.md", "# Main Title\\n\\nThis is some content.\\n## Section One")\n'
        '        _write_markdown(notes_dir, "doc2.md", "# 中文文档\\n这是一个测试内容。Hello world!")\n'
        '        _write_markdown(notes_dir, "subdir/doc3.md", "Document without H1\\n## First Section\\nContent here.")\n'
        '        output_file = Path(temp_dir) / "index.json"\n\n'
        "        result = subprocess.run(\n"
        '            [sys.executable, "note_index.py", str(notes_dir), "--output", str(output_file)],\n'
        "            cwd=Path.cwd(),\n"
        "            capture_output=True,\n"
        "            text=True,\n"
        "        )\n"
        "        assert result.returncode == 0\n\n"
        '        records = json.loads(output_file.read_text(encoding="utf-8"))\n'
        "        assert len(records) == 3\n"
        '        assert [record["title"] for record in records] == ["Main Title", "中文文档", "Document without H1"]\n'
        '        assert [record["path"] for record in records] == sorted(record["path"] for record in records)\n',
        encoding="utf-8",
    )


def _git_diff_summary(repo_path: Path) -> dict[str, Any]:
    status = _run_git_command(repo_path, "status", "--short")
    diff_stat = _run_git_command(repo_path, "diff", "--stat")
    changed_files = [line.strip() for line in status.splitlines() if line.strip()]
    return {
        "changedFiles": changed_files,
        "diffStat": diff_stat,
    }


def _build_repair_context(task_key: str, verification: list[dict[str, Any]]) -> dict[str, Any]:
    details = _format_repair_failures(verification)
    if task_key == "YGG-CG-01":
        guidance = (
            "The authoritative failures show the root implementation is still incomplete. Read note_index.py, tests/test_note_index.py, and README.md once, then replace note_index.py with a complete implementation in one write_file pass before making any smaller follow-up edits. "
            "Do not stop with an analysis-only response, and do not spend extra rounds on list_directory or repetitive re-reading after the implementation plan is clear. "
        )
    elif task_key == "YGG-CG-03" and any(str(item.get("check") or "") == "cg03_artifacts" and int(item.get("returncode") or 0) != 0 for item in verification):
        guidance = (
            "Apply the direct replace_text specs for note_index.py, tests/test_note_index.py, and README.md. "
            "Do not use write_file, and do not rewrite the baseline CG-01 tests or counting rules while doing this. "
        )
    else:
        guidance = (
            "Do not rewrite existing contract tests just to make failures disappear. Prefer fixing note_index.py first, and only edit tests when the failure itself proves a test expectation conflicts with the contract or the exclude requirements. "
        )
    return {
        "id": f"{task_key.lower()}_repair_feedback",
        "title": "external verification feedback",
        "verbatim": True,
        "content": (
            "The previous edit pass finished but the live runner's external verification failed. "
            "Repair the existing workspace in place instead of starting over. "
            "Treat the original task contract and its concrete examples as authoritative. "
            f"{guidance}"
            "Do not add helper verification tests, debug prints, or alternate scenarios. Stop once these failures are addressed:\n"
            f"{details}\n"
            "Treat these failures as authoritative. After fixing them, hand off without doing shell self-validation because the live runner will rerun verification."
        ),
        "importance": 1.0,
    }


def _summarize_verification_detail(detail: str, *, max_lines: int = 12, max_chars: int = 1200) -> str:
    text = detail.strip()
    if not text:
        return "verification failed without stderr/stdout"
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    interesting_lines = [
        line.strip()
        for line in lines
        if line.strip().startswith("FAILED ")
        or line.strip().startswith("E       ")
        or line.strip().startswith(">")
        or "AssertionError" in line
        or "NameError" in line
        or line.strip().startswith("assert ")
        or line.strip().startswith("__")
    ]
    selected_lines = interesting_lines[:max_lines] if interesting_lines else [line.strip() for line in lines[:max_lines]]
    summary = "\n".join(selected_lines)
    if len(summary) > max_chars:
        return f"{summary[: max_chars - 3]}..."
    return summary


def _format_repair_failures(verification: list[dict[str, Any]]) -> str:
    failure_lines: list[str] = []
    for item in verification:
        returncode = int(item.get("returncode") or 0)
        if returncode == 0:
            continue
        label = str(item.get("check") or item.get("command") or item.get("kind") or "verification")
        stderr = str(item.get("stderr") or "").strip()
        stdout = str(item.get("stdout") or "").strip()
        detail = _summarize_verification_detail(stderr or stdout or "verification failed without stderr/stdout")
        failure_lines.append(f"- {label}: {detail}")
    return "\n".join(failure_lines) if failure_lines else "- external verification reported an unspecified failure"


def _build_repair_goal(task_key: str, verification: list[dict[str, Any]]) -> str:
    details = _format_repair_failures(verification)
    if task_key == "YGG-CG-01":
        strategy = (
            "This is a repair pass for the existing note-index workspace. The failures show note_index.py still contains placeholder behavior. "
            "Read the three root files once, then overwrite note_index.py in one write_file pass with the final implementation, while preserving the original CG-01 contract examples and existing test surface. "
            "Prefer fixing note_index.py and README. Only edit tests if a failure explicitly proves the test content is inconsistent with the authoritative contract."
        )
    elif task_key == "YGG-CG-03":
        if any(str(item.get("check") or "") == "cg03_artifacts" and int(item.get("returncode") or 0) != 0 for item in verification):
            strategy = (
                "This is a repair pass for the inherited note-index workspace. Apply the direct replace_text specs to note_index.py, tests/test_note_index.py, and README.md. "
                "Preserve the CG-01 baseline behavior while adding --exclude and its CLI/test/README coverage."
            )
        else:
            strategy = (
                "This is a repair pass for the inherited note-index workspace. Preserve the CG-01 baseline behavior while fixing the exclude feature. "
                "Keep test changes minimal and aligned to the original contract plus the exclude requirements."
            )
    else:
        strategy = "This is a repair pass for the existing workspace. Fix the concrete verification failures without restarting from scratch."
    return f"{strategy}\n\nAuthoritative verification failures to fix:\n{details}"


def _run_shell_verification(command: str, cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False, shell=True)
    return {
        "kind": "shell",
        "command": command,
        "cwd": str(cwd.resolve()),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _run_python_verification(args: list[str], cwd: Path) -> dict[str, Any]:
    completed = subprocess.run([sys.executable, *args], cwd=cwd, capture_output=True, text=True, check=False)
    return {
        "kind": "python",
        "command": " ".join([sys.executable, *args]),
        "cwd": str(cwd.resolve()),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _run_custom_verification(check: str, cwd: Path) -> dict[str, Any]:
    note_index = cwd / "note_index.py"
    tests_path = cwd / "tests" / "test_note_index.py"
    readme_path = cwd / "README.md"
    result = {
        "kind": "python-check",
        "check": check,
        "cwd": str(cwd.resolve()),
        "returncode": 0,
        "stdout": "",
        "stderr": "",
    }
    if check == "cg01_functional":
        if not note_index.exists():
            result["returncode"] = 1
            result["stderr"] = "missing note_index.py"
            return result
        try:
            spec = importlib.util.spec_from_file_location(f"_cg01_note_index_{cwd.name}", note_index)
            if spec is None or spec.loader is None:
                raise RuntimeError("unable to load note_index.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as exc:
            result["returncode"] = 1
            result["stderr"] = f"failed to import note_index.py: {exc}"
            return result
        issues: list[str] = []
        required_symbols = ("count_words_cjk", "process_markdown_file")
        for symbol in required_symbols:
            if not callable(getattr(module, symbol, None)):
                issues.append(f"missing callable: {symbol}")
        if issues:
            result["returncode"] = 1
            result["stderr"] = "; ".join(issues)
            return result

        try:
            extract_title_and_headings = getattr(module, "extract_title_and_headings", None)
            extract_title = getattr(module, "extract_title", None)
            extract_headings = getattr(module, "extract_headings", None)

            def _extract(content: str) -> tuple[str | None, list[str]]:
                if callable(extract_title_and_headings):
                    title_value, headings_value = extract_title_and_headings(content)
                    normalized_title = None if title_value is None else str(title_value)
                    normalized_headings = [str(item) for item in list(headings_value or [])]
                    return normalized_title, normalized_headings
                if callable(extract_title) and callable(extract_headings):
                    title_value = extract_title(content)
                    headings_value = extract_headings(content)
                    normalized_title = None if title_value is None else str(title_value)
                    normalized_headings = [str(item) for item in list(headings_value or [])]
                    return normalized_title, normalized_headings
                raise RuntimeError("missing extract_title_and_headings or extract_title/extract_headings helpers")

            count_expectations = [
                ("你好世界", 4),
                ("这是一个测试", 6),
                ("This is a test 这是一个测试", 10),
                ("Version 1.0", 2),
                ("测试123", 3),
            ]
            for text, expected in count_expectations:
                actual = int(module.count_words_cjk(text))
                if actual != expected:
                    issues.append(f"count_words_cjk({text!r}) expected {expected}, got {actual}")

            title, headings = _extract("# Main Title\n## Section 1\n### Subsection")
            if title != "Main Title":
                issues.append(f"extract_title_and_headings title mismatch: {title!r}")
            if headings != ["Main Title", "Section 1", "Subsection"]:
                issues.append(f"extract_title_and_headings headings mismatch: {headings!r}")

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_root = Path(temp_dir)
                doc1 = temp_root / "doc1.md"
                doc2 = temp_root / "doc2.md"
                doc3 = temp_root / "doc3.md"
                doc1.write_text("# My Document Title\n\nThis is some content.\n## Section One", encoding="utf-8")
                doc2.write_text("Document without H1\n## First Section\nContent here.", encoding="utf-8")
                doc3.write_text("# 中文文档\n这是一个测试内容。Hello world!", encoding="utf-8")
                processed = {
                    "doc1": module.process_markdown_file(doc1),
                    "doc2": module.process_markdown_file(doc2),
                    "doc3": module.process_markdown_file(doc3),
                }
                if processed["doc1"] is None or processed["doc1"].get("word_count") != 9:
                    issues.append(f"process_markdown_file doc1 word_count mismatch: {processed['doc1']}")
                if processed["doc1"] is None or list(processed["doc1"].get("headings") or []) != ["My Document Title", "Section One"]:
                    issues.append(f"process_markdown_file doc1 headings mismatch: {processed['doc1']}")
                if processed["doc2"] is None or processed["doc2"].get("word_count") != 7:
                    issues.append(f"process_markdown_file doc2 word_count mismatch: {processed['doc2']}")
                if processed["doc2"] is None or list(processed["doc2"].get("headings") or []) != ["First Section"]:
                    issues.append(f"process_markdown_file doc2 headings mismatch: {processed['doc2']}")
                if processed["doc3"] is None or processed["doc3"].get("word_count") != 14:
                    issues.append(f"process_markdown_file doc3 word_count mismatch: {processed['doc3']}")

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_root = Path(temp_dir)
                notes_dir = temp_root / "notes"
                (notes_dir / "subdir").mkdir(parents=True, exist_ok=True)
                (notes_dir / "doc1.md").write_text("# Main Title\n\nThis is some content.\n## Section One", encoding="utf-8")
                (notes_dir / "doc2.md").write_text("# 中文文档\n这是一个测试内容。Hello world!", encoding="utf-8")
                (notes_dir / "subdir" / "doc3.md").write_text("Document without H1\n## First Section\nContent here.", encoding="utf-8")
                output_file = temp_root / "index.json"
                cli = subprocess.run(
                    [sys.executable, str(note_index), str(notes_dir), "--output", str(output_file)],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if cli.returncode != 0:
                    issues.append(f"cli failed with returncode {cli.returncode}: {cli.stderr.strip() or cli.stdout.strip()}")
                elif not output_file.exists():
                    issues.append("cli did not create the requested output file")
                else:
                    payload = json.loads(output_file.read_text(encoding="utf-8"))
                    if len(payload) != 3:
                        issues.append(f"cli output entry count mismatch: {len(payload)}")
                    paths = [str(item.get("path") or "") for item in payload]
                    if paths != sorted(paths):
                        issues.append(f"cli output is not sorted by path: {paths}")
                    titles = [str(item.get("title") or "") for item in payload]
                    if titles != ["Main Title", "中文文档", "Document without H1"]:
                        issues.append(f"cli titles mismatch: {titles}")
        except Exception as exc:
            issues.append(f"functional verification raised {exc}")

        if issues:
            result["returncode"] = 1
            result["stderr"] = "; ".join(issues)
        else:
            result["stdout"] = "core note-index behavior passed functional verification"
        return result
    if check == "cg01_artifacts":
        missing = [str(path.relative_to(cwd)) for path in (note_index, tests_path, readme_path) if not path.exists()]
        readme_text = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""
        tests_text = tests_path.read_text(encoding="utf-8") if tests_path.exists() else ""
        test_count = len(re.findall(r"^\s*def test_", tests_text, flags=re.MULTILINE))
        cjk_mentioned = any(token in readme_text or token in tests_text for token in ("CJK", "中文", "Han", "word_count"))
        readme_mentions_run = "python note_index.py" in readme_text and "--output" in readme_text
        tests_compile = True
        try:
            compile(tests_text, str(tests_path), "exec")
        except SyntaxError:
            tests_compile = False
        if missing or not cjk_mentioned or test_count < 3 or not readme_mentions_run or not tests_compile:
            result["returncode"] = 1
            issues = []
            if missing:
                issues.append(f"missing files: {', '.join(missing)}")
            if not cjk_mentioned:
                issues.append("missing explicit CJK word_count note in README/tests")
            if test_count < 3:
                issues.append("tests/test_note_index.py does not contain at least 3 test functions")
            if not readme_mentions_run:
                issues.append("README does not document python note_index.py ... --output ... usage")
            if not tests_compile:
                issues.append("tests/test_note_index.py is not syntactically valid")
            result["stderr"] = "; ".join(issues)
        else:
            result["stdout"] = "note_index.py, tests, README, and test/README contract present"
        return result
    if check == "cg03_artifacts":
        contents = {
            "note_index.py": note_index.read_text(encoding="utf-8") if note_index.exists() else "",
            "tests/test_note_index.py": tests_path.read_text(encoding="utf-8") if tests_path.exists() else "",
            "README.md": readme_path.read_text(encoding="utf-8") if readme_path.exists() else "",
        }
        issues = []
        if "--exclude" not in contents["note_index.py"]:
            issues.append("note_index.py does not expose --exclude")
        if "exclude" not in contents["tests/test_note_index.py"]:
            issues.append("tests do not cover exclude behavior")
        if "--exclude" not in contents["README.md"]:
            issues.append("README does not document --exclude")
        if issues:
            result["returncode"] = 1
            result["stderr"] = "; ".join(issues)
        else:
            result["stdout"] = "exclude flag present in implementation, tests, and README"
        return result
    raise ValueError(f"Unsupported custom verification: {check}")


def _run_verifications(specs: list[dict[str, Any]], cwd: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for spec in specs:
        relative_cwd = Path(spec.get("cwd") or ".")
        resolved_cwd = (cwd / relative_cwd).resolve()
        kind = str(spec.get("kind") or "")
        if kind == "shell":
            results.append(_run_shell_verification(str(spec["command"]), resolved_cwd))
            continue
        if kind == "python":
            results.append(_run_python_verification([str(arg) for arg in spec.get("args") or []], resolved_cwd))
            continue
        if kind == "python-check":
            results.append(_run_custom_verification(str(spec.get("check") or ""), resolved_cwd))
            continue
        raise ValueError(f"Unsupported verification kind: {kind}")
    return results


def _select_live_candidate_models(provider: str, model: str) -> list[dict[str, Any]]:
    from .llm_runtime import load_runtime_candidate_models

    candidates = [
        dict(candidate)
        for candidate in load_runtime_candidate_models() or []
        if str(candidate.get("provider") or "") == provider and str(candidate.get("model") or "") == model
    ]
    if not candidates:
        raise RuntimeError(f"requested live candidate is unavailable: {provider}/{model}")
    return candidates


def _create_runtime_task(task_payload: dict[str, Any]) -> dict[str, Any]:
    from . import get_persistence_runtime
    from .persistence import TaskRepository, WorkspaceBootstrapRepository

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task = TaskRepository(session).create_task(task_payload)
    return task.model_dump(by_alias=True, mode="json")


def _collect_task_runtime_artifacts(task_id: str, workspace_root: Path) -> dict[str, Any]:
    from . import get_persistence_runtime
    from .persistence import PromptAssetRepository, RuntimeRepository, TaskRepository, WorkspaceBootstrapRepository

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        runtime_repository = RuntimeRepository(session)
        prompt_repository = PromptAssetRepository(session)
        task = task_repository.get_task(task_id)
        agent_runs = task_repository.list_agent_runs(task_id)
        snapshots = task_repository.list_snapshots(task_id)
        route_decisions = runtime_repository.list_model_route_decisions(task_id=task_id, limit=20)
        invocations = runtime_repository.list_model_invocations(task_id=task_id, limit=20)
        prompt_artifacts = {}
        for invocation in invocations:
            if invocation.prompt_compile_artifact_id:
                artifact = prompt_repository.get_prompt_compile_artifact(invocation.prompt_compile_artifact_id)
                if artifact is not None:
                    prompt_artifacts[artifact.id] = artifact.model_dump(by_alias=True, mode="json")

    sorted_invocations = sorted(invocations, key=lambda item: item.started_at)
    invocation_payloads = []
    for invocation in sorted_invocations:
        request_payload = _read_json_ref(invocation.request_ref, workspace_root)
        response_payload = _read_json_ref(invocation.response_ref, workspace_root)
        invocation_payloads.append(
            {
                "record": invocation.model_dump(by_alias=True, mode="json"),
                "requestPayload": request_payload,
                "responsePayload": response_payload,
            }
        )

    return {
        "task": task.model_dump(by_alias=True, mode="json") if task is not None else None,
        "agentRuns": [run.model_dump(by_alias=True, mode="json") for run in agent_runs],
        "snapshots": [snapshot.model_dump(by_alias=True, mode="json") for snapshot in snapshots],
        "routeDecisions": [decision.model_dump(by_alias=True, mode="json") for decision in route_decisions],
        "invocations": invocation_payloads,
        "promptArtifacts": prompt_artifacts,
    }


def _run_task_sequence(
    *,
    task_key: str,
    task_def: dict[str, Any],
    sandbox_manifest: dict[str, Any],
    sandbox_root: Path,
    task_workspace: Path,
    provider: str,
    model: str,
    repair_rounds_remaining: int = 1,
) -> dict[str, Any]:
    from .support import new_id

    candidate_models = _select_live_candidate_models(provider, model)
    audit_level = str(task_def.get("auditLevel") or "default")
    pause_resume_attempted = bool(task_def.get("pauseResume"))
    explicit_resume_message = str(task_def.get("resumeMessage") or "").strip() or None
    resume_objective = str(task_def.get("resumeObjective") or task_def["currentObjective"])
    initial_resume_message = explicit_resume_message or (f"Resume {task_key}." if pause_resume_attempted else None)
    env_overrides = dict(sandbox_manifest.get("env") or {})
    env_overrides["YGGDRASIL_GIT_REPO_PATH"] = str(task_workspace.resolve())
    env_overrides["YGGDRASIL_MCP_PROJECT_WORKSPACE"] = str(task_workspace.resolve())
    editable_paths = [str(item) for item in task_def.get("editablePaths") or [] if str(item).strip()]
    if editable_paths:
        env_overrides["YGGDRASIL_MCP_EDIT_ALLOWED_PATHS"] = json.dumps(editable_paths, ensure_ascii=False)
    previous_env = _apply_env(env_overrides)
    task_id = new_id("task", task_key, stable=False)
    started_at = utc_now()
    try:
        from fastapi.testclient import TestClient
        from yggdrasil_agent_runtime.app import app as runtime_app
        from yggdrasil_worker.registry import run_worker_once
        from . import ensure_workspace_bootstrap
        from .mcp_bridge import close_mcp_bridge_sessions, update_mcp_bridge_workspace

        update_mcp_bridge_workspace(str(task_workspace.resolve()))
        close_mcp_bridge_sessions()
        reset_persistence_runtime()
        ensure_workspace_bootstrap()
        active_capabilities = [str(item) for item in task_def.get("activeCapabilities") or []]
        current_context = [dict(item) for item in task_def.get("context") or [] if isinstance(item, dict)]
        if task_key == "YGG-CI-01":
            current_context.extend(_build_ci01_runtime_context(task_workspace))
        if task_key == "YGG-CG-03":
            current_context.extend(_build_cg03_runtime_context(task_workspace))
        registered_tools = _filter_registered_tools(active_capabilities, task_def.get("allowedToolNames"))
        budget_state: dict[str, Any] = {
            "costBudgetTotal": 5.0,
        }
        token_budget_total = _live_task_token_budget(task_def)
        if token_budget_total is not None:
            budget_state["tokenBudgetTotal"] = token_budget_total

        task_payload = {
            "id": task_id,
            "appId": task_def["appId"],
            "taskType": "coding",
            "title": task_def["title"],
            "goal": task_def["goal"],
            "status": "draft",
            "currentObjective": task_def["currentObjective"],
            "currentFocus": task_def["currentFocus"],
            "budgetState": budget_state,
        }
        if initial_resume_message is not None:
            task_payload["resumeMessage"] = initial_resume_message
        task = _create_runtime_task(task_payload)
        client = TestClient(runtime_app)
        start_payload = {
            "taskType": str(task_def.get("runtimeTaskType") or "coding"),
            "currentFocus": task_def["currentFocus"],
            "currentObjective": task_def["currentObjective"],
            "currentContext": current_context,
            "activeCapabilities": active_capabilities,
            "registeredTools": registered_tools,
            "allowModelFallback": False,
            "allowToolExecution": True,
            "candidateModels": candidate_models,
            "temperature": float(task_def.get("temperature") or 0.1),
            "maxTokens": int(task_def.get("maxTokens") or 900),
            "maxToolRounds": int(task_def.get("maxToolRounds") or 16),
            "auditLevel": audit_level,
        }
        if task_def.get("thinking") is not None:
            start_payload["thinking"] = task_def.get("thinking")
        if task_def.get("reasoningEffort") is not None:
            start_payload["reasoningEffort"] = task_def.get("reasoningEffort")
        start_response = client.post(f"/runtime/tasks/{task['id']}/start", json=start_payload)
        if start_response.status_code != 202:
            raise RuntimeError(f"{task_key} start failed: {start_response.text}")

        worker_results: list[dict[str, Any]] = []
        pause_resume_success = False
        if pause_resume_attempted:
            pause_resume_message = explicit_resume_message or f"Resume {task_key}."
            pause_payload = {
                "reason": f"{task_key.lower()}-safe-stop",
                "resumeMessage": pause_resume_message,
            }
            pause_response = client.post(f"/runtime/tasks/{task['id']}/pause-request", json=pause_payload)
            if pause_response.status_code != 202:
                raise RuntimeError(f"{task_key} pause request failed: {pause_response.text}")
            first_attempts = _drain_worker_attempts(run_worker_once)
            worker_results.extend(first_attempts)
            first = first_attempts[-1]
            first_result = first.get("result") or {}
            first_status = str(first_result.get("status") or "")
            snapshot = (first_result.get("snapshot") or {}) if isinstance(first_result.get("snapshot"), dict) else {}
            if first_status == "shutdown-checkpoint":
                snapshot = {
                    "id": first_result.get("snapshotId"),
                    "resumeToken": first_result.get("resumeToken"),
                }
            if first_status not in {"paused", "shutdown-checkpoint"}:
                raise RuntimeError(f"{task_key} did not pause cleanly: {json.dumps(first, ensure_ascii=False)}")
            resume_response = client.post(
                f"/runtime/tasks/{task['id']}/resume",
                json={
                    "resumeToken": snapshot.get("resumeToken"),
                    "resumeMessage": pause_resume_message,
                    "nextObjective": resume_objective,
                },
            )
            if resume_response.status_code != 202:
                raise RuntimeError(f"{task_key} resume request failed: {resume_response.text}")
            second_attempts = _drain_worker_attempts(run_worker_once)
            worker_results.extend(second_attempts)
            second = second_attempts[-1]
            final_result = second
            pause_resume_success = (second.get("result") or {}).get("status") == "completed"
        else:
            final_attempts = _drain_worker_attempts(run_worker_once)
            worker_results.extend(final_attempts)
            final_result = final_attempts[-1]

        if (final_result.get("result") or {}).get("status") != "completed":
            raise RuntimeError(f"{task_key} worker failed: {json.dumps(final_result, ensure_ascii=False)}")

        task_runtime = _collect_task_runtime_artifacts(task_id, Path(sandbox_manifest["workspaceRoot"]))
        verification = _run_verifications(task_def.get("verification") or [], task_workspace)
        diff_summary = _git_diff_summary(task_workspace)
        first_token_seconds = _first_token_seconds(task_runtime.get("invocations") or [])
        first_useful_seconds = _first_useful_output_seconds(task_runtime.get("invocations") or [])
        end_at_raw = (task_runtime.get("task") or {}).get("endedAt")
        start_at_raw = (task_runtime.get("task") or {}).get("startedAt")
        end_at = datetime.fromisoformat(str(end_at_raw).replace("Z", "+00:00")) if end_at_raw else None
        persisted_start_at = datetime.fromisoformat(str(start_at_raw).replace("Z", "+00:00")) if start_at_raw else started_at
        issues = []
        for item in verification:
            if int(item.get("returncode") or 0) == 0:
                continue
            detail = str(item.get("stderr") or "").strip() or str(item.get("stdout") or "").strip()
            if detail:
                issues.append(detail)
        trace_ids = [
            str((item.get("record") or {}).get("traceId"))
            for item in task_runtime.get("invocations") or []
            if (item.get("record") or {}).get("traceId")
        ]
        attempt_result = {
            "taskKey": task_key,
            "taskId": task_id,
            "taskWorkspace": str(task_workspace.resolve()),
            "appId": task_def["appId"],
            "auditLevel": audit_level,
            "workerResults": worker_results,
            "taskRuntime": task_runtime,
            "verification": verification,
            "diffSummary": diff_summary,
            "issues": issues,
            "traceIds": trace_ids,
            "toolExecutionNames": _tool_execution_names(task_runtime.get("invocations") or []),
            "firstTokenSeconds": first_token_seconds,
            "firstTokenAt": _first_token_at(task_runtime.get("invocations") or [], first_token_seconds),
            "firstUsefulOutputSeconds": first_useful_seconds,
            "firstUsefulOutputAt": _first_useful_output_at(task_runtime.get("invocations") or [], first_useful_seconds),
            "startAt": _format_timestamp(persisted_start_at),
            "endAt": _format_timestamp(end_at),
            "totalDurationSeconds": _seconds_between(persisted_start_at, end_at),
            "finalStatus": (final_result.get("result") or {}).get("status"),
            "pauseResumeAttempted": pause_resume_attempted,
            "pauseResumeSuccess": pause_resume_success,
            "assistantPreview": str((final_result.get("result") or {}).get("assistantText") or ""),
        }
        if issues and repair_rounds_remaining > 0:
            repair_task_def = dict(task_def)
            repair_task_def["pauseResume"] = False
            repair_task_def["resumeMessage"] = None
            repair_task_def["currentFocus"] = f"{task_def['currentFocus']} repair"
            repair_task_def["currentObjective"] = (
                f"Repair the existing {task_key} workspace so all failed verifications pass. "
                "Work from the files already created instead of restarting from scratch."
            )
            repair_task_def["goal"] = _build_repair_goal(task_key, verification)
            repair_context = [dict(item) for item in task_def.get("context") or []]
            if task_key == "YGG-CG-01":
                repair_task_def["allowedToolNames"] = ["mcp.read.read_file", "mcp.edit.write_file"]
                preferred_context_ids = {
                    "cg01_scope",
                    "cg01_cjk_rule",
                    "cg01_behavior_examples",
                    "cg01_heading_guard",
                    "cg01_validation_handoff",
                    "cg01_tokenization_hint",
                    "cg01_final_state",
                    "cg01_no_extras",
                }
                repair_context = [
                    item
                    for item in repair_context
                    if str(item.get("id") or "") in preferred_context_ids
                ]
            repair_task_def["context"] = [
                _build_repair_context(task_key, verification),
                *repair_context,
            ]
            repaired_result = _run_task_sequence(
                task_key=task_key,
                task_def=repair_task_def,
                sandbox_manifest=sandbox_manifest,
                sandbox_root=sandbox_root,
                task_workspace=task_workspace,
                provider=provider,
                model=model,
                repair_rounds_remaining=repair_rounds_remaining - 1,
            )
            repaired_result["repairAttempts"] = [attempt_result, *(repaired_result.get("repairAttempts") or [])]
            return repaired_result
        return attempt_result
    finally:
        close_mcp_bridge_sessions()
        reset_persistence_runtime()
        _restore_env(previous_env)


def _build_live_pack_summary(
    *,
    sandbox_root: Path,
    manifest_path: Path,
    sandbox_manifest: dict[str, Any],
    source_workspace: Path,
    sandbox_workspace: Path,
    preparation: dict[str, Any],
    results: list[dict[str, Any]],
    provider: str,
    model: str,
    scorecard_csv: Path | None,
    batch_id: str | None,
    environment_id: str | None,
    failed_task_key: str | None = None,
    fatal_error: str | None = None,
) -> dict[str, Any]:
    successful_first_useful = [
        float(item["firstUsefulOutputSeconds"])
        for item in results
        if item.get("firstUsefulOutputSeconds") is not None and not item.get("issues")
    ]
    fastest_first_useful = min(successful_first_useful) if successful_first_useful else None
    resolved_batch_id = batch_id or f"G2-LIVE-{utc_now().strftime('%Y%m%d')}"
    resolved_environment_id = environment_id or f"sandbox-live-{utc_now().strftime('%Y%m%d')}"
    coordination_backend = str((sandbox_manifest.get("env") or {}).get("YGGDRASIL_COORDINATION_BACKEND") or "memory")
    scorecard_rows = [
        _build_scorecard_row(
            task_key=item["taskKey"],
            task_def=_REAL_USER_LIVE_TASK_DEFS[item["taskKey"]],
            execution=item,
            fastest_first_useful=fastest_first_useful,
            provider=provider,
            model=model,
            batch_id=resolved_batch_id,
            environment_id=resolved_environment_id,
            coordination_backend=coordination_backend,
        )
        for item in results
    ]
    if scorecard_csv is not None:
        _append_scorecard_rows(scorecard_csv.resolve(), scorecard_rows)

    summary = {
        "generatedAt": utc_now().isoformat(),
        "sandboxRoot": str(sandbox_root),
        "sandboxManifest": str(manifest_path),
        "workspaceRoot": str(sandbox_workspace),
        "sourceWorkspace": str(source_workspace),
        "provider": provider,
        "model": model,
        "batchId": resolved_batch_id,
        "environmentId": resolved_environment_id,
        "preparation": preparation,
        "tasks": results,
        "scorecardRows": scorecard_rows,
        "scorecardCsv": str(scorecard_csv.resolve()) if scorecard_csv is not None else None,
    }
    if failed_task_key is not None:
        summary["failedTaskKey"] = failed_task_key
    if fatal_error is not None:
        summary["fatalError"] = fatal_error
    return summary


def run_real_user_live_task_pack(
    *,
    sandbox_root: Path,
    tasks: list[str] | None = None,
    provider: str = "longcat",
    model: str = "LongCat-Flash-Lite",
    scorecard_csv: Path | None = None,
    output_path: Path | None = None,
    batch_id: str | None = None,
    environment_id: str | None = None,
) -> dict[str, Any]:
    sandbox_root = sandbox_root.expanduser().resolve()
    manifest_path = sandbox_root / "sandbox-manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Sandbox manifest missing: {manifest_path}")
    sandbox_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_workspace = Path(str(sandbox_manifest.get("sourceWorkspace") or "")).resolve()
    sandbox_workspace = Path(str(sandbox_manifest.get("workspaceRoot") or "")).resolve()
    selected_tasks = tasks or list(_REAL_USER_LIVE_TASK_ORDER)
    unknown = [task for task in selected_tasks if task not in _REAL_USER_LIVE_TASK_DEFS]
    if unknown:
        raise ValueError(f"Unsupported live task(s): {', '.join(unknown)}")

    ci01_workspace = sandbox_workspace
    pack_a_workspace: Path | None = None
    preparation: dict[str, Any] = {}
    if "YGG-CI-01" in selected_tasks:
        preparation["YGG-CI-01"] = _prepare_ci01_baseline(ci01_workspace)
    if any(task_key in selected_tasks for task_key in ("YGG-CG-01", "YGG-CG-03")):
        pack_a_workspace = _prepare_greenfield_workspace(sandbox_root)
        if "YGG-CG-03" in selected_tasks and "YGG-CG-01" not in selected_tasks:
            _seed_cg01_reference_solution(pack_a_workspace)
            _ensure_git_repo(pack_a_workspace, baseline_message="prepare YGG-CG-03 inherited baseline")
        preparation["YGG-CG-01"] = {"workspace": str(pack_a_workspace.resolve())}
        preparation["YGG-CG-03"] = {"workspace": str(pack_a_workspace.resolve())}

    results: list[dict[str, Any]] = []
    failure: Exception | None = None
    failed_task_key: str | None = None
    for task_key in selected_tasks:
        task_def = _REAL_USER_LIVE_TASK_DEFS[task_key]
        if task_key == "YGG-CI-01":
            task_workspace = ci01_workspace
        else:
            if pack_a_workspace is None:
                raise RuntimeError(f"Greenfield workspace was not prepared for task {task_key}")
            task_workspace = pack_a_workspace
        try:
            execution = _run_task_sequence(
                task_key=task_key,
                task_def=task_def,
                sandbox_manifest=sandbox_manifest,
                sandbox_root=sandbox_root,
                task_workspace=task_workspace,
                provider=provider,
                model=model,
            )
            results.append(execution)
            if task_key == "YGG-CG-01":
                _ensure_git_repo(task_workspace, baseline_message="prepare YGG-CG-03 baseline")
        except Exception as exc:
            failed_task_key = task_key
            failure = exc
            results.append(
                {
                    "taskKey": task_key,
                    "taskId": None,
                    "taskWorkspace": str(task_workspace.resolve()),
                    "appId": task_def["appId"],
                    "auditLevel": str(task_def.get("auditLevel") or "default"),
                    "workerResults": [],
                    "taskRuntime": {},
                    "verification": [],
                    "diffSummary": {},
                    "issues": [str(exc)],
                    "traceIds": [],
                    "toolExecutionNames": [],
                    "firstUsefulOutputSeconds": None,
                    "firstUsefulOutputAt": None,
                    "startAt": None,
                    "endAt": None,
                    "totalDurationSeconds": None,
                    "finalStatus": "failed",
                    "pauseResumeAttempted": bool(task_def.get("pauseResume")),
                    "pauseResumeSuccess": False,
                    "assistantPreview": "",
                    "fatalError": str(exc),
                }
            )
            break

    summary = _build_live_pack_summary(
        sandbox_root=sandbox_root,
        manifest_path=manifest_path,
        sandbox_manifest=sandbox_manifest,
        source_workspace=source_workspace,
        sandbox_workspace=sandbox_workspace,
        preparation=preparation,
        results=results,
        provider=provider,
        model=model,
        scorecard_csv=scorecard_csv,
        batch_id=batch_id,
        environment_id=environment_id,
        failed_task_key=failed_task_key,
        fatal_error=str(failure) if failure is not None else None,
    )
    output_target = _task_pack_output_path(output_path, source_workspace)
    output_file = _write_json_output(output_target, summary)
    if output_file is not None:
        summary["outputFile"] = output_file
    if failure is not None:
        raise failure
    return summary

from .live_setup import *  # noqa: F403,F401

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
    from ..llm_runtime import load_runtime_candidate_models

    candidates = [
        dict(candidate)
        for candidate in load_runtime_candidate_models() or []
        if str(candidate.get("provider") or "") == provider and str(candidate.get("model") or "") == model
    ]
    if not candidates:
        raise RuntimeError(f"requested live candidate is unavailable: {provider}/{model}")
    return candidates


def _create_runtime_task(task_payload: dict[str, Any]) -> dict[str, Any]:
    from .. import get_persistence_runtime
    from ..persistence import TaskRepository, WorkspaceBootstrapRepository

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task = TaskRepository(session).create_task(task_payload)
    return task.model_dump(by_alias=True, mode="json")


def _collect_task_runtime_artifacts(task_id: str, workspace_root: Path) -> dict[str, Any]:
    from .. import get_persistence_runtime
    from ..persistence import PromptAssetRepository, RuntimeRepository, TaskRepository, WorkspaceBootstrapRepository

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
    from ..support import new_id

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
        from .. import ensure_workspace_bootstrap
        from ..mcp_bridge import close_mcp_bridge_sessions, update_mcp_bridge_workspace

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
            pause_response = client.post(f"/runtime/tasks/{task['id']}/pause", json=pause_payload)
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
                }
            if first_status not in {"paused", "shutdown-checkpoint"}:
                raise RuntimeError(f"{task_key} did not pause cleanly: {json.dumps(first, ensure_ascii=False)}")
            resume_response = client.post(
                f"/runtime/tasks/{task['id']}/resume",
                json={
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
    model: str = "LongCat-2.0",
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

__all__ = [name for name in globals() if not name.startswith("__")]


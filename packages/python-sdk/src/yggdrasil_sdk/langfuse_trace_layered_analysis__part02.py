def _safe_json_loads(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value
def _coerce_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
def _compact_window_list(windows: list[int]) -> str:
    if not windows:
        return "-"
    sorted_windows = sorted(set(windows))
    ranges: list[str] = []
    start = sorted_windows[0]
    previous = sorted_windows[0]
    for value in sorted_windows[1:]:
        if value == previous + 1:
            previous = value
            continue
        ranges.append(f"{start}-{previous}" if start != previous else str(start))
        start = value
        previous = value
    ranges.append(f"{start}-{previous}" if start != previous else str(start))
    return ", ".join(ranges)
def _canonicalize_runtime_text(text: str) -> str:
    normalized = _normalize_text(text)
    for pattern, replacement in _DYNAMIC_ID_PATTERNS:
        normalized = pattern.sub(replacement, normalized)
    normalized = re.sub(r"\b\d{4,}\b", "<num>", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()
def _window_text_excerpt(window: WindowRecord, limit: int = 260) -> str:
    if not window.rawContext.strip():
        return "-"
    canonical = _canonicalize_runtime_text(window.rawContext)
    return normalize_excerpt(canonical, limit) or "-"
def _text_units(text: str) -> list[str]:
    normalized = _canonicalize_runtime_text(text)
    if not normalized:
        return []
    parts = re.split(r"[\n。！？;；]+", normalized)
    units: list[str] = []
    for part in parts:
        compact = " ".join(part.split()).strip()
        if len(compact) >= 12:
            units.append(compact)
    return units
def _text_delta_summary(current_text: str, reference_text: str) -> str:
    current_canonical = _canonicalize_runtime_text(current_text)
    reference_canonical = _canonicalize_runtime_text(reference_text)
    if current_canonical == reference_canonical:
        return "与代表窗口文本等价，仅动态 ID 或计数不同。"
    current_units = _text_units(current_text)
    reference_units = _text_units(reference_text)
    reference_set = set(reference_units)
    current_set = set(current_units)
    added = [item for item in current_units if item not in reference_set][:2]
    removed = [item for item in reference_units if item not in current_set][:2]
    parts: list[str] = []
    if added:
        parts.append("新增: " + " / ".join(normalize_excerpt(item, 96) for item in added))
    if removed:
        parts.append("移除: " + " / ".join(normalize_excerpt(item, 96) for item in removed))
    if parts:
        return "；".join(parts)
    return "文本整体相近，但存在局部措辞变化。"
def _message_excerpt_payload(messages: list[ConversationMessage], *, limit: int = 220) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for message in messages:
        payload.append(
            {
                "role": message.role,
                "index": message.index,
                "excerpt": normalize_excerpt(message.content, limit) or "-",
            }
        )
    return payload
def _hash_fingerprint_payload(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(serialized.encode("utf-8")).hexdigest()[:12]
def _normalize_list(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for raw in values:
        compact = " ".join(str(raw or "").split()).strip().lower()
        if compact:
            normalized.append(compact)
    return normalized
def _extract_window_contract_fields(window: WindowRecord) -> dict[str, Any]:
    raw_context = window.rawContext
    work_tree_match = _WORK_TREE_HANDOFF_PATTERN.search(raw_context)
    protected_refs_raw = _extract_task_field(_PROTECTED_REFS_PATTERN, raw_context)
    return {
        "currentObjective": _extract_task_field(_CURRENT_OBJECTIVE_PATTERN, raw_context),
        "currentFocus": _extract_task_field(_CURRENT_FOCUS_PATTERN, raw_context),
        "restartInstruction": _extract_task_field(_RESTART_INSTRUCTION_PATTERN, raw_context),
        "memoryRetrievalSummary": _extract_task_field(_MEMORY_HANDOFF_PATTERN, raw_context),
        "protectedRefs": [item.strip() for item in protected_refs_raw.split(",") if item.strip()] if protected_refs_raw else [],
        "workTreeStatus": work_tree_match.group("status").strip() if work_tree_match is not None else "",
        "workTreeCurrentNode": (
            work_tree_match.group("currentNode").strip()
            if work_tree_match is not None
            else str(window.workTreeNode or "").strip()
        ),
        "workTreeRecoveryAnchor": work_tree_match.group("recoveryAnchor").strip() if work_tree_match is not None else "",
    }
def _window_fingerprint_payload(window: WindowRecord, runtime_window_record: dict[str, Any] | None = None) -> dict[str, Any]:
    contract = _extract_window_contract_fields(window)
    runtime_memory_state = runtime_window_record.get("memoryRetrievalState") if isinstance(runtime_window_record, dict) and isinstance(runtime_window_record.get("memoryRetrievalState"), dict) else {}
    return {
        "topNodes": _normalize_list(window.topNodes),
        "workTreeNode": str((runtime_window_record or {}).get("workTreeCurrentNodeId") or window.workTreeNode or contract.get("workTreeCurrentNode") or "").strip().lower(),
        "rehydratedContextCount": window.rehydratedContextCount,
        "restoredFieldCount": window.restoredFieldCount,
        "retrievedNodeCount": (runtime_memory_state.get("matchedNodeCount") if runtime_memory_state else None) or window.retrievedNodeCount,
        "materializedContextCount": (runtime_memory_state.get("materializedNodeCount") if runtime_memory_state else None) or window.materializedContextCount,
        "retrievalFingerprint": runtime_memory_state.get("retrievalFingerprint") if runtime_memory_state else "",
        "currentObjective": str((runtime_window_record or {}).get("currentObjective") or contract.get("currentObjective") or ""),
        "currentFocus": str((runtime_window_record or {}).get("currentFocus") or contract.get("currentFocus") or ""),
        "restartInstruction": str((runtime_window_record or {}).get("restartMessageDigest") or contract.get("restartInstruction") or ""),
        "responseRequirementsDigest": str((runtime_window_record or {}).get("responseRequirementsDigest") or ""),
        "memoryRetrievalSummary": str(runtime_memory_state.get("summary") or contract.get("memoryRetrievalSummary") or "") if runtime_memory_state else contract.get("memoryRetrievalSummary") or "",
        "protectedRefs": (runtime_window_record or {}).get("protectedRefIds") or contract.get("protectedRefs") or [],
        "workTreeStatus": str((runtime_window_record or {}).get("workTreeStatus") or contract.get("workTreeStatus") or ""),
        "workTreeRecoveryAnchor": str((runtime_window_record or {}).get("workTreeRecoveryAnchor") or contract.get("workTreeRecoveryAnchor") or ""),
        "stateFingerprint": str((runtime_window_record or {}).get("stateFingerprint") or ""),
    }
def _candidate_db_paths(workspace_root: Path) -> list[Path]:
    candidates = [
        workspace_root / ".yggdrasil" / "evaluation.db",
        workspace_root / ".yggdrasil" / "runtime.db",
    ]
    sandboxes_root = workspace_root / ".yggdrasil" / "state" / "evaluation-sandboxes"
    if sandboxes_root.exists():
        candidates.extend(sorted(sandboxes_root.glob("**/evaluation.db")))
    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        candidate_str = str(candidate)
        if candidate_str in seen or not candidate.exists():
            continue
        seen.add(candidate_str)
        deduped.append(candidate)
    return deduped
def _candidate_window_execution_paths(workspace_root: Path) -> list[Path]:
    state_dir = resolve_state_dir(workspace_root)
    candidate_dirs = [state_dir / "runtime" / "window-executions"]
    sandboxes_root = state_dir / "evaluation-sandboxes"
    if sandboxes_root.exists():
        for sandbox in sandboxes_root.iterdir():
            if not sandbox.is_dir():
                continue
            candidate_dirs.append(sandbox / ".yggdrasil" / "state" / "runtime" / "window-executions")
    deduped: list[Path] = []
    seen: set[str] = set()
    for directory in candidate_dirs:
        if not directory.exists() or not directory.is_dir():
            continue
        for candidate in sorted(directory.glob("*.json")):
            candidate_str = str(candidate)
            if candidate_str in seen:
                continue
            seen.add(candidate_str)
            deduped.append(candidate)
    return deduped
def _load_window_execution_records(task_id: str, workspace_root: Path) -> dict[int, list[dict[str, Any]]]:
    records_by_window: dict[int, list[dict[str, Any]]] = {}
    if not task_id:
        return records_by_window
    for candidate in _candidate_window_execution_paths(workspace_root):
        payload = read_json(candidate, {})
        if not isinstance(payload, dict):
            continue
        if str(payload.get("taskId") or "").strip() != task_id:
            continue
        window_index = _coerce_int(payload.get("windowIndex")) or 1
        payload["artifactPath"] = str(candidate)
        records_by_window.setdefault(window_index, []).append(payload)
    return records_by_window
def _table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    row = cursor.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return bool(row and row[0])
def _load_local_db_trace_match(
    *,
    trace_id: str,
    evidence: ObservationEvidence,
    workspace_root: Path,
) -> LocalDbTraceMatch | None:
    fallback_window_records = _load_window_execution_records(str(evidence.taskId or "").strip(), workspace_root) if evidence.taskId else {}
    for db_path in _candidate_db_paths(workspace_root):
        try:
            connection = sqlite3.connect(db_path)
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            if not _table_exists(cursor, "model_invocations") or not _table_exists(cursor, "tasks"):
                connection.close()
                continue

            matched_by = ""
            rows: list[sqlite3.Row] = []
            if evidence.invocationId:
                rows = cursor.execute(
                    "SELECT * FROM model_invocations WHERE id = ? ORDER BY created_at",
                    (evidence.invocationId,),
                ).fetchall()
                if rows:
                    matched_by = "invocationId"
            if not rows:
                rows = cursor.execute(
                    "SELECT * FROM model_invocations WHERE trace_id = ? ORDER BY created_at",
                    (trace_id,),
                ).fetchall()
                if rows:
                    matched_by = "traceId"
            if not rows and evidence.taskId:
                rows = cursor.execute(
                    "SELECT * FROM model_invocations WHERE task_id = ? ORDER BY created_at",
                    (evidence.taskId,),
                ).fetchall()
                if rows:
                    matched_by = "taskId"
            if not rows:
                connection.close()
                continue

            task_id = str(rows[0]["task_id"] or evidence.taskId or "").strip()
            if not task_id:
                connection.close()
                continue
            task_row = cursor.execute(
                "SELECT id, agent_run_id, execution_root_node_id FROM task_snapshots WHERE task_id = ? ORDER BY created_at DESC LIMIT 1",
                (task_id,),
            ).fetchone() if _table_exists(cursor, "task_snapshots") else None
            task_info = cursor.execute(
                "SELECT id, execution_root_node_id FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            execution_root_node_id = (
                str(task_info["execution_root_node_id"]).strip()
                if task_info is not None and task_info["execution_root_node_id"] is not None
                else None
            )
            node_writes_by_window: dict[int, list[dict[str, Any]]] = {}
            if execution_root_node_id is not None and _table_exists(cursor, "nodes"):
                node_rows = cursor.execute(
                    "SELECT id, title, window_index, source_work_tree_node_id, created_at FROM nodes WHERE parent_id = ? ORDER BY window_index, created_at",
                    (execution_root_node_id,),
                ).fetchall()
                for row in node_rows:
                    window_index = _coerce_int(row["window_index"]) or 1
                    node_writes_by_window.setdefault(window_index, []).append(
                        {
                            "id": str(row["id"]),
                            "title": str(row["title"]),
                            "sourceWorkTreeNodeId": str(row["source_work_tree_node_id"] or "").strip() or None,
                            "createdAt": str(row["created_at"]),
                        }
                    )

            restart_snapshots_by_window: dict[int, list[dict[str, Any]]] = {}
            if _table_exists(cursor, "task_snapshots"):
                snapshot_rows = cursor.execute(
                    "SELECT id, pending_actions, created_at FROM task_snapshots WHERE task_id = ? AND snapshot_type = 'restart' ORDER BY created_at",
                    (task_id,),
                ).fetchall()
                for row in snapshot_rows:
                    pending_actions = _safe_json_loads(row["pending_actions"])
                    if not isinstance(pending_actions, list):
                        continue
                    for action in pending_actions:
                        if not isinstance(action, dict) or action.get("kind") != "window-restart":
                            continue
                        target_window = _coerce_int(action.get("targetWindowIndex"))
                        if target_window is None:
                            continue
                        restart_snapshots_by_window.setdefault(target_window, []).append(
                            {
                                "id": str(row["id"]),
                                "createdAt": str(row["created_at"]),
                                "carryForwardSummary": str(action.get("carryForwardSummary") or "").strip(),
                                "windowSpanTokens": _coerce_int(action.get("windowSpanTokens")),
                                "effectiveContextWindow": _coerce_int(action.get("effectiveContextWindow")),
                            }
                        )
            window_execution_by_window = _load_window_execution_records(task_id, workspace_root)
            connection.close()
            return LocalDbTraceMatch(
                dbPath=str(db_path),
                matchedBy=matched_by,
                taskId=task_id,
                agentRunId=str(rows[0]["agent_run_id"] or "").strip() or None,
                executionRootNodeId=execution_root_node_id,
                nodeWritesByWindow=node_writes_by_window,
                restartSnapshotsByWindow=restart_snapshots_by_window,
                windowExecutionByWindow=window_execution_by_window,
            )
        except sqlite3.Error:
            continue
    if evidence.taskId and fallback_window_records:
        return LocalDbTraceMatch(
            dbPath="",
            matchedBy="window-execution-artifact",
            taskId=str(evidence.taskId),
            agentRunId=evidence.agentRunId,
            executionRootNodeId=None,
            nodeWritesByWindow={},
            restartSnapshotsByWindow={},
            windowExecutionByWindow=fallback_window_records,
        )
    return None
def _observation_tool_execution_count(evidence: ObservationEvidence) -> int | None:
    if evidence.localArtifacts is not None:
        tool_executions = evidence.localArtifacts.responsePayload.get("toolExecutions")
        if isinstance(tool_executions, list):
            return len([item for item in tool_executions if isinstance(item, dict)])
    metadata_count = _coerce_int(evidence.metadata.get("toolExecutionCount"))
    if metadata_count is not None:
        return metadata_count
    return None
def _observation_output_tokens(evidence: ObservationEvidence) -> int | None:
    for key in ("completion_tokens", "output_tokens", "outputTokens"):
        value = _coerce_int(evidence.usageDetails.get(key))
        if value is not None:
            return value
    return None
def _final_invocation_token_delta(evidence: ObservationEvidence) -> int | None:
    if evidence.localArtifacts is None:
        return None
    observations = evidence.localArtifacts.responsePayload.get("contextLengthObservations")
    if not isinstance(observations, list):
        return None
    before_model = None
    task_end = None
    for item in observations:
        if not isinstance(item, dict):
            continue
        phase = str(item.get("phase") or "")
        estimated_tokens = _coerce_int(item.get("estimatedTokens"))
        if phase == "beforeModelInvocation":
            before_model = estimated_tokens
        elif phase == "taskEnd":
            task_end = estimated_tokens
    if before_model is None or task_end is None:
        return None
    return task_end - before_model
def _build_window_execution_audits(
    evidence: ObservationEvidence,
    local_db_match: LocalDbTraceMatch | None,
) -> list[dict[str, Any]]:
    windows = evidence.windows or [
        WindowRecord(
            window=1,
            snapshot="-",
            rawContext="",
            topNodes=[],
            workTreeNode=None,
            rehydratedContextCount=None,
            restoredFieldCount=None,
            retrievedNodeCount=None,
            materializedContextCount=None,
        )
    ]
    groups_by_fingerprint: dict[str, dict[str, Any]] = {}
    audits: list[dict[str, Any]] = []
    for index, window in enumerate(windows):
        runtime_window_records = local_db_match.windowExecutionByWindow.get(window.window, []) if local_db_match is not None else []
        runtime_window_record = runtime_window_records[-1] if runtime_window_records else None
        payload = _window_fingerprint_payload(window, runtime_window_record)
        fingerprint = _hash_fingerprint_payload(payload)
        group = groups_by_fingerprint.get(fingerprint)
        if group is None:
            group = {
                "label": f"G{len(groups_by_fingerprint) + 1}",
                "anchorWindow": window.window,
            }
            groups_by_fingerprint[fingerprint] = group

        previous = audits[-1] if audits else None
        retrieval_changed = None
        contract_changed = None
        work_tree_changed = None
        if previous is not None:
            previous_payload = previous["fingerprintPayload"]
            retrieval_changed = (
                previous_payload.get("topNodes") != payload.get("topNodes")
                or previous_payload.get("retrievalFingerprint") != payload.get("retrievalFingerprint")
                or previous_payload.get("retrievedNodeCount") != payload.get("retrievedNodeCount")
                or previous_payload.get("materializedContextCount") != payload.get("materializedContextCount")
            )
            contract_changed = any(
                previous_payload.get(key) != payload.get(key)
                for key in ("currentObjective", "currentFocus", "restartInstruction", "responseRequirementsDigest", "memoryRetrievalSummary", "protectedRefs")
            )
            work_tree_changed = any(
                previous_payload.get(key) != payload.get(key)
                for key in ("workTreeNode", "workTreeStatus", "workTreeRecoveryAnchor", "stateFingerprint")
            )

        local_nodes = local_db_match.nodeWritesByWindow.get(window.window, []) if local_db_match is not None else []
        restart_snapshots = local_db_match.restartSnapshotsByWindow.get(window.window, []) if local_db_match is not None else []

        classification = "cluster-anchor-window"
        keep_reason = f"重复簇 {group['label']} 的首个代表窗口。"
        keep = True
        discard_candidate = False
        if index == 0:
            classification = "bootstrap-window"
            keep_reason = "初始窗口，负责建立任务骨架和首个检索锚点。"
        elif index == len(windows) - 1:
            classification = "delivery-window"
            keep_reason = "最终窗口，负责产出最终交付。"
        elif group["anchorWindow"] != window.window and local_nodes:
            classification = "repeated-but-memory-write"
            keep_reason = "虽然指纹重复，但本地 DB 记录到新的节点写入。"
        elif group["anchorWindow"] != window.window:
            classification = "repeated-carry-forward-window"
            keep = False
            discard_candidate = True
            keep_reason = f"与窗口 {group['anchorWindow']} 指纹一致，可在人工分析时折叠。"

        evidence_lines: list[str] = []
        if window.materializedContextCount is not None and index == 0:
            evidence_lines.append(f"初始化阶段先物化了 {window.materializedContextCount} 条运行时上下文。")
        if previous is not None and retrieval_changed is False:
            evidence_lines.append("与上一窗口相比，检索结果集没有变化。")
        if previous is not None and contract_changed is False:
            evidence_lines.append("与上一窗口相比，restart 合同没有变化。")
        if previous is not None and work_tree_changed is False:
            evidence_lines.append("与上一窗口相比，work tree 锚点没有变化。")
        if local_nodes:
            evidence_lines.append(f"本地 DB 记录到 {len(local_nodes)} 个新增节点。")
        if restart_snapshots:
            evidence_lines.append(f"本地 DB 记录到 {len(restart_snapshots)} 次对应窗口的 restart 快照。")
        if runtime_window_record is not None:
            evidence_lines.append(
                "runtime window record: "
                f"outcome={runtime_window_record.get('transitionOutcome')}, "
                f"contextItems={runtime_window_record.get('currentContextCount')}, "
                f"workTree={runtime_window_record.get('workTreeCurrentNodeId') or '-'}。"
            )
            planning_stub_flag = ((runtime_window_record.get("llm") or {}).get("planningStub0_1") if isinstance(runtime_window_record.get("llm"), dict) else None)
            if planning_stub_flag is not None:
                evidence_lines.append(f"runtime window record 标记 planningStub0_1={planning_stub_flag}。")
        if not evidence_lines:
            evidence_lines.append("该窗口首次引入了一组新的执行指纹。")

        if local_nodes:
            memory_tree_signal = f"local-db: 新增 {len(local_nodes)} 个节点"
        elif runtime_window_record is not None:
            memory_tree_signal = (
                "runtime-window-record: "
                f"retrievalFingerprint={payload.get('retrievalFingerprint') or '-'}, "
                f"workTree={runtime_window_record.get('workTreeCurrentNodeId') or '-'}"
            )
        elif previous is not None and retrieval_changed is False and work_tree_changed is False:
            memory_tree_signal = "langfuse-proxy: 未观察到检索集或 work tree 变化"
        elif previous is not None and (retrieval_changed or work_tree_changed):
            signal_parts: list[str] = []
            if retrieval_changed:
                signal_parts.append("检索集变化")
            if work_tree_changed:
                signal_parts.append("work tree 变化")
            memory_tree_signal = "langfuse-proxy: " + "，".join(signal_parts)
        elif window.materializedContextCount is not None:
            memory_tree_signal = f"langfuse-proxy: 物化 {window.materializedContextCount} 条上下文"
        else:
            memory_tree_signal = "证据不足"

        audits.append(
            {
                "window": window.window,
                "snapshot": window.snapshot,
                "classification": classification,
                "keep": keep,
                "discardCandidate": discard_candidate,
                "keepReason": keep_reason,
                "redundancyGroup": group["label"],
                "anchorWindow": group["anchorWindow"],
                "fingerprint": fingerprint,
                "fingerprintPayload": payload,
                "retrievalChanged": retrieval_changed,
                "contractChanged": contract_changed,
                "workTreeChanged": work_tree_changed,
                "memoryTreeSignal": memory_tree_signal,
                "localNodeWriteCount": len(local_nodes),
                "localNodeTitles": [str(item.get("title") or "") for item in local_nodes],
                "restartSnapshotCount": len(restart_snapshots),
                "runtimeWindowRecordCount": len(runtime_window_records),
                "runtimeWindowOutcome": runtime_window_record.get("transitionOutcome") if isinstance(runtime_window_record, dict) else None,
                "runtimeWindowPlanningStub0_1": ((runtime_window_record.get("llm") or {}).get("planningStub0_1") if isinstance(runtime_window_record, dict) and isinstance(runtime_window_record.get("llm"), dict) else None),
                "evidence": evidence_lines,
            }
        )
    return audits
def _build_observation_execution_audit(
    *,
    trace_id: str,
    evidence: ObservationEvidence,
    workspace_root: Path | None,
) -> dict[str, Any]:
    resolved_workspace = resolve_workspace_root(workspace_root)
    local_db_match = _load_local_db_trace_match(trace_id=trace_id, evidence=evidence, workspace_root=resolved_workspace)
    window_audits = _build_window_execution_audits(evidence, local_db_match)
    discard_windows = [audit["window"] for audit in window_audits if audit["discardCandidate"]]
    keep_windows = [audit["window"] for audit in window_audits if audit["keep"]]
    redundancy_groups: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for audit in window_audits:
        grouped.setdefault(str(audit["redundancyGroup"]), []).append(audit)
    for label, items in grouped.items():
        if len(items) <= 1:
            continue
        anchor_window = min(int(item["anchorWindow"]) for item in items)
        repeated_windows = [int(item["window"]) for item in items if int(item["window"]) != anchor_window]
        redundancy_groups.append(
            {
                "label": label,
                "anchorWindow": anchor_window,
                "repeatedWindows": repeated_windows,
                "reason": (
                    "这些窗口的检索结果、restart 合同和 work tree 锚点指纹一致，"
                    "可在执行分析时折叠为同一个代表窗口。"
                ),
            }
        )
    redundancy_groups.sort(key=lambda item: int(item["anchorWindow"]))

    output_tags = _extract_output_tags(evidence.outputText)
    data_sources = ["langfuse:input.messages", "langfuse:metadata", "langfuse:output"]
    if evidence.localArtifacts is not None:
        data_sources.append("local-llm-artifacts")
    if local_db_match is not None:
        if local_db_match.dbPath:
            data_sources.append(f"local-db:{Path(local_db_match.dbPath).name}")
        if local_db_match.windowExecutionByWindow:
            data_sources.append("local-runtime-window-execution")

    tool_execution_count = _observation_tool_execution_count(evidence)
    output_tokens = _observation_output_tokens(evidence)
    final_token_delta = _final_invocation_token_delta(evidence)
    memory_evidence_level = (
        "local-db"
        if local_db_match is not None
        else "local-artifact"
        if evidence.localArtifacts is not None
        else "langfuse-proxy"
    )
    assessment = (
        f"检测到 {len(discard_windows)} 个可折叠窗口：{_compact_window_list(discard_windows)}。"
        if discard_windows
        else "没有检测到可直接折叠的重复窗口。"
    )
    ui_review_plan = [
        f"在 Langfuse UI 中按 traceId={trace_id} 搜索这条 trace。",
        f"打开 observationId={evidence.observationId}，重点检查 input.messages 里的 runtime carry-forward 文本。",
        (
            f"人工 review 时优先保留窗口 {_compact_window_list(keep_windows)}，"
            f"把窗口 {_compact_window_list(discard_windows)} 作为折叠候选。"
            if discard_windows
            else "人工 review 时可逐窗口检查，无需额外折叠。"
        ),
    ]
    recommendations = [
        "在 runtime 中持久化 restart 指纹、topNodes hash、workTreeNode、createdNodeCount 和 memoryTagWrites.appliedCount 到 Langfuse metadata。",
        "当连续窗口的检索指纹、restart 合同指纹和 work tree 指纹都不变时，考虑短路重启循环，直接沿用代表窗口。",
    ]
    if discard_windows:
        recommendations.append(
            f"当前 observation 的窗口 {_compact_window_list(discard_windows)} 仅表现为重复 carry-forward，可在分析报告和人工审查里默认折叠。"
        )
    if local_db_match is None:
        recommendations.append("为 live real-task run 保留对应 sandbox/evaluation.db，后续分析器才能把记忆树节点新增按窗口还原出来。")
    elif not local_db_match.windowExecutionByWindow:
        recommendations.append("保留 runtime/window-executions 工件，后续窗口级分析可以直接读取每窗结构化状态而不是只靠文本重建。")

    return {
        "observationId": evidence.observationId,
        "model": evidence.model,
        "profile": evidence.profile,
        "taskId": evidence.taskId,
        "invocationId": evidence.invocationId,
        "toolExecutionCount": tool_execution_count,
        "outputTokens": output_tokens,
        "memoryWriteTagCount": len(output_tags),
        "finalInvocationTokenDelta": final_token_delta,
        "dataSources": data_sources,
        "memoryEvidenceLevel": memory_evidence_level,
        "assessment": assessment,
        "keepWindows": keep_windows,
        "discardWindows": discard_windows,
        "windowAudits": window_audits,
        "redundancyGroups": redundancy_groups,
        "localDbMatch": local_db_match,
        "uiReviewPlan": ui_review_plan,
        "recommendations": recommendations,
    }
def _serialize_observation_evidence(evidence: ObservationEvidence) -> dict[str, Any]:
    return {
        "observationId": evidence.observationId,
        "model": evidence.model,
        "profile": evidence.profile,
        "invocationId": evidence.invocationId,
        "agentRunId": evidence.agentRunId,
        "taskId": evidence.taskId,
        "taskGoal": evidence.taskGoal,
        "taskObjective": evidence.taskObjective,
        "windows": [asdict(window) for window in evidence.windows],
        "outputText": evidence.outputText,
        "inputTools": evidence.inputTools,
        "metadata": evidence.metadata,
        "modelParameters": evidence.modelParameters,
        "usageDetails": evidence.usageDetails,
        "selfTalkFields": evidence.selfTalkFields,
        "assistantProcessUtterances": evidence.assistantProcessUtterances,
        "toolCallNames": evidence.toolCallNames,
        "localArtifacts": asdict(evidence.localArtifacts) if evidence.localArtifacts is not None else None,
    }
def _build_execution_audit_payload(
    *,
    trace_id: str,
    observations: list[ObservationEvidence],
    observation_audits: list[dict[str, Any]],
    requested_provider: str,
    requested_model: str,
    langfuse_base_url: str,
) -> dict[str, Any]:
    return {
        "traceId": trace_id,
        "analysisMode": "window-execution-audit",
        "langfuseBaseUrl": langfuse_base_url,
        "requestedProvider": requested_provider,
        "requestedModel": requested_model,
        "observationCount": len(observations),
        "observations": [_serialize_observation_evidence(evidence) for evidence in observations],
        "observationAudits": observation_audits,
    }
def _build_execution_audit_markdown(
    *,
    trace_id: str,
    observations: list[ObservationEvidence],
    observation_audits: list[dict[str, Any]],
    requested_provider: str,
    requested_model: str,
    langfuse_base_url: str,
) -> str:
    discard_observation_count = sum(1 for audit in observation_audits if audit["discardWindows"])
    total_discard_windows = sum(len(audit["discardWindows"]) for audit in observation_audits)
    lines = [
        "# Langfuse LLM Text Review",
        "",
        f"- traceId: {trace_id}",
        f"- observationCount: {len(observations)}",
        "- analysisMode: llm-text-review",
        f"- langfuseBaseUrl: {langfuse_base_url}",
        f"- compatibilityArgs: provider={requested_provider}, model={requested_model}",
        f"- observationsWithRepeatedWindows: {discard_observation_count}",
        f"- totalRepeatedWindows: {total_discard_windows}",
        "",
        "## Langfuse UI",
        "",
        "- 打开上面的 base URL，进入 Observability -> Traces。",
        f"- 用 traceId `{trace_id}` 过滤 trace。",
        "- 打开 trace 后，在 timeline 里逐个点 observation，重点看 input / output / metadata。",
        "- 如果只关心文字，把注意力放在 input.messages 最后一个 user runtime message，以及 output 文本。",
        "",
    ]

    for evidence, audit in zip(observations, observation_audits, strict=True):
        windows_by_number = {window.window: window for window in evidence.windows}
        initial_messages = _message_excerpt_payload(evidence.initialMessages)
        final_output_excerpt = normalize_excerpt(evidence.outputText, 400) or "-"
        lines.extend(
            [
                f"## {evidence.model} / {evidence.profile}",
                "",
                f"- observationId: {audit['observationId']}",
                f"- taskId: {audit['taskId'] or '-'}",
                f"- invocationId: {audit['invocationId'] or '-'}",
                f"- detectedWindows: {len(audit['windowAudits'])}",
                f"- keepWindows: {_compact_window_list(audit['keepWindows'])}",
                f"- repeatedWindows: {_compact_window_list(audit['discardWindows'])}",
                "",
                "### Initial Prompt Excerpts",
                "",
            ]
        )
        for message in initial_messages:
            lines.append(f"- {message['role']}#{message['index']}: {message['excerpt']}")

        lines.extend(
            [
                "",
                "### Window Text Ledger",
                "",
                "| window | snapshot | keep | text relation | runtime text excerpt |",
                "|---:|---|---|---|---|",
            ]
        )
        for window_audit in audit["windowAudits"]:
            window_number = int(window_audit["window"])
            window = windows_by_number.get(window_number)
            anchor_window = windows_by_number.get(int(window_audit["anchorWindow"]))
            if window is None:
                continue
            if anchor_window is None or anchor_window.window == window.window:
                text_relation = "代表窗口"
            else:
                text_relation = _text_delta_summary(window.rawContext, anchor_window.rawContext)
            lines.append(
                f"| {window_audit['window']} | {window_audit['snapshot']} | {'keep' if window_audit['keep'] else 'fold'} | {text_relation} | {_window_text_excerpt(window)} |"
            )

        lines.extend(["", "### Repeated Window Clusters", ""])
        if audit["redundancyGroups"]:
            for group in audit["redundancyGroups"]:
                anchor_window = windows_by_number.get(int(group["anchorWindow"]))
                anchor_excerpt = _window_text_excerpt(anchor_window) if anchor_window is not None else "-"
                lines.append(
                    f"- {group['label']}: 代表窗口 {group['anchorWindow']}，重复窗口 {_compact_window_list(group['repeatedWindows'])}，共享文本摘录：{anchor_excerpt}"
                )
        else:
            lines.append("- 未发现重复窗口簇。")

        lines.extend(["", "### Final Output Excerpt", "", final_output_excerpt, ""])

        lines.extend(["### Langfuse Review Focus", ""])
        for item in audit["uiReviewPlan"]:
            lines.append(f"- {item}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"
def analyze_trace(
    *,
    trace_id: str,
    requested_provider: str,
    requested_model: str,
    workspace_root: Path | None = None,
) -> str:
    load_workspace_dotenv(workspace_root)
    resolved_workspace = resolve_workspace_root(workspace_root)
    base_url = os.environ["LANGFUSE_BASE_URL"].rstrip("/")
    public_key = os.environ["LANGFUSE_PUBLIC_KEY"]
    secret_key = os.environ["LANGFUSE_SECRET_KEY"]
    auth_value = base64.b64encode(f"{public_key}:{secret_key}".encode("utf-8")).decode("ascii")
    auth_header = f"Basic {auth_value}"

    payload = _fetch_observations(trace_id, base_url=base_url, auth_header=auth_header)
    observation_payloads = payload.get("data") if isinstance(payload.get("data"), list) else []
    observation_payloads.sort(key=lambda item: (str(item.get("model") or ""), str(item.get("id") or "")))
    evidence_list = [_build_observation_evidence(item, workspace_root=resolved_workspace) for item in observation_payloads]

    observation_audits = [
        _build_observation_execution_audit(trace_id=trace_id, evidence=evidence, workspace_root=resolved_workspace)
        for evidence in evidence_list
    ]

    return _build_execution_audit_markdown(
        trace_id=trace_id,
        observations=evidence_list,
        observation_audits=observation_audits,
        requested_provider=requested_provider,
        requested_model=requested_model,
        langfuse_base_url=base_url,
    )
def analyze_trace_payload(
    *,
    trace_id: str,
    requested_provider: str,
    requested_model: str,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    load_workspace_dotenv(workspace_root)
    resolved_workspace = resolve_workspace_root(workspace_root)
    base_url = os.environ["LANGFUSE_BASE_URL"].rstrip("/")
    public_key = os.environ["LANGFUSE_PUBLIC_KEY"]
    secret_key = os.environ["LANGFUSE_SECRET_KEY"]
    auth_value = base64.b64encode(f"{public_key}:{secret_key}".encode("utf-8")).decode("ascii")
    auth_header = f"Basic {auth_value}"

    payload = _fetch_observations(trace_id, base_url=base_url, auth_header=auth_header)
    observation_payloads = payload.get("data") if isinstance(payload.get("data"), list) else []
    observation_payloads.sort(key=lambda item: (str(item.get("model") or ""), str(item.get("id") or "")))
    evidence_list = [_build_observation_evidence(item, workspace_root=resolved_workspace) for item in observation_payloads]
    observation_audits = [
        _build_observation_execution_audit(trace_id=trace_id, evidence=evidence, workspace_root=resolved_workspace)
        for evidence in evidence_list
    ]
    return _build_execution_audit_payload(
        trace_id=trace_id,
        observations=evidence_list,
        observation_audits=observation_audits,
        requested_provider=requested_provider,
        requested_model=requested_model,
        langfuse_base_url=base_url,
    )
def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze a Langfuse real-task trace into a deterministic execution audit report.")
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--analysis-provider", default="longcat")
    parser.add_argument("--analysis-model", default="LongCat-2.0-Preview")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".yggdrasil") / "state" / "analysis" / "langfuse-real-task-execution-audit.md",
    )
    parser.add_argument("--json-output", type=Path, default=None)
    args = parser.parse_args()

    report = analyze_trace(
        trace_id=args.trace_id,
        requested_provider=args.analysis_provider,
        requested_model=args.analysis_model,
    )
    payload = analyze_trace_payload(
        trace_id=args.trace_id,
        requested_provider=args.analysis_provider,
        requested_model=args.analysis_model,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(report)
if __name__ == "__main__":
    main()
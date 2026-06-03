from .._common import *  # noqa: F403,F401
from ..bootstrap import *  # noqa: F403,F401
from ..scorer import *  # noqa: F403,F401

def _run_subagent_pr_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    from fastapi.testclient import TestClient
    from yggdrasil_core_api.app import app
    from yggdrasil_sdk.collaboration_runtime import launch_subagent_task
    from yggdrasil_worker.registry import run_worker_once

    with tempfile.TemporaryDirectory(prefix="yggdrasil-eval-git-") as temp_dir:
        repo_path = Path(temp_dir) / "collaboration-repo"
        repo_path.mkdir(parents=True, exist_ok=True)
        _run_git(repo_path, "init", "-b", "main")
        _run_git(repo_path, "config", "user.name", "Evaluation User")
        _run_git(repo_path, "config", "user.email", "evaluation@example.com")
        (repo_path / "README.md").write_text("# Evaluation Repo\n", encoding="utf-8")
        _run_git(repo_path, "add", "README.md")
        _run_git(repo_path, "commit", "-m", "init")
        os.environ["YGGDRASIL_GIT_REPO_PATH"] = str(repo_path)

        parent_task = _seed_parent_task()
        launched = launch_subagent_task(
            str(parent_task["id"]),
            {
                "title": "Evaluation child path",
                "goal": "Produce a child proposal and merge it back.",
                "createdBy": {"type": "agent", "id": "evaluation"},
            },
        )
        processed = run_worker_once()
        if processed.get("result", {}).get("status") != "completed":
            raise RuntimeError(f"subagent execution failed: {json.dumps(processed, ensure_ascii=False)}")

        client = TestClient(app)
        pr_id = str(processed["result"]["pullRequest"]["id"])
        reviewed = client.post(
            f"/collaboration/pull-requests/{pr_id}/review",
            json={
                "decision": "approved",
                "mergeImmediately": True,
                "reviewedBy": {"type": "agent", "id": "evaluation"},
            },
        )
        if reviewed.status_code != 200:
            raise RuntimeError(f"subagent review failed: {reviewed.text}")
        review_body = reviewed.json()
        return {
            "branchName": launched["branch"]["name"],
            "pullRequestId": pr_id,
            "pullRequestStatus": review_body["pullRequest"]["status"],
            "mergeCommitRef": review_body["git"].get("mergeCommitRef"),
        }

def _run_m9_shared_multimodal_reasoning_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    from yggdrasil_memory_organizer.plugin import MemoryOrganizerModule
    from yggdrasil_multimodal_memory.plugin import MultimodalMemoryModule
    from yggdrasil_relation_discovery.plugin import RelationDiscoveryModule
    from yggdrasil_shared_memory.plugin import describe_mounts_tool, plugin as shared_memory_plugin
    from yggdrasil_training_lab.plugin import TrainingLabModule

    case_payload = dict(case or {})
    question = str(
        case_payload.get("query")
        or "为什么主任务必须挂载共享空间中的多模态恢复证据，并把这些证据通过关联发现沉淀为 dataset version 与 model artifact，而不是只保留一条摘要？"
    )
    expected_keywords = [str(keyword) for keyword in case_payload.get("expectedKeywords") or []]
    transcript = _read_text_fixture(str(case_payload.get("fixture") or "m9_multimodal_shared_evidence.txt"))
    shared_setup = _seed_shared_space_mount()
    _seed_training_prompt_assets("m9-shared-multimodal")

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        node_repository = NodeRepository(session)
        shared_related_node = _create_context_node(
            node_repository,
            branch_id=shared_setup["branchId"],
            space_id=shared_setup["spaceId"],
            title="Distillation Readiness Note",
            content="关联发现表明恢复步骤、共享空间证据、多模态摘要与 dataset version / model artifact 之间必须保留图谱连接。",
        )
        low_value_node = _create_context_node(
            node_repository,
            branch_id=DEFAULT_BRANCH_ID,
            space_id="space_default",
            title="Temporary Scratchpad",
            content="临时草稿，后续应由软遗忘治理压缩。",
        )
        node_repository.append_version(
            low_value_node["id"],
            {
                "importance": 0.05,
                "stability": 0.1,
                "accessScore": 0.0,
                "feedforwardScore": 0.0,
                "changeReason": "m9-acceptance-low-value",
                "updatedBy": {"type": "agent", "id": "evaluation"},
            },
        )

    ingest_result = MultimodalMemoryModule().ingest_asset(
        {
            "mediaType": "audio",
            "sourceText": transcript,
            "spaceId": shared_setup["spaceId"],
            "branchId": shared_setup["branchId"],
            "ownerNodeId": shared_setup["anchorNodeId"],
            "executionContext": {
                "projectId": DEFAULT_PROJECT_ID,
                "spaceId": shared_setup["spaceId"],
                "branchId": shared_setup["branchId"],
                "actor": {"type": "module", "id": "evaluation"},
            },
        }
    )
    describe_result = describe_mounts_tool(
        {
            "executionContext": {
                "projectId": DEFAULT_PROJECT_ID,
                "spaceId": "space_default",
                "branchId": DEFAULT_BRANCH_ID,
                "ownerProfileId": "identity_profile_default",
                "subject": shared_setup["subject"],
            }
        }
    )
    expanded = shared_memory_plugin.expand_retrieval(
        {
            "executionContext": {
                "projectId": DEFAULT_PROJECT_ID,
                "spaceId": "space_default",
                "branchId": DEFAULT_BRANCH_ID,
                "ownerProfileId": "identity_profile_default",
                "subject": shared_setup["subject"],
                "rootMount": {"spaceId": "space_default"},
            }
        }
    )
    scan_result = RelationDiscoveryModule().scan_branch_relations({"branchId": shared_setup["branchId"]})
    organizer_preview = MemoryOrganizerModule().apply_soft_forgetting(
        {
            "branchId": DEFAULT_BRANCH_ID,
            "targetCount": 1,
            "dryRun": True,
        }
    )
    organizer_result = MemoryOrganizerModule().apply_soft_forgetting(
        {
            "branchId": DEFAULT_BRANCH_ID,
            "targetCount": 1,
            "dryRun": False,
        }
    )
    training_lab = TrainingLabModule()
    dataset_result = training_lab.prepare_dataset(
        {
            "datasetName": "m9_acceptance_shared_reasoning",
            "branchId": shared_setup["branchId"],
            "maxRows": 12,
            "includeMemoryNodes": True,
        }
    )
    model_result = training_lab.stage_model_artifact(
        {
            "datasetVersionId": dataset_result["datasetVersion"]["id"],
            "baseModel": "gpt-5.4",
            "tuningMethod": "distillation",
            "minimumRows": 1,
        }
    )

    context_blocks = [
        (
            "共享空间挂载证据: 主任务已挂载共享空间，并通过 mounted branch 读取恢复材料；"
            f"accessible mounts={len(describe_result.get('accessibleMounts') or [])}。"
        ),
        (
            "多模态证据: "
            + str(ingest_result["summaryNode"].get("content") or "")
        ),
        (
            "关联与实验证据: "
            + str(scan_result.get("summary") or "")
            + f" dataset version={dataset_result['datasetVersion']['version']}"
            + f" model artifact={model_result['modelArtifact']['status']}"
        ),
        (
            "软遗忘治理: "
            + str(organizer_result.get("summary") or "")
        ),
    ]
    answer = _generate_strategy_answer(case_payload, question, "m9-shared-multimodal", context_blocks)
    answer_text = str(answer.get("outputText") or "")
    answer_coverage = _coverage_ratio(answer_text, expected_keywords)
    context_coverage = _coverage_ratio("\n\n".join(context_blocks), expected_keywords)
    combined_score = round(context_coverage * 0.7 + answer_coverage * 0.3, 4)

    if not describe_result.get("accessibleMounts"):
        raise RuntimeError("shared mount description did not expose any accessible mounts")
    if not expanded.get("nodes"):
        raise RuntimeError("mounted retrieval expansion did not return any nodes")
    if ingest_result.get("segmentCount", 0) < 1:
        raise RuntimeError("multimodal ingestion did not create any segments")
    if not scan_result.get("createdEdges"):
        raise RuntimeError("relation discovery did not materialize any latent edges")
    if organizer_preview.get("candidates", [{}])[0].get("nodeId") != low_value_node["id"]:
        raise RuntimeError("memory organizer did not target the expected low-value node")
    if dataset_result["datasetVersion"].get("rowCount", 0) < 1:
        raise RuntimeError("training lab did not create a dataset row")
    if model_result["modelArtifact"].get("status") != "validated":
        raise RuntimeError("training lab did not validate the staged model artifact")
    if combined_score < 0.75:
        raise RuntimeError(f"m9 shared reasoning answer coverage is too low: {combined_score}")

    return {
        "question": question,
        "expectedKeywords": expected_keywords,
        "answerPreview": normalize_excerpt(answer_text, 240),
        "answerCoverage": answer_coverage,
        "contextCoverage": context_coverage,
        "combinedScore": combined_score,
        "mountedSpaceCount": len(describe_result.get("accessibleMounts") or []),
        "expandedNodeCount": len(expanded.get("nodes") or []),
        "segmentCount": int(ingest_result.get("segmentCount") or 0),
        "createdEdgeCount": len(scan_result.get("createdEdges") or []),
        "datasetVersionId": dataset_result["datasetVersion"]["id"],
        "datasetRowCount": dataset_result["datasetVersion"]["rowCount"],
        "modelArtifactId": model_result["modelArtifact"]["id"],
        "modelArtifactStatus": model_result["modelArtifact"]["status"],
        "softForgotNodeId": organizer_result["adjustedNodes"][0]["nodeId"],
        "usedFeatures": [
            "shared-memory.describe-mounts",
            "shared-memory.expand-retrieval",
            "multimodal-memory.ingest-asset",
            "relation-discovery.scan-branch",
            "memory-organizer.soft-forgetting",
            "training-lab.prepare-dataset",
            "training-lab.stage-model-artifact",
        ],
        "liveScenario": {
            "question": question,
            "combinedScore": combined_score,
            "usedFeatures": 7,
        },
        "relatedNodeId": shared_related_node["id"],
    }

def _run_m9_pause_resume_memory_tree_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    from fastapi.testclient import TestClient
    import yggdrasil_model_providers
    from yggdrasil_agent_runtime.app import app as runtime_app
    from yggdrasil_worker.registry import run_worker_once

    case_payload = dict(case or {})
    question = str(
        case_payload.get("query")
        or "在挂载共享记忆树后，任务必须在 safe-stop 中保留哪些上下文，恢复后又如何继续完成最终写入？"
    )
    expected_keywords = [str(keyword) for keyword in case_payload.get("expectedKeywords") or []]
    shared_setup = _seed_shared_space_mount()

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        node_repository = NodeRepository(session)
        task_repository = TaskRepository(session)
        _create_context_node(
            node_repository,
            branch_id=shared_setup["branchId"],
            space_id=shared_setup["spaceId"],
            title="Mounted Recovery Branch",
            content="挂载记忆树中的恢复分支要求 safe-stop 保留 snapshot、protectedItems 与 resume token。",
        )
        task = task_repository.create_task(
            {
                "id": "eval_task_m9_pause_resume",
                "title": "M9 Pause Resume Acceptance",
                "goal": "Validate mounted-memory safe-stop and seamless resume.",
                "status": "draft",
                "currentObjective": question,
                "currentFocus": "m9-pause-resume-acceptance",
                "resumeMessage": "恢复后继续完成跨空间恢复总结。",
                "budgetState": {
                    "tokenBudgetTotal": 1400,
                    "costBudgetTotal": 5.0,
                },
            }
        )

    client = TestClient(runtime_app)
    original_invoke_model = yggdrasil_model_providers.invoke_model

    def _fake_invoke_model(**_kwargs):
        output_text = (
            "## 结果\n"
            "已保留 mounted memory tree、protectedItems、snapshot token，并在恢复后完成最终写入。\n\n"
            "## 证据\n"
            "- safe-stop snapshot 已创建并可恢复。\n"
            "- 恢复态继续使用 mounted shared space 与 followup actions。\n\n"
            "## 风险\n"
            "- 若恢复 token 失效，任务需要重新进入 safe-stop。\n\n"
            "## 已知问题\n"
            "- 当前验收使用固定响应，重点验证 pause/resume 链而非开放式写作质量。"
        )
        return {
            "mode": "live",
            "provider": "acceptance-provider",
            "model": "acceptance-model",
            "outputText": output_text,
            "finishReason": "stop",
            "usage": {
                "inputTokens": 120,
                "outputTokens": 90,
                "totalTokens": 210,
            },
            "costUsed": 0.0,
            "error": None,
            "toolCalls": [],
            "rawResponse": {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": output_text},
                    }
                ],
                "usage": {
                    "prompt_tokens": 120,
                    "completion_tokens": 90,
                    "total_tokens": 210,
                },
            },
            "requestPayload": {
                "model": "acceptance-model",
                "messages": [],
                "stream": True,
            },
            "firstTokenLatencyMs": 25.0,
        }

    yggdrasil_model_providers.invoke_model = _fake_invoke_model
    try:
        started = client.post(
            f"/runtime/tasks/{task.id}/start",
            json={
                "currentFocus": "执行挂载记忆树任务的 safe-stop 验收",
                "currentObjective": question,
                "takeoverPlanConfirmed": True,
                "planConfirmed": True,
                "confirmPlan": True,
                "takeoverAutoConfirm": True,
                "responseRequirements": "输出 Markdown，并在同一响应中包含这四段：## 结果、## 证据、## 风险、## 已知问题。",
                "currentContext": [
                    {
                        "id": "ctx_resume_keep",
                        "title": "Safe Stop Plan",
                        "content": "safe-stop 必须保留 protectedItems、snapshot token、mounted summary 与恢复后的 followup actions。",
                        "importance": 0.98,
                    },
                    {
                        "id": "ctx_resume_noise",
                        "title": "Noise",
                        "content": "低价值草稿应在恢复后继续压缩。",
                        "importance": 0.1,
                    },
                ],
                "protectedItems": [{"kind": "node", "id": "ctx_resume_keep"}],
                "activeCapabilities": ["shared-memory"],
            },
        )
        if started.status_code != 202:
            raise RuntimeError(f"m9 pause-resume start failed: {started.text}")
        paused = client.post(
            f"/runtime/tasks/{task.id}/pause-request",
            json={
                "reason": "m9-acceptance-safe-stop",
                "resumeMessage": "恢复后继续完成挂载记忆树总结。",
            },
        )
        if paused.status_code != 202:
            raise RuntimeError(f"m9 pause request failed: {paused.text}")
        first = run_worker_once("agent-runtime")
        if first.get("result", {}).get("status") != "paused":
            raise RuntimeError(f"m9 pause step failed: {json.dumps(first, ensure_ascii=False)}")
        snapshot = first["result"]["snapshot"]
        root_mount_preview = snapshot.get("rootMountPreview") or {}
        if not root_mount_preview.get("accessibleMounts"):
            raise RuntimeError("m9 pause snapshot did not include any mounted shared space")

        resumed = client.post(
            f"/runtime/tasks/{task.id}/resume",
            json={
                "resumeToken": snapshot["resumeToken"],
                "nextObjective": "恢复后完成跨空间恢复说明并写入最终执行记录。",
                "takeoverPlanConfirmed": True,
                "planConfirmed": True,
                "confirmPlan": True,
                "takeoverAutoConfirm": True,
                "responseRequirements": "输出 Markdown，并在同一响应中包含这四段：## 结果、## 证据、## 风险、## 已知问题。",
            },
        )
        if resumed.status_code != 202:
            raise RuntimeError(f"m9 resume request failed: {resumed.text}")
        resume_result = run_worker_once("agent-runtime")
        second = resume_result
        result_status = str((second.get("result") or {}).get("status") or "")
        task_status = None
        for _ in range(20):
            with runtime.session_scope() as session:
                current_task = TaskRepository(session).get_task(task.id)
                task_status = current_task.status if current_task is not None else None
            if task_status == "awaiting-approval":
                break
            if task_status == "completed":
                second = {
                    "status": "processed",
                    "result": {
                        "status": "completed",
                        "task": current_task.model_dump(by_alias=True, mode="json") if current_task is not None else None,
                    },
                }
                result_status = "completed"
                break
            if result_status != "continuing" and task_status not in {"queued", "running"}:
                break
            second = run_worker_once("agent-runtime")
            result_status = str((second.get("result") or {}).get("status") or "")
        if task_status == "awaiting-approval":
            approved = client.post(f"/runtime/tasks/{task.id}/approve-completion", json={})
            if approved.status_code != 200:
                raise RuntimeError(f"m9 approve completion failed: {approved.text}")
            second = {
                "status": "processed",
                "result": approved.json(),
            }
            result_payload = second["result"]
            result_status = str(result_payload.get("status") or "")
        else:
            result_payload = second.get("result") or {}
            result_status = str(result_payload.get("status") or "")
        if result_status != "completed":
            raise RuntimeError(f"m9 resume completion failed: {json.dumps(second, ensure_ascii=False)}")
    finally:
        yggdrasil_model_providers.invoke_model = original_invoke_model

    rehydration = (resume_result.get("result") or {}).get("rehydration") or (second["result"].get("rehydration") or {})
    restored_state = rehydration.get("restoredState") or {}
    context_blocks = [
        (
            "记忆树 safe-stop: "
            f"snapshot={snapshot['id']} safe-stop={snapshot['safeToPause']} protectedItems preserved before pause."
        ),
        (
            "挂载恢复上下文: "
            f"mountedSpaces={len(root_mount_preview.get('accessibleMounts') or [])} mountedRefs={len(root_mount_preview.get('mountedNodeRefs') or [])}."
        ),
        (
            "无感恢复: "
            + "; ".join(str(summary) for summary in rehydration.get("summaries") or [])
            + f" restoredContext={len(restored_state.get('currentContext') or [])} resume actions={len(rehydration.get('followupActions') or [])}"
        ),
    ]
    answer = _generate_strategy_answer(case_payload, question, "m9-pause-resume", context_blocks)
    answer_text = str(answer.get("outputText") or "")
    answer_coverage = _coverage_ratio(answer_text, expected_keywords)
    context_coverage = _coverage_ratio("\n\n".join(context_blocks), expected_keywords)
    combined_score = round(context_coverage * 0.7 + answer_coverage * 0.3, 4)

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        node_repository = NodeRepository(session)
        persisted_task = task_repository.get_task(task.id)
        execution_notes = [
            node
            for node in node_repository.list_nodes(branch_id=persisted_task.branch_id, limit=200)
            if node.node_type == "task" and node.parent_id == persisted_task.execution_root_node_id
        ]
        snapshots = task_repository.list_snapshots(task.id)
    if combined_score < 0.75:
        raise RuntimeError(f"m9 pause-resume answer coverage is too low: {combined_score}")
    if persisted_task is None or persisted_task.status != "completed":
        raise RuntimeError("m9 pause-resume task did not reach completed status")
    if len(execution_notes) < 2:
        raise RuntimeError("m9 pause-resume did not persist both pre-pause and post-resume execution notes")
    if not snapshots or snapshots[0].status != "consumed":
        raise RuntimeError("m9 pause-resume snapshot was not consumed on resume")

    return {
        "question": question,
        "expectedKeywords": expected_keywords,
        "answerPreview": normalize_excerpt(answer_text, 240),
        "answerCoverage": answer_coverage,
        "contextCoverage": context_coverage,
        "combinedScore": combined_score,
        "pauseStatus": first["result"]["status"],
        "resumeStatus": second["result"]["status"],
        "snapshotId": snapshot["id"],
        "mountedSpaceCount": len(root_mount_preview.get("accessibleMounts") or []),
        "mountedRefCount": len(root_mount_preview.get("mountedNodeRefs") or []),
        "rehydratedContextCount": len(restored_state.get("currentContext") or []),
        "rehydratedProtectedItemCount": len(restored_state.get("protectedItems") or []),
        "followupActionCount": len(rehydration.get("followupActions") or []),
        "executionNoteCount": len(execution_notes),
        "usedFeatures": [
            "shared-memory.mount-root",
            "pause-resume.prepare",
            "pause-resume.rehydrate",
            "runtime-kernel.pause-request",
            "runtime-kernel.resume",
        ],
        "liveScenario": {
            "question": question,
            "combinedScore": combined_score,
            "usedFeatures": 5,
        },
    }

def _run_m9_control_plane_resource_surface_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    from fastapi.testclient import TestClient
    from yggdrasil_core_api.app import app

    case_payload = dict(case or {})
    client = TestClient(app)
    dataset_name = str(case_payload.get("datasetName") or f"m9_control_plane_{utc_now().strftime('%H%M%S')}")
    ingested = client.post(
        "/assets/ingest",
        json={
            "mediaType": "document",
            "sourceText": str(
                case_payload.get("sourceText")
                or "共享空间恢复记录、多模态素材摘要和训练实验样本必须作为正式资源暴露到控制面，并能被后续评测与运维链路读取。"
            ),
            "spaceId": "space_default",
            "branchId": DEFAULT_BRANCH_ID,
        },
    )
    if ingested.status_code != 201:
        raise RuntimeError(f"asset ingestion failed: {ingested.text}")
    asset_payload = ingested.json()
    asset_id = str(asset_payload["asset"]["id"])

    prepared = client.post(
        "/training/dataset-versions/prepare",
        json={
            "datasetName": dataset_name,
            "maxRows": int(case_payload.get("maxRows") or 12),
            "includeMemoryNodes": True,
        },
    )
    if prepared.status_code != 201:
        raise RuntimeError(f"dataset preparation failed: {prepared.text}")
    dataset_payload = prepared.json()
    dataset_id = str(dataset_payload["datasetVersion"]["id"])

    staged = client.post(
        "/training/model-artifacts/stage",
        json={
            "datasetVersionId": dataset_id,
            "baseModel": str(case_payload.get("baseModel") or "gpt-5.4"),
            "tuningMethod": str(case_payload.get("tuningMethod") or "distillation"),
            "minimumRows": 1,
        },
    )
    if staged.status_code != 201:
        raise RuntimeError(f"model artifact staging failed: {staged.text}")
    artifact_payload = staged.json()
    artifact_id = str(artifact_payload["modelArtifact"]["id"])

    assets = client.get("/assets", params={"limit": 50})
    asset_detail = client.get(f"/assets/{asset_id}")
    datasets = client.get("/training/dataset-versions", params={"limit": 50})
    dataset_detail = client.get(f"/training/dataset-versions/{dataset_id}")
    artifacts = client.get("/training/model-artifacts", params={"limit": 50})
    artifact_detail = client.get(f"/training/model-artifacts/{artifact_id}")
    responses = [assets, asset_detail, datasets, dataset_detail, artifacts, artifact_detail]
    if any(response.status_code != 200 for response in responses):
        raise RuntimeError("control-plane resource surface returned non-200 responses")

    asset_count = len(assets.json().get("assets") or [])
    dataset_count = len(datasets.json().get("datasetVersions") or [])
    artifact_count = len(artifacts.json().get("modelArtifacts") or [])
    if asset_count < 1 or dataset_count < 1 or artifact_count < 1:
        raise RuntimeError("control-plane resource lists did not expose the seeded resources")
    if len(asset_detail.json().get("segments") or []) < 1:
        raise RuntimeError("asset detail did not expose segments")
    if len(dataset_detail.json().get("previewRows") or []) < 1:
        raise RuntimeError("dataset detail did not expose preview rows")
    if not artifact_detail.json().get("metrics"):
        raise RuntimeError("model artifact detail did not expose validation metrics")

    return {
        "assetId": asset_id,
        "segmentCount": len(asset_detail.json().get("segments") or []),
        "datasetVersionId": dataset_id,
        "datasetRowCount": int(dataset_payload["datasetVersion"].get("rowCount") or 0),
        "modelArtifactId": artifact_id,
        "modelArtifactStatus": artifact_payload["modelArtifact"].get("status"),
        "resourceCounts": {
            "assets": asset_count,
            "datasets": dataset_count,
            "artifacts": artifact_count,
        },
    }

def _run_m9_prompt_control_plane_case(case: dict[str, Any] | None = None) -> dict[str, Any]:
    from fastapi.testclient import TestClient
    from yggdrasil_core_api.app import app

    case_payload = dict(case or {})
    seeded = _seed_training_prompt_assets(str(case_payload.get("seedName") or "m9-prompt-control-plane"))
    client = TestClient(app)
    app_id = str(case_payload.get("appId") or "yggdrasil.app.software-factory")

    prompt_profiles = client.get("/prompting/prompt-profiles", params={"appId": app_id})
    seed_templates = client.get("/prompting/seed-templates", params={"appId": app_id})
    registered_tools = client.get(
        "/prompting/registered-tools",
        params={"activeCapabilities": str(case_payload.get("activeCapabilities") or "text-memory,shared-memory,training-lab")},
    )
    compile_artifacts = client.get("/prompting/compile-artifacts", params={"limit": 50})
    compile_artifact_detail = client.get(f"/prompting/compile-artifacts/{seeded['promptCompileArtifactId']}")
    preview = client.post(
        "/prompting/compile-preview",
        json={
            "appId": app_id,
            "runType": "main",
            "taskType": "coding",
            "activeCapabilities": ["text-memory", "shared-memory", "training-lab"],
            "task": {
                "title": "PromptOps Evaluation",
                "goal": "Expose the compiled prompt through the control plane.",
                "currentFocus": "prompt-control-plane",
                "currentObjective": "Verify prompt profile, seed template, tool registration, and compiled messages.",
                "resumeMessage": "继续查看 prompt 编译结果。",
            },
            "request": {
                "currentFocus": "prompt-control-plane",
                "currentObjective": "Verify prompt profile, seed template, tool registration, and compiled messages.",
                "responseRequirements": "输出必须包含风险与下一步。",
            },
        },
    )
    responses = [prompt_profiles, seed_templates, registered_tools, compile_artifacts, compile_artifact_detail, preview]
    if any(response.status_code not in {200, 201} for response in responses):
        raise RuntimeError("prompt control-plane surface returned non-200 responses")

    profile_list = prompt_profiles.json().get("promptProfiles") or []
    template_list = seed_templates.json().get("seedTemplates") or []
    tool_list = registered_tools.json().get("registeredTools") or []
    artifact_list = compile_artifacts.json().get("promptCompileArtifacts") or []
    preview_payload = preview.json().get("compiledPrompt") or {}
    if len(profile_list) < 2:
        raise RuntimeError("prompt control plane did not expose prompt profiles")
    if len(template_list) < 3:
        raise RuntimeError("prompt control plane did not expose seed templates")
    if not any(str(tool.get("name") or "") == "training_lab.prepare_dataset" for tool in tool_list):
        raise RuntimeError("prompt control plane did not expose the expected registered tool")
    if not any(str(artifact.get("id") or "") == seeded["promptCompileArtifactId"] for artifact in artifact_list):
        raise RuntimeError("prompt control plane did not expose the seeded compile artifact")
    if len((compile_artifact_detail.json().get("compiledMessages") or {}).get("messages") or []) < 1:
        raise RuntimeError("compile artifact detail did not expose compiled messages")
    if preview_payload.get("promptProfileId") != "yggdrasil.software-factory.main-agent":
        raise RuntimeError("prompt preview did not select the software-factory main prompt profile")
    if preview_payload.get("seedTemplateId") != "yggdrasil.seed.coding.inherit-project":
        raise RuntimeError("prompt preview did not select the expected coding seed template")

    return {
        "appId": app_id,
        "promptProfileCount": len(profile_list),
        "seedTemplateCount": len(template_list),
        "registeredToolCount": len(tool_list),
        "promptCompileArtifactId": seeded["promptCompileArtifactId"],
        "previewScenario": preview_payload.get("scenario"),
        "previewMessageCount": len(preview_payload.get("messages") or []),
    }

__all__ = [name for name in globals() if not name.startswith("__")]

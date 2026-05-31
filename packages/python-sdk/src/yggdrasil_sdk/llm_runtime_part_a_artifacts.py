def _response_file_payload(
    audit_level: str,
    *,
    task: Any,
    run: Any,
    invocation_id: str,
    prompt_artifact_id: str,
    final_result: dict[str, Any],
    usage_totals: dict[str, int],
    accumulated_cost: float,
    tool_executions: list[dict[str, Any]],
    round_summaries: list[dict[str, Any]],
    local_runtime_timings: dict[str, Any],
    first_token_latency_ms: float | None,
    context_length_observations: list[dict[str, Any]] | None = None,
    runtime_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "appId": getattr(task, "app_id", None),
        "invocationId": invocation_id,
        "taskId": task.id,
        "agentRunId": run.id,
        "promptCompileArtifactId": prompt_artifact_id,
        "mode": final_result.get("mode"),
        "provider": final_result.get("provider"),
        "model": final_result.get("model"),
        "finishReason": final_result.get("finishReason"),
        "assistantText": str(final_result.get("outputText") or ""),
        "usage": usage_totals,
        "costUsed": accumulated_cost,
        "error": final_result.get("error"),
        "auditLevel": audit_level,
        "localRuntimeTimings": dict(local_runtime_timings),
    }
    if first_token_latency_ms is not None:
        payload["firstTokenLatencyMs"] = first_token_latency_ms
    if context_length_observations:
        payload["contextLengthObservations"] = [dict(item) for item in context_length_observations if isinstance(item, dict)]
    if runtime_metrics:
        payload["runtimeMetrics"] = dict(runtime_metrics)
    if audit_level == "strict":
        payload["toolExecutions"] = tool_executions
        payload["rounds"] = round_summaries
        payload["rawResponse"] = final_result.get("rawResponse")
        return payload

    if audit_level == "default":
        payload["toolExecutionSummaries"] = _tool_execution_summaries(tool_executions)
        payload["rounds"] = round_summaries
        return payload

    payload["toolExecutionCount"] = len(tool_executions)
    payload["roundCount"] = len(round_summaries)
    return payload
def _persist_prompt_assets(
    session,
    *,
    task: Any,
    run: Any,
    invocation_id: str,
    compiled_prompt,
    workspace_root: Path,
    audit_level: str,
):
    repository = PromptAssetRepository(session)
    prompt_profile = get_prompt_profile_definition(
        compiled_prompt.prompt_profile_id,
        app_id=compiled_prompt.app_id,
    )
    seed_template = get_seed_template_definition(
        compiled_prompt.seed_template_id,
        app_id=compiled_prompt.app_id,
    )

    prompt_profile_body = (
        prompt_profile.model_dump(by_alias=True, mode="json")
        if prompt_profile is not None
        else {
            "id": compiled_prompt.prompt_profile_id,
            "version": compiled_prompt.prompt_profile_version,
        }
    )
    prompt_profile_hash = _json_hash(prompt_profile_body)
    prompt_profile_record = repository.upsert_prompt_profile_version(
        PromptProfileVersionRecord(
            id=new_id("promptprof", compiled_prompt.prompt_profile_id, compiled_prompt.prompt_profile_version, prompt_profile_hash, stable=True),
            promptProfileId=compiled_prompt.prompt_profile_id,
            name=str(prompt_profile_body.get("name") or compiled_prompt.prompt_profile_id),
            version=compiled_prompt.prompt_profile_version,
            runScope=str(prompt_profile_body.get("runScope") or "any"),
            body=prompt_profile_body,
            contentHash=prompt_profile_hash,
            createdAt=utc_now(),
        )
    )

    seed_template_record = None
    if seed_template is not None:
        seed_template_body = seed_template.model_dump(by_alias=True, mode="json")
        seed_template_hash = _json_hash(seed_template_body)
        seed_template_record = repository.upsert_seed_template_version(
            SeedTemplateVersionRecord(
                id=new_id("seedtpl", seed_template.id, seed_template.version, seed_template_hash, stable=True),
                seedTemplateId=seed_template.id,
                name=seed_template.name,
                version=seed_template.version,
                domain=seed_template.domain,
                scenario=seed_template.scenario,
                body=seed_template_body,
                contentHash=seed_template_hash,
                createdAt=utc_now(),
            )
        )

    compiled_messages_path = ensure_state_subdir("prompt/compiled", workspace_root) / f"{invocation_id}.json"
    write_json(compiled_messages_path, _compiled_prompt_file_payload(audit_level, compiled_prompt, invocation_id))
    compiled_messages_ref = _invocation_file_ref(compiled_messages_path, workspace_root)
    takeover_protocol_snapshot = (
        compiled_prompt.takeover_protocol.model_dump(by_alias=True, mode="json")
        if compiled_prompt.takeover_protocol is not None
        else None
    )
    work_tree_snapshot = (
        dict(takeover_protocol_snapshot.get("workTree") or {}) if isinstance(takeover_protocol_snapshot, dict) else None
    )
    artifact_hash = _json_hash(
        {
            "promptProfileId": compiled_prompt.prompt_profile_id,
            "seedTemplateId": compiled_prompt.seed_template_id,
            "runType": compiled_prompt.run_type,
            "taskType": compiled_prompt.task_type,
            "scenario": compiled_prompt.scenario,
            "registeredTools": compiled_prompt.registered_tools,
            "bootSections": compiled_prompt.boot_sections,
            "systemSections": compiled_prompt.system_sections,
            "userSections": compiled_prompt.user_sections,
            "takeoverProtocol": takeover_protocol_snapshot,
            "messages": compiled_prompt.messages,
        }
    )
    return repository.create_prompt_compile_artifact(
        {
            "appId": compiled_prompt.app_id,
            "projectId": task.project_id,
            "taskId": task.id,
            "agentRunId": run.id,
            "modelInvocationId": invocation_id,
            "promptProfileVersionId": prompt_profile_record.id,
            "seedTemplateVersionId": seed_template_record.id if seed_template_record is not None else None,
            "runType": compiled_prompt.run_type,
            "taskType": compiled_prompt.task_type,
            "scenario": compiled_prompt.scenario,
            "registeredTools": compiled_prompt.registered_tools,
            "bootSections": compiled_prompt.boot_sections,
            "systemSections": compiled_prompt.system_sections,
            "userSections": compiled_prompt.user_sections,
            "workTreeSnapshot": work_tree_snapshot,
            "takeoverProtocolSnapshot": takeover_protocol_snapshot,
            "compiledMessagesRef": compiled_messages_ref.model_dump(mode="json"),
            "contentHash": artifact_hash,
            "createdAt": utc_now(),
        }
    )
__all__ = [name for name in globals() if not name.startswith("__")]

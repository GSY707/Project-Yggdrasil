from ._imports import *  # noqa: F403,F401
from ._records import _external_ref


def _prompt_profile_version_record(model: PromptProfileVersionORM) -> PromptProfileVersionRecord:
    return PromptProfileVersionRecord(
        id=model.id,
        promptProfileId=model.prompt_profile_id,
        name=model.name,
        version=model.version,
        runScope=model.run_scope,
        body=dict(model.body or {}),
        contentHash=model.content_hash,
        createdAt=model.created_at,
    )


def _seed_template_version_record(model: SeedTemplateVersionORM) -> SeedTemplateVersionRecord:
    return SeedTemplateVersionRecord(
        id=model.id,
        seedTemplateId=model.seed_template_id,
        name=model.name,
        version=model.version,
        domain=model.domain,
        scenario=model.scenario,
        body=dict(model.body or {}),
        contentHash=model.content_hash,
        createdAt=model.created_at,
    )


def _prompt_compile_artifact_record(model: PromptCompileArtifactORM) -> PromptCompileArtifactRecord:
    return PromptCompileArtifactRecord(
        id=model.id,
        appId=model.app_id,
        projectId=model.project_id,
        taskId=model.task_id,
        agentRunId=model.agent_run_id,
        modelInvocationId=model.model_invocation_id,
        promptProfileVersionId=model.prompt_profile_version_id,
        seedTemplateVersionId=model.seed_template_version_id,
        runType=model.run_type,
        taskType=model.task_type,
        scenario=model.scenario,
        registeredTools=list(model.registered_tools or []),
        bootSections=dict(model.boot_sections or {}),
        systemSections=dict(model.system_sections or {}),
        userSections=dict(model.user_sections or {}),
        workTreeSnapshot=dict(model.work_tree_snapshot or {}) if model.work_tree_snapshot is not None else None,
        takeoverProtocolSnapshot=dict(model.takeover_protocol_snapshot or {}) if model.takeover_protocol_snapshot is not None else None,
        compiledMessagesRef=_external_ref(model.compiled_messages_ref),
        contentHash=model.content_hash,
        createdAt=model.created_at,
    )


__all__ = [name for name in globals() if not name.startswith("__")]

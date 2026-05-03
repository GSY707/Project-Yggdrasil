from ._base import *  # noqa: F403,F401

class PromptingServiceMixin:
    def list_prompt_profiles(
        self,
        app_id: str | None = None,
        active_capabilities: list[str] | None = None,
    ) -> dict[str, object]:
        resolved_app_id = app_id or active_application_id(self.workspace_root)
        return {
            "appId": resolved_app_id,
            "promptProfiles": [
                profile.model_dump(by_alias=True, mode="json")
                for profile in list_prompt_profile_definitions(resolved_app_id, active_capabilities)
            ]
        }

    def list_seed_templates(
        self,
        app_id: str | None = None,
        active_capabilities: list[str] | None = None,
    ) -> dict[str, object]:
        resolved_app_id = app_id or active_application_id(self.workspace_root)
        return {
            "appId": resolved_app_id,
            "seedTemplates": [
                template.model_dump(by_alias=True, mode="json")
                for template in list_seed_template_definitions(resolved_app_id, active_capabilities)
            ]
        }

    def list_registered_prompt_tools(
        self,
        active_capabilities: list[str] | None = None,
        app_id: str | None = None,
    ) -> dict[str, object]:
        resolved_app_id = app_id or active_application_id(self.workspace_root)
        resolved_capabilities = active_capabilities or resolve_application_active_capabilities(
            app_id=resolved_app_id,
            workspace_root=self.workspace_root,
        )
        return {
            "appId": resolved_app_id,
            "activeCapabilities": list(resolved_capabilities or []),
            "registeredTools": list_registered_agent_tools(resolved_capabilities),
        }

    def list_prompt_compile_artifacts(
        self,
        *,
        project_id: str | None = None,
        task_id: str | None = None,
        app_id: str | None = None,
        limit: int = 100,
    ) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            artifacts = PromptAssetRepository(session).list_prompt_compile_artifacts(
                project_id=project_id,
                task_id=task_id,
                app_id=app_id,
                limit=limit,
            )
        return {
            "promptCompileArtifacts": [artifact.model_dump(by_alias=True, mode="json") for artifact in artifacts]
        }

    def get_prompt_compile_artifact(self, artifact_id: str) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            prompt_repository = PromptAssetRepository(session)
            runtime_repository = RuntimeRepository(session)
            artifact = prompt_repository.get_prompt_compile_artifact(artifact_id)
            if artifact is None:
                raise KeyError(artifact_id)
            linked_invocation = next(
                (
                    invocation
                    for invocation in runtime_repository.list_model_invocations(app_id=artifact.app_id, limit=200)
                    if invocation.id == artifact.model_invocation_id or invocation.prompt_compile_artifact_id == artifact.id
                ),
                None,
            )
        return {
            "promptCompileArtifact": artifact.model_dump(by_alias=True, mode="json"),
            "compiledMessages": self._load_ref_payload(artifact.compiled_messages_ref.locator if artifact.compiled_messages_ref else None),
            "modelInvocation": linked_invocation.model_dump(by_alias=True, mode="json") if linked_invocation is not None else None,
            "requestPayload": self._load_ref_payload(linked_invocation.request_ref.locator if linked_invocation and linked_invocation.request_ref else None),
            "responsePayload": self._load_ref_payload(linked_invocation.response_ref.locator if linked_invocation and linked_invocation.response_ref else None),
        }

    def compile_prompt_preview(self, payload: dict[str, Any]) -> dict[str, object]:
        task_payload = payload.get("task") if isinstance(payload.get("task"), dict) else {}
        request_payload = payload.get("request") if isinstance(payload.get("request"), dict) else {}
        root_mount_payload = payload.get("rootMount") if isinstance(payload.get("rootMount"), dict) else {}
        app_id = str(payload.get("appId") or request_payload.get("appId") or active_application_id(self.workspace_root))
        try:
            effective_config = load_effective_application_config(app_id, self.workspace_root)
        except KeyError as exc:
            raise ValueError(f"Unknown application: {app_id}") from exc
        preview_defaults = effective_config.get("promptPreviewDefaults") if isinstance(effective_config.get("promptPreviewDefaults"), dict) else {}
        run_type = str(payload.get("runType") or effective_config.get("defaultRunType") or "main")
        task_type = str(payload.get("taskType") or effective_config.get("defaultTaskType") or "generic")
        active_capabilities = [
            str(item)
            for item in (
                payload.get("activeCapabilities")
                or root_mount_payload.get("activeCapabilities")
                or effective_config.get("defaultCapabilities")
                or []
            )
            if str(item).strip()
        ]
        request_payload = {**request_payload, "appId": app_id}
        if not request_payload.get("responseRequirements") and preview_defaults.get("responseRequirements"):
            request_payload["responseRequirements"] = str(preview_defaults["responseRequirements"])
        task = SimpleNamespace(
            title=str(task_payload.get("title") or "Prompt Control Preview"),
            goal=str(task_payload.get("goal") or "Preview the compiled runtime prompt."),
            current_focus=str(task_payload.get("currentFocus") or request_payload.get("currentFocus") or "prompt-ops"),
            current_objective=str(task_payload.get("currentObjective") or request_payload.get("currentObjective") or task_payload.get("goal") or "preview compile"),
            resume_message=str(task_payload.get("resumeMessage") or request_payload.get("resumeMessage") or ""),
            app_id=app_id,
        )
        root_mount = {
            "systemIntro": str(root_mount_payload.get("systemIntro") or "Prompt compile preview"),
            "rootSummary": str(root_mount_payload.get("rootSummary") or "Use the same prompt compiler that the runtime persists into prompt artifacts."),
            "taskObjective": str(root_mount_payload.get("taskObjective") or request_payload.get("currentObjective") or task.goal),
            "resumeMessage": str(root_mount_payload.get("resumeMessage") or task.resume_message),
            "mountedNodeRefs": list(root_mount_payload.get("mountedNodeRefs") or []),
            "accessibleMounts": list(root_mount_payload.get("accessibleMounts") or []),
            "activeCapabilities": active_capabilities,
        }
        current_context = [
            dict(item)
            for item in payload.get("currentContext") or []
            if isinstance(item, dict)
        ]
        compiled = compile_runtime_prompt(
            task=task,
            run_type=run_type,
            task_type=task_type,
            root_mount=root_mount,
            current_context=current_context,
            request=request_payload,
            resume_path=str(payload.get("resumePath")) if payload.get("resumePath") is not None else None,
        )
        return {
            "appId": app_id,
            "compiledPrompt": compiled.model_dump(by_alias=True, mode="json"),
            "registeredTools": compiled.registered_tools,
        }



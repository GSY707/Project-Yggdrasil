from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from yggdrasil_sdk.contracts import ToolDescriptor
from yggdrasil_sdk.hooks import HookNames
from yggdrasil_sdk.module import BaseModulePlugin, HookRegistration
from yggdrasil_sdk.persistence import get_persistence_runtime
from yggdrasil_sdk.persistence.constants import DEFAULT_BRANCH_ID, DEFAULT_PROJECT_ID
from yggdrasil_sdk.persistence.repositories import NodeRepository, PromptAssetRepository, RuntimeRepository, TrainingRepository, WorkspaceBootstrapRepository
from yggdrasil_sdk.support import ensure_state_subdir, normalize_excerpt, relative_workspace_path, resolve_workspace_root, utc_now, write_json


def _read_json_ref(locator: str | None) -> Any:
    if not locator:
        return None
    path = resolve_workspace_root() / locator
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


class TrainingLabModule(BaseModulePlugin):
    module_id = "training-lab"

    def manifest_path(self) -> Path:
        return Path(__file__).resolve().parents[2] / "yggdrasil.module.yaml"

    def register_hooks(self) -> tuple[HookRegistration, ...]:
        return (
            HookRegistration(name=HookNames.MODULE_ENABLE_PREFLIGHT, handler=self.enable_preflight),
            HookRegistration(name=HookNames.MODULE_HEALTH_REPORT, handler=self.report_health),
            HookRegistration(name=HookNames.AGENT_TOOLS_REGISTER, handler=self.register_tools_hook),
        )

    def register_tools(self) -> tuple[dict[str, object], ...]:
        tools = (
            ToolDescriptor(
                name="training_lab.prepare_dataset",
                moduleId=self.module_id,
                version="0.1.0",
                displayName="Prepare Dataset Version",
                description="Build a formal dataset version from prompt compile artifacts, model invocations, and optionally memory nodes.",
                schemaRef="docs/specs/asset-packaging-evaluation-data-spec-v0.1.md",
                executionMode="sync",
                timeoutMs=6000,
                permissionRequired=["evaluation.read", "model.write"],
                inputSchema={
                    "type": "object",
                    "properties": {
                        "datasetName": {"type": "string"},
                        "branchId": {"type": "string"},
                        "maxRows": {"type": "integer", "minimum": 1, "maximum": 200},
                        "includeMemoryNodes": {"type": "boolean"},
                    },
                    "required": ["datasetName"],
                    "additionalProperties": False,
                },
                implementationRef="yggdrasil_training_lab.plugin:prepare_dataset_tool",
            ),
            ToolDescriptor(
                name="training_lab.stage_model_artifact",
                moduleId=self.module_id,
                version="0.1.0",
                displayName="Stage Model Artifact",
                description="Create a formal model artifact manifest and validation gate from a dataset version.",
                schemaRef="docs/specs/asset-packaging-evaluation-data-spec-v0.1.md",
                executionMode="sync",
                timeoutMs=4000,
                permissionRequired=["model.write"],
                inputSchema={
                    "type": "object",
                    "properties": {
                        "datasetVersionId": {"type": "string"},
                        "baseModel": {"type": "string"},
                        "tuningMethod": {"type": "string", "enum": ["sft", "dpo", "distillation", "adapter"]},
                        "minimumRows": {"type": "integer", "minimum": 1},
                    },
                    "required": ["datasetVersionId", "baseModel", "tuningMethod"],
                    "additionalProperties": False,
                },
                implementationRef="yggdrasil_training_lab.plugin:stage_model_artifact_tool",
            ),
        )
        return tuple(tool.model_dump(by_alias=True) for tool in tools)

    def register_tools_hook(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "tools": list(self.register_tools()),
            "toolCount": len(self.register_tools()),
            "moduleId": self.module_id,
        }

    def enable_preflight(self, payload: dict[str, object]) -> dict[str, object]:
        return {"status": "ok", "summary": "Training Lab preflight passed."}

    def report_health(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "status": "healthy",
            "summary": "Training Lab is ready to create dataset versions and stage model artifacts.",
        }

    def prepare_dataset(self, payload: dict[str, object]) -> dict[str, object]:
        execution_context = payload.get("executionContext") if isinstance(payload.get("executionContext"), dict) else {}
        project_id = str(execution_context.get("projectId") or payload.get("projectId") or DEFAULT_PROJECT_ID)
        branch_id = str(payload.get("branchId") or execution_context.get("branchId") or DEFAULT_BRANCH_ID)
        dataset_name = str(payload.get("datasetName") or "dataset")
        max_rows = int(payload.get("maxRows") or 24)
        include_memory_nodes = bool(payload.get("includeMemoryNodes", True))

        runtime = get_persistence_runtime()
        rows: list[dict[str, Any]] = []
        with runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            prompt_repository = PromptAssetRepository(session)
            runtime_repository = RuntimeRepository(session)
            node_repository = NodeRepository(session)
            training_repository = TrainingRepository(session)

            artifacts = prompt_repository.list_prompt_compile_artifacts(project_id=project_id, limit=max_rows * 2)
            invocations = runtime_repository.list_model_invocations(limit=max_rows * 2)
            invocation_by_artifact_id = {
                str(invocation.prompt_compile_artifact_id): invocation
                for invocation in invocations
                if invocation.prompt_compile_artifact_id is not None
            }
            for artifact in artifacts:
                compiled_payload = _read_json_ref(artifact.compiled_messages_ref.locator)
                invocation = invocation_by_artifact_id.get(artifact.id)
                response_payload = _read_json_ref(invocation.response_ref.locator) if invocation and invocation.response_ref else None
                rows.append(
                    {
                        "kind": "prompt-artifact",
                        "artifactId": artifact.id,
                        "taskId": artifact.task_id,
                        "runType": artifact.run_type,
                        "taskType": artifact.task_type,
                        "messages": (compiled_payload or {}).get("messages") if isinstance(compiled_payload, dict) else [],
                        "assistantText": normalize_excerpt(str(((response_payload or {}).get("rawResponse") or {})), 320),
                        "registeredTools": artifact.registered_tools,
                    }
                )
                if len(rows) >= max_rows:
                    break

            if include_memory_nodes and len(rows) < max_rows:
                for node in node_repository.list_nodes(branch_id=branch_id, limit=max_rows * 2):
                    if node.node_type == "root":
                        continue
                    rows.append(
                        {
                            "kind": "memory-node",
                            "nodeId": node.id,
                            "title": node.title,
                            "content": normalize_excerpt(node.content, 280),
                            "rootBranch": node.root_branch,
                        }
                    )
                    if len(rows) >= max_rows:
                        break

            version = utc_now().strftime("v%Y%m%d%H%M%S")
            workspace_root = resolve_workspace_root()
            dataset_dir = ensure_state_subdir(f"datasets/{dataset_name}", workspace_root)
            dataset_path = dataset_dir / f"{version}.jsonl"
            dataset_path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")
            dataset_record = training_repository.create_dataset_version(
                {
                    "datasetName": dataset_name,
                    "version": version,
                    "sourceFilter": {
                        "projectId": project_id,
                        "branchId": branch_id,
                        "includeMemoryNodes": include_memory_nodes,
                    },
                    "storageKey": relative_workspace_path(dataset_path, workspace_root),
                    "rowCount": len(rows),
                }
            )
        return {
            "datasetVersion": dataset_record.model_dump(by_alias=True, mode="json"),
            "previewRows": rows[:3],
            "summary": f"Prepared dataset {dataset_name}@{version} with {len(rows)} rows.",
        }

    def stage_model_artifact(self, payload: dict[str, object]) -> dict[str, object]:
        minimum_rows = int(payload.get("minimumRows") or 8)
        runtime = get_persistence_runtime()
        with runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            training_repository = TrainingRepository(session)
            dataset = training_repository.get_dataset_version(str(payload.get("datasetVersionId")))
            if dataset is None:
                raise KeyError(str(payload.get("datasetVersionId")))
            workspace_root = resolve_workspace_root()
            artifact_dir = ensure_state_subdir("models/artifacts", workspace_root)
            artifact_id = str(payload.get("id") or f"modelart_{dataset.id}_{payload.get('tuningMethod')}")
            status = "validated" if dataset.row_count >= minimum_rows else "staged"
            metrics_path = artifact_dir / f"{artifact_id}.json"
            metrics_payload = {
                "artifactId": artifact_id,
                "datasetVersionId": dataset.id,
                "rowCount": dataset.row_count,
                "minimumRows": minimum_rows,
                "readyForValidation": dataset.row_count >= minimum_rows,
                "generatedAt": utc_now().isoformat(),
            }
            write_json(metrics_path, metrics_payload)
            artifact_record = training_repository.create_model_artifact(
                {
                    "id": artifact_id,
                    "baseModel": str(payload.get("baseModel") or "unknown-base-model"),
                    "tuningMethod": str(payload.get("tuningMethod") or "distillation"),
                    "datasetVersionId": dataset.id,
                    "metricsRef": {"type": "file", "locator": relative_workspace_path(metrics_path, workspace_root)},
                    "storageKey": relative_workspace_path(metrics_path, workspace_root),
                    "status": status,
                }
            )
        return {
            "modelArtifact": artifact_record.model_dump(by_alias=True, mode="json"),
            "validationGate": metrics_payload,
            "summary": f"Staged model artifact {artifact_record.id} with status {artifact_record.status}.",
        }


plugin = TrainingLabModule()


def prepare_dataset_tool(payload: dict[str, object]) -> dict[str, object]:
    return plugin.prepare_dataset(payload)


def stage_model_artifact_tool(payload: dict[str, object]) -> dict[str, object]:
    return plugin.stage_model_artifact(payload)
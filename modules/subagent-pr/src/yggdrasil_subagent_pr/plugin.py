from __future__ import annotations

from pathlib import Path
from typing import Any

from yggdrasil_sdk.collaboration_runtime import create_pull_request, review_pull_request
from yggdrasil_sdk.contracts import (
    EventEnvelope,
    EventHandlingResult,
    ModuleEventEmission,
    ToolDescriptor,
    WorkerActivityDescriptor,
)
from yggdrasil_sdk.hooks import HookNames
from yggdrasil_sdk.module import BaseModulePlugin, HookRegistration
from yggdrasil_sdk.support import utc_now


def _normalize_actor(payload: dict[str, Any], key: str, default_id: str) -> dict[str, str]:
    actor = payload.get(key)
    if isinstance(actor, dict) and actor.get("id"):
        return {"type": str(actor.get("type", "agent")), "id": str(actor["id"])}
    return {"type": "agent", "id": default_id}


class SubagentPrModule(BaseModulePlugin):
    module_id = "subagent-pr"

    def manifest_path(self) -> Path:
        return Path(__file__).resolve().parents[2] / "yggdrasil.module.yaml"

    def register_hooks(self) -> tuple[HookRegistration, ...]:
        return (
            HookRegistration(name=HookNames.MODULE_ENABLE_PREFLIGHT, handler=self.enable_preflight),
            HookRegistration(name=HookNames.MODULE_HEALTH_REPORT, handler=self.report_health),
            HookRegistration(name=HookNames.AGENT_TOOLS_REGISTER, handler=self.register_tools_hook),
            HookRegistration(name=HookNames.WORKER_ACTIVITIES_REGISTER, handler=self.register_activities),
        )

    def enable_preflight(self, payload: dict[str, object]) -> dict[str, object]:
        install = payload.get("install") if isinstance(payload.get("install"), dict) else {}
        if str(install.get("runtimeMode") or "") != "in-process":
            return {"status": "error", "summary": "Sub-Agent PR requires in-process runtime mode."}
        return {"status": "ok", "summary": "Sub-Agent PR preflight passed."}

    def report_health(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "status": "healthy",
            "summary": "Sub-Agent PR is ready to register tools and react to task events.",
        }

    def register_tools(self) -> tuple[dict[str, object], ...]:
        tools = (
            ToolDescriptor(
                name="subagent_pr.create",
                moduleId=self.module_id,
                version="0.1.0",
                displayName="Create Sub-Agent Pull Request",
                schemaRef="docs/specs/collaboration-and-governance-data-spec-v0.1.md",
                executionMode="sync",
                timeoutMs=5000,
                idempotent=False,
                permissionRequired=["pr.write", "branch.write"],
            ),
            ToolDescriptor(
                name="subagent_pr.review",
                moduleId=self.module_id,
                version="0.1.0",
                displayName="Review Sub-Agent Pull Request",
                schemaRef="docs/specs/collaboration-and-governance-data-spec-v0.1.md",
                executionMode="sync",
                timeoutMs=5000,
                idempotent=False,
                permissionRequired=["pr.write"],
            ),
        )
        return tuple(tool.model_dump(by_alias=True) for tool in tools)

    def create_pull_request(self, payload: dict[str, object]) -> dict[str, object]:
        result = create_pull_request(dict(payload))
        result["reviewChecklist"] = [
            "Validate branch diff semantics.",
            "Review source annotations before merge.",
            "Confirm branch target and budget inheritance.",
        ]
        result["changedEntityCount"] = len(result.get("changedEntities") or [])
        return result

    def review_pull_request(self, payload: dict[str, object]) -> dict[str, object]:
        raw_pr = payload.get("pullRequest") if isinstance(payload.get("pullRequest"), dict) else {}
        pr_id = payload.get("prId") or raw_pr.get("id")
        if pr_id is None:
            raise KeyError("prId")
        return review_pull_request(str(pr_id), dict(payload))

    def register_tools_hook(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "tools": list(self.register_tools()),
            "toolCount": len(self.register_tools()),
            "moduleId": self.module_id,
        }

    def register_activities(self, payload: dict[str, object]) -> dict[str, object]:
        activities = (
            WorkerActivityDescriptor(
                name="subagent.pr.create",
                moduleId=self.module_id,
                description="Create a pull request from a sub-agent branch into a target branch.",
                implementationRef="yggdrasil_subagent_pr.plugin:SubagentPrModule.create_pull_request",
                timeoutMs=5000,
                retryable=True,
            ),
            WorkerActivityDescriptor(
                name="subagent.pr.review",
                moduleId=self.module_id,
                description="Apply a review decision to a sub-agent pull request.",
                implementationRef="yggdrasil_subagent_pr.plugin:SubagentPrModule.review_pull_request",
                timeoutMs=5000,
                retryable=True,
            ),
        )
        return {
            "activities": [activity.model_dump(by_alias=True) for activity in activities],
            "moduleId": self.module_id,
        }

    def handle_event(self, envelope: EventEnvelope) -> EventHandlingResult:
        if envelope.event_type != "task.started":
            return EventHandlingResult(
                status="ignored",
                handled=False,
                summary=f"Event {envelope.event_type} is not handled by {self.module_id}.",
            )

        if isinstance(envelope.payload.get("pullRequest"), dict):
            review_result = self.review_pull_request(envelope.payload)
            aggregate_id = str(review_result["pullRequest"]["id"])
            event_type = "pr.reviewed"
            payload = review_result
            summary = "Reviewed pull request in response to task.started event."
        else:
            create_result = self.create_pull_request(envelope.payload)
            aggregate_id = str(create_result["pullRequest"]["id"])
            event_type = "pr.created"
            payload = create_result
            summary = "Created pull request in response to task.started event."

        emission = ModuleEventEmission(
            aggregateType="pull-request",
            aggregateId=aggregate_id,
            eventType=event_type,
            payload=payload,
            projectId=envelope.project_id,
            spaceId=envelope.space_id,
            branchId=envelope.branch_id,
            taskId=envelope.task_id,
            correlationId=envelope.correlation_id,
            causationId=envelope.event_id,
            source=self.module_id,
        )
        return EventHandlingResult(
            status="handled",
            handled=True,
            summary=summary,
            emittedEvents=[emission],
            healthStatus="healthy",
        )


plugin = SubagentPrModule()
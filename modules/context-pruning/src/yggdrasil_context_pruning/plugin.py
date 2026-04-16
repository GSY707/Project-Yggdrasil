from __future__ import annotations

from pathlib import Path
from typing import Any

from yggdrasil_sdk.contracts import ActorRef, ContextPruningPlan, EntityRef, EventEnvelope, EventHandlingResult, ModuleEventEmission
from yggdrasil_sdk.hooks import HookNames
from yggdrasil_sdk.module import BaseModulePlugin, HookRegistration
from yggdrasil_sdk.support import new_id, normalize_excerpt, utc_now


def _normalize_ref(value: Any, default_kind: str, index: int) -> EntityRef:
    if isinstance(value, EntityRef):
        return value
    if isinstance(value, dict):
        return EntityRef.model_validate(value)
    return EntityRef(kind=default_kind, id=str(value or f"generated-{index}"))


def _keyword_overlap(next_objective: str, item: dict[str, Any]) -> int:
    objective_terms = {term.lower() for term in str(next_objective).split() if term.strip()}
    haystack = f"{item.get('title', '')} {item.get('content', '')}".lower()
    return sum(1 for term in objective_terms if term in haystack)


def _estimated_tokens(item: dict[str, Any]) -> int:
    explicit = item.get("estimatedTokens")
    if explicit is not None:
        return max(1, int(explicit))
    return max(1, len(str(item.get("content", ""))) // 4)


class ContextPruningModule(BaseModulePlugin):
    module_id = "context-pruning"

    def manifest_path(self) -> Path:
        return Path(__file__).resolve().parents[2] / "yggdrasil.module.yaml"

    def register_hooks(self) -> tuple[HookRegistration, ...]:
        return (
            HookRegistration(name=HookNames.MODULE_ENABLE_PREFLIGHT, handler=self.enable_preflight),
            HookRegistration(name=HookNames.MODULE_HEALTH_REPORT, handler=self.report_health),
            HookRegistration(name=HookNames.CONTEXT_PRUNING_PLAN, handler=self.plan),
            HookRegistration(
                name=HookNames.CONTEXT_PRUNING_EXECUTE,
                handler=self.execute,
                side_effects="controlled-write",
            ),
        )

    def enable_preflight(self, payload: dict[str, object]) -> dict[str, object]:
        install = payload.get("install") if isinstance(payload.get("install"), dict) else {}
        if str(install.get("desiredState") or "enabled") not in {"enabled", "disabled"}:
            return {"status": "error", "summary": "Unexpected desired state for Context Pruning."}
        return {"status": "ok", "summary": "Context Pruning preflight passed."}

    def report_health(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "status": "healthy",
            "summary": "Context Pruning is ready to propose and execute pruning plans.",
        }

    def plan(self, payload: dict[str, object]) -> dict[str, object]:
        next_objective = str(payload.get("nextObjective") or payload.get("currentObjective") or "").strip()
        source_run_id = str(payload.get("sourceRunId") or payload.get("agentRunId") or new_id("run", self.module_id))
        task_id = str(payload.get("taskId") or new_id("task", source_run_id, stable=True))
        current_context = payload.get("currentContext") if isinstance(payload.get("currentContext"), list) else []
        budget = payload.get("budget") if isinstance(payload.get("budget"), dict) else {}
        protected_items = payload.get("protectedItems") if isinstance(payload.get("protectedItems"), list) else []
        protected_refs = [_normalize_ref(item, "node", index) for index, item in enumerate(protected_items)]
        protected_ids = {item.id for item in protected_refs}
        max_retained_tokens = int(
            budget.get("maxRetainedTokens")
            or budget.get("tokenBudget")
            or budget.get("tokenBudgetTotal")
            or 1200
        )

        scored_items: list[dict[str, Any]] = []
        for index, item in enumerate(current_context):
            if not isinstance(item, dict):
                continue
            item_ref = _normalize_ref(item.get("ref") or item.get("entityRef") or item.get("id"), "node", index)
            score = float(item.get("importance", 0.5)) + _keyword_overlap(next_objective, item)
            if item_ref.id in protected_ids:
                score += 10.0
            scored_items.append(
                {
                    "ref": item_ref,
                    "score": score,
                    "tokens": _estimated_tokens(item),
                    "item": item,
                }
            )

        scored_items.sort(key=lambda item: item["score"], reverse=True)
        retained_refs: list[EntityRef] = []
        compressed_refs: list[EntityRef] = []
        dropped_refs: list[EntityRef] = []
        retained_tokens = 0

        for scored_item in scored_items:
            ref = scored_item["ref"]
            tokens = scored_item["tokens"]
            is_protected = ref.id in protected_ids
            if is_protected or retained_tokens + tokens <= max_retained_tokens:
                retained_refs.append(ref)
                retained_tokens += tokens
                continue
            if scored_item["score"] >= 1.0:
                compressed_refs.append(ref)
                continue
            dropped_refs.append(ref)

        plan = ContextPruningPlan(
            id=new_id("prune", task_id, source_run_id),
            taskId=task_id,
            sourceRunId=source_run_id,
            nextObjective=next_objective or "Continue current task.",
            protectedRefs=protected_refs,
            retainedRefs=retained_refs,
            compressedRefs=compressed_refs,
            droppedRefs=dropped_refs,
            rationale=(
                f"Retained {len(retained_refs)} items inside a {max_retained_tokens}-token budget, "
                f"compressed {len(compressed_refs)} items, dropped {len(dropped_refs)} items."
            ),
            status="proposed",
            createdBy=ActorRef(type="module", id=self.module_id),
            createdAt=utc_now(),
        )
        response = plan.model_dump(by_alias=True, mode="json")
        response["estimatedRetainedTokens"] = retained_tokens
        response["estimatedCompressedTokens"] = sum(
            scored_item["tokens"] for scored_item in scored_items if scored_item["ref"] in compressed_refs
        )
        return response

    def execute(self, payload: dict[str, object]) -> dict[str, object]:
        current_context = payload.get("currentContext") if isinstance(payload.get("currentContext"), list) else []
        raw_plan = payload.get("plan") if isinstance(payload.get("plan"), dict) else self.plan(payload)
        normalized_plan = {
            key: value
            for key, value in raw_plan.items()
            if key not in {"estimatedRetainedTokens", "estimatedCompressedTokens"}
        }
        pruning_plan = ContextPruningPlan.model_validate(normalized_plan)
        executed_plan = pruning_plan.model_copy(update={"status": "executed"})
        items_by_id = {}

        for index, item in enumerate(current_context):
            if not isinstance(item, dict):
                continue
            ref = _normalize_ref(item.get("ref") or item.get("entityRef") or item.get("id"), "node", index)
            items_by_id[ref.id] = item

        retained_items = [items_by_id[ref.id] for ref in executed_plan.retained_refs if ref.id in items_by_id]
        compressed_items = [
            {
                "ref": ref.model_dump(),
                "summary": normalize_excerpt(
                    str(items_by_id.get(ref.id, {}).get("content") or items_by_id.get(ref.id, {}).get("title") or ""),
                    96,
                ),
            }
            for ref in executed_plan.compressed_refs
        ]
        dropped_items = [ref.model_dump() for ref in executed_plan.dropped_refs]
        return {
            "status": "executed",
            "plan": executed_plan.model_dump(by_alias=True, mode="json"),
            "retainedItems": retained_items,
            "compressedItems": compressed_items,
            "droppedItems": dropped_items,
            "compressedNarrative": (
                f"Retained {len(retained_items)} high-value items and compressed {len(compressed_items)} items "
                f"for the next objective: {executed_plan.next_objective}."
            ),
        }

    def handle_event(self, envelope: EventEnvelope) -> EventHandlingResult:
        if envelope.event_type != "context.pruning.requested":
            return EventHandlingResult(
                status="ignored",
                handled=False,
                summary=f"Event {envelope.event_type} is not handled by {self.module_id}.",
            )

        plan_result = self.plan(envelope.payload)
        aggregate_id = str(plan_result.get("taskId") or envelope.task_id or new_id("prune", envelope.event_id, stable=True))
        emissions = [
            ModuleEventEmission(
                aggregateType="task",
                aggregateId=aggregate_id,
                eventType="context.pruning.planned",
                payload=plan_result,
                projectId=envelope.project_id,
                spaceId=envelope.space_id,
                branchId=envelope.branch_id,
                taskId=envelope.task_id,
                correlationId=envelope.correlation_id,
                causationId=envelope.event_id,
                source=self.module_id,
            )
        ]
        summary = "Generated context pruning plan."
        if bool(envelope.payload.get("executeImmediately", True)):
            execute_result = self.execute({**envelope.payload, "plan": plan_result})
            emissions.append(
                ModuleEventEmission(
                    aggregateType="task",
                    aggregateId=aggregate_id,
                    eventType="context.pruning.completed",
                    payload=execute_result,
                    projectId=envelope.project_id,
                    spaceId=envelope.space_id,
                    branchId=envelope.branch_id,
                    taskId=envelope.task_id,
                    correlationId=envelope.correlation_id,
                    causationId=envelope.event_id,
                    source=self.module_id,
                )
            )
            summary = "Generated and executed context pruning plan."
        return EventHandlingResult(
            status="handled",
            handled=True,
            summary=summary,
            emittedEvents=emissions,
            healthStatus="healthy",
        )


plugin = ContextPruningModule()
from __future__ import annotations

from typing import Any

from .contracts import ModelRouteDecision
from .support import new_id, utc_now


DEFAULT_CANDIDATES = [
	{
		"model": "gpt-5.4",
		"provider": "copilot",
		"quality": 0.97,
		"costPer1k": 1.1,
		"latencyMs": 1700,
		"contextWindow": 128000,
	},
	{
		"model": "gpt-4.1",
		"provider": "openai",
		"quality": 0.95,
		"costPer1k": 1.0,
		"latencyMs": 1600,
		"contextWindow": 128000,
	},
	{
		"model": "gpt-4.1-mini",
		"provider": "openai",
		"quality": 0.84,
		"costPer1k": 0.32,
		"latencyMs": 850,
		"contextWindow": 128000,
	},
	{
		"model": "claude-3.7-sonnet",
		"provider": "anthropic",
		"quality": 0.93,
		"costPer1k": 0.85,
		"latencyMs": 1200,
		"contextWindow": 200000,
	},
]


TASK_WEIGHTS = {
	"coding": {"quality": 0.45, "budget": 0.15, "latency": 0.1, "context": 0.3},
	"research": {"quality": 0.45, "budget": 0.1, "latency": 0.1, "context": 0.35},
	"maintenance": {"quality": 0.2, "budget": 0.4, "latency": 0.25, "context": 0.15},
	"generic": {"quality": 0.35, "budget": 0.25, "latency": 0.15, "context": 0.25},
}


def _normalize_candidates(candidates: list[dict[str, object]] | None) -> list[dict[str, Any]]:
	raw_candidates = candidates or DEFAULT_CANDIDATES
	normalized: list[dict[str, Any]] = []
	for candidate in raw_candidates:
		normalized.append(
			{
				"model": str(candidate.get("model")),
				"provider": candidate.get("provider"),
				"quality": float(candidate.get("quality", 0.75)),
				"costPer1k": float(candidate.get("costPer1k", candidate.get("cost", 0.5))),
				"latencyMs": int(candidate.get("latencyMs", 1000)),
				"contextWindow": int(candidate.get("contextWindow", 64000)),
			}
		)
	return normalized


def _filter_candidates(
	candidates: list[dict[str, Any]],
	*,
	budget_limit: float | None,
	required_context_window: int | None,
	min_quality: float | None,
) -> list[dict[str, Any]]:
	filtered: list[dict[str, Any]] = []
	for candidate in candidates:
		if budget_limit is not None and candidate["costPer1k"] > budget_limit:
			continue
		if required_context_window is not None and candidate["contextWindow"] < required_context_window:
			continue
		if min_quality is not None and candidate["quality"] < min_quality:
			continue
		filtered.append(candidate)
	return filtered


def build_model_route_decision(
	task_type: str,
	*,
	task_id: str | None = None,
	agent_run_id: str | None = None,
	candidates: list[dict[str, object]] | None = None,
	budget_limit: float | None = None,
	required_context_window: int | None = None,
	min_quality: float | None = None,
) -> dict[str, object]:
	normalized_candidates = _normalize_candidates(candidates)
	viable_candidates = _filter_candidates(
		normalized_candidates,
		budget_limit=budget_limit,
		required_context_window=required_context_window,
		min_quality=min_quality,
	)
	if not viable_candidates:
		raise ValueError("No viable candidate model satisfies the current budget, quality, or context constraints.")

	weights = TASK_WEIGHTS.get(task_type, TASK_WEIGHTS["generic"])
	max_cost = max(candidate["costPer1k"] for candidate in viable_candidates)
	max_latency = max(candidate["latencyMs"] for candidate in viable_candidates)

	scored_candidates: list[dict[str, object]] = []
	for candidate in viable_candidates:
		budget_score = 1.0 - (candidate["costPer1k"] / max_cost if max_cost else 0.0)
		latency_score = 1.0 - (candidate["latencyMs"] / max_latency if max_latency else 0.0)
		context_score = 1.0
		if required_context_window:
			context_score = min(candidate["contextWindow"] / required_context_window, 1.0)
		total_score = (
			candidate["quality"] * weights["quality"]
			+ budget_score * weights["budget"]
			+ latency_score * weights["latency"]
			+ context_score * weights["context"]
		)
		scored_candidates.append(
			{
				**candidate,
				"budgetScore": round(budget_score, 3),
				"latencyScore": round(latency_score, 3),
				"contextScore": round(context_score, 3),
				"totalScore": round(total_score, 3),
				"scoreSummary": (
					f"quality={candidate['quality']:.2f}, budget={budget_score:.2f}, "
					f"latency={latency_score:.2f}, context={context_score:.2f}"
				),
			}
		)

	scored_candidates.sort(key=lambda candidate: candidate["totalScore"], reverse=True)
	chosen = scored_candidates[0]
	decision = ModelRouteDecision(
		id=new_id("route", task_id or task_type, chosen["model"]),
		taskId=task_id,
		agentRunId=agent_run_id,
		selectedModel=chosen["model"],
		selectedProvider=str(chosen["provider"]) if chosen["provider"] is not None else None,
		candidateModels=scored_candidates,
		reason=(
			f"Selected {chosen['model']} for task type {task_type} because it maximized weighted quality, "
			f"budget, latency, and context fit."
		),
		budgetScore=float(chosen["budgetScore"]),
		qualityScore=float(chosen["quality"]),
		latencyScore=float(chosen["latencyScore"]),
		routePolicyVersion="v0.1-task-weighted",
		createdAt=utc_now(),
	)
	response = decision.model_dump(by_alias=True, mode="json")
	response["taskType"] = task_type
	return response

from __future__ import annotations

from yggdrasil_sdk.model_routing import build_model_route_decision


def route_model(
    task_type: str,
    candidates: list[dict[str, object]] | None = None,
    budget_limit: float | None = None,
    required_context_window: int | None = None,
) -> dict[str, object]:
    return build_model_route_decision(
        task_type,
        candidates=candidates,
        budget_limit=budget_limit,
        required_context_window=required_context_window,
    )
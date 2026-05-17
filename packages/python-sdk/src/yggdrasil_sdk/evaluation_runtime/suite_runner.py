from ._common import *  # noqa: F403,F401
from .bootstrap import *  # noqa: F403,F401
from .scorer import *  # noqa: F403,F401

from .suite_cases_part_a import *  # noqa: F403,F401
from .suite_cases_part_b import *  # noqa: F403,F401
from .suite_cases_g2 import *  # noqa: F403,F401
from .suite_cases_g4 import *  # noqa: F403,F401

SCENARIO_HANDLERS: dict[str, Any] = {
    "m4.memory_import_retrieval": _run_memory_import_case,
    "m5.main_agent_pause_resume": _run_main_agent_case,
    "m6.subagent_pr_loop": _run_subagent_pr_case,
    "m8.memory_strategy_compare": _run_memory_strategy_compare_case,
    "m8.live_llm_task_execution": _run_live_llm_task_case,
    "m8.live_llm_tool_task": _run_live_llm_tool_case,
    "m9.shared_multimodal_reasoning": _run_m9_shared_multimodal_reasoning_case,
    "m9.pause_resume_memory_tree": _run_m9_pause_resume_memory_tree_case,
    "m9.control_plane_resource_surface": _run_m9_control_plane_resource_surface_case,
    "m9.prompt_control_plane": _run_m9_prompt_control_plane_case,
    "g2.complex_file_split_regression": _run_g2_complex_file_split_regression_case,
    "g4.scene_prompt_contract": _run_g4_scene_prompt_contract_case,
    "g4.scene_resume_contract": _run_g4_scene_resume_contract_case,
    "g4.scene_runtime_recovery": _run_g4_scene_runtime_recovery_case,
    "g4.scene_switch_isolation": _run_g4_scene_switch_isolation_case,
    "g4.live_provider_matrix": _run_g4_live_provider_matrix_case,
}

def run_evaluation_suite(suite_id: str, workspace_root: Path | None = None) -> dict[str, Any]:
    definition = get_evaluation_suite_definition(suite_id, workspace_root)
    fallback_context = None
    runtime = None
    try:
        runtime, run = _prepare_suite_run(definition, suite_id, workspace_root)
    except Exception:
        fallback_context = local_evaluation_runtime_environment(workspace_root)
        fallback_context.__enter__()
        runtime, run = _prepare_suite_run(definition, suite_id, workspace_root)

    try:
        case_results: list[dict[str, Any]] = []
        with observe_span("evaluation", f"suite:{suite_id}", kind="evaluation", attributes={"suiteId": suite_id}) as span:
            record_log("evaluation", "info", f"Starting evaluation suite {suite_id}", attributes={"runId": run.id})
            for case in definition.get("cases") or []:
                case_id = str(case.get("id") or new_id("evalcase", suite_id))
                scenario = str(case.get("scenario") or "")
                handler = SCENARIO_HANDLERS.get(scenario)
                if handler is None:
                    case_results.append(
                        {
                            "id": case_id,
                            "title": str(case.get("title") or case_id),
                            "scenario": scenario,
                            "status": "failed",
                            "durationMs": 0.0,
                            "detail": {"error": f"Unsupported scenario: {scenario}"},
                        }
                    )
                    continue

                case_started = perf_counter()
                try:
                    with isolated_runtime_environment(
                        disable_live_llm=not bool(case.get("requireLive", False)),
                        allow_paid_models=bool(case.get("allowPaidModels", False)),
                    ):
                        detail = handler(case)
                    case_status = "passed"
                except Exception as exc:
                    detail = {"error": str(exc), "errorType": exc.__class__.__name__}
                    case_status = "failed"
                    record_log(
                        "evaluation",
                        "error",
                        f"Evaluation case failed: {case_id}",
                        attributes={"runId": run.id, "suiteId": suite_id, "caseId": case_id, "error": str(exc)},
                    )
                duration_ms = round((perf_counter() - case_started) * 1000.0, 2)
                record_metric(
                    "evaluation",
                    "case.duration",
                    duration_ms,
                    kind="histogram",
                    unit="ms",
                    attributes={"suiteId": suite_id, "caseId": case_id, "status": case_status},
                )
                case_results.append(
                    {
                        "id": case_id,
                        "title": str(case.get("title") or case_id),
                        "scenario": scenario,
                        "status": case_status,
                        "durationMs": duration_ms,
                        "detail": detail,
                        "tags": [str(tag) for tag in case.get("tags") or []],
                        "difficulty": str(case.get("difficulty") or "medium"),
                    }
                )

            passed_count = len([row for row in case_results if row["status"] == "passed"])
            failed_count = len(case_results) - passed_count
            total_duration_ms = round(sum(float(row["durationMs"]) for row in case_results), 2)
            metrics_payload = {
                "suiteId": suite_id,
                "suiteName": definition.get("name") or suite_id,
                "runId": run.id,
                "status": "completed" if failed_count == 0 else "failed",
                "caseCount": len(case_results),
                "passedCount": passed_count,
                "failedCount": failed_count,
                "failedCaseCount": failed_count,
                "passRate": round(passed_count / len(case_results), 4) if case_results else 0.0,
                "totalDurationMs": total_duration_ms,
                "cases": case_results,
                "generatedAt": utc_now().isoformat(),
                "traceId": span["traceId"],
            }
            metrics_payload.update(_aggregate_case_metrics(case_results))

        metrics_dir = resolve_state_dir(workspace_root) / "evaluations"
        metrics_dir.mkdir(parents=True, exist_ok=True)
        metrics_path = metrics_dir / f"{run.id}.json"
        write_json(metrics_path, metrics_payload)
        with runtime.session_scope() as session:
            repository = EvaluationRepository(session)
            completed_run = repository.update_run(
                run.id,
                {
                    "status": metrics_payload["status"],
                    "metricsRef": ExternalRef(type="file", locator=str(metrics_path.resolve())),
                    "endedAt": utc_now(),
                }
            )

        record_log(
            "evaluation",
            "info",
            f"Completed evaluation suite {suite_id}",
            attributes={"runId": completed_run.id, "status": completed_run.status, "failedCount": metrics_payload["failedCount"]},
        )
        flush_observability_exporters()
        return {
            "suite": definition,
            "run": completed_run.model_dump(by_alias=True, mode="json"),
            "metrics": metrics_payload,
        }
    finally:
        if runtime is not None:
            runtime.dispose()
        if fallback_context is not None:
            fallback_context.__exit__(None, None, None)


__all__ = [name for name in globals() if not name.startswith("__")]

from __future__ import annotations

import pytest

from yggdrasil_sdk import run_evaluation_suite


pytestmark = pytest.mark.slow
DEBUG_PLAN_SKIP = pytest.mark.skip(reason="Moved to debug plan 2026-06-08: M9 acceptance capability chain")


@DEBUG_PLAN_SKIP
def test_m9_acceptance_suite_exercises_capability_chain() -> None:
    result = run_evaluation_suite("evalsuite_acceptance_m9_capabilities")

    assert result["run"]["status"] == "completed"
    metrics = result["metrics"]
    assert metrics["status"] == "completed"
    assert metrics["passRate"] == 1.0

    cases = {case["id"]: case for case in metrics["cases"]}

    shared_case = cases["evalcase_m9_shared_multimodal_reasoning"]
    assert shared_case["status"] == "passed"
    shared_detail = shared_case["detail"]
    assert shared_detail["mountedSpaceCount"] >= 1
    assert shared_detail["segmentCount"] >= 1
    assert shared_detail["createdEdgeCount"] >= 1
    assert shared_detail["datasetRowCount"] >= 1
    assert shared_detail["modelArtifactStatus"] == "validated"
    assert shared_detail["combinedScore"] >= 0.75
    assert {
        "shared-memory.describe-mounts",
        "shared-memory.expand-retrieval",
        "multimodal-memory.ingest-asset",
        "relation-discovery.scan-branch",
        "memory-organizer.soft-forgetting",
        "training-lab.prepare-dataset",
        "training-lab.stage-model-artifact",
    } <= set(shared_detail["usedFeatures"])

    pause_case = cases["evalcase_m9_pause_resume_memory_tree"]
    assert pause_case["status"] == "passed"
    pause_detail = pause_case["detail"]
    assert pause_detail["pauseStatus"] == "paused"
    assert pause_detail["resumeStatus"] == "completed"
    assert pause_detail["mountedSpaceCount"] >= 1
    assert pause_detail["rehydratedContextCount"] >= 1
    assert pause_detail["followupActionCount"] >= 1
    assert pause_detail["executionNoteCount"] >= 2
    assert pause_detail["combinedScore"] >= 0.75
    assert {
        "shared-memory.mount-root",
        "pause-resume.prepare",
        "pause-resume.rehydrate",
        "runtime-kernel.pause-request",
        "runtime-kernel.resume",
    } <= set(pause_detail["usedFeatures"])

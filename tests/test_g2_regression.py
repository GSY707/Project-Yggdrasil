from __future__ import annotations

from yggdrasil_sdk import run_evaluation_suite


def test_g2_regression_suite_fixes_complex_file_split_sample() -> None:
    result = run_evaluation_suite("evalsuite_regression_g2_controlled_autonomy")

    assert result["run"]["status"] == "completed"
    metrics = result["metrics"]
    assert metrics["status"] == "completed"
    assert metrics["passRate"] == 1.0

    detail = metrics["cases"][0]["detail"]
    assert detail["legacyMonolithsAbsent"] is True
    assert detail["routeLayerUsesServices"] is True
    assert {group["groupId"] for group in detail["groups"]} == {
        "persistence.repositories",
        "core-api.services",
    }
    assert detail["maxLineCount"] <= 800

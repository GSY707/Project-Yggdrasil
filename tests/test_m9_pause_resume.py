from __future__ import annotations

from yggdrasil_agent_runtime.runtime import prepare_pause_snapshot
from yggdrasil_pause_resume.plugin import PauseResumeModule


def test_pause_resume_module_adds_resume_digest_and_rehydrates_context() -> None:
    snapshot = prepare_pause_snapshot(
        "task_pause_m9",
        {
            "agentRunId": "run_pause_m9",
            "pendingActions": [{"kind": "await-human-review"}],
            "currentResponseState": "completed",
            "currentContextState": [
                {
                    "id": "ctx_restore",
                    "title": "Resume Context",
                    "content": "resume recovery shared memory runtime graph",
                }
            ],
        },
    )
    assert snapshot["safeToPause"] is True
    assert "resumeToken" not in snapshot
    assert snapshot["contextRef"]["type"] == "state-file"
    assert snapshot["storageManifestRef"]["type"] == "state-file"
    assert any(action["kind"] == "resume-digest" for action in snapshot["pendingActions"])
    assert any("Prepared safe-stop" in summary for summary in snapshot["moduleSummaries"])

    rehydrated = PauseResumeModule().rehydrate_resume(
        {
            "taskSnapshot": snapshot,
            "rootMounts": snapshot["rootMountPreview"],
        }
    )
    assert rehydrated["restoredState"]["currentContext"][0]["id"] == "ctx_restore"
    assert rehydrated["followupActions"][0]["kind"] == "resume-checkpoint"

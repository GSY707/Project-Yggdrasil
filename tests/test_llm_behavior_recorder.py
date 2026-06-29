from __future__ import annotations

from types import SimpleNamespace

from yggdrasil_sdk.llm_runtime.behavior_recorder import persist_llm_behavior_record
from yggdrasil_sdk.support import read_json, write_json


def test_llm_behavior_recorder_persists_runtime_derived_trace(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("YGGDRASIL_STATE_DIR", raising=False)
    monkeypatch.delenv("YGGDRASIL_STATE_ROOT", raising=False)
    task = SimpleNamespace(id="task_behavior", project_id="project_behavior")
    run = SimpleNamespace(id="run_behavior")
    invocation = {"id": "llm_behavior", "status": "completed"}
    state_dir = tmp_path / ".yggdrasil" / "state"
    request_path = state_dir / "llm" / "requests" / "llm_behavior.json"
    response_path = state_dir / "llm" / "responses" / "llm_behavior.json"
    prompt_path = state_dir / "prompt" / "compiled" / "llm_behavior.json"

    write_json(
        request_path,
        {
            "messages": [{"role": "user", "content": "do work"}],
            "tools": [{"function": {"name": "mcp.web.search_web"}}],
        },
    )
    write_json(
        response_path,
        {
            "assistantText": (
                "<work-node-create title=\"查资料\">探索来源</work-node-create>\n"
                "- 搜索工具: `mcp.web.search_web` (1次)\n"
                "- 网页抓取: `mcp.web.fetch_webpage` (18次)"
            ),
            "runtimeMetrics": {"windowIndex": 1, "restartCount": 0},
            "rounds": [
                {
                    "index": 0,
                    "mode": "live",
                    "finishReason": "tool_calls",
                    "toolCalls": ["mcp.web.search_web", "mcp.web.fetch_webpage"],
                    "toolFailures": [],
                }
            ],
            "toolExecutions": [
                {"tool": {"name": "mcp.web.search_web"}, "success": True, "result": {"status": "ok"}},
                {"tool": {"name": "mcp.web.fetch_webpage"}, "success": True, "result": {"status": "ok"}},
                {"tool": {"name": "mcp.web.fetch_webpage"}, "success": True, "result": {"status": "ok"}},
            ],
        },
    )
    write_json(
        prompt_path,
        {
            "messages": [
                {
                    "role": "system",
                    "content": "工作树使用案例。根节点和非叶子节点负责高层视角，叶子节点执行。",
                }
            ],
            "prompt": {"registeredTools": [{"name": "mcp.web.search_web"}]},
        },
    )

    result = persist_llm_behavior_record(
        workspace_root=tmp_path,
        task=task,
        run=run,
        invocation=invocation,
        prompt_artifact_id="prompt_behavior",
        request_path=request_path,
        response_path=response_path,
        prompt_path=prompt_path,
        status="completed",
    )

    record_path = tmp_path / ".yggdrasil" / "state" / "llm" / "behavior-records" / "llm_behavior.json"
    record = read_json(record_path, {})
    assert result["summary"]["toolExecutionCount"] == 3
    assert record["prompt"]["textAvailable"] is True
    assert record["prompt"]["containsWorkTreeCases"] is True
    assert record["prompt"]["containsRootLeafGuidance"] is True
    assert record["assistantBehavior"]["workTreeDirectives"][0]["tag"] == "work-node-create"
    assert record["assistantBehavior"]["workTreeNaturalLanguageClaims"] == []
    assert record["assistantBehavior"]["workTreeClaimWithoutDirective"] is False
    assert record["integrity"]["actualToolCounts"] == {
        "mcp.web.fetch_webpage": 2,
        "mcp.web.search_web": 1,
    }
    assert record["integrity"]["assistantSelfReportToolCountMismatches"] == [
        {"toolName": "mcp.web.fetch_webpage", "reportedCount": 18, "actualCount": 2}
    ]

    index_path = tmp_path / ".yggdrasil" / "state" / "llm" / "behavior-records" / "by-task" / "task_task_behavior.json"
    index = read_json(index_path, {})
    assert index["recordCount"] == 1
    assert index["records"][0]["recordRef"] == ".yggdrasil/state/llm/behavior-records/llm_behavior.json"


def test_llm_behavior_recorder_flags_natural_language_work_tree_claim_without_directive(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("YGGDRASIL_STATE_DIR", raising=False)
    monkeypatch.delenv("YGGDRASIL_STATE_ROOT", raising=False)
    task = SimpleNamespace(id="task_behavior_claim", project_id="project_behavior")
    run = SimpleNamespace(id="run_behavior_claim")
    invocation = {"id": "llm_behavior_claim", "status": "completed"}
    state_dir = tmp_path / ".yggdrasil" / "state"
    request_path = state_dir / "llm" / "requests" / "llm_behavior_claim.json"
    response_path = state_dir / "llm" / "responses" / "llm_behavior_claim.json"
    prompt_path = state_dir / "prompt" / "compiled" / "llm_behavior_claim.json"

    write_json(request_path, {"messages": [{"role": "user", "content": "do work"}]})
    write_json(response_path, {"assistantText": "现在创建并进入 leaf 2，然后写 Leaf Handoff。"})
    write_json(prompt_path, {"messages": [{"role": "system", "content": "根节点和非叶子节点负责高层视角，叶子节点执行。"}]})

    result = persist_llm_behavior_record(
        workspace_root=tmp_path,
        task=task,
        run=run,
        invocation=invocation,
        prompt_artifact_id="prompt_behavior_claim",
        request_path=request_path,
        response_path=response_path,
        prompt_path=prompt_path,
        status="completed",
    )

    record_path = tmp_path / ".yggdrasil" / "state" / "llm" / "behavior-records" / "llm_behavior_claim.json"
    record = read_json(record_path, {})
    assert result["summary"]["workTreeDirectiveCount"] == 0
    assert result["summary"]["workTreeClaimWithoutDirective"] is True
    assert record["assistantBehavior"]["workTreeDirectives"] == []
    assert record["assistantBehavior"]["workTreeNaturalLanguageClaims"]
    assert record["assistantBehavior"]["workTreeClaimWithoutDirective"] is True


def test_llm_behavior_recorder_treats_work_node_complete_as_directive(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("YGGDRASIL_STATE_DIR", raising=False)
    monkeypatch.delenv("YGGDRASIL_STATE_ROOT", raising=False)
    task = SimpleNamespace(id="task_behavior_complete", project_id="project_behavior")
    run = SimpleNamespace(id="run_behavior_complete")
    invocation = {"id": "llm_behavior_complete", "status": "completed"}
    state_dir = tmp_path / ".yggdrasil" / "state"
    request_path = state_dir / "llm" / "requests" / "llm_behavior_complete.json"
    response_path = state_dir / "llm" / "responses" / "llm_behavior_complete.json"
    prompt_path = state_dir / "prompt" / "compiled" / "llm_behavior_complete.json"

    write_json(request_path, {"messages": [{"role": "user", "content": "do work"}]})
    write_json(
        response_path,
        {
            "assistantText": (
                '<work-node-complete status="completed">\n'
                "Result: leaf finished.\n"
                "Evidence: search A.\n"
                "Parent next: evaluate.\n"
                "</work-node-complete>"
            )
        },
    )
    write_json(prompt_path, {"messages": [{"role": "system", "content": "根节点和非叶子节点负责高层视角，叶子节点执行。"}]})

    result = persist_llm_behavior_record(
        workspace_root=tmp_path,
        task=task,
        run=run,
        invocation=invocation,
        prompt_artifact_id="prompt_behavior_complete",
        request_path=request_path,
        response_path=response_path,
        prompt_path=prompt_path,
        status="completed",
    )

    record_path = tmp_path / ".yggdrasil" / "state" / "llm" / "behavior-records" / "llm_behavior_complete.json"
    record = read_json(record_path, {})
    assert result["summary"]["workTreeDirectiveCount"] == 1
    assert result["summary"]["workTreeClaimWithoutDirective"] is False
    assert record["assistantBehavior"]["workTreeDirectives"][0]["tag"] == "work-node-complete"
    assert record["assistantBehavior"]["workTreeClaimWithoutDirective"] is False


def test_llm_behavior_recorder_counts_round_tool_calls_when_execution_list_is_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("YGGDRASIL_STATE_DIR", raising=False)
    monkeypatch.delenv("YGGDRASIL_STATE_ROOT", raising=False)
    task = SimpleNamespace(id="task_round_tools", project_id="project_behavior")
    run = SimpleNamespace(id="run_round_tools")
    invocation = {"id": "llm_round_tools", "status": "completed"}
    state_dir = tmp_path / ".yggdrasil" / "state"
    request_path = state_dir / "llm" / "requests" / "llm_round_tools.json"
    response_path = state_dir / "llm" / "responses" / "llm_round_tools.json"
    prompt_path = state_dir / "prompt" / "compiled" / "llm_round_tools.json"

    write_json(request_path, {"toolSpecs": [{"function": {"name": "mcp.web.search_web"}}]})
    write_json(prompt_path, {"messageCount": 2, "messageDigests": [{"sha256": "a"}, {"sha256": "b"}]})
    write_json(
        response_path,
        {
            "assistantText": "已达到配置的工具轮次上限。",
            "rounds": [
                {"index": 0, "finishReason": "tool_calls", "toolCalls": ["mcp.web.search_web"]},
                {
                    "index": 1,
                    "finishReason": "tool-round-limit-short-circuit",
                    "toolCalls": ["mcp.web.fetch_webpage", "mcp.web.fetch_webpage"],
                },
            ],
        },
    )

    result = persist_llm_behavior_record(
        workspace_root=tmp_path,
        task=task,
        run=run,
        invocation=invocation,
        prompt_artifact_id="prompt_round_tools",
        request_path=request_path,
        response_path=response_path,
        prompt_path=prompt_path,
        status="completed",
    )

    record_path = tmp_path / ".yggdrasil" / "state" / "llm" / "behavior-records" / "llm_round_tools.json"
    record = read_json(record_path, {})
    assert result["summary"]["toolExecutionCount"] == 0
    assert result["summary"]["observedToolCallCount"] == 3
    assert record["prompt"]["messageCount"] == 2
    assert record["prompt"]["messageDigestCount"] == 2
    assert record["prompt"]["textAvailable"] is False
    assert record["prompt"]["requestToolSpecCount"] == 1
    assert record["integrity"]["toolEvidenceSource"] == "rounds.toolCalls"
    assert record["integrity"]["actualToolCounts"] == {
        "mcp.web.fetch_webpage": 2,
        "mcp.web.search_web": 1,
    }

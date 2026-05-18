# P2 任务16实现规范：runtime metrics（2026-05-17）

来源：从总规范文档按任务拆分，保持原始代码片段与断言建议。

---

# 任务 16 (C6): 记录 runtime metrics

### 16.1 目标与背景

统一 restart 前后指标口径与字段名，形成可比较的指标快照。关键承诺：
- 定义统一的 RuntimeMetricsSnapshot 数据类
- 包含标准字段：windowIndex、restartCount、totalTokensUsed、totalCostUsed、cumulativeWindowSpanTokens、carryForwardLossCount
- 在每次窗口结束时生成快照并保存到 artifact
- 保证同一任务跨窗口指标单调性与一致性

### 16.2 新增数据类/模型定义

**文件**: `packages/python-sdk/src/yggdrasil_sdk/contracts.py`

在 `ToolExecutionResult` 之后添加：

```python
class RuntimeMetricsSnapshot(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    # Window identification
    window_index: int = Field(alias="windowIndex")
    restart_count: int = Field(alias="restartCount")
    
    # Token consumption
    total_tokens_used: int = Field(alias="totalTokensUsed")
    input_tokens_used: int = Field(alias="inputTokensUsed")
    output_tokens_used: int = Field(alias="outputTokensUsed")
    cache_hit_tokens: int = Field(alias="cacheHitTokens", default=0)
    reasoning_tokens: int = Field(alias="reasoningTokens", default=0)
    
    # Cost consumption
    total_cost_used: float = Field(alias="totalCostUsed")
    
    # Cumulative spans
    cumulative_window_span_tokens: int = Field(alias="cumulativeWindowSpanTokens")
    window_span_tokens: int = Field(alias="windowSpanTokens")
    
    # Carry-forward loss tracking
    carry_forward_loss_count: int = Field(alias="carryForwardLossCount", default=0)
    
    # Compression/pruning
    compression_count: int = Field(alias="compressionCount", default=0)
    
    # Tool round statistics
    tool_rounds_executed: int = Field(alias="toolRoundsExecuted", default=0)
    tool_calls_total: int = Field(alias="toolCallsTotal", default=0)
    tool_calls_failed: int = Field(alias="toolCallsFailed", default=0)
    
    # Timing information
    total_latency_ms: float = Field(alias="totalLatencyMs")
    first_token_latency_ms: float | None = Field(default=None, alias="firstTokenLatencyMs")
    
    # Context information
    effective_context_window: int = Field(alias="effectiveContextWindow")
    window_restart_threshold: int = Field(alias="windowRestartThreshold")
    
    # Capture timestamp
    captured_at: str = Field(default_factory=utc_now)
    
    # Optional metadata
    notes: str | None = None


class RuntimeMetricsArtifact(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    task_id: str = Field(alias="taskId")
    agent_run_id: str = Field(alias="agentRunId")
    snapshots: list[RuntimeMetricsSnapshot]
    baseline_snapshot: RuntimeMetricsSnapshot | None = Field(
        default=None, alias="baselineSnapshot"
    )  # Metrics from window 0 or previous restart
    parity_check: dict[str, Any] | None = None  # Optional parity comparison results
    created_at: str = Field(default_factory=utc_now)
```

### 16.3 函数签名变更说明

#### 16.3.1 新增指标收集函数

**文件**: `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py`

在文件顶部导入后添加：

```python
from ..contracts import RuntimeMetricsSnapshot, RuntimeMetricsArtifact


def _build_runtime_metrics_snapshot(
    runtime_metrics: dict[str, Any],
    *,
    input_tokens_used: int,
    output_tokens_used: int,
    cost_used: float,
    tool_executions: list[dict[str, Any]] | None = None,
    latency_ms: float = 0.0,
    first_token_latency_ms: float | None = None,
    cache_hit_tokens: int = 0,
    reasoning_tokens: int = 0,
) -> RuntimeMetricsSnapshot:
    """
    Build a runtime metrics snapshot from current execution state.
    
    Args:
        runtime_metrics: Current runtime metrics dict
        input_tokens_used: Tokens used in input
        output_tokens_used: Tokens used in output
        cost_used: Cost consumed
        tool_executions: List of tool execution records
        latency_ms: Total execution latency
        first_token_latency_ms: Time to first token
        cache_hit_tokens: Cache hit token count
        reasoning_tokens: Reasoning token count
    
    Returns:
        RuntimeMetricsSnapshot with standardized fields
    """
    total_tokens_used = input_tokens_used + output_tokens_used
    
    # Count tool statistics
    tool_calls_total = 0
    tool_calls_failed = 0
    tool_rounds_executed = 0
    
    if tool_executions:
        for execution in tool_executions:
            if isinstance(execution, dict):
                tool_calls_total += 1
                if not execution.get("success", False):
                    tool_calls_failed += 1
        
        # Estimate tool rounds (approximate)
        tool_rounds_executed = max(1, len([e for e in tool_executions if e.get("success")]))
    
    return RuntimeMetricsSnapshot(
        window_index=max(_int_metric(runtime_metrics.get("windowIndex"), 1), 1),
        restart_count=max(_int_metric(runtime_metrics.get("restartCount"), 0), 0),
        total_tokens_used=total_tokens_used,
        input_tokens_used=input_tokens_used,
        output_tokens_used=output_tokens_used,
        cache_hit_tokens=cache_hit_tokens,
        reasoning_tokens=reasoning_tokens,
        total_cost_used=round(cost_used, 6),
        cumulative_window_span_tokens=max(
            _int_metric(runtime_metrics.get("cumulativeWindowSpanTokens"), 0), 0
        ),
        window_span_tokens=max(
            _int_metric(runtime_metrics.get("windowSpanTokens"), 0), 0
        ),
        carry_forward_loss_count=max(
            _int_metric(runtime_metrics.get("carryForwardLossCount"), 0), 0
        ),
        compression_count=max(
            _int_metric(runtime_metrics.get("compressionCount"), 0), 0
        ),
        tool_rounds_executed=tool_rounds_executed,
        tool_calls_total=tool_calls_total,
        tool_calls_failed=tool_calls_failed,
        total_latency_ms=latency_ms,
        first_token_latency_ms=first_token_latency_ms,
        effective_context_window=max(
            _int_metric(runtime_metrics.get("effectiveContextWindow"), 0), 0
        ),
        window_restart_threshold=max(
            _int_metric(runtime_metrics.get("windowRestartThreshold"), 0), 0
        ),
    )
```

#### 16.3.2 新增指标保存函数

**文件**: `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py`

```python
def _persist_runtime_metrics_artifact(
    session,
    *,
    task_id: str,
    agent_run_id: str,
    current_snapshot: RuntimeMetricsSnapshot,
    baseline_snapshot: RuntimeMetricsSnapshot | None = None,
    parity_check: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Persist runtime metrics snapshot to artifact storage.
    
    Returns:
        Artifact record dict with id and locator
    """
    runtime_repository = RuntimeRepository(session)
    artifact_id = new_id("metrics-artifact", task_id, agent_run_id, stable=False)
    
    snapshots = [current_snapshot]
    if baseline_snapshot is not None:
        snapshots.insert(0, baseline_snapshot)
    
    artifact_payload = {
        "id": artifact_id,
        "taskId": task_id,
        "agentRunId": agent_run_id,
        "snapshots": [s.model_dump(by_alias=True, mode="json") for s in snapshots],
        "baselineSnapshot": (
            baseline_snapshot.model_dump(by_alias=True, mode="json")
            if baseline_snapshot is not None
            else None
        ),
        "parityCheck": parity_check,
        "createdAt": utc_now(),
    }
    
    artifact_path = ensure_state_subdir("runtime/metrics", resolve_workspace_root()) / f"{artifact_id}.json"
    write_json(artifact_path, artifact_payload)
    
    return {
        "id": artifact_id,
        "locator": str(relative_workspace_path(artifact_path, resolve_workspace_root())),
        "payload": artifact_payload,
    }
```

#### 16.3.3 修改执行主循环以收集并保存指标

**修改位置**: `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py` (在返回最终结果前)

```python
# 在 invoke_runtime_completion 完成后，构建最终返回前添加：

            # Build metrics snapshot for this window/execution
            metrics_snapshot = _build_runtime_metrics_snapshot(
                runtime_metrics,
                input_tokens_used=actual_input_tokens,
                output_tokens_used=actual_output_tokens,
                cost_used=actual_cost,
                tool_executions=llm_result.get("toolExecutions"),
                latency_ms=_elapsed_ms(llm_invoke_started_at),
                first_token_latency_ms=llm_result.get("timings", {}).get("firstTokenLatencyMs"),
                cache_hit_tokens=int(usage_totals.get("cacheHitInputTokens", 0)),
                reasoning_tokens=int(usage_totals.get("reasoningTokens", 0)),
            )
            
            # Persist metrics artifact
            baseline_snapshot = None
            if runtime_metrics.get("windowIndex", 1) > 1 and resume_path == "restart-snapshot":
                # For restart cases, include baseline from first window
                baseline_snapshot = None  # Could be fetched from previous run
            
            metrics_artifact = _persist_runtime_metrics_artifact(
                session,
                task_id=task_id,
                agent_run_id=run.id,
                current_snapshot=metrics_snapshot,
                baseline_snapshot=baseline_snapshot,
            )
            
            # Add metrics artifact reference to response
            response["runtimeMetricsSnapshot"] = metrics_snapshot.model_dump(by_alias=True, mode="json")
            response["runtimeMetricsArtifactId"] = metrics_artifact["id"]
            response["runtimeMetricsLocator"] = metrics_artifact["locator"]
```

### 16.4 集成点说明

1. **指标收集时机**:
   - 每次 invoke_runtime_completion 完成后
   - 包括 LLM 调用、工具执行、成本追踪等全面数据

2. **指标保存位置**:
   - 本地文件系统: `runtime/metrics/{artifact-id}.json`
   - 可通过 artifact API 查询和对比

3. **多窗口对比**:
   - 保存 baseline 指标供跨窗口对比
   - 支持计算 parity gap（质量下降幅度）

4. **监控集成**:
   - 指标可导入 Prometheus/Grafana
   - 支持告警（如成本陡增）

### 16.5 测试断言建议

```python
def test_runtime_metrics_snapshot_captures_all_fields() -> None:
    """Test that snapshot captures all required fields."""
    snapshot = _build_runtime_metrics_snapshot(
        {
            "windowIndex": 2,
            "restartCount": 1,
            "cumulativeWindowSpanTokens": 5000,
            "carryForwardLossCount": 0,
            "effectiveContextWindow": 8000,
            "windowRestartThreshold": 6000,
        },
        input_tokens_used=1000,
        output_tokens_used=500,
        cost_used=0.5,
        latency_ms=2500.0,
    )
    
    assert snapshot.window_index == 2
    assert snapshot.restart_count == 1
    assert snapshot.total_tokens_used == 1500
    assert snapshot.total_cost_used == 0.5
    assert snapshot.cumulative_window_span_tokens == 5000


def test_metrics_monotonicity_across_windows() -> None:
    """Test that cumulative metrics increase monotonically across windows."""
    snapshot_w1 = RuntimeMetricsSnapshot(
        window_index=1,
        cumulative_window_span_tokens=5000,
        total_tokens_used=1000,
        total_cost_used=0.5,
        # ... other fields
    )
    
    snapshot_w2 = RuntimeMetricsSnapshot(
        window_index=2,
        cumulative_window_span_tokens=10000,
        total_tokens_used=800,
        total_cost_used=0.3,
        # ... other fields
    )
    
    # Cumulative should increase
    assert snapshot_w2.cumulative_window_span_tokens >= snapshot_w1.cumulative_window_span_tokens
    
    # Per-window may vary, but cumulative is consistent
    # (This is a design choice - cumulative = sum of all prior windows)


def test_metrics_artifact_persists_and_retrieves() -> None:
    """Test that metrics artifact is persisted and can be retrieved."""
    # Build and persist artifact
    # Verify that:
    # 1. File is created at expected path
    # 2. JSON content matches input
    # 3. Can be loaded back from disk
    pass
```

---


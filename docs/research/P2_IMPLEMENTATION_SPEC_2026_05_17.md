# P2 推理执行稳态化 - 详细代码实现规范 (2026-05-17)

- 文档状态：Implementation Specification for Phase P2 (Tasks 14-17)
- 日期：2026-05-17
- 目标：提供完整的代码改动指导，用于实现 LLM 预算治理、工具失败隔离、指标导出、安全停止等四大任务

---

## 任务 14 (C2): LLM 调用与预算治理

### 14.1 目标与背景

固化 hard fail 与 retry 边界，避免成功后被预算后置检查误判。关键承诺：
- 累积成本超过预算时立即 hard fail，停止工具循环
- 定义明确的 retry 策略上限
- 预调用时检查预算充分性
- 返回结构包含 `budgetCheckResult` 标记是否触发预算限制

### 14.2 新增常量定义

**文件**: `packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py`

```python
# 新增常量（在文件头部 _USAGE_COUNTER_FIELDS 之后）
_MAX_TOOL_RETRIES = 2
_COST_BUDGET_BUFFER = 0.01  # 1% safety margin
_TOKEN_BUDGET_SAFETY_MARGIN = 32  # minimum safety buffer in tokens
```

### 14.3 新增数据类/模型定义

**文件**: `packages/python-sdk/src/yggdrasil_sdk/contracts.py`

在 `BudgetState` 类之后添加：

```python
class BudgetCheckResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    check_passed: bool = Field(alias="checkPassed")
    reason: str | None = None  # null if check_passed=True
    available_token_budget: int = Field(alias="availableTokenBudget")
    available_cost_budget: float = Field(alias="availableCostBudget")
    estimated_total_tokens: int = Field(alias="estimatedTotalTokens")
    estimated_cost: float = Field(alias="estimatedCost")
    timestamp: str = Field(default_factory=utc_now)


class BudgetOverrunResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    is_overrun: bool = Field(alias="isOverrun")
    violation_type: Literal["token", "cost", "both"] | None = Field(
        default=None, alias="violationType"
    )
    tokens_used: int = Field(alias="tokensUsed")
    cost_used: float = Field(alias="costUsed")
    tokens_exceeded_by: int = Field(alias="tokensExceededBy")
    cost_exceeded_by: float = Field(alias="costExceededBy")
```

### 14.4 函数签名变更说明

#### 14.4.1 新增预算检查函数

**文件**: `packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py`

在 `invoke_runtime_completion` 函数之前添加新的预算检查函数：

```python
def _check_pre_invocation_budget(
    budget: BudgetState,
    *,
    estimated_input_tokens: int,
    estimated_output_tokens: int,
    estimated_cost: float,
) -> BudgetCheckResult:
    """
    Pre-invocation budget validation.
    
    Args:
        budget: Current budget state
        estimated_input_tokens: Estimated input tokens for next call
        estimated_output_tokens: Estimated output tokens for next call
        estimated_cost: Estimated cost for next call
    
    Returns:
        BudgetCheckResult with pass/fail status and details
    
    Raises:
        None - returns result object instead
    """
    estimated_total_tokens = estimated_input_tokens + estimated_output_tokens
    available_token_budget = (
        budget.token_budget_total - budget.token_budget_used
        if budget.token_budget_total is not None
        else float("inf")
    )
    available_cost_budget = (
        budget.cost_budget_total - budget.cost_budget_used
        if budget.cost_budget_total is not None
        else float("inf")
    )
    
    violation_reason = None
    check_passed = True
    
    # Token budget check with safety margin
    if budget.token_budget_total is not None:
        required_tokens = estimated_total_tokens + _TOKEN_BUDGET_SAFETY_MARGIN
        if available_token_budget < required_tokens:
            violation_reason = (
                f"Insufficient token budget: "
                f"required {required_tokens}, available {available_token_budget}"
            )
            check_passed = False
    
    # Cost budget check with buffer
    if budget.cost_budget_total is not None and check_passed:
        required_cost = estimated_cost + _COST_BUDGET_BUFFER
        if available_cost_budget < required_cost:
            violation_reason = (
                f"Insufficient cost budget: "
                f"required {required_cost:.6f}, available {available_cost_budget:.6f}"
            )
            check_passed = False
    
    return BudgetCheckResult(
        check_passed=check_passed,
        reason=violation_reason,
        available_token_budget=int(available_token_budget) if available_token_budget != float("inf") else 999999,
        available_cost_budget=float(available_cost_budget) if available_cost_budget != float("inf") else 999999.0,
        estimated_total_tokens=estimated_total_tokens,
        estimated_cost=estimated_cost,
    )


def _check_post_invocation_budget(
    budget: BudgetState,
    *,
    input_tokens_used: int,
    output_tokens_used: int,
    cost_used: float,
) -> BudgetOverrunResult:
    """
    Post-invocation budget validation.
    
    Returns BudgetOverrunResult indicating whether actual usage exceeded budget.
    """
    total_tokens_used = input_tokens_used + output_tokens_used
    tokens_after = budget.token_budget_used + total_tokens_used
    cost_after = budget.cost_budget_used + cost_used
    
    is_overrun = False
    violation_type = None
    tokens_exceeded_by = 0
    cost_exceeded_by = 0.0
    
    # Check token overrun
    if budget.token_budget_total is not None and tokens_after > budget.token_budget_total:
        is_overrun = True
        violation_type = "token"
        tokens_exceeded_by = tokens_after - budget.token_budget_total
    
    # Check cost overrun
    if budget.cost_budget_total is not None and cost_after > budget.cost_budget_total:
        is_overrun = True
        if violation_type == "token":
            violation_type = "both"
        else:
            violation_type = "cost"
        cost_exceeded_by = round(cost_after - budget.cost_budget_total, 6)
    
    return BudgetOverrunResult(
        is_overrun=is_overrun,
        violation_type=violation_type,
        tokens_used=total_tokens_used,
        cost_used=cost_used,
        tokens_exceeded_by=tokens_exceeded_by,
        cost_exceeded_by=cost_exceeded_by,
    )
```

#### 14.4.2 修改 `invoke_runtime_completion` 中的预算检查

**修改位置**: `packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py` (已有代码位置 ~1220-1230)

```python
# 原有代码（替换前）：
            estimated_cost = round(
                (input_tokens + output_tokens) * float(route_preview["candidateModels"][0]["costPer1k"]) / 1000.0,
                6,
            )
            _enforce_budget(task.budget, input_tokens=input_tokens, output_tokens=output_tokens, estimated_cost=estimated_cost)

# 替换为：
            estimated_cost = round(
                (input_tokens + output_tokens) * float(route_preview["candidateModels"][0]["costPer1k"]) / 1000.0,
                6,
            )
            
            # Pre-invocation budget check
            pre_check = _check_pre_invocation_budget(
                task.budget,
                estimated_input_tokens=input_tokens,
                estimated_output_tokens=output_tokens,
                estimated_cost=estimated_cost,
            )
            if not pre_check.check_passed:
                raise ValueError(f"Pre-invocation budget check failed: {pre_check.reason}")
            
            # Store pre-check result in request for downstream tracking
            request["_budgetCheckResult"] = pre_check.model_dump(by_alias=True, mode="json")
```

#### 14.4.3 修改工具循环中的累积成本检查

**修改位置**: `packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py` (已有代码位置 ~1000-1020)

```python
# 原有代码（替换前）：
                _merge_usage(usage_totals, dict(result.get("usage") or {}))
                accumulated_cost += float(result.get("costUsed", 0.0) or 0.0)
                round_modes.append(str(result.get("mode") or "unknown"))
                tool_calls = [call for call in result.get("toolCalls") or [] if isinstance(call, dict) and call.get("name")]

# 替换为：
                _merge_usage(usage_totals, dict(result.get("usage") or {}))
                accumulated_cost += float(result.get("costUsed", 0.0) or 0.0)
                round_modes.append(str(result.get("mode") or "unknown"))
                tool_calls = [call for call in result.get("toolCalls") or [] if isinstance(call, dict) and call.get("name")]
                
                # Hard fail if cost budget exceeded after this round
                if task.budget.cost_budget_total is not None:
                    if accumulated_cost > task.budget.cost_budget_total:
                        # Log and trigger hard fail
                        _logger.warning(
                            "Cost budget exceeded during tool loop: "
                            "accumulated=%.6f, limit=%.6f, round=%d, invocation=%s",
                            accumulated_cost,
                            task.budget.cost_budget_total,
                            round_index,
                            invocation.id,
                        )
                        # Force tool loop termination
                        final_result = {
                            "mode": "cost-budget-exceeded",
                            "finishReason": "cost-budget-hard-fail",
                            "outputText": (
                                f"Task execution halted: accumulated cost ({accumulated_cost:.6f}) "
                                f"exceeded budget ({task.budget.cost_budget_total:.6f})."
                            ),
                            "toolCalls": [],
                        }
                        break
```

#### 14.4.4 修改返回结构中的预算判定结果

**修改位置**: `packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py` (在最终返回结果时)

```python
# 在 invoke_runtime_completion 的返回字典中添加 budgetCheckResult 字段
            return {
                "status": "completed",
                "invocation": invocation.model_dump(by_alias=True, mode="json"),
                "usage": {
                    "inputTokens": usage_totals["inputTokens"],
                    "outputTokens": usage_totals["outputTokens"],
                    "totalTokens": usage_totals["totalTokens"],
                    "cacheHitInputTokens": usage_totals.get("cacheHitInputTokens", 0),
                    "cacheWriteInputTokens": usage_totals.get("cacheWriteInputTokens", 0),
                    "reasoningTokens": usage_totals.get("reasoningTokens", 0),
                },
                "costUsed": round(accumulated_cost, 6),
                "budgetCheckResult": pre_check.model_dump(by_alias=True, mode="json"),  # NEW
                "assistantText": str(final_result.get("outputText") or ""),
                "toolExecutions": [dict(execution) for execution in tool_executions],
                "finishReason": final_result.get("finishReason"),
                # ... other fields ...
            }
```

### 14.5 集成点说明

1. **预算检查时机**:
   - Pre-check: 在 LLM 调用前执行，预检成本/token 充分性
   - In-loop check: 每轮工具调用后检查累积成本
   - Post-check: 调用完成后检查实际用量是否超标

2. **错误处理链**:
   ```
   预检失败 → ValueError 异常 → 外层 catch → 返回 failed 状态
   工具循环中超预算 → hard fail → 生成截断结果 → 返回 completed 状态
   后检失败 → 设置 budget_overrun 标记 → 返回 failed 状态
   ```

3. **关键参与方**:
   - `invoke_runtime_completion()`: 主入口，执行预检和后检
   - `execution_loop.py` 中的 `execute_agent_task()`: 消费返回结果的 budgetCheckResult
   - `snapshot.py`: 保存预算违规信息供恢复使用

### 14.6 测试断言建议

```python
def test_pre_invocation_budget_check_blocks_insufficient_cost() -> None:
    """Test that pre-check detects insufficient cost budget."""
    budget = BudgetState(cost_budget_total=1.0, cost_budget_used=0.8)
    result = _check_pre_invocation_budget(
        budget,
        estimated_input_tokens=1000,
        estimated_output_tokens=500,
        estimated_cost=0.5,  # 0.8 + 0.5 > 1.0
    )
    assert result.check_passed is False
    assert "cost budget" in (result.reason or "").lower()


def test_pre_invocation_budget_check_passes_sufficient_budget() -> None:
    """Test that pre-check passes with sufficient budget."""
    budget = BudgetState(cost_budget_total=1.0, cost_budget_used=0.2)
    result = _check_pre_invocation_budget(
        budget,
        estimated_input_tokens=1000,
        estimated_output_tokens=500,
        estimated_cost=0.3,  # 0.2 + 0.3 <= 1.0
    )
    assert result.check_passed is True
    assert result.reason is None


def test_post_invocation_budget_overrun_detected() -> None:
    """Test that post-check detects cost overrun."""
    budget = BudgetState(cost_budget_total=1.0, cost_budget_used=0.8)
    result = _check_post_invocation_budget(
        budget,
        input_tokens_used=1000,
        output_tokens_used=500,
        cost_used=0.3,  # 0.8 + 0.3 > 1.0
    )
    assert result.is_overrun is True
    assert result.violation_type == "cost"
    assert result.cost_exceeded_by > 0.0


def test_hard_fail_terminates_tool_loop_on_cost_budget_exceeded() -> None:
    """Test that tool loop hard-fails when accumulated cost exceeds budget."""
    # This requires integration test with mock LLM provider
    # Verify that when accumulated_cost > budget.cost_budget_total:
    # 1. Tool loop breaks immediately
    # 2. final_result.finishReason == "cost-budget-hard-fail"
    # 3. No more tool calls are executed
    pass
```

---

## 任务 15 (C3): 工具调用执行回合

### 15.1 目标与背景

工具失败隔离，不污染主状态机；失败转可恢复 pending action。关键承诺：
- 每个工具执行异常捕获后记录 failure 信息
- 工具 failure 不导致整个工具回合失败
- 返回 error result 而非抛异常
- tool_failures 列表记录所有失败的工具调用，供后续分析

### 15.2 新增数据类/模型定义

**文件**: `packages/python-sdk/src/yggdrasil_sdk/contracts.py`

在 `BudgetOverrunResult` 之后添加：

```python
class ToolExecutionFailure(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    tool_call_id: str = Field(alias="toolCallId")
    tool_name: str = Field(alias="toolName")
    error_type: str = Field(alias="errorType")  # e.g., "timeout", "permission", "execution", "validation"
    error_message: str = Field(alias="errorMessage")
    arguments: dict[str, Any] = Field(default_factory=dict)
    retry_count: int = Field(alias="retryCount", default=0)
    is_retryable: bool = Field(alias="isRetryable", default=False)
    timestamp: str = Field(default_factory=utc_now)
    round_index: int = Field(alias="roundIndex")


class ToolExecutionResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    tool_call_id: str = Field(alias="toolCallId")
    tool_name: str = Field(alias="toolName")
    success: bool
    result: dict[str, Any] | None = None
    error: ToolExecutionFailure | None = None
    execution_time_ms: float = Field(alias="executionTimeMs")
```

### 15.3 函数签名变更说明

#### 15.3.1 新增工具执行包装函数

**文件**: `packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py`

在 tool_result_to_message_content 函数之后添加：

```python
def _execute_tool_with_isolation(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    task: Any,
    run: Any,
    root_mount: dict[str, Any],
    current_context: list[dict[str, Any]],
    tool_call_id: str,
    round_index: int,
    max_retries: int = _MAX_TOOL_RETRIES,
) -> dict[str, Any]:
    """
    Execute a tool call with exception isolation.
    
    Returns a dict containing:
    - success: bool
    - result: dict if success=True
    - error: ToolExecutionFailure dict if success=False
    - execution_time_ms: float
    
    Never raises exception for tool execution errors.
    """
    execution_started_at = perf_counter()
    retry_count = 0
    last_error = None
    is_retryable = False
    error_type = "unknown"
    
    while retry_count <= max_retries:
        try:
            execution = execute_registered_tool(
                tool_name,
                arguments,
                task=task,
                run=run,
                root_mount=root_mount,
                current_context=current_context,
            )
            execution_time_ms = round((perf_counter() - execution_started_at) * 1000.0, 2)
            
            return {
                "toolCallId": tool_call_id,
                "toolName": tool_name,
                "success": True,
                "result": execution,
                "error": None,
                "executionTimeMs": execution_time_ms,
                "retryCount": retry_count,
            }
        except TimeoutError as exc:
            last_error = str(exc)
            error_type = "timeout"
            is_retryable = True
            retry_count += 1
            if retry_count <= max_retries:
                _logger.debug(
                    "Tool execution timeout (retryable), tool=%s, call_id=%s, retry=%d/%d",
                    tool_name, tool_call_id, retry_count, max_retries
                )
                continue
        except PermissionError as exc:
            last_error = str(exc)
            error_type = "permission"
            is_retryable = False
            break
        except ValueError as exc:
            last_error = str(exc)
            error_type = "validation"
            is_retryable = False
            break
        except Exception as exc:
            last_error = str(exc)
            error_type = "execution"
            is_retryable = isinstance(exc, (ConnectionError, RuntimeError))
            retry_count += 1
            if is_retryable and retry_count <= max_retries:
                _logger.debug(
                    "Tool execution error (retryable), tool=%s, call_id=%s, error=%s, retry=%d/%d",
                    tool_name, tool_call_id, error_type, retry_count, max_retries
                )
                continue
            break
    
    execution_time_ms = round((perf_counter() - execution_started_at) * 1000.0, 2)
    
    failure = {
        "toolCallId": tool_call_id,
        "toolName": tool_name,
        "errorType": error_type,
        "errorMessage": last_error or "Unknown error",
        "arguments": arguments,
        "retryCount": retry_count,
        "isRetryable": is_retryable,
        "roundIndex": round_index,
    }
    
    return {
        "toolCallId": tool_call_id,
        "toolName": tool_name,
        "success": False,
        "result": None,
        "error": failure,
        "executionTimeMs": execution_time_ms,
        "retryCount": retry_count,
    }
```

#### 15.3.2 修改工具循环中的执行逻辑

**修改位置**: `packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py` (已有工具执行循环，~1060-1090)

```python
# 原有代码（替换前）：
                assistant_tool_calls = _assistant_tool_calls_payload(tool_calls, round_index)
                conversation_messages.append(_assistant_tool_round_message(result, assistant_tool_calls))
                for call in tool_calls:
                    tool_call_id = str(call.get("id") or new_id("toolcall", call.get("name"), round_index))
                    try:
                        execution = execute_registered_tool(
                            str(call.get("name")),
                            call.get("arguments") if isinstance(call.get("arguments"), dict) else {},
                            task=task,
                            run=run,
                            root_mount=root_mount,
                            current_context=current_context,
                        )
                        execution["success"] = True
                    except Exception as exc:
                        execution = {
                            "tool": {"name": str(call.get("name"))},
                            "arguments": call.get("arguments") if isinstance(call.get("arguments"), dict) else {},
                            "result": {"status": "error", "error": str(exc)},
                            "success": False,
                        }
                    execution["toolCallId"] = tool_call_id
                    tool_executions.append(execution)
                    conversation_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "name": str(call.get("name")),
                            "content": tool_result_to_message_content(execution),
                        }
                    )

# 替换为：
                assistant_tool_calls = _assistant_tool_calls_payload(tool_calls, round_index)
                conversation_messages.append(_assistant_tool_round_message(result, assistant_tool_calls))
                
                # Track tool failures for this round
                round_tool_failures = []
                
                for call in tool_calls:
                    tool_call_id = str(call.get("id") or new_id("toolcall", call.get("name"), round_index))
                    
                    # Execute with isolation - never raises exception
                    execution = _execute_tool_with_isolation(
                        str(call.get("name")),
                        call.get("arguments") if isinstance(call.get("arguments"), dict) else {},
                        task=task,
                        run=run,
                        root_mount=root_mount,
                        current_context=current_context,
                        tool_call_id=tool_call_id,
                        round_index=round_index,
                    )
                    
                    # Track failures for analysis
                    if not execution["success"] and execution.get("error") is not None:
                        round_tool_failures.append(execution["error"])
                    
                    tool_executions.append(execution)
                    
                    # Convert to message for conversation
                    message_content = tool_result_to_message_content(execution)
                    conversation_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "name": str(call.get("name")),
                            "content": message_content,
                        }
                    )
                
                # Store round failures for later analysis
                if round_tool_failures:
                    round_summaries[-1]["toolFailures"] = [
                        {
                            "toolName": f["toolName"],
                            "errorType": f["errorType"],
                            "isRetryable": f["isRetryable"],
                        }
                        for f in round_tool_failures
                    ]
```

### 15.4 集成点说明

1. **工具执行层**:
   - `_execute_tool_with_isolation()`: 新增包装函数，提供异常隔离
   - 返回统一的结构化结果，不抛异常

2. **消息构建**:
   - 失败的工具调用也加入 conversation_messages
   - LLM 可在下一轮看到失败信息，决定重试或跳过

3. **指标记录**:
   - round_summaries 中新增 toolFailures 字段
   - 支持后续分析和调试

4. **恢复流程**:
   - snapshot 中保存 tool_failures 列表
   - 恢复时可重放失败工具调用或跳过

### 15.5 测试断言建议

```python
def test_tool_execution_failure_isolated_and_returns_error_result() -> None:
    """Test that tool execution failures are isolated and don't break loop."""
    # Mock execute_registered_tool to raise exception
    # Verify that:
    # 1. _execute_tool_with_isolation returns dict with success=False
    # 2. error field contains ToolExecutionFailure details
    # 3. No exception is raised
    pass


def test_tool_execution_with_retryable_error_retries_up_to_max() -> None:
    """Test that retryable errors (timeout, connection) are retried."""
    # Mock execute_registered_tool to raise TimeoutError first 2 times, succeed on 3rd
    # Verify that:
    # 1. Tool is called 3 times total (1 initial + 2 retries)
    # 2. Final result has success=True
    # 3. retryCount field shows 2
    pass


def test_tool_execution_with_non_retryable_error_fails_immediately() -> None:
    """Test that non-retryable errors fail immediately without retries."""
    # Mock execute_registered_tool to raise PermissionError
    # Verify that:
    # 1. Tool is called 1 time only
    # 2. Final result has success=False
    # 3. errorType == "permission"
    # 4. isRetryable == False
    pass


def test_tool_failures_recorded_in_round_summary() -> None:
    """Test that tool failures are recorded in round_summaries."""
    # Execute with 1 success + 1 failure
    # Verify that round_summaries[-1]["toolFailures"] contains failure entry
    pass


def test_failed_tool_result_added_to_conversation_messages() -> None:
    """Test that failed tool results are added to conversation for LLM."""
    # Execute with tool failure
    # Verify that conversation_messages includes:
    # - role: "tool"
    # - content contains error information
    pass
```

---

## 任务 16 (C6): 记录 runtime metrics

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

## 任务 17 (C7): 安全停止与可恢复断点

### 17.1 目标与背景

保存 pending tool calls 与 savepoint，恢复时原位续跑。关键承诺：
- 在 SafeShutdownInterrupt 发生时，snapshot 中保存 checksum 校验和
- checksum = sha256(json.dumps(pending_action, sort_keys=True))
- 恢复时校验 checksum 防止数据污染
- 支持 pending action 原位恢复，不丢失执行语义

### 17.2 新增数据类/模型定义

**文件**: `packages/python-sdk/src/yggdrasil_sdk/contracts.py`

在 `RuntimeMetricsArtifact` 之后添加：

```python
class PendingActionSnapshot(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    action_type: Literal["tool-call", "memory-write", "external-action"] = Field(alias="actionType")
    action_payload: dict[str, Any] = Field(alias="actionPayload")
    
    # Checksum for integrity verification
    checksum: str  # sha256 hex digest
    checksum_algorithm: str = Field(default="sha256", alias="checksumAlgorithm")
    
    # Recovery metadata
    checksum_verified_at: str | None = Field(default=None, alias="checksumVerifiedAt")
    checksum_failed: bool = Field(default=False, alias="checksumFailed")
    failure_reason: str | None = Field(default=None, alias="failureReason")


class SafeStopSnapshot(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    task_id: str = Field(alias="taskId")
    agent_run_id: str = Field(alias="agentRunId")
    invocation_id: str = Field(alias="invocationId")
    round_index: int = Field(alias="roundIndex")
    
    # Pending state
    pending_tool_calls: list[dict[str, Any]] = Field(alias="pendingToolCalls")
    pending_tool_call_count: int = Field(alias="pendingToolCallCount")
    
    # Conversation history
    conversation_messages: list[dict[str, Any]] = Field(alias="conversationMessages")
    assistant_message: dict[str, Any] | None = Field(default=None, alias="assistantMessage")
    
    # Action snapshots with checksums
    pending_action_snapshots: list[PendingActionSnapshot] = Field(
        alias="pendingActionSnapshots"
    )
    
    # Runtime state
    usage_totals: dict[str, int] = Field(alias="usageTotals")
    accumulated_cost: float = Field(alias="accumulatedCost")
    round_summaries: list[dict[str, Any]] = Field(alias="roundSummaries")
    round_modes: list[str] = Field(alias="roundModes")
    
    # Recovery info
    safe_stop_reason: str = Field(alias="safeStopReason")  # e.g., "pause-requested", "shutdown-signal"
    can_resume: bool = Field(alias="canResume", default=True)
    resume_token: str = Field(alias="resumeToken")
    
    # Timestamps
    created_at: str = Field(default_factory=utc_now)
    last_verified_at: str | None = Field(default=None, alias="lastVerifiedAt")
```

### 17.3 函数签名变更说明

#### 17.3.1 新增校验和计算函数

**文件**: `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py`

在文件顶部添加：

```python
from hashlib import sha256
import json


def _compute_action_checksum(action_payload: dict[str, Any]) -> str:
    """
    Compute SHA256 checksum of action payload.
    
    Args:
        action_payload: Action data to checksum
    
    Returns:
        Hex digest of SHA256 hash
    """
    payload_json = json.dumps(action_payload, sort_keys=True, separators=(",", ":"))
    return sha256(payload_json.encode("utf-8")).hexdigest()


def _verify_action_checksum(
    action: PendingActionSnapshot,
    expected_checksum: str | None = None,
) -> tuple[bool, str | None]:
    """
    Verify action checksum.
    
    Args:
        action: Action to verify
        expected_checksum: Optional expected checksum. If None, use action.checksum
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if expected_checksum is None:
        expected_checksum = action.checksum
    
    computed_checksum = _compute_action_checksum(action.action_payload)
    
    if computed_checksum == expected_checksum:
        return True, None
    
    return False, (
        f"Checksum mismatch: expected {expected_checksum}, got {computed_checksum}"
    )
```

#### 17.3.2 新增 SafeStop 快照构建函数

**文件**: `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py`

```python
def build_safe_stop_snapshot(
    task_id: str,
    *,
    agent_run_id: str,
    invocation_id: str,
    round_index: int,
    pending_tool_calls: list[dict[str, Any]],
    conversation_messages: list[dict[str, Any]],
    assistant_message: dict[str, Any] | None,
    usage_totals: dict[str, int],
    accumulated_cost: float,
    round_summaries: list[dict[str, Any]],
    round_modes: list[str],
    safe_stop_reason: str = "pause-requested",
) -> SafeStopSnapshot:
    """
    Build a safe-stop snapshot with checksums for all pending actions.
    
    Args:
        task_id: Task ID
        agent_run_id: Agent run ID
        invocation_id: LLM invocation ID
        round_index: Current tool round index
        pending_tool_calls: Pending tool calls to preserve
        conversation_messages: Full conversation history
        assistant_message: Last assistant message
        usage_totals: Token usage totals
        accumulated_cost: Cost used so far
        round_summaries: Round execution summaries
        round_modes: Round mode per round
        safe_stop_reason: Reason for safe stop
    
    Returns:
        SafeStopSnapshot with checksums computed for each pending action
    """
    resume_token = new_id("resume-token", task_id, agent_run_id, invocation_id, stable=False)
    
    # Build pending action snapshots with checksums
    pending_actions = []
    for idx, tool_call in enumerate(pending_tool_calls):
        checksum = _compute_action_checksum(tool_call)
        action = PendingActionSnapshot(
            id=new_id("pending-action", task_id, idx, stable=False),
            action_type="tool-call",
            action_payload=tool_call,
            checksum=checksum,
            checksum_algorithm="sha256",
        )
        pending_actions.append(action)
    
    return SafeStopSnapshot(
        id=new_id("safe-stop-snapshot", task_id, agent_run_id, invocation_id, stable=False),
        task_id=task_id,
        agent_run_id=agent_run_id,
        invocation_id=invocation_id,
        round_index=round_index,
        pending_tool_calls=pending_tool_calls,
        pending_tool_call_count=len(pending_tool_calls),
        conversation_messages=conversation_messages,
        assistant_message=assistant_message,
        pending_action_snapshots=pending_actions,
        usage_totals=usage_totals,
        accumulated_cost=accumulated_cost,
        round_summaries=round_summaries,
        round_modes=round_modes,
        safe_stop_reason=safe_stop_reason,
        can_resume=True,
        resume_token=resume_token,
    )
```

#### 17.3.3 新增恢复验证函数

**文件**: `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py`

```python
def verify_safe_stop_snapshot(
    snapshot: SafeStopSnapshot,
    strict: bool = True,
) -> dict[str, Any]:
    """
    Verify all checksums in a safe-stop snapshot.
    
    Args:
        snapshot: Snapshot to verify
        strict: If True, fail on any checksum mismatch. If False, log but allow.
    
    Returns:
        Verification result dict:
        {
            "valid": bool,
            "checked_count": int,
            "failed_count": int,
            "errors": [str],
            "verified_at": str,
        }
    """
    errors = []
    checked_count = 0
    failed_count = 0
    
    for action in snapshot.pending_action_snapshots:
        checked_count += 1
        is_valid, error_msg = _verify_action_checksum(action)
        
        if not is_valid:
            failed_count += 1
            errors.append(error_msg or "Unknown verification error")
            if strict:
                action.checksum_failed = True
                action.failure_reason = error_msg
    
    is_valid = failed_count == 0
    
    result = {
        "valid": is_valid,
        "checked_count": checked_count,
        "failed_count": failed_count,
        "errors": errors,
        "verified_at": utc_now(),
    }
    
    if not is_valid and strict:
        raise ValueError(f"Safe-stop snapshot verification failed: {'; '.join(errors)}")
    
    return result
```

#### 17.3.4 修改 SafeShutdownInterrupt 处理流程

**修改位置**: `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py` (在处理 SafeShutdownInterrupt 的位置)

```python
# 原有代码（替换前）：
            except SafeShutdownInterrupt as _shutdown_exc:
                _logger.info(
                    "Safe shutdown requested during tool execution for task %s (invocation %s, round %d, %d pending tool calls). Saving checkpoint.",
                    task_id,
                    _shutdown_exc.invocation_id,
                    _shutdown_exc.round_index,
                    len(_shutdown_exc.pending_tool_calls),
                )
                snap_result = save_pending_tool_calls_snapshot(
                    task_id,
                    agent_run_id=run.id,
                    pending_tool_calls=_shutdown_exc.pending_tool_calls,
                    conversation_messages=_shutdown_exc.conversation_messages,
                    assistant_message=_shutdown_exc.assistant_message,
                    invocation_id=_shutdown_exc.invocation_id,
                    round_index=_shutdown_exc.round_index,
                    usage_totals=_shutdown_exc.usage_totals,
                    accumulated_cost=_shutdown_exc.accumulated_cost,
                    round_summaries=_shutdown_exc.round_summaries,
                    round_modes=_shutdown_exc.round_modes,
                    current_context_state=effective_context,
                    root_mount_preview=root_mount,
                    app_id=task.app_id,
                    project_id=task.project_id,
                    branch_id=task.branch_id,
                    lock_already_held=True,
                    session_override=session,
                    request_state=_build_restart_request_state(
                        request,
                        request.get("runtimeMetrics") if isinstance(request.get("runtimeMetrics"), dict) else {},
                    ),
                )

# 替换为：
            except SafeShutdownInterrupt as _shutdown_exc:
                _logger.info(
                    "Safe shutdown requested during tool execution for task %s (invocation %s, round %d, %d pending tool calls). "
                    "Building and verifying safe-stop snapshot.",
                    task_id,
                    _shutdown_exc.invocation_id,
                    _shutdown_exc.round_index,
                    len(_shutdown_exc.pending_tool_calls),
                )
                
                # Build safe-stop snapshot with checksums
                safe_stop_snapshot = build_safe_stop_snapshot(
                    task_id,
                    agent_run_id=run.id,
                    invocation_id=_shutdown_exc.invocation_id,
                    round_index=_shutdown_exc.round_index,
                    pending_tool_calls=_shutdown_exc.pending_tool_calls,
                    conversation_messages=_shutdown_exc.conversation_messages,
                    assistant_message=_shutdown_exc.assistant_message,
                    usage_totals=_shutdown_exc.usage_totals,
                    accumulated_cost=_shutdown_exc.accumulated_cost,
                    round_summaries=_shutdown_exc.round_summaries,
                    round_modes=_shutdown_exc.round_modes,
                    safe_stop_reason="pause-requested",
                )
                
                # Verify checksums before persisting
                verification_result = verify_safe_stop_snapshot(safe_stop_snapshot, strict=False)
                _logger.info(
                    "Safe-stop snapshot verification: checked=%d, failed=%d, valid=%s",
                    verification_result["checked_count"],
                    verification_result["failed_count"],
                    verification_result["valid"],
                )
                
                # Persist the snapshot
                snap_result = save_pending_tool_calls_snapshot(
                    task_id,
                    agent_run_id=run.id,
                    pending_tool_calls=_shutdown_exc.pending_tool_calls,
                    conversation_messages=_shutdown_exc.conversation_messages,
                    assistant_message=_shutdown_exc.assistant_message,
                    invocation_id=_shutdown_exc.invocation_id,
                    round_index=_shutdown_exc.round_index,
                    usage_totals=_shutdown_exc.usage_totals,
                    accumulated_cost=_shutdown_exc.accumulated_cost,
                    round_summaries=_shutdown_exc.round_summaries,
                    round_modes=_shutdown_exc.round_modes,
                    current_context_state=effective_context,
                    root_mount_preview=root_mount,
                    app_id=task.app_id,
                    project_id=task.project_id,
                    branch_id=task.branch_id,
                    lock_already_held=True,
                    session_override=session,
                    request_state=_build_restart_request_state(
                        request,
                        request.get("runtimeMetrics") if isinstance(request.get("runtimeMetrics"), dict) else {},
                    ),
                )
                
                # Add safe-stop snapshot reference to result
                snap_result["safeStopSnapshot"] = safe_stop_snapshot.model_dump(by_alias=True, mode="json")
                snap_result["checksumVerification"] = verification_result
```

### 17.4 集成点说明

1. **SafeStop 触发**:
   - SafeShutdownInterrupt 异常捕获
   - 调用 build_safe_stop_snapshot 构建包含校验和的快照

2. **校验和计算时机**:
   - 保存前：为每个 pending action 计算 SHA256
   - 恢复前：重新验证校验和，检测数据污染

3. **恢复流程**:
   - 加载快照时调用 verify_safe_stop_snapshot
   - 若验证失败：记录 failure_reason，可选拒绝恢复
   - 若验证通过：恢复 pending_tool_calls，原位续跑

4. **数据一致性保障**:
   - JSON 序列化时使用 sort_keys=True 保证确定性
   - Checksum 作为数据完整性证明

### 17.5 测试断言建议

```python
def test_safe_stop_snapshot_computes_checksums() -> None:
    """Test that safe-stop snapshot computes checksums for pending actions."""
    pending_tool_calls = [
        {"id": "call-1", "name": "search", "arguments": {"query": "test"}},
        {"id": "call-2", "name": "summarize", "arguments": {"text": "content"}},
    ]
    
    snapshot = build_safe_stop_snapshot(
        "task-123",
        agent_run_id="run-1",
        invocation_id="inv-1",
        round_index=1,
        pending_tool_calls=pending_tool_calls,
        conversation_messages=[],
        assistant_message=None,
        usage_totals={"inputTokens": 100, "outputTokens": 50},
        accumulated_cost=0.01,
        round_summaries=[],
        round_modes=["live"],
    )
    
    # Verify all actions have checksums
    assert len(snapshot.pending_action_snapshots) == 2
    for action in snapshot.pending_action_snapshots:
        assert action.checksum is not None
        assert len(action.checksum) == 64  # SHA256 hex is 64 chars


def test_checksum_verification_passes_for_intact_action() -> None:
    """Test that checksum verification passes for intact action."""
    action_payload = {"id": "call-1", "name": "search", "arguments": {"query": "test"}}
    checksum = _compute_action_checksum(action_payload)
    
    action = PendingActionSnapshot(
        id="action-1",
        action_type="tool-call",
        action_payload=action_payload,
        checksum=checksum,
    )
    
    is_valid, error_msg = _verify_action_checksum(action)
    assert is_valid is True
    assert error_msg is None


def test_checksum_verification_fails_for_corrupted_action() -> None:
    """Test that checksum verification fails for corrupted action."""
    action_payload = {"id": "call-1", "name": "search", "arguments": {"query": "test"}}
    checksum = _compute_action_checksum(action_payload)
    
    # Corrupt the payload after checksum computation
    corrupted_payload = {"id": "call-1", "name": "search", "arguments": {"query": "modified"}}
    
    action = PendingActionSnapshot(
        id="action-1",
        action_type="tool-call",
        action_payload=corrupted_payload,
        checksum=checksum,
    )
    
    is_valid, error_msg = _verify_action_checksum(action)
    assert is_valid is False
    assert "mismatch" in (error_msg or "").lower()


def test_safe_stop_snapshot_verification_strict_mode_raises() -> None:
    """Test that strict verification raises on checksum failure."""
    # Build snapshot with corrupted actions
    pending_tool_calls = [
        {"id": "call-1", "name": "search", "arguments": {"query": "test"}},
    ]
    
    snapshot = build_safe_stop_snapshot(
        "task-123",
        agent_run_id="run-1",
        invocation_id="inv-1",
        round_index=1,
        pending_tool_calls=pending_tool_calls,
        conversation_messages=[],
        assistant_message=None,
        usage_totals={},
        accumulated_cost=0.0,
        round_summaries=[],
        round_modes=[],
    )
    
    # Corrupt the payload
    snapshot.pending_action_snapshots[0].action_payload["arguments"]["query"] = "corrupted"
    
    # Strict verification should raise
    with pytest.raises(ValueError, match="verification failed"):
        verify_safe_stop_snapshot(snapshot, strict=True)


def test_safe_stop_snapshot_recovery_preserves_pending_actions() -> None:
    """Test that pending actions can be recovered from snapshot."""
    original_pending_calls = [
        {"id": "call-1", "name": "search", "arguments": {"query": "test"}},
        {"id": "call-2", "name": "read_file", "arguments": {"path": "/tmp/test.txt"}},
    ]
    
    snapshot = build_safe_stop_snapshot(
        "task-123",
        agent_run_id="run-1",
        invocation_id="inv-1",
        round_index=2,
        pending_tool_calls=original_pending_calls,
        conversation_messages=[],
        assistant_message=None,
        usage_totals={"inputTokens": 500},
        accumulated_cost=0.02,
        round_summaries=[],
        round_modes=["live"],
    )
    
    # Verify snapshot
    verification = verify_safe_stop_snapshot(snapshot, strict=True)
    assert verification["valid"] is True
    
    # Recover and verify
    recovered_calls = snapshot.pending_tool_calls
    assert len(recovered_calls) == 2
    assert recovered_calls[0]["id"] == "call-1"
    assert recovered_calls[1]["name"] == "read_file"
```

---

## 集成与验收标准

### 四任务集成清单

1. **任务14 + 任务15**:
   - 预检通过后进入工具循环
   - 工具失败隔离，不导致循环断裂
   - 工具失败后检查是否触发硬预算超限

2. **任务14 + 任务16**:
   - 预算检查结果包含在 metrics snapshot
   - 成本超预算标记在指标中记录

3. **任务15 + 任务17**:
   - 工具执行失败可转为 pending action
   - 恢复时能重放失败的工具调用

4. **任务16 + 任务17**:
   - SafeStop 时保存的 metrics snapshot 包含累积指标
   - 恢复后继续累积，保证单调性

### 验收门槛

| 项目 | 标准 | 验证方法 |
|-----|------|--------|
| 任务14 预检准确性 | 预检 vs 实际成本误差 < 5% | 对比 pre_check 与 actual_cost |
| 任务14 硬fail 时机 | accumulated_cost 超预算时立即停止工具循环 | 单测验证循环终止逻辑 |
| 任务15 隔离完整性 | 工具异常不导致主循环异常 | 覆盖 timeout/permission/validation 三类错误 |
| 任务15 失败追踪 | tool_failures 列表记录完整 | 验证 round_summary.toolFailures 数据 |
| 任务16 指标一致性 | 窗口间指标单调递增 | 跨窗口对比 cumulative 指标 |
| 任务16 导出完整性 | 所有标准字段都保存 | 验证 RuntimeMetricsSnapshot 所有字段非空 |
| 任务17 校验和准确性 | 恢复前后 checksum 一致 | 单测验证 verify 函数 |
| 任务17 恢复可用性 | SafeStop 后可完全恢复到中断点 | 集成测试：stop → resume → 继续执行 |

---

## 后续操作指南

### 实现顺序建议

1. **第一阶段**（1-2天）:
   - 任务14: 新增常量、数据类、预检函数
   - 任务16: 新增 RuntimeMetricsSnapshot 数据类

2. **第二阶段**（2-3天）:
   - 任务14: 集成预检到 invoke_runtime_completion
   - 任务15: 新增 _execute_tool_with_isolation 函数

3. **第三阶段**（1-2天）:
   - 任务16: 实现 _build_runtime_metrics_snapshot、_persist_runtime_metrics_artifact
   - 任务17: 新增校验和计算、SafeStop 快照函数

4. **第四阶段**（1-2天）:
   - 集成所有四项任务
   - 编写集成测试
   - 验证验收门槛

### 关键测试用例

```
P2_Test_Suite:
  ├─ test_budget_governance
  │  ├─ test_pre_check_blocks_insufficient_budget
  │  ├─ test_hard_fail_on_cost_exceeded
  │  └─ test_post_check_detects_overrun
  ├─ test_tool_isolation
  │  ├─ test_tool_failure_not_breaking_loop
  │  ├─ test_retryable_errors_retry
  │  └─ test_non_retryable_errors_fail_fast
  ├─ test_metrics_recording
  │  ├─ test_snapshot_completeness
  │  ├─ test_metrics_monotonicity
  │  └─ test_artifact_persistence
  └─ test_safe_stop
     ├─ test_checksum_computation
     ├─ test_checksum_verification
     └─ test_recovery_from_safe_stop
```

### 依赖与冲突检查

- ✅ 不与 P1 任务冲突（P1 已冻结）
- ✅ 向后兼容现有 API（新增字段都有默认值）
- ✅ 不改动现有函数签名（新增包装函数）
- ✅ 日志级别保持 INFO（现有风格）

---

## 文档更新清单

- [ ] 更新 docs/DIRECTORY_REFERENCE.md 新增文件位置
- [ ] 更新 docs/runtime-domain-data-spec-v0.1.md 新增数据类
- [ ] 生成 P2_IMPLEMENTATION_CHECKLIST.md（任务细分）
- [ ] 更新 docs/P1_TEST_COVERAGE_INVENTORY.md 增加 P2 测试计划


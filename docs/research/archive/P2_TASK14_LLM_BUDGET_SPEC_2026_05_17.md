# P2 任务14实现规范：LLM调用与预算治理（2026-05-17）

来源：从总规范文档按任务拆分，保持原始代码片段与断言建议。

---

# 任务 14 (C2): LLM 调用与预算治理

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


# P2 任务15实现规范：工具调用执行回合（2026-05-17）

来源：从总规范文档按任务拆分，保持原始代码片段与断言建议。

---

# 任务 15 (C3): 工具调用执行回合

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


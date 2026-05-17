# P2 任务14-17 文件现状审计报告 (2026-05-17)

## 执行摘要

对P2任务（任务14-17）涉及的核心文件进行了系统性代码审计。涵盖5大关键检查点，共30个具体实现方面。**整体进度: 完整实现 + 部分差距**

---

## 核心检查点审计表

| 检查点 | 子项 | 当前状态 | 缺失功能 | 实现位置 | 建议 |
|-------|------|--------|--------|---------|------|
| **1. Cost/Token预算检查** | 预算检查逻辑 | ✅ 存在 | - | llm_runtime.py L161-162 | 已正确计算remaining budget |
| | 超预算处理 | ⚠️ 部分 | hard fail边界不明确 | execution_loop.py L1224-1233 | 需补充成本超限hard fail逻辑 |
| | Invocation结果记录 | ✅ 存在 | - | llm_runtime.py L1177-1189 | 已记录token和cost使用情况 |
| | 预算恢复状态 | ✅ 存在 | - | snapshot.py L63-67 | 使用deepcopy保持contract稳定 |
| **2. 工具调用执行** | tool_calls提取 | ✅ 存在 | - | llm_runtime.py L1079-1081 | 正确过滤有效tool_calls |
| | tool_calls执行 | ✅ 存在 | - | llm_runtime.py L1104-1118 | 使用execute_registered_tool |
| | tool_failure隔离 | ✅ 存在 | - | llm_runtime.py L1114-1118 | 异常捕获+failure记录 |
| | pending_action转换 | ✅ 存在 | 恢复流程不完整 | execution_loop.py L1017-1022 | 需补充pending_action处理逻辑 |
| | 消息转换 | ✅ 存在 | - | llm_runtime.py L1119-1122 | tool role message正确构建 |
| **3. 工具执行Trace** | tool execution trace | ✅ 存在 | trace格式无标准 | llm_runtime.py L1112-1122 | 需增强trace metadata记录 |
| | tool failure处理 | ✅ 存在 | - | llm_runtime.py L1114-1118 | success flag正确标记 |
| | execution_summary | ✅ 存在 | - | llm_runtime.py L435-442 | 提取了tool/status/result信息 |
| **4. Runtime Metrics** | metrics初始化 | ✅ 存在 | - | execution_loop.py L76-120 | windowIndex/restartCount已初始化 |
| | window计数 | ✅ 存在 | - | execution_loop.py L97-99 | windowIndex从request正确解析 |
| | restart计数 | ✅ 存在 | - | execution_loop.py L100-102 | restartCount递增实现完整 |
| | token统计 | ✅ 存在 | - | execution_loop.py L103-107 | cumulativeWindowSpanTokens追踪 |
| | compression计数 | ✅ 存在 | 递增逻辑缺失 | execution_loop.py L1401 | 已实现递增但缺少完整应用场景 |
| | context window判定 | ✅ 存在 | - | execution_loop.py L126-136 | 三层判定逻辑完整 |
| **5. Safe-Stop机制** | activeToolCalls保存 | ✅ 存在 | - | snapshot.py L201, L230 | 参数正确建模 |
| | pending_actions恢复 | ✅ 存在 | 恢复流程验证不足 | execution_loop.py L1017-1020 | 需增强pending_actions验证 |
| | pending_tool_calls快照 | ✅ 存在 | - | snapshot.py L508-550 | save_pending_tool_calls_snapshot完整 |
| | savepoint机制 | ✅ 存在 | 可恢复性验证缺失 | snapshot.py L530-545 | 需补充snapshot可恢复性检验 |
| | CheckpointResume流程 | ✅ 存在 | - | llm_runtime.py L980-1001 | checkpoint-resume round正确处理 |
| | 安全停止打断点 | ✅ 存在 | - | llm_runtime.py L1099-1103 | SafeShutdownInterrupt清晰定义 |

---

## 具体位置引用

### 1. Cost/Token预算检查

**位置**: [packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py](packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py)

| 函数/代码块 | 行号 | 内容 | 状态 |
|-----------|------|------|-----|
| `_default_max_tokens` | L156-163 | token_budget_total检查 | ✅ |
| 预算check | L161-162 | `remaining = max(task.budget.token_budget_total - task.budget.token_budget_used, 64)` | ✅ 计算正确 |
| usage merge | L197-203 | `_merge_usage`合并token使用 | ✅ |
| cost记录 | L1078-1079 | `_merge_usage(usage_totals, ...)` + `accumulated_cost += ...` | ✅ |
| invocation更新 | L1177-1189 | `update_model_invocation`记录tokens和cost | ✅ |

**缺失**: Hard fail边界未定义 - 当cost超预算时应该hard stop，目前只有token预算检查

---

### 2. 工具调用执行逻辑

**位置A**: [packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py](packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py) L1079-1122

```
line 1079-1081: tool_calls提取和过滤
line 1104-1118: 工具执行循环（try-catch包裹）
line 1114-1118: 异常处理 - failure记录
line 1119-1122: tool结果消息构建
```

| 函数 | 行号 | 机制 | 验证 |
|-----|------|------|------|
| 工具提取 | 1079-1081 | 过滤有效tool_calls (包含name) | ✅ |
| 工具执行 | 1108-1112 | `execute_registered_tool(name, arguments, ...)` | ✅ |
| Failure处理 | 1114-1118 | exception捕获 → `{"success": False, "result": {"status": "error"}}` | ✅ |
| 消息桥接 | 1119-1122 | 构建role:tool的message | ✅ |

**缺失**: 
- tool_failure隔离后的retry边界不清晰 - 是否继续、是否更换工具不明确
- tool执行trace metadata不足 - 缺少execution timestamp、latency等

---

### 3. Pending Actions转换逻辑

**位置B**: [packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py](packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py) L1017-1022

```python
for pending_action in snapshot.pending_actions or []:
    if not isinstance(pending_action, dict):
        continue
    if pending_action.get("kind") not in {"pending-tool-calls", "window-restart"}:
        continue
    request_state = pending_action.get("requestState") if isinstance(pending_action.get("requestState"), dict) else {}
```

| 阶段 | 行号 | 验证 |
|-----|------|------|
| pending_action遍历 | 1017 | ✅ |
| 类型验证 | 1018-1020 | ✅ 过滤无效action |
| requestState恢复 | 1022 | ⚠️ 只提取，未应用 |

**缺失**: 
- requestState的应用逻辑不完整 - 提取后没有将其应用到request上
- pending_action验证不足 - 缺少checksum或版本验证机制

---

### 4. Runtime Metrics记录

**位置C**: [packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py](packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py) L76-136

#### 初始化 (L76-120)

```python
_runtime_metrics(task, request: dict[str, Any]) -> dict[str, Any]:
    # Line 97-99: windowIndex
    # Line 100-102: restartCount  
    # Line 103-107: cumulativeWindowSpanTokens
    # Line 108-110: carryForwardLossCount
    # Line 111-113: forcedWindowRestartBudget
    # Line 114-118: effectiveContextWindow/windowRestartRatio/windowRestartThreshold
    # Line 119-120: windowSpanTokens
```

| 指标 | 初始化行号 | 状态 | 说明 |
|-----|----------|------|------|
| windowIndex | 97-99 | ✅ | max(request.windowIndex, 1) |
| restartCount | 100-102 | ✅ | max(request.restartCount, 0) |
| cumulativeWindowSpanTokens | 103-107 | ✅ | 累积token数 |
| carryForwardLossCount | 108-110 | ✅ | 携带转移loss计数 |
| forcedWindowRestartBudget | 111-113 | ✅ | 预算递减 |
| windowRestartThreshold | 114-118 | ✅ | 三层计算逻辑 |

#### 更新与统计 (L1264-1401)

| 位置 | 操作 | 状态 |
|-----|------|------|
| L1264-1266 | 存储metrics到restart request | ✅ |
| L1289-1292 | 记录到carry-forward | ✅ |
| L1401 | compressionCount递增 | ✅ 但应用场景不明 |

**缺失**: 
- 没有metrics导出接口 - metrics只存储，未export到外部
- 没有metrics验证逻辑 - 无法检测metrics异常

---

### 5. Safe-Stop与可恢复机制

**位置D**: [packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py](packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py)

#### A. SafeShutdownInterrupt定义

[packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py](packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py) L64-86

```python
class SafeShutdownInterrupt(Exception):
    def __init__(
        self,
        *,
        pending_tool_calls: list[dict[str, Any]],  # ✅ 工具调用保存
        conversation_messages: list[dict[str, Any]],  # ✅ 对话历史保存
        invocation_id: str,  # ✅ invocation追踪
        round_index: int,  # ✅ 恢复点标记
        usage_totals: dict[str, int],  # ✅ 使用统计
        accumulated_cost: float,  # ✅ 成本累计
        round_summaries: list[dict[str, Any]],  # ✅ round摘要
        round_modes: list[str],  # ✅ round模式
        assistant_tool_calls_payload: list[dict[str, Any]],  # ✅ payload备份
        assistant_message: dict[str, Any] | None = None,  # ✅ assistant消息
    ) -> None:
```

**状态**: ✅ 完整 - 所有关键state都被保存

#### B. Pending Tool Calls快照保存

[packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py](packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py) L508-550

```python
def save_pending_tool_calls_snapshot(
    task_id: str,
    *,
    agent_run_id: str,
    pending_tool_calls: list[dict[str, Any]],  # 待执行工具
    conversation_messages: list[dict[str, Any]],  # 对话上下文
    assistant_message: dict[str, Any] | None,  # assistant消息
    invocation_id: str,  # invocation追踪
    round_index: int,  # round编号
    usage_totals: dict[str, int],  # token统计
    accumulated_cost: float,  # cost累计
    ...
) -> dict[str, Any]:
```

| 参数 | 行号 | 保存位置 | 状态 |
|-----|------|---------|------|
| pending_tool_calls | 514-515 | pending_action["toolCalls"] | ✅ |
| conversation_messages | 514-515 | pending_action["conversationMessages"] | ✅ |
| usage_totals | 516 | pending_action["usageTotals"] | ✅ |
| accumulated_cost | 517 | pending_action["accumulatedCost"] | ✅ |
| request_state | 519-520 | pending_action["requestState"] | ✅ |

**状态**: ✅ 完整

#### C. Pending Actions恢复流程

[packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py](packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py) L973-1001

```python
# Line 973-1001: 恢复流程
_resume_tool_calls: list[dict[str, Any]] | None = None
_resume_conversation_messages: list[dict[str, Any]] | None = None
_resume_assistant_message: dict[str, Any] | None = None
_resume_round_state: dict[str, Any] = {}

for _pending_action in list(request.get("pendingActions") or []):
    if isinstance(_pending_action, dict) and _pending_action.get("kind") == _PENDING_TOOL_CALLS_KIND:
        _resume_tool_calls = _pending_action.get("toolCalls") if isinstance(...) else None
        _resume_conversation_messages = _pending_action.get("conversationMessages") if isinstance(...) else None
        ...
```

| 恢复项 | 行号 | 验证 |
|------|------|------|
| tool_calls提取 | 979 | ✅ |
| conversation恢复 | 980 | ✅ |
| round_state恢复 | 981 | ✅ |
| 状态应用 | 987-1001 | ✅ 使用原值 |

**缺失**: 
- 没有恢复一致性检验 - 无法验证恢复后的state是否与保存时一致
- 没有恢复冲突处理 - 当request中已有某些state时的冲突处理

#### D. Checkpoint Resume流程

[packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py](packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py) L989-1001

```python
if _resume_tool_calls is not None:
    _resume_round_started_at = perf_counter()
    _execute_resumed_tool_calls(
        tool_calls=_resume_tool_calls,
        conversation_messages=conversation_messages,
        tool_executions=tool_executions,
        assistant_message=_resume_assistant_message,
        ...
    )
```

**状态**: ✅ - checkpoint resume round正确处理，标记为"checkpoint-resume"

#### E. Savepoint机制

[packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py](packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py) L20-30 (_build_restart_request_state)

```python
request_state = {
    key: deepcopy(request.get(key))
    for key in (
        "taskType", "runType", "currentFocus", "currentObjective", ...
    )
    if request.get(key) is not None
}
```

| 机制 | 实现 | 状态 |
|-----|------|------|
| Deep Copy | L26 `deepcopy(request.get(key))` | ✅ 避免引用问题 |
| Contract稳定性 | L46-47 | ✅ 保持空值consistency |
| Request state版本化 | L51-67 | ✅ 记录metrics版本 |

**状态**: ✅ - savepoint基础实现完整，但缺少checksum验证

---

## 缺失功能与实现建议

### 🔴 关键缺失 (P2必需)

#### 1. Hard Fail边界 - Cost超限处理
**问题**: 当accumulated_cost超过预定cost budget时，应该hard fail，但目前无此逻辑

**建议**: 
```python
# 在llm_runtime.py execute_main_agent中添加
COST_BUDGET_LIMIT = task.budget.cost_budget_total  # 假设存在此字段
if accumulated_cost > COST_BUDGET_LIMIT:
    final_result = {
        "mode": "fallback",
        "finishReason": "cost-budget-exceeded",
        "error": f"Cost budget exceeded: {accumulated_cost} > {COST_BUDGET_LIMIT}",
        "outputText": "Task terminated due to cost budget constraint.",
        ...
    }
    break  # 停止tool loop
```

**文件**: [packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py](packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py) L1078-1090

---

#### 2. Request State应用逻辑 - Pending Actions转换
**问题**: 在[execution_loop.py L1022](packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py#L1022)提取了requestState，但没有将其应用到当前request

**建议**:
```python
# 在execution_loop.py中补充应用逻辑
if "requestState" in pending_action and isinstance(pending_action["requestState"], dict):
    request_state = pending_action["requestState"]
    for key in ("windowRestartThreshold", "effectiveContextWindow", "windowRestartRatio"):
        if key in request_state and request.get(key) is None:
            request[key] = request_state[key]
```

**文件**: [packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py](packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py) L1017-1025

---

#### 3. Snapshot可恢复性验证 - Savepoint机制
**问题**: 保存pending_tool_calls_snapshot时没有验证其可恢复性

**建议**:
```python
# 在snapshot.py save_pending_tool_calls_snapshot中添加
snapshot_checksum = hashlib.sha256(
    json.dumps(pending_action, sort_keys=True).encode()
).hexdigest()
pending_action["checksum"] = snapshot_checksum
# 恢复时验证: 
saved_checksum = pending_action.get("checksum")
computed_checksum = hashlib.sha256(...).hexdigest()
if saved_checksum != computed_checksum:
    raise ValueError("Snapshot integrity check failed")
```

**文件**: [packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py](packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py) L508-550

---

### 🟡 重要缺失 (P2推荐)

#### 4. Tool Execution Trace增强
**现状**: 基本的execution记录存在，但metadata不足

**建议**: 补充以下metadata
```python
execution["trace"] = {
    "startedAt": time.time(),
    "latencyMs": latency_ms,
    "toolVersion": getattr(tool_spec, "version", "unknown"),
    "retryCount": retry_count,  # 当前缺失
    "fallbackUsed": bool(execution.get("fallbackResult")),
}
```

**文件**: [packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py](packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py) L1108-1122

---

#### 5. Runtime Metrics导出接口
**现状**: metrics被计算和存储，但无法查询

**建议**: 添加导出接口
```python
# 在执行结束时导出metrics
runtime_metrics_export = {
    "windowIndex": runtime_metrics["windowIndex"],
    "totalRestarts": runtime_metrics["restartCount"],
    "totalTokens": sum(usage_totals.values()),
    "totalCost": accumulated_cost,
    "carryForwardLoss": runtime_metrics["carryForwardLossCount"],
}
# 写入到metrics artifact
```

**文件**: [packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py](packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py) L1200-1250

---

#### 6. Tool Failure Retry边界
**现状**: tool failure被捕获但没有retry/fallback策略

**建议**: 定义retry策略
```python
MAX_TOOL_RETRIES = 2
for call in tool_calls:
    for retry_attempt in range(MAX_TOOL_RETRIES):
        try:
            execution = execute_registered_tool(...)
            break
        except ToolExecutionError as e:
            if retry_attempt < MAX_TOOL_RETRIES - 1:
                logging.warning(f"Tool retry {retry_attempt + 1}/{MAX_TOOL_RETRIES}")
                continue
            else:
                execution = {"success": False, "error": str(e), "retries_exhausted": True}
```

**文件**: [packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py](packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py) L1104-1122

---

### 🟢 可选改进 (P2后续)

#### 7. Compression Count应用
**现状**: compressionCount被递增但无实际应用场景

**建议**: 补充compression触发条件
```python
if _estimate_context_tokens(current_context) > restart_threshold * 0.9:
    runtime_metrics["compressionCount"] += 1
    current_context = _compress_context(current_context, target_tokens=restart_threshold * 0.8)
```

---

## 测试覆盖建议

### P2 Task 14-17 必需的测试用例

```python
# 1. Cost Budget Exceeded
def test_cost_budget_exceeded_hard_fails():
    """When accumulated_cost > cost_budget_total, should hard fail"""
    
# 2. Request State Recovery
def test_pending_actions_apply_request_state():
    """Pending action requestState should be merged into request"""
    
# 3. Snapshot Integrity
def test_pending_tool_calls_snapshot_integrity():
    """Snapshot should be recoverable with checksum validation"""
    
# 4. Tool Retry Logic
def test_tool_execution_retry_on_failure():
    """Tool execution should retry up to MAX_TOOL_RETRIES"""
    
# 5. Runtime Metrics Export
def test_runtime_metrics_exported_after_execution():
    """Runtime metrics should be exported and queryable"""
```

---

## 迁移检查清单

- [ ] 添加cost budget hard fail逻辑 (llm_runtime.py)
- [ ] 补充request state应用 (execution_loop.py)
- [ ] 实现snapshot checksum验证 (snapshot.py)
- [ ] 增强tool execution trace metadata (llm_runtime.py)
- [ ] 添加runtime metrics导出接口 (execution_loop.py)
- [ ] 定义tool failure retry策略 (llm_runtime.py)
- [ ] 编写P2任务的单元测试 (tests/test_*.py)
- [ ] 更新文档/DIRECTORY_REFERENCE.md

---

## 相关文件导航

| 组件 | 文件 | 行号范围 | 说明 |
|-----|------|--------|------|
| LLM Runtime | [llm_runtime.py](packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py) | L64-1200 | 核心执行引擎 |
| Execution Loop | [execution_loop.py](packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py) | L76-1400 | runtime metrics + pending actions |
| Snapshot | [snapshot.py](packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py) | L20-550 | savepoint机制 |
| Test Suite | [test_llm_retry_and_safe_shutdown.py](tests/test_llm_retry_and_safe_shutdown.py) | L1-350 | safe-stop测试 |
| Test Suite | [test_runtime_p1_hardening.py](tests/test_runtime_p1_hardening.py) | L1-250 | restart request state测试 |

---

## 附录: 代码片段参考

### SafeShutdownInterrupt使用示例
```python
# 触发
raise SafeShutdownInterrupt(
    pending_tool_calls=tool_calls,
    conversation_messages=conversation_messages,
    invocation_id=invocation.id,
    round_index=round_index,
    usage_totals=dict(usage_totals),
    accumulated_cost=accumulated_cost,
    round_summaries=list(round_summaries),
    round_modes=list(round_modes),
    assistant_tool_calls_payload=assistant_tool_calls_payload,
    assistant_message=assistant_message,
)

# 捕获与恢复
except SafeShutdownInterrupt as exc:
    snap_result = save_pending_tool_calls_snapshot(
        task_id=task.id,
        agent_run_id=run.id,
        pending_tool_calls=exc.pending_tool_calls,
        conversation_messages=exc.conversation_messages,
        ...
    )
```

### Pending Actions恢复示例
```python
# 保存时
pending_action = {
    "kind": "pending-tool-calls",
    "toolCalls": tool_calls,
    "conversationMessages": conversation_messages,
    "usageTotals": usage_totals,
    "accumulatedCost": accumulated_cost,
}

# 恢复时
if pending_action.get("kind") == "pending-tool-calls":
    _resume_tool_calls = pending_action.get("toolCalls")
    accumulated_cost = float(pending_action.get("accumulatedCost", 0.0))
    _execute_resumed_tool_calls(tool_calls=_resume_tool_calls, ...)
```

---

**报告生成时间**: 2026-05-17  
**审计范围**: P2 Task 14-17 (C2-C3, C6-C7)  
**下一步**: 实现缺失功能，补充测试用例

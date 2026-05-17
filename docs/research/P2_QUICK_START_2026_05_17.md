# P2 快速开始指南 (Quick Start)

> 5 分钟快速了解 P2 (任务14-17) 的实现要点

---

## 🎯 核心目标

完成推理执行稳态化的四个关键能力：

| 任务 | 目标 | 关键词 |
|-----|------|--------|
| **14** | LLM 预算治理 | Pre-check, Hard fail, Cost tracking |
| **15** | 工具隔离 | Exception wrapping, Failure tracking, Retry logic |
| **16** | 指标导出 | Metrics snapshot, Persistent artifact |
| **17** | 安全停止 | SHA256 checksum, Data integrity, Recovery |

---

## 📂 文件导航

### 我应该先读什么？

```
【新手路线】
1. 这个文件 (5 min) ← 你在这里
   │
   ├─ 快速了解4个任务的关键概念
   │
2. P2_IMPLEMENTATION_CHECKLIST_2026_05_17.md (10 min)
   │
   ├─ 快速定位文件改动位置
   ├─ 看到具体的行号
   │
3. P2_IMPLEMENTATION_SPEC_2026_05_17.md (1-2 小时)
   │
   ├─ 详细代码实现
   ├─ 完整的代码片段
   │
【如需深度理解】
4. docs/specs/runtime-domain-data-spec-v0.1.md
   │
   ├─ 数据结构规范
   └─ Pydantic 配置说明
```

---

## 🚀 任务概览

### 任务 14: LLM 预算治理 (C2)

**问题**: 如何防止 LLM 调用造成预算超支？

**解决方案**:
```python
# 1. 调用前检查
if not _check_pre_invocation_budget():
    raise BudgetInsufficientError()

# 2. 循环中检查
for each tool round:
    if accumulated_cost > budget:
        # 硬 fail，停止工具循环
        break

# 3. 调用后检查
_check_post_invocation_budget()
```

**关键概念**:
- **Pre-check**: 避免无法完成的 LLM 调用
- **In-loop hard fail**: 成本超出时立即停止（不是软降级）
- **Post-check**: 验证实际用量与预期一致

**新增代码行数**: ~150 行  
**修改文件**: `llm_runtime.py`

---

### 任务 15: 工具隔离 (C3)

**问题**: 工具调用失败后怎样不让整个循环崩溃？

**解决方案**:
```python
def _execute_tool_with_isolation(tool_call):
    try:
        # 执行工具
        result = execute_tool(tool_call)
        return ToolExecutionResult(success=True, result=result)
    except RetryableError as e:
        # timeout, connection → 自动重试（最多2次）
        retry_count = 0
        while retry_count < MAX_RETRIES:
            try:
                result = execute_tool(tool_call)
                return ToolExecutionResult(success=True, result=result)
            except RetryableError:
                retry_count += 1
        # 重试也失败了
        return ToolExecutionResult(success=False, error=e)
    except NonRetryableError as e:
        # permission, validation → 快速失败
        return ToolExecutionResult(success=False, error=e)
    except Exception as e:
        # 未预期的异常
        return ToolExecutionResult(success=False, error=e)
```

**关键概念**:
- **异常隔离**: 工具异常不会传出包装函数
- **智能重试**: timeout/connection 自动重试，其他错误快速失败
- **完整记录**: 所有失败都记在 `round_tool_failures` 中

**新增代码行数**: ~100 行  
**修改文件**: `llm_runtime.py`

---

### 任务 16: Metrics 导出 (C6)

**问题**: 如何追踪跨窗口的性能变化？

**解决方案**:
```python
# 1. 构建快照
metrics_snapshot = _build_runtime_metrics_snapshot(
    window_index=current_window,
    cumulative_tokens=total_tokens,
    cumulative_cost=total_cost,
    token_efficiency=tokens_per_action,
    restart_count=restarts_so_far,
    # 还有 15+ 个其他字段
)

# 2. 保存到文件
artifact_id = _persist_runtime_metrics_artifact(metrics_snapshot)
# 保存到: runtime/metrics/{artifact-id}.json

# 3. 返回给客户端
return {
    "runtimeMetricsSnapshot": metrics_snapshot,
    "runtimeMetricsArtifactId": artifact_id,
    "runtimeMetricsLocator": f"/artifacts/{artifact-id}"
}
```

**关键概念**:
- **快照完整**: 一次收集 20+ 关键指标
- **持久化**: 保存到文件，支持跨进程对比
- **跨窗口追踪**: cumulative/baseline 指标单调递增

**新增代码行数**: ~80 行  
**修改文件**: `execution_loop.py`

---

### 任务 17: 安全停止与恢复 (C7)

**问题**: SafeStop 后如何确保数据没有被污染？

**解决方案**:
```python
# 1. SafeStop 时计算校验和
for action in pending_actions:
    action.checksum = _compute_action_checksum(action)

safe_stop_snapshot = SafeStopSnapshot(
    pending_actions=pending_actions,
    # 快照包含所有 checksum
)

# 2. 恢复时验证校验和
loaded_snapshot = load_safe_stop_snapshot()
for action in loaded_snapshot.pending_actions:
    if not _verify_action_checksum(action):
        raise SnapshotCorruptedError()

# 3. 通过验证后可以安全继续
for action in loaded_snapshot.pending_actions:
    execute_action(action)  # 原位续跑
```

**关键概念**:
- **SHA256 校验**: 每个 action 都有校验和
- **确定性**: `sort_keys=True` 保证相同数据相同校验
- **恢复验证**: 加载前自动检测数据污染
- **原位续跑**: 无丢失地完全恢复

**新增代码行数**: ~120 行  
**修改文件**: `snapshot.py`, `execution_loop.py`

---

## 💾 数据结构速览

### 新增数据类 (Pydantic BaseModel)

| 任务 | 数据类 | 字段数 | 用途 |
|-----|--------|--------|------|
| 14 | BudgetCheckResult | 3 | 预检结果 |
| 14 | BudgetOverrunResult | 4 | 超支诊断 |
| 15 | ToolExecutionFailure | 5 | 失败信息 |
| 15 | ToolExecutionResult | 3 | 执行结果 |
| 16 | RuntimeMetricsSnapshot | 20+ | 性能指标 |
| 16 | RuntimeMetricsArtifact | 4 | 持久化元数据 |
| 17 | PendingActionSnapshot | 4 | 待执行动作 |
| 17 | SafeStopSnapshot | 5 | 安全停止快照 |

**重要**: 所有数据类都需要：
```python
from pydantic import BaseModel, Field
from typing import Literal

class MyModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,  # 允许用别名
        extra="forbid"           # 禁止额外字段
    )
    
    # Python: snake_case
    # JSON: camelCase (通过 alias)
    my_field: int = Field(
        alias="myField",  # JSON key
        description="..."
    )
```

---

## 🔧 集成点速查

### 4 个关键集成位置

```
packages/python-sdk/src/yggdrasil_sdk/
│
├─ contracts.py
│  ├─ 新增: BudgetCheckResult, BudgetOverrunResult (任务14)
│  ├─ 新增: ToolExecutionFailure, ToolExecutionResult (任务15)
│  ├─ 新增: RuntimeMetricsSnapshot, RuntimeMetricsArtifact (任务16)
│  └─ 新增: PendingActionSnapshot, SafeStopSnapshot (任务17)
│
├─ llm_runtime.py
│  ├─ 新增常量: _MAX_TOOL_RETRIES, _COST_BUDGET_BUFFER (任务14, 15)
│  ├─ 新增函数: _check_pre_invocation_budget() (任务14)
│  ├─ 新增函数: _check_post_invocation_budget() (任务14)
│  ├─ 新增函数: _execute_tool_with_isolation() (任务15)
│  └─ 修改: invoke_runtime_completion() 集成点 (3 处)
│
├─ runtime_kernel/
│  │
│  ├─ execution_loop.py
│  │  ├─ 新增函数: _build_runtime_metrics_snapshot() (任务16)
│  │  ├─ 新增函数: _persist_runtime_metrics_artifact() (任务16)
│  │  └─ 修改: SafeShutdownInterrupt 处理 (任务17)
│  │
│  └─ snapshot.py
│     ├─ 新增函数: _compute_action_checksum() (任务17)
│     ├─ 新增函数: _verify_action_checksum() (任务17)
│     ├─ 新增函数: build_safe_stop_snapshot() (任务17)
│     └─ 新增函数: verify_safe_stop_snapshot() (任务17)
```

---

## ⏱️ 实现时间表

### 建议的开发计划

| 日期 | 任务 | 工作内容 | 预计时间 |
|-----|-----|---------|---------|
| **Day 1** | 数据类 | 在 contracts.py 定义所有 8 个数据类 | 2 小时 |
| **Day 2** | 任务14 | 在 llm_runtime.py 实现预算检查 | 3 小时 |
| **Day 3** | 任务15 | 实现工具隔离包装函数 | 2.5 小时 |
| **Day 4** | 任务16 | 在 execution_loop.py 实现指标收集 | 2 小时 |
| **Day 5** | 任务17 | 在 snapshot.py 实现校验和函数 | 3 小时 |
| **Day 6-7** | 测试 | 运行所有测试 + 集成验证 | 2 天 |

**总计**: ~5-7 天（包括测试）

---

## ✅ 验收清单

完成所有任务后需要验证：

- [ ] **任务14** 
  - [ ] 预检函数存在并返回 BudgetCheckResult
  - [ ] 硬 fail 逻辑在工具循环中工作
  - [ ] 所有预算检查测试通过 (4 个)

- [ ] **任务15**
  - [ ] 隔离函数正确包装异常
  - [ ] 重试逻辑自动处理 timeout
  - [ ] 失败记录在 round_summaries 中
  - [ ] 所有隔离测试通过 (5 个)

- [ ] **任务16**
  - [ ] 快照收集所有 20+ 指标
  - [ ] 文件保存到 runtime/metrics/
  - [ ] 跨窗口指标单调性检查通过
  - [ ] 所有指标测试通过 (3 个)

- [ ] **任务17**
  - [ ] 校验和计算使用 sort_keys=True
  - [ ] 恢复时能检测数据污染
  - [ ] SafeStop 快照验证成功
  - [ ] 所有校验测试通过 (5 个)

---

## 🎓 学习资源

### 推荐阅读顺序

1. **本文件** (5 min) ← 快速理解概念
2. **P2_IMPLEMENTATION_CHECKLIST_2026_05_17.md** (10 min) ← 了解改动位置
3. **P2_IMPLEMENTATION_SPEC_2026_05_17.md** 相关章节 (30 min) ← 详细代码
4. **相关单元测试** (1 小时) ← 学习预期行为

### 关键概念解释

**什么是 "Hard Fail"?**
> 成本预算超出时，立即停止工具调用循环（不是降级或缩小）。这确保了成本不会继续上升。

**什么是 "异常隔离"?**
> 工具执行的任何异常都被包装函数捕获，返回统一的错误结构，而不是向上传播导致循环崩溃。

**什么是 "确定性序列化"?**
> 使用 `json.dumps(data, sort_keys=True)` 确保相同数据始终产生相同的 JSON 字符串，从而校验和一致。

**什么是 "原位续跑"?**
> 从 SafeStop 恢复后，继续执行与中断前完全相同的待执行任务，无任何丢失或重复。

---

## 💡 常见问题

### Q: 任务 14 的 "hard fail" 和 "软降级" 有什么区别?

**A**: 
- **Hard fail**: 直接停止工具循环，返回错误
- **软降级**: 继续循环，但减少功能或精度

P2 要求 hard fail（更安全）。

### Q: 任务 15 的重试逻辑什么时候触发?

**A**: 仅在 timeout/connection 错误时。  
Permission/validation 错误直接返回失败（无重试）。

### Q: 任务 16 的 metrics 保存到哪里?

**A**: `runtime/metrics/{artifact-id}.json`  
每次执行生成一个新的 artifact。

### Q: 任务 17 的校验和如何防止数据污染?

**A**: 
1. SafeStop 时计算每个 action 的 SHA256
2. 恢复时重新计算并对比
3. 如果不一致 → 快照已被污染 → 拒绝加载

---

## 📞 获取帮助

如需详细信息，请查阅：

| 问题 | 查看 |
|-----|------|
| 具体代码改动 | P2_IMPLEMENTATION_SPEC_2026_05_17.md |
| 文件位置和行号 | P2_IMPLEMENTATION_CHECKLIST_2026_05_17.md |
| 完整成果统计 | P2_COMPLETION_REPORT_2026_05_17.md |
| 数据结构规范 | docs/specs/runtime-domain-data-spec-v0.1.md |
| 项目总体路线 | docs/research/memory-tree-agent-executable-roadmap-2026-05-16.md |

---

**下一步**: 打开 `P2_IMPLEMENTATION_CHECKLIST_2026_05_17.md` 了解具体的代码改动位置。


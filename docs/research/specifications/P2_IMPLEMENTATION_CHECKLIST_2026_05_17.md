# P2 任务14-17 实现检查清单

- 文档状态：Quick Reference Implementation Checklist
- 日期：2026-05-17
- 用途：快速查阅每个任务的实现要点和集成路径

---

## 任务14 (C2): LLM调用与预算治理

### 文件修改清单

- [ ] `packages/python-sdk/src/yggdrasil_sdk/contracts.py`
  - [ ] 新增 `BudgetCheckResult` 数据类
  - [ ] 新增 `BudgetOverrunResult` 数据类

- [ ] `packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py`
  - [ ] 新增常量 `_MAX_TOOL_RETRIES = 2`
  - [ ] 新增常量 `_COST_BUDGET_BUFFER = 0.01`
  - [ ] 新增常量 `_TOKEN_BUDGET_SAFETY_MARGIN = 32`
  - [ ] 新增函数 `_check_pre_invocation_budget()`
  - [ ] 新增函数 `_check_post_invocation_budget()`
  - [ ] 修改 `invoke_runtime_completion()` 中的预检逻辑
  - [ ] 修改工具循环 (~1000-1020 行) 添加硬 fail 检查
  - [ ] 修改返回结构添加 `budgetCheckResult` 字段

### 关键代码片段位置

```
llm_runtime.py:
  - L 50-60: 新增常量定义
  - L 450-550: 新增 _check_pre_invocation_budget()
  - L 550-650: 新增 _check_post_invocation_budget()
  - L 1220-1235: 修改预检集成点
  - L 1000-1020: 修改工具循环 hard fail 逻辑
  - L 1180-1220: 修改返回结构
```

### 集成验证

- [ ] 执行 `test_pre_invocation_budget_check_blocks_insufficient_cost`
- [ ] 执行 `test_pre_invocation_budget_check_passes_sufficient_budget`
- [ ] 执行 `test_post_invocation_budget_overrun_detected`
- [ ] 执行 `test_hard_fail_terminates_tool_loop_on_cost_budget_exceeded`

---

## 任务15 (C3): 工具调用执行回合

### 文件修改清单

- [ ] `packages/python-sdk/src/yggdrasil_sdk/contracts.py`
  - [ ] 新增 `ToolExecutionFailure` 数据类
  - [ ] 新增 `ToolExecutionResult` 数据类

- [ ] `packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py`
  - [ ] 新增函数 `_execute_tool_with_isolation()`
  - [ ] 修改工具执行循环添加隔离包装

### 关键代码片段位置

```
llm_runtime.py:
  - L 1050-1150: 新增 _execute_tool_with_isolation()
  - L 1060-1090: 修改工具循环执行逻辑
    - 添加 round_tool_failures 列表
    - 调用 _execute_tool_with_isolation()
    - 记录失败信息
    - 添加到 round_summaries["toolFailures"]
```

### 集成验证

- [ ] 执行 `test_tool_execution_failure_isolated_and_returns_error_result`
- [ ] 执行 `test_tool_execution_with_retryable_error_retries_up_to_max`
- [ ] 执行 `test_tool_execution_with_non_retryable_error_fails_immediately`
- [ ] 执行 `test_tool_failures_recorded_in_round_summary`
- [ ] 执行 `test_failed_tool_result_added_to_conversation_messages`

---

## 任务16 (C6): 记录 runtime metrics

### 文件修改清单

- [ ] `packages/python-sdk/src/yggdrasil_sdk/contracts.py`
  - [ ] 新增 `RuntimeMetricsSnapshot` 数据类
  - [ ] 新增 `RuntimeMetricsArtifact` 数据类

- [ ] `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py`
  - [ ] 导入 RuntimeMetricsSnapshot, RuntimeMetricsArtifact
  - [ ] 新增函数 `_build_runtime_metrics_snapshot()`
  - [ ] 新增函数 `_persist_runtime_metrics_artifact()`
  - [ ] 修改返回最终结果前添加指标收集逻辑

### 关键代码片段位置

```
execution_loop.py:
  - L 1-30: 导入新数据类
  - L 100-200: 新增 _build_runtime_metrics_snapshot()
  - L 200-250: 新增 _persist_runtime_metrics_artifact()
  - L 2050-2080: 修改返回结果前添加指标收集
    - 调用 _build_runtime_metrics_snapshot()
    - 调用 _persist_runtime_metrics_artifact()
    - 添加到响应: runtimeMetricsSnapshot, runtimeMetricsArtifactId, runtimeMetricsLocator
```

### 集成验证

- [ ] 执行 `test_runtime_metrics_snapshot_captures_all_fields`
- [ ] 执行 `test_metrics_monotonicity_across_windows`
- [ ] 执行 `test_metrics_artifact_persists_and_retrieves`
- [ ] 验证 metrics 文件保存到 `runtime/metrics/{artifact-id}.json`

---

## 任务17 (C7): 安全停止与可恢复断点

### 文件修改清单

- [ ] `packages/python-sdk/src/yggdrasil_sdk/contracts.py`
  - [ ] 新增 `PendingActionSnapshot` 数据类
  - [ ] 新增 `SafeStopSnapshot` 数据类

- [ ] `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py`
  - [ ] 导入 sha256, json
  - [ ] 新增函数 `_compute_action_checksum()`
  - [ ] 新增函数 `_verify_action_checksum()`
  - [ ] 新增函数 `build_safe_stop_snapshot()`
  - [ ] 新增函数 `verify_safe_stop_snapshot()`
  - [ ] 修改 SafeShutdownInterrupt 处理流程

- [ ] `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py`
  - [ ] 导入 SafeStopSnapshot 相关函数
  - [ ] 修改 SafeShutdownInterrupt 异常处理
  - [ ] 调用 build_safe_stop_snapshot()
  - [ ] 调用 verify_safe_stop_snapshot()

### 关键代码片段位置

```
snapshot.py:
  - L 1-10: 导入 sha256, json
  - L 100-130: 新增 _compute_action_checksum()
  - L 130-180: 新增 _verify_action_checksum()
  - L 180-250: 新增 build_safe_stop_snapshot()
  - L 250-320: 新增 verify_safe_stop_snapshot()

execution_loop.py:
  - L 导入行: 添加 SafeStopSnapshot 导入
  - L 1570-1620: 修改 SafeShutdownInterrupt 处理
    - 调用 build_safe_stop_snapshot()
    - 调用 verify_safe_stop_snapshot(strict=False)
    - 添加到 snap_result
```

### 集成验证

- [ ] 执行 `test_safe_stop_snapshot_computes_checksums`
- [ ] 执行 `test_checksum_verification_passes_for_intact_action`
- [ ] 执行 `test_checksum_verification_fails_for_corrupted_action`
- [ ] 执行 `test_safe_stop_snapshot_verification_strict_mode_raises`
- [ ] 执行 `test_safe_stop_snapshot_recovery_preserves_pending_actions`

---

## 四任务集成点

### 集成顺序

1. **第1阶段**: 任务14 + 任务16 基础设施
   - [ ] 部署 BudgetCheckResult 和 RuntimeMetricsSnapshot 数据类
   - [ ] 验证 pydantic 序列化

2. **第2阶段**: 任务14 集成到 llm_runtime.py
   - [ ] 部署预检函数
   - [ ] 部署硬 fail 逻辑
   - [ ] 运行基础测试

3. **第3阶段**: 任务15 集成到工具循环
   - [ ] 部署隔离包装函数
   - [ ] 修改工具执行循环
   - [ ] 记录失败统计

4. **第4阶段**: 任务16 集成到结果返回
   - [ ] 部署指标收集函数
   - [ ] 部署持久化函数
   - [ ] 验证文件保存

5. **第5阶段**: 任务17 集成到 SafeStop 流程
   - [ ] 部署校验和计算
   - [ ] 部署快照构建和验证
   - [ ] 修改异常处理

### 集成测试套件

```
integration_tests/
├── test_p2_budget_and_tool_isolation.py
│   ├── test_insufficient_budget_prevents_tool_execution
│   ├── test_tool_failure_doesnt_break_loop_within_budget
│   └── test_cost_hard_fail_after_budget_exceeded
├── test_p2_metrics_recording.py
│   ├── test_metrics_collected_after_completion
│   ├── test_metrics_artifact_findable
│   └── test_metrics_monotonic_across_restarts
├── test_p2_safe_stop_recovery.py
│   ├── test_safe_stop_snapshot_verified_on_resume
│   ├── test_corrupted_snapshot_rejected
│   └── test_pending_actions_restored_after_stop
└── test_p2_e2e_scenarios.py
    ├── test_scenario_budget_exhausted_mid_tool_round
    ├── test_scenario_safe_stop_and_resume_same_task
    └── test_scenario_multi_window_metrics_consistency
```

---

## 验收标准检查表

| 任务 | 完成标准 | 检查状态 |
|-----|--------|--------|
| 任务14 | 预检准确性: 预检 vs 实际成本误差 < 5% | [ ] |
| 任务14 | 硬fail 时机: accumulated_cost 超预算时立即停止 | [ ] |
| 任务15 | 隔离完整性: 工具异常不导致主循环异常 | [ ] |
| 任务15 | 失败追踪: tool_failures 列表完整记录 | [ ] |
| 任务16 | 指标一致性: 窗口间指标单调递增 | [ ] |
| 任务16 | 导出完整性: 所有标准字段都保存 | [ ] |
| 任务17 | 校验和准确性: 恢复前后 checksum 一致 | [ ] |
| 任务17 | 恢复可用性: SafeStop 后可完全恢复 | [ ] |

---

## 常见修改错误

### ❌ 容易遗漏的地方

1. **任务14**: 忘记在工具循环中添加 hard fail 检查
   - 需要在 ~1000-1020 行添加成本检查
   - 不仅是预检，循环中也要检查

2. **任务15**: 工具失败后没有添加到 round_summaries
   - round_summaries[-1]["toolFailures"] 字段很关键
   - 供后续分析和恢复使用

3. **任务16**: 忘记在正确的地方收集指标
   - 需要在 llm_result 返回后收集
   - 需要保存到文件系统，不仅在内存

4. **任务17**: 校验和计算时没有 sort_keys=True
   - JSON 序列化必须使用 sort_keys=True
   - 否则相同数据会有不同的校验和

### ✅ 验证要点

- [ ] 所有新增函数都有 docstring
- [ ] 所有新增数据类都继承 BaseModel 并配置 populate_by_name
- [ ] 所有 alias 字段都使用 camelCase
- [ ] 所有日志都使用 _logger.info/debug/warning
- [ ] 所有异常都有明确的错误消息
- [ ] 所有测试都覆盖正常和异常路径

---

## 参考文档

- 实现规范索引: [P2_IMPLEMENTATION_SPEC_2026_05_17.md](P2_IMPLEMENTATION_SPEC_2026_05_17.md)
- 任务14规范: [P2_TASK14_LLM_BUDGET_SPEC_2026_05_17.md](P2_TASK14_LLM_BUDGET_SPEC_2026_05_17.md)
- 任务15规范: [P2_TASK15_TOOL_ROUND_SPEC_2026_05_17.md](P2_TASK15_TOOL_ROUND_SPEC_2026_05_17.md)
- 任务16规范: [P2_TASK16_RUNTIME_METRICS_SPEC_2026_05_17.md](P2_TASK16_RUNTIME_METRICS_SPEC_2026_05_17.md)
- 任务17规范: [P2_TASK17_SAFE_STOP_SPEC_2026_05_17.md](P2_TASK17_SAFE_STOP_SPEC_2026_05_17.md)
- 集成验收指南: [P2_IMPLEMENTATION_INTEGRATION_GUIDE_2026_05_17.md](P2_IMPLEMENTATION_INTEGRATION_GUIDE_2026_05_17.md)
- 现状审计: [P2_TASK_14_17_FILE_STATUS_AUDIT.md](P2_TASK_14_17_FILE_STATUS_AUDIT.md)
- 可执行路线图: [memory-tree-agent-executable-roadmap-2026-05-16.md](memory-tree-agent-executable-roadmap-2026-05-16.md)
- 数据规格: [../specs/runtime-domain-data-spec-v0.1.md](../specs/runtime-domain-data-spec-v0.1.md)


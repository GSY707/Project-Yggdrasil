# P2 任务14-17集成与验收指南（2026-05-17）

来源：从总规范文档按“集成与验收标准/后续操作指南/文档更新清单”拆分。

---

# 集成与验收标准

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


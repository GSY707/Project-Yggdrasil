# P2 执行结果验证与 P3 完成报告（2026-05-17）

- 文档状态：Verification + Delivery Report
- 日期：2026-05-17
- 范围：
  - P2（任务 14-17）执行结果核验
  - P3（任务 18-20）代码与评测闭环补齐

---

## 1. P2 验证结论

### 1.1 已落地能力（代码存在且有测试覆盖）

1. 预算检查数据结构：`BudgetCheckResult`、`BudgetOverrunResult`。
2. 工具执行隔离：`_execute_tool_with_isolation`，支持可重试失败隔离。
3. 指标快照结构：`RuntimeMetricsSnapshot`、`RuntimeMetricsArtifact`。
4. 安全停止基础：`SafeShutdownInterrupt`、pending action checksum（`_compute_snapshot_checksum` / `_verify_snapshot_integrity`）。

### 1.2 剩余差异（已降级为口径项）

1. 预算 pre/post check 已完成主链路接线：`invoke_runtime_completion()` 每轮调用前执行 pre-check，调用后执行 post-check，并把结构化结果写入 round summary 与最终返回载荷。
2. P2 文档中的“独立 SafeStopSnapshot 类型与 build/verify 函数命名”在现实现中采用了等价但不同命名/承载方式（pending action checksum 路径），当前属于命名口径差异，不影响可恢复行为。

### 1.3 验证命令与结果

```powershell
uv run pytest -q tests/test_llm_retry_and_safe_shutdown.py tests/test_task_takeover.py tests/test_g4_multiscene.py
```

结果：`34 passed`（新增预算 pre/post check 单测后）。

---

## 2. P3 完成内容

## 2.1 任务 18（E1）交付段落硬门禁

变更：`modules/task-takeover/src/yggdrasil_task_takeover/plugin.py`

- 缺失必需段落（result/evidence/pending/incomplete）时，`verificationItems.status` 从 `warning` 升级为 `failed`。
- 语义从“软提示”提升为“硬失败信号”，可用于上层 gate 直接阻断通过。

新增测试：`tests/test_task_takeover.py`

- `test_task_takeover_module_hard_fails_when_required_delivery_section_missing`

## 2.2 任务 19（D6）多次重启稳定性报告

变更：`packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_g4.py`

- 新增 `_g4_restart_stability_report()`，支持按 tier（如 30/60/100）生成稳定性报告：
  - `targetRestarts`
  - `observedRestartCount`
  - `passed`
  - `restartSuccessRate0_1`
- 支持严格门禁：当 case 配置 `failOnRestartStabilityViolation=true` 且 tier 未达标时，case 直接失败。

配置补齐：`evaluation/suites/g4-window-restart-stress.json`

- 为两个 stress case 增加：
  - `restartStabilityTiers: [30, 60, 100]`
  - `failOnRestartStabilityViolation: true`

新增测试：`tests/test_g4_multiscene.py`

- `test_g4_restart_stability_report_supports_tiered_thresholds`

## 2.3 任务 20（E2）真实任务 parity 冻结

变更：`packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/scorer.py`

- 新增 `_real_task_window_parity_summary()`，在 short/long 成对 case 上冻结以下指标：
  - `goalCompletionParity0_1`
  - `deliveryEquivalence0_1`
  - `qualityDeltaToLongWindow0_100`
  - `qualityDeltaThreshold0_100`
  - `parityPassed0_1`
- 将结果写入 suite 聚合指标：`metrics.realTaskWindowParity`。

配套字段：`packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_g4.py`

- 在 `providerMatrixEntry` 中补充：
  - `goalCompletion0_1`
  - `deliveryCompletion0_1`
  - `officialAcceptancePassed0_1`
  - `parityPairKey`
  - `parityRole`
  - `qualityDeltaThreshold0_100`

配置补齐：`evaluation/suites/g4-real-task-window-parity.json`

- short case：`parityRole=short`
- long case：`parityRole=long`
- 对两者统一设置：
  - `parityPairKey=g4-real-task-window-parity`
  - `qualityDeltaThreshold0_100=8.0`

新增测试：`tests/test_g4_multiscene.py`

- `test_g4_aggregate_case_metrics_emits_real_task_window_parity_summary`

---

## 3. 本次定向回归

```powershell
uv run pytest -q tests/test_llm_retry_and_safe_shutdown.py tests/test_task_takeover.py tests/test_g4_multiscene.py
```

- 结果：34 passed
- 说明：P3 改动与既有 G4/P2 相关路径在本地定向回归通过。

---

## 4. P3 官方评测运行结果（2026-05-17）

### 4.1 D6 入口

命令：

```powershell
corepack pnpm eval:g4:window-stress
```

- 结果：`passRate=1.0`（本次输出中可见 providerSummary 正常产出）。

### 4.2 E2 入口

命令：

```powershell
corepack pnpm eval:g4:real-task-parity
```

- runId：`evalrun_7016b7b1cc27493abe3b`
- 结果：`status=failed`、`passRate=0.0`。
- 失败原因：两条 case 都命中严格 acceptance 失败（缺少必需小节/短语，同时 restart 指标未达阈值）。

说明：这属于 live 评测行为结果未达标，而非本次 P2/P3 代码接线缺失。

---

## 5. 结论

1. P2：任务 14-17 的工程能力已闭环，预算 pre/post check 主链路与断言测试已补齐。
2. P3：任务 18-20 的代码、配置与聚合指标已落地，且本地回归通过；D6 入口已跑通。
3. 当前剩余项集中在 E2 的 live parity 通过率，不在“代码缺失”层面，而在“正式运行结果未达 acceptance”层面。

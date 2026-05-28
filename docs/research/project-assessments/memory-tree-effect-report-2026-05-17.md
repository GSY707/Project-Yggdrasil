# 世界树计划 · 记忆树效果详细报告（2026-05-17）

- 文档状态：Detailed Investigation Report
- 日期：2026-05-17
- 目标：汇总本次对“记忆树代替上下文窗口”效果的全部发现，包括代码链路、回归测试、live 评测、历史证据与风险结论。

---

## 1. 本次检查范围

本次覆盖了四类证据：

1. 运行时主链代码（写树、检索、重启恢复、预算与状态机）。
2. 单测/集成测试（P1/P4、shared-memory、prompting、provider gate、runtime/pruning）。
3. 历史正式评测证据（已落库 evalrun）。
4. 本次 live 评测实跑结果（使用 .env 环境）。

---

## 2. 代码层发现

## 2.1 记忆树主链已接线能力

在运行时主循环中可以观察到以下能力已接线：

1. `currentContext` 物化后参与检索回填，并写入 `memoryRetrievalState`。
2. `takeoverProtocol.workTree` 与 `memoryRetrievalState` 可进 request/root mount。
3. restart/snapshot 路径可携带 requestState、runtimeMetrics、carry-forward 信息。
4. memory-write 标签解析与写入路径存在完整调用链。

关键文件：

- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover.py`
- `packages/python-sdk/src/yggdrasil_sdk/prompting.py`

## 2.2 预算与状态机的当前风险点

在 `llm_runtime.py` 可以看到 pre/post budget-check 分支都在；但本次失败样本显示，分支落态与用例预期存在偏差，影响“执行是否计入预算”与“是否失败”的一致性。

关键文件：

- `packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/root_mount.py`

---

## 3. 测试结果汇总（本次实跑）

## 3.1 通过的测试组

命令：

```powershell
uv run pytest -q tests/test_runtime_p4_foundation.py tests/test_runtime_p1_hardening.py tests/test_m9_shared_memory.py tests/test_prompting_runtime.py tests/test_g4_multiscene.py
```

结果：`33 passed`。

说明：P1/P4 接线、共享内存、prompting、G4 多场景门控基础链路在本机通过。

---

命令：

```powershell
uv run pytest -q tests/test_deepseek_gateway.py tests/test_g4_multiscene.py -k "paid or allow_paid or provider_matrix or gateway"
```

结果：`20 passed`。

说明：free 默认、paid 显式批准、provider matrix 相关门控逻辑在单测层可用。

## 3.2 失败的测试组

命令：

```powershell
uv run pytest -q tests/test_runtime_and_pruning.py::test_main_agent_runtime_pause_resume_closed_loop tests/test_runtime_and_pruning.py::test_main_agent_runtime_fails_when_actual_usage_exceeds_budget
```

结果：`2 failed`。

失败现象：

1. pause/resume 闭环中 `token_budget_used` 仍为 0。
2. 预期“后置超预算失败”场景实际返回 `completed`。

这两个失败不直接证明记忆树主链失效，但会影响“预算约束语义可信度”，属于发布级风险。

---

## 4. 历史评测证据（仓库内可读）

## 4.1 窗口重启稳定性正向证据

- 文件：`.yggdrasil/state/evaluations/evalrun_c42e1101cf93459a9162.json`
- 观察：可见 `windowIndex=101`、`restartCount=100`、`restartSuccessRate0_1=1.0` 等字段。

解读：多次重启技术闭环在历史样本中可成立。

## 4.2 真实任务 parity 历史正向样本

- 文件：`.yggdrasil/state/evaluations/evalrun_590eca26a63247308373.json`
- 观察：可见 `windowIndex=2`、`restartCount=1`、`cumulativeWindowSpanTokens≈4.10M`、`restartSuccessRate0_1=1.0`。

解读：在历史条件下出现过“短长窗口都跑通”的结构性正向样本。

## 4.3 严格 acceptance 历史失败样本

- 文件：`.yggdrasil/state/evaluations/evalrun_ac1f6540396f4f42aadf.json`
- 观察：失败原因包含缺少必需小节、缺少关键短语、窗口指标未达到阈值等。

解读：严格交付门下，模型输出仍可能退化为 planning/stub，交付级 parity 不是稳定必然事件。

---

## 5. 本次 live 评测结果（使用 .env）

## 5.1 real-task parity（本次）

命令：

```powershell
$env:YGGDRASIL_ALLOW_PAID_MODELS='1'; corepack pnpm eval:g4:web-research:default
```

结果摘要：

1. 运行生成 `evalrun_6b0cb49fe6074cc6b2fd`。
2. `caseCount=4`，`passedCount=0`，`failedCount=4`。
3. 4 个 case 全部失败，错误一致：
   - `g4 currentContextFiles failed to read scripts/benchmarks/__pycache__/sqlite_concurrency_benchmark.cpython-312.pyc with encoding utf-8 ...`

解读：本次失败主要是评测语料装载问题（把二进制 `.pyc` 当文本读取），不是模型生成质量结论本身；因此这次 run 不能用于判定记忆树交付效果优劣。

## 5.2 window-stress（本次）

命令：

```powershell
$env:YGGDRASIL_ALLOW_PAID_MODELS='1'; corepack pnpm eval:g4:window-stress
```

输出中可见关键指标：

1. `windowIndex=101`
2. `restartCount=100`
3. `restartSuccessRate0_1=1.0`
4. provider 输出为 `longcat`（`LongCat-2.0-Preview`）
5. providerSummary 中可见 longcat 的 `passRate=1.0`、`avgRestartCount=100.0`

解读：本次 live 压测再次给出了“多次重启稳定”的正向证据，说明记忆树 + restart handoff 在技术闭环上仍然成立。

---

## 6. free / paid LLM 相关发现

## 6.1 门控机制

1. 网关层 `YGGDRASIL_ALLOW_PAID_MODELS` 控制 paid provider 是否进入 catalog。
2. 评测层支持 case 级 `allowPaidModels`，隔离环境会显式设置/清理 paid 开关。

对应文件：

- `adapters/model-providers/src/yggdrasil_model_providers/gateway.py`
- `packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/bootstrap.py`
- `packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_runner.py`
- `evaluation/suites/g4-real-task-web-research-default.json`

## 6.2 本次观察

1. paid 门控逻辑在测试层通过（20 passed）。
2. real-task parity 的失败由语料读取报错主导，不是 paid 网关拒绝主导。
3. window-stress 输出中实际跑出的 provider 是 longcat；本次没有拿到 deepseek 的同等实跑效果证据。

---

## 7. 对“记忆树效果”的综合判断

## 7.1 明确成立的部分

1. 记忆树 + restart handoff 的技术闭环已多次出现正向证据（包含 100 次重启样本）。
2. work tree / retrieval / snapshot / carry-forward 主链具备可运行实现。
3. free 默认 + paid 显式批准的控制面已经具备代码能力。

## 7.2 当前仍未闭合的部分

1. 预算预检/后检与状态机落态一致性存在回归失败（2 个失败用例）。
2. real-task parity 本次 run 被语料装载错误阻断，无法得出有效交付质量结论。
3. 深度 provider 对照（尤其 paid deepseek 路径）仍缺本次可用实测证据。

## 7.3 风险级别

- 技术闭环风险：中（重启链路较强）。
- 交付闭环风险：高（严格 acceptance 与语料装载链路仍可导致整体 run 失效）。
- 发布级风险：高（预算语义一致性 + real-task parity 装载链路）。

---

## 8. 本次可复现实验清单

```powershell
uv run pytest -q tests/test_runtime_p4_foundation.py tests/test_runtime_p1_hardening.py tests/test_m9_shared_memory.py tests/test_prompting_runtime.py tests/test_g4_multiscene.py
uv run pytest -q tests/test_deepseek_gateway.py tests/test_g4_multiscene.py -k "paid or allow_paid or provider_matrix or gateway"
uv run pytest -q tests/test_runtime_and_pruning.py::test_main_agent_runtime_pause_resume_closed_loop tests/test_runtime_and_pruning.py::test_main_agent_runtime_fails_when_actual_usage_exceeds_budget
$env:YGGDRASIL_ALLOW_PAID_MODELS='1'; corepack pnpm eval:g4:web-research:default
$env:YGGDRASIL_ALLOW_PAID_MODELS='1'; corepack pnpm eval:g4:window-stress
```

---

## 9. 总结

1. 记忆树在“多窗口重启稳定性”方面仍表现出强证据。
2. 本次 real-task parity 失败主要由 `.pyc` 被误读为文本导致，属于评测装载缺陷，应优先修复。
3. 预算预检/后检与执行状态的一致性缺陷会影响质量门可信度，需尽快修复后再做正式发布判定。



# 世界树计划 · G4 真实任务窗口对照验证（2026-05-16）

- 文档状态：Initial Scorecard Parity Finding, Superseded On Delivery Axis
- 日期：2026-05-16
- 官方命令：`corepack pnpm eval:g4:real-task-parity`
- 官方 suite：`evalsuite_g4_real_task_window_parity`
- 当前正式 run：`evalrun_590eca26a63247308373`

## 0. 修正说明（2026-05-16 晚）

这份文档保留的是首轮未保留工件时的初版判断。随后在保留完整 prompt / request / response 工件的重跑 `evalrun_941c8b8ca2204966812d` 中，已经确认：

1. 两个 case 虽然仍然 `passed`，但最终输出都只停在 planning stub，没有完成原始任务要求的 final release brief 与 parity judgment。
2. 因此，这份文档里“短窗口与长窗口效果等价”的结论，只能保留为**结构性 scorecard parity**，不能再解释成**最终交付质量 parity**。
3. 当前更准确的基线见 [g4-real-task-window-parity-rerun-log-audit-2026-05-16.md](g4-real-task-window-parity-rerun-log-audit-2026-05-16.md)。

---

## 1. 任务价值判断

这次验证选择的不是“人为重复材料把 prompt 撑长”，而是一条直接面向当前主线的真实 repo-wide 工作：

1. 任务目标是基于当前仓库的真实文档、协议、评测、运行时、provider、测试、前端与应用 surface，输出一份关于伪无限上下文窗口 release parity 的正式判断。
2. 这条任务直接服务于当前第一优先级，因为它要求系统在同一任务里同时保留 runtime 闭环、协议语义、评测口径、provider 证据和文档状态，而不是只回答一个孤立问题。
3. 因此它是高价值任务，不是为了制造 1M token 而拼接的低价值长样本。

---

## 2. 复杂度设计

本次实验没有用 `forcedWindowRestartBudget` 去人工刷跨度，而是逐轮扩大真实语料覆盖面，直到真实任务本身达到 1M 级以上复杂度：

1. 首轮校准 `evalrun_02bfef48a47d4d4aad81`：仅装载定点关键文件，`cumulativeWindowSpanTokens` 约 `63k`，不足以代表 1M 级工作。
2. 第二轮校准 `evalrun_74d78800cbd84228b061`：加入核心目录 glob，`cumulativeWindowSpanTokens` 约 `403k`，仍不足 1M。
3. 正式 run `evalrun_590eca26a63247308373`：把当前 repo 的根配置、docs、infra、evaluation fixtures/suites、packages、modules、services、adapters、tests、apps/web、applications、migrations、scripts 一并纳入真实语料池，最终把同一任务的 `cumulativeWindowSpanTokens` 提升到约 `4.10M`。

这里使用的 1M 级口径以 `cumulativeWindowSpanTokens` 为准，而不是最终一次模型调用的 prompt 大小。最终 prompt 仍被压缩在可执行窗口内，但被压缩之前的真实任务跨度已经达到多窗口量级。

---

## 3. 窗口设置

本次对照没有使用失真的极小窗口，而是用了两档现实里可讨论的工作集大小：

1. short-window：`effectiveContextWindow=64000`，`windowRestartThreshold=48000`
2. long-window：`effectiveContextWindow=128000`，`windowRestartThreshold=96000`

两条路径共享同一 provider、同一任务、同一 acceptance contract、同一 repo-wide 真实语料，只改变窗口长度。

---

## 4. 结果

| 维度 | Short 64k | Long 128k |
|------|-----------|------------|
| runId | `evalrun_590eca26a63247308373` | `evalrun_590eca26a63247308373` |
| provider | `longcat / LongCat-Flash-Lite` | `longcat / LongCat-Flash-Lite` |
| pass | `true` | `true` |
| `acceptance_pass_0_1` | `1` | `1` |
| `planQualityScore0_100` | `96.0` | `96.0` |
| `restartCount` | `1` | `1` |
| `windowIndex` | `2` | `2` |
| `cumulativeWindowSpanTokens` | `4103262` | `4103261` |
| `restartSuccessRate0_1` | `1.0` | `1.0` |
| `beforeContextPruning estimatedTokens` | `24326` | `40166` |
| `firstUsefulOutputSeconds` | `29.75` | `2.34` |

补充说明：

1. `beforeContextPruning` 观测到的是 restart 之后的 carry-forward 工作集，而不是原始 repo-wide 语料总量。
2. 原始任务跨度由 `cumulativeWindowSpanTokens` 表达，二者都已经超过 `4.10M`。
3. 这说明当前实验不是通过制造一次超大 prompt 达成，而是通过真实语料进入多窗口接续后完成。

---

## 5. 结论

在当前 LongCat 路径上，可以得出的结论是：

1. 同一条 1M 级以上的真实 repo-wide 任务，在 `64k` 与 `128k` 两档窗口下都通过了同一 acceptance contract。
2. 本次没有观察到显著质量退化：两条路径的 `planQualityScore0_100` 同为 `96.0`，`acceptance_pass_0_1` 同为 `1`。
3. 可观察到的主要差异在时延，而不是最终效果：本次 short-window 的 `firstUsefulOutputSeconds` 明显高于 long-window，但最终任务结论与质量口径保持一致。

因此，基于这份初版 run 当时可见的 scorecard 和 summary，短窗口与长窗口在结构性指标上呈现出等效；但 2026-05-16 的保留日志重跑已经证明，这还不能被解释为最终交付质量等效。

---

## 6. 剩余缺口

本次验证并不意味着 release 门槛已经完全冻结，仍有两项必须继续完成：

1. 先修正 acceptance 口径，把“release brief 已完成、parity judgment 已明确给出”冻结成强验收项，再谈 multi-provider 复制。
2. 用 `deepseek_direct / deepseek-v4-pro` 复跑同一条真实任务，但前提是不再沿用当前会把恢复态拉成 planning stub 的 prompt contract。
3. 基于 `evalrun_1160dc08b84e4b6e8268` 的 stress 证据、首轮 `evalrun_590eca26a63247308373` 的结构性对照，以及保留日志重跑暴露出的 delivery drift，重新冻结正式门槛：`restartSuccessRate0_1`、`goalCompletionParity0_1`、`deliveryEquivalence0_1`、`qualityDeltaToLongWindow0_100`。
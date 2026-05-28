# LLM 真实任务无限上下文能力评估（2026-05-17）

## 1. 纠偏后的评估口径

这份报告只按两类证据给结论：

1. 任务目标：来自 `evaluation/suites/g4-real-task-web-research-default.json` 的真实任务契约。
2. 任务结果：来自 Langfuse trace 中 LLM 的最终输出原文，而不是 `deliveryEquivalence0_1`、`restartCount`、`cumulativeWindowSpanTokens` 这类执行指标。

执行指标只作为辅助证据，不再单独承担“任务效果是否达成”的结论职责。

## 2. 任务目标

本轮真实任务的目标是：

1. 审视当前 Project Yggdrasil 仓库，输出一份 release-ready 的伪无限上下文 parity brief。
2. 先判断这是不是当前仓库的高价值真实任务。
3. 在同一任务契约下，对 short-window 与 long-window 给出是否等价的最终判断。
4. 结论必须覆盖 runtime、evaluation、protocol、provider、documentation、evidence 等横切面，而不是只谈 token 或单次 prompt。

## 3. 这次真正使用的链路

本轮重新跑了真实任务，并把 Langfuse 真正接进观测链路：

1. 启动 Langfuse：`corepack pnpm infra:langfuse:up`
2. 重新执行真实任务对照：`corepack pnpm eval:g4:web-research:default`
3. 从 Langfuse trace `75c172aae4ff70de8ec320f08ff43fcb` 读取 4 个 generation 的最终输出
4. 使用专用分析器 `scripts/analyze_langfuse_real_task_trace.py` 生成逐窗口分析工件：`.yggdrasil/state/analysis/langfuse-real-task-trace.md`

这一步同时说明两件事：

1. Langfuse 现在不是“已配置但未使用”，而是已经接收到本轮真实任务 trace。
2. DeepSeek 链路本轮确实可用，因为 Langfuse 里出现了 `deepseek-v4-pro` 的真实 generation 输出。

## 4. 任务结果：LLM 最终输出，而不是执行指标

本轮 trace 一共记录到 4 条最终输出，每条都形成了完整 brief，但它们的第 6 节结论并不一致。

| 路径 | provider / model | 窗口数 | 第 6 节最终结论 | 任务结果摘要 |
|---|---|---:|---|---|
| DeepSeek short64k | `deepseek-v4-pro` | 17 | 等价 | 明确写出“short-window 路径与 long-window 参考路径在本仓库当前状态中可视为等价”。 |
| DeepSeek long128k | `deepseek-v4-pro` | 9 | 等价 | 明确写出“任务效果等价”，认为最小充分证据集已经足够支撑相同工程结论。 |
| LongCat short64k | `LongCat-2.0-Preview` | 17 | 不等价 | 明确写出“当前 repo 状态下，short-window 路径不能被认定为与 long-window 参考等价”，理由是工具链可用性与上下文完整性存在差距。 |
| LongCat long128k | `LongCat-2.0-Preview` | 9 | 等价 | 明确写出“在 current repo state 下，short-window 路径与 long-window 路径在同一 acceptance contract 下交付等价”。 |

关键点不是 3 条说“等价”、1 条说“不等价”，而是：

1. LLM 在真实任务里确实输出了最终结果，不再是空泛 planning stub。
2. 这些真实结果彼此冲突，因此不能再用汇总指标把它们强行压成一个“稳定等价”的总结论。

## 5. 任务效果判定

按“任务目标 vs 任务结果”对照，本轮任务效果应判定为：

1. 真实任务输出能力成立。4 条路径都能在最终窗口给出结构完整的 release brief。
2. 多窗口连续性成立。所有路径都通过 restart / snapshot / memory retrieval 把任务拖到了最终交付窗口。
3. 稳定等价结论不成立。因为 4 条真实结果中存在一条明确的“不等价”结论，当前不能把项目表述为“已经稳定证明 short-window 与 long-window 等价”。

因此，本轮正确结论不是“已经验证等价”，而是：

> 系统已经能在真实任务中跨多窗口产生最终判断，但这个判断在不同 provider / profile 上仍然不稳定，当前最多只能说“具备真实任务交付能力，尚未得到稳定的一致等价结论”。

## 6. 逐窗口分析

### 6.1 能力定义

这次窗口分析按 4 种能力拆开：

1. 上下文窗口连续性：窗口重启后任务是否继续沿同一目标前进。
2. 记忆树能力：窗口重启后重新取回的最小充分证据是什么。
3. 工作树能力：每次重启是否仍锚定在同一 work tree 节点。
4. 最终交付能力：LLM 在哪个窗口真正产出了用户可消费的最终 brief。

### 6.2 每条路径里每个窗口做了什么

完整逐窗口表已经由分析器写入 `.yggdrasil/state/analysis/langfuse-real-task-trace.md`。这里保留对 4 条路径的摘要判断。

#### DeepSeek short64k

1. 窗口 1：建立真实任务目标和 release brief 约束，没有最终输出。
2. 窗口 2 到 16：每个窗口都在做同一件事：恢复 restart snapshot、恢复 25 个 runtime request 字段、重新检索最小充分证据节点，并保持同一个 work tree 锚点 `work-tree-node_e28235d916ca03115428`。
3. 窗口 17：首次出现真正的 LLM 最终交付，给出完整 7 节 brief，并在第 6 节判定“等价”。

#### DeepSeek long128k

1. 窗口 1：建立任务目标与交付结构。
2. 窗口 2 到 8：重复执行恢复快照、重建最小证据集、保持同一 work tree 锚点 `work-tree-node_4e5e27f9241db9cd75f8`。
3. 窗口 9：产出最终 brief，并在第 6 节判定“任务效果等价”。

#### LongCat short64k

1. 窗口 1：建立任务目标和高价值判断框架。
2. 窗口 2 到 16：每个窗口都在做恢复快照、保持 work tree 锚点 `work-tree-node_5dcc9d5e59cf81b72792`、重取 `required output structure`、`delivery mode contract`、`window policy` 这组最小证据。
3. 窗口 17：产出最终 brief，但第 6 节明确判定“不等价”。它把“不等价”的原因写成了真实任务结果的一部分：short-window 下工具链不可用、上下文检索有界、恢复语义存在额外间接层。

#### LongCat long128k

1. 窗口 1：建立任务目标与最终输出结构。
2. 窗口 2 到 8：持续恢复快照、重取最小充分证据、保持同一 work tree 锚点 `work-tree-node_0dde49ed0dfd77006a11`。
3. 窗口 9：产出最终 brief，并在第 6 节判定“等价”。

### 6.3 这次逐窗口分析说明了什么

这次最重要的窗口级发现不是“发生了多少次 restart”，而是：

1. 前面的大多数窗口里，LLM 并没有产生用户可消费的最终结果；这些窗口的核心作用是恢复状态、压缩工作集、重新挂载最小证据。
2. 真正的用户可消费输出只出现在最后一个窗口。
3. 一旦最后窗口拿到的最小证据集不同，最终 brief 的结论就会分叉。这正是 LongCat short64k 给出“不等价”的根本信号。

## 7. 指标只能作辅助证据

本轮仍然保留两类辅助指标，但它们不再直接等于“任务结果”：

1. `window-stress` 已证明 100 次 restart 的技术闭环成立。
2. 本轮 real-task 里，short64k 路径经历 17 个窗口，long128k 路径经历 9 个窗口，说明系统已经能在真实任务里完成多窗口接续。

这些指标能证明“链路可运行”，却不能证明“任务效果已稳定等价”；后者必须由上面的 LLM 最终输出负责。

## 8. 修复与观测结论

### 8.1 已验证的修复

1. 分片导入 NameError 修复后，真实任务链路可以重新跑通。
2. DeepSeek paid provider 链路已恢复到可调用状态，本轮 Langfuse 中已出现 DeepSeek 的真实 generation 输出。
3. Langfuse 已真正投入使用，而不是停留在配置层。

### 8.2 仍未收口的问题

1. LongCat short64k 的真实最终输出仍然认为“不等价”，这与其余 3 条路径冲突。
2. 因此当前最大的未收口问题不是“有没有输出”，而是“为什么 short64k + LongCat 的最小证据集会导向不同结论”。

## 9. 下一步

1. 优先处理 LongCat short64k 的结论分叉，重点检查恢复态 prompt contract、delivery mode contract 和最小证据集是否把“工具禁用”误解释成了“能力不等价”。
2. 把 `scripts/analyze_langfuse_real_task_trace.py` 固定为后续真实任务 / 无限上下文评估的默认分析入口，避免再回到只看汇总指标的旧口径。
3. 在修复结论分叉之前，不再对外宣称“已经稳定证明 short-window 与 long-window 等价”；更准确的表述应是“真实任务多窗口交付能力已成立，但稳定等价结论仍待收口”。


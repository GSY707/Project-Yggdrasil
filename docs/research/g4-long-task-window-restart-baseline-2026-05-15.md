# 世界树计划 · Gate 4 长任务与上下文窗口重启基线研究（2026-05-15）

- 文档状态：Historical Baseline Updated After Runtime + Live Evidence
- 日期：2026-05-15
- 目标：保留 2026-05-15 基线判断，并补充说明哪些结论已被后续 runtime 实现与 live 证据覆盖，哪些 release 问题仍然存在。
- 关联文档：
  - [Gate 4 正式闭环报告（2026-05-15）](g4-closeout-2026-05-15.md)
  - [Gate 4 评估与完美实现路线图（2026-05-15）](g4-assessment-and-roadmap-2026-05-15.md)
  - [运行时与工具数据规格 v0.1](../specs/runtime-domain-data-spec-v0.1.md)
  - [Agent 运行时协议 v0.1](../specs/agent-runtime-protocol-v0.1.md)
  - [Work Tree Protocol v0.1](../specs/work-tree-protocol-v0.1.md)
  - [任务接管协议 v0.1](../specs/task-takeover-protocol-v0.1.md)
  - [事件契约 v0.1](../protocols/event-contracts-v0.1.md)

---

## 0. 后续状态更新（2026-05-16）

这份文档的主体内容保留的是 2026-05-15 的基线判断；其中“restart loop 尚未正式实现”这一结论，已经被后续实现和 live 证据覆盖：

1. `execution_loop` 已落地正式 restart controller。
2. `snapshotType=restart`、carry-forward package、`context.restart.requested/completed` 与 runtimeMetrics 已进入正式 runtime 路径。
3. `evalsuite_g4_window_restart_stress` 已在 2026-05-15 的正式 live run `evalrun_1160dc08b84e4b6e8268` 中完成首轮复跑；DeepSeek 与 LongCat 两个 case 都通过，且 `restartCount=100`、`windowIndex=101`、`restartSuccessRate0_1=1.0`。
4. 因此，这份基线文档目前更适合作为“为什么当时必须补 restart loop”的历史依据，而不是当前状态报告。

当前真正还未收口的是：在真实任务上做 short-window vs long-window 的正式 parity 对照。

---

## 1. 先给结论

1. 当前仓库已经具备长任务所需的几个前置基座：context pruning、pause/resume、TaskSnapshot、work tree，以及 token usage 与 context length 的正式观测链路。
2. 但在 2026-05-15 这个基线时间点上，“多次上下文窗口重启”还没有形成正式执行闭环。规格里已经预留了 `restartMessage`、`restart-requested`、`restarting`、`context.restart.requested`、`context.restart.completed` 与 `snapshotType=restart`，当时的运行时实现还没有把这些对象串成真正的 restart loop。
3. 当前官方 LongCat longform 样本还远不是窗口级长任务。LongCat 的正式 `contextWindow` 是 `128000`，而最新官方 longform live artifact 中，LongCat case 只有 `4091` total tokens，`3078` maxContextLengthTokens，而且没有出现任何 `beforeWindowRestart` 观测。
4. 因此，仓库今天可以成立的表述是：“G4 已具备长任务 restart 议题的前置基座与观测能力”；不能成立的表述是：“G4 已正式验证 LongCat 下 10 倍窗口、10 次以上窗口重启的长任务能力”。
5. 这不推翻 [Gate 4 正式闭环报告（2026-05-15）](g4-closeout-2026-05-15.md)；那份闭环报告针对的是多场景正式化与 provider matrix 基线。本文讨论的是 G4 下一阶段最关键的新硬要求：超长任务与多次窗口重启。

---

## 2. 已核实的基线事实

| 维度 | 已核实事实 | 工程含义 |
|------|------------|----------|
| LongCat 正式窗口 | [adapters/model-providers/src/yggdrasil_model_providers/gateway.py](../../adapters/model-providers/src/yggdrasil_model_providers/gateway.py) 将 `LongCat-Flash-Lite` 的 `context_window` 定义为 `128000`。 | 若采用“10 倍上下文窗口任务”作为出口标准，则累计任务跨度至少要覆盖 `1,280,000` tokens 量级。 |
| 当前官方长样本入口 | [evaluation/suites/g4-provider-matrix-longform.json](../../evaluation/suites/g4-provider-matrix-longform.json) 只固定了一个 `g4-coding-longform` 单任务样本；[README.md](../../README.md) 和 [package.json](../../package.json) 已把它定义为官方命令入口。 | 现有 longform suite 的定位是“比快任务更长的单任务样本”，不是“强制多次窗口重启的正式压力套件”。 |
| 最新官方 live 证据 | `.yggdrasil/state/evaluations/evalrun_821c46b4b4584f38911e.json` 中，LongCat case 的 `totalTokens=4091`、`nonCacheInputTokens=2811`、`maxContextLengthTokens=3078`。 | 这只相当于一个 128k 窗口的约 `2.4%` 最大上下文占用，距离“单窗口吃满”都还很远，更谈不上“10 倍窗口任务”。 |
| 上下文观测链路 | [packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py](../../packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py) 已记录 `beforeContextPruning`、`afterContextPruning`、`beforeModelInvocation`、`taskEnd`，且当存在 `restartMessage` 时会记录 `beforeWindowRestart`。 | 观测位已经开始对 restart 让路，但还缺真正的 restart 触发器、状态迁移和 run-to-run handoff。 |
| 重启相关正式对象 | [docs/specs/runtime-domain-data-spec-v0.1.md](../specs/runtime-domain-data-spec-v0.1.md) 已给 `Task` 定义 `restartMessage`、`restart-requested`、`restarting`，并给 `TaskSnapshot` 预留 `snapshotType: pause | restart | checkpoint`。 | 控制面语义已经存在，说明项目方向明确；缺的是 runtime 落地。 |
| work tree 语义 | [docs/specs/work-tree-protocol-v0.1.md](../specs/work-tree-protocol-v0.1.md) 中 `WorkTreeNode.phase` 已允许 `restarting`，并要求通过 `recoveryAnchor` 进行正式恢复。 | work tree 已能表达 restart 阶段，但运行时尚未把 restart 真的投影到节点推进与恢复锚点上。 |
| 事件契约 | [docs/protocols/event-contracts-v0.1.md](../protocols/event-contracts-v0.1.md) 已预留 `context.restart.requested` 与 `context.restart.completed`。 | 审计口径已经占坑，但当前代码检索未发现对应事件发射实现。 |
| 快照实现现状 | [packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py](../../packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py) 当前只实际创建 `pause` 与 `checkpoint` 快照。 | `restart` 快照还停留在契约层，没有进入正式 runtime 路径。 |

补充判断：本轮代码与测试检索没有发现 `context.restart.requested` / `context.restart.completed` 的运行时发射代码，也没有发现针对 `snapshotType="restart"` 的正式回归样本。这说明 restart 在当前仓库里仍然属于“有对象定义、无闭环实现”的状态。

---

## 3. 当前缺口到底在哪里

### 3.1 缺的是 restart loop，不是 restart 字段

当前仓库已经有 restart 相关字段和状态，但还缺 4 个真正决定系统是否能做超长任务的核心环节：

1. 缺少正式的 restart 触发条件：什么时候只做 pruning，什么时候必须做 window restart，目前没有冻结规则。
2. 缺少 restart handoff 包：重启时必须保留哪些摘要、哪些 work tree 节点、哪些证据引用、哪些预算信息，目前没有正式最小集合。
3. 缺少 restart 状态迁移闭环：谁把任务从 `running` 推到 `restart-requested` / `restarting`，谁负责创建 restart snapshot，谁负责启动下一次 run，目前没有控制器。
4. 缺少 restart 完成语义：何时清掉 `restartMessage`，何时算本轮 restart 成功接续，何时视为重启失败并要求 repair，目前没有明确判定。

### 3.2 当前执行循环仍然是“单次 run 优先”的结构

[packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py](../../packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py) 现在做得最好的部分是：

1. 在执行前后做上下文估算与 pruning。
2. 在 pause/resume 路径上复用 snapshot。
3. 在 request payload 里把 `contextLengthObservations` 传到 runtime response artifact。

但它还没有成为多轮 window restart 调度器：

1. 没有 `windowIndex`、`restartCount`、`tokensSinceLastRestart`、`cumulativeWindowSpanTokens` 这类跨 run 变量。
2. 没有“触发 restart 后立刻结束当前 run，并把 carry-forward state 交给下一轮 run”的控制流。
3. `restartMessage` 当前更像恢复提示词插槽，而不是真正的重启协议执行器。

### 3.3 work tree 已经够表达，但还没有被真正驱动

当前 work tree 的 formalism 已经足够支撑第一阶段的长任务 restart：

1. 它已经有 `currentNodeId`、`recoveryAnchor`、`phase=restarting`。
2. 它已经要求 pause/resume 或 repair 只能通过正式 recovery anchor 续跑。
3. 它已经要求任务完成时把 work tree 总体状态同步为 `completed`。

真正缺的不是“没有 work tree 概念”，而是“restart 时谁来更新 work tree”。至少还缺下面这些动作：

1. restart 发生时，把当前节点从 `executing` 切到 `restarting` 或写入 restart 子状态。
2. 把新的 `recoveryAnchor`、carry-forward summary ref、window index 绑定到当前节点或任务级恢复入口。
3. 在 restart 后的新 run 中，把 `currentNodeId` 准确恢复到重启前的执行节点，而不是重新从树根泛化理解任务。

### 3.4 当前不必急着新增 ExecutionTreeProtocol

是否现在就要引入单独的 execution tree，是这轮研究里最容易被过度设计的点。我的判断是：**第一阶段不必。**

原因很直接：

1. 当前目标不是并行分支调度，也不是 speculative branching，而是“同一条任务链在多个上下文窗口之间安全续跑”。
2. 对这个目标来说，现有 `executionRootNodeId`、`AgentRun.parentRunId`、`TaskSnapshot`、`WorkTreeProtocol` 已经足够表达一条串行 restart 链。
3. 只有在后续出现下面场景时，ExecutionTreeProtocol 才值得单独冻结：
   - 一个任务在 restart 后分裂出多个候选执行分支。
   - 不同 restart 窗口需要并行验证和仲裁。
   - 需要对子分支结果做正式合流与淘汰。

结论：**G4 长任务第一阶段应先把 restart loop 跑通，而不是先把树模型升级到更复杂的并行执行图。**

### 3.5 当前评测还没有真正压到 restart 问题

现有 `evalsuite_g4_provider_matrix_longform` 的价值是真实、稳定、可复跑，但它还没有成为 restart 能力的证明：

1. 当前 case 只覆盖一个较长的 coding 任务，没有强制窗口溢出。
2. 最新 LongCat live artifact 没有 `beforeWindowRestart` 观测，说明本次执行中根本没有发生 restart。
3. 当前 scorecard 里虽然已经有 `tokenUsage` 与 `contextLengthObservations`，但还没有 `restartCount`、`windowIndex`、`cumulativeWindowSpanTokens` 这类长任务核心指标。

---

## 4. 对“10 倍上下文窗口任务”的正式口径建议

如果把用户当前要求冻结成 G4 长任务出口标准，建议直接采用下面这组硬口径：

1. 官方模型：`longcat / LongCat-Flash-Lite`
2. 官方窗口：`contextWindow = 128000`
3. 目标任务跨度：`cumulativeWindowSpanTokens >= 1,280,000`
4. 最低 restart 次数：`restartCount >= 10`
5. 每个窗口都必须满足安全上限：
   - soft prune 阈值建议在 `55% ~ 65%` 窗口区间
   - hard restart 阈值建议在 `75% ~ 80%` 窗口区间
6. 每次 restart 都必须保留 4 类正式证据：
   - work tree 当前节点与 recovery anchor
   - carry-forward summary 或压缩产物引用
   - 未完成验证项与待交付物引用
   - token / context / restart 观测值
7. 最终交付不能以“重新从头做一遍”达成；必须证明同一个任务链跨 10 次以上窗口重启后仍能完成同一目标。

这里最重要的澄清是：**目标不是把单次 prompt 硬塞到 128 万 tokens。目标是把一个足够长的任务，拆成 10 次以上受控的窗口间接续。**

---

## 5. 最小落地路线

### 5.1 先冻结 restart 协议

第一步不是加更多样本，而是把 restart 协议正式化。最小需要冻结下面这些字段与动作：

1. restart 触发原因：`context-overflow-risk`、`planned-window-rotation`、`forced-repair-restart` 等。
2. restart 载荷：`windowIndex`、`restartCount`、`carryForwardSummaryRef`、`workTreeNodeId`、`recoveryAnchor`、`tokensBeforeRestart`。
3. restart 事件：`context.restart.requested`、`context.restart.completed`、必要时补 `context.restart.failed`。
4. restart 快照：把 `snapshotType=restart` 从契约占位变成正式实现。
5. restart 完成条件：新 run 成功读取 carry-forward package 并恢复到正确 work tree 节点后，才允许把上一次 restart 标记为 completed。

实现形式有两个可选方向：

1. 新增独立规格，例如 `docs/specs/context-window-restart-protocol-v0.1.md`。
2. 直接扩写 [运行时与工具数据规格 v0.1](../specs/runtime-domain-data-spec-v0.1.md)、[Agent 运行时协议 v0.1](../specs/agent-runtime-protocol-v0.1.md) 与 [事件契约 v0.1](../protocols/event-contracts-v0.1.md)。

第一阶段我更建议第二种：先在现有规格上补齐最小协议，避免先把文档树分得过细。

### 5.2 再把 execution loop 变成 restart controller

运行时内核需要新增一个非常具体的控制器，而不是继续把 restart 当成提示词消息：

1. 在 pruning 后、LLM 调用前判断是否越过 hard restart 阈值。
2. 如果越过阈值，先发 `context.restart.requested`，再创建 `snapshotType=restart` 的正式快照。
3. 从当前窗口提炼 carry-forward summary、protected refs、work tree 恢复锚点与待办证据引用。
4. 结束当前 run，并以新的 run 接续执行，而不是在同一轮上下文里强行续写。
5. 新 run 成功接上后，发 `context.restart.completed`，并把 `restartCount`、`windowIndex`、`cumulativeWindowSpanTokens` 写入 runtime artifact。

### 5.3 把 restart 正式投影到 work tree

为了保证“长任务不是每次重启都重新理解任务”，work tree 至少要做到：

1. restart 前记录当前 `currentNodeId`。
2. restart 时为当前节点写入 `recoveryAnchor` 和最近一次 carry-forward summary ref。
3. restart 后的新 run 必须恢复到同一执行节点或其明确后继节点。
4. 连续多次 restart 仍然共享同一个 `executionRootNodeId`，不重新生成新的任务树。

### 5.4 补齐长任务专用观测指标

现有 `tokenUsage` 和 `contextLengthObservations` 已经打下底子，但要判定 10 次以上窗口重启，还必须追加：

1. `restartCount`
2. `windowIndex`
3. `cumulativeWindowSpanTokens`
4. `tokensBeforeRestart[]`
5. `carryForwardSummaryTokens[]`
6. `workTreeNodeIdAtRestart[]`
7. `restartReason[]`

这些指标应该进入 3 个地方：runtime response artifact、G4 provider matrix entry、scorecard/provider summary。

### 5.5 最后再做真正的 G4 长任务压力套件

建议不要直接把现有 `g4-provider-matrix-longform` 改成超重压力任务，而是新增一个专门面向 restart 的套件，避免破坏当前稳定基线。最小形态可以是：

1. 一个官方 LongCat-only live suite。
2. 一个单任务、多阶段、强约束 acceptance 的长任务样本。
3. 样本设计上强制产生 10 次以上窗口轮换，而不是只追求大文件或大段 prompt。
4. 通过标准必须同时满足：
   - `restartCount >= 10`
   - `cumulativeWindowSpanTokens >= 1,280,000`
   - `maxContextLengthTokens` 始终低于安全阈值
   - 最终交付通过 deterministic acceptance
   - work tree 连续性与 evidence chain 未断裂

---

## 6. 不建议现在做的事

1. 不建议把“单次 prompt 塞到更大”当作长任务能力。那只会得到一次性上下文填充，不会得到正式 restart 能力。
2. 不建议先引入独立 execution tree 再回头补 restart controller。当前主要矛盾不在树模型，而在串行 restart loop 没有闭环。
3. 不建议直接把当前官方 longform suite 改成超重压力套件。现有 suite 的价值是稳定基线，应该保留；restart 压力应放在独立套件里。
4. 不建议用总 token 数字替代长任务证明。真正需要证明的是：同一任务链能否跨多个窗口安全续跑、保留计划、保留证据、保留交付连续性。

---

## 7. 最终判断

一句话结论：

> **作为 2026-05-15 的历史基线，这份文档正确描述了当时“还缺 restart orchestration”的状态；而在当前仓库状态下，这一缺口已经被 runtime/controller/stress suite/live evidence 覆盖，下一步最小正确动作变成真实任务的 short-window / long-window parity 验证。**

这也是本轮研究给出的明确优先级：

1. 先补协议。
2. 再补 restart loop。
3. 然后补观测与评测。
4. 最后才谈 LongCat 1.28M 量级任务的正式 live 认证。
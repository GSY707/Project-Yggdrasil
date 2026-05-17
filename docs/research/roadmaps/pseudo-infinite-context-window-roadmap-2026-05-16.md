# 世界树计划 · 伪无限上下文窗口研究与优先级路线（2026-05-16）

- 文档状态：Updated After Implementation And Log-Preserved Audit
- 日期：2026-05-16
- 目标：回答三个具体问题：
  - 当前项目的理论研究是否已经支持“记忆树是主体、上下文窗口只是工作集”的伪无限上下文方向。
  - 为什么这个方向现在必须提升为项目第一优先级。
  - 如何用可执行的正式评测去逼近“无限次上下文窗口重启”的工程验证。
- 关联文档：
  - [世界树计划 PRD v0.1](../PRD-v0.1.md)
  - [系统核心理念](系统核心理念.md)
  - [Gate 4 长任务与上下文窗口重启基线研究（2026-05-15）](g4-long-task-window-restart-baseline-2026-05-15.md)
  - [通向最终目标的路线图（2026-04-30）](final-goal-roadmap-2026-04-30.md)
  - [Gate 4 评估与完美实现路线图（2026-05-15）](g4-assessment-and-roadmap-2026-05-15.md)
  - [质量基线](../QUALITY_BASELINE.md)
  - [开发 TODO](../../todo.md)

---

## 0. 2026-05-16 实现更新

当前仓库已经补上第一版正式实现：

1. execution loop 已落地 restart controller，不再只记录 `restartMessage`。
2. `restart snapshot`、`carry-forward package`、`context.restart.requested/completed` 事件与 `runtimeMetrics` 已进入正式 runtime 路径。
3. 评测侧已新增 `evalsuite_g4_window_restart_stress` / `corepack pnpm eval:g4:window-stress`，并批准使用 `deepseek_direct / deepseek-v4-pro` 与 `longcat / LongCat-2.0-Preview` 作为正式 stress provider（保留 `LongCat-Flash-Lite` 作为对照项）。
4. 2026-05-15 的正式 live run `evalrun_1160dc08b84e4b6e8268` 已补上 LongCat / DeepSeek 的首轮 stress 证据：两条 provider 路径都在 `effectiveContextWindow=120` 下完成 `restartCount=100`、`windowIndex=101`、`restartSuccessRate0_1=1.0`。
5. 2026-05-16 的正式 LongCat real-task parity run `evalrun_590eca26a63247308373` 给出了第一条结构性真实任务对照证据：同一条 repo-wide 任务在 `64k` 与 `128k` 两档窗口下都通过了当时的 scorecard 口径，`cumulativeWindowSpanTokens` 约为 `4.10M`。
6. 但同日晚的保留日志重跑 `evalrun_941c8b8ca2204966812d` 已确认：这条证据只足以证明 restart 技术闭环，不足以证明最终交付 parity；恢复态 prompt contract 仍会把输出拉成 planning stub。
7. 因此，仓库内当前还缺的已经不只是“扩到更多 provider”，还包括把记忆树主体、work tree continuity、恢复态 prompt contract 和 goal-level acceptance 一起补齐。

---

## 1. 先给结论

1. **理论上已经支持。** 当前项目的核心研究并不把上下文窗口当作真正的记忆边界，而是把记忆树当作长期记忆主体，把动态加载、压缩、裁剪和恢复当作长任务成立的前提。
2. **工程主路径只闭合到了 restart 技术层。** 当前仓库已经有正式的多次窗口重启控制器、restart snapshot、carry-forward package、runtimeMetrics 和官方 stress suite 入口；LongCat / DeepSeek 的首轮 live stress 证据也已经落下。但保留日志重跑说明，真实任务 parity 仍只证明了 restart 技术闭环，尚未证明交付闭环。
3. **因此应当把它提升为当前第一优先级。** Gate 1 到 Gate 4 的正式基线已经闭合，当前最关键的不再是多补几个场景或继续清理非阻塞技术债，而是把“伪无限上下文窗口”从理论方向补成正式运行时能力和正式评测能力。
4. **评测上不能直接证明“无限次”，但可以证明“受控多次”。** 正确做法不是盲目追更长 prompt，而是手动限制有效上下文窗口，迫使系统在同一任务上完成 100 次窗口重启/压缩，再与更长上下文窗口的 reference run 做结果对比。
5. **最终目标不是更大的窗口数字，而是相同的任务效果。** 这条路线的目标仍然是：短上下文窗口路径与长上下文窗口路径在同一 acceptance contract 下得到相同结论，差异主要允许出现在时延与成本，而不是最终质量和交付完整性。当前的问题正是这件事还没有被证明。

---

## 2. 当前理论为什么已经支持这条路线

### 2.1 PRD 的原始定位已经给出了方向

[世界树计划 PRD v0.1](../PRD-v0.1.md) 已经写明：

1. 动态加载记忆可以缓解上下文窗口限制。
2. 对上下文进行裁剪与压缩可以提升长任务的持续执行能力。
3. `G1` 的目标就是“让 Agent 的有效记忆范围超出当前上下文窗口”。
4. 记忆树是主数据，不让临时会话日志替代长期记忆。

这意味着项目从一开始就不是以“把所有东西都塞进单次上下文窗口”为目标，而是以“把真正的长期状态放在窗口之外”作为产品定位。

### 2.2 系统核心理念已经给出“伪无限”的理论基础

[系统核心理念](系统核心理念.md) 已经给出了更直接的理论表述：

1. 当任务被不断分解后，每次 token 生成所需的信息其实并不多。
2. 只要单次 token 生成所需的上文长度小于模型上下文窗口，模型就可以完成任务，无论这个任务整体有多长。
3. 因此系统应当让 LLM 动态加载记忆。
4. 在这套系统下，AI 的记忆范围不是上下文窗口，而是整个记忆树。

这套表述本质上已经等价于：**上下文窗口只是当前工作集，真正的长期状态在记忆树里。**

### 2.3 G4 长任务基线研究已经证明方向正确、闭环未完

[Gate 4 长任务与上下文窗口重启基线研究（2026-05-15）](g4-long-task-window-restart-baseline-2026-05-15.md) 已经把现状说清楚：

1. 当前仓库已经拥有长任务 restart 议题的前置基座与观测能力。
2. 但多次上下文窗口重启还没有形成正式执行闭环。
3. 现有官方 LongCat longform 样本还远未触达窗口级压力。

所以结论不是“理论不支持”，而是“理论支持且工程基座已具备，但还缺最后一段最关键的 runtime/controller/eval 闭环”。

---

## 3. 这里所说的“伪无限上下文窗口”到底是什么

这不是神秘概念，而是一套很具体的运行时分工：

1. **记忆树**：持久主体，保存长期事实、来源、结构关系、压缩后的摘要与可恢复引用。
2. **work tree**：执行指针，表达当前任务处于哪一个执行节点、下一次恢复要从哪里继续。
3. **上下文窗口**：临时工作集，只放当前步骤真正需要的少量状态。
4. **context pruning / compression**：工作集整理机制，避免窗口被无关或低价值信息撑满。
5. **window restart**：当当前工作集接近上限时，生成 carry-forward package，把任务切到下一个窗口继续执行。

如果用硬件类比，这条路线就是：

1. 记忆树像主存与持久存储。
2. 上下文窗口像高速缓存与当前寄存工作集。
3. restart / compression 像缓存整理与工作集轮换。

所以“伪无限”并不是说模型真的拥有无限上下文，而是说：**系统可以通过可恢复的多窗口接续，让整体任务跨度在工程上不再受单一上下文窗口直接约束。**

---

## 4. 当前还剩什么

下面的缺口指的是“真实任务 parity 与 release 口径”，不是“仓库内完全没有实现”。

### 4.1 缺真实任务 parity 证据

当前仓库已经有正式 restart loop、restart snapshot 与 runtimeMetrics，首轮 live stress 和首条 LongCat real-task parity 也已经通过，但仍缺下面这些 release 级证据：

1. 同一真实任务在多 provider 下的正式对照样本，而不仅是 LongCat 单 provider。
2. `finalAcceptanceParity0_1` 与 `deliveryEquivalence0_1` 的冻结门槛。
3. 不同窗口长度与不同 provider 下质量差值的稳定口径。
4. 将 parity 结论写回正式 README / 研究文档 / release 证据索引的最终收口。

### 4.2 缺“记忆树主体”路线的真实任务对照

当前已有的 provider matrix、longform 样本与 window stress，只能说明“restart 机制已闭环、短窗口压力可复跑”，还不能说明“真实全局工作在不同窗口长度下能得到同样结果”。要证明这一点，必须补齐专门的真实任务对照：

1. 任务本身必须对当前仓库有真实价值，而不是重复填充的长 prompt。
2. short-window 与 long-window 必须共享同一 acceptance contract 与同一正式产出物。
3. 观测 carry-forward 是否带来计划漂移、证据丢失和交付退化。

### 4.3 缺“第一优先级”级别的项目口径

当前 README 和 todo 仍然把“维持 G4 基线 + 清理技术债”放在更显眼的位置。这与当前项目的真实关键任务已经不一致。真正该优先做的是：

1. freeze restart protocol
2. 实现 restart controller
3. 建立 100 次受控窗口轮换评测
4. 让短窗口与长窗口在相同任务上达到相同结论

---

## 5. 从今天起的正式优先级调整

从 2026-05-16 起，建议把项目执行锚点明确改成：

> **在维持 Gate 4 正式基线不回退的前提下，把“伪无限上下文窗口 / Gate 4 长任务完美实现”提升为当前第一优先级。**

这意味着优先级顺序应当变成：

1. 第一优先：restart protocol、restart controller、carry-forward package、work tree continuity、长任务观测。
2. 第二优先：100 次窗口重启/压缩与长窗口 reference 的正式对比评测。
3. 第三优先：在上述基础上继续补 provider matrix 长任务样本。
4. 最后才是前端 SDK 大文件拆分等非阻塞技术债。

同时也意味着下面这些事都不应压过这条主线：

1. 继续扩更多应用场景。
2. 提前启动 Gate 5 的自我优化主线。
3. 先做与长任务闭环无关的结构性清理。

---

## 6. 正式评测应该怎么做

### 6.1 核心原则

因为“无限次”无法直接评测，正式评测应该采用“**受控多次**”来逼近：

1. 手动限制有效上下文窗口，而不是直接依赖模型原生最大窗口。
2. 在同一任务上，强制系统经历大量 context pruning / window restart。
3. 再用更长上下文窗口跑同一任务作为 reference。
4. 比较两条路径的最终 acceptance 结果和交付质量，而不是只比较 token 数。

### 6.2 官方 stress 口径建议

建议冻结一条专门的 stress 口径：

1. 同一任务链必须经历 **100 次上下文窗口重启或压缩轮换**。
2. short-window 路径的 `effectiveContextWindow` 应由运行时显式限制，而不是让 provider 自由使用大窗口掩盖问题。
3. reference 路径使用更长上下文窗口或更宽松阈值，作为质量对照。
4. 两条路径必须共享同一 acceptance contract、同一 work tree 目标和同一交付要求。

### 6.3 关键指标

| 指标 | 含义 | 建议口径 |
|------|------|----------|
| `effectiveContextWindow` | 人为限制后的有效窗口大小 | 作为 stress 条件固定写入 artifact |
| `restartCount` | 正式窗口重启次数 | stress 口径固定目标为 `100` |
| `compressionCount` | 正式压缩次数 | 与 restart 一起统计，不允许用“只压缩不重启”绕开问题 |
| `cumulativeWindowSpanTokens` | 整个任务累计跨过的窗口跨度 | 至少覆盖 `100 × effectiveContextWindow` 量级 |
| `maxContextLengthTokens` | 任一窗口内的最大上下文占用 | 必须持续低于 hard restart 阈值 |
| `restartSuccessRate0_1` | 每次 restart 是否成功接续到下一窗口 | 目标为 `1.0` |
| `finalAcceptanceParity0_1` | short-window 与 long-window 是否得到相同验收结论 | 目标为 `1` |
| `deliveryEquivalence0_1` | short-window 与 long-window 是否满足同一交付 contract | 目标为 `1` |
| `qualityDeltaToLongWindow0_100` | 相对长窗口路径的质量差值 | 目标是尽量接近 `0`；正式门槛在实现 3 轮稳定复跑后冻结 |
| `carryForwardLossCount` | 因摘要、引用或状态丢失导致的显式断裂次数 | 目标为 `0` |

### 6.4 通过标准的本质

真正的通过标准不是“总 token 很大”，而是下面两条同时成立：

1. 短窗口路径与长窗口路径在同一任务上得到相同 acceptance 结论。
2. 质量差异主要表现在时延与成本，而不是最终效果、证据完整性和交付连续性。

换句话说，项目真正要证明的是：

> **短上下文窗口的任务效果与长上下文窗口相同。**

---

## 7. 已落地项与下一步

1. **已落地**：在 runtime/domain/spec 层补齐 `windowIndex`、`restartCount`、`cumulativeWindowSpanTokens`、`carryForwardLossCount` 等正式字段。
2. **已落地**：execution loop 中的 restart controller、restart snapshot、carry-forward package 与自动 requeue/resume 已形成技术闭环。
3. **已落地**：`restartCount`、`compressionCount`、`cumulativeWindowSpanTokens`、`carryForwardLossCount` 已写入正式 response artifact 与 provider summary。
4. **已落地**：`evalsuite_g4_window_restart_stress` 与 `corepack pnpm eval:g4:window-stress` 已进仓，并批准使用 LongCat / DeepSeek 正式复跑。
5. **已落地**：`evalsuite_g4_real_task_window_parity` 与 `corepack pnpm eval:g4:real-task-parity` 已进仓，并完成了 LongCat `64k` vs `128k` 的 4M 真实任务结构性对照。
6. **已确认的新问题**：保留日志重跑证明当前恢复态仍依赖 snapshot summary handoff，而不是记忆树主体；work tree continuity 和 goal-level delivery parity 尚未成立。
7. **下一步**：先修正恢复态 prompt contract、记忆树/工作树恢复语义与强验收口径，再做 DeepSeek 复制和 multi-provider parity 门槛冻结。

---

## 8. 最终判断

一句话结论：

> **当前项目的理论研究仍然支持“记忆树为主体、上下文窗口为工作集”的伪无限上下文路线；但保留日志重跑已经证明，仓库当前落地的是 restart 技术闭环，而不是记忆树主体驱动的交付闭环。接下来要完成的不只是多 provider 复跑，还包括修正恢复态 contract 本身。**

因此，从今天开始，把这条路线提升为项目第一优先级是合理且必要的。
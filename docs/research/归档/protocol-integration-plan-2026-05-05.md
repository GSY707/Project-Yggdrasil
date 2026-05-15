# 世界树计划 · G1/G2 推进与新协议纳入整理（2026-05-05）

- 文档状态：Working Draft
- 日期：2026-05-05
- 口径说明：
  - 本文中的 G1 / G2 指路线图中的 Gate 1 / Gate 2。
  - 它们不等同于 PRD 顶层长期目标里的 G1=记忆树内核、G2=可恢复任务运行。
- 关联文档：
  - [G1 阶段闭合评估报告（2026-05-04）](g1-stage-assessment-2026-05-04.md)
  - [G2 阶段推进记录（2026-05-04）](g2-stage-progress-2026-05-04.md)
  - [Gate 2 差距测试与成因分析（2026-05-04）](g2-gap-assessment-2026-05-04.md)
  - [通向最终目标的路线图](final-goal-roadmap-2026-04-30.md)
  - [工作树协议（研究草稿 v0.1）](work-tree-protocol-draft-2026-05-05.md)
  - [超图推理协议（研究草稿 v0.1）](hypergraph-reasoning-protocol-draft-2026-05-05.md)
  - [Task Takeover Protocol v0.1](../specs/task-takeover-protocol-v0.1.md)
  - [运行时与工具数据规格 v0.1](../specs/runtime-domain-data-spec-v0.1.md)
  - [记忆与建树数据规格 v0.1](../specs/memory-domain-data-spec-v0.1.md)

## 1. 一句话结论

- G1 当前不是能力卡住，而是证据未补齐：live smoke 已恢复，剩余动作是 3 张真实任务卡在同一 provider 下重跑并补齐任务级 supplier-side 证据。
- G2 当前不是协议没想清，而是稳定复现证据不足：重复执行样本、复杂文件拆分固定回归、计划质量与返工率真实样本、首响观测都还没补齐。
- 新协议不改变这条主线：工作树协议进入 Gate 2 的下一版结构化升级，超图推理协议明确延后到 Gate 3 之后。

## 2. 当前状态快照

| 维度 | 当前状态 | 当前判定 | 对推进的含义 |
| --- | --- | --- | --- |
| G1 | 原闭合声明已暂停；live smoke 已恢复；3 张真实任务卡待在同一 provider 下重跑 | 待真实任务复核 | 先补任务级证据，不再把焦点放在“provider 能不能打通” |
| G2 | 出口标准 0 / 3 闭合；任务接管协议与评分链已接通 | 进行中 | 先证明重复执行稳定，再扩大正式协议边界 |
| 工程健康度 | pytest、web:typecheck、eval:regression、eval:m8:live 已通过 | 健康 | 当前可以直接冲证据闭环，不需要先返工基础设施 |
| 新协议 | 工作树有明确 Gate 2 承接面；超图推理仍是 research draft | 已分流 | 两份协议不能同权并进，必须分 gate 推进 |

## 3. 当前为什么会卡住

### 3.1 G1 的真实瓶颈

G1 当前剩下的不是“能力没做出来”，而是“真实任务级证据还没有按新口径补齐”：

- `eval:m8:live` 已证明真实 supplier-side 调用链恢复。
- 现有 3 次内部试跑已经有评分表、截图、trace 和工件索引。
- 还缺的是 `YGG-CI-01`、`YGG-CG-01`、`YGG-CG-03` 在同一 live provider 下的任务级重跑资产。

因此，G1 的推进动作应收敛为“补证据”，而不是重新讨论是否继续补基础设施或扩新能力。

### 3.2 G2 的真实瓶颈

G2 当前的主要缺口有 4 类：

1. 重复执行证据不足。
   - 当前只有 3 条内部试跑记录，不能证明“同一批窄路径任务可稳定复现”。
2. 复杂文件拆分还没有进入固定回归。
   - 实际代码已经做过拆分，但还没有变成正式任务卡、固定样本和回归入口。
3. 质量指标已能记账，但还不能判质。
   - `planQualityScore0_100`、`reworkCount`、`reworkRate` 已接通 schema 与汇总链，但冻结样本未回填。
   - 首 token / 首次有效输出级别的首响观测仍未正式补齐。
4. 文档与看板存在轻微漂移。
   - 部分“未拆分”技术债在代码层已完成，真正缺口是“正式回归化”和“任务级样本化”。

## 4. 新协议如何影响 G1/G2 推进

### 4.1 工作树协议

工作树不是从零开始的新方向，而是 Gate 2 现有链路的结构化升级：

- Agent Runtime Protocol 已有“我要干什么”根分支。
- runtime-domain-data-spec 已要求 Task 能映射到 execution root 或等价的工作树入口。
- Task Takeover Protocol 已正式固化 objective / constraints / plan / verification / delivery。

因此，工作树当前应承担的角色是：

- 作为 Gate 2 下一版 Task Takeover 的设计输入。
- 作为 safe-stop / resume、context pruning、阶段性重启共享的数据对象来源。
- 作为计划质量、返工率、阶段态观测的结构化前提。

当前不应做的事也要写清：

- 不在 G2 复跑证据还不足时，把工作树升级成所有任务的强制硬约束。
- 不把所有记忆节点和关系提前改写成工作树结构。
- 不在正式对象没定稿前，先把 PromptProfile 阶段字段写死。

### 4.2 超图推理协议

超图推理当前只有研究价值，没有 Gate 2 需要的正式承接面：

- memory-domain-data-spec 目前只有 `Edge.reason`，没有关系推理工件或关系集合查询对象。
- relation-discovery 现在是模块方向，不是正式 relation reasoning protocol。
- Gate 2 当前的主目标仍是窄路径稳定复现，不适合同期扩大到高阶关系推理。

因此，超图推理的正确位置是：

- 现在保留为 research draft。
- Gate 3 再和 relation-discovery、memory-domain spec、复杂关系推理评测一起收口。
- 在 Gate 2 没闭合前，不写进出口标准，也不改成正式运行时硬约束。

## 5. 接下来的推进原则

1. 先补证据，再扩协议。
2. 先闭合窄路径，再扩场景和应用面。
3. 先让正式对象落地，再改 Prompt 元数据和文风层规则。
4. 先把一次性成功变成固定回归，再宣称能力已经产品化。
5. 每次协议升级都必须对应可观测收益，而不是只增加抽象层。

## 6. 明确推进顺序

| 顺序 | 目标 | 核心动作 | 交付物 | 备注 |
| --- | --- | --- | --- | --- |
| 1 | 先补 G1 复核证据 | 在同一 live provider 下重跑 `YGG-CI-01`、`YGG-CG-01`、`YGG-CG-03`，补 supplier-side 任务级证据，并更新 scorecard、trace、工件索引 | 3 张任务卡的新一轮 live 证据资产 + G1 复核结论 | 这是当前最短路径，不需要新增协议 |
| 2 | 建立 G2 重复执行基线 | 连续 3 轮重复执行 `YGG-CG-01` 与 `YGG-CG-03`，产出通过率、人工接管中位数、澄清回合、恢复成功率汇总 | 一版可比较的 G2 基线报告 | 先证明稳定复现，再谈“更聪明” |
| 3 | 补齐 G2 判质能力 | 在复跑样本中回填 `planQualityScore0_100`、`reworkCount`、`reworkRate`；补复杂文件拆分固定回归；补首响观测与实测 P50 / P95 | 质量基线回写、固定回归样本、自检与交付模板 | 这一层完成后，G2 才开始接近“产品化” |
| 4 | 打开工作树正式修改窗口 | 先提交 RFC 或等价协议变更说明，再把工作树纳入 Task Takeover 与 runtime-domain-data-spec | 协议变更包、字段草案、工件位置定义 | 只有在步骤 1 到 3 有证据后才启动 |
| 5 | 为 Gate 3 准备超图推理升级条件 | 固定 relation-discovery、memory-domain spec 与评测样本三者的收口条件 | Gate 3 升级前提清单 | 不进入当前 Gate 2 主线 |

## 7. 正式协议修改顺序

当且仅当 G1 复核补齐、G2 初版重复执行基线成立后，再打开正式协议修改窗口。推荐顺序如下：

1. 先走 RFC 或等价的公共协议变更评审。
   - 这一步不是形式化动作，而是为了避免任务接管、运行时数据规格和 Prompt 字段再次脱节。
2. 先改 [../specs/task-takeover-protocol-v0.1.md](../specs/task-takeover-protocol-v0.1.md)
   - 新增工作树子结构。
   - 明确工作树在目标解析之后、计划生成之前构建。
   - 明确阶段性重启、返工检测和优先图如何进入协议工件。
3. 再改 [../specs/runtime-domain-data-spec-v0.1.md](../specs/runtime-domain-data-spec-v0.1.md)
   - 增加任务分解对象、优先边对象和恢复锚点对象。
   - 让 safe-stop / resume、context pruning 和 execution root 共享同一套正式引用面。
4. 然后再动 Prompt 和评分链。
   - Prompt 侧只在正式对象存在后再补阶段态，例如 `planning`、`executing`、`recovering`、`restarting`。
   - scorecard 和评测链补计划质量、返工率、重启次数和工作树覆盖率等指标。
5. 最后处理超图推理的正式承接。
   - 在 Gate 3 再改 [../specs/memory-domain-data-spec-v0.1.md](../specs/memory-domain-data-spec-v0.1.md) 或新增 relation reasoning spec。
   - 同步补 relation-discovery 的查询、工件和评测，而不是单改 `Edge.reason`。

## 8. 明确暂不做的事

- 不把超图推理写进 Gate 2 出口标准。
- 不在当前阶段扩大 memory-domain spec 的基础 Edge 结构。
- 不在正式 spec 之前先改 PromptProfile 字段，避免数据对象和 Prompt 元数据脱节。
- 不在 G2 还没拿到重复执行证据时，同时重开新场景扩展或新大模块。
- 不让工作树和超图推理变成新的大而全抽象；每次只推进与当前 gate 直接相关的一段。

## 9. 当前执行口径

把这次整理压缩成一句执行话术，就是：

> 先把 G1 的真实任务级证据补齐，再用重复执行、固定回归和质量指标把 G2 做成“可证明的稳定复现”；工作树只服务 Gate 2 下一版结构化升级，超图推理明确锁到 Gate 3 之后。
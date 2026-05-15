# Task Takeover Protocol v0.1

- 文档状态：Candidate
- 版本：v0.1
- 日期：2026-05-15
- 关联文档：
  - [Agent 运行时协议 v0.1](agent-runtime-protocol-v0.1.md)
  - [工作树协议 v0.1](work-tree-protocol-v0.1.md)
  - [运行时与工具数据规格 v0.1](runtime-domain-data-spec-v0.1.md)
  - [Gate 2 闭环报告（2026-05-15）](../research/g2-closeout-2026-05-15.md)
  - [Gate 3 正式闭环报告（2026-05-15）](../research/g3-closeout-2026-05-15.md)

## 1. 目标

把 Gate 2 所要求的“任务接管协议”从路线描述提升为正式协议对象和正式运行时链路。

本协议覆盖 6 个阶段：

1. 目标解析
2. 约束抽取
3. 计划生成
4. 执行
5. 验证
6. 交付

协议的责任不是替代 Prompt，而是把这些阶段的输入输出结构、持久化点、观测指标和回归验证固定下来。

## 2. 协议对象

当前实现使用以下正式对象：

- `TaskTakeoverProtocol`
  - 任务接管的主对象，包含目标、约束、计划、交付、验证、指标、模块来源和 hook trace。
- `TaskTakeoverAmbiguity`
  - 接管时发现的歧义项，区分 required / non-required。
- `TaskTakeoverConstraint`
  - 显式约束，覆盖 objective / scope / budget / runtime / tooling / delivery / policy / environment。
- `TaskTakeoverPlanStep`
  - 正式计划步骤，带 phase、status、依赖关系和预期证据。
- `WorkTreeNode`
  - 计划步骤在 runtime 中的正式执行节点投影，带 phase、status、约束引用和 recovery anchor。
- `WorkTreeProtocol`
  - 正式工作树对象，记录 root objective、当前节点、整体状态和 entropy budget。
- `TaskTakeoverDeliverySection`
  - 结构化交付片段，固定为 `result`、`evidence`、`pending`、`incomplete` 四类。
- `TaskTakeoverVerificationItem`
  - 验证项，区分 `passed`、`warning`、`failed`、`not-run`。
- `TaskTakeoverMetrics`
  - 当前协议级指标集合，至少包括：
    - `planQualityScore0_100`
    - `reworkCount`
    - `reworkRate`
    - `clarificationNeeded`
    - `deliveryCompletenessScore0_100`
    - `verificationPassRate`

## 3. 运行时接线

### 3.1 Hook 名称

当前协议通过以下 hook 暴露：

- `task.takeover.parse-objective`
- `task.takeover.extract-constraints`
- `task.takeover.generate-plan`
- `task.takeover.verify-delivery`
- `task.takeover.format-output`

### 3.2 当前接线位置

主 Agent 运行时必须按下面顺序接入：

1. 在 RootMount 建立之后、模型路由决策之前，生成 `TaskTakeoverProtocol`。
2. 将协议对象注入 request，并作为 Prompt 编译输入的一部分。
3. 在模型完成后、执行记录写入前，对交付内容进行结构化格式化与验证。
4. 将最终协议与 work tree 一起落盘为独立工件，并将其摘要挂到执行记录的来源注解里。

### 3.3 工件要求

同一次主 Agent 运行，以下工件必须能够看到同一份接管协议：

1. 编译后的 Prompt 元数据
2. LLM request transcript
3. 运行时返回结果
4. `runtime/takeover/*.json` 工件
5. 执行记录节点的 source annotation

## 3.4 Work tree 约束

Gate 3 以后，`TaskTakeoverProtocol` 不再只有 plan 文本，而是必须同时带上 `workTree`：

1. work tree 必须由 objective / constraints / plan 派生，而不是临时自由生成。
2. runtime 完成时必须把 work tree 状态同步到 `completed`。
3. 若任务进入 pause/resume 或 repair，work tree 必须保留可恢复锚点。

## 4. 与 Prompt 的分工

Prompt 负责：

- 行为准则
- 交付风格
- 工具使用偏好
- 场景身份 overlay

任务接管协议负责：

- 目标和约束是否被结构化固定
- 计划步骤是否被生成并可追踪
- 验证和交付是否被结构化检查
- 指标是否能被正式采集与复盘

因此，Prompt 可以影响表现形式，但不能替代协议对象。

## 5. Gate 3 增量出口标准

在 Gate 2 已闭合的基础上，Gate 3 额外要求以下 5 条同时成立：

1. `TaskTakeoverProtocol` 必须正式包含 `workTree`，且 `workTree` 能在 prompt、request、result 和 artifact 中被同一版本追踪。
2. runtime 完成或恢复后，work tree 状态必须和任务正式状态同步。
3. work tree 必须为 pause/resume 或 repair 提供恢复锚点，而不是只靠自然语言续跑。
4. 协议指标与 work tree 状态必须能在正式 live task pack 中被观测，而不是只在离线测试中存在。
5. 协议对象扩展不能破坏既有 Gate 2 回归与复杂文件拆分固定样本。

## 6. 当前实现边界

当前版本已经实现：

- 正式 contracts
- 正式 hook 名称
- `task-takeover` 模块
- 主循环接线
- Prompt 注入
- 协议工件落盘
- 协议摘要挂入执行记录
- work tree 正式对象与 completed 状态同步

Gate 3 已闭合；后续扩展不再是“是否有正式对象”，而是“如何把 work tree、返工率和跨 provider 质量纳入更固定的 nightly / release baseline”。

## 7. 后续扩展约束

为了避免 Gate 3 / Gate 4 返工，后续扩展必须遵守以下约束：

1. 不允许把新的接管阶段回写成主循环硬编码字符串分支；优先走 hook 和结构化对象。
2. 不允许把计划质量和返工率只记在 Markdown 或手工报告里；必须进入正式工件或评分链。
3. 不允许把复杂文件拆分继续当一次性技术债处理；必须进入任务类型与固定回归集。

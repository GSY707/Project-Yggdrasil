# Task Takeover Protocol v0.1

- 文档状态：Candidate
- 版本：v0.1
- 日期：2026-05-04
- 关联文档：
  - [Agent 运行时协议 v0.1](agent-runtime-protocol-v0.1.md)
  - [运行时与工具数据规格 v0.1](runtime-domain-data-spec-v0.1.md)
  - [Gate 2 闭环报告（2026-05-15）](../research/g2-closeout-2026-05-15.md)
  - [Gate 2 差距测试与成因分析（归档）](../research/归档/g2-gap-assessment-2026-05-04.md)

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
4. 将最终协议落盘为独立工件，并将其摘要挂到执行记录的来源注解里。

### 3.3 工件要求

同一次主 Agent 运行，以下工件必须能够看到同一份接管协议：

1. 编译后的 Prompt 元数据
2. LLM request transcript
3. 运行时返回结果
4. `runtime/takeover/*.json` 工件
5. 执行记录节点的 source annotation

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

## 5. Gate 2 出口标准

Gate 2 的“任务接管协议”闭合，至少要求以下 5 条同时成立：

1. 协议覆盖：主 Agent coding 窄路径任务每次运行都能生成 `TaskTakeoverProtocol`，其中必须包含 objective、constraints、plan 三部分。
2. 工件覆盖：编译 Prompt、request transcript、运行时结果和执行记录都能引用同一份协议对象或其工件。
3. 交付覆盖：每次运行都能产出 `result / evidence / pending / incomplete` 四类交付段，并给出验证项和协议指标。
4. 复跑覆盖：同一批窄路径任务至少重复执行 3 轮，能够观察通过率、人工接管中位数、澄清回合和协议指标是否稳定。
5. 回归覆盖：至少一个“复杂文件拆分”样本进入固定回归集，并要求协议对象全程可追踪。

## 6. 当前实现边界

当前版本已经实现：

- 正式 contracts
- 正式 hook 名称
- `task-takeover` 模块
- 主循环接线
- Prompt 注入
- 协议工件落盘
- 协议摘要挂入执行记录

当前仍未闭合的部分：

- live 任务卡中的协议指标仍需通过同一 provider 复跑补足真实样本
- 复杂文件拆分回归样本已进入固定回归集：`evalsuite_regression_g2_controlled_autonomy`
- 重复执行样本仍不足以证明稳定复现

## 7. 后续扩展约束

为了避免 Gate 3 / Gate 4 返工，后续扩展必须遵守以下约束：

1. 不允许把新的接管阶段回写成主循环硬编码字符串分支；优先走 hook 和结构化对象。
2. 不允许把计划质量和返工率只记在 Markdown 或手工报告里；必须进入正式工件或评分链。
3. 不允许把复杂文件拆分继续当一次性技术债处理；必须进入任务类型与固定回归集。

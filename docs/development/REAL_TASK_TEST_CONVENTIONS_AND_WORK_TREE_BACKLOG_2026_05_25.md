# 真实任务测试约定与工作树后续任务拆分（2026-05-25）

## 1. 目的

这份文档做两件事：

1. 固定后续真实任务测试题的默认出题约定，避免继续把“项目内定向提示词”当成通用真实任务。
2. 把当前工作树后续工作拆成可以执行的任务包，明确哪些适合一起做，哪些必须前后依赖。

## 2. 新增约定

### 2.1 默认测试任务约定

- 测试任务尽可能与本项目业务本身无关，不要把“解释本仓库当前实现”“总结本仓库某条内部路线”当作默认真实任务。
- 任务描述只给一个目标，不在任务文本里内嵌步骤规划、章节顺序、执行顺序或完成路径。
- 规划必须由 agent 在运行时自己生成，测试合同不应替 agent 提前写好 plan。
- 除正式证据集、验收口径和必要边界外，不向任务输入注入额外的“应该先做 A 再做 B”的指令。

### 2.2 这条约定的含义

- 当前默认真实任务入口是 `g4-real-task-web-research-default`，后续应继续扩大“外部题面 + 自主规划”的覆盖面。

- 任务目标可以利用本仓库提供的工具、协议和环境来完成。
- 但任务本身应尽量像一个外部真实工作目标，而不是“让 agent 复述本项目自我说明”。
### 2.3 明确例外

下面这类 case 可以不遵守“只给单目标、不预置规划”的默认约定，但必须显式标注为 harness 或 debug case：

- 专门验证 work tree / takeover / pause-resume / sibling continuation / failed-leaf bubble 的 runtime 语义测试。
- 专门验证 provider/tool policy 继承、窗口恢复或 prompt/retrieval 指针一致性的底层调试任务。

原因：这类 case 的目的本来就不是评测 agent 的自然规划能力，而是验证 runtime 是否按协议推进。

## 3. 对当前工作树测试线的影响

### 3.1 哪些 case 属于默认真实任务

- `g4-real-task-web-research-default` 已成为默认真实任务入口，后续应继续扩大“外部题面 + 自主规划”的覆盖面。

### 3.2 哪些 case 属于例外 harness

- `g4-real-task-work-tree-debug` 目前属于明确例外：它故意预置嵌套 `takeoverProtocol` 和分步工作树，用来验证 `child-1 -> child-2 -> root`、leaf failure bubble、approval 停点等 runtime 语义。
- 这条线现在可以继续保留，但应在命名和文档中明确它是“runtime debug harness”，不是默认真实任务模板。

### 3.3 当前 baseline

- 最新 live baseline 是 `evalrun_a1259708b3a14b8a96c1`。
- 这条 baseline 已证明 short/long 两条路径都能收口到 `awaiting-approval`，且 `workTreeContinuity0_1 = 1`。
- 后续不应再重复消耗时间去证明同一条 `child-1 -> child-2 -> root` continuity 已经成立，而应转向剩余差距。

## 4. 任务分类

### 4.1 A 类：测试合同与题目设计

目标：把“真实任务”与“runtime debug harness”正式分开。

包含任务：

- A1. 为默认真实任务固定新约定：单目标、无内嵌规划、尽量与项目业务弱相关。
- A2. 重新设计一组更外部化的真实任务样本，替换当前过度 repo-specific 的题目。
- A3. 在 suite contract verifier 中增加对“内嵌规划/多目标/过强 repo 自指”的拒绝检查。
- A4. 明确 `minimal-workset` 与 `work-tree-debug` 的职责边界：前者评测真实任务，后者评测 runtime 语义。

### 4.2 B 类：工作树结果门禁与交付语义

目标：把“runtime 已推进到 root/awaiting-approval”与“delivery verifier 仍判 incomplete”之间的漂移补平。

包含任务：

- B1. 补齐 `delivery.evidence / pending / incomplete` 的正式生成逻辑。
- B2. 决定这些字段是否升级为 hard gate，而不是 advisory verifier。是
- B3. 统一 child completion summary 的格式，避免一个 child 是过程描述、另一个 child 是结论摘要。
- B4. 校准 `deliveryCompletenessScore0_100`，避免两个子节点都完成后根节点仍长期停在 25%。
- B5. 把 approve/revision live 链路纳入同一条真实任务 work-tree suite。

### 4.3 C 类：工作树模型与实际运行对齐

目标：让工件能稳定说明 runtime 确实按模型切节点、切栈、恢复和上浮。

包含任务：

- C1. 提供更直观的节点切换轨迹工件，减少“只能靠拼 JSON 推断”的现状。
- C2. 固化 `currentNodeId / topFrameId / Working_Node / memoryRetrievalState.workTreeNodeId` 的一致性验收。
- C3. 为返工/恢复补充明确根因字段，而不是只留下 `reworkRate`。
- C4. 补齐 mixed outcome 场景的正式汇总策略：一个 child failed、另一个 completed 时，root 应如何收口。

### 4.4 D 类：前缀缓存与 continuation cache

目标：把协议里的 `preserve-prefix` 从“声明存在”推进到“真实命中”。

包含任务：

- D1. 为 `WorkContextFrame.prefixCacheKey` 生成真实缓存键，而不是长期为 `null`。
- D2. continuation 时保留可复用前缀，不重新编译 root 到父节点的完整 prompt。
- D3. 在 live runtime metrics 中区分 cache hit / cache write / non-cache input，并把它们变成正式验收证据。
- D4. 为 short/long live suite 增加“缓存命中链路已生效”的验收口径。
- D5. 明确 provider 侧 prefix cache 和 runtime continuation cache 的边界，避免把两者混为同一实现。

### 4.5 E 类：工具策略与 provider 漂移硬化

目标：把 continuation 运行条件冻结到足以承接缓存和稳定复跑。

包含任务：

- E1. 在 `allowToolExecution=false` 时，runtime 级硬拦截模型自发 tool call，而不是只靠 prompt 隐藏工具描述。
- E2. 持续保证 continuation 继承 `candidateModels / allowToolExecution / temperature / maxTokens` 等关键约束。
- E3. 为 provider/tool policy 漂移增加专门回归，避免后续缓存调试被其它漂移噪音污染。

### 4.6 F 类：分析器与观测面

目标：把当前“人工拼工件”的读法产品化。

包含任务：

- F1. 为 LLM 工作分析器增加工作树调试模式摘要卡。
- F2. 在分析结果中直接展示节点切换时间线、frame 变更、continuation 原因和 approval 停点。
- F3. 把缓存命中、child bubble、mixed outcome 汇总到单一视图里。

## 5. 适合一起做的任务包

### 5.1 任务包 P1：测试合同重构

适合一起做：A1、A2、A3、A4。

原因：这些任务都在定义“未来到底用什么题目来测”，应一次性把默认真实任务与专用 harness 的边界讲清楚。

交付物：

- 新的真实任务出题约定。
- 重新整理后的 suite contract。
- 对应 contract verifier 回归测试。

### 5.2 任务包 P2：工作树门禁闭环

适合一起做：B1、B2、B3、B4、B5。

原因：这些任务都在修“为什么 runtime 看起来已经完成，但 verifier/approval 语义仍然不闭合”。拆开做会反复改合同。

交付物：

- `delivery.*` 字段闭环。
- approve/revision live 闭环。
- 更稳定的 child summary 和 completion score。

### 5.3 任务包 P3：缓存闭环

适合一起做：D1、D2、D3、D4、D5。

原因：前缀缓存和 continuation cache 只有在“键生成、运行时复用、指标记录、验收口径”一起落地时才有意义；单点改动无法证明真的生效。

交付物：

- 非空 `prefixCacheKey`。
- continuation 复用链路。
- live suite 中的缓存命中证据。

### 5.4 任务包 P4：稳定性硬化

适合一起做：E1、E2、E3。

原因：这些任务的共同目标是减少 continuation 复跑噪音，为缓存和 parity 验收提供稳定环境。

交付物：

- `allowToolExecution=false` 的 runtime 硬门禁。
- provider/tool policy 漂移回归。

### 5.5 任务包 P5：观测与分析

适合一起做：C1、C3、F1、F2、F3。

原因：这些任务共同改善“我们如何读懂一次 live run”，适合在 runtime 语义相对稳定后集中补。

交付物：

- 节点切换时间线。
- 返工原因工件。
- 工作树调试专用 analyzer 视图。

## 6. 建议执行顺序

### 第一阶段

- 先做 P1。

原因：如果默认真实任务约定不先固定，后面的 live suite 会继续混用“通用真实任务”和“专用 debug harness”，验收对象不稳定。

### 第二阶段

- 再做 P2。

原因：当前 runtime continuity baseline 已经过了，下一步最影响验收可信度的是 verifier 与 approval 语义漂移。

### 第三阶段

- 再做 P3。

原因：缓存闭环必须建立在 continuation 语义已经稳定、验收目标已经冻结的前提上；否则很难判断缓存收益是否真实。

### 第四阶段

- 做 P4。

原因：工具策略和 provider 漂移硬化会直接提升缓存与 parity 复跑的稳定性，但它本质上是护栏，不应先于验收口径本身。

### 第五阶段

- 做 P5。

原因：观测面改进重要，但它主要提升调试效率，不应阻塞语义闭环和缓存闭环。

## 7. 当前推荐的近期执行清单

如果只看接下来一轮，建议按下面顺序推进：

1. 先完成 P1，把“默认真实任务约定”和“work-tree debug harness 例外”冻结下来。
2. 紧接着完成 P2，把 `delivery verifier`、approval、child summary、completion score 的漂移收平。
3. 之后集中做 P3，把前缀缓存和 continuation cache 作为独立里程碑落地。

## 8. 完成标准

### 8.1 默认真实任务约定完成标准

- 至少有一组真实任务 case 满足：单目标、无内嵌规划、项目业务弱相关。
- 对应 contract verifier 会拒绝多目标、步骤化题面和显式规划 stub。

### 8.2 工作树闭环完成标准

- runtime 工件、delivery verifier 和 approval 状态不再互相矛盾。
- mixed outcome、sibling continuation、root approval 都有 live 证据。

### 8.3 缓存闭环完成标准

- live 工件里 `prefixCacheKey` 不再长期为 `null`。
- live evalrun 不再长期是 `cacheHitInputTokens = 0`。
- short/long continuation 链路能给出缓存命中证据，而不是只声明 `cachePolicy = preserve-prefix`。




# 本轮收口状态

P1 已收口。`g4-real-task-work-tree-debug.json` 现已补齐 `suiteRole=runtime-debug-harness`、`suiteRoleNote` 与例外约定；`tests/test_suite_contract_verifier.py` 的全量 suite 角色回归已通过。当前口径也已冻结为：`g4-real-task-externalized.json` 是默认真实任务入口，`g4-real-task-web-research-default.json` 只保留 legacy 参考。

P2 已收口。`task-takeover` 现在会正式生成并校验 `delivery.result / evidence / pending / incomplete` 四段，`delivery.pending` 与 `delivery.incomplete` 已升级为 hard gate；`tests/test_runtime_p2_delivery_gate.py` 现补齐“缺字段即 delivery-gate-blocked”与“同一多节点工作树链路里的 revision -> 复跑 -> approve”回归，`tests/test_runtime_p4_foundation.py` 继续锁住 child completion summary、mixed outcome 和 sibling/root 收口。

P3 已收口。缓存主实现与验收门禁保持不变，但协议文档现已单独冻结 provider prefix cache 与 runtime continuation cache 的边界：`prefixCacheKey`/`preserve-prefix` 负责 runtime continuation 语义，`cacheHitInputTokens`/`cacheWriteInputTokens` 才是 provider 侧真实命中证据。`g4-real-task-work-tree-debug.json` 与 `suite_cases_g4.py` 继续把两类证据都纳入正式验收。

P5 已收口。`docs/LLM_WORK_ANALYZER_USER_GUIDE.md` 现已把 work-tree debug 摘要卡、节点切换时间线、cache trace、child bubble 与 mixed outcome 固定成标准读法，不再要求操作者自己去拼 UI 字段语义。

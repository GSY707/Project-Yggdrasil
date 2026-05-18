# 记忆树与伪无限上下文窗口优化作战手册（2026-05-18）

## 执行状态更新（2026-05-18 晚）

相对于本手册最初版本，当前仓库已经完成第一轮基础设施收口：

1. runtime 已开始落每窗结构化 `window_execution_record`，并写入 `.yggdrasil/state/runtime/window-executions/`。
2. Langfuse generation metadata 已补入窗口执行摘要，不再只有 observation 文本链。
3. Langfuse 分析器已能补读本地 `runtime/window-executions` 工件，并输出结构化 JSON payload，不再只产 markdown。

但这仍然只是“分析基础设施第一轮完成”，还不是“记忆树主导执行”已经达成。当前最关键的剩余问题已经可以聚焦到：

1. carry-forward 仍是摘要包，不是执行指针包。
2. 官方评测仍未把 `workTreeContinuity0_1` 和 `minimalWorksetRatio0_1` 变成正式门禁。
3. canonical real-task case 仍然大量注入 `currentContextFiles/currentContextGlobs`，实验设计本身还不满足“窗口只保留最小工作集”。

## 1. 当前问题不是“还能不能跑”，而是“为什么会这样跑”

基于当前仓库内已有研究、真实任务复跑和 Langfuse 数据损耗审计，可以把现阶段的问题压缩成 3 句：

1. 现有评测更擅长证明 `restartCount`、`windowIndex`、`cumulativeWindowSpanTokens` 这些技术闭环指标，而不擅长解释每个窗口内 LLM 为什么还能继续完成任务。
2. 现有分析程序仍以 Langfuse observation 文本重建窗口骨架为主，缺少直接来自 runtime 的结构化窗口事实，因此会天然模糊。
3. 当前 carry-forward 仍偏自然语言摘要包，work tree 还没有完全成为 durable execution pointer，所以“记忆树为主体、窗口为最小工作集”还没有被真正冻结成工程现实。

这意味着下一阶段不能继续只看汇总分数或单次报告结论，而要切换到“窗口级因果分析 + 受控实验 + 收紧验收”的工作方式。

---

## 2. 优化目标需要重新定义

后续优化不应再以“跑通一次真实任务”或“出现一次高分”作为主目标，而应同时满足以下 4 条：

1. 记忆主存由记忆树承担。
   - 重启后继续执行时，主依据应是检索回来的结构化记忆、work tree 指针和任务合同，而不是上一窗口遗留的大段自然语言。
2. 当前窗口只承载最小子任务工作集。
   - 每个窗口只保留当前 objective、当前 focus、当前执行指针、必要证据和当前动作输入，不再大规模复挂 repo 原文。
3. 每个窗口都能解释“状态为什么正确延续”。
   - 必须能回答：这一窗口用了哪些记忆、沿哪个 work tree 节点继续、丢了什么、为什么还能得出当前结论。
4. short-window 与 long-window 的对照要以交付等价为准。
   - 是否等价，应由最终交付物和目标达成情况决定，而不是由 restart 成功率或平均分单独决定。

---

## 3. 为什么现有分析会模糊

### 3.1 现有分析以“文本重建”多于“状态读取”

当前主分析入口虽然已经能输出逐窗口报告，但它的主证据面仍然是：

1. Langfuse 的 input messages
2. Langfuse 的 output text
3. observation metadata
4. runtime 用户消息里的 carry-forward 文本链

这类分析能回答“看起来发生了什么”，但不够擅长回答：

1. 这一窗口实际检索到的是哪一组节点
2. work tree 指针是否真的发生推进
3. memory-write 是否真的写回了树
4. carry-forward 到底丢掉了哪些结构化状态

所以它更像“法医式重构”，不是“运行时原生事实读取器”。

### 3.2 Langfuse 不是完整审计面

当前 runtime 本地 request/response 工件保留的信息，比 Langfuse observation 多很多。Langfuse 进入分析链后，会天然丢失：

1. `runtimeMetrics` 细节
2. `contextLengthObservations`
3. `toolExecutions` 明细
4. `rounds` 明细
5. `rawResponse`
6. prompt 编译时的大量本地元数据

如果分析器拿不到本地工件或本地 `evaluation.db`，它就只能依赖代理信号推断窗口行为，模糊是必然结果。

### 3.3 当前评测默认回答“过没过”，不回答“为什么过/为什么不过”

现在的官方 suite 已经能检查：

1. 必需小节
2. 必需短语
3. reject phrases
4. `restartCount`
5. `windowIndex`
6. `cumulativeWindowSpanTokens`

但这些更接近 acceptance gate，而不是窗口级解释器。它能告诉你“哪里不达标”，却不能直接告诉你“第 7 个窗口开始为什么 drift 到 planning stub”或“第 12 个窗口为什么 retrieval 没变但结论变了”。

---

## 4. 下一阶段应该分 4 条主线推进

## 主线 A：先把窗口级观测做硬，不再靠猜

第一优先级不是继续跑更多 case，而是让每个窗口的关键状态都能被直接读取。

建议在 runtime 每个窗口固定持久化一份 `window_execution_record`，至少包含：

1. `taskId`、`invocationId`、`windowIndex`、`restartCount`
2. `sourceSnapshotId`、`targetSnapshotId`、`restartReason`
3. `currentObjective`、`currentFocus`
4. `workTreeCurrentNodeId`、`workTreeRecoveryAnchor`、`workTreeStatus`
5. `materializedContextCount`、`materializedNodeIds`
6. `retrievedNodeIds`、`retrievedNodeCount`、`retrievalFingerprint`
7. `memoryRetrievalSummary`、`reverseTraceMode`
8. `carryForwardItemIds`、`carryForwardTokenEstimate`、`carryForwardLossCount`
9. `responseRequirementsDigest`、`restartMessageDigest`
10. `memoryTagWrites.detectedCount`、`appliedCount`、`blockedCount`
11. `assistantTextSummary`、`outputLabels`
12. `deliveryMode`、`judgmentMode`、`planningStub0_1`

这份记录应同时进入两处：

1. 本地 runtime 工件
2. Langfuse metadata 的精简版摘要

目的不是把 Langfuse 变成本地数据库，而是让 Langfuse 至少能直接标出“这一窗口的结构化状态骨架”，避免分析器继续从自然语言里猜。

### 直接对应的实现入口

1. `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop_part_b.py`
2. `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop_transitions.py`
3. `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py`
4. `packages/python-sdk/src/yggdrasil_sdk/llm_runtime_part_a.py`
5. `packages/python-sdk/src/yggdrasil_sdk/llm_runtime_part_b.py`

## 主线 B：把分析器从“报告生成器”升级为“窗口级因果分析器”

当前分析器已经能输出逐窗口内容，但下一步需要从“描述窗口”升级到“审判窗口”。

建议每个窗口固定给出 6 个判定：

1. 这一窗口的唯一目标是什么
2. 这一窗口真正新增了什么状态
3. 这一窗口继承了什么状态
4. 这一窗口丢失了什么状态
5. 这一窗口的结论来自哪些证据
6. 这一窗口是否只是重复 carry-forward

分析器不应只输出 narrative markdown，还应输出结构化 JSON，字段至少包括：

1. `windowRole`: bootstrap / execution / recovery / delivery / repeated-carry-forward
2. `stateDelta`: objective / retrieval / work tree / delivery contract 的增量
3. `evidenceSufficiency`: sufficient / insufficient / ambiguous
4. `deliveryRisk`: low / medium / high
5. `memoryTreeDependency`: low / medium / high
6. `driftSignals`: planning-stub / stale-retrieval / lost-pointer / overwide-context

这样做的目的，是把“分析模糊”这个问题本身变成可以回归测试的对象。

### 直接对应的实现入口

1. `packages/python-sdk/src/yggdrasil_sdk/langfuse_trace_layered_analysis.py`
2. `scripts/analyze_langfuse_real_task_trace.py`
3. `scripts/analyze_langfuse_real_task_execution_audit.py`
4. `scripts/analyze_langfuse_real_task_trace_layered.py`

## 主线 C：对 runtime 做 3 个关键语义修复

如果想真正优化效果，而不是只优化报告质量，runtime 本身需要继续收紧 3 件事。

### C1. 把 carry-forward 从摘要包改成“执行指针包”

下一窗口最关键的不是读到一段看起来合理的总结，而是拿到：

1. 当前 work tree 节点
2. 当前 objective/focus
3. 关键 protected refs
4. 上一窗口已确认的交付合同
5. 必须保留的 retrieval anchor

因此 carry-forward 的优先级应从“摘要覆盖面”切换为“执行连续性”。

### C2. 强化恢复态的 delivery-first 合同

当前 prompt contract 已经比早期版本更好，但还需要继续冻结两个约束：

1. 恢复态默认继续执行，不允许退回规划前言
2. 如果任务要求最终交付，恢复态窗口必须优先产出正式交付结构，而不是“先总结当前局势”

### C3. 让 retrieval 真正以 work tree 为锚

后续要重点检查：

1. 首轮执行是否已经植入 work tree 锚点
2. 检索排序是否优先围绕当前 work tree 节点和最近交付节点展开
3. pruning 是否在高压窗口下错误保留了大段 repo 原文，反而把树内状态挤掉

### 直接对应的实现入口

1. `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py`
2. `packages/python-sdk/src/yggdrasil_sdk/prompting.py`
3. `modules/text-memory/src/yggdrasil_text_memory/plugin.py`
4. `modules/context-pruning/src/yggdrasil_context_pruning/plugin.py`
5. `modules/pause-resume/src/yggdrasil_pause_resume/plugin.py`

## 主线 D：把评测从“结构 pass”推进到“交付等价 pass”

后续评测不应只保留当前 acceptance gate，而应再补 4 组正式指标：

1. `goalCompletionParity0_1`
   - short-window 与 long-window 是否得出相同任务完成结论。
2. `deliveryEquivalence0_1`
   - 两条路径是否都交出满足同一合同的最终交付物。
3. `workTreeContinuity0_1`
   - 恢复后是否仍沿同一执行指针推进，而不是回到 planning-first。
4. `minimalWorksetRatio0_1`
   - 最终窗口中，树内结构化记忆与大块原文上下文的占比是否达到目标范围。

如果没有这 4 组指标，系统就还是容易出现“技术闭环看起来很好，但真实交付仍在漂移”的假阳性。

### 直接对应的实现入口

1. `packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_g4.py`
2. `packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/scorer.py`
3. `evaluation/suites/g4-real-task-window-parity.json`
4. `evaluation/suites/g4-window-restart-stress.json`

---

## 5. 下一轮实验不要再混做，改成受控消融矩阵

如果继续一边改 runtime、一边改 prompt、一边换 provider、一边换分析口径，最后仍然很难知道真正有效的是哪一项。建议改成下面 4 类受控实验，每次只改一个变量。

### 实验 1：只验证 carry-forward 表示法

固定：

1. 同一任务
2. 同一 provider / model
3. 同一 `effectiveContextWindow`
4. 同一 `forcedWindowRestartBudget`

只比较：

1. 自然语言摘要包
2. 结构化执行指针包

观测目标：

1. planning stub 是否下降
2. work tree continuity 是否上升
3. delivery equivalence 是否上升

### 实验 2：只验证 retrieval 与 pruning

固定 runtime 其它部分，只比较：

1. 现有 retrieval 排序
2. 强 work-tree-anchor retrieval
3. 不同 pruning 预算和保护策略

观测目标：

1. retrieval fingerprint 稳定性
2. 最终交付质量
3. 窗口最小化程度

### 实验 3：只验证恢复态 prompt contract

固定相同任务和窗口压力，只比较：

1. 当前恢复态合同
2. 更强 delivery-first 合同

观测目标：

1. planning stub 命中率
2. 最终窗口交付段落完整率
3. acceptance fail 原因分布

### 实验 4：只验证“树是否真的成了主体”

固定其它条件，只比较：

1. restart 后允许重新挂大量 `currentContext`
2. restart 后只允许结构化记忆 + 最小证据

观测目标：

1. 模型能否继续完成任务
2. 最终结论是否稳定
3. 哪些任务对树依赖足够强，哪些任务仍依赖窗口原文

---

## 6. 推荐的推进顺序

### 第 1 步：先补观测，不先补结论

先补 `window_execution_record`、Langfuse metadata 摘要、分析器 JSON 输出。没有这一步，再多复跑也只是继续产生模糊报告。

### 第 2 步：固定一条标准真实任务

选一条 canonical real-task case，固定 provider、固定窗口参数、固定任务契约，只在这一条上做多轮受控实验，不要先扩 provider 矩阵。

### 第 3 步：先做单 provider 收口，再谈跨 provider

先在一条主 provider 上把：

1. `restartSuccessRate0_1`
2. `goalCompletionParity0_1`
3. `deliveryEquivalence0_1`
4. `workTreeContinuity0_1`

全部收稳，再去比较 DeepSeek、LongCat 等跨 provider 行为差异。否则很容易把“provider 差异”误当成“记忆树改进效果”。

### 第 4 步：最后才冻结正式门槛

只有当单 provider 上连续 3 轮受控实验稳定之后，才应该冻结：

1. `qualityDeltaToLongWindow0_100`
2. `minimalWorksetRatio0_1`
3. `restartCount`
4. `cumulativeWindowSpanTokens`

否则门槛会继续被当前不稳定的实现牵着走。

---

## 7. 可以直接采用的完成定义

当且仅当以下条件同时满足时，才应对外表述“记忆树与伪无限上下文窗口效果已进入稳定优化阶段”：

1. 每个窗口都能输出结构化 `window_execution_record`。
2. 分析器可以直接基于本地工件和 metadata 还原窗口因果链，而不是主要依赖文本推断。
3. 恢复态窗口不再系统性漂移到 planning stub。
4. short-window 与 long-window 在严格 acceptance 下达到交付级 parity。
5. 最终窗口输入中，结构化记忆与最小证据占主导，大块 repo 原文不再充当实际主记忆。

---

## 8. 当前最值得立刻做的 4 件事

1. 给 runtime 增加结构化 `window_execution_record` 输出，并把关键摘要同步到 Langfuse metadata。
   - 状态：已完成第一轮。
2. 把现有 Langfuse 分析器升级成结构化 JSON + 因果判定输出，不再只产 markdown 报告。
   - 状态：JSON 输出已完成，因果判定字段还未收口。
3. 在单一 canonical real-task case 上做 4 类受控消融实验，先定位真正有效的变量。
   - 状态：未开始。
4. 把评测门禁从“结构 pass”提升为“交付等价 + work tree 连续性 + 最小工作集”联合验收。
   - 状态：只完成 `goalCompletionParity0_1` / `deliveryEquivalence0_1` / `qualityDeltaToLongWindow0_100`，其余关键指标未接线。

---

## 9. 相关文档入口

建议与本手册配套阅读：

1. `docs/research/technical-analysis/g4-real-task-window-parity-rerun-log-audit-2026-05-16.md`
2. `docs/research/project-assessments/memory-tree-theory-gap-assessment-2026-05-17.md`
3. `docs/research/roadmaps/memory-tree-agent-executable-roadmap-2026-05-16.md`
4. `docs/development/LLM_REAL_TASK_INFINITE_CONTEXT_EVAL_2026_05_17.md`
5. `docs/development/LANGFUSE_TRACE_DATA_LOSS_AUDIT_2026_05_18.md`

---

## 10. 当前执行状态矩阵

按“观测层 / 分析层 / runtime 语义层 / 评测层”拆开，当前仓库状态如下。

### 10.1 观测层

1. `window_execution_record` 已有第一版。
   - 已落点：`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop_part_a.py`
   - 已接线：`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop_transitions.py`、`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop_part_b.py`
   - 已包含：窗口索引、restart 计数、work tree 指针、retrieval 指纹、contract digest、planningStub0_1、memoryTagWrites 计数。
   - 未包含：`carryForwardItemIds`、`retrievedNodeIds`、`deliveryMode`、`judgmentMode`、精确的最小工作集占比。
2. Langfuse metadata 摘要已完成第一版。
   - 已落点：`packages/python-sdk/src/yggdrasil_sdk/llm_runtime_part_a.py`、`packages/python-sdk/src/yggdrasil_sdk/llm_runtime_part_b.py`
   - 现状：开始态和结束态 metadata 都已带 `windowExecution` 摘要。
   - 缺口：目前更偏“窗口骨架摘要”，还不是完整因果证据面。

### 10.2 分析层

1. 分析器 JSON 输出已完成第一版。
   - 已落点：`packages/python-sdk/src/yggdrasil_sdk/langfuse_trace_layered_analysis.py`
   - 现状：除了 markdown 外，已经能输出结构化 payload，适合后续回归和自动比较。
2. 分析器已能补读本地 `runtime/window-executions` 工件。
   - 现状：重复窗口判定和 memory tree signal 已不再只依赖 Langfuse 文本。
   - 缺口：`stateDelta`、`evidenceSufficiency`、`deliveryRisk`、`memoryTreeDependency`、`driftSignals` 这些判定字段还没有正式冻结。

### 10.3 runtime 语义层

1. 恢复态 contract 已比早期版本明显收紧。
   - 现状：`responseRequirements` / `restartMessage` 已可跨窗口透传；恢复态不再默认强制“先总结局势”。
2. carry-forward 仍是摘要包。
   - 当前实现位置：`packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py`
   - 当前行为：仍从 `currentContextState` 的前若干条拼 header + evidence bullets，并按 token 上限压缩。
   - 结论：这还是“可读 handoff”，不是“强执行指针包”。
3. retrieval 还没有被正式证明“以 work tree 为主体”。
   - 现状：请求里已有 `workTreeNodeId`、`reverseTraceMode`，但评测和分析还没有把“是否真的围绕 work tree 收敛”固定成硬指标。

### 10.4 评测层

1. `goalCompletionParity0_1`、`deliveryEquivalence0_1`、`qualityDeltaToLongWindow0_100` 已经进入聚合。
   - 当前实现位置：`packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/scorer.py`
2. `workTreeContinuity0_1` 和 `minimalWorksetRatio0_1` 还没有接入 scorer。
   - 现状：代码中没有消费 `windowExecutionArtifact` 或 `runtime/window-executions` 的逻辑。
3. canonical real-task parity case 仍然过宽。
   - 当前定义位置：`evaluation/suites/g4-real-task-window-parity.json`
   - 现状：case 同时挂了大量 `currentContextFiles` 与 `currentContextGlobs`，这会直接削弱“窗口最小化”实验的解释力。

---

## 11. 当前仓库分析结论（2026-05-18 晚）

这次基于当前代码现实做完一轮分析后，可以把“应该怎么优化”压缩成 5 条非常具体的结论。

### 11.1 已经补上的不是最终能力，而是“解释能力”

当前最重要的正向进展，是系统终于开始保留每窗结构化状态，而不是只留下 carry-forward 文本和最终分数。这意味着后续优化可以首次围绕真实窗口状态做，而不是继续围绕模糊报告做。

换句话说：

1. 现在已经更容易定位问题。
2. 但问题本身还没有被根治。

### 11.2 当前最大行为缺口仍然是 carry-forward 表示法

从 `snapshot.py` 现在的实现看，carry-forward 仍然是：

1. 读取 `currentContextState`
2. 取前几条上下文
3. 做去重和 excerpt 压缩
4. 拼出 `Window restart handoff` / `Current objective` / `Current focus` / `Carry-forward evidence`

这说明它仍是“摘要包”。

这类包的问题不是一定会失败，而是它缺少严格的执行语义。它不能稳定保证：

1. 下一窗口一定沿同一 work tree 节点推进。
2. 下一窗口一定保留同一 retrieval anchor。
3. 下一窗口一定优先执行交付合同，而不是退回 planning stub。

因此，当前最值得优先优化的 runtime 项，不是更复杂的 prompt，而是先把 carry-forward 改成结构化执行指针包。

### 11.3 当前评测仍在“交付结果”与“窗口连续性”之间断层

`scorer.py` 现在已经能聚合：

1. `goalCompletionParity0_1`
2. `deliveryEquivalence0_1`
3. `qualityDeltaToLongWindow0_100`

这比早期只看 `restartCount` 已经好很多。但它仍然缺少两类关键指标：

1. `workTreeContinuity0_1`
2. `minimalWorksetRatio0_1`

这会导致一种典型盲区：

1. 最终 brief 看起来完成了。
2. short/long 也可能表面等价。
3. 但中间其实是靠过宽上下文撑出来的，不是靠记忆树主体撑出来的。

如果不把这两类指标接进去，系统仍然可能在“结果上通过、机制上失真”的状态里停很久。

### 11.4 当前 canonical case 本身就在稀释“最小工作集”实验

`g4-real-task-window-parity.json` 当前设计仍把大量 repo 文件和 glob 直接装进 case。它适合证明“真实任务很复杂”，但不适合证明“窗口已经最小化”。

因为一旦实验入口本身就把大面积 repo surface 直接灌进来，后面即使 restart 发生，你也很难断言：

1. 最终交付究竟是靠树内结构化记忆完成的。
2. 还是靠入口阶段就已经塞进窗口的大量原文完成的。

所以在当前阶段，canonical case 应拆成两类：

1. `real-task-parity-baseline`：继续保留 repo-wide 复杂度，用来证明真实任务可交付。
2. `real-task-minimal-workset`：只保留任务合同 + 极少量初始锚点，其余尽量依赖 retrieval/work tree，用来证明记忆树主体成立。

### 11.5 当前真正的优化优先级已经可以重排

现在不应该再把精力平均分给所有方向。最优顺序已经比较清楚：

1. 先修 carry-forward 表示法。
2. 再把 `workTreeContinuity0_1` / `minimalWorksetRatio0_1` 接进评测。
3. 然后拆出真正的 minimal-workset canonical case。
4. 最后才做 retrieval/pruning/prompt contract 的受控消融。

原因很直接：

1. 不先修 carry-forward，窗口连续性仍然没有稳定语义。
2. 不先补评测，后面任何优化都很难形成硬证据。
3. 不先拆 case，实验设计本身就会持续混淆“树主导”与“上下文主导”。

---

## 12. 应该怎么优化：正式优先级

### P0：把 carry-forward 改成结构化执行指针包

目标：让下一窗口拿到的是“执行所需最小状态”，不是“上一窗口文本摘要”。

优先保留字段应改为：

1. `workTreeCurrentNodeId`
2. `workTreeRecoveryAnchor`
3. `currentObjective`
4. `currentFocus`
5. `responseRequirementsDigest`
6. `restartMessageDigest`
7. `protectedRefIds`
8. `retrievalFingerprint`
9. `retrievedNodeIds` 或最小 retrieval anchor 集

明确降低优先级的字段：

1. 大段自然语言 evidence bullets
2. 可替代的 repo 文本摘要
3. 多条重复 context item excerpt

### P1：把窗口工件接入正式 scorer

目标：让评测直接消费 `runtime/window-executions`，而不是只看最终 response。

应新增正式聚合指标：

1. `workTreeContinuity0_1`
2. `minimalWorksetRatio0_1`
3. `planningStubRate0_1`
4. `retrievalDriftRate0_1`

最小实现方式：

1. suite case 在产出 detail 时写入 `windowExecutionArtifactRef` 或直接回捞本地工件。
2. scorer 按 short/long case 分别聚合这些窗口级指标。
3. parity summary 在 `goalCompletionParity0_1` 和 `deliveryEquivalence0_1` 之外，再增加窗口连续性和最小工作集门。

### P2：拆出真正可用的 minimal-workset canonical case

目标：把“真实任务可交付”和“记忆树主导成立”拆成两条实验线。

建议新增一条 canonical case：

1. 只保留任务合同
2. 只保留极少量初始锚点文件
3. 明确限制 `currentContextGlobs`
4. 让绝大部分证据依赖 retrieval/work tree 回收

这样才能真正验证：

1. 树是不是主体
2. 窗口是不是最小工作集

### P3：最后再做受控消融实验

在 P0-P2 完成前，不建议过早扩大消融矩阵。完成后再做：

1. carry-forward 表示法对比
2. retrieval 排序对比
3. pruning 预算对比
4. 恢复态 prompt contract 对比

否则实验结论会持续被 carry-forward 和 case 设计本身污染。

---

## 13. 建议执行命令

### 13.1 当前已接好的窄回归

```powershell
uv run pytest tests/runtime/test_runtime_restart_and_resume.py tests/runtime/test_runtime_budget_and_audit.py tests/runtime/test_runtime_core_and_memory.py tests/test_langfuse_trace_layered_analysis.py -q
```

### 13.2 生成 Langfuse 窗口审计 markdown + JSON

```powershell
uv run python -m yggdrasil_sdk.langfuse_trace_layered_analysis --trace-id <TRACE_ID> --analysis-provider longcat --analysis-model LongCat-2.0-Preview --output .yggdrasil/state/analysis/langfuse-real-task-execution-audit.md --json-output .yggdrasil/state/analysis/langfuse-real-task-execution-audit.json
```

### 13.3 当前最值得做的下一轮实现顺序

1. 先改 `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py` 的 `_build_carry_forward_context`。
2. 再把 `packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_g4.py` 与 `packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/scorer.py` 接到 `runtime/window-executions`。
3. 然后再收缩 `evaluation/suites/g4-real-task-window-parity.json`，新增 minimal-workset canonical case。

---

## 14. 当前结论

一句话结论：

当前项目已经完成“窗口级观测和分析基础设施第一轮收口”，但真正决定记忆树效果的主矛盾已经收敛为 3 个具体点：

1. carry-forward 仍然是摘要包。
2. 评测还没把窗口连续性和最小工作集接成硬门。
3. canonical case 仍然过宽，暂时还不适合证明“树是主体”。

所以现在最正确的优化方向不是继续泛化调 prompt，也不是继续只跑更多 provider，而是先把这 3 个点按 P0 -> P1 -> P2 的顺序收掉。
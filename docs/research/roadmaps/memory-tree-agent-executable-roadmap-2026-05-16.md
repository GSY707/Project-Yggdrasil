# 世界树计划 · 记忆树 Agent 可执行路线图（2026-05-16）

- 文档状态：Executable Implementation Roadmap（已完成，待验收）
- 日期：2026-05-16
- 目标：把“记忆树代替上下文窗口成为 LLM 的全部记忆”落成可执行工程计划，不依赖原拆分文档的建议顺序。

### 执行状态更新（2026-05-17）

1. P2 已完成主链路闭环（含预算 pre/post check 接线与回归），验证结论见 `docs/research/P2_VERIFICATION_AND_P3_DELIVERY_2026_05_17.md`。
2. P3（任务 18-20）已完成工程落地：
  - E1：交付段落缺失从 warning 升级为 failed（硬门禁语义）。
  - D6：G4 case 增加 tier 化 restart stability 报告与可选强失败门禁。
  - E2：新增 short-window vs long-window parity 冻结指标并进入 suite 聚合输出。
  - P3 缺口收口（2026-05-17）：`evalsuite_g4_real_task_web_research_default` 已支持 free 默认 + case 级少量 paid 批准；评测聚合改为按 parity pair + provider/model 分组，避免 LongCat 与 DeepSeek 样本混成单一 parity 结论。
3. P4（任务 21-26）已完成基础工程收口：
  - B6：共享空间写入在 mounted-space / mountMode / write tuple 上前置校验，并保留 blockers。
  - A4：WorkTree 在无 plan 时也会生成 bootstrap 节点，保证 `currentNodeId` 与 `recoveryAnchor` 可恢复。
  - A3/A5：root mount 显式输出 `startupContract`，task-takeover 将启动合同与根挂载转为结构化约束。
  - A2/A1：任务创建阶段补齐 project/space/branch 一致性校验与缺失 branch workspace 自动引导。
4. 官方入口运行状态：
  - `eval:g4:window-stress` 本次运行通过（`passRate=1.0`）。
  - `eval:g4:web-research:default` 本次运行 failed（严格 acceptance 未通过），当前剩余工作转为 live 结果达标而非代码接线缺失。

---

## 1. 总目标与验收基线

### 1.1 第一优先级目标

在多窗口执行中，模型有效记忆来源必须由记忆树主导，而非上下文窗口残留。具体体现为：

1. 关键状态可写入记忆树并带来源追踪。
2. 下一窗口推理依赖检索回填的结构化记忆，而非上窗口自然语言残留。
3. 任意 restart/resume 后可沿同一 WorkTree 执行指针继续交付。
4. 在严格 acceptance 下，short-window 与 long-window 达到交付级 parity。

### 1.2 统一验收门

以下 4 条全部满足，才算主目标达成：

1. delivery gate：输出包含 result/evidence/pending/incomplete，且 judgment 字段齐全。
2. restart gate：`restartCount>=1`、`windowIndex>=2`、`cumulativeWindowSpanTokens` 达到套件阈值。
3. memory gate：恢复态中 `memoryRetrievalState` 与 `takeoverProtocol.workTree` 可还原且可继续推进。
4. parity gate：`goalCompletionParity0_1=1`、`deliveryEquivalence0_1=1`，`qualityDeltaToLongWindow0_100` 在阈值内。

---

## 2. 执行顺序（可直接开工）

本路线图采用以下顺序，不复用原文档中的顺序建议：

1. C4
2. C5
3. B1
4. B2
5. B3
6. B4
7. B5
8. D2
9. D4
10. C1
11. D5
12. D1
13. D3
14. C2
15. C3
16. C6
17. C7
18. E1
19. D6
20. E2
21. B6
22. A4
23. A3
24. A5
25. A2
26. A1

说明：该顺序把“写树闭环 + 取树闭环 + 恢复闭环 + 严格验收闭环”前置，接入层和外围治理后置。

---

## 3. 分阶段可执行计划

## Phase P0：写树与取树最小闭环（任务 1-7）

目标：先证明记忆树可持续写入并主导检索，不让上下文窗口残留成为主记忆。

### 任务 1：C4 解析 assistant memory-write 标签

- 输入：assistant 原文、memoryWriteTagsEnabled 开关、当前 request。
- 实现：
  - 文件：packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py
  - 统一解析 `<memory-write>` 标签，拆分 clean text / writes / blocked。
  - 对 empty-content、missing-title-or-nodeId、非法 action 做硬阻断。
- 输出：`memoryTagWrites.detected/applied/blocked` 结构化结果。
- 验证：新增/更新 focused test，断言 `detectedCount`、`blockedReason`、`appliedCount`。
- 证据：response artifact 中出现 memoryTagWrites 统计。
- 退出条件：不再出现 silent skip 或误写节点。

### 任务 2：C5 应用 memory-write 到节点仓储

- 输入：C4 输出的合法 writes、rootMount、task/space/branch。
- 实现：
  - 文件：packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py
  - 支持 create/append/replace，统一 source annotation。
  - 禁止 existing node retarget（nodeId 与目标 branch/space 不一致时拒绝）。
- 输出：节点版本递增、annotation 可追踪。
- 验证：仓储级单测覆盖 create/append/replace/retarget-block。
- 证据：node version 变化与 invocation label 可审计。
- 退出条件：写树行为与审计记录 100% 对齐。

### 任务 3：B1 currentContext 物化到运行时节点

- 输入：currentContext、windowIndex、workTreeNodeId。
- 实现：
  - 文件：packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py
  - 物化节点写入 sourceWindowIndex/sourceWorkTreeNodeId/sourceRunId。
- 输出：可检索节点集合。
- 验证：节点仓储可按 taskId + sourceWindowIndex 查询。
- 证据：runtime metrics 中 materializedNodeIds 非空。
- 退出条件：恢复后能追溯每个上下文切片来源。

### 任务 4：B2 记忆树 plan_tree 规划

- 输入：目标文本块、已有节点关系、任务 objective。
- 实现：
  - 文件：modules/text-memory/src/yggdrasil_text_memory/plugin.py
  - 固定分块粒度、父子关系构建规则、最大深度保护。
- 输出：可遍历 plan_tree。
- 验证：模块单测验证树结构稳定性（同输入同结构）。
- 证据：plan_tree artifact 含 nodeCount/depth。
- 退出条件：规划结果在重跑中结构波动可控。

### 任务 5：B3 expand_retrieval 检索扩展

- 输入：核心命中节点、workTreeNodeId、reverseTraceMode。
- 实现：
  - 文件：modules/text-memory/src/yggdrasil_text_memory/plugin.py
  - 实现有界扩展（层数、分支数、token 预算上限）。
  - 优先扩展与当前 work tree 节点相关联边。
- 输出：扩展后 retrieval items。
- 验证：扩展前后 token/数量在上限内；相关性分不下降。
- 证据：`memoryRetrievalState.summary` 可解释扩展来源。
- 退出条件：不再出现无界扩展污染窗口。

### 任务 6：B4 context-pruning 预算裁剪

- 输入：retrieval items、token budget、保护字段列表。
- 实现：
  - 文件：modules/context-pruning/src/yggdrasil_context_pruning/plugin.py
  - 裁剪时硬保护合同字段（responseRequirements/restartMessage/workTree 指针）。
  - 加入“先删低相关摘要，再删正文”的两段式策略。
- 输出：预算内工作集。
- 验证：在固定 budget 下重复运行结果稳定。
- 证据：pruning report 含 dropped-kept 原因。
- 退出条件：裁剪后仍能完成交付而非退化成 planning stub。

### 任务 7：B5 retrieval 状态写入 runtime_state

- 输入：retrieval request/result、protected items。
- 实现：
  - 文件：packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py
  - 固定 `memoryRetrievalState` 字段名与语义，禁止 formatter 漂移。
- 输出：prompt 可消费的 retrieval state。
- 验证：compiled prompt 工件包含 retrieval state 且字段齐全。
- 证据：prompt artifact 与 requestState 一致。
- 退出条件：恢复前后字段兼容，无丢字段。

---

## Phase P1：恢复链路硬化（任务 8-13）

目标：任何 restart/resume 后都能继续同一执行节点，并维持 delivery-first 合同。

### 任务 8：D2 构建 restart request state

- 输入：request、runtimeMetrics。
- 实现：
  - 文件：packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py
  - 快照中强制包含 responseRequirements、restartMessage、takeoverProtocol、memoryRetrievalState。
  - 深拷贝嵌套字段，防止后续被引用覆盖。
- 输出：完整 requestState 快照。
- 验证：resume 后 requestUpdates 与快照字段逐项比对通过。
- 证据：snapshot.pendingActions.requestState 完整。
- 退出条件：跨窗口合同字段 0 丢失。

### 任务 9：D4 恢复 WorkTree 执行指针

- 输入：snapshot requestState、takeoverProtocol.workTree。
- 实现：
  - 文件：packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover.py
  - 文件：modules/pause-resume/src/yggdrasil_pause_resume/plugin.py
  - 恢复时显式恢复 currentNodeId/status/recoveryAnchor；缺失时 fallback 到最近可执行节点而非重置 plan。
- 输出：durable execution pointer。
- 验证：resume 后下一步动作属于恢复前 currentNodeId 对应 phase。
- 证据：runtime artifact 记录 preResumeNodeId/postResumeNodeId。
- 退出条件：恢复后不再回到 planning-first。

### 任务 10：C1 运行时 Prompt 编译

- 输入：task_contract + runtime_state + response_requirements + resume_path。
- 实现：
  - 文件：packages/python-sdk/src/yggdrasil_sdk/prompting.py
  - 编译逻辑读取恢复态字段，避免默认文案覆盖正式合同。
  - 把 workTree/memoryRetrievalState 作为一等段落输出。
- 输出：可审计 compiled prompt。
- 验证：恢复态与首轮 prompt 的合同段落一致性通过 diff 检查。
- 证据：prompt compile artifact 字段齐全。
- 退出条件：恢复态 prompt 不再退化为“先总结局势”。

### 任务 11：D5 恢复态 Prompt 合同对齐

- 输入：resume_path、responseRequirements、restartMessage。
- 实现：
  - 文件：packages/python-sdk/src/yggdrasil_sdk/prompting.py
  - `_format_response_requirements` 增加恢复态分支：强制 delivery-first。
- 输出：恢复窗口输出合同一致。
- 验证：恢复态 case 必须命中 required sections + required judgment。
- 证据：G4 acceptance check 不再触发 missing-section/missing-judgment。
- 退出条件：恢复态交付结构与首轮保持同级质量。

### 任务 12：D1 触发窗口重启判定

- 输入：effectiveContextWindow、windowRestartRatio、token span。
- 实现：
  - 文件：packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py
  - 统一阈值计算与 runtime metrics 口径。
- 输出：可审计 trigger decision。
- 验证：边界值测试（刚好低于阈值、刚好等于阈值、强制预算触发）。
- 证据：trigger reason 与 token 边界可追踪。
- 退出条件：触发行为可预测且与配置一致。

### 任务 13：D3 生成 carry-forward package

- 输入：currentContextState、workTree、memoryRetrievalState。
- 实现：
  - 文件：packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py
  - 压缩时保留执行指针关键字段，避免重复内容造成重启震荡。
- 输出：可恢复上下文包。
- 验证：carryForwardLossCount 统计准确且可回归。
- 证据：restart 后第一轮能读取并继续当前节点。
- 退出条件：多次重启后仍不丢执行语义。

---

## Phase P2：推理执行稳态化（任务 14-17）

目标：把模型调用、工具回合、指标记录、安全停止做成可持续复跑的稳定链路。

### 任务 14：C2 LLM 调用与预算治理

- 输入：route decision、budget policy、runtime metrics。
- 实现：
  - 文件：packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py
  - 固化 hard fail 与 retry 边界，避免成功后被预算后置检查误判。
- 输出：稳定 invocation 结果。
- 验证：request/response artifact 成对落盘；预算违规路径可复现。
- 证据：cost/token 统计与判定一致。
- 退出条件：调用成功与预算判定口径一致。

### 任务 15：C3 工具调用执行回合

- 输入：toolCalls、round state、pending actions。
- 实现：
  - 文件：packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py
  - 工具失败隔离，不污染主状态机；失败转可恢复 pending action。
- 输出：tool execution trace。
- 验证：工具失败 case 不导致任务状态机崩溃。
- 证据：tool executions 工件可追踪。
- 退出条件：工具层失败不会破坏交付层推进。

### 任务 16：C6 记录 runtime metrics

- 输入：window/restart/token/span/carry-forward 指标。
- 实现：
  - 文件：packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py
  - 统一 restart 前后指标口径与字段名。
- 输出：可比较的指标快照。
- 验证：同任务跨窗口指标单调性与一致性检查通过。
- 证据：response artifact 指标可直接对比。
- 退出条件：监控图上无明显口径跳变。

### 任务 17：C7 安全停止与可恢复断点

- 输入：activeToolCalls、pendingActions、safe-stop policy。
- 实现：
  - 文件：packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py
  - 保存 pending tool calls 与 savepoint，恢复时原位续跑。
- 输出：可恢复断点。
- 验证：中断后 resume 成功并继续未完成动作。
- 证据：snapshot 中 pending-tool-calls 可回放。
- 退出条件：safe-stop 不再丢失未完成动作。

---

## Phase P3：严格交付与 parity 冻结（任务 18-20）

目标：从“技术闭环”升级到“交付闭环”，并形成官方门槛证据。

### 任务 18：E1 交付段落解析与验收

- 输入：assistant final output。
- 实现：
  - 文件：modules/task-takeover/src/yggdrasil_task_takeover/plugin.py
  - 强制 result/evidence/pending/incomplete 四段解析与校验。
- 输出：delivery completion 与质量分。
- 验证：缺关键小节必须 fail，不能软通过。
- 证据：verification items 与 pass rate 可追踪。
- 退出条件：交付检查成为硬门禁。

### 任务 19：D6 多次重启稳定性

- 输入：受控窗口参数、forced restart budget。
- 实现：
  - 文件：packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_g4.py
  - 跑 N 次 restart（建议 30/60/100 阶梯），记录成功率与交付质量。
- 输出：restart stability 报告。
- 验证：`restartSuccessRate0_1` 达阈值；失败可定位到具体窗口。
- 证据：evaluation artifacts 完整。
- 退出条件：N 次重启连续可恢复、可继续、可交付。

### 任务 20：E2 真实任务 parity 评测

- 输入：short-window vs long-window 同任务语料。
- 实现：
  - 文件：packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_g4.py
  - 文件：evaluation/suites/g4-real-task-web-research-default.json
  - 冻结 acceptance parity 与 delivery equivalence 指标，禁止结构性 pass 替代交付 pass。
- 输出：官方 parity 结论。
- 验证：严格 acceptance 下通过，且失败时给出可解释差异。
- 证据：正式 evalrun + 保留日志 + 指标报告。
- 退出条件：多 provider 下 parity 结论稳定。

---

## Phase P4：外围完备性补齐（任务 21-26）

目标：补齐权限、接入、挂载协议，减少规模化推广时的系统性风险。

### 任务 21：B6 共享空间写权限校验

- 输入：targetSpace/targetBranch、relation tuple、write request。
- 实现：
  - 文件：modules/shared-memory/src/yggdrasil_shared_memory/plugin.py
  - relation=write 前置校验，失败返回 blockers。
- 输出：允许/阻断路径显式化。
- 验证：跨空间写入权限回归测试。
- 证据：权限判定日志可审计。
- 退出条件：不存在未授权跨空间写入。

### 任务 22：A4 构建 WorkTreeProtocol 初始执行指针

- 输入：takeover objective/constraints/plan。
- 实现：
  - 文件：packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover.py
  - 初始化 currentNodeId/status/phase 并可恢复。
- 输出：初始 durable pointer。
- 验证：首次启动即可定位当前执行节点。
- 证据：takeoverProtocol.workTree 完整。
- 退出条件：A4 与 D4 字段完全兼容。

### 任务 23：A3 构建 TaskTakeoverProtocol

- 输入：task/request/rootMount/currentContext。
- 实现：
  - 文件：modules/task-takeover/src/yggdrasil_task_takeover/plugin.py
  - 约束结构化，避免纯文本拼接。
- 输出：objective/constraints/plan 协议对象。
- 验证：protocol 可注入 runtime_state 并参与 prompt。
- 证据：hook trace + applied modules。
- 退出条件：协议字段稳定并可演进。

### 任务 24：A5 写入启动合同

- 输入：start payload。
- 实现：
  - 文件：packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py
  - 启动时显式携带 responseRequirements/restartMessage，并进入快照透传链。
- 输出：跨窗口合同一致。
- 验证：compiled prompt 与 snapshot 同步含该字段。
- 证据：requestState 对比报告。
- 退出条件：合同字段跨窗口 0 漂移。

### 任务 25：A2 构建 root mount（三根分支）

- 输入：task/app/space/branch。
- 实现：
  - 文件：packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/root_mount.py
  - identity/context/execution 映射稳定。
- 输出：rootMountPackage。
- 验证：prompt 编译可稳定读取三根分支。
- 证据：root mount artifact 可审计。
- 退出条件：activeCapabilities 与根分支映射稳定。

### 任务 26：A1 创建任务记录与工作空间引导

- 输入：ownerProfileId/spaceId/branchId。
- 实现：
  - 文件：packages/python-sdk/src/yggdrasil_sdk/persistence/repositories/task_repository.py
  - 任务初始化与工作空间引导完整性校验。
- 输出：可运行 task。
- 验证：任务可被 runtime 拉起并继承 app/space/branch。
- 证据：task record 与首轮 run 工件。
- 退出条件：接入层不再成为恢复链路隐患来源。

---

## 4. 任务执行卡模板（每项照抄即可）

每个任务在实施时必须填写以下卡片，避免“完成但不可验收”：

1. 任务编号：例如 D4。
2. 目标：一句话定义可交付结果。
3. 变更文件：列出精确文件路径。
4. 接口/字段变更：新增字段、默认值、兼容策略。
5. 测试：单测/集成/评测命令与预期结果。
6. 证据：artifact 路径与关键指标。
7. 风险与回滚：失败触发条件、回退方案。
8. Done Definition：满足哪些硬条件才算完成。

---

## 5. 每周推进节奏（建议）

### 第 1 周

- 完成 Phase P0（任务 1-7）。
- 里程碑：写树+取树最小闭环可复跑。

### 第 2 周

- 完成 Phase P1（任务 8-13）。
- 里程碑：恢复链路不回退到 planning stub。

### 第 3 周

- 完成 Phase P2 + E1（任务 14-18）。
- 里程碑：推理执行稳态 + 严格交付硬门。

### 第 4 周

- 完成 D6 + E2（任务 19-20），启动多 provider 对照。
- 里程碑：形成首版交付级 parity 证据。

### 第 5 周

- 收尾 Phase P4（任务 21-26）。
- 里程碑：权限与接入层全面补齐，准备门槛冻结。

---

## 6. 风险清单（按影响排序）

1. 恢复态合同退化：恢复后 prompt 回落到 planning-first。
2. WorkTree 指针漂移：多次 restart 后 currentNodeId 丢失或错误。
3. 检索无界扩展：导致窗口污染并稀释关键证据。
4. memory-write 误写：写入成功但目标节点错误，造成隐性数据损坏。
5. parity 假阳性：结构性通过但交付不通过。

---

## 7. 结论

1. 这套顺序优先保证“记忆树写入-检索-恢复-验收”四闭环，不再把接入层当主战场。
2. 若 Phase P0/P1 未闭合，后续 D6/E2 的任何高分都不应解释为“记忆树已替代窗口”。
3. 真正的完成标准不是 restart 技术成功，而是在严格 acceptance 下获得可复现的交付级 parity。


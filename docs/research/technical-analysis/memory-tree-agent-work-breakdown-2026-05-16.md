# 世界树计划 · 记忆树 Agent 全工作拆分与实现研究（2026-05-16）

- 文档状态：Task Decomposition + Implementation Guide（已完成）
- 日期：2026-05-16
- 目标：把“记忆树 Agent 的所有工作”拆分成最小可推进子任务；每个子任务至少包含一次有效推进（规划、基于记忆树思考、或执行修改）；对每个子任务评估难度并给出实现路径。

---

## 1. 拆分边界与最小单元定义

### 1.1 拆分边界

本拆分覆盖以下主链：

1. 任务接入与目标建立（Task/Takeover）
2. 记忆树工作集准备（mount/materialize/retrieval）
3. 推理与执行（prompt/llm/tool/memory-write）
4. 窗口重启与恢复（snapshot/carry-forward/resume）
5. 交付验证与评测闭环（delivery/acceptance/parity）

### 1.2 最小工作单元定义

一个子任务必须满足至少一条：

1. 产生一个新的可验证计划或协议对象。
2. 在记忆树上新增、更新、压缩或关联一次有效状态。
3. 产生一次可验证执行结果（模型调用、工具调用、交付解析、评测记录）。

---

## 2. 难度分级标准

- L1（低）：单模块、低耦合、可用单测直接验证。
- L2（中低）：跨 2 个模块，存在字段契约或参数同步。
- L3（中高）：跨 runtime 主链，涉及 prompt/llm/context 三方协同。
- L4（高）：涉及窗口重启、恢复语义、状态延续与评测一致性。
- L5（极高）：多 provider、长链路稳定性、正式门槛冻结与回归治理。

---

## 3. 全量最小子任务清单（26 项）

## A. 任务接入与接管规划（A1-A5）

### A1. 创建任务记录与工作空间引导
- 有效推进：完成一次 task 初始化。
- 难度：L1
- 实现：调用 TaskRepository 创建 task；ensure branch workspace。
- 关键点：ownerProfileId、spaceId、branchId 必须完整。
- 验证：任务可被 runtime 拉起。

### A2. 构建 root mount（三根分支）
- 有效推进：形成 identity/context/execution 根挂载。
- 难度：L1
- 实现：在 runtime 启动阶段生成 rootMountPackage。
- 关键点：activeCapabilities 与 root 节点映射稳定。
- 验证：prompt 编译可读取三根分支。

### A3. 构建 TaskTakeoverProtocol
- 有效推进：生成 objective/constraints/plan 的接管协议。
- 难度：L2
- 实现：task-takeover 模块构建 coding protocol。
- 关键点：constraints 需要结构化而非纯文本拼接。
- 验证：protocol 可注入 runtime_state。

### A4. 构建 WorkTreeProtocol 初始执行指针
- 有效推进：形成当前执行节点与阶段。
- 难度：L2
- 实现：从 takeover 结果投影 work tree。
- 关键点：节点状态字段必须可恢复（phase/status/currentNodeId）。
- 验证：恢复后能继续同一执行节点。

### A5. 写入启动合同（responseRequirements/restartMessage）
- 有效推进：任务交付合同进入 request。
- 难度：L2
- 实现：start payload 显式携带 responseRequirements 与 restartMessage。
- 关键点：后续 snapshot 必须透传这两项。
- 验证：compiled prompt 可见合同条款。

## B. 记忆树工作集准备（B1-B6）

### B1. currentContext 物化到运行时节点
- 有效推进：当前上下文转为可检索节点。
- 难度：L2
- 实现：execution_loop 中 materialize runtime context items。
- 关键点：物化节点来源标注与窗口索引一致。
- 验证：node repo 中可查到新节点。

### B2. 记忆树 plan_tree 规划
- 有效推进：一次建树规划完成。
- 难度：L2
- 实现：text-memory.plan_tree 生成结构化树层级。
- 关键点：分块粒度和父子关系稳定。
- 验证：节点树可遍历且层级合理。

### B3. expand_retrieval 检索扩展
- 有效推进：检索集从核心节点扩展到关联节点。
- 难度：L3
- 实现：text-memory.expand_retrieval 基于节点关系扩展。
- 关键点：防止无界扩展导致窗口污染。
- 验证：retrieval item 数量与 token 可控。

### B4. context-pruning 预算裁剪
- 有效推进：在 token 预算内得到可用工作集。
- 难度：L3
- 实现：按重要度与摘要策略裁剪 context items。
- 关键点：不能裁掉关键合同字段。
- 验证：裁剪后 prompt 仍可完成任务。

### B5. retrieval 状态写入 runtime_state
- 有效推进：将检索结果结构化注入 prompt 上下文。
- 难度：L2
- 实现：runtime_state 中写入 mounted/retrieval 信息。
- 关键点：字段名稳定，避免 prompt formatter 漂移。
- 验证：compiled prompt 中存在 retrieval state。

### B6. 共享空间写权限校验
- 有效推进：一次 write 校验成功或明确阻断。
- 难度：L3
- 实现：shared-memory 权限 tuple 与 targetSpace/targetBranch 校验。
- 关键点：跨空间写入必须先验证 relation=write。
- 验证：允许路径可写，禁止路径有 blockers。

## C. 推理与执行主链（C1-C7）

### C1. 运行时 Prompt 编译
- 有效推进：产出一份可审计 compiled prompt。
- 难度：L3
- 实现：compile_runtime_prompt 组装 task_contract + runtime_state + response_requirements。
- 关键点：恢复态不能退化为 planning-first 文案。
- 验证：compiled prompt artifact 字段齐全。

### C2. LLM 调用与预算治理
- 有效推进：完成一次 invocation 并返回 assistantText/toolCalls。
- 难度：L3
- 实现：llm_runtime 执行 provider/model 路由与调用。
- 关键点：budget hard fail 与 retry 策略边界。
- 验证：request/response artifact 成对落盘。

### C3. 工具调用执行回合
- 有效推进：完成至少一轮 tool call -> tool result。
- 难度：L3
- 实现：execution_control 执行工具并回填结果。
- 关键点：tool 失败不应污染主任务状态机。
- 验证：tool executions 工件可追踪。

### C4. 解析 assistant memory-write 标签
- 有效推进：从回复中提取至少一个合法 memory-write。
- 难度：L2
- 实现：正则解析标签与属性，拆分 clean text/writes/blocked。
- 关键点：empty-content 与 missing-title-or-nodeId 要阻断。
- 验证：detectedCount、blocked/applied 计数正确。

### C5. 应用 memory-write 到节点仓储
- 有效推进：成功 create/append/replace 一次节点内容。
- 难度：L3
- 实现：按 action 写入 node，并附 source annotation。
- 关键点：existing node 的 retarget 需禁止。
- 验证：node version 增长，annotation 可查询。

### C6. 记录 runtime metrics
- 有效推进：本轮执行指标写入 response artifact。
- 难度：L2
- 实现：写入 windowIndex/restartCount/cumulativeWindowSpanTokens 等。
- 关键点：字段在 restart 前后口径一致。
- 验证：artifact 中指标可比较。

### C7. 安全停止与可恢复断点
- 有效推进：safe-stop 下次可继续。
- 难度：L3
- 实现：pending tool calls、shutdown control 与 savepoint。
- 关键点：不得丢失未完成动作。
- 验证：resume 后流程连续。

## D. 窗口重启与恢复闭环（D1-D6）

### D1. 触发窗口重启判定
- 有效推进：一次 restart trigger 决策（触发或不触发）。
- 难度：L2
- 实现：_window_restart_trigger 基于 effectiveContextWindow 与比例阈值。
- 关键点：阈值计算和 runtime metrics 记录同步。
- 验证：trigger reason 与 token 边界可审计。

### D2. 构建 restart request state
- 有效推进：一次完整 requestState 快照。
- 难度：L3
- 实现：snapshot 中保存 request 关键键值（含 responseRequirements/restartMessage）。
- 关键点：缺字段会导致跨窗口合同丢失。
- 验证：snapshot.pendingActions.requestState 可还原。

### D3. 生成 carry-forward package
- 有效推进：从当前窗口压出可恢复上下文包。
- 难度：L4
- 实现：_build_carry_forward_context 组装 restart instruction + summary。
- 关键点：避免重复字段造成 restart 震荡。
- 验证：carryForwardLossCount 为 0。

### D4. 恢复 WorkTree 执行指针
- 有效推进：恢复后继续同一执行节点。
- 难度：L4
- 实现：_work_tree_from_protocol_parts + snapshot payload 恢复。
- 关键点：work tree 必须是 durable execution pointer。
- 验证：恢复后非 planning stub，而是继续交付链。

### D5. 恢复态 Prompt 合同对齐
- 有效推进：恢复窗口输出满足最终交付合同。
- 难度：L4
- 实现：response requirements 在恢复态仍指向 delivery-first。
- 关键点：不能被“先总结局势”默认文案覆盖。
- 验证：输出包含约定小节与判断语句。

### D6. 多次重启稳定性（N 次）
- 有效推进：N 次 restart 连续成功。
- 难度：L5
- 实现：受控窗口压测（如 100 次）并记录重启成功率。
- 关键点：每次都要可恢复、可继续、可交付。
- 验证：restartSuccessRate0_1 达到目标。

## E. 交付与评测闭环（E1-E2）

### E1. 交付段落解析与验收
- 有效推进：成功解析 result/evidence/pending/incomplete 并通过校验。
- 难度：L2
- 实现：task-takeover 的 _parse_delivery_sections + verify_delivery。
- 关键点：缺关键小节必须 fail。
- 验证：delivery completion 与质量分可追踪。

### E2. 真实任务 parity 评测
- 有效推进：完成 short-window vs long-window 一次正式对照。
- 难度：L5
- 实现：suite case forward 合同字段，冻结 acceptance parity 与 delivery equivalence 指标。
- 关键点：结构性 pass 不能替代交付 pass。
- 验证：official suite 在严格 acceptance 下通过。

---

## 4. 建议实现顺序（面向交付闭环）

1. P0：A5 -> C1 -> D2 -> D5（先锁定跨窗口合同一致性）
2. P0：D4 -> E1（恢复后必须能继续交付而非回到计划）
3. P1：B3 -> B4 -> C5（记忆树检索与写回质量）
4. P1：D6 -> E2（受控多次窗口对照 + 正式 parity）
5. P2：B6 + D3（权限与压缩稳定性优化）

---

## 5. 每个子任务的标准实现模板

每个子任务按同一模板执行，避免“做了但不可验收”：

1. 输入：request/task/snapshot 的最小必要字段。
2. 处理：明确调用函数与数据流。
3. 输出：新增/修改了哪些结构化对象。
4. 验证：单测或 suite 的通过条件。
5. 观测：artifact/log 里可直接定位的证据路径。

---

## 6. 关键代码与协议锚点

- runtime 主循环：packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py
- restart 快照：packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py
- work tree 恢复：packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover.py
- prompt 编译：packages/python-sdk/src/yggdrasil_sdk/prompting.py
- 任务接管：modules/task-takeover/src/yggdrasil_task_takeover/plugin.py
- 记忆检索：modules/text-memory/src/yggdrasil_text_memory/plugin.py
- 软遗忘：modules/memory-organizer/src/yggdrasil_memory_organizer/plugin.py
- G4 suite case：packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_g4.py

---

## 7. 当前结论

1. 记忆树 Agent 的完整工作可拆成 26 个最小可推进子任务。
2. 真正决定是否达到“伪无限上下文交付闭环”的核心，不在 A/B 基础层，而在 D4/D5/D6 + E2。
3. 实施上应先确保“恢复态合同一致 + work tree 持续执行”，再扩 provider 与压力规模；否则只会重复得到结构性 pass，而非交付级 parity。

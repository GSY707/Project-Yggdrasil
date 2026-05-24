# 提示词、启动流程、工作流程重做执行文档（2026-05-23）

## 0. 来源与结论

本执行文档以 `docs/new/工作树.md`、`docs/new/元提示词.md`、`docs/new/世界树计划正式项目定义.md` 三份材料为准。

本轮变更的核心结论是：世界树运行时应从“代码强控 LLM 的任务状态机”转为“代码为 LLM 提供记忆、身体、边界、协作和反馈世界”。Boot Prompt 只负责唤醒、寻址和最低生存法则；工作树负责执行栈和工作记忆；工作流程由 LLM 基于当前工作节点、记忆树和工具索引主动推进。

## 1. 执行原则

1. 记忆树是长期状态主体，上下文窗口只是当前工作缓存。
2. Prompt 不承载业务知识，只提供隐性倾向、启动法则和当前现场恢复信息。
3. 工作树不是外部项目管理清单，而是 `我要干什么` 根分支下的动态工作记忆。
4. 系统维护拓扑、版本、权限、审计和工具边界；LLM 负责语义判断、节点摘要、经验上浮和下潜决策。
5. 记忆更新优先级高于任务推进。关键新知、失败原因、约束和关联必须及时写树。
6. 大量未知文件、长文本或非决策性重活必须优先委派 Sub-Agent 预读、建树和摘要。
7. 当前任务结束不能等同于单次 LLM 输出结束。任务根节点完成后进入待批准结束状态，再由用户或上层流程批准完成。
8. 工作树必须配套 `WorkContextStack`：下探子节点时 push frame，完成子节点时 pop frame 回父级上下文并追加子节点摘要，默认不通过窗口重启回到父节点。

## 2. 现状差距

| 区域 | 当前状态 | 主要差距 | 目标状态 |
| --- | --- | --- | --- |
| Prompt | `compile_runtime_prompt()` 混合 profile、seed、工具、运行态和响应要求 | Boot Prompt 与场景身份、输出契约仍耦合 | Boot Prompt 只包含 I/O 绑定、根指针、行为宪法、PC 恢复 |
| 启动 | `build_root_mount_package()` 挂载 identity/context/execution 引用和 `startupContract` | 缺少明确程序计数器、邮箱/待机语义、能力/工具/工作/知识加载顺序 | 启动后按根指针恢复现场，并进入待机或当前工作节点 |
| 工作树 | `WorkTreeProtocol` 是 takeover plan 的可恢复投影 | 节点缺少父子语义、执行摘要、工作节点标签、动态下潜/上浮 | 工作树成为执行栈、任务清单、上下文压缩返回指针 |
| 运行流程 | `execute_main_agent_work_item()` 倾向单轮执行后 completed/paused/restarting | 缺少“节点完成后写摘要再 pop 回父级上下文”的栈式闭环，完成判定过早 | 运行循环围绕当前工作节点和上下文栈推进，根节点完成后等待批准 |
| 记忆写入 | 支持 `<memory-write>` 标签写入 | 缺少正式的读索引/读节点/版本写/追加日志/提案合并工具语义 | 形成 LLM 可感知的记忆管理工具集和冲突降级路径 |
| 多 Agent | 已有 Sub-Agent、PR 协作等基础模块 | 缺少触发原则、工作树空间隔离、冲突仲裁协议 | Sub-Agent、Fork、联邦协作都以工作树节点隔离和摘要合并为边界 |

## 3. 目标运行模型

### 3.1 根指针

启动时必须向 LLM 暴露四类根指针：

- `[ID: 001 我是谁]`：人格、权限、能力、工具使用偏好、长期自我约束。
- `[ID: 002 我在哪]`：项目、世界、环境、来源边界和当前外部状态。
- `[ID: 003 我要干什么]`：工作树、当前工作节点、留言、任务预算和待机队列。
- `[NODE_ID: SYS_ROOT_PROTOCOL]`：系统宪法、底层协议和能力索引入口。

现有 `identity/context/execution` 命名可以保留为底层 rootBranch，但对 LLM 暴露时要映射为上述中文语义根。

### 3.2 Boot Prompt 四段

Boot Prompt 必须稳定拆成四段：

1. 物理接口绑定：声明 LLM 只能通过结构化工具、MCP 泛型工具和指定消息工具触碰外界。
2. 世界地图根指针：给出三大根节点和系统宪法指针，不内嵌完整业务知识。
3. 行为宪法：说明写入限制、拓扑宽度限制、Sub-Agent 免死金牌、节点命名以 `questions_it_answers` 为路牌。
4. 现场恢复：注入当前 `Working_Node`、resume/restart memo、邮箱/待机状态和下一步需要判断的入口。

### 3.3 工作节点标签

每次进入工作树节点时，上下文必须带有稳定标签：

```text
<Working_Node: node_id>
```

该标签同时承担三件事：

- 物理书签：锚定当前认知焦点。
- 返回指针：节点完成、失败或压缩后回到父节点。
- 压缩边界：上下文压缩工具以该标签定位压缩起点、终点和恢复展开点。

### 3.4 工作树节点 v0.2

在现有 `WorkTreeNode` 基础上增加语义字段，保持向后兼容：

```yaml
WorkTreeNodeV2:
  id: string
  parentNodeId: string|null
  title: string
  questionsItAnswers: [string]
  nodeText: string                 # 50 到 200 字，面向 LLM 的自然语言状态切片
  localGoal: string
  localConstraints: [string]
  localContextRefs: [EntityRef]
  workingNodeAnnotation: string    # 例如 <Working_Node: A.1.2>
  executionSummary: string|null    # 完成或失败后写入的高密度摘要
  status: pending|in-progress|summarizing|completed|failed|blocked|skipped
  relationIds: [string]
  priority: integer
  version: integer
```

`WorkTreeProtocol` 需要补充：

```yaml
WorkTreeProtocolV2:
  version: "0.2.0"
  rootNodeId: string
  currentNodeId: string|null
  loadedNodeIds: [string]
  indexMapRefs: [EntityRef]
  pcMemo: string|null
  status: planned|standby|active|paused|awaiting-approval|completed|failed
```

### 3.5 栈式上下文主流程

工作树 v0.2 必须支持主流程：

```text
<初始节点>启动内容
<工作开始>大致规划过程
<执行节点1>执行过程，继续往下探细节
<分过程1>继续细节下探
<最细节执行1>最细节执行的过程
```

当 `<最细节执行1>` 完成时，系统应写入该节点 `executionSummary`，pop 当前 frame，回到父级上下文：

```text
<初始节点>启动内容
<工作开始>大致规划过程
<执行节点1>执行过程，继续往下探细节
<分过程1>继续细节下探，最细节执行1完成
```

然后继续最细节执行2。分过程1完成后再 pop 回执行节点1，继续分过程2。这个流程依靠 `WorkContextStack` 维护上下文窗口和模型前缀缓存；窗口重启只作为预算、安全停止或 provider 限制下的 fallback。

## 4. 分阶段实施

### P0. 协议冻结与文档补齐

改动：

- 新增 `docs/specs/work-tree-protocol-v0.2.md`，冻结工作树节点 v0.2、状态机和压缩返回语义。
- 新增或更新 `docs/specs/agent-runtime-protocol-v0.2.md`，冻结启动、待机、运行、结束批准流程。
- 把 `docs/new/` 三份材料标记为本轮设计来源，避免继续引用不存在的 `docs/research/世界树计划正式项目定义.md`。

验收：

- 所有后续代码任务都能引用明确字段和状态迁移，不再依赖口头解释。

### P1. 数据契约与持久化

改动入口：

- `packages/python-sdk/src/yggdrasil_sdk/contracts.py`
- `packages/python-sdk/src/yggdrasil_sdk/domain.py`
- `packages/python-sdk/src/yggdrasil_sdk/persistence/orm.py`
- `migrations/versions/`

具体任务：

1. 扩展 `WorkTreeNode` 和 `WorkTreeProtocol`，新增 v0.2 字段，旧 v0.1 字段继续可读。
2. 为工作树节点补父子关系、执行摘要、`questionsItAnswers`、`workingNodeAnnotation`、`pcMemo`。
3. 增加 `WorkContextStack` / `WorkContextFrame` contract，记录 top frame、父帧、prefix cache key、child completion summaries 和 cursor state。
4. 允许 `TaskSnapshotSummary` 和 window execution artifact 记录 `currentNodeId`、`pcMemo`、`workingNodeAnnotation`、`topFrameId`、`stackDigest`。
5. 迁移时不破坏现有 takeover artifact，缺失 v0.2 字段时自动补 bootstrap 节点和 root frame。

验收：

- 旧测试继续通过。
- 新增单测覆盖 v0.1 artifact 读入并升级到 v0.2 工作树。

### P2. Boot Prompt 与 Prompt 编译

改动入口：

- `packages/python-sdk/src/yggdrasil_sdk/prompting.py`
- `applications/*/prompt-profiles/main-agent.yaml`
- `modules/subagent-runtime/prompt-profiles/subagent.yaml`
- `tests/test_prompting_runtime.py`

具体任务：

1. 在 `CompiledPrompt` 中引入 `bootSections` 或等价字段，明确四段 Boot Prompt。
2. 将 `kernelTruth` 中的系统级规则迁移到统一 Boot Prompt，应用 profile 只保留场景偏好。
3. `system_sections` 必须包含物理接口、根指针、行为宪法；`user_sections` 必须包含现场恢复、当前工作节点标签和能力/协议索引。
4. 编译恢复态 Prompt 时必须只出现一次 resume/restart memo，且必须携带 `Working_Node`。
5. Prompt 不再要求模型输出格式化待办，工作树父子结构承担计划清单。

验收：

- Prompt 单测断言 Boot Prompt 四段都存在。
- 应用场景文案不再污染 Boot Prompt。
- 恢复态 prompt 中 `Working_Node`、`pcMemo`、`memoryRetrievalState.workTreeNodeId` 一致。

### P3. 启动流程与现场恢复

改动入口：

- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/root_mount.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop_part_b.py`
- `modules/pause-resume/`
- `tests/runtime/test_runtime_restart_and_resume.py`

具体任务：

1. `build_root_mount_package()` 输出中文语义根指针、`SYS_ROOT_PROTOCOL`、能力索引、工具索引、邮箱/待机状态。
2. 启动加载顺序固定为：你的能力、你的工具、你的工作、你的知识。
3. resume/restart 优先恢复 `currentNodeId`、`workingNodeAnnotation`、`pcMemo`，再加载检索上下文。
4. 冷启动无任务时进入 `standby`，等待用户消息或邮箱消息，不直接跑任务。
5. 热启动有未完成工作节点时进入该节点，不重新生成完整初始计划。

验收：

- 冷启动 root mount 可说明自己在哪里、能做什么、当前是否待机。
- 窗口重启后回到同一工作节点，工作树指针不漂移。
- snapshot 损坏时拒绝恢复并保留错误原因。

### P4. 工作流程与工作树运行时

改动入口：

- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop_part_b.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop_transitions.py`
- `modules/task-takeover/`
- `tests/test_runtime_p4_foundation.py`

具体任务：

1. 新增工作树管理函数：创建子节点、切换当前节点、写执行摘要、完成节点、失败节点、上浮父节点、读取兄弟节点状态。
2. 新增上下文栈管理函数：`push_frame`、`pop_frame`、`update_cursor_state`、`append_child_completion_summary`、`persist_stack_snapshot`。
3. takeover plan 只作为初始工作树建议，不再锁死 LLM 动态扩树。
4. 当前节点完成前必须写 `executionSummary`；失败节点必须写避坑摘要。
5. 子节点完成后默认 pop 回父帧，不默认触发窗口重启。
6. 根节点完成后任务状态进入 `awaiting-approval`，不直接 `completed`。
7. `currentFocus` 从普通字符串降级为 UI 摘要，权威执行指针改为 `workTree.currentNodeId` 与 `contextStack.topFrame.nodeId`。

验收：

- 单个任务可以经历下潜、执行、摘要、上浮。
- 子节点完成后能回到父级上下文并继续下一个兄弟节点。
- 未写摘要不能完成或跳出当前节点。
- 任务最终需要显式批准完成。

### P5. 记忆工具与冲突处理

完成情况（2026/5/24）：已完成并补齐并发安全闭环。`tool_runtime.py` 现会向正式工具透传 `sourceWorkTreeNodeId`；`modules/text-memory/` 已暴露 `read_node`、`read_index`、`update_memory_with_version`、`append_memory_log`、`submit_memory_proposal`、`forget_node`；Prompt 已明确“正式记忆工具优先、`<memory-write>` 旁路次之”，并在宽节点/高冲突场景下优先引导创建细分子节点做空间隔离；其中 `append_memory_log` 已升级为仓储层原子追加，避免并发日志静默覆盖，相关回归覆盖见 `tests/runtime/test_runtime_core_and_memory.py`。

改动入口：

- `packages/python-sdk/src/yggdrasil_sdk/tool_runtime.py`
- `modules/text-memory/`
- `modules/shared-memory/`
- `modules/mcp-bridge/`
- `tests/test_m9_shared_memory.py`

具体任务：

1. 暴露 LLM 可见的记忆工具：读取记忆节点、读取记忆索引、更新记忆节点、遗忘记忆节点。
2. 更新记忆节点支持写、改、关联三种模式。
3. 并发冲突提供三条语义路径：`update_memory_with_version`、`append_memory_log`、`submit_memory_proposal`。
4. 当宏观节点过宽或写冲突风险高时，LLM 应优先创建细分子节点实现空间隔离。
5. 保留 `<memory-write>` 作为轻量旁路写入，但正式工具优先。

验收：

- 并发写同一节点不会静默覆盖。
- 版本冲突可转化为 LLM 可处理的合并任务。
- 所有写入带 `sourceWorkTreeNodeId`。

### P6. 多 Agent、侧信道和邮箱

完成情况（2026/5/24）：已形成闭环。`launch_subagent_task()` 会规范化 `workTreeNodeId` 绑定并生成 `subagentBudgetDecision` artifact；同一份节点绑定和预算决策会沿 launch payload、worker work item、readonly context、PR manifest 透传。`RuntimeRepository` 现已新增独立 `mailbox_messages` / `side_channel_events` 持久化表与 core-api 读写入口，并补齐 Alembic 迁移 `7ad7d9b8c4f1_runtime_mailbox_side_channel_tables.py`；`root_mount.py` 会优先从仓储读取 mailbox state，`execution_loop_part_b.py` 会在 standby 短路前把 pending mailbox 注入 `currentContext` 并消费，从而让 mailbox 真正唤醒待机任务；`takeover.py` 与 `collaboration_runtime_part_b.py` 现已支持把 sub-agent completion summary 合并回 parent work tree / `childCompletionSummaries`，再通过 mailbox + side-channel 唤醒 parent 继续汇总；`packages/frontend-sdk/src/types.ts` 与 `apps/web/app/components/task-detail-page.tsx` 现已把 `canApprove/canRequestRevision/recommendedRevisionNodeId`、`mailboxState/mailboxMessages`、`sideChannelEvents` 接入任务详情页，P6 不再只停留在后端返回字段。

改动入口：

- `modules/subagent-pr/`
- `services/worker/`
- `services/core-api/src/yggdrasil_core_api/api/routes/runtime.py`
- `packages/frontend-sdk/src/types.ts`
- `apps/web/app/components/task-detail-page.tsx`

具体任务：

1. `spawn_sub_agent` 成为大规模预读、建树、摘要和非决策重活的首选路径。
2. Fork 用于同级同构并行分支，分支必须绑定不同工作树子节点，预算按模型能力、节点复杂度、上下文窗口和成本动态分配。
3. 联邦 Agent 通过共享节点和独立 mailbox 表异步协作。
4. 主信道只保留常规 agent loop；侧信道承载非中断工具回执、邮箱通知和上下文警告。
5. 默认输出口不是对外消息通道；对外交流必须走消息工具或邮箱工具。

验收：

- Sub-Agent 结果能回写到对应工作树节点，并由主 Agent 摘要合并。
- 邮箱消息能在待机态唤醒任务。
- 邮箱使用独立 `mailbox` 表，而不是复用 outbox/event 作为主存储。
- Fork 预算分配 artifact 能说明每个子节点为什么选择对应模型和预算。
- 侧信道通知不会打断当前工具调用。

### P7. 评测、门禁和回滚

完成情况（2026/5/24）：P7 门禁已收口并通过。`tests/test_runtime_p4_foundation.py` 与 `tests/test_g4_multiscene.py` 已统一为单路径门禁：suite 运行可用且 recovery 场景全部按 `awaiting-approval` 契约断言，避免旧 completed 快速路径回流。本轮实测命令 `uv run pytest tests/test_g4_multiscene.py::test_g4_multiscene_suite_passes_official_scene_contracts tests/test_g4_multiscene.py::test_g4_multiscene_suite_encodes_single_path_recovery_contracts -q` 结果为 `2 passed`。

改动入口：

- `tests/test_prompting_runtime.py`
- `tests/test_runtime_p4_foundation.py`
- `tests/runtime/`
- `tests/test_g4_multiscene.py`
- `evaluation/suites/`

最小验证命令：

```powershell
uv run pytest tests/test_prompting_runtime.py tests/test_runtime_p4_foundation.py tests/runtime/test_runtime_restart_and_resume.py -q
```

涉及记忆写入和冲突处理时追加：

```powershell
uv run pytest tests/runtime/test_runtime_core_and_memory.py tests/test_m9_shared_memory.py -q
```

涉及应用场景 Prompt 时追加：

```powershell
uv run pytest tests/test_g4_multiscene.py -q
```

回滚策略：

- 新流程为默认且唯一运行路径，不再依赖任何运行时灰度开关。
- v0.2 contract 必须能读取 v0.1 artifact。
- 旧 `completed` 快速路径已退场；完成态统一经工作树进入 `awaiting-approval` 后再批准收口。

## 5. 完成判定

本轮重做完成时必须同时满足：

1. Boot Prompt 只承担启动法则和现场恢复，不再夹带场景业务知识。
2. 每个运行窗口都有稳定 `Working_Node`，Prompt、snapshot、window execution artifact 三者一致。
3. 工作树节点支持动态下潜、摘要上浮、失败避坑和父节点返回。
4. 记忆写入、检索和冲突处理都能关联到当前工作节点。
5. 冷启动进入待机，热启动恢复现场，长任务重启不丢当前节点。
6. 根任务完成后进入等待批准状态，而不是模型单次输出后直接完成。
7. 新增或改动文档均已登记到 `docs/DIRECTORY_REFERENCE.md`。

# LLM 长程控制过度设计审计（2026-06-27）

## 结论

当前项目已经比较重视“稳”，但长程 / 超长程任务的更大问题是“够不够长”。系统里有一批为了防错而叠加的状态、检测、门禁和提示词规则，它们会把 LLM 从持续工作拉回“解释状态 / 满足格式 / 等待批准 / 汇报阻断”的循环，导致注意力被稀释，长程工作长度被截断。

更合适的方向是：LLM 全程控制工作，runtime 只做安全边界、资源边界、持久化和后台审计。普通进度、未决项、局部状态、计划变化应优先由 LLM 用自然语言工作日志表达，而不是转成大量硬状态和每轮 prompt 检测项。

## 保留边界

以下不应删除，只能减小它们进入 prompt 的频率和体积：

- 外部危险动作权限：删除数据、发布、网络执行、shell 执行、付款、真实 provider 高成本调用。
- durable snapshot / resume：长任务必须能恢复，但恢复真相不应每轮完整塞给 LLM。
- 预算上限：避免无限烧钱，但预算应更像 resource lease，而不是任务语义状态。
- 工具调用审计：保留日志和回放，不应变成每轮模型必须复述的检查清单。
- 用户明确要求审批的最终交付：保留审批；非破坏性长程内部节点不应反复进入审批态。

## 过度设计点

### P0：prompt response requirements 过度编排

位置：

- `packages/python-sdk/src/yggdrasil_sdk/prompting.py`
- `tests/test_prompting_runtime.py`

审计时问题：

- `_format_response_requirements()` 每轮给模型大量“必须 / 不得 / 只能”规则。
- 规则把工作树拓扑、父节点编排、child 行为、delivery readiness、恢复态 judgment、memory-write、clarification gate 都塞进同一个输出要求段。
- 这会让模型优先满足合同文本，而不是持续推进工作。

应改方向：

- 把 response requirements 收敛成 3 条以内：
  1. 当前目标是什么。
  2. 允许自主推进、拆分、执行、记录。
  3. 只有安全/预算/用户审批边界会中断。
- 工作树规则不应每轮重复；改为短 `runtime_hints`，且只在偏离时出现。
- `judgment`、formal footer、节点归属等格式不应强制每轮出现。

### P0：delivery gate 把格式完整性当硬任务状态

位置：

- `modules/task-takeover/src/yggdrasil_task_takeover/plugin.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/transitions.py`
- `tests/test_task_takeover.py`
- `tests/test_runtime_p2_delivery_gate.py`

现状问题：

- `delivery.result / evidence / pending / incomplete` 全部是 hard gate。
- 缺少 `pending` 或 `incomplete` 会触发 `delivery-gate-blocked` / retry / failed。
- 这会让模型为了过格式门而交付，而不是自然继续工作。

应改方向：

- hard gate 只保留真正的安全 / 证据边界：
  - 需要 web/source URL 时不能伪造来源。
  - 需要真实测试时不能谎称已跑。
  - 破坏性操作必须确认。
- `pending` / `incomplete` 默认降为 advisory 或由 LLM 自然语言说明。
- delivery parser 只做后台审计，不应主动把任务打成 failed。

本轮处理：

- `delivery.result / evidence` 保留为 advisory，`pending / incomplete` 不再作为 verification item。
- `delivery-gate-blocked` 不再直接把任务打成 failed；安全 / 来源证据类 hard gate 仍保留。
- 工具循环和工具轮次上限 fallback 不再强制输出固定四段交付模板。

### P0：needs-clarification + allowToolExecution=false 限制探索

位置：

- `packages/python-sdk/src/yggdrasil_sdk/prompting.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/transitions.py`
- `tests/test_runtime_p4_stability_hardening.py`
- `tests/test_runtime_p2_delivery_gate.py`

审计时问题：

- `needs-clarification` 会把任务变成“先确认再执行”。
- 某些链路会配合 `allowToolExecution=false`，导致 LLM 无法通过工具探索来澄清。
- 对长任务来说，很多“澄清”本来应该通过小步调查解决，而不是等用户确认。

应改方向：

- `needs-clarification` 不应是阻断执行的状态；应变成 LLM 工作日志中的“clarification needed”标记。
- 默认允许 read-only / inspect / search / grep / test-discovery 工具。
- 只有写入、删除、发布、付款、外部网络高风险动作需要确认。

本轮处理：

- clarification 态在 `allowToolExecution=false` 时默认仍暴露只读工具子集。
- invoke 层同步使用只读工具过滤，不再只在 prompt 层“说可以探索”。
- 普通 takeover confirmation 默认不再把协议推入 `needs-clarification`；只有显式要求确认或真实 ambiguity 才阻断。

### P1：workTreeResolution 从提示变成了控制器

位置：

- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/work_tree_graph.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/worker.py`
- `packages/python-sdk/src/yggdrasil_sdk/prompting.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover.py`

审计时问题：

- `recommendedAction` / `deliveryReadiness` 曾经能阻断交付。
- 它解决了“切一次任务就交付”，但如果继续加强，会把 LLM 从控制者降级为执行 controller 指令。
- 每轮展示 readiness / blocker 也会增加注意力税。

应改方向：

- 保留后台 `frontierItems`，但 `recommendedAction` 默认不进 prompt。
- prompt 只给 LLM 一个极短的“当前未解决主题摘要”，不要求服从动作。
- delivery readiness 不应阻断普通继续工作；只在模型明确声明最终完成时参与审计。
- 允许 LLM 自然语言声明“我先不交付，继续做 X”，runtime 不应强行解释为 blocked。

本轮处理：

- prompt 中 `work_tree_resolution` 改为 `runtime_hints`，并明确是辅助线索，不覆盖任务 / 工具 / 用户请求 / 当前节点。
- delivery reducer 只把 `missing-target-evidence` 这类真实证据缺口作为 hard blocker；`open-frontier-pressure`、`policy-not-ready` 等降级为提示 / 审计。
- 相关测试从“开放前沿必须阻断”改为“开放前沿只提示，证据缺口才阻断”。

### P1：状态重复且层级过多

位置：

- `packages/python-sdk/src/yggdrasil_sdk/contracts.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/root_mount.py`

现状问题：

- `TaskRuntimeState.phase`、`WorkTreeProtocol.status`、`WorkTreeNode.phase/status`、`TaskTakeoverProtocol.currentPhase/status`、`WorkContextFrame.status`、snapshot status、transition outcome 同时存在。
- 很多状态是过渡设计，语义相互覆盖，例如 `verified`、`awaiting-approval`、`delivery`、`summarizing`、`needs-clarification`。
- 状态越多，越容易让测试和提示词绑定旧中间态，而不是绑定“LLM 是否还在有效工作”。

应改方向：

- 持久状态压到最小集合：
  - task：`running / paused / awaiting-user / completed / failed`
  - node：`open / done / abandoned`
  - snapshot：保留 storage lifecycle，不进入 LLM prompt。
- 其他状态转为自然语言字段：
  - `progress_note`
  - `current_intent`
  - `open_questions`
  - `next_action`
- transition outcome 只作审计，不作业务协议。

### P1：awaiting-approval 过早成为任务收口点

位置：

- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_control.py`
- `tests/test_runtime_p4_foundation.py`

现状问题：

- root 完成后进入 `awaiting-approval`，再由外部 approve 变成 `completed`。
- 对普通短任务是合理的；对超长任务会导致频繁停在审批态。
- 如果 LLM 需要持续推进“下一阶段”，这个状态会过早切断工作。

应改方向：

- 引入“LLM 自主继续”默认：非破坏性任务 root 汇总后可以自动创建下一工作节点，而不是停审批。
- `awaiting-approval` 仅用于用户显式要求最终确认、外部发布、删除、付款、不可逆操作。
- approval 是用户交互边界，不是每个 root 汇总的默认边界。

### P1：Fork ready-set 和 maxForks 以调度状态限制工作长度

位置：

- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/work_tree_graph.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/fork_runtime.py`
- `tests/runtime/test_fork_launch_planner.py`

现状问题：

- `maxForks`、`reserveParentMergeSlots`、`allowRecursiveFork` 是资源保护，但容易变成工作形态限制。
- ready/blocked set 暗示 runtime 决定哪个 child 能走，而不是 LLM 持续管理队列。

应改方向：

- scheduler 只做 resource lease：并发槽、成本、模型额度。
- LLM 决定 work queue 的语义顺序。
- blocked set 不进入 prompt；只在资源无法分配或依赖真实缺失时报告。

### P2：memory-write 和 validation blocked 列表太像任务状态

位置：

- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/state_memory.py`
- `packages/python-sdk/src/yggdrasil_sdk/prompting.py`

现状问题：

- `<memory-write>` 被解析、校验、应用、blocked，返回复杂结构。
- 对 LLM 来说，记忆应是工作日志和长期上下文，不应每次写入都变成一个阻断面。

应改方向：

- 默认将失败写入转为“记忆提案”或 append-only journal，而不是 blocked。
- 只在权限越界、版本冲突、目标节点不存在且无法推断时阻断。
- prompt 中不要反复解释 memory-write 语法；工具 schema 足够时让工具承担。

### P2：root mount / startup contract 过重

位置：

- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/root_mount.py`
- `packages/python-sdk/src/yggdrasil_sdk/prompting.py`

现状问题：

- root mount 同时承载 identity/context/execution roots、startup mode、tool index、capability index、mailbox、standby、semantic roots。
- 这些对 runtime 有用，但不应每轮完整进入 LLM 注意力。

应改方向：

- prompt 只保留当前任务相关根摘要和工具简表。
- 详细 root mount 改为可按需查询。
- startup contract 作为后台审计，不作为每轮工作合同。

## Batch 1-4 落地状态

### Batch 1：先减 prompt 注意力税

- 已完成：`_format_response_requirements()` 收敛为短合同。
- 已完成：移除每轮强制 `judgment`、memory-write 标签教学、root/child 大段编排说明。
- 已完成：`work_tree_resolution` 渲染为 `runtime_hints`，不再出现“必须优先服从”。
- 已完成：takeover prompt 去掉计划质量、返工率、交付完整度等中间指标。

### Batch 2：把 delivery gate 从硬门禁降为审计

- 已完成：`pending` / `incomplete` 从 hard gate 移除。
- 已完成：`delivery.result / evidence` 仅 advisory。
- 已完成：`delivery-gate-blocked` 不直接 failed；继续路径存在时转 continuation，否则进入 `resume-blocked`。
- 已完成：保留 web/source evidence gate 作为 hard gate。

### Batch 3：needs-clarification 不再禁工具

- 已完成：clarification 默认允许 read-only 工具。
- 已完成：prompt 和 invoke 两层都使用只读工具过滤。
- 已完成：普通 takeover confirmation 默认不再进入 `needs-clarification`。
- 部分完成：`needs-clarification` 仍作为持久协议状态存在，后续应继续压缩为更轻的用户输入 / blocker 语义。

### Batch 4：状态瘦身

- 已完成：prompt 不再暴露 `currentPhase`、计划质量、返工率、交付完整度、栈 digest 等过渡指标。
- 已完成：resolution action 从交付硬控制降为 `runtime_hints`。
- 已完成：删除未引用的 `runtime_kernel/takeover_work_tree_runtime.py`，避免旧 sibling 选择语义继续污染路线。
- 已完成：工具 fallback 不再塞任务无关的比较矩阵、来源表和固定 heading。
- 部分完成：协议层状态集合尚未整体收敛，`awaiting-approval` 默认收口仍保留。

## 新目标口径

长程任务不是“每轮都被检查得足够稳”，而是“LLM 能持续拥有工作控制权”。

运行时应该做：

- 持久化 LLM 工作日志。
- 提供当前任务、上下文、工具和资源。
- 在安全、预算、不可逆动作处中断。
- 后台审计可回放事实。

运行时不应该做：

- 每轮替 LLM 决定下一步语义动作。
- 把格式缺失当成任务失败。
- 用大量状态名代替 LLM 的自然语言进度描述。
- 把检测结果持续塞进 prompt 造成注意力稀释。

## 本轮仍保留 / 后续

本轮没有一次性删除所有状态，原因不是方向不成立，而是这些点已经触及产品控制面和历史评测口径：

- `awaiting-approval` 默认 root 收口仍保留；后续应改成仅在用户显式要求确认、外部发布、删除、付款、不可逆操作时进入。
- `TaskTakeoverProtocol.status/currentPhase`、`WorkTreeNode.phase/status`、transition outcome 仍有重复；后续应按 durable state 与 audit note 拆分。
- Fork ready-set 仍包含资源调度以外的语义 blocked 信息；后续应把调度器收敛成 resource lease，语义顺序交给 LLM。
- root mount/startup contract 仍偏重；后续应继续把非当前任务信息改为按需查询。

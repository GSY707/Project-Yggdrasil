# 滚动前沿工作树分辨率运行提示说明（2026-06-27）

## 目标

本实现把长程 / 超长程任务的推进线索从“LLM 是否愿意认真规划”改成“当前工作树是否还有未解决前沿和真实证据缺口”。宽泛节点是合法节点，不再要求先证明自己是叶子；宽泛节点可以继续拆、局部执行、拿到结果后再继续规划。

这轮实现完整接入正式运行链，但仍不新增数据库状态，不扩展 `WorkTreeProtocol.status` / `WorkTreeNode.status`。运行时只传递派生运行提示 `workTreeResolution`，动作数量固定为 5 个：

- `refine`：继续提高当前节点分辨率，创建更小范围的子节点或重排局部计划。
- `work`：在当前分辨率下做探测、验证或局部执行。
- `merge`：子节点尚未收束，父节点应合并 / 等待 / 重新编排，而不是交付。
- `deliver`：开放前沿压力低、子节点已收束、证据满足时提示可以交付。
- `block`：当前节点硬阻塞，等待外部输入或环境变化。

## 已采纳的设计判断

1. 任务可以无限细分，细分越多通常质量越高；系统不能假定一次规划足够。
2. 叶子节点不应成为硬前提。宽泛节点必须存在，否则大型任务规划无法形成。
3. 防止“切一次任务就开始交付”不应主要靠权限隔离，而应靠前沿提示、证据事实和 LLM 自主继续工作。
4. 工作树必须支持滚动规划：先计划一部分，拿到证据后继续计划。
5. LLM 默认会走最快输出路径；运行时提示应让模型看到未解决前沿，但不能把提示扩张成替 LLM 决策的硬控制器。
6. 状态数必须克制。功能相近的状态合并，避免把长程控制做成状态爆炸。

## 八个长程核心前沿

`build_long_run_core_frontiers()` 固定返回 8 个超长程任务必须显式处理的前沿：

| 前沿 ID | 类别 | 作用 |
| --- | --- | --- |
| `queue-reliability` | `reliability` | worker 队列需要 ack、visibility timeout、reclaim 和幂等 work item。 |
| `durable-snapshot` | `durability` | resume 真相必须是 durable snapshot，不能依赖 Redis TTL package。 |
| `transactional-node` | `transaction` | 节点执行需要前置条件、后置条件、版本检查和幂等键。 |
| `plan-lifecycle` | `planning` | 计划节点需要生命周期、替代、过期和 stale-plan 检测。 |
| `typed-merge` | `merge` | Fork / child 结果需要 typed envelope 合并，而不是只靠自然语言摘要。 |
| `semantic-gc` | `hygiene` | 长工作树需要语义垃圾回收，处理废旧计划、摘要和 transcript。 |
| `long-run-eval` | `evaluation` | 长程 / 超长程需要显式 deterministic + live gate，不把 smoke 当证据。 |
| `observability-replay` | `observability` | 超长 run 需要可回放 trace，定位首次错误计划、摘要或工具转移。 |

这些不是新的任务状态，而是 `FrontierItem`，可挂到任意工作树节点上，参与前沿压力计算。

## 运行时入口

实现入口位于：

- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/work_tree_graph.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/worker.py`
- `packages/python-sdk/src/yggdrasil_sdk/prompting.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/transitions.py`
- `tests/runtime/test_work_tree_graph_scheduler.py`
- `tests/test_prompting_runtime.py`

新增导出：

- `FrontierItem`
- `WorkTreeResolutionPolicy`
- `DeliveryReadinessResult`
- `NodeResolutionAssessment`
- `build_long_run_core_frontiers()`
- `assess_node_resolution()`
- `compute_delivery_readiness()`

## 正式执行链

1. `worker.py` 在 takeover/work tree 已同步后调用 `assess_node_resolution()`，把结果写入 `request.workTreeResolution`、`rootMount.workTreeResolution` 和 `request.workTreeGraphState`。
2. 若请求设置 `enableLongRunCoreFrontiers=true`，worker 会把八个长程核心前沿合并进 `workTreeGraphState.frontierItems[]`，但不会重复添加同 ID 前沿。
3. `prompting.py` 在恢复态 prompt 中新增 `<runtime_hints>` 区块，只展示当前节点、建议下一步、readiness 和最高压力的前 3 个开放前沿，避免把模型注意力浪费在全局大计划。
4. `response_requirements` 明确 `runtime_hints` 只是辅助线索，不覆盖任务、工具、用户请求和当前工作节点；当交付未就绪时，模型应继续推进有价值的前沿，但不被强制套固定交付模板。
5. `transitions.py` 把 `request.workTreeResolution` 传入 `advance_takeover_after_delivery()`。
6. `takeover.py` 在交付推进前合并上游 `deliveryReadiness` 与本地重算结果；只有真实 `missing-target-evidence` 仍缺失时才返回 `work-tree-resolution-blocked` continuation。开放前沿、策略未就绪等信号只保留为运行提示 / 审计线索，未收束 child 由父节点编排路径处理。

这条链路的关键点是：LLM 可以尝试输出候选交付，runtime 不再因为格式或普通前沿压力替 LLM 判死；只有任务结构硬事实（例如声明了 expected evidence 但没有证据）才阻断。防“切一次任务就交付”不靠权限隔离，而靠前沿提示、证据事实和后续工作树继续滚动。

## 合同缝隙处理

本轮额外补了 3 个容易导致“看似接入、实际可绕过”的缝隙：

1. 证据 readiness 前移：`expectedEvidence` 声明后，只要当前节点还没有 `producedEvidenceRefs`，交付前就会出现 `missing-target-evidence`，不再等节点已 `completed/summarizing` 后才检查。
2. 上游 readiness 非权威：`advance_takeover_after_delivery()` 会读取 `workTreeResolution.deliveryReadiness`，但只把 `missing-target-evidence` 这类任务证据硬事实升级成阻断。`open-frontier-pressure`、`policy-not-ready` 等不再关闭 LLM 的交付 / 继续判断。
3. 陈旧 payload 清理：worker 在 takeover/work tree 缺失、当前节点为空或 assessment 失败时，会删除 `request/rootMount` 上旧的 `workTreeResolution`，避免 stale 控制信号进入 prompt 或 transition。

证据门槛允许本轮真实产生的 `evidenceRefs` 消解 `:missing-evidence` 派生前沿，并在 `complete_current_work_node()` 中写回当前节点 `producedEvidenceRefs`。这避免“节点永远无法完成”，同时保留无证据交付阻断。

## 前沿压力规则

`assess_node_resolution()` 会合并两类前沿：

1. `graphState.frontierItems[]` 传入的显式前沿。
2. 由当前工作树派生的前沿。

派生前沿包括：

- 宽泛 frame：低 `detailLevel` 且文本过长、期望证据过多或 child 数超过内联阈值。
- 未收束子节点：父节点应 `merge` 或继续编排，而不是交付。
- 失败子节点缺少 `failureSummary`：父节点还不能吸收失败经验。
- 已声明 `expectedEvidence` 但缺少 `producedEvidenceRefs`：交付证据不足。
- 计划反复变化：超过 `planChurnRefineThreshold` 后要求提高分辨率。
- 同一分辨率失败超预算：超过 `failureRetryBudget` 后要求拆小或换策略。
- root 有候选交付但 child 未收束：候选交付只能作为阶段摘要。

## 交付 readiness

`compute_delivery_readiness()` 不修改工作树状态，只返回派生结果：

- `ready`
- `blockers`
- `openFrontierCount`
- `maxFrontierPressure`

当前阻断项：

- `open-frontier-pressure`
- `unresolved-children`
- `target-not-summarized`
- `missing-target-evidence`

这些 blocker 主要供 prompt 和审计使用。Reducer 只把 `missing-target-evidence` 作为硬阻断；`unresolved-children` 由父节点编排路径处理；`open-frontier-pressure` 与策略类 blocker 作为继续工作的提示，不直接阻断完成。

## 失败预算

失败预算不用于追求零失败，而用于控制何时提高分辨率：

- 未超预算：可以继续同分辨率 `work`。
- 超预算：转为 `refine`，要求拆小、改探测路径或回到父节点重排。

这避免 LLM 在坏节点里反复硬编答案，也避免一次失败就把整个任务打死。

## 已验证

已新增并通过以下回归：

```powershell
uv run pytest tests/runtime/test_work_tree_graph_scheduler.py tests/test_prompting_runtime.py -q --basetemp=tmp/pytest-frontier-fix-subagent-gaps
uv run ruff check packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/work_tree_graph.py packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/__init__.py packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/worker.py packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop/transitions.py packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover.py packages/python-sdk/src/yggdrasil_sdk/prompting.py tests/runtime/test_work_tree_graph_scheduler.py tests/test_prompting_runtime.py
```

覆盖内容：

- 宽泛 root frame 不直接交付，而是推荐 `refine`。
- child 未收束时，候选交付只作为阶段摘要，delivery readiness 阻断。
- 失败预算超限后，同分辨率重试转为 `refine`。
- 低前沿压力、证据齐备、节点完成时允许 `deliver`。
- 八个长程核心缺口全部进入默认前沿种子。
- prompt 会渲染 `<runtime_hints>`；开放前沿只展示 severity 最高的 3 个。
- response requirements 明确 `runtime_hints` 是辅助线索，不是硬控制器。
- delivery reducer 不再因开放前沿或上游 policy-not-ready 返回 `work-tree-resolution-blocked`，且不新增协议状态。
- expected evidence 缺失会在节点完成前阻断交付；本轮真实 `evidenceRefs` 会写回 `producedEvidenceRefs`。
- 上游 `deliveryReadiness.ready=false` 只有在 surviving blocker 是 `missing-target-evidence` 时才阻断交付。
- worker assessment 失败会清除陈旧 `workTreeResolution`。

## 后续

后续应继续把八个核心前沿逐项落成真实 durable 机制和评测门槛，尤其是 queue ack/reclaim、durable snapshot、transactional node 和 replay。当前本轮只完成“运行时提示 + prompt 瘦身 + 证据硬门槛”的闭环，不声称已经完成这些底层长期可靠性工程。

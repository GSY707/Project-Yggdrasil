# Work Tree Protocol v0.1

- 文档状态：Candidate
- 版本：v0.1
- 日期：2026-05-15
- 关联文档：
  - [任务接管协议 v0.1](task-takeover-protocol-v0.1.md)
  - [运行时与工具数据规格 v0.1](runtime-domain-data-spec-v0.1.md)
  - [Gate 3 正式闭环报告（2026-05-15）](../research/g3-closeout-2026-05-15.md)

## 1. 目标

Work tree 用来把任务接管协议中的计划步骤投影成一棵可恢复、可验证、可落盘的正式执行树。

它不替代计划本身，而是负责回答下面三个问题：

1. 当前任务正在树上的哪个节点。
2. 下一次恢复应该从哪个节点或 recovery anchor 继续。
3. 执行完成时，哪些计划步骤已经被正式验证并交付。

## 2. 对象结构

当前正式对象定义在 [packages/python-sdk/src/yggdrasil_sdk/contracts.py](../../packages/python-sdk/src/yggdrasil_sdk/contracts.py) 中。

### 2.1 WorkTreeNode

```yaml
WorkTreeNode:
  id: string
  title: string
  phase: planning | executing | recovering | restarting | verification | delivery
  status: pending | in-progress | completed | blocked | skipped
  planStepIds: [string]
  constraintIds: [string]
  dependsOn: [string]
  expectedEvidence: [string]
  recoveryAnchor: string|null
```

### 2.2 WorkTreeProtocol

```yaml
WorkTreeProtocol:
  version: string
  rootObjective: string
  status: planned | active | paused | verified | completed
  currentNodeId: string|null
  nodes: [WorkTreeNode]
  recoveryAnchor: string|null
  entropyBudgetRemaining: integer
```

## 3. 运行时约束

1. Work tree 必须从 `TaskTakeoverProtocol.plan` 与 `constraints` 派生，不能由模型自由生成未受约束的新节点。
2. `currentNodeId` 必须始终指向当前活跃节点，或在任务完成时为 `null`。
3. 带 `recoveryAnchor` 的节点必须可映射到 pause/resume 或 repair 后的正式恢复入口。
4. 任务完成时，runtime 必须把 work tree 的总体状态同步为 `completed` 并重写正式工件。
5. Prompt、request transcript、runtime 结果和 takeover artifact 必须看到同一份 work tree。

## 4. 状态语义

- `planned`：树已生成，但尚未进入正式执行。
- `active`：至少一个节点已进入执行态或恢复态。
- `paused`：任务已进入正式可恢复状态，等待 resume。
- `verified`：执行完成，验证已通过，但最终交付或工件刷新尚未结束。
- `completed`：执行、验证、交付和工件刷新全部完成。

## 5. Gate 3 冻结决策

Gate 3 先冻结最小正式边界，不额外引入超图推理、动态重排或模型自由扩树：

1. work tree 只表达 takeover plan 的正式执行投影。
2. entropy budget 只作为 runtime 可观测字段，不作为当前版本的硬失败条件。
3. recovery anchor 只允许引用正式 resume / repair 入口，不允许引用临时脚本或人工笔记。

## 6. 后续扩展边界

Gate 4 以后可以扩展：

1. work tree 与复杂文件拆分样本的固定回归绑定。
2. work tree 节点级耗时、首 token、工具轮次和返工率观测。
3. work tree 到 hypergraph reasoning 的更高阶映射。
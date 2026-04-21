# Hook 点协议 v0.1

- 文档状态：Draft
- 版本：v0.1
- 日期：2026-04-16

## 1. 目标

定义模块可以向系统贡献行为的位置、输入输出契约与执行约束。

Hook 不是任意代码插入点，而是被平台显式治理的扩展接口。

## 2. Hook 分类

- lifecycle：模块生命周期相关。
- pipeline：参与某条领域处理流水线。
- contributor：向系统注册新能力、路由、工具、面板等。
- validator：执行校验、评分或约束检查。

## 3. 通用执行规则

- 每个 hook 必须声明 name、type、timeoutMs、idempotent。
- hook 输入必须满足平台定义的 schema。
- 除非文档允许，否则 hook 不得直接修改输入对象。
- pipeline hook 的输出必须可合并且可审计。
- hook 超时、抛错或返回非法结果时，平台可跳过、降级或隔离模块。

## 4. Hook 注册模型

每个 hook 注册项最少包含：

- name：hook 名称。
- implementation：入口实现。
- order：执行顺序或优先级。
- timeoutMs：超时。
- idempotent：是否幂等。
- sideEffects：none、read-only、controlled-write。

## 5. 第一版标准 Hook 清单

### 5.1 生命周期 Hook

- module.install.validate
- module.install.plan-migrations
- module.enable.preflight
- module.enable.post-activate
- module.disable.pre-drain
- module.disable.post-stop
- module.health.report

### 5.2 API 与 Worker 扩展 Hook

- api.routes.register
- api.schemas.register
- worker.activities.register
- worker.schedules.register

### 5.3 Agent 与任务运行时 Hook

- agent.tools.register
- agent.startup.mount-root
- agent.startup.extend-system-context
- prompt.profiles.register
- prompt.seed-templates.register
- task.pause.prepare
- task.resume.rehydrate

### 5.4 记忆流水线 Hook

- memory.ingest.preprocess
- memory.ingest.plan-tree
- memory.ingest.suggest-links
- memory.retrieve.expand
- memory.retrieve.rerank
- memory.write.validate

### 5.5 上下文整理 Hook

- context.pruning.plan
- context.pruning.execute
- context.pruning.verify

### 5.6 前端扩展 Hook

- frontend.panels.register
- frontend.widgets.register
- frontend.commands.register
- frontend.routes.register

## 6. 关键 Hook 契约

### 6.1 memory.ingest.plan-tree

- 作用：根据输入片段与全局概览，生成候选树结构与候选父节点方案。
- 输入：
  - importJob
  - orderedFragments
  - globalOutline
  - budget
- 输出：
  - candidateParents
  - candidateNodes
  - confidence
- 约束：
  - 不得直接提交最终写入。
  - 输出必须可被人工或主 Agent 审核。

### 6.2 agent.startup.mount-root

- 作用：参与根节点挂载与启动上下文组装。
- 输入：
  - projectId
  - taskId
  - rootBranches
  - startupPolicy
- 输出：
  - mountFragments
  - priority
- 约束：
  - 不得移除 Kernel 必需挂载项。

### 6.3 context.pruning.plan

- 作用：为困难任务生成上下文修剪计划。
- 输入：
  - nextObjective
  - currentContext
  - budget
  - protectedItems
- 输出：
  - retainedItems
  - compressedItems
  - droppedItems
  - rationale
- 约束：
  - 必须保留下一步任务强相关内容。
  - 不得无理由删除 protectedItems。

### 6.4 task.pause.prepare

- 作用：在安全停止点生成暂停快照。
- 输入：
  - taskState
  - pendingWrites
  - activeToolCalls
  - currentResponseState
- 输出：
  - snapshotDelta
  - safeToPause
  - blockers
- 约束：
  - 未冲刷完成的关键写入不得被静默丢弃。

### 6.5 task.resume.rehydrate

- 作用：在恢复任务时将快照还原成运行时上下文。
- 输入：
  - taskSnapshot
  - rootMounts
  - resumePolicy
- 输出：
  - restoredState
  - resumeMessage
  - followupActions

## 7. 冲突处理

- 同一 hook 若有多个实现，按 order 执行。
- contributor hook 输出冲突时，以唯一键去重或由 Kernel 合并。
- pipeline hook 输出冲突时，必须显式定义 mergeStrategy。
- 无法合并时，任务进入 failed 或 requires-review。

## 8. 幂等与副作用

- validator hook 必须幂等。
- contributor hook 应尽量幂等。
- controlled-write hook 必须声明写入对象范围，并记录审计日志。

## 9. 第一版约束

- 第一版优先开放最少 hook，不追求全开放插件平台。
- 高风险 hook 只能由内置模块或受信模块实现。
- 所有 hook 都必须有 contract test。
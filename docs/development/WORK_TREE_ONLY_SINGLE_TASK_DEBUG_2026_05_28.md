# Work-Tree Only 单任务调试基线（2026-05-28）

## 目标

在调试阶段先禁用记忆树相关能力，只保留工作树能力，验证 LLM 是否能按工作树语义完成一次真实任务。

## 本轮落地

- 在 `evalsuite_g4_real_task_work_tree_debug` 的两个 live case 中显式设置：
  - `activeCapabilities: ["task-takeover"]`
- 在 G4 live runner 启动请求构造中补齐能力透传：
  - `suite_cases_g4.py` 现在会把 case 里的 `activeCapabilities` 写入 `/runtime/tasks/{id}/start` payload。

## 预期行为

- root mount 仅挂载 `task-takeover`（以及核心运行时能力）。
- 运行时不再挂载 `text-memory`、`shared-memory`、`memory-organizer` 等记忆树相关能力。
- 调试关注点收敛到：
  - `currentNodeId`
  - `WorkContextStack`
  - child 完成/失败上浮
  - parent 编排与 `awaiting-approval`

## 验证命令

```powershell
corepack pnpm eval:g4:work-tree-debug
```

若只想先跑一条 case，可直接使用 evaluation CLI 的 case 过滤参数（若当前 CLI 版本支持），或临时在 suite 中保留单 case 后执行。

## 回滚方式

- 删除 `g4-real-task-work-tree-debug.json` 中两处 `activeCapabilities` 即可恢复到默认能力解析。
- 删除 `suite_cases_g4.py` 中 `activeCapabilities` 下发逻辑即可恢复旧行为。

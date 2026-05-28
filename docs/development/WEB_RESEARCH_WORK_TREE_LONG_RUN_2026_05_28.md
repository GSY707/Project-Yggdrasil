# Web Research Work-Tree Long 入口（2026-05-28）

## 目的

提供一个专门观察“工作树在长任务中的行为”的 live 入口：

- 真实网络搜索任务（Web search）
- 长任务多窗口 continuation
- 明确观察 parent/child 编排收敛

## 新增入口

- Suite: `evalsuite_g4_web_research_work_tree_long`
- 文件: `evaluation/suites/g4-web-research-work-tree-long.json`
- 命令: `corepack pnpm eval:g4:web-research:work-tree-long`

## 关键配置

- Provider 固定：`longcat / LongCat-2.0-Preview`
- 工具执行：开启（`allowToolExecution=true`）
- 能力收敛：`activeCapabilities=[task-takeover,mcp-bridge,context-pruning,text-memory]`
- 长任务压力：
  - `effectiveContextWindow=24000`
  - `forcedWindowRestartBudget=18`
  - `maxWindowCycles=36`
- 长任务验收门槛：
  - `acceptanceMinRestartCount=8`
  - `acceptanceMinWindowIndex=9`
  - `acceptanceMinCumulativeWindowSpanTokens=250000`

## 观测重点

- 工作树连续性：`workTreeContinuity0_1`
- 节点推进：`currentNodeId`、`workTreeNodeId`
- 续跑质量：`restartCount`、`windowIndex`、`cumulativeWindowSpanTokens`
- 交付质量：是否满足 `## 结果 / ## 证据 / ## 风险 / ## 已知问题`

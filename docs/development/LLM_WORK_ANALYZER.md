# LLM 工作分析器

## 目标

LLM 工作分析器用于对世界树 agent 的一次正式运行做 run-first 的结构化回放。它不依赖单一外部 trace，而是把数据库索引与本地 state 工件拼接成统一视图，服务两类主要场景：

- 评测：对同一任务在不同 provider、不同窗口策略、不同 prompt 版本下的执行过程做窗口级和工具级对照。
- 调试：定位“为什么这一窗失败 / fallback / 反复 tool loop / 恢复后偏成 planning stub / work tree 锚点漂移”。

## 数据源

分析器默认同时读取两类正式数据面：

- 数据库：tasks、agent_runs、model_invocations、task_snapshots、route_decisions、mailbox_messages、side_channel_events。
- state 工件：llm/requests、llm/responses、prompt/compiled、runtime/metrics、runtime/takeover、runtime/work-context-stack、runtime/window-executions。

这意味着它既能回答“这次 run 最终用了多少 token / cost / fallback”，也能回答“第几窗调用了什么工具、当时 work tree 节点是什么、恢复时拿了哪份 takeover/work-context-stack”。

## 粒度

分析器当前支持以下粒度：

- run：一次任务运行的总体摘要，适合控制面总览、回归统计和 live run 结论归档。
- window：按 invocation 归一化的窗口视图，展示 currentObjective/currentFocus、window metrics、work tree、memory retrieval 摘要和交付摘要。
- turn：按 roundSummaries 重建的轮次视图，适合看 tool-calls、budget-check、first-token latency、finishReason。
- tool：按 toolExecutions 或 toolExecutionSummaries 输出的工具视图，适合看工具名、成功率、duration、sourceWorkTreeNodeId 和失败摘要。
- artifact：按 request/response/prompt/metrics/takeover/work-context/window-execution 的文件清单输出，适合人工回溯原始工件。
- source：保留 route decisions、snapshots、mailbox、side-channel 和 run state 原始来源摘要，适合排障时做二次对照。

## 持久化位置

每次分析默认会把结果落到 state 目录：

- .yggdrasil/state/analysis/llm-work/{analysisId}.json
- .yggdrasil/state/analysis/llm-work/{analysisId}.md
- .yggdrasil/state/analysis/llm-work/latest-by-task/{taskId}.json

其中：

- json 适合后续自动评测、前端查询和脚本消费。
- md 适合人工审查和 issue/PR 中快速贴结论。
- latest-by-task 适合“给我当前任务最新分析”的调试入口。

## API

core-api 现提供三个正式入口：

- POST /runtime/analysis/runs：按 taskId、runId 或 invocationId 触发分析，可选 granularity 与 persist。
- GET /runtime/analysis/runs/{analysisId}：读取既有分析工件，可按 granularity 过滤返回视图。
- GET /tasks/{taskId}/analysis/latest：读取该任务最新分析；若尚无缓存，则会按该任务当前运行现场即时生成。

## CLI

当前提供两种命令行入口：

- uv run yggdrasil-llm-work-analysis --task-id <TASK_ID>
- uv run python scripts/analyze_llm_work_run.py --run-id <RUN_ID>

常用参数：

- --granularity run,window,tool
- --format json 或 --format md
- --output <PATH>
- --no-persist

## 评测与调试建议

- 评测对比优先保留 json：同一任务在不同 provider/window profile 下重跑后，直接对比 summary、windows、tools 三层差异。
- 本地调试优先看 window + artifact：先确认 workTreeCurrentNodeId、currentFocus、retrievalFingerprint，再回到 request/response 原文。
- 如果要调查 pause/resume 或恢复态偏航，优先联看 takeover、work-context-stack、windowExecutionArtifact 和 snapshots。

## 当前限制

- runtime/window-executions 目前更适合作为“补充证据”而不是唯一窗口历史源；当前窗口主骨架仍以 model_invocations + request/response/runtimeMetrics 为准。
- default 和 lean 审计级别下，tool 级细节可能只有 summary，没有完整 toolExecutions；分析器会降级输出 summary 视图。
- 这个版本先做本地 run-first 分析，不强依赖 Langfuse；如果要做 trace 对账，建议和 langfuse_trace_layered_analysis.py 联用。
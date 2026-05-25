# LLM 工作分析器使用说明书

> 面向需要查看、对比和排查世界树 Agent 运行过程的操作者、评测同学和开发者。

---

## 1. 这是什么

LLM 工作分析器用于把一次任务运行拆成多层结构化视图，帮助你回答下面这些问题：

- 这次任务一共跑了多少窗、多少轮、多少次工具调用？
- 哪一窗开始偏航、退化成 planning stub、触发 fallback 或失败？
- 某个工具是在什么 work tree 节点下执行的，耗时多久，结果是什么？
- 当前任务的 request/response/prompt/metrics/takeover 等工件是否都存在，缺哪一层？

它和普通日志页面的区别在于：

- 普通任务详情页偏任务控制和状态总览。
- 观测页偏 span、log、metric 信号聚合。
- LLM 工作分析器偏单任务运行过程的结构化回放。

---

## 2. Web 入口

当前 Web 已提供两个入口：

- 任务详情页摘要卡：/tasks/{taskId}
- 完整分析页：/tasks/{taskId}/analysis

推荐使用顺序：

1. 先在任务详情页看摘要卡，快速确认窗口数、工具数、工件覆盖率。
2. 再点“打开完整分析页”，进入完整的窗口、轮次、工具和工件视图。

---

## 3. 任务详情页怎么用

任务详情页中的“运行过程分析摘要”卡片会显示：

- Windows：当前分析识别出的窗口数，以及最新窗口编号和 restart 次数。
- Turns：当前分析识别出的轮次数、工具执行次数和 fallback 数。
- Tokens：输入 / 输出 token 总量。
- Artifacts：当前已找到的工件数量，例如 request、response、prompt、metrics。

这个摘要卡适合做两件事：

- 快速判断任务是否值得进一步排查。
- 在不离开任务详情页的情况下，先看最近 3 个窗口和最近几次工具执行。

### 刷新分析

如果任务刚运行完，或者你怀疑分析结果已经过时，可以点击“刷新分析”。

刷新行为会重新生成当前任务的最新分析工件，然后任务详情页会重新读取最新结果。

---

## 4. 完整分析页怎么看

完整分析页按五个主层次组织：

### 4.1 Coverage

这里先看覆盖率。它告诉你：

- request / response / prompt / metrics 是否都存在
- window-execution 是否有补充证据
- tool 记录是完整 detailed 还是只有 summary
- takeover protocol 和 work-context-stack 是否可读

如果覆盖率本身不完整，后面的分析要保守解读。

### 4.2 Windows

窗口视图最适合判断“任务在哪一窗开始出问题”。

重点关注：

- Current Objective / Current Focus：这窗到底在试图完成什么
- Work Tree Node / Recovery Anchor：执行锚点是否正确
- assistantTextSummary：这一窗实际交付了什么
- memoryRetrievalState：匹配了多少记忆节点，retrievalFingerprint 是否发生突变

常见排查方式：

- 如果 focus 和 objective 突然变空或变得很泛，通常是恢复/检索合同出了问题。
- 如果 work tree node 突然跳变，通常要回看 takeover 与上下文栈。

### 4.3 Turns

轮次视图主要用于看：

- 每一轮是 live、fallback 还是 budget-check
- finishReason 是 tool-calls、stop 还是 error
- toolCalls / toolFailures 数量
- latency 和 first-token latency 是否异常

如果一窗里 round 数异常增多，通常表示工具循环或上下文收敛不顺。

### 4.4 Tools

工具视图用于定位具体工具执行问题。

重点字段：

- toolName
- success / status
- durationMs
- sourceWorkTreeNodeId
- resultPreview / failureSummary

如果 sourceWorkTreeNodeId 不符合预期，说明模型是在错误的工作节点上下文里调了工具。

### 4.5 Artifacts

工件视图给出原始文件位置，适合进一步回看：

- llm-request
- llm-response
- compiled-prompt
- runtime-metrics
- takeover-protocol
- work-context-stack
- window-execution

当页面摘要不足时，应直接打开这里的 locator 对应文件做人工检查。

---

## 5. 推荐排障流程

### 场景 A：任务最后交付不对

1. 先看 Windows，确认最后一窗的 currentFocus 和 assistantTextSummary。
2. 如果最后一窗 focus 正确但输出不对，再看 Turns 是否出现 fallback 或 budget-check。
3. 如果轮次正常，再去 Artifacts 打开 response 和 compiled prompt 原文。

### 场景 B：任务中途开始偏航

1. 比较相邻两窗的 currentObjective、currentFocus、workTreeCurrentNodeId。
2. 检查 retrievalFingerprint 是否突然变化。
3. 如果 work tree 锚点漂移，再看 Source Signals 里的 takeover protocol 和 work-context-stack。

### 场景 C：工具调用很多但没有推进

1. 看 Turns 里 round 数是否异常多。
2. 看 Tools 里是不是重复同一工具、同一 sourceWorkTreeNodeId。
3. 回到 request/response 工件确认是不是重复 idempotent tool loop。

### 场景 D：想做评测对比

1. 对同一任务分别生成不同 provider / window profile 的分析结果。
2. 对比 summary、windows、tools 三层。
3. 不要只比较最终输出；要重点比较 focus 演进、工具序列和工件覆盖率。

---

## 6. CLI / API 入口

除了 Web，还可以直接走 CLI 和 API。

### CLI

```powershell
uv run yggdrasil-llm-work-analysis --task-id <TASK_ID>
uv run python scripts/analyze_llm_work_run.py --run-id <RUN_ID> --format md
```

常用参数：

- --task-id
- --run-id
- --invocation-id
- --granularity run,window,tool
- --format json 或 md
- --output <PATH>
- --no-persist

### API

```http
POST /runtime/analysis/runs
GET /runtime/analysis/runs/{analysisId}
GET /tasks/{taskId}/analysis/latest
```

最常用的是：

- 任务运行后用 GET /tasks/{taskId}/analysis/latest 直接取最新分析
- 想强制重算时用 POST /runtime/analysis/runs

---

## 7. 注意事项

- window-execution 当前更适合作为补充证据，不是唯一窗口历史来源。
- 如果运行时审计级别是 default 或 lean，工具细节可能只有 summary，没有完整 toolExecutions。
- 如果 request / response / prompt / metrics 缺失，分析页仍会展示结果，但结论应按“覆盖率不足”处理。

---

## 8. 你最常会用到的按钮

- 任务详情页：“LLM 工作分析” 进入完整分析页
- 任务详情页摘要卡：“刷新分析” 重新生成最新工件
- 完整分析页：“重新生成分析” 用于复跑后刷新结果
- 完整分析页：“返回任务详情” 回到控制面继续看 pause/resume、快照、route decision 和 mailbox
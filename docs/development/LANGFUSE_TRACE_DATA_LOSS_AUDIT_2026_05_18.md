# Langfuse Trace Data Loss Audit 2026-05-18

## 结论

当前一条完整 LLM 调用从本地 runtime 进入 Langfuse 后，会发生一次明显的降采样；再进入 Langfuse 五层分析程序后，会再发生一次以“可重建窗口证据”为中心的二次收缩。

对本次样本 `75c172aae4ff70de8ec320f08ff43fcb` 来说，Layer 4 和 Layer 5 之前看起来“不完整”，核心不是分析器凭空漏掉了现成数据，而是：

1. Langfuse observation 里本来就没有保存本地 request/response 工件的大部分审计细节。
2. 当前工作区里也没有这批 invocation 对应的本地 request/response JSON，可供分析器补回。
3. 中间窗口内容高度重复，确实是 runtime restart 合同被稳定回放的结果，不是报告误判。

## 一层：本地 runtime 原始持久化能保留什么

### request 工件

在 `packages/python-sdk/src/yggdrasil_sdk/llm_runtime_part_a.py` 中，request 工件会按 audit level 持久化：

- `strict`：完整 `messages`、`tools`、`initialMessages`、`conversation_messages`、`toolExecutions`、`rounds`
- `default`：`initialMessageDigests`、`finalMessageDigests`、`toolSpecs`、`toolExecutionSummaries`、`rounds`
- `minimal`：消息数、工具数、轮次数等计数

额外还会保留：

- `invocationId`
- `taskId`
- `agentRunId`
- `requestedModel`
- `requestedProvider`
- `temperature`
- `maxTokens`
- `thinking`
- `reasoningEffort`
- `promptCompileArtifactId`
- `promptMetadata`
- `auditLevel`

### response 工件

同样在 `packages/python-sdk/src/yggdrasil_sdk/llm_runtime_part_a.py` 中，response 工件至少会保留：

- `assistantText`
- `usage`
- `costUsed`
- `error`
- `mode`
- `provider`
- `model`
- `finishReason`
- `localRuntimeTimings`
- `contextLengthObservations`
- `runtimeMetrics`

若 `auditLevel == strict`，还会继续保留：

- `toolExecutions`
- `rounds`
- `rawResponse`

这意味着本地 runtime 才是“完整调用审计面”，Langfuse 不是。

## 二层：进入 Langfuse 之后保留了什么

### start 阶段写入

在 `packages/python-sdk/src/yggdrasil_sdk/llm_runtime_part_b.py` 中，`start_langfuse_generation()` 发送给 Langfuse 的 input payload 只有：

- `messages`
- `tools`
- `taskId`
- `agentRunId`
- `invocationId`

同时写入的 observation metadata 只有：

- `serviceName`
- `requestedProvider`
- `requestedModel`
- `taskType`
- `runType`
- `promptProfileId`
- `seedTemplateId`
- `promptScenario`

同时写入的 model parameters 只有：

- `temperature`
- `max_tokens`
- `thinking`
- `reasoning_effort`

### finish 阶段更新

在 `finish_langfuse_generation()` 中，写回 Langfuse 的内容只有：

- `output`: 最终输出文本 `outputText`
- `metadata`: `invocationId`、`status`、`provider`、`mode`、`toolExecutionCount`、`traceId`
- `usage_details`: prompt/completion/total tokens
- `cost_details`: total cost
- `model`
- `level`
- `status_message`

## 三层：从本地 runtime 到 Langfuse 的信息损耗

### request 侧丢失

进入 Langfuse 之后，以下内容不会保留在 observation input 中：

- `promptCompileArtifactId`
- `promptMetadata`
- `auditLevel`
- `initialMessageDigests` / `finalMessageDigests`
- `toolExecutionSummaries`
- `rounds`
- 本地 request 工件里按 audit level 保存的 conversation 审计结构

### response 侧丢失

进入 Langfuse 之后，以下内容不会保留在 observation output 中：

- `finishReason`
- `localRuntimeTimings`
- `contextLengthObservations`
- `runtimeMetrics`
- `toolExecutions` 明细
- `rounds` 明细
- `rawResponse`
- 严格审计下的推理原始响应体
- 工具执行结果内容；Langfuse 里只剩 `toolExecutionCount`

换句话说，Langfuse 里保住了“输入消息 + 可用工具 + 最终输出 + 少量调用元数据”，但丢掉了“本地审计面的大部分过程数据”。

## 四层：进入分析程序之后还能用什么

当前分析程序位于 `packages/python-sdk/src/yggdrasil_sdk/langfuse_trace_layered_analysis.py`。它现在会使用：

- observation `input.messages`
- observation `input.tools`
- observation `metadata`
- observation `modelParameters`
- observation `usageDetails`
- observation `output`
- runtime 用户消息中的窗口重启文本链

并据此重建：

- Layer 1：任务目标、任务结果、完成度、效果判断
- Layer 2：每窗口一句话摘要
- Layer 3：每窗口过程步骤
- Layer 4：按窗口分组的自言自语字段 / assistant 过程话语 / tool call 名称
- Layer 5：完整初始对话 + 重建窗口上下文 + 结构化窗口状态 + Langfuse metadata + 可用本地 invocation 工件

### 分析程序这一层仍然丢了什么

如果当前工作区里找不到对应 invocation 的本地 request/response JSON，分析程序仍然无法恢复：

- `conversationMessages`
- `toolExecutions`
- `rounds`
- `rawResponse`
- `reasoningContent` 原文
- `contextLengthObservations` / `runtimeMetrics` 的本地完整版

本次样本就是这种情况：分析器已经实现了本地工件回捞逻辑，但当前工作区中没有对应 invocation 文件，所以只能基于 Langfuse observation 做最完整的重建。

## 五层：为什么中间窗口真的一样

代码路径上，重复不是报告捏造，而是 runtime 真的在稳定回放同一组恢复态合同。

在 `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py` 中，`_build_restart_request_state()` 会把以下字段直接拷入下一轮 `requestState`：

- `responseRequirements`
- `restartMessage`
- `takeoverProtocol`
- `memoryRetrievalState`

在 `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop_transitions.py` 中，窗口重启会把当前 `request` 和 `effective_context` 打成 restart snapshot。

在 `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop_part_b.py` 中，resume 路径又会把 `pending_action.requestState` 里的字段填回 `request`，规则是“原请求没有值时直接继承快照值”。

因此，如果两轮之间没有注入新的合同差异、新的 retrieval state 差异或新的 conversation 进展，中间窗口就会自然长得几乎一样。当前样本正是这种情况。

## 这次修复后分析器的变化

本次修复已完成：

- 结构化分析调用采用按窗口数扩张的 token 预算，并对 JSON 截断做重试/回退，不再把“解析失败”误写成“LLM 不可用”
- Layer 4 改为按窗口输出，并显式标出“该窗口 Langfuse 本来就没记录到独立自言自语/工具调用”
- Layer 5 增加结构化窗口状态、Langfuse metadata/model parameters/usage，以及本地 invocation 工件补位入口
- 若当前工作区存在对应 invocation request/response 文件，分析器会自动补回更多本地审计信息

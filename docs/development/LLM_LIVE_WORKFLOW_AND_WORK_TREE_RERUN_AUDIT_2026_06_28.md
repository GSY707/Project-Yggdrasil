# LLM Live Workflow And Work-Tree Rerun Audit - 2026-06-28

## 范围

本轮按 `evalsuite_g4_real_task_web_research_default` 重跑储能路线选择 live 任务，目标是复核运行中 LLM 是否按新工作树口径工作，以及能否从工件中看见真实资料检索过程。

运行命令：

```powershell
$env:YGGDRASIL_EVAL_PRESERVE_SANDBOX='1'
$env:YGGDRASIL_RUNTIME_AUDIT_LEVEL='strict'
uv run python -m yggdrasil_sdk.evaluation_cli run --suite evalsuite_g4_real_task_web_research_default
```

本轮主工件：

- wrapper 日志：`tmp/live-rerun-20260628-214050/evaluation.log`
- 工作分析报告：`tmp/live-rerun-20260628-214050/llm-work-analysis.md`
- sandbox：`.yggdrasil/state/evaluation-sandboxes/evalsandbox_9faf11ab84e148c092e8/`
- invocation：`llm_4464cae44d3e488c9cb3`
- task：`task_25a9fa48e96841079b72`
- run：`run_080b3b166e784a9c8cfa`

## 结果摘要

- live 任务通过，`exit_code=0`，task/run/model invocation 均为 `completed`。
- provider/model 为 `longcat / LongCat-2.0-Preview`，没有 fallback。
- LLM 共 5 个 round：4 轮工具调用，1 轮最终交付。
- behavior record 落盘成功：`.yggdrasil/state/evaluation-sandboxes/evalsandbox_9faf11ab84e148c092e8/.yggdrasil/state/llm/behavior-records/llm_4464cae44d3e488c9cb3.json`
- 编译 prompt 确认包含新工作树案例和 root/leaf 分工提示。
- LLM 没有主动发出 `<work-node-create>` 或 `<work-node-enter>`，工作树节点切换数为 0。

## Prompt 是否进新口径

本轮 request 的 system/user prompt 中已经包含：

- `工作树使用案例 1/2/3`
- `根节点和非叶子节点主要负责工作流程控制、任务理解、方向重估和信息合并`
- `叶子节点负责具体查资料、改文件、跑命令和局部试错`
- `执行会产生搜索记录、编辑过程、命令输出、失败尝试、重复项或候选路线时，依据 currentNodeId、Working_Node 和 WorkContextStack 创建/进入合适工作节点`
- `每轮重要证据、工具批次或准备交付前，重新审视任务目标、当前工作树位置、未闭合问题和是否需要新增/进入/回收子节点`

因此这轮不是 prompt 未注入导致的失败。

## LLM 实际工作流程

本轮 LLM 的实际流程是：

1. 先确认交付四类储能技术比较报告，然后直接并行发起 4 次 `mcp.web.search_web`。
2. 4 次 search 都返回 `count=0`，工具本身 wrapper 成功，但搜索结果为空。
3. LLM 转向直接抓取权威来源：IEA、IRENA、BNEF。
4. IEA/IRENA 返回 403；BNEF 返回 JS 渲染页面壳。
5. LLM 转向 Wikipedia 四个条目，并追加 DOE/NREL 氢储能页面。
6. DOE 返回页面壳/脚本内容，NREL SSL 失败。
7. LLM 最终主要基于 Wikipedia 可抽取内容生成报告，并在报告里承认来源单一、IEA/IRENA/NREL 等权威来源访问失败。

工具执行明细：

- `mcp.web.search_web`: 4 次
- `mcp.web.fetch_webpage`: 9 次
- behavior record 记录的实际工具调用数：13
- MCP wrapper 视角 `success=True`：13 次
- 具体工具 payload 视角存在失败或弱结果：
  - search 4 次均 `count=0`
  - IEA/IRENA 403
  - NREL SSL EOF
  - BNEF/DOE 返回 JS/页面壳

这解释了“只有报告让人不信”的问题：模型确实调用了工具，但可用资料质量弱，最终报告的证据强度不足。

## 工作树使用判断

本轮工作树使用不符合目标。

证据：

- `assistantBehavior.workTreeDirectives=[]`
- `integrity.roundCount=5`
- `integrity.toolExecutionCount=13`
- `work-context-stack` 工件不存在
- LLM 工作分析报告显示：
  - 窗口数：1
  - 节点切换数：0
  - 工作树时间线只有 `work-tree-node_1c9d9947730f284f5bc1 -> completed`
- takeover protocol 虽然预生成 root 下 6 个 plan child，但 LLM 实际一直停在第一个 child：`探索验证面（实验优先）`
- 其他 child 仍为 pending：`固定研究问题`、`抽取约束`、`收集与归纳`、`校验证据`、`交付结论`

结论：runtime 有任务工作树壳和当前节点标记，但 LLM 没有主动把 search/fetch、来源失败、候选路线或综合判断拆到 leaf。模型仍倾向在当前节点内完成“搜索 -> 失败切换 -> 报告”全流程。

## 缓存命中异常

本轮落盘 metrics 显示：

- `cacheHitInputTokens=0`
- `cacheWriteInputTokens=0`
- `nonCacheInputTokens=105501`

但最终 raw provider usage 含有：

```json
{
  "effectiveCachedTokens": 34560,
  "prompt_tokens": 40782,
  "prompt_tokens_details": {
    "cached_tokens": 34560
  },
  "cache_read_tokens": 0,
  "cached_tokens": 0
}
```

根因是 provider gateway 的 usage 归一化会在顶层 `cached_tokens=0` 处提前返回，遮蔽嵌套的 `prompt_tokens_details.cached_tokens=34560`。

本轮已修复：

- `adapters/model-providers/src/yggdrasil_model_providers/gateway.py`
- `tests/test_deepseek_gateway.py`

修复后用本轮 raw usage 重新归一化得到：

- `cacheHitInputTokens=34560`
- `nonCacheInputTokens=6222`

注意：本轮已落盘的 live metrics 是修复前生成的证据，不应回改。下一次 live 才会在正式 metrics 中显示修复后的 cache hit。

## 后续判断

1. Prompt 新口径已经进入运行中 LLM。
2. 行为记录器能稳定记录 round、tool、prompt signal 和 work-tree directive；这次清楚证明了“有工具调用，但没有主动工作树指令”。
3. 当前工作树使用问题更像执行习惯和 runtime 编排问题，不是 prompt 完全缺失。
4. 下一步应把“执行噪声进入 child/leaf”从自然语言提示进一步接到 runtime 行为，例如在 search/fetch 批次、工具失败批次或证据综合前由 runtime 施加更强的当前节点建议或自动进入执行 leaf。

## 2026-06-28 追加实验：追问、反思、批评继续

本节补跑 3 个单独 live 实验。所有实验都围绕同一个储能路线选择任务，但实验变量分开：完成后追问、步骤反思提示、批评后 revision 继续。

### 实验 1：完成后 user 追问

- suite：`evalsuite_g4_real_task_work_tree_post_question_live`
- run dir：`tmp/live-work-tree-experiments-20260628-221648/01-post-question-final`
- sandbox：`.yggdrasil/state/evaluation-sandboxes/evalsandbox_59f8a45102f6467788a2`
- 主 invocation：`llm_df8f1c4f1ed74520af5c`
- post action artifact：`.yggdrasil/state/evaluation-sandboxes/evalsandbox_59f8a45102f6467788a2/.yggdrasil/state/evaluations/g4-post-completion-actions/20260628-153327_g4-work-tree-post-question-grid-storage_ask-why-no-work-tree.json`

结果：

- 主任务完成，7 个 round，24 次工具执行，`workTreeDirectiveCount=0`。
- post action 以 `user` 角色追加问题：“为什么你刚才没有明显使用工作树？为什么主要在根节点完成？如果报告里写了下一步应该做什么，为什么没有继续做下一步？”
- LLM 追问回答承认：它把 8 个并行论文/网络检索和报告综合都放在 root，未创建/进入工作节点；它把“交付报告”误当作任务终点，所以列出缺口后没有继续执行。
- harness 修复：diagnostic follow-up action 现在会把 provider 返回的 `outputText` 同步保存到 artifact 顶层 `assistantText/outputText`，避免后续看 artifact 时误判为空回答。

判断：追问能得到有效自我归因，说明模型知道自己偏离了工作树口径；但这是事后解释，不会自动改正本轮执行。

### 实验 2：每步反思提示

- suite：`evalsuite_g4_real_task_work_tree_step_reflection_live`
- run dir：`tmp/live-work-tree-experiments-20260628-221648/02-step-reflection`
- sandbox：`.yggdrasil/state/evaluation-sandboxes/evalsandbox_bc100ce1067545b7a854`
- invocation：`llm_0b5df8a4d78e4a389374`

结果：

- 主任务完成，14 个 round，22 次工具执行，`workTreeDirectiveCount=0`。
- prompt 要求每轮重要证据/工具批次后重新审视目标、当前工作树位置、是否需要新增/进入工作节点、证据缺口和下一步。
- LLM 仍直接写出 `energy_storage_comparison_report.md`，没有主动发出 `<work-node-create>` 或 `<work-node-enter>`。

判断：自然语言“每步反思”不足以打断单节点工作惯性。它能改善叙述，但不能保证模型把执行噪声放进 child/leaf。

### 实验 3：批评后继续

第一次 `critique-continue` 设计让真实任务自然跑到 approval 再 revision，实际失败点是 harness 设计而不是批评消息：任务最终进入 `completed`，而 `/request-revision` 只接受 `awaiting-approval`。该轮产生过一个有用信号：显式 seeded work tree 能让 LLM 至少发出一次 `<work-node-enter nodeId="route-comparison">`，但后续窗口仍出现工具循环惯性。

第二次改为窄实验：先种一个 `awaiting-approval` 的半成品工作树，再发批评式 revision 消息。

- suite：`evalsuite_g4_real_task_work_tree_critique_continue_live`
- run dir：`tmp/live-work-tree-experiments-20260628-221648/03c-critique-continue-seeded-revision-preserved`
- evalrun：`evalrun_b75551675fa7455d8d04`
- sandbox：`.yggdrasil/state/evaluation-sandboxes/evalsandbox_a6e11f83e66947bf9e02`
- invocation：`llm_2084c77161a64480b485`
- task：`task_18cf5ea612514ffdad41`
- post action artifact：`.yggdrasil/state/evaluation-sandboxes/evalsandbox_a6e11f83e66947bf9e02/.yggdrasil/state/evaluations/g4-post-completion-actions/20260628-155225_g4-work-tree-critique-continue-grid-storage_critique-continue-root.json`
- behavior record：`.yggdrasil/state/evaluation-sandboxes/evalsandbox_a6e11f83e66947bf9e02/.yggdrasil/state/llm/behavior-records/llm_2084c77161a64480b485.json`

结果：

- revision API 成功返回 202，post action 状态 `completed`，worker result 回到 `awaiting-approval`。
- LLM 确实继续干活：raw response 有 5 个 round，`observedToolCallCount=19`，其中 `text_memory.read_index=1`、`mcp.web.search_web=6`、`mcp.web.fetch_webpage=12`。
- 但 LLM 仍停留在 root：`currentNodeId=root`、`workingNodeAnnotation=<Working_Node: root>`、`workTreeDirectives=[]`。
- 最终不是高质量完成，而是 `finishReason=tool-round-limit-short-circuit`，assistant 文本为“已达到配置的工具轮次上限，本窗口停止继续调用工具...后续应按当前任务目标继续综合...”
- suite 外层状态为 passed，是因为 case 执行没有异常；provider matrix 内部 `pass=false`、`officialAcceptancePassed0_1=0`，原因是工具证据和工作树连续性验收没有达标。

判断：批评式 revision 能把 LLM 从 approval 拉回继续执行，但不能解决 root-only/单节点惯性；如果要让它进入未完成节点，revision target 不能只写 `nodeId=root`，需要 runtime 按缺口直接 reopen child/leaf，或在工具批次后由 runtime 注入更强的当前节点建议。工具末尾提醒“反思工作流程控制”只能作为保底方案，不应作为首选修复。

### 行为记录器修复

第三组保留 sandbox 暴露出一个记录口径问题：LongCat response 有 `rounds[*].toolCalls`，但没有详细 `toolExecutions` 列表，旧行为记录器和 provider matrix 因此把工具数记成 0。

本轮已修复：

- `packages/python-sdk/src/yggdrasil_sdk/llm_runtime/behavior_recorder.py`
  - 保留 `toolExecutionCount` 表示详细 execution 记录数。
  - 新增 `observedToolCallCount`、`roundToolCounts`、`toolEvidenceSource`。
  - 当 `toolExecutions` 缺失时，`actualToolCounts` 回退到 `rounds.toolCalls`。
  - digest-only compiled prompt 不再误记为 `messageCount=0`，会写 `messageCount/messageDigestCount/textAvailable`。
- `packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_g4.py`
  - provider matrix 的工具统计和工具名列表同样回退到 `rounds.toolCalls`。
- `tests/test_llm_behavior_recorder.py`、`tests/test_g4_multiscene.py`
  - 补齐 round-derived tool call 与 seeded revision harness 回归。

保留 sandbox 要求：后续 live 行为实验必须设置 `YGGDRASIL_EVAL_PRESERVE_SANDBOX=1`。否则 raw request/response、window execution、post action artifact 会随临时目录清理，只剩汇总 JSON，不足以判断模型是否真的查资料。

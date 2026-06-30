# LLM 工作树硬提示实验记录（2026-06-29）

## 目的

本轮只验证运行中 LLM 是否更愿意把具体工具工作放入 child/leaf，并用真实储能比较任务观察 prompt、工具调用、工作树和最终交付。格式美化不是目标；重点是工作树是否真的可用、行为记录是否可信。

## 本轮代码变更

1. `packages/python-sdk/src/yggdrasil_sdk/llm_runtime/invoke.py` 新增 `toolResultReflectionReminder` 请求字段。
   - 为 `true` 时，每个工具批次结束后追加一条 `role=user` 的 `[tool-batch-ended]` 提醒。
   - 提醒要求模型重新审视目标、当前工作节点、是否需要进入 leaf/回父节点/收束交付。
   - 该能力是显式开关，不作为所有任务默认行为。
2. `packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_g4.py` 透传 `toolResultReflectionReminder`，使 G4 live suite 能直接实验该字段。
3. 新增四个单 case live suite 和四个 `package.json` 命令：
   - `eval:g4:work-tree:tool-end-reminder`
   - `eval:g4:work-tree:tool-call-leaf-example`
   - `eval:g4:work-tree:leaf-self-talk`
   - `eval:g4:work-tree:deepseek-v4-pro`
4. 追加 `eval:g4:work-tree:deepseek-v4-pro-critique-continue`，把“批评后继续”叠加到 DeepSeek 父/leaf 口径上：
   - `runtime_kernel/execution_control.py` 允许 `completed` 任务在最新 work tree 仍有 `pending/in-progress/summarizing/blocked/failed` 节点时通过 `/request-revision` 重开。
   - `runtime_kernel/takeover.py` 让 revision 的 `nodeId=root` 映射到动态 root node id，避免 live 任务 root id 不是字面 `root` 时无法定位。
   - `evaluation_runtime/suite_cases_g4.py` 在 post-completion revision 中继续透传 `candidateModels`、模型参数、上下文窗口参数和 `toolResultReflectionReminder`，避免 revision 阶段掉回其它模型。
5. 追加 `eval:g4:work-tree:deepseek-v4-pro-node-tool-budget`，验证“每节点 5 次 toolcall 机会 + 第 6 次工具末尾警告 + auto-unfinished 继续位置”：
   - `runtime_kernel/takeover.py` 新增 `nodeId=auto-unfinished` 解析：当前节点有未完成子节点时在当前节点继续；当前节点完成但 sibling 未完成时回父节点继续；否则回到第一个未完成节点的父节点。
   - `llm_runtime/invoke.py` 新增 `workTreeNodeToolCallSoftLimit` 请求字段。字段只在工具批次后注入警告，不实际拒绝第 7 次工具调用。
   - `evaluation_runtime/suite_cases_g4.py` 透传 `workTreeNodeToolCallSoftLimit` 到 start payload 和 post-completion revision payload。
   - `evaluation_cli.py` 固定 stdout 为 UTF-8/replacement，避免 Windows GBK 控制台在 live 结果含 emoji 时打印崩溃。
6. 追加 `eval:g4:work-tree:deepseek-v4-pro-directive-required`，验证“自然语言换节点无效 + runtime 可验证 directive + 子节点范围确认 + 快照侧信道诊断”：
   - `runtime_kernel/execution_loop/state_memory.py` 新增自然语言工作树声明检测：模型声称创建/进入/切换 leaf、leaf handoff 或返回父节点，但没有可应用 directive 时，生成 `work-tree-directive-required` transition；不从自然语言直接推断并修改工作树。
   - 本轮补齐 child/leaf 有效交付路径：`<work-node-complete status="completed">...</work-node-complete>` 会调用 `complete_current_work_node()`，把当前 child/leaf 标为 completed，把摘要写入父 frame 的 `childCompletionSummaries`，并把 currentNodeId 冒泡回父节点继续评估；`work-node-handoff` 作为同义标签被解析为 complete。
   - `runtime_kernel/execution_loop/worker.py` 会把 `directiveRequired` transition 传给 `transitions.py`，避免 reducer 已发现漂移但 transition 阶段丢弃。
   - `runtime_kernel/execution_loop/transitions.py` 让 `work-tree-directive-required` 优先于 awaiting-approval/completed，并在 continuation 中追加纠偏指令；进入 child/leaf 后追加“范围、停止点、返回方式、用 `work-node-complete` 交付回父节点”确认提示；continuation 追加器已对相同提示去重，避免 repeated child checkpoint / delivery retry 文案在长链续跑中膨胀。
   - `prompting.py` 明确“换工作节点和结束 child/leaf 都必须操作工作树，自然语言说换节点或 Leaf Handoff 无效”，并要求子节点开始工具工作前先确认范围、停止点和返回方式。
   - `llm_runtime/behavior_recorder.py` 新增 `workTreeNaturalLanguageClaims` 与 `workTreeClaimWithoutDirective`，并把 `work-node-complete` / `work-node-handoff` 计为有效 directive，用于审计模型是否只是文本声称换节点。
   - `evaluation_runtime/suite_cases_g4.py` 的 diagnostic follow-up 可带 `runtime/work-tree snapshot`，侧信道直接询问模型当前工作状态、回滚位置和漂移原因。

## 实验结论

| 实验 | 运行证据 | 工作树行为 | 任务/交付 | 结论 |
|------|----------|------------|-----------|------|
| 1. 工具末尾强提醒 | `tmp/live-work-tree-hard-fix-20260629/01-tool-end-reminder/stdout.json`；沙盒 `evalsandbox_a2d264bfdd04432bb2ae`；invocation `llm_b017600ec4f14988a6a7` | 12 次工具批次后都注入提醒，但 assistant 没有发出 `work-node-create/enter` | `taskStatusAtExit=completed`，22 次工具，21 成功，LongCat 写出报告 | 硬提醒能进入上下文，但不足以打断 LongCat 的 root/当前节点惯性。 |
| 2. 工具调用即 leaf 示例 | `tmp/live-work-tree-hard-fix-20260629/02-tool-call-leaf-example/stdout.json`；沙盒 `evalsandbox_ded74ba4b7164a9a962d`；invocations `llm_4555347ae5d34118948d`、`llm_2cc0f2f3f5944ffb8148`、`llm_391b140863dd4dba81af` | 首窗口只创建 child 并停止；后两窗口合计执行 71 次工具；第三窗口已经回到父/高层节点继续改报告，但未显式评估/关闭工作树 | `task/result/latestRun=completed`，`goalCompletion=1`，但 `deliveryCompletion=0`、官方验收 0 | 强示例最能促成 leaf 执行，但仅靠“工具进 leaf”不够；还必须把“父节点评估子节点、宣告完成，子节点不能做这些事”写成硬案例。 |
| 3. 更明确执行示例 + 自言自语 | 正式重跑：`tmp/live-work-tree-hard-fix-20260629/03b-leaf-self-talk-encoded/stdout.json`；沙盒 `evalsandbox_b518cf68976f4a7fbafd`；invocation `llm_6722c8df8d074734a7b3` | 正式重跑没有新建 leaf，单窗口在当前工作节点完成工具；补充失败运行 `evalsandbox_ff7fdac30c9b45a5800f` 曾先建 leaf，但未写文件且节点未收束 | 正式重跑 `task/result/latestRun=completed`，19 次工具 0 失败，写出 `workspace/storage_comparison_report.md`；官方验收 0 | 自言自语/执行后判断提示不稳定，可能提升交付动作，但不能稳定约束进入 leaf。 |
| 4. DeepSeek V4 Pro | `tmp/live-work-tree-hard-fix-20260629/04-deepseek-v4-pro/stdout.json`；沙盒 `evalsandbox_cd50a79907cc4831855b`；invocation `llm_114cceb59364425594d3` | 没有发出工作树 directive，单窗口在当前工作节点完成任务 | `pass=true`、官方验收 1、`deliveryCompletion=1`，27 次工具 0 失败，DeepSeek `deepseek_direct/deepseek-v4-pro` | 模型质量显著提升，能完成严格交付；但换模型本身不等于会用 leaf。 |

## 补充重跑：leaf 执行，父节点评估

按用户新思路调整实验 2 与 DeepSeek suite：案例改成“父/编排节点只创建证据 leaf 并停止；leaf 只执行工具并回传发现、证据引用、废弃路线、缺口与风险；父/编排节点评估子节点交接，决定下一个 leaf 或最终交付；leaf 不能宣告整体任务完成，不能写最终报告”。DeepSeek 重跑使用的就是这套实验 2 方法，不是旧实验 4 的无 leaf 示例口径。

| 重跑 | 运行证据 | 行为记录 | 结论 |
|------|----------|----------|------|
| 2b. LongCat + 父评估案例 | `tmp/live-work-tree-hard-fix-20260629/05-tool-call-leaf-parent-eval/stdout.json`；沙盒 `evalsandbox_926c66d1376043899fc2`；invocations `llm_ccfd95cce6ba4f938112`、`llm_d7c2585d133f42a99d57`、`llm_2397c9dd53fc477e8c2c` | 首窗口没有先建 leaf，而是在 root/seeded 高层节点直接执行 37 次工具并写出 `energy_storage_comparison_report.md`；第二窗口作为父节点读取报告、做了子节点交付评价，并创建 `补充来源与修订报告` child；第三窗口在该 child 内执行 30 次工具并写出 `energy_storage_comparison_report_v2.md`，但在 child 内自称“父节点评估”并让任务 completed。最终 root 仍 `in-progress`，模板兄弟节点仍 `pending`，新 child 仍 `in-progress`。 | 新案例能诱发一次父节点评估和追加 child，但不能稳定阻止 LongCat 在首窗口直接完成报告，也不能保证 child 完成后回父节点收束。suite pass、68 次工具、67 次成功，只能证明真实工具执行，不证明工作树行为合格。 |
| 4b. DeepSeek V4 Pro + 父评估案例 | `tmp/live-work-tree-hard-fix-20260629/06-deepseek-leaf-parent-eval/stdout.json`；沙盒 `evalsandbox_a99e8a59bbfe4b28a918`；invocations `llm_43c42d72c6d7434fb596`、`llm_d319f1561a5a475eadaf` | 首窗口在 root/orchestrator 只做 `text_memory.retrieve/read_node`，声明 root 不执行具体工具，并创建 `锂离子电池储能网络调研` leaf；第二窗口在 leaf 内执行 28 次真实检索/抓取/论文检索工具并输出 Leaf A 回传。之后任务直接 completed，没有回到父节点评估 Leaf A，也没有继续创建钠离子、液流电池、绿氢 leaf。最终 root 和 seeded 高层节点仍 `in-progress`，其它模板节点 `pending`，Leaf A 仍 `in-progress`。 | DeepSeek 更服从“先开 leaf，再在 leaf 做工具”的入口规则，但 leaf 完成后没有自动回父节点继续调度。suite pass、32 次工具、28 次成功，只说明它产出了可保存的 leaf 交接，不说明完整任务已按工作树完成。 |

## 追加实验：批评后继续 + 先做任务控制分析

实验目的：验证“如果有任务/工作节点未完成，发送一句类似批评的消息，并要求 LLM 继续”是否能修补 DeepSeek 在 Leaf A handoff 后没有回父节点继续调度的问题。消息不只批评，而是要求先做任务控制分析，再继续执行：说明当前节点、未完成节点、父/leaf 职责、缺失路线/证据/矛盾处理，并选择下一步 leaf 或父节点动作。

| 运行 | 证据 | 行为记录 | 结论 |
|------|------|----------|------|
| 7. 首次 DeepSeek 批评继续 | `tmp/live-work-tree-hard-fix-20260629/07-deepseek-critique-continue-control-analysis/stdout.json`；沙盒 `evalsandbox_c2ceb2124b714a5e885e` | 初始阶段比旧 DeepSeek 基线更接近预期：先建编排节点、Li-ion leaf，再进入 Na-ion、Flow Battery 等节点；但 revision 阶段没有保留 DeepSeek candidate，最终因 `g4 provider matrix provider mismatch: expected deepseek_direct, got longcat` 失败。 | 该轮不能作为 DeepSeek 行为结论，只证明 `completed` + 未完成 work tree 的 revision 重开链路有必要，同时暴露了 post-completion revision 丢失 `candidateModels` 的 harness bug。 |
| 8. 修复模型路由后重跑 | `tmp/live-work-tree-hard-fix-20260629/08-deepseek-critique-continue-fixed-route/stdout.json`；沙盒 `evalsandbox_0340f3943ac042688d96`；post action `20260629-063241_g4-work-tree-deepseek-v4-pro-critique-continue-grid-storage_task-control-critique-continue.json`；invocations `llm_f9a58dff148d49c39dbd`、`llm_84d5ce6d75814e38a328`、`llm_2c364590508949bf8318` | 三个 invocation 都保持 `deepseek_direct/deepseek-v4-pro`。suite 层面 `passedCount=1`，post action `completed`，总工具 45 次且 0 失败，cache hit input tokens 188416、non-cache input tokens 63984。行为上，revision 阶段 `llm_2c364590508949bf8318` 没有执行新工具、没有发工作树 directive，输出预览直接从“数据采集完成...现在进入父节点信息合并阶段”开始生成完整报告；最终 work tree 仍有 root/seeded 高层/编排节点 `in-progress` 和多个模板节点 `pending`。 | 技术链路已修通：批评消息能让 completed+unfinished 任务继续，且 revision 能保持 DeepSeek。行为结论仍不合格：它让 LLM 继续产出报告，但没有稳定落实“先任务控制分析 -> 进入缺失 leaf -> 父节点评估 -> 再交付”。 |

## 追加实验：auto-unfinished 继续位置 + 每节点 5 次 toolcall 软预算

本轮按新判断实现 harness 自动继续位置：如果某节点声明完成但还有未完成子节点，就在该节点继续；如果 sibling 未完成，就回父节点继续调度。实验同时加入一条强 prompt：每个工作节点只有 5 次 toolcall 机会；要做更多事应进入子节点，或回父节点；每次进入新节点刷新机会；第 6 次工具调用后，在工具末尾警告“你应该进行工作流程上的安排，下次 toolcall 将被拒绝”。代码不做实际拒绝。

| 运行 | 证据 | 行为记录 | 结论 |
|------|------|----------|------|
| 9. DeepSeek + auto-unfinished + 节点工具预算 | metrics：`.yggdrasil/state/evaluations/evalrun_fdee593d0136443caa27.json`；run dir：`tmp/live-work-tree-hard-fix-20260629/09-deepseek-node-tool-budget-auto-unfinished/`；suite `evalsuite_g4_real_task_work_tree_deepseek_v4_pro_node_tool_budget_live` | 外层 `status=completed`、`passedCount=1`，但 detail 仍是 `pass=false`、`officialAcceptancePassed0_1=0`、`deliveryCompletion0_1=0`、`workTreeContinuity0_1=0`。5 个窗口，19 次工具执行（17 成功、2 失败），post action `auto-unfinished-critique-continue` completed，tokens：input 57161、output 3505、cache hit 44160、non-cache 13001。窗口行为：先进入父/编排节点，再进入 Li-ion leaf；Li-ion leaf 用满 5 次工具后主动输出 leaf handoff；revision 后 auto-unfinished 把 continuation 放回父/编排节点，transition 为 `parent-orchestration-required`；随后模型声称创建/进入 Leaf 2，但没有真实工作树 directive，最终仍在父/编排节点执行 6 次工具并输出 Na-ion handoff。最终 work tree 中 root、seeded 高层、编排节点、Li-ion leaf 仍 `in-progress`，多个模板节点仍 `pending`。 | `auto-unfinished` 明显比 `nodeId=root` 好：revision 不再直接在 root 写报告，而是回到父/编排层。5 次工具预算也有效影响行为：Li-ion leaf 在 5 次后停手交接，第 6 次警告被模型显式感知。但仍不够：模型可在父节点伪造“Leaf 2 handoff”，没有真实创建/进入 Na-ion leaf，也没有完成父节点最终收束。 |

## 追加实验：runtime directive-required + 范围强化 + 快照侧信道

实验目的：把“我创建/进入 leaf/返回父节点”从自然语言升级为 runtime 可验证 directive。原则是不让自然语言直接创建、切换或完成节点，避免污染工作树；如果模型声称换节点、leaf handoff 或返回父节点但没有可应用 directive，runtime 触发 `work-tree-directive-required`，续跑时要求先补 `<work-node-create>`、`<work-node-enter>` 或 `<work-node-complete>`。同时，进入 child/leaf 后提示先确认范围、停止点和返回父节点方式；post-completion 侧信道把 runtime/work-tree snapshot 作为 user 消息问模型，让模型自己定位漂移原因。

| 运行 | 证据 | 行为记录 | 结论 |
|------|------|----------|------|
| 10. DeepSeek + directive-required 首次完整 run | metrics：`.yggdrasil/state/evaluations/evalrun_356801f206254ab7a50c.json`；sandbox：`.yggdrasil/state/evaluation-sandboxes/evalsandbox_f038f39ec7ee4054a4b0/`；suite `evalsuite_g4_real_task_work_tree_deepseek_v4_pro_directive_required_live` | 外层 `status=completed`、`passedCount=1`，但 detail 仍是 `pass=false`、`officialAcceptancePassed0_1=0`、`deliveryCompletion0_1=0`、`workTreeContinuity0_1=0`。5 个窗口，15 次工具执行（14 成功、1 失败），post action `runtime-revision` 与 `diagnostic-followup` 均 completed；tokens：input 48394、output 4557、cache hit 31232、non-cache 17162、reasoning 1692。窗口链：root bubble -> 创建 Li-ion/Na-ion leaf -> leaf 交接后 completed -> auto-unfinished revision 回 root 并创建 Flow Battery leaf -> Flow leaf 交接后 completed。behavior record 显示两次 leaf handoff 是 `workTreeClaimWithoutDirective=true`；侧信道诊断明确指出 runtime 仍认为当前节点是 leaf，模型自述返回父节点与 runtime 状态不一致，原因是没有节点完成/移交结构化指令。 | 首次完整 run 证明新 recorder 和 snapshot 侧信道有效，也证明 directive-required 对“创建 child”有效：revision 阶段没有再伪造 Leaf 2，而是发了真实 create directive。缺口也更清楚：leaf handoff/返回父节点没有被首版 detector 拦住，因为当时只在父/控制节点检测自然语言漂移。 |
| 11. 修复 leaf handoff 检测后重跑（超时中止） | sandbox：`.yggdrasil/state/evaluation-sandboxes/evalsandbox_34516ca2a53b440d8d9e/`；无完整 evalrun，npm/uv/python 后台进程已确认并终止 | behavior index 记录 15 个 invocation，窗口记录 30 份（task + llm artifact 成对）。`work-tree-directive-required` 多次触发：例如 leaf `work-tree-node_cc96d582a2c540f5a63c` 试图“返回父节点”时被拦截，随后模型用 `work-node-enter` 回到父节点；Na-ion leaf 的 `leaf handoff` 也被拦截；父节点/leaf 之间的切换变成 runtime 可见的 `enter-existing-child`、`parent-orchestration-required`、`enter-child` 链。 | 修复有效：自然语言 leaf handoff 不再静默 completed，而是被 runtime 打断并要求补 directive。但当时的新问题暴露得更强：系统还没有 `work-node-complete` / `work-node-handoff` / `return-parent-with-summary` 这种“关闭当前节点并带摘要回父节点”的可验证动作，模型只能用 create/enter 反复补洞，容易进入长循环。该 run 因 30 分钟超时被人工终止，不能作为完成态验收，只作为流程控制证据。 |

## 本轮修复：child 有效交付路径

这轮按“不是模型弱，而是代码没有给有效路径和正确案例”的判断修 runtime：`work-node-complete` / `work-node-handoff` 成为可解析 directive。模型在 child/leaf 达到停止点时，不再只能写自然语言 `Leaf Handoff` 或 `返回父节点`，而是可以输出：

```xml
<work-node-complete status="completed">
Result: 本节点完成的具体结果。
Evidence: 本节点实际使用的工具结果、文件、链接、测试或记忆引用。
Gaps/Risks: 仍不确定项、失败尝试、已废弃路线和风险。
Parent next: 请父节点评估后决定继续开 leaf、补证据或收束最终交付。
</work-node-complete>
```

运行时效果：当前 child/leaf 被标为 `completed`，`executionSummary` 保存交付摘要，父 frame 的 `childCompletionSummaries` 收到该摘要，`currentNodeId` 自动回到父节点并排 continuation。`work-tree-directive-required` 纠偏消息在检测到自然语言 handoff/返回父节点时，也会直接给出上面的正确交付案例，而不是只要求 create/enter。聚焦验证已通过：`test_work_node_complete_directive_bubbles_leaf_to_parent_with_summary` 证明 complete directive 能真实回父节点，recorder 和 prompt 测试也已同步。

重跑 live 时又暴露出一个代码侧缺口：模型可能在同一个 LLM window 里同时输出 `work-node-enter` 和 `work-node-complete`，并在这同一窗口里调用工具。因为 runtime 是 window 结束后才应用 directive，如果允许同窗 enter+complete，就会把旧节点窗口里的工具工作误标成新 leaf 已完成。本轮已收窄 reducer：当同一窗口出现多个会改变当前节点的 directive 时，只应用第一条，后续 directive 记录为 `multiple-work-tree-state-directives-in-one-window` blocked，并通过第一条 transition 续跑；prompt 和 live suite 也写明“每个 LLM window 最多一个 current-node-changing directive，输出后停止”。

同一轮 live 还暴露出第二个代码侧缺口：`Child/leaf start checkpoint` 和 delivery retry tail 会随着 continuation 反复拼接到 `responseRequirements`，导致 prompt 噪声越来越大，模型后段更容易过度开 leaf、反复补证据而不收束。已修复为相同 continuation instruction 只保留一份；`resumeMessage` 仍设置为本轮纠偏内容，便于下一窗口聚焦。

| 运行 | 证据 | 行为记录 | 结论 |
|------|------|----------|------|
| 12. DeepSeek + `work-node-complete` + continuation 去重 | metrics：`.yggdrasil/state/evaluations/evalrun_90e62958ee694652a9f5.json`；sandbox：`.yggdrasil/state/evaluation-sandboxes/evalsandbox_960ab8a01c3948b4878b/`；run dir：`tmp/live-work-tree-complete-20260629/05-deepseek-directive-complete-dedupe/` | 结果 `failed`，原因是 `maxWindowCycles=24`；24 个 response window，46 次工具，14 个 `work-node-create`、8 个 `work-node-complete`、2 个 `work-node-enter`、0 个多 state-directive window。最终 work tree 16 节点：8 completed、5 pending、3 in-progress，currentNodeId 落在 `最终合成：构建对比矩阵并撰写推荐报告`。 | 有效交付路径已被真实 LLM 采用：多个 leaf 在工具执行后用 `work-node-complete` 回父节点，父节点能读取 child summaries 并继续调度；同窗 enter+complete 未复发。`最终合成/撰写报告` 开成 child 是合理路径，只要 child 做完后用 `work-node-complete` 交回父节点并由父节点认可即可；本轮不能据此判定停止条件有问题，更直接的问题是 24 轮窗口不够。 |
| 13. 轮次与手动继续修正（代码/配置） | suite 配置已把 directive-required live 主 run 与 revision action 的 `maxWindowCycles` 从 24 提升到 64，并启用 `allowManualContinueOnMaxWindowCycles=true`；harness 满轮后不再抛 RuntimeError，而是返回 `status=blocked` / `manual-continue-required`，携带最后 queued work item、taskId、processedRunCount 和 sandbox/state 信息。 | prompt 口径同步修正：最终合成/撰写报告可以作为 child 执行并产出完整报告草稿，但必须通过 `work-node-complete` 交回父节点，由父节点认可并宣告整体完成。 | 下一轮 live 应先验证 64 轮是否足够跑完“最终合成 child -> 父节点认可”链路；若仍满轮，则保留现场手动继续，而不是把它记录成模型/协议失败。 |
| 14. 64 轮 live 的提前截断修正 | metrics：`.yggdrasil/state/evaluations/evalrun_5c30dee62af74a3a8418.json`；sandbox：`.yggdrasil/state/evaluation-sandboxes/evalsandbox_e402f16fb6d44b47ba4b/`；run dir：`tmp/live-work-tree-complete-20260630/01-deepseek-directive-complete-64/`。 | 结果 `failed`，但不是 64 轮跑满：8 个 window 后被 `delivery.web-grounded-evidence` 截断。行为记录显示 12 次工具、4 个 create、1 个 enter、2 个 complete，首个窗口仍出现多 state directive；最终失败点是 leaf/父节点阶段无法获得有效 web 证据，门禁把非根工作节点的证据缺口当成整任务交付失败。 | 已修 runtime：hard delivery gate 仍只约束 root 最终交付；当本窗口是 `bubble-parent` / `continue-sibling` / `work-tree-continue` 等 child 工作树转移时，证据缺口应通过 child summary 回到父节点继续调度，而不是覆盖成 `delivery-gate-blocked`。新增回归 `test_child_completion_with_missing_web_evidence_bubbles_to_parent` 已通过；下一轮 live 才能真正验证 64 轮稳定性。 |
| 15. 门禁修正后 64 轮 live | metrics：`.yggdrasil/state/evaluations/evalrun_d79a4168cca348a3b235.json`；sandbox：`.yggdrasil/state/evaluation-sandboxes/evalsandbox_cbfdc1d38b344d70a612/`；run dir：`tmp/live-work-tree-complete-20260630/02-deepseek-directive-complete-64-after-gate-fix/`。 | 主流程越过上次 8 窗口截断点，并生成 `workspace/reports/ldes_route_selection_2030_final_v2.md` 与 `workspace/LDES_Comparison_Report_2030.md`。全 run 79 个 LLM response、91 个工具缓存、37 个 create、6 个 enter、83 个 complete、27 个多 state directive 窗口。最终 verification 三项通过，但 suite `blocked`：post-completion action 到 `processedRunCount=64` 后返回 `manual-continue-required`。最终 work tree 31 节点：24 completed、2 in-progress、5 pending；queued continuation 保留在 `work-item_67115ecdf8fb44efb538`。 | 结论：非根 hard gate 修正有效，工作树能长时间跑并产出报告；但仍不稳定。核心缺口是：1) seeded 高层节点仍可残留 pending，root 与最终合成父节点没有干净宣告整体完成；2) 同类 `work-tree-directive-required` 纠偏按不同 Scope 反复进入 `responseRequirements`，prompt 膨胀；3) 模型仍频繁同窗输出多个 state directive，runtime 能拦住但会造成额外 continuation；4) 报告文本仍可能写“Web 实时搜索通道不可用”，而 verification 因有成功工具执行通过，说明交付门禁还需要检查“最终报告自述”与工具证据的一致性。 |

## 追加实验：父子信息保留、结束收束与废旧节点清理

本轮把收束问题拆成三个独立 live 实验，避免把“信息丢失”和“结束流程不清楚”混在一起：

1. `evalsuite_g4_real_task_work_tree_deepseek_v4_pro_parent_retention_live`：DeepSeek V4 Pro，要求父节点在开新 leaf 前读取 `childCompletionSummaries`、已完成节点摘要、报告文件和工具证据，并写 `Parent Evidence Inventory`。如果已存在最终报告、source table 和 contradiction analysis，父节点应停止开 leaf 并完成自身/root。这个实验验证“实际干了但父节点感觉没干”的信息保留路径。
2. `evalsuite_g4_real_task_work_tree_deepseek_v4_pro_finish_prune_live`：DeepSeek V4 Pro，明确父节点停止条件和正确交付案例，同时新增废旧节点清理 directive：`<work-node-skip nodeId="...">reason</work-node-skip>` / `<work-node-prune nodeId="...">reason</work-node-prune>`。pending/in-progress child 如果是重复、过时、被真实 completed child 覆盖的 seeded placeholder，应被标为 `skipped`，而不是永久残留阻塞 root 收束。
3. `evalsuite_g4_real_task_work_tree_longcat_finish_prune_live`：LongCat-2.0，沿用第二个实验的结束/清理口径，只替换模型，验证失败是否主要来自代码/案例路径，而不是 DeepSeek 本身。

运行时语义：`work-node-skip` 与 `work-node-prune` 等价，都是可审计的废旧节点清理动作。它们只能作用于非 root 节点，必须带 reason，且目标节点不能还有未完成 child；成功后目标节点状态变为 `skipped`，`failureSummary` 保存清理理由，当前节点如果正好是被 skip 的节点则回到父节点。`skipped` 已是终态，父节点收束时与 `completed` / `failed` 一起视为 child terminal。

| 运行 | 证据 | 行为记录 | 结论 |
|------|------|----------|------|
| 16. DeepSeek parent-retention | metrics：`.yggdrasil/state/evaluations/evalrun_7947386eb44f480cad96.json`；sandbox：`.yggdrasil/state/evaluation-sandboxes/evalsandbox_de331431d9ad49e2ba07/`；分析：`tmp/live-work-tree-convergence-20260630/convergence-analysis.md` | 44 个 window，152 次工具执行（144 成功），assistant text 中 22 次 create、24 次 complete、1 次 enter。detail 层 `pass=false`、`deliveryCompletion0_1=0`、`workTreeContinuity0_1=0`，但 harness 外层仍显示 case passed。最终 work tree 23 节点：17 completed、1 in-progress、5 pending、0 skipped；root 仍 in-progress，5 个 seeded 高层节点仍 pending。 | 父节点信息保留提示能让模型多次写 `Parent Evidence Inventory` 并识别“不是父子信息丢失，而是工具/证据通道问题”，但不能清掉 seeded pending，也不能让 root 干净收束。这个方向不能单独解决“实际干了但感觉没干”。 |
| 17. DeepSeek finish-prune | metrics：`.yggdrasil/state/evaluations/evalrun_4c35306b3677410f9325.json`；sandbox：`.yggdrasil/state/evaluation-sandboxes/evalsandbox_b492d883ee2f44039695/`；分析：`tmp/live-work-tree-convergence-20260630/convergence-analysis.md` | 64 个 window 后 `manual-continue-required`，124 次工具执行（112 成功），assistant text 中 18 次 create、40 次 complete、1 次 enter、7 次 prune、5 次 skip，5 个多 directive window。最终 work tree 21 节点：14 completed、1 failed、1 skipped、1 in-progress、4 pending。产物 `workspace/ldes_comparison_report_2030.md` 已写入。 | 新 `skip/prune` 路径真实生效：至少 1 个废旧 seeded 节点被标为 `skipped`，说明允许删除/跳过是可行的。但模型只清掉一部分，仍留下 root in-progress 和 4 个 seeded pending；停止条件仍需要 runtime 层自动收束或更明确地批量处理兄弟占位节点。 |
| 18. LongCat-2.0 finish-prune | metrics：`.yggdrasil/state/evaluations/evalrun_73b271ede5694e61b1b0.json`；sandbox：`.yggdrasil/state/evaluation-sandboxes/evalsandbox_077fc08d68fa4605ba51/`；报告产物：`workspace/reports/LDES_2030_comparison_report.md` | 64 个 window 后 `blocked/manual-continue-required`，197 次工具执行（195 成功、2 次 `text_memory.append_memory_log` KeyError），`workTreeContinuity0_1=1`，tokens：input 29709、output 1165、cache hit 20736、non-cache 8973。最终 work tree 中 root 仍 `in-progress`，5 个 seeded 高层节点仍 `pending`，2 个节点 `skipped`，多个真实执行 leaf 已 `completed`。正式报告文件已写入，但报告来源表只写 `arXiv:...` 与领域来源，没有落 `http(s)://` 证据链接；official acceptance 因 `evidenceLinks=0` 失败。 | `LongCat-2.0` 模型名已可真实调用，且默认 `workTreeDirectiveRequired` / 批评式 revision 控制没有阻断工具执行；工作树连续性比旧结果好。但父/root 收束仍失败，模型会写“所有子节点均已终止”的验收自述，而 runtime 仍有 root/seeded pending。报告没有把工具证据 URL 落入最终文件，说明“真的查了资料”还需要交付物级证据链接门禁，不能只看工具调用数。 |

本轮还修复了一个评测器缺口：`suite_cases_g4.py` 以前会把最后 assistant 的验收短文保存为 `preservedPaper` 并用于 official acceptance，导致真实写入 workspace 的报告文件被旁路。现在评测会优先选择 `workspace/reports` / `output(s)` / `deliverables` 下更像正式交付物的 Markdown 正文；如果正式报告仍没有 `http(s)://` 证据链接，`g4-min-evidence-links` 仍保持失败，不放宽为 `arXiv:...` 文本。

## 当前测试与默认化状态

已执行 / 已保留入口的工作树 live 实验：

| 实验入口 | 主要变量 | 当前定位 |
| --- | --- | --- |
| `eval:g4:work-tree:post-question` | completed 后用 user 追问“为什么不用工作树”等 | 诊断用；不默认 |
| `eval:g4:work-tree:step-reflection` | 每步后反思当前工作树位置 | 诊断用；不默认 |
| `eval:g4:work-tree:critique-continue` | 批评式 revision 继续 | 补救入口；不默认 |
| `eval:g4:work-tree:tool-end-reminder` | 工具结果末尾提醒流程控制 | suite-only；不默认 |
| `eval:g4:work-tree:tool-call-leaf-example` | 强 leaf 示例 | suite-only；案例已强化父/子边界 |
| `eval:g4:work-tree:leaf-self-talk` | leaf 内自言自语确认 scope / stopping point / return path | suite-only；不默认 |
| `eval:g4:work-tree:deepseek-v4-pro` | 换 DeepSeek V4 Pro | 模型对照 |
| `eval:g4:work-tree:deepseek-v4-pro-critique-continue` | DeepSeek + 批评继续 | 模型 + 补救对照 |
| `eval:g4:work-tree:deepseek-v4-pro-node-tool-budget` | auto-unfinished + 每节点 5 次 toolcall 软预算 | suite-only；`auto-unfinished` runtime 能力保留 |
| `eval:g4:work-tree:deepseek-v4-pro-directive-required` | 自然语言换节点无效 + runtime directive-required + complete | 高强度协议实验；不全局默认 |
| `eval:g4:work-tree:deepseek-v4-pro-parent-retention` | 父节点读取 child summaries / artifacts 后再开 leaf | 诊断父子信息丢失；不默认 |
| `eval:g4:work-tree:deepseek-v4-pro-finish-prune` | DeepSeek + 停止条件 + skip/prune | 收束实验；skip/prune runtime 能力保留 |
| `eval:g4:work-tree:deepseek-v4-flash-finish-prune` | DeepSeek V4 Flash + 同一 finish/prune 口径 | 模型对照；用于测试默认 directive-required / revision control |
| `eval:g4:work-tree:longcat-finish-prune` | LongCat-2.0 + 同一 finish/prune 口径 | 模型对照；skip/prune runtime 能力保留 |

DeepSeek V4 Flash 补充归因（`evalrun_94a007f1e8a74d338d58` / `evalsandbox_bbef81c7e0d9411e86fe`）：这轮不是“报告质量差”导致的工作树结论，而是工作树链路本身没有推进。8 个 window 的 takeover 快照显示 currentNodeId 始终在 root，root 始终 `in-progress`；5 个 root-level seeded 节点（固定研究问题、抽取约束、收集与归纳、校验证据、交付结论）从头到尾保持 `pending`；模型只把第一个 seeded 探索节点从 completed/active 清成 `skipped`，没有创建真实执行 leaf，也没有进入“列出全部 pending seeded child -> 批量 prune/skip -> root complete”的父节点核账流程。因此 `workTreeContinuity0_1=0` 的含义是：窗口连续执行存在，但工作树没有形成有效的节点推进/收束连续性，仍停留在 root + seeded pending 结构。

DeepSeek V4 Flash directive-required 机制复核：同一旧 run 中，compiled prompt 已包含“自然语言不会切换 currentNodeId / complete leaf”的规则，post-completion action `auto-unfinished-directive-required-continue` 也进入 `currentFocus=work-tree-directive-required`。机制本身生效；失败点是模型多次输出错误标签 `<work-tree-node-create ...>`，而 runtime 支持的是 `<work-node-create ...>` / `<work-node-enter ...>` / `<work-node-complete ...>` 等 `work-node-*` directive，因此没有可应用的状态变更。

新增未完成节点工具后的复跑：

| 编号 | 证据 | 关键行为 | 结论 |
| --- | --- | --- | --- |
| 19. DeepSeek V4 Flash + `list_unfinished_work_nodes` | metrics：`.yggdrasil/state/evaluations/evalrun_7d736ac1c0a04621893c.json`；sandbox：`.yggdrasil/state/evaluation-sandboxes/evalsandbox_60a26e8edf4d49b69d3d/`；报告：`workspace/long_duration_storage_comparison_report.md` | suite 外层 `failed`，错误来自 worker `timeoutExceeded=true` / `awaiting-approval` 口径；但最终 takeover 已 `verified`，work tree 为 root `completed`、3 个真实 child `completed`、5 个 seeded child `skipped`。本轮调用了 `task_takeover.list_unfinished_work_nodes`，并完成“查未完成节点 -> 清 seeded 占位 -> 开真实 child -> child complete -> root complete”的链路。 | 工作树链路这次是成功样本；失败不应解读为 root/seeded pending 未收束，而是 evaluation worker 对 `awaiting-approval` / timeout 的完成态判定还没有和 work tree completed 对齐。 |
| 20. LongCat-2.0 + `list_unfinished_work_nodes` | metrics：`.yggdrasil/state/evaluations/evalrun_c0993760679040ec8fce.json`；sandbox：`.yggdrasil/state/evaluation-sandboxes/evalsandbox_4d8871c3a55644708668/`；报告：`workspace/LDES_Route_Selection_Report_2030.md` | suite 外层 `failed`，但最终 takeover 已 `verified`，work tree 为 root `completed`、3 个真实 child `completed`、5 个 seeded child `skipped`。`llm_08837077201346dcad61` 调用了 `task_takeover.list_unfinished_work_nodes`，先识别 seeded pending，再清理占位节点；后续两个真实 child 分别完成文献采集和报告编制，最后 root 完成。报告仍有来源 URL/DOI 不足的质量缺口。 | LongCat 也能采用新工具和清理路径。当前主要缺口从“模型不会收束工作树”转成两个后续问题：外层 evaluation 不接受 awaiting-approval completed work tree；交付物质量门禁需要继续要求 URL/DOI 级证据。 |
| 21. DeepSeek V4 Flash + `confirmChildren` 收束复跑 | metrics：`.yggdrasil/state/evaluations/evalrun_fe0bb32dd4244c4bbeb3.json`；sandbox：`.yggdrasil/state/evaluation-sandboxes/evalsandbox_dcb220891abb4a9b8bce/`；报告：`workspace/report.md` | suite 外层 `completed/passed`，case 用时约 16m49s；12 个 worker window，transition 链为 prune/enter/enter/bubble/bubble/enter/enter/bubble/bubble/bubble/awaiting-approval/awaiting-approval。最终 work tree 干净收束：root `completed`，5 个真实节点 `completed`，5 个 seeded planning placeholder `skipped`，无 pending/in-progress。真实工具执行 79 次（76 成功，3 次 `text_memory.append_memory_log` 失败），工具类别包含 `web` / `compute` / `memory`，调用了 `task_takeover.list_unfinished_work_nodes`，最终 root 使用 `work-node-complete confirmChildren="true"`。official acceptance 仍因 `evidenceLinks=0` 失败，detail 层 `pass=false`，但 `failOnAcceptanceViolation=false` 使 suite 外层通过。 | 新的 `confirmChildren` 与“状态信号不是任务未完成判断”的提示已打通 DeepSeek V4 Flash 的最终收束路径。工作树问题这轮不再是 root/seeded pending，而是报告质量门禁：最终报告有来源表和工具证据，但没有把 `http(s)://` 证据链接落入交付物。后置 diagnostic follow-up 会输出旧式/错误 directive 语言，只能作为自我解释样本，不应覆盖 runtime takeover JSON 的事实。 |
| 22. LongCat-2.0 + `confirmChildren` 收束复跑 | metrics：`.yggdrasil/state/evaluations/evalrun_d2d79016d29e46a582bb.json`；sandbox：`.yggdrasil/state/evaluation-sandboxes/evalsandbox_306b6a68d1644a4587f8/`；报告：`workspace/report_draft.md` | suite 外层 `completed/passed`，case 用时约 12m47s；4 个 worker window，transition 链为 bubble-parent/work-tree-skip/awaiting-approval/awaiting-approval。最终 work tree 干净收束：root `completed`，1 个真实 child `completed`，5 个 seeded planning placeholder `skipped`，无 pending/in-progress。真实工具执行 64 次（64 成功，0 失败），工具类别包含 `web` / `memory`，调用了 `task_takeover.list_unfinished_work_nodes`，最终 root 使用 `work-node-complete confirmChildren="true"`。official acceptance 仍因 `evidenceLinks=0` 失败，detail 层 `pass=false`，但 suite 外层通过。 | LongCat-2.0 同样能稳定采用“列未完成节点 -> prune seeded child -> root confirmChildren 完成”的路径，而且轮次明显少于 DeepSeek。当前共同缺口不是工作树收束，而是最终报告 URL 证据链接门禁；另外 `workTreeContinuity0_1=0` 与实际 transition 链不一致，说明该指标不适合作为本轮工作树成败的单一判断。 |

当前已经默认进入 runtime / prompt 的特性：

1. 默认 prompt 说明 root/非叶子节点负责高层视角、流程控制、方向重估、信息合并和最终完成判断；leaf 只负责自己边界内的具体执行，不能宣告全局任务完成。
2. 默认 prompt 说明 child/leaf 开始前要确认 scope、stopping point、return path；完成后用 `work-node-complete` 把结果交回父节点，由父节点选择继续开 leaf、关闭/清理 child 或最终交付。
3. `work-node-create` / `work-node-enter` / `work-node-complete` / `work-node-handoff` / `work-node-skip` / `work-node-prune` 的解析和行为记录已进入代码路径。
4. `work-node-complete` 默认 bubble 回父节点，把 child summary 写入父 frame；子节点不能直接替 root 完成全局任务。
5. `work-node-skip` / `work-node-prune` 支持批量清理无后代占位子节点；清理有终态 leaf 的父节点需要 `confirmChildren="true"`；有未完成后代时返回 `work-tree-prune-confirm-required`。
6. `auto-unfinished` revision 选择逻辑仍在 runtime 中：当前节点有未完成 child 时在当前节点继续；当前节点完成但 sibling 未完成时回父节点继续；否则回到第一个未完成节点的父节点。后续实验看起来“丢了”是因为部分 suite 满 64 轮后直接 `manual-continue-required`，没有进入 post-completion revision。
7. `manual-continue-required` 已是长任务满轮后的保留现场机制。
8. 行为记录器默认记录 assistant work-tree directive、自然语言声明与真实工具行为，用于审计“报告自述”和“真实做过什么”的差异。
9. `llm_runtime/invoke.py` 默认启用工作树 directive barrier：同一 assistant response 里只要出现会改变当前节点的 `work-node-*` 标签，runtime 会先延后本轮 provider toolCalls，把标签交给 worker 应用；下一窗口在新的 `currentNodeId` 下重新编译 prompt 后再执行工具。
10. `workTreeDirectiveRequired` 已默认启用：模型用自然语言声称创建/进入/切换节点、Leaf Handoff 或返回父节点但没有可应用 directive 时，runtime 会触发 `work-tree-directive-required` continuation，要求先补真实 `work-node-*` 标签。
11. `request_task_revision()` 默认采用批评式任务控制继续：未显式指定时选择 `nodeId=auto-unfinished`，在 `resumeMessage/responseRequirements` 中要求先做 Task Control Analysis，再选择真实 work-tree directive、清理废旧节点、进入 leaf 或完成当前父/root。
12. `task_takeover.list_unfinished_work_nodes` 已注册为只读 agent tool：从当前 `takeoverProtocol.workTree` 列出所有非终态节点，标记 root、current node、未完成 child、可能的 seeded planning placeholder，并直接给出 `suggestedBatchPruneNodeIds` 与批量 `<work-node-prune nodeIds="...">...</work-node-prune>` 示例。默认 prompt 和 revision 提示在 unresolved children 场景要求优先使用该工具，避免模型手工扫描整棵 workTree JSON。
13. provider 调用默认使用流式响应；`YGGDRASIL_LLM_STREAM_IDLE_TIMEOUT_SECONDS` 只表示连续无字节返回的 idle timeout，不再把 provider 持续输出的长生成误判成总时长超时。流式断开会进入 retry，并在成功响应的 `rawResponse.streamReconnect` 中记录重连事件；DeepSeek 重试仍可切到非 stream + `Connection: close` 作为保底。provider profile 已记录模型最大输出上限：DeepSeek V4 Flash/Pro 384000、LongCat-2.0 128000；网关会把较小 runtime `maxTokens` 提升到模型支持上限，并用 `yggdrasil_requested_max_tokens` 留下原始请求值。
14. `work-node-complete` 已支持 `confirmChildren="true"`：如果当前节点还有非终态后代，未确认时 runtime 会提醒这只是“节点未标终态”的状态信号，不等于实际工作没完成；确认后 runtime 会把当前节点及其非终态子树递归标为 completed。`parent-orchestration-required`、revision 默认提示和 `task_takeover.list_unfinished_work_nodes` 均已改成“先核查状态与交付物，再自行判断”的口径。

仍是 suite-only / 未默认化的特性：

1. `toolResultReflectionReminder` 工具末尾强提醒。
2. 每节点 5 次 toolcall 软预算和第 6 次警告。
3. diagnostic follow-up 侧信道追问。

下一步代码方向：

1. runtime 收束语义继续加强：父节点在所有 child terminal 且交付物存在时，应有稳定路径批量 prune 被覆盖 seeded child，并完成 root；`task_takeover.list_unfinished_work_nodes` 先缩短了模型链路，但仍不是自动收束。

## 关键观察

1. 工作树标签已经成为工具执行前的 runtime barrier。模型如果在同一 response 一边创建/进入/完成节点一边返回 provider toolCalls，runtime 会把 toolCalls 记录为 `deferredToolCallsByWorkTreeDirective`，不在旧节点执行；worker 先应用工作树 directive 并排下一窗口，让工具工作落到新的当前节点。
2. `toolResultReflectionReminder` 是低侵入硬提醒，能让模型在每次工具批次后看到流程控制提示，但 LongCat 仍倾向直接把任务做完，不主动发工作树标签。
3. “每个工具调用为一个 leaf”的示例过硬时，确实能促成 child/leaf；但必须同时规定父节点职责，否则 leaf 会自称完成整体任务，或者 runtime 会在 leaf 输出后直接把任务标 completed。
4. DeepSeek V4 Pro 在同题中通过严格验收，缓存命中与非缓存 token 都有记录，工具证据充分；加入实验 2 的强 leaf 方法后，它能先开 leaf 并在 leaf 内执行工具，但仍不会自动完成“父节点评估 -> 下一 leaf -> 最终交付”的全流程。
5. 上一轮最大缺口不是“模型能否创建 leaf”，而是“leaf handoff 后父节点/高层节点必须重新获得控制权，并评估是否继续、关闭或交付”；本轮已把这条路径实现为 `work-node-complete`，live 已证明模型会采用该路径。`最终合成/撰写报告` 可以作为 child，关键是它完成后必须回父节点认可。
6. “批评后继续 + 先做任务控制分析”能解决 revision 入口和继续干活问题，但仍不能独立解决工作树流程控制；如果 runtime 只把任务重开到 root，模型可能把批评理解成“补一份更完整报告”，而不是继续未完成 leaf。
7. `auto-unfinished` continuation 是正确方向：它能把 post-completion revision 从 root 纠正到父/编排节点。但如果后续“创建/进入 child”仍只停留在自然语言，而没有 directive/runtime 状态变化，模型仍会在父节点执行 leaf 工作。
8. 节点级 toolcall 软预算能改变模型策略，但作为 prompt 压力仍不够硬；它能让模型少用工具并输出 handoff，不能保证 LLM 真实切换工作树节点。
9. `work-tree-directive-required` 能把“自然语言声称换节点”变成 runtime 可见错误：父节点伪造 leaf、leaf handoff、返回父节点都能被记录并纠偏。它解决的是“文本表演不等于状态变化”的问题。
10. 只靠 `create/enter` 两类 directive 不够。leaf 结束需要一个可验证的完成/交接动作；本轮新增的 `work-node-complete` 解决运行时路径问题，后续实验要观察 LLM 是否会按正确案例稳定使用它，而不是继续写自然语言 handoff。
11. 长链 continuation 的 prompt 去重是工作树控制的一部分。否则即使协议正确，重复 checkpoint 也会把模型推向“继续补 leaf/补证据”的惯性，削弱父节点最终评估与收束。
12. `delivery.web-grounded-evidence` 这种最终交付 hard gate 不能在 child/leaf handoff 窗口直接截断整棵工作树。leaf 的证据缺口必须先作为交付摘要返回父节点，由父节点决定补证、换路线或最终判定；只有 root 最终交付才应被 hard gate 阻断。
13. 门禁修正后，真实任务能越过早期截断并长时间使用工作树。新增 `list_unfinished_work_nodes` 后，DeepSeek V4 Flash 与 LongCat-2.0 均出现 root completed + seeded skipped 的成功轨迹；但 DeepSeek V4 Flash `evalrun_7bf1bde2dcb54e769560` 又暴露出新缺口：suite 外层 completed/passed 时，最终 takeover 仍可能保留 root 和深层节点 `in-progress`。因此“外层完成态”和“工作树节点干净收束”必须分开验收。
14. 如果允许 seeded placeholder 存在，就必须允许父节点审计后删除或跳过它们。否则模型即使已经完成真实工作，也会被旧规划节点拖住，表现成“报告产出但任务不结束”。
15. DeepSeek V4 Flash 手动 revision 继续 `run_3858cfd93790449c9d9c` 不是 provider timeout：LLM 调用了 `task_takeover.list_unfinished_work_nodes`、记忆和文件搜索工具，最后以 `finishReason=length` 截断且无 final assistant directive，runtime 排了下一轮 continuation。继续消费到 `run_48824ae64a294af2b734` 后，runtime 仍返回 `parent-orchestration-required`，未完成节点仍是 root -> 探索样本池 -> 系统采集 -> matrix parent -> web/paper leaf 五层 `in-progress`。后续已把 provider 请求上限提升到模型支持最大值，并加入 `confirmChildren` 完成子树确认；若仍出现循环，就应归因于父节点调度/收束，而不是输出 token 上限。

## 暂不切成默认行为的原因

1. 工具末尾提醒没有显著改善 leaf 使用，默认开启会增加上下文噪声。
2. 强 leaf 示例能改善执行位置，但会放大父节点完成态问题；如果 runtime 不保证 leaf handoff 后回父节点，强示例会制造“leaf 写完即 completed”的假完成。
3. DeepSeek 结果证明高质量模型可以提升最终报告可信度，但不能替代工作树协议修复。
4. 批评式 revision 已固化为默认补救入口，但仍不能替代工作树正确性本身；它的作用是把继续位置、任务控制分析和真实 directive 要求写入 continuation，让 LLM 回到未完成节点继续。
5. 节点工具调用软预算适合作为实验开关，不适合直接默认开启；否则模型可能为遵守 5 次限制而过早交接、降低证据质量。
6. `work-tree-directive-required` 已默认开启；后续风险重点从“是否开启”转为“纠偏文本是否过度重复、是否会在无工作树任务中制造噪声”。

## 后续建议

1. 如果目标是“必须 leaf 执行”，prompt 示例应显式要求根/父节点只创建 child 并停止，不能把创建 child 和工具调用放进同一窗口。
2. 下一步应改 runtime 收束语义：leaf 输出 handoff 后默认 bubble 到父节点继续编排，父节点必须评估 child 输出并显式选择“继续开 leaf / 关闭 child / 最终交付”。子节点不能直接把整体任务标 completed。
3. revision 继续时不应只把 `nodeId=root` 当作目标；runtime 应根据 unfinished nodes 和最近 leaf handoff 选择父/编排节点，或者至少把“当前必须评估哪个 child、下一 leaf 是什么”写入 continuation frame。
4. 下一步应把“父节点自然语言说进入 leaf”升级为 runtime 可验证动作：如果模型声称创建/进入 child 但没有 directive，harness 应继续停在父节点并要求补发 directive，不能让父节点直接执行 leaf 工具。
5. 下一步应重跑 64 轮 live：允许“最终合成 / 撰写报告 / 交付结论”作为 child 执行；验收重点改为该 child 是否用 `work-node-complete` 交回父节点、父节点是否认可并完成整体任务。若 64 轮仍不够，使用 `manual-continue-required` 现场继续。
6. 对真实任务验收同时看两类指标：交付质量指标（`pass/officialAcceptance`）和工作树行为指标（directive、current node、node status、window execution）。
7. DeepSeek V4 Pro 可作为高质量真实任务基线，也可作为“模型能服从 leaf 入口规则”的基线；但在父节点自动收束修复前，不能作为完整工作树使用成功的证据。



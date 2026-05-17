# 世界树计划 · G4 真实任务窗口对照重跑与日志审计（2026-05-16）

- 文档状态：Log-Preserved Rerun On LongCat With Root-Cause Analysis
- 日期：2026-05-16
- 重跑命令：`$env:YGGDRASIL_EVAL_PRESERVE_SANDBOX=1; $env:YGGDRASIL_RUNTIME_AUDIT_LEVEL='strict'; corepack pnpm eval:g4:real-task-parity`
- 重跑 run：`evalrun_941c8b8ca2204966812d`

## 0. 后续正式重跑补记（2026-05-16 晚）

在完成记忆树主链升级收尾和 Windows 本地评估句柄清理修复后，又做了一次可复查的正式重跑：

- 正式 run：`evalrun_222cdf10ebd642009bdb`
- 运行命令：
  - `YGGDRASIL_DATABASE_URL=sqlite+pysqlite:///<repo>/.yggdrasil/evaluation.db`
  - `YGGDRASIL_AUTO_CREATE_SCHEMA=1`
  - `YGGDRASIL_EVAL_PRESERVE_SANDBOX=1`
  - `YGGDRASIL_RUNTIME_AUDIT_LEVEL=strict`

这次重跑的目的不是再看 scorecard 是否 `passed`，而是确认：

1. 工件是否真正保留到仓库 `.yggdrasil/state/evaluation-sandboxes/` 下，可供复查。
2. 最终 response 是否已经从 planning stub 变成任务要求的 `release brief + parity judgment`。
3. 当前 suite 是否真的再次触发了多窗口重启，而不是在单窗口内直接完成一个较短回答。

结论如下：

1. **工件保留已生效。** 两个 case 的 request / response / compiled prompt 已稳定落到仓库 state 下：
	- short64k：`.yggdrasil/state/evaluation-sandboxes/evalsandbox_729522f1532d47a88d01/`
	- long128k：`.yggdrasil/state/evaluation-sandboxes/evalsandbox_a2bdad8d16fa4e2e825b/`
2. **最终输出仍然不是 release brief。** 两个 case 的 raw response 都停在“先总结当前局势，再给出最稳妥的下一步”的 planning stub：
	- short64k response：`.yggdrasil/state/evaluation-sandboxes/evalsandbox_729522f1532d47a88d01/.yggdrasil/state/llm/responses/llm_cfc8acbca56e4f2cb411.json`
	- long128k response：`.yggdrasil/state/evaluation-sandboxes/evalsandbox_a2bdad8d16fa4e2e825b/.yggdrasil/state/llm/responses/llm_d958c9d3281d40dbbc85.json`
3. **这次 run 已经不再是多窗口验证。** 两个 case 都只有 `windowIndex=1`、`restartCount=0`、`cumulativeWindowSpanTokens=0`，`beforeContextPruning` 也只有 `7` 个 context item、约 `459` token。也就是说，这次 suite 实际跑成了单窗口短回答，而不是先前 `4.10M` 级跨度、`restartCount=1` 的真实窗口接续任务。
4. **因此当前结果只能说明“命令可跑、工件可审计、planning stub 仍在”，不能说明“记忆树恢复后的真实任务 parity 已验收通过”。** 这次的 `pass=true` 依然只是结构性 pass，不是最终交付质量 pass，也不是多窗口等价性 pass。

这个补记和上文并不冲突，而是把当前结论进一步收紧为：

1. 先前 run 暴露的是“多窗口技术闭环成立，但恢复后输出漂移到 planning stub”。
2. 本次 run 进一步暴露的是“当前 suite/运行配置甚至没有再次触发多窗口重启，因此已经不能充当真实窗口 parity 的正式验收”。

### 0.1 验收器收紧后的正式复跑（2026-05-16 晚）

在把 `g4.live_provider_matrix` 的官方验收从“只看 invocation completed”收紧到“同时检查最终交付结构、判断短语和 restart 证据”之后，又做了一次正式复跑：

- 正式 run：`evalrun_ac1f6540396f4f42aadf`
- suite 状态：`failed`
- 结果：`2/2 failed`

两个 case 的失败原因都已经不再是模糊的 scorecard 争议，而是被正式 acceptance 直接判出：

1. 缺少必需小节：`任务价值判断 / 联调覆盖范围 / 关键集成链路 / short-window 配置 / long-window 配置 / acceptance 对照结论 / 风险与下一步`
2. 缺少 `高价值` 或等价判断短语，或者直接命中 planning-stub 拒绝短语。
3. `restartCount=0`、`windowIndex=1`、`cumulativeWindowSpanTokens=0`，不满足“真实多窗口任务”最低证据门槛。

对应保留沙箱：

1. short64k：`.yggdrasil/state/evaluation-sandboxes/evalsandbox_030c9e5833ca4c9ea1dd/`
2. long128k：`.yggdrasil/state/evaluation-sandboxes/evalsandbox_d32f14c45d1742b2adfc/`

这意味着当前结论已经从“人工审计认为不算通过”升级成“官方 suite 在正式 acceptance 下直接 failed”。

### 0.3 推进到理论水平需要做的事（2026-05-16 晚）

基于对代码库的完整分析（`execution_loop.py` / `snapshot.py` / `prompting.py` / `suite_cases_g4.py`），把工程推进到理论水平需要按如下 4 个层次逐层修复。

#### 推进项 A：触发层稳定化（已部分修复）

**已查明**：

- `.yggdrasil/state/evaluations/evalrun_1160dc08b84e4b6e8268.json` 文件存在，**不是**文件丢失导致的触发层回归。
- `_window_restart_trigger` 逻辑本身正确：`effectiveContextWindow=64000`、`windowRestartRatio=0.75`，理论 restart 阈值 = 48000 tokens；只要 context 加载出 ≥ 48000 tokens 就会触发。
- `evalrun_222cdf10ebd642009bdb` 的 `beforeContextPruning: 7 items / 459 tokens` 说明 `_g4_current_context` 在该次 run 里只返回了 7 个 item，而不是预期的 100+ 个。

**假设根因（待验证）**：

evaluation sandbox 是否在隔离环境下运行，导致 `resolve_workspace_root()` 返回沙箱目录而不是仓库根目录，进而让 `currentContextFiles` 和 `currentContextGlobs` 的文件路径全部无法 resolve。需要在 `_g4_current_context` 的开头打印 `workspace_root` 路径来确认。先前触发 4.10M 的 run 可能是在不同环境下执行的（非沙箱路径或使用了不同的 workspace root 实现）。

**短期可操作修复**（已实施 1 项，待实施 1 项）：

1. **已实施**：suite_cases_g4.py 现在可以 forward `responseRequirements` 和 `restartMessage`，确保即使触发层当前不工作，一旦 restart 发生语义层就能正确产出。
2. **待实施**：在 `_g4_current_context` 里加一条 debug log，记录 `workspace_root` 路径和最终返回的 item 数量，下次 run 时直接从 sandbox audit 日志里读取。

**长期要求**：确保 `resolve_workspace_root()` 在 evaluation sandbox 环境下始终指向实际仓库根，而不是沙箱隔离目录。这是触发层能稳定工作的唯一保证。

#### 推进项 B：恢复语义修复（已完成核心代码）

**问题根因**：

`prompting.py` 的 `_format_response_requirements` 第 1 行硬编码：

```
1. 先总结当前局势，再给出最稳妥的下一步。
```

这条指令在所有窗口（包括 restart 后的窗口 2）都生效。模型把这条指令当作主要输出格式，产出"我会先总结当前局势，再给出最稳妥的下一步"之类的前言，进入 planning stub，而不是直接交付最终产出。此外，`suite_cases_g4.py` 此前从未把 case 配置里的 `responseRequirements` 字段 forward 到 `start_payload`，导致即使 suite JSON 写了交付合同，也对模型不可见。

**已实施修复**（本轮）：

1. **`prompting.py`**：`_format_response_requirements` 现在检测 `has_delivery_contract`：若 `responseRequirements` 字段存在，第 1 行改为 `"1. 直接产出以下要求指定的最终交付物，不要停在计划或下一步总结。"`，从而把 planning-first 模式切换为 delivery-first 模式。
2. **`suite_cases_g4.py`**：`_run_g4_live_provider_matrix_case` 现在检测 `case_payload.get("responseRequirements")` 和 `case_payload.get("restartMessage")`，将它们 forward 进 `start_payload`。
3. **`g4-real-task-window-parity.json`**：两个 case 均加入 `responseRequirements`（7 小节 + 明确要求 `高价值` 和 `等价/不等价` 判断）和 `restartMessage`（窗口 restart 时要求模型直接产出完整 release brief，不得停在计划）。

**关于 `responseRequirements` 的跨窗口传递**：

`snapshot.py` 的 `_build_restart_request_state` 已经把 `responseRequirements` 纳入 keys 列表，因此它会随 restart snapshot 的 `pendingActions.requestState` 被传递到下一个窗口。无需额外修改。

#### 推进项 C：交付合同跨窗口透传（已完成核心代码）

**问题根因**：

`snapshot.py` 的 `_build_carry_forward_context` 从 request payload 读取 `restartMessage`（或 fallback 到 `resumeMessage`），并嵌入 carry-forward package 的 `content` 字段（`Restart instruction: {restart_message}`）。但此前 `_build_restart_request_state` 的 keys 列表里没有 `restartMessage`，导致初始 start_payload 里的 `restartMessage` 在第一次 restart 后无法被写入 snapshot 的 `requestState`，第二次以后的窗口拿不到这条指令。

**已实施修复**（本轮）：

`snapshot.py` 的 `_build_restart_request_state` keys 列表新增 `restartMessage`。效果：初始 start_payload 里的 `restartMessage` 现在会随 `requestState` 一起持久化进 snapshot 的 `pendingActions`，后续每次窗口重启都能从 carry-forward package 里读到同一条交付合同提示。

#### 推进项 D：100 次受控窗口对照评测（未开始）

当前触发层和交付合同层修复完成后，下一个真正的长距离目标是：

1. **将 `effectiveContextWindow` 降到一个 100 次可重复触发的合理值**（例如 8192 或 16384），并把 `forcedWindowRestartBudget=100` 用于压力测试。
2. **建立 `finalAcceptanceParity0_1` 和 `deliveryEquivalence0_1` 两个正式指标**，分别衡量"短窗口路径与长窗口路径是否得出相同验收结论"和"两条路径的最终交付物是否满足同一合同"。
3. **冻结 `restartSuccessRate0_1`**：100 次 restart 中每次都必须成功接续到下一窗口，目标为 1.0。
4. **冻结质量差值门槛**：短窗口相对长窗口的质量差值（`qualityDeltaToLongWindow0_100`）需在 3 轮稳定复跑后冻结成正式出口标准。

这 4 个指标一旦全部满足，才算从"结构性闭环成立"升级到"理论水平成立"的正式 release 证据。

#### 推进项 E：触发层根因调查脚本

在下次正式复跑前，建议在 `_g4_current_context` 内部加如下 debug 插桩，直接读取 sandbox 审计日志：

```python
import logging
_logger = logging.getLogger(__name__)
_logger.debug(
    "g4_current_context: workspace_root=%s, files=%d, globs=%d, total_items=%d",
    workspace_root,
    len(case_payload.get("currentContextFiles") or []),
    len(case_payload.get("currentContextGlobs") or []),
    len(context_items),
)
```

这条日志落到 `.yggdrasil/state/observability/` 下后，可以直接从 sandbox 里读取 `workspace_root` 值，确认是仓库根还是沙箱目录。

---

### 0.2 工程现实与理论设想的差距

把这几次重跑放在一起后，工程现实和理论设想之间的差距已经可以明确分成 4 层：

1. **任务触发层。**
	- 理论设想：real-task parity 必须稳定进入多窗口 restart，才有资格讨论 64k/128k 是否等价。
	- 工程现实：最新正式 run 已经退化成 `windowIndex=1 / restartCount=0 / cumulativeWindowSpanTokens=0` 的单窗口短回答，说明“真实任务语料足以压出 restart”这件事还没有被稳定冻结成执行现实。
2. **恢复语义层。**
	- 理论设想：恢复后的全部工作记忆应由记忆树 + work tree 驱动，模型继续沿原执行节点完成最终交付。
	- 工程现实：即使 earlier rerun 已证明技术 restart 闭环成立，恢复态仍然容易被 prompt contract 拉回 planning stub，work tree 更像计划骨架而不是 durable execution pointer。
3. **交付合同层。**
	- 理论设想：最终输出应直接是 release brief，并明确回答 short-window 与 long-window 是否等价。
	- 工程现实：模型仍然会交出“先总结当前局势，再给出下一步”的计划前言，缺少正式小节、缺少高价值判断、缺少 parity judgment。
4. **评测门禁层。**
	- 理论设想：scorecard pass 应等价于任务真的交付完成。
	- 工程现实：如果不把小节结构、判断短语和 restart 证据显式冻结进 acceptance，系统就会把 structural pass 误报成 delivery pass。当前已经通过收紧验收器把这个偏差从“研究结论”转成“正式 failed signal”。

---

## 1. 任务目标

本次重跑沿用正式 suite `evalsuite_g4_real_task_window_parity` 的同一条真实任务：

> Review the current Project Yggdrasil repository and produce a final release brief for pseudo-infinite context parity. The brief must first judge whether this is a high-value real task for the current repo, then synthesize the global integration chain across runtime, evaluation, protocol, provider, documentation, and evidence surfaces. The final answer must explicitly decide whether a realistic short-window path can be treated as equivalent to a realistic long-window reference for the current repo state.

运行期 objective 没变，仍然是：

> Turn the current repo state into a release-ready parity judgment across realistic context windows without dropping cross-surface evidence.

---

## 2. 日志保留结果

这次重跑显式开启了：

1. `YGGDRASIL_EVAL_PRESERVE_SANDBOX=1`：把每个 case 的隔离评测沙箱保留到仓库 state 下。
2. `YGGDRASIL_RUNTIME_AUDIT_LEVEL=strict`：保留完整 request / response / compiled prompt / rawResponse 工件。

两个 case 的保留沙箱如下：

| Case | Sandbox | Invocation | 关键工件 |
|------|---------|------------|----------|
| short64k | `.yggdrasil/state/evaluation-sandboxes/evalsandbox_d18119b6731849d0b54f/` | `llm_02a762911fe243738a34` | `llm/requests/llm_02a762911fe243738a34.json` / `llm/responses/llm_02a762911fe243738a34.json` / `prompt/compiled/llm_02a762911fe243738a34.json` |
| long128k | `.yggdrasil/state/evaluation-sandboxes/evalsandbox_a36b08c6576b482694a2/` | `llm_a0ef16ca13794fa9969a` | `llm/requests/llm_a0ef16ca13794fa9969a.json` / `llm/responses/llm_a0ef16ca13794fa9969a.json` / `prompt/compiled/llm_a0ef16ca13794fa9969a.json` |

每个沙箱内还保留了：

1. `evaluation.db`：任务、snapshot、invocation 等数据库记录。
2. `.yggdrasil/state/observability/`：本 case 的观测日志。
3. `.yggdrasil/state/runtime/`：运行期打包和恢复相关状态。

---

## 3. 每个上下文窗口内做了什么

### 3.1 short64k case

- case id：`evalcase_g4_real_task_window_parity_longcat_short64k`
- task id：`task_85eb12a515e54ac98f60`
- `restartCount=1`
- `windowIndex=2`
- `cumulativeWindowSpanTokens=4104637`

窗口 1：

1. 接收真实 repo-wide 任务，请求 objective 仍是 parity judgment。
2. 未产生任何 assistant 文本，也没有工具调用。
3. Worker 结果直接进入 `restarting`，生成 restart snapshot `snap_4b1b9eaaa8a44981a4e4`。
4. snapshot 记录显示它把整个窗口跨度 `4104637` token 压成 1 个 carry-forward package，并把 `windowIndex` 从 1 推到 2。

窗口 2：

1. 从 snapshot 恢复，只 rehydrate 了 1 个 context item。
2. 编译后的 prompt 一共 10 条 messages，真正携带当前任务状态的是最后 1 条 `runtime_state` 用户消息。
3. 这个 `runtime_state` 包里仍包含原始 `task_goal`，但 response requirement 已经变成“先总结当前局势，再给出最稳妥的下一步”。
4. 本窗口没有工具调用，只有 1 轮模型调用。
5. `afterWindowRestart` 的 carry-forward 工作集大小是 `24326` token；真正发给模型的 prompt message 总量约 `2047` token。

### 3.2 long128k case

- case id：`evalcase_g4_real_task_window_parity_longcat_long128k`
- task id：`task_f0fdba8ae67e4419996e`
- `restartCount=1`
- `windowIndex=2`
- `cumulativeWindowSpanTokens=4104636`

窗口 1：

1. 同样先承接真实 repo-wide 任务。
2. 同样没有 assistant 文本，也没有工具调用。
3. Worker 结果进入 `restarting`，生成 restart snapshot `snap_0e391a5720644d2daeaf`。
4. snapshot 记录显示整窗跨度被压成 1 个 carry-forward package，切到 `windowIndex=2`。

窗口 2：

1. 同样只 rehydrate 了 1 个 context item。
2. 编译 prompt 也是 10 条 messages，最后 1 条是 `runtime_state + task_contract + mounted_context_items + response_requirements + takeover_protocol` 的组合包。
3. 这里同样保留了原始 `task_goal`，但 response requirement 也同样变成“先总结当前局势，再给出最稳妥的下一步”。
4. 没有工具调用，只有 1 轮模型调用。
5. `afterWindowRestart` 的 carry-forward 工作集大小是 `40166` token；真正发给模型的 prompt message 总量约 `2047` token。

---

## 4. 最终完成了什么

从 raw response 看，这次重跑虽然 case 级状态仍是 passed，但两个 case 的最终文本都没有完成原始要求中的“release brief + parity judgment”。

short64k 的最终输出：

1. 先复述“当前局势 / 任务目标 / 约束 / 缺失信息”。
2. 然后给出一个泛化的下一步计划：定位实现面、实施改动、验证行为、结构化交付。
3. 没有给出针对当前仓库的 release brief，也没有给出 short-window vs long-window 是否等价的最终判断。

long128k 的最终输出：

1. 同样先做局势总结。
2. 同样停在“建议先扫描目录、查找 runtime/evaluation/protocol/provider/documentation 文件”的计划阶段。
3. 同样没有交付原始 task goal 要求的最终 parity 结论。

这说明本次重跑真正“完成”的事情，不是完成 release brief，而是：

1. 在两个窗口配置下都成功走完了 `窗口 1 压缩 / 窗口 2 恢复 / 单轮模型调用 / 任务 completed` 的运行闭环。
2. 但恢复后窗口 2 的 prompt contract 已经把模型引导到“恢复态计划回答”，而不是原始任务要求的最终交付态。

---

## 5. 对记忆设计分析的直接价值

这次保留日志的重跑给了三个非常直接的分析点：

1. 问题不只是“能不能跨 4M 级任务重启”，而是“重启后 carry-forward package 是否保住了正确的交付 contract”。
2. 两个 case 都证明窗口 1 没有做模型级推理输出，核心工作只是压缩与 handoff；真正的交付几乎全部压到了窗口 2。
3. 窗口 2 虽然保住了 task goal 文本，但 response requirement 和 takeover plan 明显把输出牵引成了 planning stub，这比单纯的 token 丢失更值得优先排查。

如果后续要继续做更细的分析，建议优先对比：

1. `prompt/compiled/*.json` 中最后 1 条 `runtime_state` 消息。
2. `task_snapshots.pending_actions[].carryForwardSummary` 的内容密度。
3. response 中 `rawResponse.choices[].message.content` 与原始 `task_goal` 的偏离程度。

---

## 6. 更深层问题分析

### 6.1 记忆树为什么没有生效

这次重跑暴露的第一个关键问题是：窗口恢复真正依赖的不是记忆树检索，而是 restart snapshot 生成的临时 carry-forward package。

具体证据链如下：

1. 窗口 1 在 `execution_loop` 里于 LLM 调用前直接进入 restart 分支，因此没有 assistant 文本、没有工具调用，也没有新的 execution note / memory write 可以在窗口 2 被检索回来。
2. 窗口 2 的 `current_context` 不是由记忆树重新检索得到，而是先通过 `_load_snapshot_context(snapshot)` 读取 `snapshot.contextRef`，再可选经过 resume rehydrate hook 修补。
3. `snapshot._build_carry_forward_context()` 并不会保留一棵结构化记忆树，它只读取 `currentContextState[:5]`，把前 5 个 item 压成 1 个 `carry-forward-package`，随后反复 `normalize_excerpt()`，直到内容缩进 restart 预算。
4. `build_root_mount_package()` 虽然仍然挂载了 identity/context/execution roots，但 `compile_runtime_prompt()` 真正写入 prompt 的 `mounted_context_items` 只来自 `current_context`，不会自动把 root mount 内的节点内容展开成新的工作集。

因此，这条路径的真实语义不是“记忆树主体 + 窗口工作集”，而是“snapshot 摘要 handoff + 窗口 2 单轮恢复回答”。

### 6.2 工作树为什么没有生效

第二个问题是：work tree 在 schema 和 prompt 文本里都存在，但没有作为恢复态执行指针真正生效。

具体证据链如下：

1. `snapshot._build_restart_request_state()` 只保留 `currentFocus`、`currentObjective`、`taskObjective`、`activeCapabilities`、`protectedItems` 和 `runtimeMetrics` 等基础字段，不保留 `takeoverProtocol` 或 `workTree`。
2. 窗口 2 恢复时，`execution_loop` 会把 snapshot 里的 `requestState` 合并回 request，但随后又重新调用 `build_task_takeover_protocol()`。也就是说，work tree 不是被恢复，而是被重建。
3. 这次重建使用的输入已经不是原始 repo-wide 工作集，而是缩水到 1 个 item 的 carry-forward package，因此 `takeover` 只能基于摘要重新长出一个泛化计划。
4. `takeover.build_task_takeover_protocol()` 的默认状态是 `currentPhase="plan"`、`status="prepared"`；`_work_tree_from_protocol_parts()` 也只是把 plan step 文本化成 `WorkTreeNode`。这更像计划骨架，不像恢复中的执行树。
5. 由于窗口 1 在 LLM 之前就 restart，运行时没有机会经过 `finalize_task_takeover_protocol()` 和 execution node 写回路径，把真实 delivery/verification 进度固化成可恢复状态。

因此，这次 run 里 work tree 的问题不是“完全不存在”，而是“只作为 prompt 文本存在，没有成为 durable execution state”。

### 6.3 提示词引导为什么不足

第三个问题是：恢复后窗口 2 的 prompt contract 与原始任务交付目标并不一致。

直接证据来自两份保留工件：

1. 两个 case 的窗口 2 compiled prompt 都被编译为 `appId=yggdrasil.app.coding-greenfield`。
2. `promptProfileId` 都是 `yggdrasil.coding-greenfield.main-agent`。
3. `seedTemplateId` 都是 `yggdrasil.seed.coding.new-project`，`scenario=coding.new-project`。
4. `prompting._format_response_requirements()` 在未显式覆盖时会硬编码：
	- 先总结当前局势，再给出最稳妥的下一步。
	- 若证据不足，明确说明缺失信息。
	- 保持 grounded 在当前挂载上下文、工具结果和正式状态上。
	- 默认采用 concise 风格。

这几条指令和原始 suite task goal 的“产出 final release brief，并明确判断 short-window 与 long-window 是否等价”并不对齐。

更关键的是，恢复态 prompt 还额外注入了一份 `takeover_protocol`，而该协议的 `currentPhase/status` 仍停留在 `plan/prepared`。模型收到的高权重局部指令因此变成：

1. 先总结当前局势。
2. 再给最稳妥的下一步。
3. 用 planning-style 的 work tree 来组织回答。

在这种编译结果下，即使 prompt 里仍然保留了原始 `task_goal` 文本，窗口 2 也很容易被引导成 planning stub，而不是最终交付态的 release brief。

### 6.4 为什么之前关于闭合和等价的结论有问题

这次重跑说明，之前的“阶段闭合”结论成立得过早，而且闭合的位置不对。

正确的分层应该是：

1. **技术闭环成立。** 窗口 1 压缩、生成 restart snapshot、窗口 2 恢复、完成单轮模型调用，这条 runtime orchestration 链路确实已经闭合。
2. **交付闭环没有成立。** 原始任务要求的 final release brief 和 parity judgment 没有被交付，两个 case 最终都停在 planning stub。
3. **因此“64k 与 128k 任务效果等价”目前不能成立。** 当前最多只能说：`64k` 与 `128k` 在这条 LongCat 路径上都完成了相同的 restart 技术流程，并且都漂移到了同一种 planning-style 输出。

这类误判是如何产生的，也已经比较清楚：

1. 初版结论主要基于 `pass`、`acceptance_pass_0_1`、`planQualityScore0_100`、`restartSuccessRate0_1` 等 scorecard 指标。
2. 这些指标更接近“调用成功、协议形状完整、计划质量看起来合理”，而不是“原始 task goal 的最终交付完成”。
3. 现有测试也强化了这种偏差：`tests/test_runtime_and_pruning.py` 里的 restart 闭环测试主要断言 `restartCount`、`windowIndex`、`parentRunId` 等结构性结果；`tests/test_prompting_runtime.py` 主要断言 takeover protocol/work tree 被写进 prompt，而不验证它们是否保住了原始交付目标。

因此，之前的闭合本质上是：**runtime shape 闭合了，delivery contract 没有闭合。**

---

## 7. 这些问题是如何产生的

从代码路径看，这不是单点 bug，而是几层实现顺序叠加后共同产生的结果：

1. suite 定义了一条真实的 repo-wide release brief 任务，但没有显式绑定更贴合该任务的 app/profile/response requirement；运行时最终把它归入 `coding-greenfield / coding.new-project` 的默认编译链。
2. repo-wide `currentContext` 太大，窗口 1 还没来得及形成任何任务内推理产物，就先被 hard restart 截断。
3. restart snapshot 的第一版实现优先保证的是“可续跑”和“token 安全”，所以 `carry-forward package` 被设计成单 item 摘要，而不是保真恢复包。
4. 恢复阶段并没有把先前的 takeover/work tree 执行状态原样带回，而是用缩水后的摘要重新生成一份 `plan/prepared` 协议。
5. prompt compiler 又在恢复态无条件叠加“先总结局势，再给下一步”的通用 response requirements，于是模型被进一步拉向规划回答。
6. 评测层的 pass 口径没有把“release brief 已完成、parity judgment 已明确给出”冻结成强验收项，导致一次 technically passed 的 run 被误解为“真实任务 parity 已验证”。

换句话说，这次记录暴露出的不是单个函数的错误，而是当前实现顺序的自然后果：

1. 先补了 restart 可续跑性。
2. 再补了 scorecard 与 stress 指标。
3. 但记忆树主体、work tree continuity、恢复态 prompt contract 和 goal-level acceptance 还没有被一起补齐。

这也是为什么这次重跑的价值非常高：它把“系统能重启”与“系统能在重启后继续交付原任务”这两件事彻底拆开了。

---

## 8. 当前应采用的正确表述

基于这次保留日志重跑，当前最准确的表述应该是：

1. LongCat `64k` / `128k` 的这条 4M 真实任务样本，已经证明 restart 技术闭环成立。
2. 但它没有证明“记忆树为主体”的恢复路径已经生效，也没有证明 work tree continuity 已成立。
3. 它同样没有证明 short-window 与 long-window 在原始任务交付效果上已经等价。
4. 当前真实成立的结论是：恢复态 prompt contract 存在明显 drift，delivery 阶段并未闭合，旧结论需要按“技术闭环成立、交付闭环未证实”重写。
# 工作树真实任务调试基线（2026-05-25）

## 1. 目的

接下来的工作树调试以真实任务为主，不再先从 provider 锁定或纯离线 stub 入手。provider 只在它直接改变工作树判断时才算主问题。

这份基线做三件事：

1. 把“我们设想中的工作树”整理成可判真的目标模型。
2. 把真实任务测试准备成可执行的 suite 入口，而不是口头 checklist。
3. 明确当前实现和测试面还差什么，避免继续拿 release brief/parity 输出替代工作树调试。

## 2. 我们设想中的工作树

### 2.1 基本定位

- 工作树是执行栈和动态工作记忆，不是 takeover plan 的只读投影。
- `WorkContextStack` 是当前窗口里的运行栈，不是另外一套计划对象。
- 长期状态属于工作树/记忆树；上下文窗口以当前工作集为主，但允许保留有限线性 continuation 轨迹，用于父节点编排和缓存命中。

### 2.2 权威执行指针

同一时刻必须有一组一致的执行指针：

- `workTree.currentNodeId`
- `WorkContextStack.topFrameId` 对应的 `nodeId`
- `Working_Node` 标注
- `memoryRetrievalState.workTreeNodeId`

`currentFocus` 只适合作为 UI 摘要，不能替代上述正式执行指针。

### 2.3 正常推进语义

- 子节点开始：push frame，下潜到子节点。
- 子节点完成：必须先写 `executionSummary`，再把摘要写入父 frame 的 `childCompletionSummaries(status=completed)`。
- 子节点完成后必须先回编排父节点；由父节点根据 child 摘要、线性轨迹和剩余节点状态决定是否进入 sibling、继续拆 leaf 或请求外部输入。
- 根节点完成后进入 `awaiting-approval`，不能直接 `completed`。

### 2.4 失败与窗口超限语义

- 叶子失败：必须写 `failureSummary`。
- 非根叶子失败或窗口超限：失败信息先上浮到父节点，形成 `childCompletionSummaries(status=failed)`；下一轮先回父节点，由父节点决定是否进入 sibling、继续拆 leaf、重排局部工作或请求外部输入。
- 根节点失败：整任务可以失败，不再上浮。
- `restart` 只是 legacy/stress 兼容口径，不是默认的父子切换方式。

### 2.5 跨窗口一致性

真实任务多窗口下，至少要检查下面几类对象是否连续：

- 节点指针：`currentNodeId`、`Working_Node`、`topFrameId`
- 检索指针：`memoryRetrievalState.workTreeNodeId`
- 合同指针：`responseRequirementsDigest`、`restartMessageDigest`
- 窗口工件：`window-execution`、`takeoverProtocol`、`workContextStack`

provider 约束需要透传，但它是为了减少续跑漂移，不是这条调试线的主验收对象。

## 3. 按这个设想准备测试

### 3.1 新的真实任务 suite

新增：`evalsuite_g4_real_task_work_tree_debug`

目标：

- 不再让真实任务默认落回 root-only release brief。
- 直接预置一个嵌套 `takeoverProtocol`，让 live case 从 `child-1` 起步。
- 用 short `64k` 和 long `128k` 两条真实任务路径做工作树调试，而不是做 provider matrix。

这套 suite 的要求：

- 输出固定为 7 段工作树调试报告。
- short case 重点确认 `child-1 -> root(父节点编排) -> child-2 -> root` continuation，而不是继续把 legacy restart 数当成主目标。
- long case 作为参考路径，允许单窗口完成，但必须保留工作树一致性检查。
- acceptance 以工作树模型、实际路径、窗口一致性、失败上浮、approval 语义为主。

### 3.2 新增的测试准备点

- `suite_cases_g4.py` 现在增加 `_g4_bind_takeover_protocol()` 和 `_g4_live_provider_matrix_start_payload()`，让 live real-task runner 支持显式 `takeoverProtocol`，并在启动前把 `taskId` 绑定到真实 case task。
- `tests/test_g4_multiscene.py` 新增配置测试，保证新 suite 使用嵌套工作树、strict audit、v0.2 协议锚点和 work-tree debug 输出结构。
- `tests/test_g4_multiscene.py` 新增 contract verifier 测试，锁住工作树 debug 报告的 acceptance 口径。

### 3.3 后续真正要跑的真实任务检查

准备完成后，真实调试应按下面顺序跑：

1. 跑 short `64k` case，确认 `child-1 -> root(父节点编排) -> child-2 -> root` 是否成立。
2. 读取 `window-execution`、`takeoverProtocol`、`workContextStack`，对齐当前节点、top frame、retrieval node pointer。
3. 如果出现 overflow，确认是不是非根叶子失败上浮，而不是整树 root-only fail。
4. 如果根节点交付完成，确认任务停在 `awaiting-approval`。

### 3.4 新增测试任务约定（2026-05-25）

- 默认真实任务测试应尽可能与本项目业务本身弱相关，避免继续把“总结本仓库内部实现”当作默认题面。
- 默认真实任务只给一个目标，不在任务文本里直接给步骤规划或预写 plan。
- 规划必须由 agent 在运行时自己完成；题面只提供目标、边界和必要证据集。
- 明确例外：像 `g4-real-task-work-tree-debug` 这种专门验证 work tree/takeover 语义的 harness，可以继续显式预置 `takeoverProtocol`，但应被视为 runtime debug case，而不是默认真实任务模板。
- 这条约定与后续任务拆分已单独整理到 `docs/development/REAL_TASK_TEST_CONVENTIONS_AND_WORK_TREE_BACKLOG_2026_05_25.md`。

## 4. 当前差距

### 4.1 真实任务入口的差距

- 默认真实任务入口现已明确切到 `g4-real-task-web-research-default`；它承担“单目标、弱项目内生化、由 agent 自主规划”的正式 real-task 合同。
- 旧的 repo-specific 最小工作集口径只保留历史参考，不再作为默认真实任务模板。
- `g4-real-task-work-tree-debug` 已明确标成 `runtime-debug-harness`，继续承接显式 `takeoverProtocol`、child/sibling/root continuation 与 approval 语义调试。

### 4.2 acceptance 口径的差距

- 新 suite 已经把 7 段工作树调试结构、`workTreeContinuity`、父节点编排恢复和 retrieval drift 变成正式门槛。
- 旧的 restart/window-span 硬门槛已经从 work-tree debug suite 里移除，避免把 task continuation 误判成失败。
- approve/revision 控制面链路应并入同一条父节点编排语义：先 `child-1 -> root -> child-2 -> root -> awaiting-approval`，再走 revision 复跑和 approve finalize。

### 4.3 工件分析的差距

- LLM 工作分析器页面已具备工作树调试摘要卡、节点切换时间线、cache trace、child bubble 与 mixed outcome 视图。
- `docs/LLM_WORK_ANALYZER_USER_GUIDE.md` 现已把这些视图整理成固定读法；只有在 coverage 缺失时，才需要回到 `window-execution`、`takeoverProtocol`、`workContextStack` 做人工拼接。

### 4.4 本轮已补齐的闭环

- `task-takeover` 现已把 `delivery.result / evidence / pending / incomplete` 四段都作为正式字段生成；若首次输出缺失 `pending` 或 `incomplete`，runtime 会先排一轮同节点纠偏续跑，明确要求直接补齐正式交付；若纠偏后仍未满足 hard gate，才会落成 `delivery-gate-blocked`。
- `tests/test_runtime_p2_delivery_gate.py` 新增“缺字段阻断交付”与“多节点链路 revision -> 复跑 -> approve”回归，不再依赖孤立的 root-only approve/revision 样本，并额外锁住“误停先补一轮、二次仍缺段才失败”的 delivery gate 纠偏语义。
- 分析器页面已经有专门的工作树调试摘要卡与时间线，用户手册也已补齐相应读法。

### 4.5 已补上的基础缺口

- live runner 已透传显式嵌套 `takeoverProtocol`，真实任务不再默认退化成 root-only。
- 当前运行时仍残留“失败后自动切 sibling”的旧语义；下一轮应先回父节点，再由父节点决定是否进入下一个 sibling。
- `execution_loop_part_b.py` 现在会把 `invoke_runtime_completion()` 的 provider/LLM invocation exception 也按“当前叶子失败”处理；当 `failure_transition.requiresContinuation` 为真时，会先写回 `failed + failureSummary`，再续跑 sibling/parent continuation，而不是直接把整任务打成 failed。
- `execution_loop_part_b.py` 现已恢复 root/single-path 窗口超限的 carry-forward restart snapshot 闭环：若本地 work-tree failure continuation 不可用，不再把 overflow 直接终结成 `failed-window-overflow`，而是排一条带 `resumeToken` 的 restart 续跑工单；非根叶子仍优先沿 failed-leaf bubble/sibling continuation 语义收口。
- `tests/test_runtime_p4_foundation.py` 的下一轮回归目标应切到父节点先接管：真实 provider 异常与窗口超限都先回父节点，再由父节点决定如何继续。
- 新 suite 已接入 `eval:g4:work-tree-debug` 命令，并改成以 work-tree continuity 为主的验收口径。

### 4.6 当前 live 收口状态（2026-05-25 16:00）

- 最新真实 rerun `evalrun_a1259708b3a14b8a96c1` 已完成，`passedCount=2/2`，`passRate=1.0`。
- short `64k` case 与 long `128k` case 都达到 `workTreeContinuity0_1=1`、`officialAcceptancePassed0_1=1`，并通过同一组 parity 指标。
- 两条 live 路径最终都把根节点停在 `awaiting-approval`，说明当前 continuity 基线已可用；下一轮要把这条基线改成 `child-1 -> root -> child-2 -> root` 的父节点编排路径。
- `task-takeover` 的 delivery verifier 现已升格为四段 hard gate，并由定向回归锁住；work-tree live suite 仍以 `awaiting-approval` 为主收口口径，但不再把 delivery verifier 漂移视为独立残余缺口。

## 5. 下一轮优先级

这轮真实任务基线通过后，下一轮应优先做：

1. 把 `evalrun_a1259708b3a14b8a96c1` 固定为当前 live baseline，不再重复追同一条 short/long continuation 证据。
2. 把 child 完成/失败后的默认语义收口为“先回父节点，再由父节点编排下一步”，继续优先使用真实任务而不是离线 stub。
3. 持续固化 live artifact，把 `prefixCacheKey`、有限线性轨迹和 cache hit/write 证据写回基线文档，避免缓存闭环只停留在代码和验收器里。
4. `allowToolExecution=false` 下模型自发 tool call 的残余漂移是否需要在 runtime 层硬拦截，也应与当前 continuity baseline 分开处理。
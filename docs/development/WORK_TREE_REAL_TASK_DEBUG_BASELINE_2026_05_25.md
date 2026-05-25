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
- 长期状态属于工作树/记忆树；上下文窗口只保留当前最小工作集。

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
- 子节点完成后默认续跑 sibling；无 sibling 时 pop 回父节点。
- 根节点完成后进入 `awaiting-approval`，不能直接 `completed`。

### 2.4 失败与窗口超限语义

- 叶子失败：必须写 `failureSummary`。
- 非根叶子失败或窗口超限：失败信息先上浮到父节点，形成 `childCompletionSummaries(status=failed)`；如果父节点还有 sibling continuation，则下一轮直接切到下一个 sibling，否则再回父节点继续。
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
- short case 重点确认 `child-1 -> child-2 -> root` continuation，而不是继续把 legacy restart 数当成主目标。
- long case 作为参考路径，允许单窗口完成，但必须保留工作树一致性检查。
- acceptance 以工作树模型、实际路径、窗口一致性、失败上浮、approval 语义为主。

### 3.2 新增的测试准备点

- `suite_cases_g4.py` 现在增加 `_g4_bind_takeover_protocol()` 和 `_g4_live_provider_matrix_start_payload()`，让 live real-task runner 支持显式 `takeoverProtocol`，并在启动前把 `taskId` 绑定到真实 case task。
- `tests/test_g4_multiscene.py` 新增配置测试，保证新 suite 使用嵌套工作树、strict audit、v0.2 协议锚点和 work-tree debug 输出结构。
- `tests/test_g4_multiscene.py` 新增 contract verifier 测试，锁住工作树 debug 报告的 acceptance 口径。

### 3.3 后续真正要跑的真实任务检查

准备完成后，真实调试应按下面顺序跑：

1. 跑 short `64k` case，确认 `child-1 -> child-2 -> root` 是否成立。
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

- 现有 `g4-real-task-minimal-workset` 更像 release brief/parity 输出测试，不是工作树调试测试。
- 现在已有独立 `g4-real-task-work-tree-debug` suite 和显式 `takeoverProtocol` 透传；剩余问题不在入口，而在运行时语义和工件读法。

### 4.2 acceptance 口径的差距

- 新 suite 已经把 7 段工作树调试结构、`workTreeContinuity`、minimal workset 和 retrieval drift 变成正式门槛。
- 旧的 restart/window-span 硬门槛已经从 work-tree debug suite 里移除，避免把 task continuation 误判成失败。
- 还没有把 approve/revision 的 live 链路接到同一条 real-task work-tree debug 验收里。

### 4.3 工件分析的差距

- LLM 工作分析器已经能看 window/tool/artifact，但还没有一条专门针对工作树调试的固定读法。
- 目前仍需要人工把 `window-execution`、`takeoverProtocol`、`workContextStack` 三层拼起来看。

### 4.4 还没补上的东西

- 还没有端到端 live pytest 去断言 approve/revision 与真实任务 continuation 在同一条链路上闭环。
- 还没有针对 analyzer 页面增加“工作树调试模式”的专门摘要卡。

### 4.5 已补上的基础缺口

- live runner 已透传显式嵌套 `takeoverProtocol`，真实任务不再默认退化成 root-only。
- `fail_current_work_node()` 在存在 sibling 时会直接切到下一个 sibling continuation，不再停在父节点等待外部恢复。
- `execution_loop_part_b.py` 现在会把 `invoke_runtime_completion()` 的 provider/LLM invocation exception 也按“当前叶子失败”处理；当 `failure_transition.requiresContinuation` 为真时，会先写回 `failed + failureSummary`，再续跑 sibling/parent continuation，而不是直接把整任务打成 failed。
- `tests/test_runtime_p4_foundation.py` 已新增 provider exception leaf failure continuation 回归，锁住真实 provider 异常与窗口超限共用同一条 continuation 语义。
- 新 suite 已接入 `eval:g4:work-tree-debug` 命令，并改成以 work-tree continuity 为主的验收口径。

### 4.6 当前 live 收口状态（2026-05-25 16:00）

- 最新真实 rerun `evalrun_a1259708b3a14b8a96c1` 已完成，`passedCount=2/2`，`passRate=1.0`。
- short `64k` case 与 long `128k` case 都达到 `workTreeContinuity0_1=1`、`officialAcceptancePassed0_1=1`，并通过同一组 parity 指标。
- 两条 live 路径最终都把根节点停在 `awaiting-approval`，说明当前 work-tree 调试 suite 的 `child-1 -> child-2 -> root` 收口已经跑通。
- 仍有一条独立残余现象：`task-takeover` 的 delivery verifier 依旧会把 `delivery.evidence / pending / incomplete` 记为 `missing`，`verificationPassRate=0.25`；但这次它没有阻塞官方 suite acceptance，因此应单独处理，不再与 work-tree continuity 回归混在一起。

## 5. 下一轮优先级

这轮真实任务基线通过后，下一轮应优先做：

1. 把 `evalrun_a1259708b3a14b8a96c1` 固定为当前 live baseline，不再重复追同一条 short/long continuation 证据。
2. 转到下一条运行时缺口：叶子节点单点失败语义与缓存支持，继续优先使用真实任务而不是离线 stub。
3. 单独判定 `task-takeover` 的 `delivery.evidence / pending / incomplete` 缺失是否需要升级为正式 hard gate。
4. `allowToolExecution=false` 下模型自发 tool call 的残余漂移是否需要在 runtime 层硬拦截，也应与当前 continuity baseline 分开处理。
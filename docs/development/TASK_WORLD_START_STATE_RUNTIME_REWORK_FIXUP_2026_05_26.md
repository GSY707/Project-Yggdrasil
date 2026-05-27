# 任务文档：世界树 Agent 三阶段拆分返工版（直接发给 code agent）

这份文档不是让你重新设计协议，而是让你把上一轮没有切干净的地方补齐。

你的目标只有一个：

让世界树 agent 真的按“先建世界 / 再醒来 / 再开始工作”运行，而不是表面上多了一个 `TaskRuntimeState`，实际还是沿用旧入口。

## 0. 开始前必须读

按顺序读完再动代码：

1. [docs/specs/world-build-awakening-task-start-protocol-v0.1.md](../specs/world-build-awakening-task-start-protocol-v0.1.md)
2. [docs/development/WORLD_BUILD_INITIAL_AWAKENING_TASK_START_EXECUTION_2026_05_26.md](WORLD_BUILD_INITIAL_AWAKENING_TASK_START_EXECUTION_2026_05_26.md)
3. [docs/development/TASK_WORLD_START_STATE_AND_TASK_RUNTIME_SPLIT_2026_05_26.md](TASK_WORLD_START_STATE_AND_TASK_RUNTIME_SPLIT_2026_05_26.md)

如果没读完这三份文档，不要开始改代码。

## 1. 返工目标

你要让世界树 agent 出现下面这些真实变化：

1. 在“建世界 / 初次苏醒”阶段，世界树 agent 只能看到通用世界，不能提前看到任何任务信息。
2. 只有当“最近一次真实工作现场”存在并且可直接回去时，世界树 agent 才能走无损恢复。
3. 其他恢复情况，一律回到起始状态，再读取任务级工作状态，然后继续工作。
4. `TaskRuntimeState` 要成为任务态唯一真入口。
5. 旧的 request 顶层任务字段、旧的 root mount 顶层任务字段，只能做兼容壳，不能继续主导启动、恢复和 prompt 编译。

## 2. 这次必须修掉的缺口

按严重性排序，必须全部修完：

1. 世界级 root mount 和 boot prompt 还在偷带任务信息。
2. 只要有 `resumeMessage` 或 `restartMessage`，世界树 agent 就会被误判成“正在回到最近工作现场”。
3. `startupMode` 先按旧节点指针算，再把世界级节点字段清空，导致世界树 agent 进入自相矛盾状态。
4. `TaskRuntimeState` 虽然加了，但 prompt、snapshot、continuation、主循环仍然主要沿用旧入口。
5. 当前测试还在保护旧路径，导致旧行为会被继续当成正确结果。

## 3. 硬规则

你必须遵守：

1. 世界级阶段不能看到任务信息。
2. `resumeMessage` 和 `restartMessage` 只是提示，不等于最近一次真实工作现场。
3. 只有真实的最近一次工作现场，才能触发无损恢复。
4. `TaskRuntimeState` 必须成为任务态唯一真入口。
5. 旧 request 顶层 `currentNodeId`、`takeoverProtocol`、`workContextStack` 不能继续做主入口。
6. 旧 root mount 顶层 `taskObjective`、`resumeMessage`、`currentNodeId` 不能继续做 prompt 主入口。
7. 不要只改 prompt 文案，必须改真实数据流。
8. 不要删掉无损恢复；你要做的是把“无损恢复”和“回起始状态再读任务态”分开。
9. 不要把“索引优先”做成“永远只有索引”；进入任务后仍然要能按需展开工具和知识正文。
10. 不要改本任务无关的前端、评测 UI、模块市场、联邦协作逻辑。

## 4. 你要改的文件

先改这些运行时文件：

1. `packages/python-sdk/src/yggdrasil_sdk/contracts.py`
2. `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/root_mount.py`
3. `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop_part_b.py`
4. `packages/python-sdk/src/yggdrasil_sdk/prompting.py`
5. `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py`
6. `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover.py`

再改这些测试：

1. `tests/test_prompting_runtime.py`
2. `tests/test_runtime_p4_foundation.py`
3. `tests/runtime/test_runtime_restart_and_resume.py`

最后同步：

1. `docs/DIRECTORY_REFERENCE.md`

## 5. 按顺序执行，不要跳步

### 步骤 1：先收口合同层

编辑 `contracts.py`。

你要做的事：

1. 明确 `TaskRuntimeState` 是任务态唯一真入口。
2. `RootMountPackage` 只保留世界级内容，不再默认携带任务目标、恢复提示、当前节点这类任务现场信息。
3. 所有“自动回填当前节点”的兼容逻辑，只允许发生在任务态路径，不允许回填到世界级路径。
4. 明确区分这三种 phase：
   - `start-state`
   - `task-state-loaded`
   - `lossless-restore`

不要做的事：

1. 不要再新增另一套并行任务态模型。
2. 不要保留“世界级字段为空，但启动模式仍按旧节点算”的兼容行为。
3. 不要为了兼容省事，继续让 `RootMountPackage` 兼任任务态主入口。

### 步骤 2：收紧世界级 root mount

编辑 `runtime_kernel/root_mount.py`。

你要做的事：

1. `build_root_mount_package()` 只产出世界级 / 起始状态级内容。
2. `[ID: 003 我要干什么]` 只保留：通用工作协议、待机入口、工作状态读取入口。
3. 世界级路径里默认不要输出：
   - `taskObjective`
   - `currentFocus`
   - `resumeMessage`
   - `currentNodeId`
   - `workingNodeAnnotation`
   - `workTree`
4. `startupMode` 不能继续只靠旧 `currentNodeId` 判断。
5. 只有真实最近现场存在时，世界树 agent 才能在这里被标记为可无损恢复。
6. mailbox / side-channel 只能形成“有任务输入要读”，不能直接把世界级状态改成“当前节点已挂载”。
7. 初次苏醒阶段的能力、工具、知识只给索引，不全量给正文。

不要做的事：

1. 不要把 `resumeMessage` 留在世界级摘要里。
2. 不要把 mailbox 唤醒直接翻译成世界级 `currentNodeId`。
3. 不要先算出 `resume-node`，再把节点字段清空。

### 步骤 3：重排主循环启动顺序

编辑 `runtime_kernel/execution_loop_part_b.py`。

你要做的事：

1. 先构建世界级 `root_mount`。
2. 再判断这次是否真的有任务输入。
3. 有任务输入时，再读取或构建 `TaskRuntimeState`。
4. 只有在 `TaskRuntimeState` 建立之后，才同步：
   - `takeoverProtocol`
   - `workContextStack`
   - `currentNodeId`
   - `workingNodeAnnotation`
   - `pcMemo`
5. 只有真实最近现场存在时，才走 `lossless-restore -> resume-node`。
6. 只是带了 `resumeMessage` / `restartMessage` / `currentNodeId`，不能直接判成无损恢复。
7. mailbox 唤醒先转成任务输入，再走任务状态读取。

不要做的事：

1. 不要在主循环一开始就从 request 顶层 `currentNodeId` 判定启动模式。
2. 不要把 `task-state-loaded` 和 `lossless-restore` 合并成同一个意思。
3. 不要继续让旧 request 顶层字段抢在 `TaskRuntimeState` 前面生效。

### 步骤 4：拆 prompt 数据来源

编辑 `prompting.py`。

你要做的事：

1. boot / awakening section 只读世界级 `root_mount`。
2. `scene_recovery`、`currentWorkingNode`、`currentWorkTree`、恢复提示、当前节点这些任务级内容，只能来自 `TaskRuntimeState`。
3. 初次苏醒阶段：
   - 工具只给索引与入口
   - 知识只给索引与入口
4. 任务阶段：
   - 允许按需展开工具正文
   - 允许按需展开知识正文
5. prompt 读取顺序必须改成：`TaskRuntimeState` 优先，旧 root mount 顶层任务字段不再兜底主路径。

不要做的事：

1. 不要只改提示文本。
2. 不要继续从世界级 root mount 兜底 `currentNodeId`。
3. 不要把工具正文永久删光。

### 步骤 5：收紧 takeover 和 snapshot

编辑 `takeover.py` 和 `snapshot.py`。

你要做的事：

1. `sync_takeover_runtime_state()` 只能在 `TaskRuntimeState` 已建立后调用。
2. restart / pause / checkpoint 的 requestState 要明确区分：
   - 真实无损恢复
   - 回起始状态，再读取任务级工作状态
3. continuation payload 不能再绕过 `TaskRuntimeState` 直接塞旧顶层任务指针。
4. snapshot fallback 必须支持“回起始状态 -> 重读任务态”这条路径。
5. `resumeToken`、`restartMessage`、carry-forward package 不能自动等同于“真实最近现场存在”。

不要做的事：

1. 不要删无损恢复。
2. 不要让旧 continuation payload 偷偷绕过新入口。
3. 不要让 snapshot rehydrate 后重新把世界级 root mount 长成任务态主入口。

### 步骤 6：最后改测试

先砍掉保护旧路径的断言，再补保护新路径的断言。

你至少要补或改这些断言：

1. `tests/test_runtime_p4_foundation.py`
   - 世界级 root mount 即使输入了任务目标、恢复提示、当前节点，也不能把这些信息暴露给世界树 agent。
   - `[ID: 003 我要干什么]` 只能保留通用工作协议、待机入口、工作状态读取入口。
   - 世界级 `startupMode` 不能出现“说自己正在恢复当前节点，但当前节点字段为空”的矛盾组合。

2. `tests/test_prompting_runtime.py`
   - 初次苏醒阶段的 boot / world roots / runtime state 不能出现任务目标、当前焦点、恢复提示、当前节点、工作树。
   - 初次苏醒阶段工具和知识只显示索引与入口，不显示完整正文。
   - 只有当 `TaskRuntimeState` 合法存在时，任务级 prompt 才能出现当前节点、工作树、scene recovery。
   - prompt 取任务态数据时，必须优先读 `TaskRuntimeState`，不能继续优先读世界级 root mount 顶层旧字段。

3. `tests/runtime/test_runtime_restart_and_resume.py`
   - start 请求里仅有 `currentNodeId` 或 `resumeMessage` 时，不能直接判成无损恢复。
   - 只有带有真实最近现场的 snapshot / checkpoint / restart 状态时，才允许进入 `resume-node`。
   - 无损恢复失败时，必须回到起始状态，再读取 `TaskRuntimeState`，不能直接失败，也不能回退到旧顶层入口。
   - mailbox 唤醒只能形成任务输入，不能把世界级 root mount 直接变成“当前节点已挂载”的恢复态。
   - 窗口重启 continuation 必须能区分“真实无损恢复”和“起始状态后重读任务态”。

不要做的事：

1. 不要为了让旧测试过而把旧行为留着。
2. 不要只补 happy path，不补误判路径。

## 6. 你必须跑的命令

先分别跑：

```powershell
uv run pytest tests/test_prompting_runtime.py -q
uv run pytest tests/test_runtime_p4_foundation.py -q
uv run pytest tests/runtime/test_runtime_restart_and_resume.py -q
```

再合并跑一次：

```powershell
uv run pytest tests/test_prompting_runtime.py tests/test_runtime_p4_foundation.py tests/runtime/test_runtime_restart_and_resume.py -q
```

如果这三组里面任何一组挂了，就先修这三组，不要扩散范围。

## 7. 完成标准

只有同时满足下面这些条件，任务才算完成：

1. 世界树 agent 在世界级阶段完全看不到任务信息。
2. 只有真实最近一次工作现场，才能让世界树 agent 走无损恢复。
3. `TaskRuntimeState` 已成为任务态唯一真入口。
4. 旧 request 顶层任务字段和旧 root mount 顶层任务字段不再主导启动、恢复、prompt 编译。
5. `start-state`、`task-state-loaded`、`lossless-restore` 三条语义已经分开，不再互相冒充。
6. 初次苏醒只拿索引，进入任务后才按需展开工具与知识正文。
7. 指定三组测试全部通过，而且锁住的是新语义，不是旧兼容壳。
8. `docs/DIRECTORY_REFERENCE.md` 已同步更新。

## 8. 你最容易做错的地方

1. 只改 prompt，不改真实数据流。
2. 只改 `[ID: 003 我要干什么]` 的文案，不改它承载的数据。
3. 把“世界级不能看到任务信息”误解成“任何时候都不能有当前节点”。
4. 把 `resumeMessage` 当成“真实最近现场存在”的证据。
5. 新增了 `TaskRuntimeState`，但 prompt 和 continuation 还是从旧字段取数。
6. 为了图省事，让旧测试继续保护旧路径。

## 9. 失败时怎么汇报

如果你做不完，不要说空话。只允许按下面格式汇报：

### 失败汇报

1. 已完成文件
   - 列出已改文件。
   - 写明每个文件完成到哪一步。

2. 当前卡住步骤
   - 写清楚卡在第几步。
   - 写清楚世界树 agent 现在会卡在什么状态。

3. 卡住位置
   - 写明函数名。
   - 写明测试名。
   - 写明报错摘要。

4. 已确认成立的新行为
   - 只写已经验证通过的行为。

5. 尚未完成文件
   - 列出还没改到的文件。

6. 禁止模糊结论
   - 不要写“差不多了”。
   - 不要写“只剩收尾”。
   - 只能写已完成、未完成、卡住点、下一步。
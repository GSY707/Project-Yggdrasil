# 任务文档：把启动链改成“起始状态 + 任务级工作状态读取”（发给 code agent）

这份文档是发给干活很快但判断力较弱的 code agent 的。不要让它自由发挥，让它严格按顺序做。

## 0. 任务目标

你的目标不是重写整个世界树系统，而是完成这件事：

1. 世界级启动只形成起始状态，不注入当前任务节点。
2. 每次任务开始时，从起始状态出发，再单独读取任务级工作状态。
3. 工具和知识在初次苏醒阶段只加载索引，任务阶段再按需展开正文。

## 1. 开始前必须读的文档

按顺序读：

1. [docs/specs/world-build-awakening-task-start-protocol-v0.1.md](../specs/world-build-awakening-task-start-protocol-v0.1.md)
2. [docs/development/WORLD_BUILD_INITIAL_AWAKENING_TASK_START_EXECUTION_2026_05_26.md](WORLD_BUILD_INITIAL_AWAKENING_TASK_START_EXECUTION_2026_05_26.md)
3. [docs/specs/agent-runtime-protocol-v0.2.md](../specs/agent-runtime-protocol-v0.2.md)

如果没读完这三份文档，不要开始改代码。

## 2. 硬规则

你必须遵守：

1. 不要把当前任务节点放进世界级 `RootMountPackage`。
2. 不要把“初次苏醒不看任务”误解成“任务阶段也不能有当前节点”。
3. 不要只改 prompt 文案，必须改真实数据来源。
4. 不要用一个 `isAwakening` 布尔开关糊住所有阶段差异。
5. 不要删除无损恢复；你要做的是把“无损恢复”和“回起始状态重读任务状态”分开。
6. 不要把工具和知识永远只保留索引；任务阶段仍然要能按需展开正文。
7. 不要改与本任务无关的前端、评测 UI、模块市场、联邦协作逻辑。

## 3. 你要改的文件

先改这些：

1. `packages/python-sdk/src/yggdrasil_sdk/contracts.py`
2. `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/root_mount.py`
3. `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop_part_b.py`
4. `packages/python-sdk/src/yggdrasil_sdk/prompting.py`
5. `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover.py`
6. `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py`

然后改这些测试：

1. `tests/test_prompting_runtime.py`
2. `tests/test_runtime_p4_foundation.py`
3. `tests/runtime/test_runtime_restart_and_resume.py`

## 4. 按顺序执行，不要跳步

### 步骤 1：先补合同

编辑 `contracts.py`。

你要做的事：

1. 新增 `TaskRuntimeState` 模型。
2. `TaskRuntimeState` 至少要有这些字段：
   - `taskId`
   - `phase`
   - `taskObjective`
   - `currentFocus`
   - `currentNodeId`
   - `workingNodeAnnotation`
   - `pcMemo`
   - `resumeMessage`
   - `restartMessage`
   - `takeoverProtocol`
   - `workContextStack`
   - `memoryRetrievalState`
   - `budgetState`
3. 保留 `RootMountPackage`，但让它在世界级路径下默认不携带当前任务节点。
4. 把旧兼容逻辑里“自动回填 currentNodeId”的行为限制到任务级路径。

不要做的事：

1. 不要直接删掉 `RootMountPackage` 里的旧字段。
2. 不要因为兼容麻烦就继续把任务字段偷偷塞回 root mount。

### 步骤 2：收紧根挂载

编辑 `runtime_kernel/root_mount.py`。

你要做的事：

1. `build_root_mount_package()` 只产出世界级 / 起始状态级内容。
2. `[ID: 003 我要干什么]` 的摘要改成：通用工作协议、待机入口、工作状态读取入口。
3. 世界级路径里默认不要输出：
   - `currentNodeId`
   - `workingNodeAnnotation`
   - `currentWorkingNode`
   - `workTree`
4. 新增一个 helper，建议命名为 `build_task_runtime_state()`，专门产出任务级状态。
5. 初次苏醒阶段的能力、工具、知识都只给索引，不全量给正文。

不要做的事：

1. 不要把 mailbox 唤醒直接变成 `currentNodeId`。
2. 不要让 `startupMode` 继续只靠 `currentNodeId` 判断。

### 步骤 3：重排执行顺序

编辑 `runtime_kernel/execution_loop_part_b.py`。

你要做的事：

1. 先构建 `root_mount`。
2. 再判断有没有任务输入。
3. 有任务输入时，再读取或构建 `TaskRuntimeState`。
4. 只有在 `TaskRuntimeState` 已存在后，才同步：
   - `takeoverProtocol`
   - `workContextStack`
   - `currentNodeId`
   - `workingNodeAnnotation`
5. mailbox / side-channel 唤醒先转成任务输入，再走任务状态读取。

不要做的事：

1. 不要在主循环一开始就从 request 顶层取 `currentNodeId` 当启动依据。

### 步骤 4：拆 prompt 编译来源

编辑 `prompting.py`。

你要做的事：

1. boot / awakening section 只读 `root_mount`。
2. `scene_recovery`、`currentWorkTree`、`currentWorkingNode` 这些任务级内容，只能来自 `TaskRuntimeState`。
3. 初次苏醒阶段：
   - 工具只给索引与入口
   - 知识只给索引与入口
4. 任务阶段：
   - 允许按需展开工具正文
   - 允许按需展开知识正文

不要做的事：

1. 不要只改提示文本。
2. 不要把所有工具描述永久删光。

### 步骤 5：收紧 takeover 和 snapshot

编辑 `takeover.py` 和 `snapshot.py`。

你要做的事：

1. `sync_takeover_runtime_state()` 只能在 `TaskRuntimeState` 已建立后调用。
2. continuation request 要区分两种情况：
   - 无损恢复成功
   - 回起始状态，再重读任务状态
3. snapshot fallback 明确支持“回起始状态 -> 重读任务状态”。

不要做的事：

1. 不要删无损恢复。
2. 不要让旧 continuation payload 绕过新入口。

### 步骤 6：最后改测试

编辑测试文件。

你至少要补或改这些断言：

1. `tests/test_prompting_runtime.py`
   - 初次苏醒 prompt 不带当前任务节点
   - 工具和知识只以索引形式出现
   - 任务级 prompt 在 `TaskRuntimeState` 出现后才带当前节点
2. `tests/test_runtime_p4_foundation.py`
   - 世界级 root mount 不带当前任务节点
   - `[ID: 003 我要干什么]` 只保留通用工作协议和入口
3. `tests/runtime/test_runtime_restart_and_resume.py`
   - 无损恢复成功时直接恢复任务级状态
   - 无损恢复失败时回到起始状态，再重读任务状态

## 5. 你必须跑的命令

先跑：

```powershell
uv run pytest tests/test_prompting_runtime.py tests/test_runtime_p4_foundation.py tests/runtime/test_runtime_restart_and_resume.py -q
```

如果你改动过程中把这三组测挂了，就先修这三组，不要扩散范围。

如果这三组通过，再额外跑：

```powershell
uv run pytest tests/test_runtime_p1_hardening.py -q
```

## 6. 完成标准

只有同时满足下面这些条件，任务才算完成：

1. 世界级 root mount 不再默认带当前任务节点。
2. 新任务从起始状态进入，再读取任务级工作状态。
3. prompt 的世界级 section 和任务级 section 已经分开。
4. 初次苏醒阶段是索引优先，不是全文灌入。
5. 任务阶段仍能按需展开工具和知识正文。
6. 无损恢复和回起始状态重读任务状态两条路径都存在。
7. 上面指定的测试全部通过。

## 7. 你最容易做错的地方

1. 只改 prompt，不改真实数据流。
2. 只改 `[ID: 003]` 的文案，不改它承载的数据。
3. 把“初次苏醒不带任务”误解成“任何时候都不能有 currentNodeId”。
4. 忘了 revision / reopen / continuation 这些路径。
5. 把索引优先做成永久只有索引。
6. 为了图省事，用一个布尔开关把所有阶段硬并在一起。

## 8. 失败时怎么汇报

如果你做不完，不要说空话。只允许按下面格式汇报：

1. 已完成哪些文件。
2. 哪一步卡住。
3. 卡住的准确函数名或测试名。
4. 还没改到哪些文件。

不要提交“我觉得差不多了”这种模糊状态。
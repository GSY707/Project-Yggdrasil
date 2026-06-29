# 世界构建、初次苏醒与任务级工作状态读取实施文档（2026-05-26）

- 文档状态：Draft for implementation
- 目标：把 [世界构建、初次苏醒与任务启动协议 v0.1](../specs/world-build-awakening-task-start-protocol-v0.1.md) 翻译成实现层执行计划。
- 关联规格：
  - [Agent 运行时协议 v0.2](../specs/agent-runtime-protocol-v0.2.md)
  - [工作树协议 v0.2](../specs/work-tree-protocol-v0.2.md)
  - [世界构建、初次苏醒与任务启动协议 v0.1](../specs/world-build-awakening-task-start-protocol-v0.1.md)
- 关联旧执行文档：
  - [提示词、启动流程、工作流程重做执行文档（2026-05-23）](WORLD_BUILD_INITIAL_AWAKENING_TASK_START_EXECUTION_2026_05_26.md)

## 0. 本轮实施结论

这轮实现层改造的重点，不是立刻补完整个“世界编译器”，而是先把运行时口径硬拆成两层：

1. 世界级层：建世界、初次苏醒、形成起始状态。
2. 任务级层：从起始状态进入任务、读取工作状态、恢复当前工作树、进入执行。

也就是说，这轮代码改造的核心不是“让 LLM 更会干活”，而是“让 LLM 不再在错误的阶段看到错误的信息”。

## 1. 这一轮要解决什么

当前主链路仍然接近下面这条旧口径：

```text
根挂载
-> 直接计算 currentNodeId / workingNodeAnnotation / startupMode
-> 直接把当前工作树和恢复提示编进 prompt
-> 直接进入执行
```

而新口径要求的是：

```text
世界构建结果
-> 初次苏醒
-> 起始状态
-> 任务开始
-> 读取任务级工作状态
-> 恢复或建立当前工作树
-> 执行
```

实现层要解决的，就是把这两条链真正分开。

## 2. 这一轮不解决什么

为了避免范围失控，这轮明确不做下面这些事：

1. 不实现完整的“代码和文档经 LLM 编译为世界树”的全量世界编译流水线。
2. 不把工作树重新做成硬控制器；工作树语义以“上下文卫生、父节点高层视角、leaf 执行、有用信息与引用回收”为准。
3. 不把所有运行时合同一次性彻底重命名。
4. 不在这一轮里追求 UI、控制面、评测层全部同步完成。

这一轮只做最关键的合同拆分：世界级起始内容和任务级工作状态分层。

## 3. 推荐的过渡实现策略

### 3.1 总体策略

本轮建议采用“过渡拆层”而不是“全量重构”：

1. 保留 `RootMountPackage` 这个对象名，但把它收紧为世界级 / 起始状态级挂载。
2. 新增一个任务级对象，建议命名为 `TaskRuntimeState`。
3. 当前任务指针、恢复指针、工作树、work context stack 不再直接塞进 root mount，而是挂到 `TaskRuntimeState`。

### 3.2 RootMountPackage 的新语义

这一轮之后，`RootMountPackage` 应主要承载：

1. 根指针。
2. 身份、世界、系统宪法。
3. 能力索引。
4. 工具索引。
5. 知识索引。
6. 通用工作协议。
7. 待机入口。
8. 工作状态读取入口。

在世界级 / 起始状态路径里，下列字段应视为默认空值或不生效：

1. `currentNodeId`
2. `workingNodeAnnotation`
3. `currentWorkingNode`
4. `workTree`
5. 任何直接代表当前任务现场的摘要

### 3.3 TaskRuntimeState 的建议字段

建议新增 `TaskRuntimeState`，至少承载：

1. `taskId`
2. `phase`
3. `taskObjective`
4. `currentFocus`
5. `currentNodeId`
6. `workingNodeAnnotation`
7. `pcMemo`
8. `resumeMessage`
9. `restartMessage`
10. `takeoverProtocol`
11. `workContextStack`
12. `memoryRetrievalState`
13. `budgetState`

其中 `phase` 至少要能区分：

1. `start-state`
2. `task-state-loaded`
3. `lossless-restore`

### 3.4 快照与恢复的两条路径

恢复必须明确区分两条路径：

1. 无损恢复成功：直接恢复最近一次 LLM 调用时的任务级状态。
2. 无损恢复失败：回到起始状态，再重新读取任务级工作状态。

不要再把“有 currentNodeId 就等于启动阶段”当成默认逻辑。

## 4. 文件级实施计划

### 4.1 contracts.py

目标：补出世界级状态与任务级状态的正式边界。

必须做：

1. 增加 `TaskRuntimeState` 合同。
2. 让 `RootMountPackage` 在世界级路径下不再默认承载当前任务节点。
3. 把兼容层里“偷偷从旧字段回填 currentNodeId”的逻辑限制到任务级路径。

不要做：

1. 不要一口气删掉所有旧字段。
2. 不要把兼容逻辑全部砍掉。

### 4.2 runtime_kernel/root_mount.py

目标：把根挂载收紧成世界级 / 起始状态级对象。

必须做：

1. `build_root_mount_package()` 不再默认产出当前任务节点。
2. `[ID: 003 我要干什么]` 的摘要改成“通用工作协议 + 待机入口 + 工作状态读取入口”。
3. 能力、工具、知识在初次苏醒阶段采用索引优先。
4. 建议新增 `build_task_runtime_state()` 或等价 helper，专门产出任务级状态。

不要做：

1. 不要在世界级根挂载里保留任务现场。
2. 不要把 mailbox 唤醒直接等价成 `currentNodeId` 已知。

### 4.3 runtime_kernel/execution_loop_part_b.py

目标：把执行顺序改成“先起始状态，再读任务状态”。

必须做：

1. 先构建世界级 `root_mount`。
2. 如果存在任务输入，再单独读取任务级工作状态。
3. 只有在任务级工作状态存在后，才同步 `takeoverProtocol`、`workContextStack`、`currentNodeId`。
4. mailbox / side-channel 唤醒要先转化成任务输入，再走任务状态读取。

不要做：

1. 不要在进入执行循环前就直接从 request 顶层反推出当前节点。

### 4.4 prompting.py

目标：把 prompt 编译分成世界级 section 和任务级 section。

必须做：

1. boot / awakening section 只使用 `RootMountPackage`。
2. `currentWorkTree`、`currentWorkingNode`、`scene_recovery` 的任务级内容只来自 `TaskRuntimeState`。
3. 工具和知识在初次苏醒阶段只提供索引与入口，不全量注入正文。

不要做：

1. 不要只改文案，不改 section 的数据来源。
2. 不要把所有工具正文永远删掉，任务级按需展开仍然要保留。

### 4.5 takeover.py 与 snapshot.py

目标：把任务级恢复从世界级起始阶段里剥离出去。

必须做：

1. `sync_takeover_runtime_state()` 只允许在任务状态读取完成后调用。
2. `build_takeover_continuation_request()` 要区分“无损恢复”与“回起始状态再读任务状态”。
3. snapshot fallback 必须明确支持“回起始状态 -> 重读任务状态”。

不要做：

1. 不要删除无损恢复。
2. 不要让 continuation payload 继续绕过新的任务开始入口。

### 4.6 测试

目标：把旧口径测试收口到新边界上。

必须补的测试重点：

1. 初次苏醒 prompt 只带索引，不带当前任务节点。
2. `RootMountPackage` 在世界级路径下不再携带当前任务节点。
3. 任务开始必须先读取工作状态，再进入当前节点。
4. 恢复分成“无损恢复成功”和“回起始状态重读任务状态”两条路径。

## 5. 实施顺序

建议严格按这个顺序做，不要乱序：

1. 先改合同。
2. 再改 root mount。
3. 再改执行循环阶段顺序。
4. 再改 prompt 编译。
5. 再改 takeover / snapshot。
6. 最后改测试。

如果顺序反过来，最容易出现“表面文案对了，底层行为还是旧口径”。

## 6. 验收标准

实现层至少要满足：

1. 世界级 prompt / root mount 不带具体任务节点。
2. 新任务从起始状态进入，再单独读取工作状态。
3. 工具和知识在初次苏醒阶段只以索引形式出现。
4. 任务阶段可以按需展开工具与知识正文。
5. 无损恢复失败后，能回起始状态，再重读任务状态。
6. 工作树上下文卫生、有用信息与引用回收、安全 / 预算 / 不可逆动作硬边界这些目标不回退。

## 7. 低级错误预警

最容易犯的错误是这几类：

1. 只改 prompt 文案，不改 `root_mount.py` 与 `execution_loop_part_b.py` 的真实顺序。
2. 把 `[ID: 003 我要干什么]` 的说明改了，但仍然把 `currentNodeId` 塞在根挂载里。
3. 误把“初次苏醒不看任务”理解成“任务阶段也不能有 currentNodeId”。
4. 把“索引优先”做成“永远只有索引，没有正文”。
5. 忘记 revision / reopen / approval 这些 continuation 路径。

## 8. 推荐的第一波验收命令

```powershell
uv run pytest tests/test_prompting_runtime.py tests/test_runtime_p4_foundation.py tests/runtime/test_runtime_restart_and_resume.py -q
```

如果这一波还不通过，不要扩大范围去改别的模块，先把运行时主链改通。

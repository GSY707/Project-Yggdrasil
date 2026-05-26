# 世界树 Agent 当前工作逻辑 vs 目标工作逻辑（2026-05-26）

## 1. 这份文档现在固定什么

这份文档现在固定的是世界树 agent 的新目标口径：

1. 父节点是工作推进的强编排者。
2. child 完成或失败后，必须先回编排父节点。
3. 上下文窗口以当前工作集为主，但允许保留有限线性 continuation 轨迹，以换取更稳定的缓存命中和续跑速度。
4. leaf 拆分尽量交给 LLM 决定，代码只提供预算、树深、安全和一致性边界。
5. 根节点完成后统一停在 `awaiting-approval`，不由单轮回答自判结束。

## 2. 世界树 agent 的当前推进方向

世界树 agent 现在已经不是“收到任务 -> 做一次长回复 -> 结束”的单轮模式，而是在向下面这条正式工作链路收口：

```text
任务进入
-> 根挂载启动
-> 进入当前工作节点
-> 按当前节点和父节点编排位置组织上下文
-> 在 child 节点执行
-> child 完成或失败后回编排父节点
-> 父节点决定是否进入 sibling、继续拆 leaf 或请求外部输入
-> 根节点交付后进入 awaiting-approval
```

当前仓库里已经具备工作树、WorkContextStack、节点摘要、awaiting-approval 和失败上浮这些正式对象；本轮要进一步收紧的是：把“自动 sibling continuation”改成“父节点先接管，再由父节点编排下一步”。

## 3. 目标工作逻辑

目标态的世界树 agent，不是代码替它排流程，而是代码把它放进一个有边界的工作环境里：

```text
<standby: 没有活动工作>
-> <root: 建立可执行计划并编排 child>
-> <child-1: 执行局部工作>
-> <root: 收到 child-1 摘要并决定进入 child-2>
-> <child-2: 执行局部工作>
-> <root: 汇总全部 child 结果>
-> <awaiting-approval>
```

这条目标路径会把世界树 agent 变成这样的工作体：

- 启动时先恢复现场，不重新讲系统大背景。
- 执行时当前节点只负责当前局部工作，父节点负责方向、顺序和下一步去向。
- 完成或失败时，child 不自己决定全局下一步，而是把控制权交回父节点。
- 父节点可以决定进入已有 child、继续创建 leaf、继续 sibling、暂停等待或请求外部输入。
- 根节点只在交付完成后停到 `awaiting-approval`。

## 4. 当前实现和目标态的主要差异

当前差异已经很清楚，主要有 4 个：

1. 当前部分路径仍残留“child 做完后自动切 sibling”的旧语义；目标态要求先回父节点，由父节点继续编排。
2. 当前上下文治理更偏“最小工作集”；目标态允许保留有限线性 continuation 轨迹，但只保留父节点编排真正需要的短轨迹。
3. 当前运行时对“进入已有 child”的显式表达还不够强；目标态要求父节点可以明确决定进入哪个已有 child。
4. 当前代码已经在做边界和一致性，但目标态要把这件事说得更清楚：代码负责边界与警戒，不替 LLM 做语义编排。

## 5. 上下文是怎样变化的

这一部分只谈上下文变化，因为这正是世界树 agent 的工作逻辑真正发生变化的地方。

## 5.1 例子一：正常推进链路

```text
<standby: 没有活动工作>
-> <root: 建立可执行计划>
-> <child-1: 检查执行证据>
-> <root: 收到 child-1 摘要并决定进入 child-2>
-> <child-2: 生成正式交付>
-> <root: 汇总交付>
-> <awaiting-approval>
```

### 阶段 A：`<standby: 没有活动工作>`

这时上下文只保留：

- 根指针。
- 启动态信息。
- mailbox / side-channel 状态。
- 当前没有活动 `Working_Node`。

这会让世界树 agent 保持在线但不空转，不会在没有工作时白白消耗一次推理。

### 阶段 B：`<root: 建立可执行计划>`

任务一进入，世界树 agent 的上下文会切到 root：

- `currentNodeId = root`
- `Working_Node = <Working_Node: root>`
- 根任务目标和根节点局部约束
- 与 root 对应的检索结果

这时 root 的职责不是立刻做完任务，而是编排整棵子树：决定先做哪个 child，是否现在就要继续拆 leaf，以及哪些信息必须留给后续 child 复用。

### 阶段 C：`<child-1: 检查执行证据>`

进入 child-1 后，上下文会收缩成：

- root 的必要摘要和当前编排位置
- child-1 的 local goal、expected evidence、局部约束
- 检索指针切到 `memoryRetrievalState.workTreeNodeId = child-1`

此时世界树 agent 的焦点是 child-1 的局部工作，而不是整条任务的所有细节。

### 阶段 D：`<root: 收到 child-1 摘要并决定进入 child-2>`

child-1 完成后，上下文不会直接跳到 child-2，而是先回 root：

- child-1 的原始执行现场被压成 `executionSummary`
- 父帧新增 `childCompletionSummaries`
- 当前上下文保留“child-1 已完成、已清理哪些原始内容、留下了什么摘要”的短轨迹
- 当前节点重新回到 root

这一步对世界树 agent 的改变最大：

- 下一步不再由 runtime 自动替它切 sibling。
- 由 root 自己决定是否进入 child-2、是否改拆 leaf、或是否需要请求额外输入。

### 阶段 E：`<child-2: 生成正式交付>`

如果 root 决定进入 child-2，那么上下文会再次切到 child-2：

- 保留 root 当前编排位置
- 保留 child-1 的摘要和 cleanup 说明
- 当前焦点切到 child-2
- 世界树 agent 只处理 child-2 的局部任务

这会让世界树 agent 能持续复用前缀和摘要，而不是每次都把上一段工作的原始长过程重新灌回窗口。

### 阶段 F：`<root: 汇总交付>`

child-2 完成后，世界树 agent 再回 root：

- root 现在持有 child-1 与 child-2 的摘要
- 当前上下文从“局部执行”切回“全局汇总”
- 世界树 agent 在 root 上决定交付结构是否完整

### 阶段 G：`<awaiting-approval>`

root 完成交付后，任务统一停在 `awaiting-approval`：

- 当前上下文重点变成结果、证据、pending、incomplete 和 revision 入口
- 世界树 agent 停在可审查、可批准、可返修的边界上

## 5.2 例子二：child 失败后，先回父节点再决定怎么继续

```text
<root: 编排>
-> <child-2: 执行>
-> <child-2 failed: 上下文窗口不足>
-> <root: 收到失败摘要并决定是否拆 leaf>
-> <leaf-1 / child-3 / 等待外部输入>
```

在这条链路里，最关键的变化是：

- child-2 失败后，世界树 agent 不应被 runtime 直接切去 sibling。
- 失败摘要必须先回 root。
- root 再决定是继续 sibling、把 child-2 下拆成 leaf-1/leaf-2，还是暂时停下来等待外部输入。

这会把世界树 agent 从“失败后被动续跑”变成“失败后主动重编排”。

## 5.3 例子三：为什么允许保留有限线性轨迹

目标态不要求世界树 agent 每次都只剩一张极干净的树快照。它允许保留有限的线性 continuation 轨迹，例如：

```text
<start>启动内容<root>
我完成了 child-1，并清理了 child-1 的原始上下文
child-1 完成摘要
现在由 root 决定是否进入 child-2
```

这类线性轨迹会直接改变世界树 agent 的工作方式：

- 它更容易保持前缀稳定，从而获得更好的缓存命中。
- 它更容易理解“为什么某些原始内容已经不在窗口里”。
- 它更容易在父节点上连续编排，而不是把每次 continuation 都变成一次重新理解现场。

但这条轨迹必须受约束：

- 保留的是短轨迹、摘要和 cleanup 说明。
- 不是把每个 child 的原始长过程无限叠加。

## 6. 现在最重要的理解

如果只保留 3 条最重要的理解，就是这 3 条：

1. 世界树 agent 的下一步去向，应该由父节点决定，而不是由 runtime 直接替它切 sibling。
2. 世界树 agent 的上下文窗口，应以当前工作集为主，但允许保留有限线性 continuation 轨迹，以换取更稳定的缓存和续跑。
3. 世界树 agent 的根节点完成后，仍然必须停在 `awaiting-approval`，不改这条收口边界。

## 7. 主要依据

- `docs/specs/agent-runtime-protocol-v0.2.md`
- `docs/specs/work-tree-protocol-v0.2.md`
- `docs/development/ROOT_PROMPT_STARTUP_WORKFLOW_REWORK_EXECUTION_2026_05_23.md`
- `docs/development/WORK_TREE_REAL_TASK_DEBUG_BASELINE_2026_05_25.md`
- `docs/new/工作树.md`
- `docs/new/元提示词.md`
- `docs/new/世界树计划正式项目定义.md`

`child-1` 完成后，当前窗口不会原样继承 `child-1` 的全部细节，而是先压成摘要，再切到 `child-2`：

- `child-1` 的原始过程被压成 `executionSummary`。
- 这个摘要挂进父 frame 的 `childCompletionSummaries`。
- 当前活动节点切到 `child-2`。
- 窗口开始围绕 `child-2` 的局部目标重新组织。

这时对世界树 agent 的影响是：

- 它保留的是“上一段工作留下了什么可复用结果”，不是“上一段工作的全过程原文”。
- 这让它能继续干下一个 sibling，而不是被前一个节点的细节拖住。

### 阶段 E：`<root: 汇总交付>`

两个子节点都完成后，窗口再次切换：

- 当前节点回到 root。
- root frame 里已经有 `child-1` 和 `child-2` 的 completion summaries。
- 当前窗口更关注总交付、证据、未完成项，而不是任一叶子的原始细节。

这时对世界树 agent 的影响是：

- 它开始从“执行节点”切到“汇总节点”。
- 它的输出逻辑会从“继续做局部动作”转向“形成正式交付”。

### 阶段 F：`<awaiting-approval>`

根节点完成后，窗口又会发生一次角色切换：

- 当前状态从 active 变成 `awaiting-approval`。
- 上下文重点从执行过程转为交付物、证据、pending、incomplete、revision 入口。

这时对世界树 agent 的影响是：

- 它不再继续盲目前进。
- 它停在可审查、可批准、可返修的边界上。

## 5.2 例子二：叶子失败，但整棵树不停

再看一条当前实现里非常关键的路径：

```text
<root: 汇总目标>
-> <child-1: 检查执行证据>
-> <child-1 failed: 证据阶段失败>
-> <child-2: 继续下一个 sibling>
-> <root: 带失败摘要继续汇总>
```

这条路径的核心不是“失败”，而是“失败后上下文怎么变”。

### `child-1` 失败前

当前窗口主要围绕 `child-1`：

- `Working_Node = child-1`
- 检索指针指向 `child-1`
- 当前工作集是 `child-1` 的证据材料

### `child-1` 失败后

当前实现不会立刻把整任务打死，而是先做三件事：

- 给 `child-1` 写 `failureSummary`
- 把失败摘要写进父 frame 的 `childCompletionSummaries(status=failed)`
- 如果有 sibling，就把当前节点切到 `child-2`

也就是说，窗口会从：

```text
<当前焦点 = child-1 的原始执行现场>
```

切成：

```text
<root 保留 child-1 的失败摘要>
-> <当前焦点切到 child-2>
```

这会直接改变世界树 agent 的工作逻辑：

- 失败信息被保留了。
- 但 agent 不会因此丢掉整条主线。
- 它会带着失败经验继续 sibling continuation。

这正是当前世界树 agent 已经具备的一个非常重要的“长期任务韧性”能力。

## 5.3 例子三：窗口超限后的恢复，不回到任务起点

再看预算或窗口超限时的上下文变化：

```text
<child-2: 生成正式交付>
-> <当前窗口超限>
-> <排入 restart continuation>
-> <新窗口恢复到同一工作节点 child-2>
-> <继续正式交付>
```

在这条路径里，关键不是“重启了”，而是“重启后上下文有没有丢主线”。

### 超限前

当前窗口里有：

- `currentNodeId = child-2`
- `Working_Node = child-2`
- 当前 root/child 摘要
- 当前交付合同和 response requirements

### 超限后排 continuation

系统会把同一条工作树上的恢复信息打包出去：

- 当前节点 ID
- 栈引用 `workContextStackRef`
- 必要的 `resumeMessage` / `restartMessage`
- 同一条交付合同要求

### 新窗口恢复后

目标态要求，新窗口恢复后仍然是：

- 同一个 `currentNodeId`
- 同一个 `Working_Node`
- 同一个检索节点指针
- 同一条交付主线

这会直接改变世界树 agent 的恢复逻辑：

- 它不是“丢了现场以后重新想一遍怎么做”。
- 它是“沿着同一个工作节点继续做没做完的那一步”。

对世界树 agent 来说，这种差别非常大：

- 前者会把每次重启都变成重新规划。
- 后者才是长期任务系统真正需要的 continuation。

## 5.4 例子四：delivery gate 把 planning stub 拉回正式交付

还有一条非常能体现当前工程倾向的路径：

```text
<root: 准备交付>
-> <模型先输出“我先检查一下上下文”>
-> <delivery-gate-retry>
-> <同一工作节点补一轮正式交付>
-> <awaiting-approval 或 blocked>
```

这条路径里，上下文变化的重点不是切节点，而是“同节点下，响应要求被加强”。

第一次输出如果只有过程说明，没有完整的 result / evidence / pending / incomplete，runtime 会：

- 保持当前工作节点不变。
- 把这次误停记成一次 delivery gate retry。
- 往续跑 payload 里追加更强的正式交付要求。

这会直接改变世界树 agent 的交付行为：

- agent 不容易停在“我先说下我的思路”。
- agent 会被系统拉回“现在就按正式交付合同把结果交出来”。

也就是说，当前世界树 agent 的系统环境已经开始主动塑造它的交付习惯。

## 6. 如果把当前世界树 agent 用一句话描述

当前世界树 agent 最准确的描述不是“能处理长上下文的聊天 agent”，而是：

```text
一个以工作树节点为执行焦点、以记忆树保存长期状态、以 WorkContextStack 维持窗口连续性、并以 awaiting-approval 作为正式停点的长期任务 agent。
```

## 7. 如果把设想中的目标态再压一句话

设想中的目标态，是让世界树 agent 进一步变成：

```text
默认不靠整包上下文硬扛，而是默认把长期状态写树、把当前窗口收缩成最小工作集、把 continuation 固定在工作树栈上推进的长期执行体。
```

## 8. 对当前阶段最重要的理解

如果只保留三条最重要的理解，可以记这三条：

1. 世界树 agent 现在已经是“围绕当前工作节点工作”，不是“围绕整条任务一次性作答”。
2. 上下文窗口现在越来越像工作缓存，不再承担长期状态主体；长期状态正在被推回工作树和记忆树。
3. 世界树 agent 的真正完成点已经从“模型说完了”改成“根节点正式交付并等待批准”。

## 9. 主要依据

- `docs/specs/agent-runtime-protocol-v0.2.md`
- `docs/specs/work-tree-protocol-v0.2.md`
- `docs/development/WORK_TREE_REAL_TASK_DEBUG_BASELINE_2026_05_25.md`
- `docs/development/ROOT_PROMPT_STARTUP_WORKFLOW_REWORK_EXECUTION_2026_05_23.md`
- `tests/test_runtime_p4_foundation.py`
- `tests/runtime/test_runtime_restart_and_resume.py`
- `tests/test_runtime_p2_delivery_gate.py`
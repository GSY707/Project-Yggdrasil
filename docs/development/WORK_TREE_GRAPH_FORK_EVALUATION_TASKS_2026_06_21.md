# 工作树图与 Fork 并行测试任务设计（2026-06-21）

- 文档状态：Candidate
- 关联规格：`docs/specs/work-tree-graph-fork-parallel-protocol-v0.1.md`
- 目标：为工作树图 ready-set、Fork 自我分裂并行、延迟信息流传递定义可执行的仿真任务、真实任务和后续批次决策。

## 1. 结论

这项功能不能只靠单元测试验收。它的核心价值是“稳定加速项目进度”，所以测试必须覆盖三件事：

1. 程序是否能正确计算 ready-set。
2. Fork 是否真的继承同一个父上下文锚点并绑定不同 child 焦点。
3. 第 n 批结果是否能正确驱动第 n+1 批自动启动或回父节点编排。

建议测试分四层：

| 层级 | 类型 | 目的 | 是否进 CI |
| --- | --- | --- | --- |
| L0 | reducer / 纯函数仿真 | 锁定 `dependsOn`、`relationIds`、`priority`、pending 信息流索引、Fork 同时运行上限 | 必须 |
| L1 | 同步 Fork 仿真 | 不接 worker，模拟多个 Fork 结果合并、递归 Fork 和下一批 ready-set | 必须 |
| L2 | runtime debug harness | 接 work item / AgentRun / window artifact，但使用可控输入 | slow / nightly |
| L3 | 真实任务 / live 任务 | 验证真实加速、少重复读取、合并质量和成本 | 手动 / nightly，不进默认 PR |

第一版不要直接用 L3 证明一切。先用 L0/L1 把语义锁死，再让 L2 证明 runtime 链路，最后用 L3 判断实际收益。

## 2. 与现有真实任务约定的关系

现有 `REAL_TASK_TEST_CONVENTIONS_AND_WORK_TREE_BACKLOG_2026_05_25.md` 已经区分默认真实任务和 runtime debug harness。工作树图与 Fork 并行测试也必须继续这个边界：

- 默认真实任务：外部化、单目标、不预置完整执行步骤，评估 Agent 自主规划。
- runtime debug harness：可以预置工作树、依赖、关系和验收路径，专门验证 runtime 语义。

本功能第一批任务大多属于 runtime debug harness，因为它们要精确检验 ready-set、Fork 视图、延迟信息流和自动放行策略。后续再补默认真实任务，用于看真实收益。

## 3. 仿真任务定义

### T0：Ready-Set Diamond

目的：验证控制流边和信息流边分离。

图形：

```text
root
  A: 收集输入
  B: 分析输入，dependsOn A
  C: 并行检查，relationIds A，但不 dependsOn A
  D: 汇总，dependsOn B, C
```

预期：

- 初始 ready-set 是 A、C。
- B 不进入 ready-set，因为 A 未完成。
- C 不因为 `relationIds=A` 被阻塞。
- A 完成后，B 进入 ready-set。
- B、C 完成后，D 进入 ready-set。

必须检测：

- `relationIds` 不参与阻塞。
- `priority` 只在同父节点 ready-set 内排序。
- `blockedSet` 原因能解释 B 为什么被阻塞。

### T1：Fork Context Anchor

目的：验证 Fork 不是 Sub-Agent，而是同一父上下文缓存的多视图分裂。

图形：

```text
root
  A: 检查 docs
  B: 检查 runtime
  C: 检查 tests
```

预期：

- A/B/C 同时进入 ready-set。
- 生成同一个 `parentContextAnchor`。
- 生成三个 `runType=fork` 的运行视图。
- 三个 Fork 的 `currentNodeId/topFrameId` 分别指向 A/B/C。
- task 级工作树的全局当前指针不被三个 Fork 互相覆盖。

必须检测：

- 不能创建 subagent task。
- 不能创建 subagent branch。
- 不能把 Fork 记录成 `runType=subagent`。

### T2：Delayed Information Flow

目的：验证“目标 child 尚未创建”时的信息流延迟传递。

图形：

```text
root
  A: 发现资料
  B: 后续实现，尚未展开 B1/B2/B3
```

A 完成后输出：

```text
信息 1：配置入口影响未来实现任务
信息 2：旧测试可能影响未来验收任务
信息 3：文档证据可供未来说明任务引用
```

预期：

- 信息先进入 B 的 `pendingInformationItems`。
- 每条只包含摘要、归类、来源、关系类型、原文/证据引用、状态。
- B 展开为 B1/B2/B3 后，B1/B2/B3 看到摘要和归类。
- B1/B2/B3 自己决定是否读取原文。

必须检测：

- 父节点不保存大段正文。
- pending 信息不强行广播到所有 child prompt。
- consumed / dismissed 状态可更新。

### T3：Auto Batch Pipeline

目的：验证第 n 批结果不改变计划时，可以自动启动第 n+1 批。

图形：

```text
root
  A1/A2/A3: 并行收集
  B1/B2/B3: 对应归一化，分别 dependsOn A1/A2/A3
  C: 汇总，dependsOn B1/B2/B3
```

策略：

```text
autoLaunchPolicy = predeclared-pipeline
```

预期：

- A 批完成且 `planImpact=none` 后，runtime 计算 B 批 ready-set。
- B 批可自动启动。
- B 批完成后 C 可进入 ready-set。
- 如果任何 A 产出 `requires-parent-replan`，B 批不得自动启动。

必须检测：

- ready-set 是程序计算。
- 自动启动是 policy gate 决定。
- 父 Agent 不负责手算 ready-set。

### T4：Parent Replan Gate

目的：验证结果改变任务图时必须回父节点。

场景：

A 完成后发现 B 的任务焦点错误，建议把 B 拆成 Bx/By，并新增 Bx dependsOn A。

预期：

- A 的结果标记 `planImpact=requires-parent-replan`。
- runtime 仍可计算 candidate ready-set，但不能自动启动 B。
- 父 Agent 必须接受或拒绝 proposed dependency / relation change。

必须检测：

- proposed dependency change 不自动改上层图。
- 自动策略被 plan-changing finding 阻断。

### T5：Mixed Fork Outcome

目的：验证同一批 Fork 中一部分完成、一部分阻塞时，父节点如何继续。

图形：

```text
root
  A: 完成
  B: blocked，需要父节点补信息
  C: 完成，但产出 pending 信息给未来 D
```

预期：

- A/C 的摘要和证据合并。
- C 的 pending 信息进入 D 或目标父节点的信息流索引。
- B 的 blocker 进入父节点编排。
- 第 n+1 批不得因为 A/C 完成而绕过 B 的控制流依赖。

必须检测：

- mixed outcome 不等同于整批失败。
- 也不等同于整批自动成功。

### T6：Budget-Limited Fork Batch

目的：验证 Fork 数量受预算和父合并成本限制。

场景：

ready-set 有 8 个 child，但 policy 最大并行数为 3，且必须保留父 Agent 合并预算。

预期：

- 只启动优先级最高的 3 个 Fork。
- 其余 child 保持 pending。
- 第一批回来后重新计算 ready-set。

必须检测：

- `priority` 排序稳定。
- 父合并预算不足时降级串行或缩小批次。

### T7：Recursive Fork Active Limit

目的：验证 Fork 子体可以继续 Fork，但同一任务 / fork tree 内同时运行的 Fork 数受 `maxForks` 限制。

图形：

```text
root
  A: 第一层 Fork child
    A1: 第二层 Fork child
    A2: 第二层 Fork child
  B: 第一层 Fork child
    B1: 第二层候选 child
```

策略：

```text
maxForks = 5
allowRecursiveFork = true
```

执行：

1. root 先 Fork A/B，当前活跃 Fork 数为 2。
2. Fork A 在自己的 child 子图下继续 Fork A1/A2。
3. 因 `maxForks=5`，A1/A2 均可启动，当前活跃 Fork 数为 4。
4. Fork B 再尝试 Fork B1/B2，其中 B1 可启动后活跃数达到 5，B2 必须等待槽位、串行或回父节点请求策略调整。
5. A1 或 B1 完成后，B2 才可作为新 Fork 启动。

预期：

- Fork A 可以继续 Fork A1/A2。
- A1/A2 继承同一个 `forkRootRunId`。
- A1/A2 的 `parentRunId` 指向 Fork A。
- `forkDepth` 从 1 增加到 2。
- Fork B 可以继续 Fork，但只能使用剩余活跃槽位。
- B2 在活跃数达到 `maxForks` 时不得启动为 Fork。
- 活跃槽位释放后，B2 才能启动。

必须检测：

- `maxForks` 是同一个任务 / fork tree 的同时活跃上限，不是累计创建上限。
- 已完成、failed、aborted 的 Fork 不占用活跃槽位。
- running、mounting、waiting-tool 的 Fork 占用活跃槽位。
- 递归 Fork 不能绕过父级预算和父节点合并预算。
- 当 `allowRecursiveFork=false` 时，Fork 子体即使有局部 ready-set，也不得继续 Fork。

## 4. 真实任务 / 仿真真实任务定义

### R1：仓库多区域实现准备审查

类型：repo-scoped runtime harness。

目标：让父 Agent 拆出多个同级 child，分别审查 contracts、runtime reducer、tests、docs 四个区域，Fork 并行读现有代码，最后回父节点形成实现切片。

为什么适合：

- 真实项目任务，但结构可控。
- 四个 child 同构，适合 Fork。
- 每个 child 都会产出对后续实现有用的信息流。

验收：

- 至少 3 个 Fork 使用同一 `parentContextAnchor`。
- 每个 Fork 输出 assigned 区域的摘要和证据引用。
- 重复读取率低于串行 baseline。
- 父节点最终输出实现切片，不是四份独立报告拼接。

### R2：产品发行链路多面审查

类型：repo-scoped runtime harness。

目标：并行审查 release docs、packaging scripts、product smoke、web release page 四条线，判断一个新发行前门禁是否可通过。

为什么适合：

- 多区域并行、信息互相影响。
- 某些发现会传给尚未展开的下游“修复/验证”节点。
- 可以测试 pending 信息流和 parent replan gate。

验收：

- 信息流只以摘要、归类和原文引用挂到下游。
- 当某条线发现硬缺口时，后续自动批次被阻断并回父节点。
- 父节点能决定下一批是修复、补测还是降级为报告。

### R3：外部化资料包对比任务

类型：默认真实任务候选。

目标：给三份外部化资料包，要求 Agent 找出共同风险、差异和优先行动，不预置工作树。

为什么适合：

- 接近真实用户任务。
- 可自然拆成三条并行资料审查。
- 不强行把任务绑定到本仓库内部语义。

需要准备：

- 三份 fixture 文档。
- 统一验收口径：共同风险、差异、证据引用、行动优先级。

验收：

- Agent 自主拆出并行 child。
- Fork 加速但不牺牲一致性。
- 最终结论和长上下文串行 baseline 质量相当。

### R4：多文件迁移计划生成

类型：repo-scoped 真实任务。

目标：让 Agent 基于一个真实设计变更，审查多个模块并生成迁移计划。

为什么适合：

- 接近后续真实开发使用方式。
- 子任务之间存在信息流但不总是控制依赖。
- 可以看 Fork 是否真的减少重复读取。

验收：

- 子任务按模块并行。
- 模块间发现通过 pending 信息流索引传递。
- 父节点最终给出阶段化迁移计划。

## 5. 指标设计

### 5.1 语义正确性指标

- ready-set correctness：ready-set 与预期节点集合一致。
- dependency blocking correctness：未满足 `dependsOn` 的节点不启动。
- relation non-blocking correctness：只有 `relationIds` 的节点不被阻塞。
- fork view isolation：Fork 运行视图 current node 正确，task 级 current node 不被覆盖。
- parent replan correctness：plan-changing finding 必须回父节点。

### 5.2 加速收益指标

- wall-clock speedup：同任务并行耗时相对串行 baseline 的下降。
- duplicate-read reduction：重复读取同一文件/证据的次数下降。
- parent merge cost：父节点合并消耗是否小于并行节省。
- fork overhead ratio：Fork 启动和合并成本占总任务成本比例。

### 5.3 质量指标

- final answer parity：并行结果与串行 baseline 的验收结论一致。
- evidence coverage：最终结论引用的证据覆盖所有关键 child。
- missing-info propagation：缺失信息能传回父节点，而不是被吞掉。
- information routing precision：pending 信息被相关 child 消费，而不是广播污染。

## 6. 后续批次还需要的东西

### Batch 1：合同与仿真测试

需要：

- `WorkTreeRelation` / `pendingInformationItems` 的 contract。
- `runType=fork`。
- ready-set 纯函数。
- 仿真 fixture。

不需要：

- worker 并行。
- live provider。
- Docker。

完成后应能跑 T0-T7 的纯函数和同步仿真测试。

### Batch 2：同步 Fork 运行视图

需要：

- parent context anchor 生成。
- Fork 启动载荷。
- Fork 结果载荷。
- `forkRootRunId`、`forkDepth`、`maxForks`、`activeForkCount`、`availableForkSlots` 计数。
- 同步模拟多个 Fork 结果。

不需要：

- 真正多 worker。
- 真实并发。

完成后应能证明同一父上下文锚点 + 不同 child 焦点成立，并证明递归 Fork 受同一同时运行上限约束。

### Batch 3：runtime work item / worker 集成

需要：

- fork work item activity 名称。
- AgentRun `runType=fork` 持久化。
- queue payload envelope 断言。
- parent merge / ready-set 重算入口。
- 删除旧 sibling continuation 语义测试。

完成后应能跑 L2 runtime debug harness。

### Batch 4：真实任务评测套件

需要：

- R1/R2 的 evaluation suite JSON。
- suite contract verifier。
- LLM 工作分析器补 Fork batch / ready-set / pending 信息流摘要。
- nightly 标记和预算上限。

完成后应能证明真实 repo 任务上的功能链路。

### Batch 5：live 收益评估

需要：

- 串行 baseline。
- 并行 Fork run。
- 质量 parity verifier。
- wall-clock / token / duplicate-read / merge-cost 指标。

完成后才能判断“稳定加速项目进度”是否成立。

## 7. 需要用户决定的事项

当前默认决策已采用本节推荐值。后续如无新约束，按推荐值进入 Batch 1 / Batch 2 设计和实现。

### D1：第一阶段是否只做仿真，不接 worker？

推荐：是。先做 L0/L1，把图语义和 Fork 视图锁住，再接并行 worker。

影响：

- 选“是”：实现风险低，但短期看不到真实加速。
- 选“否”：更快进入 runtime，但容易把 Fork 写成 Sub-Agent 或旧 sibling continuation 的补丁。

### D2：pending 信息流索引用正式字段还是 package-entry？

推荐：正式字段 `pendingInformationItems`，原文用 `originalRef` 指向 package-entry / asset / memory node。

影响：

- 正式字段：语义清楚，测试直接，可能需要 contract 和持久化更新。
- package-entry + `localContextRefs`：实现快，但信息流路由语义弱，后续容易变成“引用包黑箱”。

### D3：Fork 是否同一 task 内运行？

推荐：同一 task 内的 `AgentRun(runType=fork)`，不创建新 task，不创建新 branch。

影响：

- 同一 task：符合自我分裂语义，合并简单。
- 新 task / branch：更像 Sub-Agent，会模糊 Fork 设计目的。

### D4：自动启动默认策略是什么？

推荐：第一版默认 `disabled`；仿真和 harness 中显式打开 `predeclared-pipeline`。

影响：

- 默认 disabled：安全，父节点强编排不会被绕过。
- 默认 predeclared-pipeline：更能展示加速，但需要更强质量门禁。

### D5：旧 sibling continuation 何时删除？

推荐：Batch 3 接入 ready-set 后直接删除旧语义和旧测试，不保留兼容路径。

影响：

- 直接删除：符合当前项目原则，减少路线漂移。
- 暂留兼容：短期更稳，但会让两套调度语义并存。

### D6：真实任务先选 repo-scoped 还是外部化？

推荐：先 R1/R2 repo-scoped harness，再 R3 外部化默认真实任务。

影响：

- repo-scoped：容易验证 runtime 细节，适合开发期。
- 外部化：更接近用户价值，但实现 bug 更难归因。

### D7：第一批 live 预算和模型范围？

推荐：第一批 live 只用一个稳定主模型，预算固定，先不做 provider matrix。

影响：

- 单模型：问题归因清楚。
- 多模型：更接近产品，但会把模型差异和 runtime 功能混在一起。

## 8. 推荐下一步

如果现在开始实现，建议顺序：

1. 先按 T0-T7 写仿真测试和 fixture。
2. 同时补 contracts：`WorkTreeRelation`、`pendingInformationItems`、`runType=fork`。
3. 实现 `compute_parent_ready_set()`。
4. 实现同步 Fork 启动载荷和 parent context anchor。
5. 用 T1/T3/T4/T5/T7 证明 Fork batch、自动放行、父节点重排门禁和递归 Fork 同时运行限制。
6. 再决定是否进入 Batch 3 的 worker 集成。

这条路线能先让协议变成可执行合同，再逐步进入真实并行，避免一开始就把调度、Fork、worker、预算、live 模型全部耦合在一起。

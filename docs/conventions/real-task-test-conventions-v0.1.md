# 真实任务测试出题约定 v0.1

> 生效日期：2026-05-25
> 来源：`docs/development/REAL_TASK_TEST_CONVENTIONS_AND_WORK_TREE_BACKLOG_2026_05_25.md` §2

## 1. 适用范围

本约定适用于 `evaluation/suites/` 目录下所有 `suiteRole = "real-task"` 的评测 suite 及其 case 定义。

不适用于显式标注为 `runtime-debug-harness` 或 `legacy-repo-specific` 的 suite。

## 2. 默认真实任务四条约定

除专门的 runtime/debug harness 外，后续真实任务测试默认遵守下面四条：

### 2.1 项目业务弱相关

测试任务尽可能与本项目业务本身无关。不要把"解释本仓库当前实现""总结本仓库某条内部路线"当作默认真实任务。

**验证标准**：`taskGoal` 不得包含以下任何关键词或短语：
- `Project Yggdrasil`、`世界树`、`世界树计划`
- `本仓库`、`当前仓库`、`this repository`、`current repo`、`this repo`
- `yggdrasil_sdk`、`yggdrasil-sdk`

### 2.2 单目标

任务描述只给一个目标，不在任务文本里内嵌步骤规划、章节顺序、执行顺序或完成路径。

**验证标准**：`taskGoal` 不得包含：
- 分号分隔的多个独立目标
- 编号列表形式的多段目标（如 `1) ... 2) ... 3) ...`）

### 2.3 无内嵌规划

规划必须由 agent 在运行时自己生成，测试合同不应替 agent 提前写好 plan。

**验证标准**：`currentContext` 中的条目不得：
- 规定输出章节的精确顺序（如 `结构必须是: 1)…, 2)…, 3)…`）
- 规定执行步骤的先后顺序（如 `先做…再做…然后…`）
- 提供完整的 section heading 列表

`responseRequirements` 不得：
- 以 `Start with…Then…Finally…` 的形式规定执行路径
- 列出 3 个以上的 required section heading

### 2.4 无额外规划注入

除正式证据集、验收口径和必要边界外，不向任务输入注入额外的"应该先做 A 再做 B"的指令。

**验证标准**：`restartMessage` 不得包含：
- 预先编排好的步骤序列
- 对输出结构的精确重复规定（如完整列举所有 required section heading）

## 3. Suite 分类

每个 suite JSON 文件的顶层必须包含 `suiteRole` 字段，取值为以下之一：

| suiteRole | 含义 | 适用约定 |
|---|---|---|
| `real-task` | 评测 agent 自主规划、最小工作集控制、continuation 和交付质量 | 必须满足 §2 四条约定 |
| `runtime-debug-harness` | 评测 runtime 是否按协议推进节点、切栈、恢复和上浮 | 允许预置工作树、分步协议和内嵌规划 |
| `legacy-repo-specific` | 历史遗留的 repo-specific 任务 | 不作为新 case 的模板；加载时产生 warning |
| `provider-matrix` | Provider 能力对比和 parity 验证 | 不受 §2 约定约束 |
| `regression` | 固定回归 | 不受 §2 约定约束 |
| `benchmark` | 性能和策略基准 | 不受 §2 约定约束 |

### 3.1 当前仓库中的正式映射

- `g4-real-task-web-research-default.json` 是当前默认真实任务入口，用于验证“单目标、外部证据驱动、由 agent 自主规划”的正式合同。
- `g4-real-task-externalized.json` 保留为补充真实任务入口，用于跨题型复核 single-goal / externalized 合同。
- `g4-real-task-work-tree-debug.json` 已明确标注为 `runtime-debug-harness`，专门验证显式 `takeoverProtocol`、child/sibling/root continuation、approval stop 与 work-tree 调试报告结构。

## 4. 明确例外

下面这类 case 可以不遵守 §2 约定，但必须置于 `suiteRole = "runtime-debug-harness"` 的 suite 中，并在 suite 的 `suiteRoleNote` 中说明原因：

- 专门验证 work tree / takeover / pause-resume / sibling continuation / failed-leaf bubble 的 runtime 语义测试。
- 专门验证 provider/tool policy 继承、窗口恢复或 prompt/retrieval 指针一致性的底层调试任务。

原因：这类 case 的目的本来就不是评测 agent 的自然规划能力，而是验证 runtime 是否按协议推进。

## 5. Suite Contract Verifier 行为

`SuiteContractVerifier` 在加载 suite 定义时执行以下检查：

| 检查项 | 匹配条件 | real-task | harness | legacy |
|---|---|---|---|---|
| 多目标检测 | taskGoal 含多个分号分隔或编号目标 | **REJECT** | WARN | WARN |
| 内嵌规划检测 | currentContext 含显式章节顺序 | **REJECT** | PASS | WARN |
| 仓库自指检测 | taskGoal 引用本项目名称或仓库路径 | **REJECT** | PASS | WARN |
| 预置步骤检测 | responseRequirements 含执行路径 | **REJECT** | WARN | WARN |
| suiteRole 缺失 | 顶层无 suiteRole 字段 | **WARN** | **WARN** | **WARN** |

- **REJECT**：验证失败，suite 不满足约定。
- **WARN**：产生警告，不阻断加载。
- **PASS**：不检查此项。

## 6. 完成标准

- 至少有一组真实任务 case 满足：单目标、无内嵌规划、项目业务弱相关。
- 对应 contract verifier 会拒绝多目标、步骤化题面和显式规划 stub。
- 所有 `evaluation/suites/*.json` 都包含 `suiteRole` 字段。
- `runtime-debug-harness` suite 存在且正确标注。

# 任务核对流程审计与对齐（2026-05-27）

## 1. 目标流程（本次冻结）

任务核对流程应采用“先核对、再执行”的三段式：

1. 理解任务：Agent 先复述任务目标、边界、交付标准与已知限制。
2. 形成计划：Agent 给出可执行计划（阶段、顺序、验证点、风险）。
3. 发起核对：Agent 向任务发起者确认“理解是否正确、计划是否同意”，确认后再进入执行。

对应状态语义建议：

- `needs-clarification`：等待发起者确认理解或计划。
- `prepared`：已完成核对，可进入执行。
- `executing`：执行中。
- `awaiting-approval`：交付后等待批准。

## 2. 现有设计对照（文档层）

### 已具备

- `docs/specs/work-tree-protocol-v0.2.md` 与 `docs/specs/agent-runtime-protocol-v0.2.md` 已定义接管阶段与执行门禁：目标解析 -> 约束抽取 -> 计划生成 -> 执行 -> 验证 -> 交付。
- `docs/specs/work-tree-protocol-v0.2.md`、`docs/specs/agent-runtime-protocol-v0.2.md` 与 `docs/development/LLM_WORK_TREE_USAGE_GUIDE_AND_CASES_2026_06_28.md` 已把工作树收口为上下文卫生工具：简单任务直接完成，需要隔离噪声、候选方向、重复项、局部实验或并行工作时才建节点；child 只回传父节点需要的摘要。
- 2026-05 的工作树强编排调试材料已不再作为当前目标口径。

### 缺口

- 设计文档虽然有 `clarificationNeeded` 与 `needs-clarification`，但尚未把“先向发起者核对理解与计划”写成默认必经步骤。
- 现有文档更强调执行阶段与工作树编排，对“执行前核对门禁”的约束不够强。

## 3. 现有实现对照（代码层）

### 已具备

- `modules/task-takeover/src/yggdrasil_task_takeover/plugin.py`
  - 已实现 parse/extract/plan/verify 的结构化接管链。
  - `build_protocol()` 可在存在 required ambiguity 时把状态设为 `needs-clarification`。
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover.py`
  - 已形成 work tree 状态推进与 root `awaiting-approval` 收口。
- `packages/python-sdk/src/yggdrasil_sdk/prompting.py`
  - 已对按需工作树、节点语义、摘要回收和输出结构做提示约束。

### 缺口

- 当前 `parse_objective()` 对歧义的判定偏弱（短目标仅 `required=false`），导致多数任务默认直接进入 `prepared`。
- runtime/prompt 尚未强制“先提交理解+计划给发起者确认，再进入执行”。
- 现有测试主要覆盖交付结构、work-tree 状态与 approval 流程，缺少“先核对再执行”的阻断式回归。

## 4. 对齐建议（按影响分级）

### A. 低风险（先做）

1. 在 prompt 合同中增加显式规则：当 `TaskTakeoverProtocol.status == needs-clarification` 时，只输出“任务理解 + 执行计划 + 核对问题”，不得进入执行性结论。
2. 在 task-takeover 模块补最小判定：当目标缺失验收口径或范围边界时，生成 `required=true` ambiguity。
3. 新增测试：锁住 `needs-clarification` 时的输出和状态门禁语义。

### B. 中风险（随后）

1. 在 execution loop 增加前置门禁：`needs-clarification` 未确认前，不进入执行分支。
2. 在控制面增加“确认理解与计划”动作，动作后协议状态转为 `prepared`。

### C. 高风险（最后）

1. 将“先核对再执行”升级为默认强约束并应用到 live suite，需同步修正评测题面和验收阈值。

## 5. 本次结论

当前项目已经完成“结构化接管 + 工作树执行 + 根节点批准收口”的主链路，但尚未完成“执行前必须核对理解与计划”的强门禁闭环。

本次将目标流程正式冻结为“三段式先核对再执行”，后续实现应按 A -> B -> C 分级推进，避免直接全局硬切换导致 live 回归抖动。

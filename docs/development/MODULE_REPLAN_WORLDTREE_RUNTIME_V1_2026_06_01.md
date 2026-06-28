# 世界树运行时模块重规划 v1（2026-06-01）

## 目标

- 先把世界树 agent 的主语义稳定在清晰模块边界内，再做大规模整理。
- 保证三条核心行为不回退：
  - 工作树只作为上下文卫生与按需隔离工具，不变回硬控制器
  - child 完成后只回传父节点需要的结论、证据、废弃路线、风险和下一步
  - 根节点在需要用户确认、不可逆动作或发布边界时进入 awaiting-approval，再由控制面 approve/revision 收口

## 模块边界（建议目标态）

### 1) runtime_kernel.control_api
- 职责：任务控制面入口（start/resume/retry/pause/approve/revise），统一终态控制。
- 主要文件：
  - packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_control.py
  - packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/root_mount.py
  - packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py
- 约束：不得绕过 awaiting-approval 直接把根任务写成 completed。

### 2) runtime_kernel.execution_orchestrator
- 职责：主执行循环编排（装载 -> 恢复 -> 检索 -> LLM 调用 -> 写回 -> 转移）。
- 主要文件：
  - packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py
  - packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop_worker_entry.py
- 约束：只编排，不吞并 takeover 语义。

### 3) runtime_kernel.takeover_domain
- 职责：世界树核心语义（父子节点推进、work context stack、delivery/revision 生命周期）。
- 主要文件：
  - packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover.py
- 约束：child 完成必须上浮，不允许 child 直接整任务收口。

### 4) runtime_kernel.transition_gate
- 职责：交付门禁与状态转移（formal section 检查、delivery gate retry、awaiting-approval 收口）。
- 主要文件：
  - packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop_transitions.py
- 约束：门禁失败只能走 retry/block 路径，不能静默 completed。

### 5) runtime_kernel.context_runtime
- 职责：记忆检索、窗口指标、memory tag 写入、上下文恢复。
- 主要文件：
  - packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop_context_retrieval.py
  - packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop_metrics_memory_tags.py
  - packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop_state.py
- 约束：仅做上下文与指标，不改交付决策。

### 6) llm_runtime.invoke_gateway
- 职责：prompt 编译后模型调用、预算前后检、工具回合执行。
- 主要文件：
  - packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py
  - packages/python-sdk/src/yggdrasil_sdk/llm_runtime_core.py
  - packages/python-sdk/src/yggdrasil_sdk/llm_runtime_invoke.py
- 约束：不直接写 task 最终状态。

### 7) llm_runtime.artifacts_audit
- 职责：request/response/prompt 工件与审计分层（strict/default/lean）。
- 主要文件：
  - packages/python-sdk/src/yggdrasil_sdk/llm_runtime_tools_and_artifacts.py
  - packages/python-sdk/src/yggdrasil_sdk/llm_runtime_part_a.py
  - packages/python-sdk/src/yggdrasil_sdk/llm_runtime_part_b.py

### 8) evaluation_runtime.suite_platform
- 职责：suite 装载、隔离执行、评分聚合。
- 主要文件：
  - packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/bootstrap.py
  - packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_runner.py
  - packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/scorer.py

### 9) evaluation_runtime.g4_contracts
- 职责：g4 real-task/provider-matrix 合同拼装与验收。
- 主要文件：
  - packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_g4.py
  - packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_contract_verifier.py

### 10) mcp_servers.workspace_tools
- 职责：MCP 工具执行层（read/search/execute/web/paper/python）。
- 主要文件：
  - packages/python-sdk/src/yggdrasil_sdk/mcp_servers/base.py
  - packages/python-sdk/src/yggdrasil_sdk/mcp_servers/execute_server.py
  - packages/python-sdk/src/yggdrasil_sdk/mcp_servers/permission_layer.py
  - packages/python-sdk/src/yggdrasil_sdk/mcp_servers/read_server.py
  - packages/python-sdk/src/yggdrasil_sdk/mcp_servers/search_server.py
  - packages/python-sdk/src/yggdrasil_sdk/mcp_servers/web_server.py
  - packages/python-sdk/src/yggdrasil_sdk/mcp_servers/paper_server.py
- 约束：工具层不承载世界树编排语义。

## 执行顺序（P0/P1/P2）

## P0：先稳语义主链（优先）
- 目标：把父子节点推进与 awaiting-approval 收口锚定在 takeover + transition gate。
- 涉及文件：
  - packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop_worker_entry.py
  - packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop_transitions.py
  - packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover.py
  - packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_control.py
- 对应测试：
  - tests/test_runtime_p2_delivery_gate.py
  - tests/test_runtime_p4_foundation.py
  - tests/test_runtime_p4_stability_hardening.py
  - tests/runtime/test_runtime_restart_and_resume.py
  - tests/runtime/test_runtime_core_and_memory.py

## P1：整理 LLM + MCP 工具链
- 目标：把 llm_runtime 调用链、工件链、工具链分层，减少交叉耦合。
- 涉及文件：
  - packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py
  - packages/python-sdk/src/yggdrasil_sdk/llm_runtime_core.py
  - packages/python-sdk/src/yggdrasil_sdk/llm_runtime_invoke.py
  - packages/python-sdk/src/yggdrasil_sdk/llm_runtime_tools_and_artifacts.py
  - packages/python-sdk/src/yggdrasil_sdk/tool_runtime.py
  - packages/python-sdk/src/yggdrasil_sdk/mcp_servers/*.py
- 对应测试：
  - tests/test_llm_retry_and_safe_shutdown.py
  - tests/test_deepseek_gateway.py
  - tests/test_execute_server.py
  - tests/test_mcp_bridge.py
  - tests/test_mcp_web_paper_retry.py

## P2：整理评测平台与合同层
- 目标：让 evaluation 只验证语义，不反向污染 runtime 行为。
- 涉及文件：
  - packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/bootstrap.py
  - packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_runner.py
  - packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/scorer.py
  - packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_g4.py
  - packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_contract_verifier.py
- 对应测试：
  - tests/test_g4_multiscene__part01.py
  - tests/test_m8_runtime.py
  - tests/test_suite_contract_verifier.py

## 每阶段语义保护清单

1. 父节点编排保护
- 未完成 child 存在时，禁止直接 completed。

2. child 回父节点保护
- child 完成后 currentNodeId 必须回 parent/sibling，不允许停留 child 收尾。

3. awaiting-approval 收口保护
- 根节点交付后先 awaiting-approval；仅 approve 后 completed；revision 可回 active/queued。

## 最小验证清单

1. 静态检查
- pyright：runtime_kernel + llm_runtime + evaluation_runtime + mcp_servers。

2. 关键测试
- P0：delivery gate / foundation / restart-resume。
- P1：llm retry / gateway / execute + mcp bridge。
- P2：g4 multiscene / suite contract verifier。

3. 回归判定（通过条件）
- 不出现“result completed 但 work tree active”的漂移。
- 不出现“child 未回父节点就整任务收口”的捷径路径。

# 大文件扫描与拆分报告（2026-05-17）

## 目标

- 扫描仓库大文件。
- 拆分开发相关大文件，降低单文件维护成本。
- 更新目录与研发文档，保证导航与引用一致。

## 扫描口径

- 全仓扫描后，排除依赖与构建产物（如 node_modules、.next、.venv、.yggdrasil state）。
- 重点关注 docs、packages、services、scripts、tests。

## 本次已完成拆分

### 1) P2 实现规范拆分

原文件：
- docs/research/specifications/P2_IMPLEMENTATION_SPEC_2026_05_17.md

拆分后：
- docs/research/specifications/P2_TASK14_LLM_BUDGET_SPEC_2026_05_17.md
- docs/research/specifications/P2_TASK15_TOOL_ROUND_SPEC_2026_05_17.md
- docs/research/specifications/P2_TASK16_RUNTIME_METRICS_SPEC_2026_05_17.md
- docs/research/specifications/P2_TASK17_SAFE_STOP_SPEC_2026_05_17.md
- docs/research/specifications/P2_IMPLEMENTATION_INTEGRATION_GUIDE_2026_05_17.md

处理方式：
- 原总文档保留为拆分索引，承载导航和维护约定。
- 任务级代码片段、测试断言、集成说明迁移至子文档。

### 2) 运行时测试大文件拆分

原文件：
- tests/test_runtime_and_pruning.py

拆分后：
- tests/runtime/test_runtime_core_and_memory.py
- tests/runtime/test_runtime_restart_and_resume.py
- tests/runtime/test_runtime_budget_and_audit.py
- tests/runtime/test_runtime_pause_regressions.py

处理方式：
- 原文件降级为迁移索引，不再承载测试实现。
- 保持 pytest 发现路径稳定，避免单文件持续膨胀。

### 3) 持久化 API 测试大文件拆分

原文件：
- tests/test_persistence_api.py

拆分后：
- tests/api/test_persistence_task_runtime_api.py
- tests/api/test_persistence_control_plane_api.py
- tests/api/test_persistence_app_scope_api.py

处理方式：
- 原文件降级为迁移索引，不再承载测试实现。
- 按 API 主题拆分为 task/runtime、control-plane、app-scope 三组。

## 验证

- 已执行：`uv run pytest --collect-only tests/runtime -q`
- 收集结果：17 tests collected。
- 结论：拆分后的测试文件可被正常发现，语法与收集路径有效。

- 已执行：`uv run pytest --collect-only tests/api -q`
- 收集结果：10 tests collected。
- 结论：拆分后的 API 测试文件可被正常发现，语法与收集路径有效。

## 相关文档更新

- docs/DIRECTORY_REFERENCE.md
  - 新增 P2 拆分子文档条目。
  - 新增 tests/runtime 子目录条目。
  - 将 tests/test_runtime_and_pruning.py 标注为迁移索引。
- docs/research/README.md
  - 将 P2 规范入口更新为“索引 + 任务子文档”。
  - 修正实现规范与 quick start 导航链接。
- docs/research/specifications/P2_IMPLEMENTATION_CHECKLIST_2026_05_17.md
  - 新增任务级规范与集成指南引用。
- docs/DEVELOPER_GUIDE.md
  - 测试命令切换为 tests/api 与 tests/runtime 子目录。
  - 测试分层表补充拆分后的 API 专题文件。

## 后续建议（非阻塞）

- 对 packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py 与 packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py 做代码级拆分（按预算治理、工具回合、指标、恢复语义分层）。
- 对 packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py 与 packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py 做代码级拆分（按预算治理、工具回合、指标、恢复语义分层）。

# 大文件拆分报告（2026-06-01）

## 目标
- 按“tracked 文件中超过 1000 行必须拆分”的口径治理仓库大文件。
- 保持外部导入路径稳定，不改调用方入口。

## 执行口径
- 扫描范围：`git ls-files`。
- 拆分策略（Python）：原入口文件改为兼容门面，按顺序执行同目录 `__partNN.py` 分片。
- 拆分策略（Suite JSON）：新增 `caseRefs` 分片加载，顶层 suite 只保留元信息与引用。

## 已拆分文件
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py`
- `packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py`
- `packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_g4.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop_part_b.py`
- `packages/python-sdk/src/yggdrasil_sdk/langfuse_trace_layered_analysis.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/takeover.py`
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop_part_a.py`
- `packages/python-sdk/src/yggdrasil_sdk/prompting.py`
- `tests/test_g4_multiscene.py`
- `modules/text-memory/src/yggdrasil_text_memory/plugin.py`
- `packages/python-sdk/src/yggdrasil_sdk/llm_work_analysis.py`
- `packages/python-sdk/src/yggdrasil_sdk/contracts.py`
- `packages/python-sdk/src/yggdrasil_sdk/llm_runtime_part_b.py`
- `adapters/model-providers/src/yggdrasil_model_providers/gateway.py`
- `packages/python-sdk/src/yggdrasil_sdk/llm_runtime_part_a.py`
- `evaluation/suites/g4-real-task-window-parity.json`
- `evaluation/suites/g4-real-task-window-parity-flash.json`

## 运行时兼容改造
- `packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/bootstrap.py`
  - 新增 `caseRefs` 解析：支持从相对路径 JSON 分片合并为内存中的 `cases`。

## 结果
- 当前 tracked 文件中仍超过 1000 行的仅剩：
  - `pnpm-lock.yaml`
  - `uv.lock`

## 例外说明
- `pnpm-lock.yaml` 与 `uv.lock` 是包管理器锁文件，属于工具生成产物。
- 这两类文件无法以“多文件拆分”方式被工具链消费，强行拆分会破坏依赖解析与可复现性。

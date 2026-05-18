# Large File Inventory

统计时间：2026-05-17
统计口径：

- 代码文件：`*.py`, `*.ts`, `*.tsx`, `*.js`, `*.jsx`，行数 >= 400。
- 文档文件：`*.md`，行数 >= 300。
- 排除目录：`.venv/`, `.yggdrasil/`, `node_modules/`, `apps/web/.next/`, `tmp/`, `temp_eval_root/`, `__pycache__/`, `dist/`, `build/`。

## Code Files

| File | Lines | File Type | Module | Split Suggested | Risk | Recommendation |
|---|---:|---|---|---|---|---|
| `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py` | 4 (拆分后) | Python | runtime-kernel | Done | Medium | 入口改为兼容门面，核心实现拆分至 `execution_loop_part_a.py`、`execution_loop_part_b.py`、`execution_loop_transitions.py`。 |
| `packages/python-sdk/src/yggdrasil_sdk/ops_runtime_live.py` | 4 (拆分后) | Python | ops-runtime | Done | Medium | 入口改为兼容门面，核心实现拆分至 `ops_runtime_live_part_a.py`、`ops_runtime_live_part_b.py`。 |
| `packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py` | 4 (拆分后) | Python | llm-runtime | Done | Medium | 入口改为兼容门面，核心实现拆分至 `llm_runtime_part_a.py`、`llm_runtime_part_b.py`。 |
| `tests/test_runtime_and_pruning.py` | 1353 (拆分前) | Python | tests | Done | Medium | 已拆分至 `tests/runtime/` 下 4 个专题文件，原文件保留迁移索引。 |
| `packages/python-sdk/src/yggdrasil_sdk/collaboration_runtime.py` | 4 (拆分后) | Python | collaboration | Done | Medium | 入口改为兼容门面，核心实现拆分至 `collaboration_runtime_part_a.py`、`collaboration_runtime_part_b.py`。 |
| `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop_part_a.py` | 879 | Python | runtime-kernel | No | Medium | execution_loop 拆分后的阶段 A（检索与上下文辅助函数）。 |
| `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop_part_b.py` | 997 | Python | runtime-kernel | No | Medium | execution_loop 拆分后的主循环阶段 B。 |
| `packages/python-sdk/src/yggdrasil_sdk/llm_runtime_part_a.py` | 979 | Python | llm-runtime | No | Medium | llm_runtime 拆分后的预算/工具/工件辅助实现。 |
| `packages/python-sdk/src/yggdrasil_sdk/llm_runtime_part_b.py` | 724 | Python | llm-runtime | No | Medium | llm_runtime 拆分后的调用主流程实现。 |
| `packages/python-sdk/src/yggdrasil_sdk/ops_runtime_live_part_a.py` | 910 | Python | ops-runtime | No | Medium | ops_runtime_live 拆分后的环境准备与验证辅助实现。 |
| `packages/python-sdk/src/yggdrasil_sdk/ops_runtime_live_part_b.py` | 776 | Python | ops-runtime | No | Medium | ops_runtime_live 拆分后的任务序列与汇总实现。 |
| `packages/python-sdk/src/yggdrasil_sdk/collaboration_runtime_part_a.py` | 621 | Python | collaboration | No | Medium | collaboration_runtime 拆分后的上下文/子任务发起实现。 |
| `packages/python-sdk/src/yggdrasil_sdk/collaboration_runtime_part_b.py` | 439 | Python | collaboration | No | Medium | collaboration_runtime 拆分后的 PR 创建/审查与子任务执行实现。 |
| `packages/python-sdk/src/yggdrasil_sdk/persistence/module_platform.py` | 901 | Python | persistence | Yes | Medium | 按 repository/domain query 拆分。 |
| `packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_g4.py` | 879 | Python | evaluation | Yes | High | 按 case 类别拆分，降低单文件认知负担。 |
| `tests/test_persistence_api.py` | 860 (拆分前) | Python | tests | Done | Medium | 已拆分至 `tests/api/` 下 3 个专题文件，原文件保留迁移索引。 |
| `packages/python-sdk/src/yggdrasil_sdk/mcp_bridge.py` | 804 | Python | mcp-bridge | Yes | High | 拆分 transport/session/tool-dispatch。 |
| `adapters/model-providers/src/yggdrasil_model_providers/gateway.py` | 797 | Python | adapters | Yes | Medium | 拆分 provider catalog 与 request mapping。 |
| `packages/python-sdk/src/yggdrasil_sdk/prompting.py` | 778 | Python | prompting | Yes | High | prompt compile 与 profile registry 分层。 |
| `modules/text-memory/src/yggdrasil_text_memory/plugin.py` | 710 | Python | text-memory | Yes | High | 将检索评分、导入构树、edge 构建分模块。 |
| `packages/python-sdk/src/yggdrasil_sdk/persistence/orm.py` | 641 | Python | persistence | Yes | Medium | 模型分域拆分并收敛索引定义。 |
| `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/snapshot.py` | 613 | Python | runtime-kernel | Yes | High | 快照 schema 与存储流程拆分。 |
| `packages/frontend-sdk/src/types.ts` | 597 | TypeScript | frontend-sdk | Yes | Medium | 按页面域拆分类型文件。 |
| `packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/suite_cases_part_b.py` | 579 | Python | evaluation | Recommended | Medium | 按 suite 主题分文件。 |
| `tests/test_phase3_stability_and_scale.py` | 525 | Python | tests | Recommended | Medium | 按稳定性与规模测试拆分。 |
| `packages/python-sdk/src/yggdrasil_sdk/domain.py` | 515 | Python | sdk-domain | Recommended | Medium | 按 aggregate 拆分 domain models。 |
| `packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime/bootstrap.py` | 508 | Python | evaluation | Recommended | Medium | 拆分 CLI bootstrap 与 runtime bootstrap。 |
| `services/core-api/src/yggdrasil_core_api/services/memory_service.py` | 499 | Python | core-api | Recommended | Medium | 将读路径与写路径分离。 |
| `packages/python-sdk/src/yggdrasil_sdk/contracts.py` | 493 | Python | contracts | Recommended | Medium | 按 bounded context 拆分 contracts。 |
| `tests/test_m8_runtime.py` | 483 | Python | tests | Recommended | Medium | 按 case cluster 拆分。 |
| `migrations/versions/553bffc21802_persistence_base.py` | 470 | Python | migrations | No | Medium | 仅在新迁移中避免继续膨胀。 |
| `packages/python-sdk/src/yggdrasil_sdk/ops_runtime_scorecard.py` | 454 | Python | ops-runtime | Recommended | Medium | scorecard parser 与汇总逻辑拆分。 |
| `packages/python-sdk/src/yggdrasil_sdk/persistence/repositories/memory.py` | 441 | Python | persistence | Recommended | Medium | 查询接口按用途拆分。 |

## Documentation Files

| File | Lines | File Type | Module | Split Suggested | Risk | Recommendation |
|---|---:|---|---|---|---|---|
| `docs/DIRECTORY_REFERENCE.md` | 763 (治理前基线) | Markdown | docs | Done | High | 已在本轮重写为导航版，后续保持精简。 |
| `docs/research/归档/prompt-engineering-and-seed-templates-v0.1.md` | 710 | Markdown | docs/research | Yes | Medium | 拆分为背景、模板、案例三个文档。 |
| `文档与项目树整理.md` | 689 | Markdown | task-input | No | Low | 作为任务输入保留，不进入常规导航。 |
| `docs/DEVELOPER_GUIDE.md` | 643 | Markdown | docs | Yes | Medium | 拆分为开发环境、调试、发布三章。 |
| `docs/research/final-goal-roadmap-2026-04-30.md` | 536 | Markdown | docs/research | Yes | Medium | 拆分里程碑与执行记录。 |
| `docs/research/g4-assessment-and-roadmap-2026-05-15.md` | 490 | Markdown | docs/research | Recommended | Medium | 拆分评估结论与后续动作。 |
| `docs/USER_GUIDE.md` | 465 | Markdown | docs | Recommended | Medium | 拆分快速上手与功能参考。 |
| `docs/research/memory-tree-agent-executable-roadmap-2026-05-16.md` | 450 | Markdown | docs/research | Recommended | Medium | 拆分设计原则与实验记录。 |
| `evaluation/fixtures/real-user-validation/task-pack-2026-04-30.md` | 441 | Markdown | evaluation | No | Low | 仅在评测任务维护时阅读。 |
| `docs/PRD-v0.1.md` | 416 | Markdown | docs | Recommended | Medium | 拆分需求全景与约束附录。 |

## Immediate Split Decision

- 本轮已完成开发相关大文件拆分：
	- `docs/research/specifications/P2_IMPLEMENTATION_SPEC_2026_05_17.md` 拆分为任务14/15/16/17与集成验收 5 个子文档。
	- `tests/test_runtime_and_pruning.py` 拆分为 `tests/runtime/` 下 4 个专题测试文件。
- 	- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel/execution_loop.py`、`packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py`、`packages/python-sdk/src/yggdrasil_sdk/ops_runtime_live.py`、`packages/python-sdk/src/yggdrasil_sdk/collaboration_runtime.py` 已拆为兼容门面 + part 实现文件。
- 已完成最小验证：`uv run pytest --collect-only tests/runtime -q` 收集通过。
- 已完成语法校验：`python -m py_compile` 覆盖上述拆分文件通过。

# Module: feature-modules

## Responsibility

`modules/*` 承载插件化能力：文本记忆、上下文剪枝、共享记忆、多模态、关系发现、训练实验、协作子代理、任务接管等。

## Key Files

- `modules/text-memory/src/yggdrasil_text_memory/plugin.py`
- `modules/context-pruning/src/yggdrasil_context_pruning/__init__.py`
- `modules/task-takeover/src/yggdrasil_task_takeover/__init__.py`
- `modules/subagent-pr/src/yggdrasil_subagent_pr/__init__.py`
- `modules/shared-memory/src/yggdrasil_shared_memory/__init__.py`
- 其他模块同结构（`src/<pkg>/__init__.py` + 相关实现文件）

## Entry Points

- 模块 manifest + entry_point（由 module-host / catalog 装配）
- Hook 注册：`register_hooks()` 返回的 hook 列表

## Data Flow

runtime 触发 hook -> 模块读取上下文/持久化 -> 产出工具定义、事件结果或数据变更 -> runtime 汇总并继续执行。

## Important Types / Classes / Functions

- `BaseModulePlugin`
- `HookRegistration`
- hook 名称常量（如 worker activities register）
- `TextMemoryModule`（text-memory 主插件类）
- `_split_source_text`、`_build_edge_candidates`（text-memory 关键处理函数）
- `collect_hook_results`（hook 聚合执行入口）

## Common Change Scenarios

- 增加模块能力：扩展 hook 注册与 handler。
- 增加模块工具：输出 tool descriptors，并补测试。
- 调整记忆逻辑：优先在 text-memory 内局部改动，避免跨模块连锁。

## Tests

- `tests/test_m9_memory_organizer.py`
- `tests/test_m9_multimodal_and_relations.py`
- `tests/test_m9_shared_memory.py`
- `tests/test_m9_pause_resume.py`
- `tests/test_m9_training_lab.py`

## Risks

- hook 契约变化容易造成“无异常但能力失效”。
- 模块启停状态与生命周期状态组合较多，需覆盖启用/禁用场景。

## Related Docs

- `docs/architecture/module-boundaries.md`
- `docs/development/agent-workflow.md`

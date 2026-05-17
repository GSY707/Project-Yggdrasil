# Agent Workflow

## First Files to Read

1. `docs/DIRECTORY_REFERENCE.md`
2. `docs/architecture/overview.md`
3. `docs/architecture/module-boundaries.md`
4. 对应任务的 `docs/modules/*.md`
5. 需要验证时再读 `docs/development/build-and-test.md`

## Search Strategy

- 先按任务类型选目录，再局部搜索。
- 避免在 `tmp/`、`temp_eval_root/`、`.yggdrasil/`、`apps/web/.next/`、`node_modules/` 起步。
- 对动态路由目录（如 `[taskId]`）优先从调用方和路由注册点反查。
- 优先阅读入口文件：`main.py`、`router.py`、`runtime.py`、`registry.py`、`plugin.py`。

## Before Editing

- 确认模块边界和依赖方向。
- 确认入口文件与被调用链路。
- 确认测试位置（`tests/` 与 evaluation suites）。
- 判断是否会触发 `docs/DIRECTORY_REFERENCE.md` 更新条件。

## After Editing

- 更新受影响的导航文档与模块文档。
- 运行最小必要验证（单测、类型检查、构建或评测）。
- 记录是否新增大文件。
- 如果文档过大，按专题拆分而不是继续扩写总览文档。

## Documentation Update Rules

以下情况必须同步文档：

- 新增/删除模块目录。
- 入口文件迁移。
- 公共 contract 或接口字段变化。
- 构建/测试命令变化。
- 新增评测套件或门禁指标。

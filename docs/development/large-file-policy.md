# Large File Policy

## Why This Exists

大文件会放大 Agent 的阅读成本和改动风险，尤其在跨服务、跨模块协作时会显著增加误改概率。

## Thresholds

- 代码文件 > 400 行：需要关注并标记。
- 代码文件 > 800 行：建议规划拆分。
- 代码文件 > 1200 行：必须评估拆分方案与回归验证。
- 文档文件 > 300 行：优先拆出专题子文档。
- 文档文件 > 500 行：必须拆分，保留总览导航。

## Preferred Splitting Strategies

### Source Code

- 按职责拆分（入口调度、领域逻辑、基础工具分离）。
- 将协议/类型定义与执行逻辑分离。
- 将长流程中的独立阶段提取为可测试函数。
- 不以“纯行数目标”做机械拆分。

### Documentation

- `DIRECTORY_REFERENCE.md` 只保留导航与路由，不承载细节百科。
- 详细实现放到 `docs/modules/` 或 `docs/architecture/`。
- 采用稳定相对链接，避免空链与死链。

## Rules

- 拆分前先确认职责边界和调用方向。
- 拆分后必须验证导入路径、路由注册和测试入口。
- 拆分后更新 `docs/DIRECTORY_REFERENCE.md` 与对应专题文档。
- 对高风险大文件先记录 inventory，再决定是否立即重构。

## Current Repo Notes

- 当前最重代码集中在 `packages/python-sdk` 与 `tests/`。
- 当前最重文档集中在 `docs/research/` 与 `docs/DIRECTORY_REFERENCE.md`。
- 本轮导航治理已将总览与专题拆分，避免单文档持续膨胀。

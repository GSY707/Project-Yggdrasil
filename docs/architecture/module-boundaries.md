# Module Boundaries

## Allowed Dependencies

- `apps/web` 可以调用 `services/core-api` 暴露的 HTTP 接口，不直接调用 Python 运行时内部模块。
- `services/core-api` 可以依赖 `packages/python-sdk` 的 contracts、persistence、runtime 能力。
- `services/agent-runtime` 与 `services/worker` 可以依赖 `runtime_kernel`、模块插件与适配器。
- `modules/*` 可以依赖 `yggdrasil_sdk` 提供的 hooks、contracts、persistence API。
- `adapters/*` 可以依赖外部 provider SDK/HTTP，但不应直接实现业务策略。
- `evaluation/*` 可以依赖 `evaluation_runtime` 和正式 contracts，不应直接绕过合同层。

## Disallowed Dependencies

- 基础 SDK（`packages/python-sdk` 的通用层）不应依赖 `apps/web`。
- `adapters/*` 不应依赖 `applications/*` 场景配置实现业务分支。
- `modules/*` 不应直接 import Web 前端或 Next.js 代码。
- `tests/*` 辅助逻辑不应被生产服务 import。
- `docs/`、`evaluation/fixtures/` 不应作为运行时代码输入来源（除评测显式读取路径）。

## Boundary Rules for Future Agents

- 跨模块改动前先确认调用方向，不满足方向约束时先调整设计再改代码。
- 修改公共 contracts 时，必须联动检查 core-api、runtime、worker、web 的消费侧。
- 修改模块 hook 名称或载荷结构时，必须联动检查注册方和调用方。
- 修改应用清单（`applications/*/yggdrasil.app.yaml`）时，必须核对依赖模块是否可加载。

## Change Checklist

- 是否引入了反向依赖？
- 是否破坏了现有 API/contract 字段？
- 是否需要补回归测试（至少一个正向 + 一个失败路径）？
- 是否需要更新目录导航文档与模块文档？

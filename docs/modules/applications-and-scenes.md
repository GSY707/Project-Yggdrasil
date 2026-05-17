# Module: applications-and-scenes

## Responsibility

`applications/*` 定义场景应用插件：模块依赖、prompt profile、seed template、场景配置与前端入口声明。

## Key Files

- `applications/base-template/yggdrasil.app.yaml`
- `applications/*/yggdrasil.app.yaml`
- `applications/*/prompt-profiles/`
- `applications/*/scenes/`
- `applications/*/few-shots/`

## Entry Points

- 应用清单读取入口：module-host / app catalog。
- 默认兜底应用：`applications/base-template/yggdrasil.app.yaml`（`defaultLoad: true`）。

## Data Flow

应用清单 -> runtime 选择 prompt profile/seed -> 模块能力注入 -> 场景执行。

## Important Types / Classes / Functions

- Application manifest 关键字段：`apiVersion`、`kind`、`metadata.id`、`spec`
- `spec.prompting.defaultPromptProfileId` / `subagentPromptProfileId`
- `spec.dependencies.modules`（模块依赖清单）
- `spec.frontend.entryRoute`、`spec.frontend.dashboardRef`

## Common Change Scenarios

- 新增场景：复制模板并调整 `id`、`dependencies`、`prompting`。
- 调整默认 prompt：修改 `defaultPromptProfileId` 与 profile 文件。
- 调整前端入口：更新 `spec.frontend.entryRoute`。

## Tests

- `tests/test_g4_multiscene.py`
- `tests/test_m9_acceptance.py`
- `corepack pnpm eval:g4:multiscene`

## Risks

- app manifest 字段错误会导致应用加载失败。
- 模块依赖声明与实际可安装模块不一致会导致运行期降级。

## Related Docs

- `docs/architecture/module-boundaries.md`
- `docs/development/build-and-test.md`

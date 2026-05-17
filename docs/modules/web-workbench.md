# Module: web-workbench

## Responsibility

`apps/web` 提供统一工作台 UI，展示任务、记忆、协作、评测、观测等控制面页面。

## Key Files

- `apps/web/app/layout.tsx`：全局布局与侧边导航。
- `apps/web/app/page.tsx`：首页入口。
- `apps/web/app/components/`：核心页面组件。
- `apps/web/app/api/core/`：转发到 Core API 的代理路由。
- `apps/web/package.json`：前端脚本入口。

## Entry Points

- Next.js App Router 页面入口。
- `corepack pnpm web:dev` 本地开发入口。

## Data Flow

用户交互 -> 页面组件 -> API 代理路由 -> Core API -> 返回 JSON -> 前端渲染。

## Important Types / Classes / Functions

- `RootLayout`（`app/layout.tsx`）
- `HomePage`（`app/page.tsx`）
- `OverviewPage`、`SidebarNav`（导航与首页核心组件）
- `packages/frontend-sdk/src/types.ts` 的共享类型定义

## Common Change Scenarios

- 新增页面：在 `app/` 下新建路由和组件。
- 修改导航：调整 `layout.tsx` 与 sidebar 组件。
- 修改数据展示：先确认 Core API 字段再改前端类型。

## Tests

- `corepack pnpm web:lint`
- `corepack pnpm web:typecheck`
- `corepack pnpm web:build`

## Risks

- 与 Core API 字段不一致会导致页面空白或运行时错误。
- 动态路由目录（`[taskId]` 等）改动需要同步链接生成逻辑。

## Related Docs

- `docs/development/build-and-test.md`
- `docs/architecture/overview.md`

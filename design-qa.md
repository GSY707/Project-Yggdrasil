# Stitch 设计工程验收

本轮验收的核心判断是：普通用户界面已经从旧的浅色产品壳直接切换到 Stitch 的 Roots & Circuitry 工作台结构；Help & Diagnostics 使用同一份 Stitch 源页面做了同视口对照；中英文是同一套界面状态的语言切换，不是两套分叉设计。

## 真源与验收范围

- Stitch 项目：`6603619266131280055`（Project Yggdrasil Design System）。
- 已接受的源页面包：`docs/development/stitch-design-captures-2026-06-17/post-rework-v10-passline/`。
- 生成源页面清单：`docs/development/stitch-generated-sources-2026-07-11/README.md`。
- 本轮 Help & Diagnostics 源页面：`86b1a666db2a48b3a0c76c10066eb033`；源 HTML 镜像与截图由清单记录，未凭审美重新设计。
- 实现入口：`apps/web/app/components/release-page.tsx` 与 `apps/web/app/components/app-shell.tsx`。
- 实现地址：生产构建 `http://localhost:3101/release`；源码级路由仍为 `/release`。

验收覆盖 Web 的主导航、任务、应用、材料、数据治理、设置、Help & Diagnostics 以及维护者工作台页面，同时覆盖 Windows Launcher/Tray 的中英文入口。后续新增语言只需扩展 `apps/web/app/i18n.ts`，不会复制页面组件。

## 同视口视觉证据

Help & Diagnostics 使用逻辑视口 `1280 × 1104`，源图、英文产物和中文产物均来自同一视口。浏览器因滚动条产生的实际内容宽度差异属于渲染环境差异，不是布局参数差异。

- Stitch 源：`docs/release/stitch-ui-implementation-2026-07-11/help-diagnostics/source-1280x1104.png`
- 生产英文：`docs/release/stitch-ui-implementation-2026-07-11/help-diagnostics/production-en-1280x1104.png`
- 生产中文：`docs/release/stitch-ui-implementation-2026-07-11/help-diagnostics/production-zh-1280x1104.png`

对照结果：固定窄侧栏、顶栏、命令搜索、四张健康卡、Action Required、Maintenance、Recent Activity 与原始维护者日志的区域顺序、密度、边框、状态色和对齐方式与 Stitch 源一致；中英文只改变文案和日期格式，不改变结构。`Settings` 的激活态按 Stitch 源截图保留，即使当前路径是 `/release`，以避免把源页面静态意图改成另一套导航审美。

## 迭代与剩余风险

### P0/P1：已关闭

旧版米白背景、深绿宽侧栏、衬线大标题、宽松卡片和发布矩阵已删除；全局 token、侧栏宽度、图标、卡片边框、控件、状态色和内容密度均按 Stitch 结构重置。生产构建后的主路由与高级路由均完成烟测，未出现 `Application error`、错误页或中英文缺失文案。

### P2：资产回退已记录

Stitch Help 源页面使用远程 logo/headshot 位图；仓库没有可复用的同源资产，远程图片也不适合作为产品运行时依赖。因此实现使用本地 Material 图标与 `SA` 头像缩写作为资产回退，布局、尺寸、颜色和层级仍按源页面执行。这是唯一明确的像素级资产差异；若后续提供仓库自有 logo/avatar，可只替换资产，不改页面结构。

Stitch 对 Data & Privacy 与 Maintainer Workbench 的新生成请求未返回有效页面，失败请求没有盲目重试；这两类页面沿用已接受的源包和当前真实产品数据，并已在生成源清单中留痕。

## 验证结果

- `corepack pnpm --filter @yggdrasil/web typecheck`：通过。
- `corepack pnpm --filter @yggdrasil/web build`：通过，17 条 Web 路由生成，包含 `/release`。
- 中英文词典：551/551 key 对齐；直接 JSX 用户文案扫描仅剩品牌名和技术名。
- 生产环境语言切换：`zh-CN`/`en`、`<html lang>`、按钮选中态、状态卡、日志和日期格式均已验证；18 条 Web 路由在英文和中文状态各完成一次生产烟测。
- 空数据/后端暂不可用时，数据治理、MCP、节点详情、观测和任务分析页面进入有语义的 Loading/Empty/ErrorState，不再因接口返回不完整对象而抛出客户端异常。
- Windows PowerShell：Launcher/Tray UTF-8、语言持久化、解析与不可见 WinForms 检查通过。
- 真实本地数据库没有被本轮 QA 改写；生产视觉烟测使用隔离的健康接口 fixture，避免把既有 schema 漂移误报成 UI 缺陷。

final result: passed

# 产品发行完成度评估（2026-06-18）

## 1. 结论

当前产品发行完成度综合判断为 **55/100**。拆开看，“本地可试用发行”口径为 **72/100**，“普通用户正式发行”口径为 **48/100**，“托管 / SaaS 商业发行”口径为 **18/100**。

一句话判断：**项目已经具备本地产品预览发行能力，不再只是源码开发态；但还没有达到正式签名安装、稳定升级渠道、远端服务和商业支持的发行标准。**

| 发行层级 | 完成度 | 当前判断 |
| --- | ---: | --- |
| 开发者工作区 | 82/100 | `uv sync`、`pnpm install`、`yggdrasil:up`、Web 工作台、回归脚本和 release-check 都存在，适合贡献者和高配合试用。 |
| 本地产品模式 | 72/100 | 推荐试用路径已形成：Web-first 入口、provider gate、本地日志、备份恢复、数据治理入口都有现实实现；仍依赖源码工作区和本机依赖。 |
| Docker Compose 产品栈 | 68/100 | 完整产品 compose、镜像构建、健康检查、product smoke、备份、恢复、快照、升级、回滚已进入预览可验证；仍缺多版本正式演练、镜像发布 tag 和故障 runbook。 |
| Windows 桌面封装 | 55/100 | 未签名安装器、托盘、快捷方式、状态、日志、备份、恢复、更新检查、手动应用、升级、回滚已存在；仍不是签名安装包，也不是完整桌面壳。 |
| 数据治理发行边界 | 60/100 | Web `/data-governance` 已有资产清单、备份、删除预览、受保护 task 删除、删除证明和审计；asset / node 硬删除、日志/备份清理和远端删除未完成。 |
| 托管 / SaaS | 18/100 | 只有需求和契约草案；没有账号、租户、远端工作区、SLA、隐私条款、服务状态页或生产运维体系。 |
| 官方远端数据服务 | 20/100 | 契约草案已冻结本地优先和显式同步边界；远端托管、远端备份、远端恢复、远端删除状态机均未实现。 |

## 2. 本次核验范围

本次评估基于当前仓库静态证据和低成本命令验证：

- `package.json`
- `README.md`
- `docs/USER_GUIDE.md`
- `docs/DEVELOPER_GUIDE.md`
- `docs/development/PRODUCT_PACKAGING_AND_REMOTE_DATA_REQUIREMENTS_GAP_2026_06_04.md`
- `docs/development/INSTALL_LAUNCHER_AND_APP_PACKAGE_DISTRIBUTION_2026_06_06.md`
- `apps/web/app/components/release-page.tsx`
- `infra/docker-compose.product.yml`
- `infra/product.env.template`
- `scripts/product-compose.mjs`
- `packages/python-sdk/src/yggdrasil_sdk/ops_runtime/compose.py`
- `packaging/desktop/windows/`
- `.github/workflows/release-check.yml`

未执行完整 Docker cold start、真实多版本升级、真实外部 provider 任务和破坏性本地数据删除。本轮结论不能替代正式发布前验收。

## 3. 已完成任务

### 3.1 发行入口已经从源码态扩展到产品态

已完成：

- 根脚本提供 `corepack pnpm yggdrasil:up`，作为本地产品一键启动入口。
- 根脚本提供 `corepack pnpm product:*`，覆盖产品 compose 配置、启动、停止、状态、日志、备份、恢复、快照、升级、回滚。
- `/release` 页面、README 和用户指南明确区分开发者工作区、本地产品模式、完整 Docker Compose 产品栈、桌面封装、托管 / SaaS 和官方远端数据服务。
- Web 首屏和任务启动面板通过 provider 状态阻止无 key 或 fallback 测试模式下直接启动真实任务。

未完成：

- 本地产品模式仍要求用户在源码工作区内准备 `uv`、`pnpm`、Docker 和 `.env`。
- 没有普通用户级安装向导、离线依赖包或一键诊断修复器。

### 3.2 完整 Docker Compose 产品栈已达到预览发行

已完成：

- `infra/docker-compose.product.yml` 包含 PostgreSQL、Redis、NATS、MinIO、Temporal、Jaeger、OTel Collector、migrate、Core API、Agent Runtime、Module Host、Worker 和 Web。
- 产品栈使用独立 volume：`postgres-data`、`minio-data`、`yggdrasil-state`、`yggdrasil-backups`。
- Python 服务和 Web 服务均有产品 Dockerfile 与 `project-yggdrasil/*:${YGGDRASIL_IMAGE_TAG:-local}` 镜像名。
- `scripts/product-compose.mjs` 会优先读取未跟踪的 `infra/product.env`，不存在时回退 `infra/product.env.template`。
- `packages/python-sdk/src/yggdrasil_sdk/ops_runtime/compose.py` 的 product smoke 已同步优先读取 `infra/product.env`，避免端口覆盖后误判。
- `tests/test_product_compose_smoke_config.py` 锁定了 product env 优先级。

未完成：

- `YGGDRASIL_IMAGE_TAG` 仍默认 `local`，没有正式版本 tag、镜像仓库、发布签名或镜像 SBOM。
- 产品栈升级和回滚已有命令，但还缺跨版本矩阵、迁移失败注入、断电中断恢复和冷启动恢复演练报告。
- release-check CI 还没有把完整产品 compose cold start、product smoke、backup/restore/upgrade/rollback 纳入正式门禁。

### 3.3 Windows 桌面封装已达到未签名预览

已完成：

- `packaging/desktop/windows/` 提供未签名安装、卸载、托盘、启动、停止、状态、日志、备份、恢复、快照、升级、回滚、更新检查、手动应用更新和快捷方式入口。
- 维护动作有影响预览、手动确认、状态文件和失败恢复说明。
- 卸载默认保留本地数据；删除本地状态需要显式危险确认。
- `Build-Yggdrasil.DesktopPackage.ps1` 可构建 `dist/desktop/yggdrasil-desktop-preview.zip`。

未完成：

- ZIP 当前是预览包，不是签名安装器。
- 没有 SmartScreen 信誉、正式发布渠道、发布页下载流、自动更新信任链或静默后台更新。
- 安装器仍依赖可定位的 repo checkout，未形成“完整发行包 + 应用包 + 运行时依赖”的独立安装产物。
- 没有 Electron / Tauri / 原生桌面壳最终选型；当前是薄 PowerShell 托盘控制器。

### 3.4 数据治理具备本地保护性执行闭环

已完成：

- 数据资产 manifest、删除预览、审计表、API 和 Web `/data-governance` 已存在。
- Web 支持备份快照列表、创建备份、精确确认 task 硬删除、删除证明和审计记录展示。
- 外部 provider、Langfuse、OTel、旧备份等边界在发布页和数据治理规格中被明确说明。

未完成：

- `asset` / `node` 仍只开放预览，没有硬删除执行。
- 日志清理、旧备份清理、全量本地重置和恢复后过滤策略未冻结。
- 本地删除证明还不是机器可验证证明。
- 远端删除请求、远端删除状态查询和远端删除证明未实现。

### 3.5 发布检查链路有基础，但不是正式 release gate

已完成：

- `.github/workflows/release-check.yml` 包含 migration check、compose smoke、full offline regression、PostgreSQL regression、可选 live provider smoke、可选 G4 provider matrix。
- 根脚本 `release:check` 覆盖 Python syntax、pytest、评测回归、Web lint/typecheck/build。
- 本次低成本验证通过：
  - `corepack pnpm product:compose:config`
  - `uv run pytest tests/test_product_compose_smoke_config.py -q`
  - `Yggdrasil.Update.ps1`、`Yggdrasil.Desktop.ps1`、`Yggdrasil.Install.ps1` PowerShell parser 检查

未完成：

- `release:check` 未包含产品 compose cold start、product smoke、backup/restore/upgrade/rollback。
- live provider 和 G4 provider matrix 仍是可选，不是默认发行门禁。
- M9 acceptance 仍不是 release hard gate；此前已知 pause/resume 后续状态收口和预算失败会影响真实体验链闭合。

## 4. 未完成任务

按正式发行优先级排序：

1. **正式发行包**：已新增 `packaging/distributions/local-preview.json` 与 `Build-Yggdrasil.ReleasePackage.ps1`，能构建完整 staged repo 发行包；后续还需要真实压缩包发布演练和下载页材料。
2. **签名与发布渠道**：GitHub Releases 已作为第一版发布渠道写入发行 manifest；代码签名仍只预留步骤，证书未就绪前不冒充正式签名版。
3. **产品 compose 发布门禁**：已新增 `product:release-smoke` 并接入 `release-check` workflow；后续还需要在 CI 上稳定跑通完整 Docker 产品栈。
4. **多版本升级演练**：至少覆盖 `N-1 -> N`、迁移失败、服务缺失、端口冲突、备份不可写、回滚恢复和重复执行幂等。
5. **应用包随包发行**：已新增发行 manifest、默认应用、直达快捷方式和安装器 `-AppPackagePath` / `-DefaultAppId` / `-ShortcutName` 参数；后续还需要安装后 API smoke 验证默认应用可见。
6. **数据治理硬删除补齐**：asset / node 硬删除、日志/备份清理、全量本地重置、恢复冲突检查和删除证明稳定格式。
7. **用户级故障恢复文档**：Docker Desktop 未启动、端口占用、provider key 缺失、迁移失败、备份失败、更新失败、回滚失败都需要普通用户可执行说明。
8. **SaaS 与远端数据服务**：账号、租户、工作区、远端备份、远端删除、隐私政策、服务条款、状态页和运维 runbook 均未实现；不能在发行材料里写成可用。

## 5. 不应再保留或继续扩展的旧路线

这些不是立即删除清单，但不应继续作为正式发行方向：

- 把 `infra/docker-compose.yml` 依赖栈包装成产品栈。正式产品栈只能指向 `infra/docker-compose.product.yml`。
- 把桌面封装继续做成“旧脚本上叠补丁”。下一步应切到发行包 manifest、应用包安装参数和正式安装器。
- 把托管 / SaaS 或官方远端数据服务写成当前可用能力。当前只能写“计划中”和“契约草案”。
- 把软遗忘、删除预览或手动清目录冒充用户级硬删除闭环。
- 把未签名 ZIP 当作正式 release artifact。

## 6. 下一步建议

最小可推进顺序：

1. 在 CI 上跑通 `product:release-smoke`，并把失败日志沉淀为普通用户故障说明。
2. 用 `Build-Yggdrasil.ReleasePackage.ps1 -Distribution local-preview` 生成真实 ZIP 和 SHA256，按 GitHub Releases 草案发布一次内部 RC。
3. 增加 app package distribution smoke：安装后 `GET /applications/{appId}` 可见，快捷方式能打开指定应用页。
4. 补 GitHub Releases 发布说明模板，明确 unsigned、Docker 检测/引导、手动更新和本地数据保留边界。
5. 扩展数据治理到 asset / node 硬删除前，先冻结旧备份处理策略，避免删除后通过恢复把数据复活。

## 7. 本轮验证记录

已执行并通过：

```powershell
corepack pnpm product:compose:config
uv run pytest tests/test_product_compose_smoke_config.py -q
uv run pytest tests/test_release_packaging_config.py tests/test_product_compose_smoke_config.py -q
powershell -NoProfile -ExecutionPolicy Bypass -File packaging/desktop/windows/Build-Yggdrasil.ReleasePackage.ps1 -Distribution local-preview -SkipArchive
```

PowerShell parser 检查通过：

```text
packaging/desktop/windows/Yggdrasil.Update.ps1: ok
packaging/desktop/windows/Yggdrasil.Desktop.ps1: ok
packaging/desktop/windows/Yggdrasil.Install.ps1: ok
```

未执行：

- 默认 3000 端口下的完整 `product:release-smoke`：本机 Windows 拒绝绑定 3000。
- 真实 provider 任务。
- 真实删除本地数据。

补充验证：

```powershell
$env:YGGDRASIL_WEB_PORT='3300'
$env:YGGDRASIL_CORE_API_PORT='5500'
$env:YGGDRASIL_AGENT_RUNTIME_PORT='5501'
$env:YGGDRASIL_MODULE_HOST_PORT='5502'
corepack pnpm product:release-smoke
corepack pnpm product:down
```

该临时端口验证已跑通完整产品发布门禁：compose config、product up、product smoke、保护性备份、upgrade、upgrade 后 smoke、指定快照 rollback、rollback 后 smoke 均通过；upgrade 和 rollback 后 `product-compose-smoke` 返回 `status: "ok"`。

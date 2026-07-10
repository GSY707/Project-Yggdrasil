# GitHub Releases 发布手册

日期：2026-06-18

## 1. 当前发布口径

第一版正式发行渠道使用 GitHub Releases。发行物是 staged repo ZIP，而不是静默自动更新器或 SaaS 服务。

当前边界：

- 发行包形态：完整 staged repo + Windows 桌面启动器 + Docker Compose 产品栈。
- Docker 策略：安装器检测 / 引导 Docker Desktop，不随包安装 Docker。
- 更新策略：手动检查、手动应用；计划任务只检查更新状态，不后台执行新版代码。
- 签名策略：预留 Windows code signing 步骤；证书未就绪前，发行物必须标记为 unsigned。
- 数据删除：本轮不把 asset / node 硬删除纳入正式发行承诺。

## 2. 构建发行包

```powershell
corepack pnpm release:package
```

等价命令：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File packaging/desktop/windows/Build-Yggdrasil.ReleasePackage.ps1 -Distribution local-preview
```

输出：

- `dist/releases/project-yggdrasil-local-preview-0.1.0-preview.1.zip`
- `dist/releases/project-yggdrasil-local-preview-0.1.0-preview.1.sha256`
- staging 目录：`dist/releases/project-yggdrasil-local-preview-0.1.0-preview.1/`

## 3. 发布前门禁

必须先跑：

```powershell
corepack pnpm product:release-smoke
uv run pytest tests/test_release_packaging_config.py tests/test_product_compose_smoke_config.py -q
```

如果本机 3000 / 5000 / 5001 / 5002 端口不可绑定，可临时覆盖宿主端口：

```powershell
$env:YGGDRASIL_WEB_PORT='3300'
$env:YGGDRASIL_CORE_API_PORT='5500'
$env:YGGDRASIL_AGENT_RUNTIME_PORT='5501'
$env:YGGDRASIL_MODULE_HOST_PORT='5502'
corepack pnpm product:release-smoke
```

`product:release-smoke` 必须看到 product compose smoke 返回 `status: "ok"`，否则失败。

## 4. GitHub Release 草案

Release 标题：

```text
Project Yggdrasil local-preview 0.1.0-preview.1
```

上传资产：

- `project-yggdrasil-local-preview-0.1.0-preview.1.zip`
- `project-yggdrasil-local-preview-0.1.0-preview.1.sha256`

说明正文：

```markdown
## Release Type

Local self-hosted preview for Windows. This package is unsigned.

## Install

1. Install Docker Desktop for Windows if it is not already installed.
2. Unzip the release package.
3. Run `packaging\desktop\windows\Yggdrasil Installer.cmd`.
4. Start from the tray or Start Menu.

## Included Apps

- Deep Research Lab
- Graduate Researcher
- Coding Greenfield
- Knowledge Studio

## Update Policy

Manual check and manual apply only. No silent background update is enabled.

## Data Boundary

Local product data stays in local Docker volumes and local Yggdrasil data folders. No official hosted workspace or remote data service is included in this release.

## Known Limits

- Unsigned package; Windows SmartScreen or ExecutionPolicy warnings may appear.
- Docker Desktop is detected and guided, not bundled.
- A model-provider key must currently be stored in the local untracked `infra/product.env`; the Web settings page reports connection status but does not save keys.
- Task detail still exposes some maintainer-oriented runtime and diagnostic terminology.
- SaaS, official remote backup, official remote restore, and official remote deletion are not released.
- Asset / node hard deletion remains outside this release.
```

发布正文还必须链接：

- `docs/USER_GUIDE.md`
- `docs/AGENT_DEVELOPER_GUIDE.md`
- `docs/release/FIRST_RELEASE_USER_AUDIT_2026-07-10.md`

## 5. 发布后核验

1. 下载 ZIP 和 `.sha256`。
2. 校验 SHA256。
3. 在干净目录解压。
4. 运行安装器。
5. 验证桌面 / Start Menu / 托盘入口。
6. 验证 `Deep Research Lab` 直达快捷方式打开 `/applications/yggdrasil.app.deep-research`。
7. 运行一次 `Yggdrasil Status.cmd`。

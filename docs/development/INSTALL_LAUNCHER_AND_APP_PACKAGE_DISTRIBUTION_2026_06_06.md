# 安装、启动器与应用包随包发行评估（2026-06-06）

## 结论

当前项目已经有三条真实启动路径，但还没有一个面向普通用户的正式安装器：

1. 开发工作区：`uv sync`、`corepack pnpm install`、准备 `.env`，再运行 `corepack pnpm yggdrasil:up`。
2. Docker 产品栈预览：复制 `infra/product.env.template` 为 `infra/product.env`，再运行 `corepack pnpm product:up`。
3. Windows 桌面封装预览：运行 `packaging/desktop/windows/Yggdrasil Installer.cmd`，安装托盘和快捷方式；它背后仍调用产品 Docker Compose 栈。

因此，对贡献者来说不一定需要启动器；对外部用户、应用包购买者或应用包试用者来说，需要启动器。启动器不应只是 CLI 包装，而应成为“启动产品栈、检查 Docker/provider key、打开指定应用、维护备份与更新”的普通用户正门。

## 当前安装与启动过程

### 开发工作区

当前 README 和开发者指南的默认路径是：

```powershell
uv sync
corepack pnpm install
corepack pnpm yggdrasil:up
```

`yggdrasil:up` 会预检 Docker、端口、依赖和 provider key，启动 infra、执行 Alembic 迁移，并拉起 Core API、Agent Runtime、Module Host、Worker 与 Web。它适合外部试用和开发调试之间的过渡，但仍要求用户处在源码工作区，并理解 `.env`、端口和 Docker。

### Docker Compose 产品栈

产品栈入口是：

```powershell
Copy-Item infra/product.env.template infra/product.env
corepack pnpm product:up
```

该路径使用 `infra/docker-compose.product.yml`，会构建 Python 服务镜像和 Web 镜像，并拉起数据库、Redis、NATS、MinIO、Temporal、Jaeger、OTel Collector、Core API、Agent Runtime、Module Host、Worker 和 Web。

关键点：`infra/docker/python-service.Dockerfile` 已经把 `applications/` 拷进 Python 服务镜像。因此，如果打包前把某个应用包放进 `applications/<appId>/`，产品镜像会天然包含它，Core API 也能在运行时发现。

### Windows 桌面封装预览

当前桌面封装已经提供：

- 未签名安装/卸载脚本。
- 桌面和开始菜单快捷方式。
- 托盘控制器。
- 启动、停止、状态、日志、备份、恢复、快照、升级、回滚、更新检查和手动应用更新入口。

但它现在仍是“预览封装”：

- `Build-Yggdrasil.DesktopPackage.ps1` 只把 `packaging/desktop/windows/*` 打进 ZIP，不打包完整仓库。
- `Yggdrasil.Install.ps1` 仍需要定位一个 repo checkout，或由用户传 `-RepoRootPath`。
- 当前快捷方式只打开产品首页，没有应用包专属快捷方式。
- 当前没有签名、正式安装向导、静默更新、应用包注入参数或应用包安装验证。

## 应用包随项目打包是否可行

可行，而且技术路径已经基本清晰。

当前应用包标准位置是：

```text
applications/<appId>/
├── yggdrasil.app.yaml
├── config/defaults.json
├── memory/
├── prompt-profiles/
├── scenes/
├── few-shots/
└── web/dashboard.json
```

运行时通过 `applications/*/yggdrasil.app.yaml` 发现应用。Core API 暴露：

- `GET /applications`
- `GET /applications/{appId}`
- `POST /applications/{appId}/activate`
- `POST /applications/{appId}/config`

Web 已有稳定入口：

- `/applications`
- `/applications/{appId}`
- `/tasks?appId={appId}`
- `/prompting?appId={appId}`

所以，如果外部团队开发了一个应用包，发行时可以把它和项目一起打包。更推荐的方式不是把源码目录粗暴拷给用户，而是：

1. 构建一个“基座 + 指定应用包”的发行产物。
2. 在构建阶段把应用包复制到 staging repo 的 `applications/<appId>/`。
3. 运行 manifest 和引用文件校验。
4. 构建产品 Docker 镜像或离线镜像包。
5. 安装桌面启动器。
6. 首次启动后打开 `/applications/{appId}` 或 `/tasks?appId={appId}`。

## 能否安装时自动装上应用包并创建直达快捷方式

目标上可以，当前实现还没完全做到。

现有代码已经具备三块基础：

1. 应用包发现：只要应用包在 `applications/<appId>/` 且含 `yggdrasil.app.yaml`，catalog 能发现。
2. 应用使用界面：`/applications/{appId}` 已能展示应用详情、配置、出厂记忆、任务模板，并能从该应用启动任务。
3. 快捷方式生成：`Yggdrasil.Desktop.ps1` 已经有通用 `New-DesktopShortcut`，可以创建桌面和开始菜单快捷方式。

缺口是安装器还没有把这三块串起来：

1. 没有 `-AppPackagePath` / `-AppId` / `-ShortcutName` 这类参数。
2. 没有把外部应用包复制到 `applications/<appId>/` 的安装步骤。
3. 没有安装时的 manifest 校验和引用文件校验。
4. 没有“启动产品栈后打开指定路径”的 `start-app` 或 `-OpenPath` 参数。
5. 没有自动激活默认应用的安装后动作。

最小可行改造是：

```powershell
.\Yggdrasil.Install.ps1 install `
  -RepoRootPath <staged-repo> `
  -AppPackagePath <external-app-package> `
  -DefaultAppId yggdrasil.app.example `
  -ShortcutName "Example App"
```

安装器应把应用复制到：

```text
<staged-repo>/applications/example/
```

再创建快捷方式，目标类似：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<installRoot>\Yggdrasil.Desktop.ps1" start -OpenPath "/applications/yggdrasil.app.example"
```

或者直达任务启动：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<installRoot>\Yggdrasil.Desktop.ps1" start -OpenPath "/tasks?appId=yggdrasil.app.example"
```

`Yggdrasil.Desktop.ps1` 启动产品栈后应打开：

```text
http://localhost:<YGGDRASIL_WEB_PORT>/applications/yggdrasil.app.example
```

## 建议的产品路线

不要把新启动器做成旧脚本上的临时补丁。建议直接切到“发行包 manifest + 桌面启动器”的新结构：

```text
packaging/distributions/<distributionId>.json
```

manifest 至少包含：

```json
{
  "distributionId": "deep-research-desktop",
  "displayName": "Deep Research Lab",
  "defaultAppId": "yggdrasil.app.deep-research",
  "includedApplications": ["applications/deep-research"],
  "shortcutTargets": [
    {
      "name": "Deep Research Lab",
      "openPath": "/applications/yggdrasil.app.deep-research"
    }
  ]
}
```

启动器职责应固定为：

1. 检查 Docker Desktop。
2. 检查端口和产品 env。
3. 启动或复用产品 Compose 栈。
4. 等待 Web 和 Core API 健康。
5. 可选调用 `POST /applications/{appId}/activate`。
6. 打开应用包入口。
7. 提供状态、日志、备份、恢复、升级、回滚。

应用包职责保持纯净：

1. 提供 manifest、prompt、memory、defaults、dashboard。
2. 不硬编码 provider key。
3. 不直接改基座状态。
4. 不把业务安装逻辑塞进 prompt 或前端页面。

## 当前判断

需要启动器，但不是为了开发者，而是为了普通用户和应用包发行。

可以把应用包和整个项目一起打包；更准确地说，应把“基座产品栈 + 应用包 + 桌面启动器”做成一个发行产物。

可以在安装时自动装上应用包并创建直达应用界面的快捷方式；当前仓库已有发现、页面和快捷方式生成基础，但还缺应用包安装参数、校验、深链接打开和默认激活动作。

优先实现顺序：

1. 给 `Yggdrasil.Desktop.ps1` 增加 `-OpenPath` 或 `start-app`。
2. 给安装脚本增加应用包复制、校验和应用专属快捷方式。
3. 给构建脚本增加“完整发行包”模式，不再只打包桌面脚本。
4. 增加 app package distribution smoke：安装后 `GET /applications/{appId}` 可见，快捷方式能打开指定应用页。
5. 再做签名安装器和正式更新链路。

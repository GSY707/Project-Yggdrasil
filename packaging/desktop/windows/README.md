# Windows 桌面封装预览

这是第一版 Windows 桌面封装预览，复用完整产品 Docker Compose 栈，提供未签名安装包、托盘控制器、启动/停止、状态、日志、备份、恢复、快照、升级、回滚和手动更新入口。

当前仍不是正式签名发行版。未签名脚本可能触发 ExecutionPolicy 或 SmartScreen 提示；自动更新任务只做检查并写入 `update-state.json`，不会在后台静默下载或执行新版代码。

## 入口

| 文件 | 动作 |
|------|------|
| `Yggdrasil Installer.cmd` | 安装未签名桌面封装到 `%LOCALAPPDATA%\ProjectYggdrasil\Desktop`，写入 `install.json` 并安装开始菜单、桌面和启动项快捷方式 |
| `Yggdrasil Uninstaller.cmd` | 卸载桌面封装、启动项和快捷方式 |
| `Yggdrasil Tray.cmd` | 启动托盘控制器；托盘菜单提供 Start/Open、Status、Logs、Backup、Snapshots、Restore Latest、Check Updates、Apply Update、Rollback、Stop Product |
| `Yggdrasil Desktop.cmd` | 启动产品栈并打开 Web；端口优先读取 `infra/product.env` 的 `YGGDRASIL_WEB_PORT` |
| `Yggdrasil Stop.cmd` | 安全停止产品栈 |
| `Yggdrasil Status.cmd` | 显示 compose 状态并运行 product smoke |
| `Yggdrasil Logs.cmd` | 打开日志窗口并跟随核心服务日志 |
| `Yggdrasil Backup.cmd` | 创建产品 Compose 备份快照 |
| `Yggdrasil Restore.cmd` | 恢复最近一次产品 Compose 快照 |
| `Yggdrasil Snapshots.cmd` | 列出产品 Compose 快照 |
| `Yggdrasil Upgrade.cmd` | 创建保护性快照、重建产品栈并运行 smoke |
| `Yggdrasil Rollback.cmd` | 尝试保护性快照、恢复快照并运行 smoke |
| `Yggdrasil Update.cmd` | 检查当前 git 分支的上游更新并写入 `update-state.json` |
| `Yggdrasil Apply Update.cmd` | 仅在 fast-forward 更新可用时创建产品备份、合并上游、安装依赖并执行 `product:upgrade` |
| `Yggdrasil Install Auto Update Task.cmd` | 注册登录时和每日 09:00 的更新检查任务；只检查，不自动应用 |
| `Yggdrasil Uninstall Auto Update Task.cmd` | 删除更新检查计划任务 |
| `Yggdrasil Build Installer.cmd` | 构建未签名 ZIP：`dist/desktop/yggdrasil-desktop-preview.zip` |
| `Yggdrasil Install Shortcuts.cmd` | 安装桌面和开始菜单快捷方式 |
| `Yggdrasil Uninstall Shortcuts.cmd` | 删除桌面和开始菜单快捷方式 |
| `Yggdrasil.Desktop.ps1` | 机器可读产品控制脚本，支持 `start` / `stop` / `status` / `open` / `logs` / `backup` / `restore` / `snapshots` / `upgrade` / `rollback` / `install-shortcuts` / `uninstall-shortcuts` |
| `Yggdrasil.Tray.ps1` | PowerShell WinForms 托盘控制器 |
| `Yggdrasil.Update.ps1` | 手动更新检查/应用和计划任务安装脚本 |
| `Yggdrasil.Install.ps1` | 安装/卸载脚本；从 ZIP 运行时可传 `-RepoRootPath <repo>`，或设置 `YGGDRASIL_REPO_ROOT` |
| `Build-Yggdrasil.DesktopPackage.ps1` | 未签名 ZIP 构建脚本 |

## 数据边界

- 默认使用 `infra/docker-compose.product.yml`；若存在未跟踪的 `infra/product.env`，优先读取它，否则回退 `infra/product.env.template`。
- 数据库在 compose volume `postgres-data`。
- state root 在 compose volume `yggdrasil-state`，容器内路径为 `/workspace/.yggdrasil`。
- 备份在 compose volume `yggdrasil-backups`，容器内路径为 `/workspace/.yggdrasil-backups`。
- Provider key 仍必须由用户显式写入 `infra/product.env`、根 `.env` 或本机环境变量；不要写入模板、镜像或快捷方式。
- Provider key 状态由 Core API `/health.providerStatus` 暴露，Web 任务启动面板会阻止未配置或 fallback 测试模式下的直接启动。
- 远端同步和官方托管仍未发布。
- 签名安装包仍未完成；当前安装包明确标记 `signed=false`。
- 更新器当前是手动更新器。计划任务只检查更新；真正应用更新必须用户显式触发，并且只允许 fast-forward。

## 命令

```powershell
.\Yggdrasil.Install.ps1 install -StartTray
.\Yggdrasil.Install.ps1 install -RepoRootPath C:\skzy\QuickFileTransport\世界树计划 -StartTray
.\Yggdrasil.Desktop.ps1 start
.\Yggdrasil.Desktop.ps1 status
.\Yggdrasil.Desktop.ps1 logs
.\Yggdrasil.Desktop.ps1 backup
.\Yggdrasil.Desktop.ps1 snapshots
.\Yggdrasil.Desktop.ps1 restore -Snapshot /workspace/.yggdrasil-backups/<timestamp>
.\Yggdrasil.Desktop.ps1 upgrade
.\Yggdrasil.Desktop.ps1 rollback -Snapshot /workspace/.yggdrasil-backups/<timestamp>
.\Yggdrasil.Desktop.ps1 install-shortcuts
.\Yggdrasil.Desktop.ps1 uninstall-shortcuts
.\Yggdrasil.Desktop.ps1 stop
.\Yggdrasil.Update.ps1 check
.\Yggdrasil.Update.ps1 apply
.\Yggdrasil.Update.ps1 install-task
.\Yggdrasil.Update.ps1 uninstall-task
.\Build-Yggdrasil.DesktopPackage.ps1
```

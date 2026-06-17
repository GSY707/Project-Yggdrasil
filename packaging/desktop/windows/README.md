# Windows 桌面封装预览

这是第一版 Windows 桌面封装预览，复用完整产品 Docker Compose 栈，提供未签名安装包、托盘控制器、启动/停止、状态、诊断、备份、恢复、快照、升级、回滚、手动更新和卸载入口。

当前仍不是正式签名发行版。未签名脚本可能触发 ExecutionPolicy 或 SmartScreen 提示；自动更新任务只做检查并写入 `update-state.json`，不会在后台静默下载或执行新版代码。更新、升级、回滚和删除本地数据都需要用户显式确认。

## 入口

| 文件 | 动作 |
|------|------|
| `Yggdrasil Installer.cmd` | 安装未签名桌面封装到 `%LOCALAPPDATA%\ProjectYggdrasil\Desktop`，写入 `install.json` 并安装开始菜单、桌面和启动项快捷方式 |
| `Yggdrasil Uninstaller.cmd` | 卸载桌面封装、启动项和快捷方式；默认保留本地数据 |
| `Yggdrasil Tray.cmd` | 启动托盘控制器；托盘菜单提供 Start、Apps、Settings、Health and Diagnostics、Back Up Local Data、View Backups、Check for Updates、Apply Update、Restore Previous Version、Stop |
| `Yggdrasil Desktop.cmd` | 启动本地产品并打开 Start 首页 |
| `Yggdrasil Stop.cmd` | 停止本地产品 |
| `Yggdrasil Status.cmd` | 显示健康状态并运行产品检查 |
| `Yggdrasil Logs.cmd` | 打开诊断日志窗口 |
| `Yggdrasil Backup.cmd` | 创建本地数据备份 |
| `Yggdrasil Restore.cmd` | 恢复最近一次本地备份 |
| `Yggdrasil Snapshots.cmd` | 列出本地备份 |
| `Yggdrasil Upgrade.cmd` | 显示影响预览，确认后创建保护性备份、升级并重启本地产品 |
| `Yggdrasil Rollback.cmd` | 显示影响预览，确认后创建保护性备份并恢复上一版本或指定备份 |
| `Yggdrasil Update.cmd` | 检查当前分支上游更新，写入 `update-state.json` 和影响预览 |
| `Yggdrasil Apply Update.cmd` | 仅在 fast-forward 更新可用且工作区干净时，显示影响预览，确认后备份、应用更新并升级本地产品 |
| `Yggdrasil Install Auto Update Task.cmd` | 注册登录时和每日 09:00 的更新检查任务；只检查，不自动应用 |
| `Yggdrasil Uninstall Auto Update Task.cmd` | 删除更新检查计划任务 |
| `Yggdrasil Build Installer.cmd` | 构建未签名 ZIP：`dist/desktop/yggdrasil-desktop-preview.zip` |
| `Yggdrasil Build Release Package.cmd` | 构建完整 staged repo 发行包：`dist/releases/project-yggdrasil-<distribution>-<version>.zip` 与 `.sha256`，用于 GitHub Releases |
| `Yggdrasil Install Shortcuts.cmd` | 安装桌面和开始菜单快捷方式 |
| `Yggdrasil Uninstall Shortcuts.cmd` | 删除桌面和开始菜单快捷方式 |
| `Yggdrasil.Desktop.ps1` | 机器可读产品控制脚本，支持 `start` / `stop` / `status` / `open` / `open-apps` / `open-settings` / `logs` / `backup` / `restore` / `snapshots` / `upgrade` / `rollback` / `install-shortcuts` / `uninstall-shortcuts` |
| `Yggdrasil.Tray.ps1` | PowerShell WinForms 托盘控制器 |
| `Yggdrasil.Update.ps1` | 手动更新检查/应用和计划任务安装脚本 |
| `Yggdrasil.Install.ps1` | 安装/卸载脚本；从 ZIP 运行时可传 `-RepoRootPath <repo>`，或设置 `YGGDRASIL_REPO_ROOT` |
| `Build-Yggdrasil.DesktopPackage.ps1` | 未签名 ZIP 构建脚本 |
| `Build-Yggdrasil.ReleasePackage.ps1` | 正式发行包构建脚本：读取 `packaging/distributions/*.json`，把基座、应用包、桌面封装和发布 manifest 打入 staged repo；签名步骤预留但默认不签名 |

## 数据边界

- 默认使用 `infra/docker-compose.product.yml`；若存在未跟踪的 `infra/product.env`，优先读取它，否则回退 `infra/product.env.template`。
- 数据库在 compose volume `postgres-data`。
- state root 在 compose volume `yggdrasil-state`，容器内路径为 `/workspace/.yggdrasil`。
- 备份在 compose volume `yggdrasil-backups`，容器内路径为 `/workspace/.yggdrasil-backups`。
- AI 服务连接信息仍必须由用户显式保存在本机环境或未跟踪的产品环境文件里；不要写入模板、镜像或快捷方式。
- AI 服务连接状态由 Core API `/health.providerStatus` 暴露，Web 任务启动面板会阻止未配置或 fallback 测试模式下的直接启动。
- 远端同步和官方托管仍未发布。
- 签名安装包仍未完成；当前安装包明确标记 `signed=false`。
- 更新器当前是手动更新器。计划任务只检查更新；真正应用更新必须用户显式触发，并且只允许 fast-forward。
- 卸载默认保留 `.yggdrasil` 和 `.yggdrasil-backups`。删除本地状态和备份必须显式运行危险命令并输入确认文本；`infra/product.env` 即使在危险删除模式下也默认保留。

## 维护确认与失败恢复

- `Yggdrasil.Update.ps1 check` 会写入 `update-state.json`，包括当前版本、目标版本、变更文件预览和恢复建议。
- `Yggdrasil.Update.ps1 apply` 只允许 clean worktree + fast-forward；执行前需要输入 `APPLY UPDATE`，或由自动化显式传 `-ConfirmApply`。
- `Yggdrasil.Desktop.ps1 upgrade` 执行前需要输入 `UPGRADE YGGDRASIL`，或由自动化显式传 `-ConfirmUpgrade`。
- `Yggdrasil.Desktop.ps1 rollback` 执行前需要输入 `RESTORE PREVIOUS VERSION`，或由自动化显式传 `-ConfirmRollback`。
- `Yggdrasil.Install.ps1 uninstall` 默认只删除封装、快捷方式和启动项，保留本地数据。
- 删除本地状态和备份必须运行 `Yggdrasil.Install.ps1 uninstall -DeleteLocalData` 并输入 `DELETE LOCAL DATA`，或由自动化显式传 `-DeleteLocalData -ConfirmDeleteLocalData`。
- 维护失败会写入 `maintenance-state.json`、`update-state.json` 或 `%LOCALAPPDATA%\ProjectYggdrasil\uninstall-state.json`，用于查看失败阶段、影响预览和恢复动作。

## 命令

```powershell
.\Yggdrasil.Install.ps1 install -StartTray
.\Yggdrasil.Install.ps1 install -RepoRootPath C:\skzy\QuickFileTransport\世界树计划 -StartTray
.\Yggdrasil.Install.ps1 install -AppPackagePath C:\path\to\application -DefaultAppId yggdrasil.app.example -ShortcutName "Example App"
.\Yggdrasil.Desktop.ps1 start
.\Yggdrasil.Desktop.ps1 start-app -OpenPath /applications/yggdrasil.app.deep-research
.\Yggdrasil.Desktop.ps1 status
.\Yggdrasil.Desktop.ps1 logs
.\Yggdrasil.Desktop.ps1 backup
.\Yggdrasil.Desktop.ps1 snapshots
.\Yggdrasil.Desktop.ps1 restore -Snapshot /workspace/.yggdrasil-backups/<timestamp>
.\Yggdrasil.Desktop.ps1 upgrade
.\Yggdrasil.Desktop.ps1 rollback -Snapshot /workspace/.yggdrasil-backups/<timestamp>
.\Yggdrasil.Install.ps1 uninstall
.\Yggdrasil.Install.ps1 uninstall -DeleteLocalData
.\Yggdrasil.Desktop.ps1 install-shortcuts
.\Yggdrasil.Desktop.ps1 uninstall-shortcuts
.\Yggdrasil.Desktop.ps1 stop
.\Yggdrasil.Update.ps1 check
.\Yggdrasil.Update.ps1 apply
.\Yggdrasil.Update.ps1 install-task
.\Yggdrasil.Update.ps1 uninstall-task
.\Build-Yggdrasil.DesktopPackage.ps1
.\Build-Yggdrasil.ReleasePackage.ps1 -Distribution local-preview
```

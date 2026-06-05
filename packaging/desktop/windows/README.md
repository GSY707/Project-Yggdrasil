# Windows 桌面薄封装预览

这不是正式安装包。它是第一版 Windows 桌面入口，复用完整产品 Docker Compose 栈，提供可双击的启动、停止、状态和日志入口。

## 入口

| 文件 | 动作 |
|------|------|
| `Yggdrasil Desktop.cmd` | 启动产品栈并打开 `http://localhost:3000` |
| `Yggdrasil Stop.cmd` | 安全停止产品栈 |
| `Yggdrasil Status.cmd` | 显示 compose 状态并运行 product smoke |
| `Yggdrasil Logs.cmd` | 打开日志窗口并跟随核心服务日志 |
| `Yggdrasil.Desktop.ps1` | 机器可读控制脚本，支持 `start` / `stop` / `status` / `open` / `logs` / `backup` / `restore` |

## 数据边界

- 默认使用 `infra/docker-compose.product.yml` 与 `infra/product.env.template`。
- 数据库在 compose volume `postgres-data`。
- state root 在 compose volume `yggdrasil-state`，容器内路径为 `/workspace/.yggdrasil`。
- 备份在 compose volume `yggdrasil-backups`，容器内路径为 `/workspace/.yggdrasil-backups`。
- Provider key 仍必须由用户显式写入未跟踪 env 文件或本机环境变量；不要写入镜像。
- 远端同步、官方托管、自动更新和安装/卸载器仍未发布。

## 命令

```powershell
.\Yggdrasil.Desktop.ps1 start
.\Yggdrasil.Desktop.ps1 status
.\Yggdrasil.Desktop.ps1 logs
.\Yggdrasil.Desktop.ps1 backup
.\Yggdrasil.Desktop.ps1 restore -Snapshot /workspace/.yggdrasil-backups/<timestamp>
.\Yggdrasil.Desktop.ps1 stop
```

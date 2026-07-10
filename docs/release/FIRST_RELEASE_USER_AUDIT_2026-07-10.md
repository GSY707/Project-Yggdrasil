# 首版用户体验与发布验收

日期：2026-07-10

## 核心判断

首版可以作为 **Windows 本地自托管、未签名预览版** 发布。普通用户的材料导入、应用选择、任务草稿和详情查看闭环已真实跑通；无模型密钥时启动按钮会被正确阻止。它还不能被表述为无需技术准备的消费级产品，因为模型密钥仍需写入本机环境文件，任务详情仍混有维护者术语。

## 本轮流程

| 步骤 | 验收结果 | 健康度 |
| --- | --- | --- |
| 1. 冷启动并打开开始页 | Compose 全栈启动，首页展示服务、AI 连接和任务阻塞状态；冷启动首次数据加载较慢 | 可发布，有性能风险 |
| 2. 选择应用 | 四个普通用户应用清晰展示材料要求、模板、设置和预期审阅 | 良好 |
| 3. 导入材料 | 文本导入成功，生成 1 个切段、摘要节点和资产记录 | 良好 |
| 4. 附加材料 | 导入结果可直接进入新任务，任务表单显示素材、摘要与切段数 | 良好 |
| 5. 创建 Deep Research 草稿 | 草稿创建成功；无模型密钥时真实启动保持禁用 | 良好 |
| 6. 查看任务详情 | 草稿、目标、素材、状态和运行控制可见；页面信息密度过高且含英文诊断术语 | 可用，需后续重构 |
| 7. 查看设置 | 隐私与本地数据边界清楚；只能查看 AI 服务状态，不能在 Web 内保存密钥 | 可用，明显摩擦 |

## 最高优先级后续工作

1. 提供安全的图形化模型服务连接流程，替代手工编辑 `infra/product.env`。
2. 把任务详情默认视图收敛为目标、状态、结果、预算与暂停/恢复；把分析、调用和运行时字段移入维护者展开区。
3. 给首页数据加载增加明确超时和重试，避免冷启动时长时间停在“正在准备”。
4. 完成 Windows 签名后再把“预览版”提升为普通客户正式版。

## 发布门禁修复

首轮 `product:release-smoke` 在 Docker Desktop 29.3.1 上卡死于 `compose up --build`：同一个 Python 镜像被六个服务重复展开构建，切换 BuildKit 后又触发 Compose session header 错误。发布脚本已删除“由每个服务各自构建”的路径，改为顺序构建一次 Python 镜像和一次 Web 镜像，再用 `compose up --no-build` 启动。当前 Windows Docker Desktop 的顺序构建暂用 legacy builder；这是单一发布路径，不再保留重复 fan-out 构建。

发行包首轮构建还暴露出 `apps/web/.next` 与 `apps/web/node_modules` 被整目录复制、以及当前 Windows PowerShell 环境缺少 `Get-FileHash` 命令的问题。打包清单已改为只复制 Web 源码与必要配置，SHA256 改用 .NET 加密 API 计算；发行包不再携带本机依赖缓存或编译缓存。

## 证据

- `first-release-audit-2026-07-10/01-home.png`
- `first-release-audit-2026-07-10/02-applications.png`
- `first-release-audit-2026-07-10/03-assets.png`
- `first-release-audit-2026-07-10/04-asset-imported.png`
- `first-release-audit-2026-07-10/05-task-draft.png`
- `first-release-audit-2026-07-10/06-task-detail.png`
- `first-release-audit-2026-07-10/07-settings.png`

截图只能证明可见状态与本轮交互，不能单独证明键盘可达性、屏幕阅读器语义或完整 WCAG 合规性。

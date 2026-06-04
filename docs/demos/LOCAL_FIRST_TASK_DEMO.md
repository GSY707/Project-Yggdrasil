# 本地首次成功演示脚本

> 用途：面向外部试用者或录屏演示，证明用户可以从 Web 完成“导入素材 -> 选择应用 -> 创建任务 -> 启动任务 -> 查看结果”的第一条路径。

## 前置条件

1. 已执行依赖安装：

```powershell
uv sync
corepack pnpm install
```

2. `.env` 至少配置一个低成本或试用 provider key，例如 `LONGCAT_API_KEY`、`OPENROUTER_API_KEY` 或 `DEEPSEEK_API_KEY`。不要把真实 key 写入仓库。
3. 启动本地产品：

```powershell
corepack pnpm yggdrasil:up
```

4. 打开 `http://localhost:3000`，确认首页启动检查没有阻塞项。

## 演示正文

### 1. 导入素材

1. 进入 `/assets`。
2. 选择一个 `.txt`、`.md`、`.json`、`.csv` 或 `.log` 文本文件，或直接粘贴一段材料。
3. 确认页面显示切段预览。
4. 点击「导入素材」。
5. 记录页面显示的素材 ID、切段数量和摘要节点。

### 2. 附加到新任务

1. 点击「用这个素材创建任务」或资产卡片里的「附加到新任务」。
2. 页面进入 `/tasks`，新任务面板显示「已附加素材」。

### 3. 选择应用模板

1. 应用选择优先使用 `Deep Research Lab`。
2. 模板选择一个深度研究或资料综述模板。
3. 确认面板展示「示例任务」和「预期产物」。
4. 把任务目标改成围绕刚才素材的可验收目标，例如：

```text
基于已附加素材，整理一份结构化研究摘要，列出关键结论、证据、争议点和后续问题。
```

### 4. 创建并启动

1. 点击「只创建草稿」，展示任务 ID、「立即启动」和「查看任务」。
2. 回到面板点击「立即启动」，或直接点击「创建并启动」。
3. 进入任务详情页后，观察任务状态、运行控制、模型调用、Prompt 工件和 LLM 工作分析摘要。

## 演示口径

- 这条演示路径使用真实 Web 产品入口，不使用内部 evaluation suite 代替用户体验。
- 如果 provider key 缺失，一键启动器会提前失败；只做 fallback 本地验证时可使用 `uv run yggdrasil-ops launch --allow-missing-provider`。
- 当前正式导出路径是 `corepack pnpm ops:backup`，恢复路径是 `corepack pnpm ops:restore`。
- 当前没有 Web 删除按钮。删除本地状态前应先备份，然后停止服务并手动清理 `.yggdrasil`；Docker 卷清理需要单独确认。

# Project Yggdrasil 普通用户指南

本指南面向使用 Agent 完成任务的人。你不需要理解项目源码，但首个预览版仍要求你能安装 Docker Desktop，并在本机配置自己的模型服务密钥。

## 1. 安装

### 1.1 准备

- Windows 10/11；
- Docker Desktop；
- 至少一个受支持模型服务的 API key；
- 足够的磁盘空间用于 Docker 镜像、任务材料和本地备份。

### 1.2 下载与校验

从 [GitHub Releases](https://github.com/GSY707/Project-Yggdrasil/releases) 下载 ZIP 和同名 `.sha256`，在下载目录运行：

```powershell
$expected = (Get-Content .\project-yggdrasil-local-preview-0.1.0-preview.1.sha256).Split()[0]
$actual = (Get-FileHash .\project-yggdrasil-local-preview-0.1.0-preview.1.zip -Algorithm SHA256).Hash.ToLower()
$actual -eq $expected.ToLower()
```

结果应为 `True`。然后解压 ZIP，运行：

```text
packaging\desktop\windows\Yggdrasil Installer.cmd
```

这是未签名预览包，Windows 可能显示 SmartScreen 或 PowerShell 安全提示。只应使用本仓库 GitHub Release 提供、且 SHA256 校验通过的文件。

### 1.3 连接模型服务

在解压目录把 `infra\product.env.template` 复制为 `infra\product.env`，只填写你实际使用的服务密钥，例如：

```dotenv
YGGDRASIL_LLM_API_KEY_DEEPSEEK=你的密钥
```

不要把 `infra/product.env` 发给别人或提交到 Git。配置后重新启动 Yggdrasil。Web“设置”页当前只显示连接状态，不会保存密钥。

## 2. 第一次任务

1. 从开始菜单打开 **Yggdrasil Desktop**。
2. 等待浏览器打开 `http://localhost:3000`。
3. 首页先检查“AI 服务”和“需要处理”；存在阻塞时不要启动任务。
4. 进入“应用”，选择最接近目标的 Agent。
5. 有资料时先进入“材料”，粘贴文本或选择文本文件并导入。
6. 点击“用这个素材创建任务”，选择应用和任务模板。
7. 先“只创建草稿”，核对目标、材料和预算；确认后再启动。
8. 在任务详情查看状态、结果、暂停/恢复能力和必要的诊断信息。

## 3. 如何选择应用

| 你的目标 | 推荐应用 |
| --- | --- |
| 调研一个开放问题、比较证据 | Deep Research |
| 推进学习、论文或研究写作 | Graduate Researcher |
| 从零开发一个软件项目 | Coding Greenfield |
| 整理资料、笔记和知识档案 | Knowledge Studio |

应用模板会说明需要准备的材料、示例任务和预期产物。先选最接近的模板，再修改标题和目标，不要从空白描述开始。

## 4. 材料、隐私与模型服务

- 任务、材料、结果、运行状态和备份默认保存在本机。
- 启动真实任务后，任务目标、材料摘要、检索上下文和 Prompt 会发送给你选择的模型服务商。
- 当前浏览器直接导入以文本类文件为主；PDF、图片、音频和视频需先提供可读取的摘录或转录文本。
- 本版本没有 Project Yggdrasil 官方云端工作区、远端备份或远端删除服务。

## 5. 备份、删除与更新

- 在“数据与备份”中查看本地备份、删除影响预览和受保护的 task 删除。
- 删除前先生成影响预览，并保留默认的删除前备份。
- 卸载默认保留任务数据和备份；删除本地数据需要额外确认。
- 更新只支持手动检查和手动应用，不会在后台静默执行新版本。

## 6. 常见问题

### 首页长时间显示“正在准备”

首个冷启动需要等待数据库和本地服务就绪。若持续超过约 30 秒，从开始菜单打开 **Yggdrasil Status** 或“帮助与诊断”，确认 Docker Desktop、Core API 和数据库状态。

### 可以创建草稿，但不能启动

这是安全门。通常是模型密钥未配置或服务仍在重启。检查 `infra/product.env`，重启产品，再在“设置”确认 AI 服务为“已连接”。

### 材料已经导入，但任务里没有看到

从材料导入完成卡片点击“用这个素材创建任务”或“附加到新任务”。任务表单应显示“已附加素材”。

### 我看到英文或运行时术语

首版任务详情仍保留部分维护者诊断字段，这是已知界面边界，不影响草稿、启动和结果状态。不要修改不了解的高级控制项。

## 7. 获取帮助

先在产品内打开“帮助与诊断”，记录状态和失败步骤。公开问题可提交到 [GitHub Issues](https://github.com/GSY707/Project-Yggdrasil/issues)，不要附带 API key、原始私密材料或完整环境文件。

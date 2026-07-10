# Project Yggdrasil（世界树计划）

Project Yggdrasil 是一个面向长程任务的本地 Agent 工作台。你可以选择研究、写作、软件开发或知识整理应用，导入材料，创建任务，并保留可恢复、可审计的任务状态。

> 首个公开版本是 **Windows 本地自托管预览版**：数据默认保存在本机，运行需要 Docker Desktop 和你自己的模型服务密钥，安装包尚未签名。

[English](README.en.md) · [设计哲学（项目唯一真源）](docs/architecture/design-philosophy-and-cognitive-principles.md)

## 我想使用 Agent

适合希望直接完成研究、学习、写作、编程或知识整理任务的用户。

1. 从 [GitHub Releases](https://github.com/GSY707/Project-Yggdrasil/releases) 下载首版 ZIP 和同名 `.sha256`。
2. 校验 SHA256，解压 ZIP。
3. 安装并启动 Docker Desktop。
4. 在解压目录运行 `packaging\desktop\windows\Yggdrasil Installer.cmd`。
5. 从开始菜单打开 **Yggdrasil Desktop**，浏览器会进入 `http://localhost:3000`。
6. 在“设置”选择 LLM 供应商并保存自己的 API 密钥。
7. 在“应用”中选择场景，在“材料”中导入资料，再创建任务草稿并确认启动。

完整说明、数据边界、备份和故障处理见 [普通用户指南](docs/USER_GUIDE.md)。

## 我想基于它开发 Agent

本项目把一个 Agent 产品封装为 `applications/<appId>/` 下的应用包。应用包可以声明：

- 主 Agent 与 Sub-Agent 的 prompt profile；
- 场景模板、few-shot 和出厂记忆；
- 模块与 MCP 能力依赖；
- 用户可见的任务模板、设置项和预期产物；
- 独立的运行时记忆命名空间。

从现有应用复制最接近的示例，修改 manifest、prompt、memory、配置和 Web 元数据，然后运行装配测试。完整路径见 [Agent 开发者指南](docs/AGENT_DEVELOPER_GUIDE.md)。

## 当前包含的应用

| 应用 | 适合做什么 |
| --- | --- |
| Deep Research | 开放问题研究、证据整理与不确定性分析 |
| Graduate Researcher | 学习资料、论文方向与研究写作推进 |
| Coding Greenfield | 从产品目标或原型启动新软件项目 |
| Knowledge Studio | 把资料、访谈和笔记整理为可复用知识 |

## 首版边界

- 支持 Windows 本地自托管；没有官方 SaaS 或远端工作区。
- 模型调用会把任务目标和必要上下文发送给你选择的模型服务商。
- 未配置模型密钥时仍可导入材料和创建草稿，但系统会阻止启动真实任务。
- ZIP、PowerShell 脚本和快捷方式尚未签名，Windows 可能显示安全警告。
- 模型密钥可在 Web“设置”页保存到本机状态卷；页面只显示配置状态和密钥末四位，不回传完整密钥。环境文件仍可作为维护者部署方式。
- 任务详情保留部分运行时与诊断信息；普通用户主路径已经与维护者入口分开，但还不是最终消费级界面。

## 项目开发

参与基座开发、运行测试、理解架构或提交贡献，只从 [项目开发入口](docs/DEVELOPMENT.md) 进入。README 不再展开内部服务、命令、评测和仓库目录。

许可证：[AGPL-3.0](LICENSE)

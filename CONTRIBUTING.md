# 贡献指南

[English Version](CONTRIBUTING.en.md)

感谢你为世界树计划投入时间。

本仓库采用 AGPL-3.0 完整开源，默认原则是：进入仓库的代码、文档、样例、评测材料和实现讨论都应可以公开分发。不要提交任何真实 API key、访问令牌、密码、私有数据或不具备再分发权利的第三方材料。

## 先读哪些文件

- `docs/OPEN_SOURCE_BOUNDARY.md`：开源边界、支持矩阵、稳定性承诺
- `GOVERNANCE.md`：维护者角色、评审与决策方式
- `SECURITY.md`：安全漏洞披露流程
- `CODE_OF_CONDUCT.md`：社区行为要求
- `docs/rfcs/README.md`：重大设计变更的 RFC 流程

## 哪些改动可以直接提 PR

以下改动可以直接通过普通 PR 推进：

- 明确的缺陷修复
- 文档补充与错字修正
- 测试补强
- 不改变公共接口和架构边界的重构
- 明确局部、兼容的性能优化

## 哪些改动必须先走 RFC

以下改动在实现前必须先提交 RFC，并以 Draft PR 的形式讨论：

- Kernel / Module / Adapter 分层边界变更
- Core API 公共接口或跨服务契约变更
- 模块清单、Hook、事件、协议、数据规格变更
- 破坏兼容性的默认行为调整
- 新的基础设施依赖、部署模型或安全边界调整
- 许可、治理、发布策略的重大修改

RFC 流程见 `docs/rfcs/README.md`。

## 本地开发准备

1. 安装 Python 3.12、uv、Node.js 20+ 和 Corepack。
2. 运行 `uv sync --all-packages --group dev`。
3. 运行 `corepack pnpm install`。
4. 根据 `.env.example` 准备本地 `.env`，至少配置一个可用的模型提供方 API key。
5. 需要完整联调时，运行 `corepack pnpm infra:up`，再执行 `uv run alembic upgrade head`。

常用启动命令：

```powershell
uv run yggdrasil-core-api
uv run yggdrasil-agent-runtime
uv run yggdrasil-module-host
uv run yggdrasil-worker
corepack pnpm web:dev
```

## 提交前最低验证

按改动范围至少完成以下检查：

- Python 代码：`uv run pytest -q`
- Web 代码：`corepack pnpm web:typecheck`
- Web 代码：`corepack pnpm web:lint`
- Web 代码：`corepack pnpm web:build`
- 基础设施相关：`corepack pnpm infra:smoke`
- 评测或协议相关：补充对应测试或评测命令，并在 PR 描述中写明

如果改动较大，优先拆成多次 PR，而不是一次提交多个不相干主题。

## 提交与评审约定

- 一个 PR 只解决一个清晰问题。
- 改动公共行为时，同时更新 README、开发文档或协议文档。
- 改动如果需要 RFC，请在 PR 中链接 RFC。
- 评审以可验证事实为准：行为变化、兼容性、测试覆盖、迁移路径。
- 维护者可能要求把过大的 PR 先拆分，再继续评审。

## 测试与文档要求

- 新功能要有对应测试或明确说明为什么无法自动化验证。
- 修复缺陷时，优先补一个能复现该缺陷的测试。
- 用户可见变化必须更新文档。
- 新增模块、应用或适配器时，至少补最小使用说明和依赖说明。

## 安全与数据处理

- 不要把真实 key、cookies、token、SSH 私钥或云平台凭据提交到仓库。
- 不要提交未经许可的第三方数据集、模型权重、媒体素材或客户数据。
- 发现安全问题时，不要发公开 issue；按 `SECURITY.md` 处理。

## 社区协作方式

- Bug 请通过 GitHub Issue 模板提交。
- 普通功能请求可以通过 Feature Request 模板提交。
- 重大设计讨论请直接走 RFC，而不是把 issue 当作长期设计文档。

贡献一经合并，即表示你同意你的提交内容按本仓库当前许可证发布。
# 原始设计覆盖检查 v0.1

- 文档状态：Candidate
- 日期：2026-04-16
- 目标：检查原始文档中的设计是否已进入正式规格，避免关键理念在工程化时丢失。

## 1. 结论

原始文档中的多数核心设计已经进入 PRD、协议或数据规格，但此前确实有若干重要项没有被正式化。本次已补齐最关键的可工程化部分。

## 2. 已覆盖并正式化的设计

| 原始设计 | 当前状态 | 落点 |
| --- | --- | --- |
| 根节点三分支 | 已正式化 | [Agent 运行时协议 v0.1](agent-runtime-protocol-v0.1.md) |
| 建树算法 | 已正式化 | [Agent 运行时协议 v0.1](agent-runtime-protocol-v0.1.md) + [记忆与建树数据规格 v0.1](memory-domain-data-spec-v0.1.md) |
| 节点历史 | 已正式化 | [记忆与建树数据规格 v0.1](memory-domain-data-spec-v0.1.md) |
| 从根节点开始并发读取 | 已正式化 | [记忆与建树数据规格 v0.1](memory-domain-data-spec-v0.1.md) |
| 读取时返回子节点名和关联节点名 | 已正式化 | [记忆与建树数据规格 v0.1](memory-domain-data-spec-v0.1.md) |
| 上下文重启 | 已正式化 | [Agent 运行时协议 v0.1](agent-runtime-protocol-v0.1.md) |
| 困难任务上下文整理 | 已正式化 | [Agent 运行时协议 v0.1](agent-runtime-protocol-v0.1.md) + [运行时与工具数据规格 v0.1](runtime-domain-data-spec-v0.1.md) |
| 异步写入与安全停止点 | 已正式化 | [Agent 运行时协议 v0.1](agent-runtime-protocol-v0.1.md) + [运行时与工具数据规格 v0.1](runtime-domain-data-spec-v0.1.md) |
| Sub-Agent 与 PR 机制 | 已正式化 | [协作与治理数据规格 v0.1](collaboration-and-governance-data-spec-v0.1.md) |
| 信息来源标注与推理说明 | 已正式化 | [记忆与建树数据规格 v0.1](memory-domain-data-spec-v0.1.md) |

## 3. 这次新补上的漏项

| 漏项 | 现在如何处理 |
| --- | --- |
| 节点标题是相对父节点的方向 | 已写入 Node 约束 |
| 节点内容约 50 字、最多 200 字 | 已写入 Node.content 约束 |
| 记忆持续参数 k | 已写入 Node.activityK |
| 记忆浮动 | 已写入 Node.floatScore |
| 建树任务 Prompt 暴露主模型偏好 | 已写入 ImportPolicy.treePreferencePrompt |
| 泛型工具分发器 | 已写入 ToolDescriptor / ToolInvocationRecord |
| 模型能力分析与自动任务分配 | 已写入 ModelRouteDecision |
| 项目级导入导出 package | 已写入 ProjectPackageManifest |
| 共享空间三种挂载语义 | 已写入 SpaceMount.mountMode |
| 内核态长期改写“我是谁” | 已写入 AgentIdentityProfile.writePolicy |

## 4. 仍然属于高层策略、尚未冻结为细粒度协议的设计

| 原始设计 | 当前状态 | 说明 |
| --- | --- | --- |
| 自我进化完整闭环 | 部分覆盖 | 目前只冻结到评测、训练数据和模型产物层；完整自进化策略还未冻结 |
| Linux 文件系统式共享记忆库全部语义 | 部分覆盖 | 目前冻结到 Space、Branch、Mount、PermissionTuple；更细的软硬链接语义未冻结 |
| 多媒体模型主动生成图片记忆 | 部分覆盖 | 已预留 Asset、AssetSegment、AssetEmbedding，但生成策略未冻结 |
| 直觉参数 sigma 的调度策略 | 部分覆盖 | 已冻结为 AgentIdentityProfile.intuitionSigma，但具体路由算法未冻结 |

## 5. 不转成产品规格的内容

以下内容来自行为建议文档，更适合作为开发文化或系统提示词素材，而不是正式协议：

- 不要被细节困住。
- 先思考，再行动。
- 把一件事做到底。
- 适度娱乐。
- 打造灵魂与梦想。

这些内容不进入正式数据模型。

## 6. 当前判断

从工程落地角度看，原始文档里没有遗漏掉会直接阻塞第一版实现的关键设计。真正需要继续补的，不再是“有没有想法”，而是把这些规格继续推进到 schema、状态机和 contract test 模板层。
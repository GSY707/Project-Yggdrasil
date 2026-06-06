# 数据规格索引

- 文档状态：Candidate
- 更新时间：2026-05-23
- 目标：模块开发者只看规格即可实现模块，不需要查其他模块代码。
- 关联文档：
  - [PRD v0.1](../PRD-v0.1.md)
  - [协议索引](../protocols/README.md)
  - [Agent 运行时协议 v0.2](agent-runtime-protocol-v0.2.md)
  - [工作树协议 v0.2](work-tree-protocol-v0.2.md)

## 1. 使用原则

这些数据规格是模块开发的正式来源。

- 如果对象、字段、状态、约束没有写在规格里，模块不得假设它存在。
- 如果模块需要新增字段或改变语义，必须先更新规格，再改实现。
- 模块之间通过规格、协议和事件通信，不通过读取彼此内部表结构或内部代码通信。

## 2. 文档列表

### 当前重做入口（v0.2）

- [Agent 运行时协议 v0.2](agent-runtime-protocol-v0.2.md) - 冻结 Boot Prompt、启动、待机、运行、上下文窗口、多 Agent 与结束批准语义。
- [工作树协议 v0.2](work-tree-protocol-v0.2.md) - 冻结工作树作为动态工作记忆和执行栈的节点 schema、状态机、Working Node 标签、摘要上浮和冲突语义。
- [世界构建、初次苏醒与任务启动协议 v0.1](world-build-awakening-task-start-protocol-v0.1.md) - 重新划分“先建世界 / 再醒来 / 再开始工作”的世界级与任务级边界，强调建世界与初次苏醒不得接触具体工作信息，并引入“起始状态”作为任务起点。
- [应用包接口总规范 v0.1](application-package-interface-v0.1.md) - 定义应用包的 manifest、prompt / memory 文件、MCP 服务器、前端界面与控制面 API 接口，明确应用包可携带 memory/ 静态记忆资产，供外部团队直接按契约实现应用包。
- [官方远端数据服务契约 v0.1](remote-data-service-contract-v0.1.md) - 冻结官方远端数据服务上线前的账号、工作区、同步、远端备份、远端删除证明和本地优先边界；当前为计划契约，不代表服务已发布。
- [Graduate Researcher 应用包定义 v0.1](graduate-researcher-app-v0.1.md) - 定义“研究生”应用的目标、预算语义与计划-步骤-动作三层行为模型。
- [Graduate Researcher 测试标准 v0.1](graduate-researcher-test-standard-v0.1.md) - 定义“机器学习研究生”场景的结果验收口径，聚焦自主规划、长任务稳定性与非急性子行为。

### 现有 v0.1 领域数据规格（实现参考）

- [通用数据约定 v0.1](common-data-conventions-v0.1.md)
- [记忆与建树数据规格 v0.1](memory-domain-data-spec-v0.1.md)
- [运行时与工具数据规格 v0.1](runtime-domain-data-spec-v0.1.md)
- [协作与治理数据规格 v0.1](collaboration-and-governance-data-spec-v0.1.md)
- [模块平台数据规格 v0.1](module-platform-data-spec-v0.1.md)
- [资产、导入导出与评测数据规格 v0.1](asset-packaging-evaluation-data-spec-v0.1.md)

## 3. 阅读顺序

1. 先读通用数据约定。
2. 若参与提示词、启动流程或工作流程重做，先读 Agent 运行时协议 v0.2。
3. 再读世界构建、初次苏醒与任务启动协议 v0.1，确认“世界级学习”和“任务级读取工作状态”的边界。
4. 再读工作树协议 v0.2，确认 runtime 如何维护当前工作节点、动态下潜、摘要上浮和结束批准。
5. 再读你所属模块的主领域规格。
6. 然后读协议文档，确认 manifest、hook、事件的接入方式。
7. 最后按需要回读 v0.1 领域数据规格，处理旧数据迁移。

## 4. 模块开发最低合规要求

模块在开始编码前，必须能回答以下问题：

- 模块读写的是哪些正式对象。
- 它能写哪些字段，哪些字段只能由 Kernel 写。
- 它监听哪些事件，发布哪些事件。
- 它实现哪些 hook。
- 它失败时会进入什么状态，恢复时依赖什么快照或补偿数据。

## 5. 当前冻结范围

v0.2 已冻结以下重做边界：

- Boot Prompt 四段：物理接口、根指针、行为宪法、程序计数器恢复。
- RootMountPackage v0.2：语义根指针、索引地图、当前工作节点、邮箱和侧信道占位。
- WorkTreeProtocol v0.2：动态工作记忆、执行栈、Working Node 标签、WorkContextStack 栈式上下文、摘要上浮、等待批准完成。
- 启动模式：cold-standby、hot-resume、work-node-active、approval-review。
- 运行模式：以当前工作树节点为权威指针，`currentFocus` 只作为 UI 摘要。
- 邮箱：使用独立 `mailbox` 表作为主存储，outbox/event 只承载投递和审计。
- Fork：按模型能力、节点复杂度、上下文窗口和成本动态分配预算，并保留父 Agent 合并预算。
- 运行策略：v0.2 作为默认且唯一运行路径。

当前 v0.1 已冻结以下数据边界：

- 记忆树节点、关联边、节点版本、来源标注。
- 导入任务、片段、建树计划、关联建议。
- 任务、运行、快照、工作树、上下文修剪、工具调用、模型路由、worker activity。
- 项目、空间、分支、挂载、权限、PR。
- 模块安装记录、配置绑定、hook 注册、健康报告、outbox。
- 资产、切片、嵌入、项目级 package、评测与训练产物。
- 数据治理 manifest、本地备份快照、本地 task 删除协议、删除证明和官方远端数据服务上线前契约。

## 6. 第一版硬约束

- 第一版虽然只运行单项目，但所有关键对象都必须携带 projectId。
- 第一版必须预留 spaceId 与 branchId，不能把它们留给第二版再补。
- 第一版必须预留 TaskSnapshot 与 paused 状态。
- 第一版 package 的最小正式粒度是项目级。

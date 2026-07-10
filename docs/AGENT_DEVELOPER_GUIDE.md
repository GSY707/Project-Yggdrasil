# Project Yggdrasil Agent 开发者指南

本指南面向“基于本项目开发一个 Agent 应用”的团队。你开发的是可装配的应用包，不需要修改基座内部代码。

开始前先阅读[项目设计哲学](architecture/design-philosophy-and-cognitive-principles.md)。Agent 的语义判断属于 LLM；代码负责来源、权限、资源、安全与恢复等不变量。

## 1. 从一个现有应用开始

选择与目标最接近的目录作为参考：

```text
applications/
├── deep-research/
├── graduate-researcher/
├── coding-greenfield/
└── knowledge-studio/
```

不要直接修改示例来兼容两个场景。复制为新的应用目录，给它独立 `appId`、命名空间和资产。

## 2. 最小应用包

```text
applications/<appId>/
├── yggdrasil.app.yaml
├── config/defaults.json
├── memory/
├── prompt-profiles/main-agent.yaml
├── scenes/generic-default.yaml
├── few-shots/
└── web/dashboard.json
```

- `yggdrasil.app.yaml`：唯一装配入口，声明模块、Prompt、场景、记忆、配置与前端入口。
- `prompt-profiles/`：定义角色、工具、记忆、证据和输出合同。
- `scenes/`：定义具体任务场景 overlay，不重写公共 boot 边界。
- `memory/`：随包发布、可版本化的静态知识与决策卡。
- `few-shots/`：可独立理解的完整工作范式。
- `config/defaults.json`：应用默认值。
- `web/dashboard.json`：普通用户看到的说明、模板、设置与预期产物。

字段和装配合同以[应用包接口总规范](specs/application-package-interface-v0.1.md)为准。

## 3. 用户体验合同

一个可发布应用至少要让使用者看懂：

1. 它适合解决什么问题，不适合什么问题；
2. 启动前需要准备哪些材料；
3. 有哪些任务模板和真实示例；
4. 会产生什么结果，如何判断完成；
5. 哪些内容会发给外部模型服务；
6. 预算、失败、暂停和恢复如何处理。

不要把内部模块名、Prompt ID、MCP server ID 或数据库字段当作普通用户文案。

## 4. LLM 资产设计

- Prompt profile 要声明事实边界、工具策略、记忆策略、证据要求和输出合同。
- 场景只提供当前任务所需偏置，不复制整套系统提示词。
- 出厂记忆应是小而稳定、可寻址的知识卡；运行时记忆写入应用命名空间，不覆盖随包文件。
- 能力和工具按需展开，不把完整工具说明长期塞进上下文。
- 对效果的主张必须通过真实任务验证；单次成功不能升级为稳定能力。

## 5. 本地装配与验证

开发环境与仓库命令统一从[项目开发入口](DEVELOPMENT.md)进入。应用包提交前至少验证：

1. manifest、引用文件和模块依赖都能被发现；
2. `/applications` 中应用可见，详情页没有缺失资产；
3. `dashboard.json` 的任务模板能创建草稿；
4. 附加材料会进入任务目标与运行上下文；
5. 没有模型密钥时只允许草稿，不能误启动；
6. 至少一条真实任务完成，并留下输出、调用与恢复证据；
7. 不包含 API key、客户数据、运行状态或本机路径。

## 6. 深入协议

- [应用 manifest 协议](protocols/yggdrasil-application-manifest-v0.1.md)
- [Agent 运行时协议](specs/agent-runtime-protocol-v0.2.md)
- [工作树协议](specs/work-tree-protocol-v0.2.md)
- [应用包正式示例：Graduate Researcher](specs/graduate-researcher-app-v0.1.md)

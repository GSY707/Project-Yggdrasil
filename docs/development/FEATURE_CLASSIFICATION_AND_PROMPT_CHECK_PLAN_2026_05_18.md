# 功能形态分类与提示词功能检查计划（2026-05-18）

## 目标

本文把当前仓库中的功能按设计分成三类：纯代码、代码与提示词混合、纯提示词；并给出一套可执行的功能检查计划，其中重点覆盖纯提示词功能。

这里的“功能”采用运行时装配单元口径，而不是页面口径：

- 模块是可复用能力单元。
- 应用是场景装配单元。
- Prompt profile、seed template、few-shot 是行为策略资产单元。

## 分类口径

### 1. 纯代码功能

判断标准：功能价值主要由服务、SDK 或模块代码决定；Prompt 只消费结果，不是功能主体。

### 2. 代码与提示词混合功能

判断标准：功能通过应用 manifest 同时装配模块依赖、Prompt profile、seed template、场景配置和前端入口；运行结果同时受代码能力和 Prompt 资产影响。

### 3. 纯提示词功能

判断标准：不新增后端能力，只通过 Prompt 资产改变行为；运行时只负责加载、注册和编译这些资产。

说明：当前仓库几乎没有“完整应用级”的纯提示词产品能力。纯提示词功能主要存在于 Prompt 资产层，以及只负责注册 Prompt 资产的 scene/subagent 模块。

## 当前功能分类

## 一、纯代码功能

### 1. 基座服务与运行时

- `services/core-api`：控制面 API、查询与资产落库。
- `services/agent-runtime`：任务执行主循环、LLM 调用闭环。
- `services/module-host`：模块发现、装配、健康管理。
- `services/worker`：异步任务消费与活动执行。
- `packages/python-sdk/src/yggdrasil_sdk/runtime_kernel`：运行时主循环、快照、安全停止、窗口重启。

### 2. 纯代码模块能力

下列模块的 manifest 只声明运行时或数据处理 hook，没有 `prompt.profiles.register` 或 `prompt.seed-templates.register`：

| 模块 | 主要职责 | 设计归类 |
| --- | --- | --- |
| `text-memory` | 文本导入、检索扩展、写入校验 | 纯代码 |
| `context-pruning` | 上下文裁剪与压缩策略 | 纯代码 |
| `pause-resume` | 暂停/恢复状态保存与回填 | 纯代码 |
| `task-takeover` | 接管协议与工作树恢复 | 纯代码 |
| `shared-memory` | 跨任务共享记忆与权限语义 | 纯代码 |
| `multimodal-memory` | 多模态资产导入与节点物化 | 纯代码 |
| `relation-discovery` | 关系发现、边构建、检索增强 | 纯代码 |
| `memory-organizer` | 记忆组织与治理 | 纯代码 |
| `mcp-bridge` | MCP server/tool 暴露与桥接 | 纯代码 |
| `subagent-pr` | PR 协作与审查相关运行时能力 | 纯代码 |
| `training-lab` | 训练数据集、模型工件与验证门 | 纯代码 |

### 3. 纯代码功能的检查重点

- 以 API、模块 hook、持久化和运行时回归为主。
- 主要验证代码行为、权限、状态流和审计工件，不把 Prompt 文案作为主检查对象。

## 二、代码与提示词混合功能

应用插件是当前仓库最典型的混合功能：每个应用 manifest 都同时声明模块依赖和 Prompt 装配信息。

| 应用 | 设计定位 | 设计归类 |
| --- | --- | --- |
| `yggdrasil.app.base` | 默认兜底应用 | 代码+提示词 |
| `yggdrasil.app.coding-greenfield` | 冷启动开发场景 | 代码+提示词 |
| `yggdrasil.app.coding-inherit` | 继承式开发场景 | 代码+提示词 |
| `yggdrasil.app.deep-research` | 深度研究场景 | 代码+提示词 |
| `yggdrasil.app.epic-writing` | 长篇写作场景 | 代码+提示词 |
| `yggdrasil.app.knowledge-studio` | 知识整理场景 | 代码+提示词 |
| `yggdrasil.app.learning-coach` | 学习辅导场景 | 代码+提示词 |
| `yggdrasil.app.maintenance-ops` | 维护运维场景 | 代码+提示词 |
| `yggdrasil.app.scenic-guide` | 导览解说场景 | 代码+提示词 |
| `yggdrasil.app.software-factory` | 多 coding scene 组合场景 | 代码+提示词 |

这类功能的共同检查点：

- manifest 的模块依赖、默认 Prompt profile、默认 seed template 必须一致。
- 控制面能列出正确的 profile、seed template 和 registered tools。
- 编译后的 Prompt 必须与当前 appId、taskType、activeCapabilities 对齐。

## 三、纯提示词功能

### 1. 纯提示词功能的主要载体

| 载体 | 作用 | 当前位置 |
| --- | --- | --- |
| Prompt profile | 定义角色、行为约束、工具政策、输出契约 | `applications/*/prompt-profiles/`、`modules/subagent-runtime/prompt-profiles/` |
| Seed template | 定义场景身份覆盖、上下文覆盖、执行偏置、检索提示 | `applications/*/scenes/`、`modules/scene-*/scenes/` |
| Few-shot | 提供示例对话，约束微观策略和输出风格 | `applications/*/few-shots/`、`modules/scene-*/few-shots/` |
| Prompt-only 注册模块 | 把 Prompt 资产挂到 registry，不新增业务能力 | `modules/scene-*`、`modules/subagent-runtime` |

### 2. 当前仓库中的纯提示词功能实例

#### 2.1 Prompt profile

- 应用主 Agent profile：`applications/*/prompt-profiles/main-agent.yaml`
- 通用 Sub-Agent profile：`modules/subagent-runtime/prompt-profiles/subagent.yaml`

#### 2.2 Seed template

- 应用级 seed：`applications/base-template/scenes/generic-default.yaml`
- 应用级 seed：`applications/software-factory/scenes/generic-default.yaml`
- 应用级 seed：`applications/knowledge-studio/scenes/generic-default.yaml`
- 场景模块 seed：`modules/scene-coding-new-project/scenes/`
- 场景模块 seed：`modules/scene-coding-inherit-project/scenes/`
- 场景模块 seed：`modules/scene-research-deep/scenes/`
- 场景模块 seed：`modules/scene-writing-epic/scenes/`
- 场景模块 seed：`modules/scene-maintenance-default/scenes/`
- 场景模块 seed：`modules/scene-learning-coach/scenes/`
- 场景模块 seed：`modules/scene-scenic-guide/scenes/`

#### 2.3 Few-shot

- 通用 few-shot：`applications/base-template/few-shots/`
- coding 场景 few-shot：`applications/coding-greenfield/few-shots/`
- 其他应用 few-shot：`applications/epic-writing/few-shots/` 等应用目录
- 场景模块 few-shot：`modules/scene-*/few-shots/`

#### 2.4 Prompt-only 注册模块

下列模块虽然有极薄的一层 Python 注册代码，但从设计职责看属于纯提示词功能承载层：

- `subagent-runtime`
- `scene-coding-new-project`
- `scene-coding-inherit-project`
- `scene-research-deep`
- `scene-writing-epic`
- `scene-maintenance-default`
- `scene-learning-coach`
- `scene-scenic-guide`

这些模块的共同特征是：manifest 只暴露 `prompt.profiles.register` 或 `prompt.seed-templates.register`，不提供记忆处理、状态迁移、任务消费等业务 hook。

## 检查计划

## 一、总检查策略

### 1. 先确认归属，再做检查

每次检查先判断变更属于哪一类：

- 改模块代码：按纯代码功能检查。
- 改应用 manifest 或 app 级 Prompt 绑定：按混合功能检查。
- 只改 profile、seed、few-shot 或 scene/subagent prompt 模块：按纯提示词功能检查。

### 2. 统一检查顺序

所有功能检查都按同一顺序推进：

1. 资产/配置是否可解析。
2. registry 是否能正确暴露。
3. compile preview 是否正确装配。
4. 运行时或场景回归是否通过。
5. 是否污染其他 app/scene。

## 二、纯代码功能检查计划

最小检查集：

- 受影响模块或服务的单测/集成测试。
- hook 注册、持久化、权限、状态流检查。
- 如涉及运行时主链，补 runtime 相关回归。

推荐锚点：

- `tests/runtime/`
- `tests/api/`
- `tests/test_module_catalog.py`
- `tests/test_mcp_bridge.py`

## 三、代码与提示词混合功能检查计划

最小检查集：

- 应用 manifest 是否仍能被 app catalog 发现。
- `/prompting/prompt-profiles`、`/prompting/seed-templates`、`/prompting/registered-tools` 是否与 app 配置一致。
- `/prompting/compile-preview` 输出的 `appId`、`promptProfileId`、`seedTemplateId`、`fewShotRefs` 是否正确。
- 至少跑一条对应场景的回归或套件。

推荐锚点：

- `packages/python-sdk/src/yggdrasil_sdk/app_catalog.py`
- `packages/python-sdk/src/yggdrasil_sdk/application_runtime.py`
- `packages/python-sdk/src/yggdrasil_sdk/prompting.py`
- `services/core-api/src/yggdrasil_core_api/services/prompting_service.py`
- `tests/api/test_persistence_control_plane_api.py`
- `tests/test_g4_multiscene.py`

## 四、纯提示词功能检查计划

纯提示词功能是本计划的重点，必须按下面五层检查。

### P0. 资产结构与引用检查

检查内容：

- YAML/JSON 是否可解析。
- `id`、`version`、`runScope`、`domain` 等必填字段是否完整。
- `fewShotRefs` 是否都能解析到真实资产。
- app manifest 中的 `defaultPromptProfileId`、`subagentPromptProfileId`、`defaultSeedTemplateId` 是否有对应资产。
- `capabilityModules`、`sceneModules` 中的模块是否实际存在。

通过标准：

- 没有悬空引用、重复 ID、缺失文件、非法枚举值。

### P1. 注册与控制面可见性检查

检查内容：

- app catalog 能列出目标应用。
- Prompt registry 能列出目标 profile 与 seed template。
- registered tools 与 active capabilities 一致。

推荐入口：

- `/applications`
- `/prompting/prompt-profiles`
- `/prompting/seed-templates`
- `/prompting/registered-tools`

通过标准：

- 目标 app、profile、seed、tool 都能从控制面读到，并且归属 appId 正确。

### P2. 编译结果检查

检查内容：

- 对受影响 app 执行 `/prompting/compile-preview`。
- 核对 `compiledPrompt.appId`、`promptProfileId`、`seedTemplateId`、`fewShotRefs`。
- 核对 `registeredTools`、`systemSections`、`userSections` 是否与预期一致。
- 如果改动的是 subagent profile，必须额外检查 `runType=subagent`。

通过标准：

- Prompt 编译结果能完整反映当前 Prompt 资产变更，且没有缺失 few-shot 或错误 seed。

### P3. 行为契约审查

这一层是纯提示词功能最容易漏掉、但最重要的一层。

对 Prompt profile，重点审查：

- `systemRole` 是否与应用身份一致。
- `kernelTruth` 是否仍符合仓库的系统约束。
- `behaviorGuidelines`、`toolPolicy`、`memoryPolicy`、`evidencePolicy`、`outputContract` 之间是否互相冲突。
- 是否出现“要求直接执行”与“要求先澄清”之类的策略冲突。
- 是否要求使用当前 app 不具备的工具或模块能力。

对 seed template，重点审查：

- `domain` 与 `scenario` 是否匹配当前应用。
- `identityOverlay`、`contextOverlay`、`executionBias` 是否与场景定位一致。
- `retrievalHints`、`selectionRules` 是否仍匹配当前记忆树/工作树语义。

对 few-shot，重点审查：

- 示例是否仍表达当前希望保留的行为，而不是旧策略。
- assistant 示例是否与 `outputContract` 冲突。
- few-shot 是否过度约束，导致模型忽略真实任务上下文。

通过标准：

- Prompt 资产内部没有逻辑冲突，也没有与当前 runtime 能力边界相冲突的指令。

### P4. 场景回归检查

建议最小命令集：

```powershell
uv run pytest tests/test_prompting_runtime.py tests/api/test_persistence_control_plane_api.py -q
```

下列情况需要追加回归：

- 改 scene seed 或 app 默认 seed：追加 `uv run pytest tests/test_g4_multiscene.py -q`
- 改 resume/restart 语义：追加 `uv run pytest tests/runtime/test_runtime_restart_and_resume.py -q`
- 改 memory 写入、检索或证据表达语义：追加 `uv run pytest tests/runtime/test_runtime_core_and_memory.py -q`

通过标准：

- Prompt 控制面、编译链和对应场景回归全部通过。

### P5. 隔离与回归污染检查

检查内容：

- 一个 app 的 Prompt 变更不能把另一个 app 的 `promptProfileId`、`seedTemplateId` 或 `fewShotRefs` 改掉。
- 共享 Prompt 资产（尤其 `subagent-runtime` 和 `base-template`）变更后，至少抽查两个应用。
- 如果修改的是通用 few-shot 或通用 subagent profile，必须覆盖跨场景检查。

通过标准：

- 变更只影响预期 app/scene；共享资产变更的影响范围已被显式验证。

## 五、Prompt 变更分级检查矩阵

| 变更类型 | 必做检查 |
| --- | --- |
| 单个 few-shot 文案调整 | P0 + P1 + P2 + 最小命令集 |
| Prompt profile 的角色/工具/输出契约调整 | P0 + P1 + P2 + P3 + 最小命令集 |
| Seed template 调整 | P0 + P1 + P2 + P3 + `tests/test_g4_multiscene.py` |
| App manifest 绑定变更 | 混合功能检查全套 + P0/P1/P2 |
| `subagent-runtime` Prompt 变更 | P0 + P1 + P2（含 subagent）+ P3 + 至少两个 app 抽查 |
| `base-template` 通用 Prompt 变更 | P0 + P1 + P2 + P3 + 至少两个 app 抽查 |

## 六、推荐检查顺序

如果当前只想先把纯提示词功能检查跑通，建议按下面顺序执行：

1. 先看资产文件本身和 manifest 绑定。
2. 再看控制面列表是否能列出 profile、seed、tool。
3. 再跑 compile preview，确认最终装配结果。
4. 最后补场景回归，确认没有跨 app 污染。

这个顺序能最快把“引用没接上”“编译没生效”“行为契约互相打架”“改坏了别的应用”这四类问题分开定位。

## 证据锚点

以下文件是本分类和检查计划的直接设计依据：

- `README.md`
- `docs/DEVELOPER_GUIDE.md`
- `docs/modules/applications-and-scenes.md`
- `packages/python-sdk/src/yggdrasil_sdk/app_catalog.py`
- `packages/python-sdk/src/yggdrasil_sdk/application_runtime.py`
- `packages/python-sdk/src/yggdrasil_sdk/prompting.py`
- `services/core-api/src/yggdrasil_core_api/services/prompting_service.py`
- `applications/coding-greenfield/yggdrasil.app.yaml`
- `applications/base-template/yggdrasil.app.yaml`
- `modules/subagent-runtime/yggdrasil.module.yaml`
- `modules/scene-coding-new-project/yggdrasil.module.yaml`
- `tests/api/test_persistence_control_plane_api.py`
- `tests/test_g4_multiscene.py`
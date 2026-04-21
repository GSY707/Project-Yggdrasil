# 世界树计划开发 TODO（执行版）

## 当前阶段
- M1 到 M9 的正式工程主线已经落地，当前仓库不再处于“骨架占位”阶段。
- M9 第二阶段模块化能力已经完成后端实现、数据库迁移、控制面 API、Web 页面和正式评测补齐。
- 当前主问题已经从“把模块能力做出来”切换为“把控制面、CI 门禁、回归谱系和长期质量治理做深做稳”。
- 当前第一优先级：把新的 M9 control-plane suite、Web 控制面行为回归和运维门禁继续固化为长期质量基线。

## 规格入口
- docs/PRD-v0.1.md
- docs/protocols/README.md
- docs/specs/README.md
- docs/specs/agent-runtime-protocol-v0.1.md

## 代码盘点

### 统计口径
- 统计范围：仓库内 .py、.ts、.tsx、.json、.toml、.yaml、.yml、.css 正式工程与配置文件。
- 排除范围：.venv、node_modules、.next、build/dist、.git、本地临时状态目录与评测 sandbox。
- 不包含 markdown 文档，因此 docs 中的大量正式规格文档不纳入下面的代码统计。

### 分类标准
- 占位代码：接口形状已经固定，但返回的是假数据、空结果或演示值，不能承载正式业务。
- 临时代码：仅服务于一次性调试或过渡，不应长期保留。
- 正式工程代码：后续应继续沿用的服务、模块、SDK、控制面、评测和基础设施代码。

### 统计结果
- 占位代码：0 个文件。
- 临时代码：0 个文件。
- 正式工程代码：190 个文件。

### 占位代码清单
- 当前无。

### 临时代码清单
- 当前无。

## 已完成资产
- [x] PRD、ADR、协议和数据规格已经形成第一版正式文档。
- [x] Monorepo 工作区、共享 SDK、服务、模块、适配器与基础设施已经形成稳定边界。
- [x] M1-M8 的正式能力已经落地并通过回归、benchmark、live、ops 验证。
- [x] M9 模块已完成：shared-memory、pause-resume、multimodal-memory、relation-discovery、memory-organizer、training-lab。
- [x] Core API 已暴露 assets、training、prompting 等正式资源面。
- [x] Web 已提供资产、训练、Prompt 控制面，不再只停留在总览数字。
- [x] PromptCompiler、prompt artifact、工具注册和编译预览已经进入正式控制面。
- [x] 新增 M9 control-plane regression suite，并补齐相关 API 回归。
- [x] TypeScript baseUrl 弃用问题已经处理，前端配置已切到未来兼容写法。

## 未来工作重排

### M1-M8（已完成）
- [x] M1 清理骨架债务。
- [x] M2 持久化底座。
- [x] M3 模块宿主与事件总线。
- [x] M4 text-memory 第一条纵向链路。
- [x] M5 主 Agent 第一条闭环。
- [x] M6 Sub-Agent 与 PR 最小闭环。
- [x] M7 Web 控制台升级为正式工作台。
- [x] M8 评测与运维底座。

### M9. 第二阶段模块化能力（已完成）
- [x] 多模态记忆模块。
- [x] 自动整理与软遗忘模块。
- [x] 主动关联发现模块。
- [x] 高级权限与共享记忆空间模块。
- [x] 训练与蒸馏实验模块。
- [x] 任务暂停与无感恢复的完整产品化交付。
- [x] 正式控制面资源：assets、dataset versions、model artifacts、prompt artifacts。
- [x] 正式控制面页面：资产、训练、PromptOps。
- [x] 正式评测补充：M9 acceptance、M9 control-plane regression。
- 验收：M9 能力已经具备正式 API、正式 Web 页面、正式回归与验收链路，而不是停留在模块内部实现。

## 当前最该做的 10 件事
1. 把 CI 扩成分层门禁，纳入 M9 control-plane suite、Alembic 检查和 compose smoke。
2. 给 Web 控制面补行为回归与 smoke，覆盖资产导入、训练实验和 Prompt 预览。
3. 提升多模态 embedding 质量，替换当前 keyword-hash-v1 启发式向量方案。
4. 提升 relation-discovery 的语义与结构推断质量，降低纯词重叠带来的误连边。
5. 为 training-lab 增加 dataset diff、artifact promotion 与更细的验证门。
6. 为 Prompt 控制面增加 artifact 详情展开、invocation diff 和 profile version 审计。
7. 把资产、训练和 Prompt 统计纳入工作台总览卡片与快捷链路。
8. 为共享空间、权限 tuple、safe-stop 和恢复链补更细粒度的审计视图。
9. 把 live LLM、pause/resume 和记忆树验收结果沉淀为长期趋势指标。
10. 补充部署、环境模板与运维手册，降低本地和服务器联调成本。

## 明确不该现在做的事
- 不要为了追求“看起来更聪明”而在证据不足时写隐式推断逻辑。
- 不要让模块绕过 shared SDK 和正式协议直接读写彼此内部实现。
- 不要把本地状态目录、评测 sandbox 或生成产物重新纳入正式代码盘点。
- 不要在没有门禁和回归的前提下扩大控制面写入入口。

## 一句话原则
- 当前项目已经进入“正式产品化与长期质量治理”阶段，优先级应放在门禁、评测、控制面和质量提升，而不是回到骨架式开发。
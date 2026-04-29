# 世界树计划开发 TODO（执行版）

## 当前阶段
- M1 到 M9 的正式工程主线已经落地，当前仓库不再处于”骨架占位”阶段。
- **当前已切换为质量巩固阶段：停止新功能开发，专注修复已知 bug 与完善测试覆盖。**
- 核心决策：规模超前于验证，在真实用户验证到来之前优先打通一条端到端核心路径并夯实测试基线。

## 质量巩固计划（当前执行中）

### Phase 0 — 修复已知 Bug（先修再测）
- [x] 修复 `runtime_kernel.py` pause-request 检测 race condition（L862 覆写 + L1080 不刷新）
- [x] 为 pause-resume race condition 补充专项回归测试

### Phase 1 — 补全关键路径测试（目标：核心路径 100% 有测试）
- [x] Pause-Resume 专项：执行中途发出 pause，worker 必须在下一轮停下
- [x] Pause-Resume 专项：pause → resume 后上下文正确恢复
- [x] Pause-Resume 专项：连续 pause / resume 不累积状态污染
- [x] 权限元组验证：read-only mount 拒绝写入
- [x] 权限元组验证：exclusive-read mount 拒绝第二挂载者
- [x] 权限元组验证：无权限 Space 访问被拒绝
- [x] 错误恢复：LLM provider 5xx 时 task 状态正确回滚（不卡在 `running`）
- [x] 错误恢复：Redis 不可用时 pause 操作返回明确错误
- [x] 错误恢复：Resume 时快照损坏/缺失返回明确错误而非崩溃
- [x] Live LLM：将 `YGGDRASIL_DISABLE_LIVE_LLM` 改为 `slow` marker，CI nightly 跑

### Phase 2 — 构建 CI 门禁
- [x] `pytest.ini` 补充 `slow` marker 定义
- [x] 写 `scripts/check_migrations.sh`：验证 Alembic 头与 ORM 一致
- [x] 写 compose smoke test：启动 infra stack，调 `/health`（`scripts/smoke_test.sh`）
- [x] 配置 GitHub Actions 三层 workflow（PR / merge / nightly）

### Phase 3 — 稳定性与边界测试
- [x] 规模测试：1000 节点树的检索延迟基准
- [x] 规模测试：10 万词 fragment 导入的内存和时间上界
- [x] 并发安全：2 个 worker 同时 pause 同一 Task 不产生双重快照
- [x] 并发安全：Sub-agent 并发写同一 Space 不产生数据竞争
- [x] Hook 故障隔离：一个 module hook 抛异常，其他模块和主流程继续

### Phase 4 — 质量基线（持续）
- [x] 固化 `evalsuite_benchmark_m8_memory_strategies` 结果为数字基准
- [x] 记录关键 API 路径 P50/P95 延迟基准
- [x] 建立 `QUALITY_BASELINE.md`

### 新功能冻结（Phase 1-3 完成前不做）
- training-lab 扩展（dataset diff / artifact promotion）
- relation-discovery 语义质量提升
- Prompt 控制面板新功能
- Web 工作台统计卡片

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

## 明确不该现在做的事
- 不要在 Phase 1-3 完成前新增功能模块。
- 不要为了追求”看起来更聪明”而在证据不足时写隐式推断逻辑。
- 不要让模块绕过 shared SDK 和正式协议直接读写彼此内部实现。
- 不要把本地状态目录、评测 sandbox 或生成产物重新纳入正式代码盘点。
- 不要在没有门禁和回归的前提下扩大控制面写入入口。

## 一句话原则
- 当前项目已经进入”质量巩固”阶段：先修 bug、补测试、建门禁，然后再考虑扩展。
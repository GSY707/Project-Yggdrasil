# 世界树计划 · 防技术债开发规范

> 本文档定义本项目防止技术债积累的强制规范与建议规范。  
> **强制规范**（前缀 **[必须]**）违反时应阻断 PR 合并；**建议规范**（前缀 **[应当]**）在 Code Review 中提出。  
> 变更须同步更新 `docs/DIRECTORY_REFERENCE.md`。

---

## 1. 文件规模限制

### [必须] Python 文件不得超过 600 行

单个 `.py` 文件超过 600 行通常意味着职责混合。超过时必须在同一 PR 内拆分：
- 按领域（Domain）拆：不同业务领域放不同文件
- 按层（Layer）拆：Repository / Service / Domain Model 分层
- 按生命周期（Lifecycle）拆：启动、运行、关闭逻辑分文件

**当前豁免名单**（存量大文件，须按计划逐步拆分，见[第 9 节](#9-存量技术债清理计划)）：

| 文件 | 当前行数 | 拆分截止里程碑 |
|------|---------|--------------|
| `packages/python-sdk/.../collaboration_runtime.py` | 957 | Gate 2 前 |
| `packages/python-sdk/.../llm_runtime.py` | 853 | Gate 3 前 |
| `packages/python-sdk/.../persistence/module_platform.py` | 847 | Gate 3 前 |
| `packages/python-sdk/.../mcp_bridge.py` | 716 | Gate 3 前 |

新增文件不得进入豁免名单；豁免名单只减不增。

> 2026-05-15 更新：`repositories.py`、`evaluation_runtime.py`、`services.py`、`runtime_kernel.py` 已完成拆分并从豁免名单移除。

### [应当] TypeScript/TSX 文件不超过 400 行

超过时按页面组件（Page）、展示组件（UI）、逻辑 Hook（Logic）、类型定义（Types）分文件。

---

## 2. 异常处理规范

### [必须] 禁止裸 `pass` 吞掉异常

```python
# ❌ 禁止
try:
    do_something()
except Exception:
    pass

# ✅ 正确：非关键路径（如观测链自身）用 DEBUG 日志
try:
    do_something()
except Exception as exc:  # noqa: BLE001
    _logger.debug("non-fatal: %s", exc)

# ✅ 正确：业务关键路径用 WARNING 日志
try:
    do_something()
except Exception as exc:  # noqa: BLE001
    _logger.warning("Failed to update task status (task_id=%s): %s", task_id, exc)
```

**判断标准：**
- 观测/导出链（OTel、Langfuse flush）：`_logger.debug`，注明 non-fatal
- 业务状态更新（DB 写入、状态机转换）：`_logger.warning`，附上关键参数
- 不应吞掉的情况：影响结果正确性的操作必须向上传播异常

### [必须] 每个模块文件须有模块级 logger

```python
import logging
_logger = logging.getLogger(__name__)
```

---

## 3. 质量基线规范

### [必须] 质量基线数字必须来自实测

`docs/QUALITY_BASELINE.md` 中所有数字必须由真实测量产出：
- HTTP 延迟：来自真实压测（wrk / locust / k6）
- 内存峰值：来自 `tracemalloc` 或 `memory_profiler` 测量
- 评测分数：来自 nightly CI 实跑，连续 3 轮稳定后更新

**禁止以下做法：**
```markdown
<!-- ❌ 禁止 -->
| `/tasks/` | GET | ≤ 50 ms | ≤ 200 ms | 尚未实测，基于架构推导 |

<!-- ✅ 正确 -->
| `/tasks/` | GET | 18 ms | 67 ms | 2026-05-10 本机 SQLite，20 并发，wrk 30s |
```

### [应当] 新增关键路径时同步更新基线

每新增一条对外暴露的 API 路径，必须在同一 PR 或后续 1 个里程碑内补齐 benchmark 数字。

---

## 4. 测试规范

### [必须] 测试不得直接修改进程级环境变量

测试用例通过 `os.environ` 直接修改的环境变量必须在 teardown 还原，或使用 `pytest` 的 `monkeypatch` fixture。

```python
# ❌ 禁止
os.environ["YGGDRASIL_DATABASE_URL"] = "sqlite:///:memory:"

# ✅ 正确
def test_something(monkeypatch):
    monkeypatch.setenv("YGGDRASIL_DATABASE_URL", "sqlite:///:memory:")
```

### [必须] 大文件拆分必须配套定向回归

每次拆分大文件后，必须在同一 PR 内运行受影响的测试模块并附上通过输出：

```
uv run pytest tests/test_<affected>.py -v
```

### [应当] 新能力必须覆盖正向 + 异常路径测试

不得只写 happy-path 测试；关键服务边界（权限拒绝、DB 连接失败、LLM 超时）须有对应 test case。

### [应当] CI 门禁测试应在 PostgreSQL 上也能运行

目前所有测试基于 SQLite。新增的稳定性/并发测试应标注 `@pytest.mark.postgres`，以便未来在 PostgreSQL CI 层复用。

---

## 5. 配置与基础设施规范

### [必须] 容器内服务通信必须使用容器内网络名

Docker Compose 内的服务互相通信必须用服务名（Service Name），不得使用 `localhost`：

```yaml
# ❌ 禁止（容器内 localhost 不可路由到其他容器）
LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT: http://localhost:19090

# ✅ 正确
LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT: http://langfuse-minio:9000
```

### [必须] 宿主机可访问端口必须通过环境变量覆盖

所有 `ports:` 映射必须支持 `${YGGDRASIL_*_PORT:-默认值}` 格式，便于本机端口冲突时覆盖。

### [必须] 凭据只能通过环境变量注入，禁止硬编码进代码或配置文件

任何 API Key、密码、Token 类字段必须通过 `os.getenv()` 读取，绝不硬编码。  
`tests/test_secret_hygiene.py` 会扫描文本文件中的 live key 模式，违反者 CI 直接失败。

---

## 6. Prompt 与应用插件规范

### [必须] 应用插件 `fewShotRefs` 不得在 v1 后保持为空

`applications/*/prompt-profiles/main-agent.yaml` 中 `fewShotRefs: []` 且 `version: v1` 仅允许在初始开发阶段保留。进入正式用户验证前，每个应用至少补充 2 条真实 few-shot 示例。

### [应当] 有独立行为指令的应用插件应提供 `scenes/` 文件

`base-template`、`knowledge-studio`、`software-factory` 已有示范。有专属场景覆盖需求的应用应提供 `scenes/` 目录下的场景模板文件。

### [应当] Prompt profile 版本更新须附上变更摘要

修改 `prompt-profiles/` 内文件时，须在 PR 描述中说明变更了哪个策略字段、原因和预期影响。

---

## 7. 分层架构规范

### [必须] 不允许跨层直接导入

- **Route 层**只能调用 **Service 层**，不能直接调用 **Repository 层**
- **Service 层**只能调用 **Repository 层**，不能直接调用 **ORM 层**
- **Module 插件**只能通过 **Hook 协议**与内核通信，不能直接 import SDK 内核模块

```python
# ❌ 禁止（路由直接调用 Repository）
from yggdrasil_sdk.persistence.repositories import TaskRepository

# ✅ 正确（路由调用 Service）
from yggdrasil_core_api.services import TaskService
```

### [必须] 第二阶段能力必须以独立模块交付，不允许回写为内核硬编码

新能力首先检查是否可以通过 Hook 协议、Event 总线或 Module Manifest 实现。只有在协议层确实无法覆盖时，才提 RFC 讨论扩展内核 API。

---

## 8. PR 流程检查清单

每个 PR 合并前，作者须确认：

- [ ] 没有新增超过 600 行的 `.py` 文件（或已记录在豁免名单）
- [ ] 没有新增裸 `pass` 在 `except` 块内
- [ ] 没有在测试中使用 `os.environ[...] = ...` 直接赋值（用 monkeypatch）
- [ ] 容器间通信没有使用 `localhost`
- [ ] 没有硬编码 API Key / Token
- [ ] 新增 API 路径已有对应测试（正向 + 至少一个异常路径）
- [ ] 拆分大文件的 PR 附有定向 pytest 通过截图或日志
- [ ] `docs/DIRECTORY_REFERENCE.md` 如有结构变化已同步更新

---

## 9. 存量技术债清理计划

### 优先级 P0（Gate 1 闭合前处理）

无强制阻塞性存量债，已知配置 Bug 已修复：
- [x] `infra/langfuse-compose.yml` `LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT` 使用 `localhost` → 已修复为 `langfuse-minio:9000`
- [x] 6 处静默 `pass` 吞异常 → 已替换为带 logger 的日志输出

### 优先级 P1（Gate 2 前，必须完成）

**TD-01 · repositories.py 拆分（2831 行）**

当前状态：**已完成**。`repositories.py` 已按领域拆为 `persistence/repositories/` 子包：
```
persistence/
  repositories/
    __init__.py        # 重新导出，保持现有 import 路径兼容
    task.py            # TaskRepository, AgentRunRepository
    memory.py          # NodeRepository, ImportFragmentRepository
    evaluation.py      # EvaluationRunRepository, EvaluationSuiteRepository
    asset.py           # AssetRepository, AssetSegmentRepository
    prompting.py       # PromptProfileRepository, SeedTemplateRepository
    collaboration.py   # PullRequestRepository, ReviewCommentRepository
    platform.py        # 其余平台类 Repository
```
当前状态：已进入固定回归任务类型与评测样本。运行 `corepack pnpm eval:g2:regression` 会检查旧 monolith 文件未复活、拆分子文件仍在 600 行以内、路由层没有绕过 Service 直接导入 Repository。

**TD-02 · services.py 拆分（1411 行）**

当前状态：**已完成**。已按资源域拆为 `services/` 子包，每个路由对应一个 Service 文件：
```
core-api/services/
  task_service.py
  memory_service.py
  evaluation_service.py
  asset_service.py
  prompting_service.py
  collaboration_service.py
  runtime_service.py
```
当前状态：已纳入 `evalsuite_regression_g2_controlled_autonomy`，作为 G2 “复杂文件拆分正式能力”的固定回归样本。

**TD-03 · 补全 Core API HTTP 实测基线**

当前状态：**已完成 SQLite / in-process Core API 实测基线**。`docs/QUALITY_BASELINE.md` 第 2.3 节已经记录 `/tasks`、`/nodes`、`/memory/retrievals` 的 P50 / P95 实测值。

后续 PostgreSQL / wrk 压测作为 Gate 3 前的生产化补测，不再阻塞 Gate 2 本地回归。

### 优先级 P2（Gate 3 前）

**TD-04 · evaluation_runtime.py 拆分（1783 行）**

当前状态：**已完成**。已拆为 `evaluation_runtime/` 子包，包含 bootstrap、suite runner、scorer 等独立文件。

**TD-05 · runtime_kernel.py 拆分（1200 行）**

当前状态：**已完成**。已拆为 `runtime_kernel/` 子包，包含 root_mount、snapshot、execution_loop 等独立文件。

**TD-06 · 应用插件 fewShotRefs 补全**

为 base-template、coding-greenfield、deep-research、epic-writing 各补至少 2 条 few-shot 示例。

**TD-07 · 补全缺少 scenes/ 的应用插件**

为 coding-greenfield、coding-inherit、deep-research、epic-writing、learning-coach、maintenance-ops、scenic-guide 补充 `scenes/generic-default.yaml`。

### 优先级 P3（长期持续）

**TD-08 · PostgreSQL CI 层**

在 nightly 流水线中新增 `pytest --postgres` job，防止 SQLite 门禁值漂移导致生产问题。

**TD-09 · 前端 frontend-sdk/src/index.ts 拆分（551 行）**

按功能域拆为：api-client、types、hooks、utils 四个子模块。

---

## 10. 工具配置参考

### ruff 推荐规则（防技术债相关）

在 `pyproject.toml` 的 `[tool.ruff.lint]` 中确保启用：

```toml
[tool.ruff.lint]
select = [
  "S110",   # try-except-pass (禁止裸 pass 吞异常)
  "BLE001", # blind-exception (裸 Exception 捕获须有注释豁免)
  "G",      # flake8-logging-format (日志格式规范)
]
```

### pre-commit 推荐钩子

```yaml
# .pre-commit-config.yaml（参考）
- repo: local
  hooks:
    - id: python-file-size
      name: Python file size check (600 lines max)
      language: python
      entry: python scripts/check_file_size.py
      types: [python]
```

# 测试套件 CPU 时间开销分析 2026-04-29

- 文档状态：Draft
- 日期：2026-04-29
- 范围：本地 Windows 环境下的 pytest 集成测试
- 关联代码：
  - [tests/conftest.py](../../tests/conftest.py)
  - [packages/python-sdk/src/yggdrasil_sdk/persistence/coordination.py](../../packages/python-sdk/src/yggdrasil_sdk/persistence/coordination.py)
  - [packages/python-sdk/src/yggdrasil_sdk/persistence/bootstrap.py](../../packages/python-sdk/src/yggdrasil_sdk/persistence/bootstrap.py)
  - [packages/python-sdk/src/yggdrasil_sdk/persistence/module_platform.py](../../packages/python-sdk/src/yggdrasil_sdk/persistence/module_platform.py)
  - [packages/python-sdk/src/yggdrasil_sdk/mcp_bridge.py](../../packages/python-sdk/src/yggdrasil_sdk/mcp_bridge.py)
  - [packages/python-sdk/src/yggdrasil_sdk/prompting.py](../../packages/python-sdk/src/yggdrasil_sdk/prompting.py)
  - [packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py](../../packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py)
  - [packages/python-sdk/src/yggdrasil_sdk/runtime_kernel.py](../../packages/python-sdk/src/yggdrasil_sdk/runtime_kernel.py)
  - [services/worker/src/yggdrasil_worker/registry.py](../../services/worker/src/yggdrasil_worker/registry.py)

## 1. 先给结论

这套测试当前的总耗时，主要不是 CPU 被打满，而是大量等待。

更具体地说：

1. 测试默认已经关闭实时 LLM。
2. 当前最大等待源不是 LLM，而是每个测试都去连接一个不可达的 Redis 端口并等待失败。
3. 把这类等待剥掉之后，CPU 主要花在运行时编排、Prompt 编译、模块目录同步、MCP bridge 工具发现、SQLite/SQLAlchemy 操作，以及 JSON/Pydantic 序列化上。
4. 即使去掉 Redis 等待后，剩余的大头也仍然不是纯 CPU 计算，而是 MCP 子进程 stdio、TestClient 请求链路和 SQLite 文件 I/O 这类等待。

一句话版本：

当前 pytest 更像是在“反复做控制面装配 + 子进程工具发现 + 本地持久化 + 等待失败连接”，而不是在做重型数值计算，更不是在等待真实 LLM 推理。

## 2. 为什么可以直接把 LLM 等待基本排除掉

测试夹具在 [tests/conftest.py](../../tests/conftest.py) 里为每个测试设置了：

- `YGGDRASIL_DISABLE_LIVE_LLM=1`

这意味着本地 pytest 默认不会走真实在线模型调用，而会进入 [packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py](../../packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py) 的 fallback 路径。

所以用户问题里的“去除等待 LLM 的时间后，CPU 在干什么”，在这个仓库的默认测试配置里，实际上已经接近默认状态了。

## 3. 测量方法

### 3.1 原始全量 pytest

命令：

```powershell
python -m pytest -q --durations=25
```

结果：

- 61 个测试
- 58 passed，3 failed
- 总墙钟时间 632.33 s

最慢的测试基本集中在这些路径：

- runtime pause/resume 闭环
- M9 acceptance 闭环
- M8 benchmark
- subagent / collaboration 闭环
- module-host control-plane
- persistence / workbench / observability 控制面

### 3.2 单次夹具成本拆解

针对 [tests/conftest.py](../../tests/conftest.py) 中的共享数据库初始化和每 test 夹具，做了单独测量：

| 步骤 | 墙钟时间 | CPU 时间 | 说明 |
| --- | ---: | ---: | --- |
| `initialize_schema()` | 772.5 ms | 171.9 ms | 仅 session 级执行一次 |
| `truncate_all_tables()` | 14.2 ms | 15.6 ms | 主要是 SQLite + SQLAlchemy 删除语句 |
| `ensure_workspace_bootstrap()` | 26.6 ms | 15.6 ms | 默认工作区与基础记录补齐 |
| `Redis flushdb` 到 `127.0.0.1:6390` | 2046.8 ms | 0.0 ms | 几乎纯等待，CPU 基本不工作 |
| 每 test 总夹具成本（5 次平均） | 2071.7 ms | 约 30 ms 级 | 主体就是 Redis 连接失败等待 |

这里最关键的测量是：

- Redis 不可达时，单次 `flushdb()` 失败需要约 2046.8 ms 墙钟时间，但 CPU 时间约为 0 ms。

这说明测试总时间里有一大块根本不是 CPU 在算，而是在等连接失败。

### 3.3 去掉 Redis 等待后的“分析版”全量 pytest

为了隔离 CPU 真正的工作内容，额外做了一次分析版运行：

- 把 [packages/python-sdk/src/yggdrasil_sdk/persistence/coordination.py](../../packages/python-sdk/src/yggdrasil_sdk/persistence/coordination.py) 的 `RedisCoordinator.client()` 临时 monkeypatch 成“立即失败”的假客户端。
- 这个运行只用于时间拆分分析，不用于正式回归结论。

分析版全量结果：

- 61 个测试
- 59 passed，2 failed
- 总墙钟时间 163.037 s
- 进程 CPU 时间 21.922 s

从这组数据可以直接得到：

- 原始全量运行和分析版之间相差约 470.07 s 墙钟时间。
- 这部分几乎全部可以归因于 Redis 连接失败等待，而不是 CPU。
- 470.07 / 632.33 ≈ 74.3%，也就是当前原始 pytest 墙钟时间里，大约四分之三都被 Redis 失败等待吃掉了。

同时，即使把 Redis 等待拿掉：

- 剩余 163.037 s 墙钟时间里，真正的 CPU 时间也只有 21.922 s。
- 21.922 / 163.037 ≈ 13.4%。

所以“去掉 LLM 等待”以后，CPU 也并不是一直在忙；它是在一段一段地做控制面装配、编排和序列化，中间仍有大量 I/O 和子进程等待。

## 4. CPU 真正在做什么

下面按路径拆开说。

### 4.1 测试夹具与持久化清理

CPU 会稳定花时间在这些动作上：

- 遍历 SQLAlchemy metadata 并截断所有表
- 打开 SQLite 连接、提交事务
- 初始化 schema（session 级一次）
- 通过 `ensure_workspace_bootstrap()` 补齐默认工作区、Space、Branch 等基础记录

这部分的特点是：

- 有固定成本
- CPU 时间不算大，但每 test 都会发生
- 是“很多小成本叠起来”的典型来源

### 4.2 Runtime 编排与 Worker 分发

在运行时相关测试里，CPU 的主要工作落在：

- [services/worker/src/yggdrasil_worker/registry.py](../../services/worker/src/yggdrasil_worker/registry.py) 的 `run_worker_once()` / `dispatch_work_item()`
- [packages/python-sdk/src/yggdrasil_sdk/runtime_kernel.py](../../packages/python-sdk/src/yggdrasil_sdk/runtime_kernel.py) 的 `execute_main_agent_work_item()`
- pause / resume 状态迁移、snapshot 读写、事件记录、budget 更新

这部分不是重型算法，而是状态机推进：

- 读任务
- 组装运行时上下文
- 调一次 LLM runtime fallback
- 生成写回 payload
- 落库并写运行时事件

### 4.3 Prompt 编译与工具注册解析

去掉实时 LLM 以后，CPU 在模型调用前后的主要工作，落在：

- [packages/python-sdk/src/yggdrasil_sdk/prompting.py](../../packages/python-sdk/src/yggdrasil_sdk/prompting.py) 的 `compile_runtime_prompt()`
- `assemble_prompt_registry()`
- `list_registered_agent_tools()`
- [packages/python-sdk/src/yggdrasil_sdk/tool_runtime.py](../../packages/python-sdk/src/yggdrasil_sdk/tool_runtime.py) 的 `resolve_registered_tool_descriptors()`
- [packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py](../../packages/python-sdk/src/yggdrasil_sdk/llm_runtime.py) 的 `invoke_runtime_completion()`

CPU 在这里做的事情包括：

- 选择应用清单、PromptProfile、SeedTemplate
- 读取应用和模块贡献的 prompt 资产
- 生成 system/user message
- 归并工具描述
- 把请求、prompt artifact、response artifact 写成 JSON 文件

也就是说，LLM 不在线时，CPU 主要是在做“调用前准备”和“调用后落盘”，不是在做推理本身。

### 4.4 模块目录同步与控制面组装

在 module-host、workbench、persistence API 等测试里，CPU 会反复进入：

- [packages/python-sdk/src/yggdrasil_sdk/persistence/module_platform.py](../../packages/python-sdk/src/yggdrasil_sdk/persistence/module_platform.py) 的 `sync_catalog()`
- `_enable_module()`
- [packages/python-sdk/src/yggdrasil_sdk/persistence/bootstrap.py](../../packages/python-sdk/src/yggdrasil_sdk/persistence/bootstrap.py) 的 `sync_module_catalog_snapshot()`
- [services/core-api/src/yggdrasil_core_api/services.py](../../services/core-api/src/yggdrasil_core_api/services.py) 的 workbench / observability / prompting / runtime 汇总逻辑

CPU 在这里干的事，本质上是：

- 扫描模块 manifest
- 计算 install / hook / subscription / health 视图
- 执行模块 enable preflight
- 组装控制面响应 JSON

这类 CPU 开销更像“控制面数据加工”，而不是业务算法。

### 4.5 MCP bridge：墙钟热点很大，但不全是 CPU

最值得单独拎出来的是 [packages/python-sdk/src/yggdrasil_sdk/mcp_bridge.py](../../packages/python-sdk/src/yggdrasil_sdk/mcp_bridge.py)。

它在多组 profile 里都会冒出来，尤其是：

- `sync_mcp_bridge_servers()`
- `_with_server_client()`
- `initialize()`
- `list_tools()`
- `_request()`
- `_reader_loop()`
- `_stderr_loop()`

但这里要注意一个误区：

`mcp_bridge.py` 在墙钟时间上很热，不等于 CPU 在这里做了同等规模的计算。

从 profile 看，真正占墙钟大头的常常是：

- `BufferedReader.readline()`
- 子进程关闭与等待
- stdio JSON-RPC 往返等待

换句话说：

- CPU 在这里会做 JSON 编码/解码、schema 规范化、tool descriptor 构造。
- 但更大的时间花在“等子进程输出一行”“等 JSON-RPC 响应回来”“关闭子进程”上。

所以 MCP bridge 是当前测试里一个非常显著的“墙钟热点”，但它本质上是 I/O + 子进程协同热点，而不只是 CPU 热点。

### 4.6 API 框架、Pydantic 与 JSON 序列化

在 [tests/test_persistence_api.py](../../tests/test_persistence_api.py) 这一类测试里，还能看到大量时间走在：

- Starlette `TestClient`
- httpx request/response 生命周期
- FastAPI 路由分发
- Pydantic `model_validate` / `model_dump`
- JSON 文件读写

这部分对 CPU 的表现是：

- 每次不一定重，但调用频繁
- 容易形成大量碎片化 CPU 时间
- 和 SQLite、文件 I/O、TestClient 线程切换混在一起

## 5. 代表性采样结果

### 5.1 `tests/test_module_host_eventing.py`

分析版采样结果：

- 墙钟 42.415 s
- CPU 5.906 s

最显著的项目内热点：

- `module_platform.sync_catalog()`
- `module_platform._enable_module()`
- `mcp_bridge_module.enable_preflight()`
- `mcp_bridge.sync_mcp_bridge_servers()`
- `mcp_bridge._request()`
- `mcp_bridge._reader_loop()` / `_stderr_loop()`

这说明 module-host 路径里，CPU 主要在做模块 reconcile 与工具发现相关的控制面工作，而墙钟时间主要被 MCP 子进程 stdio 等待拉长。

### 5.2 `tests/test_persistence_api.py`

分析版采样结果：

- 墙钟 30.701 s
- CPU 9.25 s

热点集中在：

- `core_api.services.get_workbench_overview()`
- `persistence.bootstrap.sync_module_catalog_snapshot()`
- `module_platform.sync_catalog()`
- `app_catalog.build_application_catalog_snapshot()`
- `prompting` / `tool_runtime` / `mcp_bridge`

这说明 persistence / workbench / observability 路径里，CPU 的主要工作是“收集和拼装控制面视图”。

### 5.3 `tests/test_runtime_and_pruning.py`

分析版采样结果：

- 墙钟 22.259 s
- CPU 5.844 s

热点集中在：

- `run_worker_once()` / `dispatch_work_item()`
- `runtime_kernel.execute_main_agent_work_item()`
- `llm_runtime.invoke_runtime_completion()`
- `prompting.compile_runtime_prompt()`
- `list_registered_agent_tools()`
- `tool_runtime.resolve_registered_tool_descriptors()`
- `mcp_bridge_tool_descriptors()`

这说明 runtime 路径里，CPU 主要是在做：

- Worker 调度
- Prompt 编译
- 工具描述发现
- fallback 模型调用前后编排
- 结果落库与事件记录

## 6. 对“CPU 一般在干什么”的直接回答

如果不扣掉任何等待，当前测试运行期间 CPU 大部分时间其实并不忙；墙钟时间的大头在等待不可达 Redis 失败，以及等待 MCP 子进程 stdio 响应。

如果把等待 LLM 的时间排除掉：

- 由于测试默认已经禁用 live LLM，这部分本来就很少。
- CPU 真正做的主要是控制面和运行时装配工作，而不是模型推理。

可以把 CPU 工作概括成五类：

1. SQLite / SQLAlchemy 的 schema、事务、清表、仓储 CRUD。
2. Runtime 状态机推进，包括 worker dispatch、pause/resume、snapshot、event/outbox 写入。
3. Prompt 编译、应用/场景模板选择、工具描述解析。
4. 模块目录同步、module-host reconcile、hook/subscription/health 视图构建。
5. JSON / Pydantic / FastAPI / TestClient 这一整套本地控制面序列化与请求分发。

而不是：

- 真实在线 LLM 推理
- 高密度数值计算
- 长时间 CPU 100% 占满的重算法

## 7. 如果要继续优化，优先级应该怎么排

从收益排序看，最先该动的不是“再抠一点 Python 代码”，而是先去掉测试里的大块等待：

1. 让测试环境里的 Redis 不可达时立即走内存 fallback，不要每 test 都等待一次 2 秒级连接失败。
2. 减少 module-host / runtime / persistence 路径中反复触发的 MCP bridge server 同步与子进程启动关闭。
3. 减少每次控制面请求都做的全量 catalog / app catalog / prompt registry 重建。
4. 只有在上面三项收敛后，再去抠 SQLAlchemy、Pydantic、JSON 序列化这些真正的 CPU 热点。

如果目标是“缩短总测试时间”，第 1 和第 2 项远比微调 Python 逻辑更值钱。

## 8. 阶段 1 落地后补充测量

2026-04-29 已补入协调层 backend 选择与短 TTL 熔断，并让 pytest / 隔离评测环境默认使用 `YGGDRASIL_COORDINATION_BACKEND=memory`。

针对原来最明显的夹具热点，补做了一轮最小测量：

| 模式 | Redis URL | 5 次 `flushdb()` 样本（ms） | 平均值 |
| --- | --- | --- | ---: |
| `auto` | `redis://127.0.0.1:6390/15` | 218.43, 203.88, 203.56, 215.89, 203.64 | 209.08 |
| `memory` | `redis://127.0.0.1:6390/15` | 0.01, 0.00, 0.00, 0.00, 0.00 | 0.00 |

补充结论：

1. 仅靠短 TTL 熔断，已经把单次失败等待从之前的约 2 秒级压到约 200 ms 级。
2. 对测试和隔离评测这类不需要真实 Redis 协调的场景，显式切到 `memory` backend 的收益更直接，几乎可以把这一段开销归零。
3. 这进一步证明阶段 1 的主收益来自“不要走无意义的网络失败路径”，而不是优化 Python 计算本身。
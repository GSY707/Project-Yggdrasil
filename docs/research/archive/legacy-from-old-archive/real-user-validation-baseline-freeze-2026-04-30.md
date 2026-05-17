# 世界树计划 · 真实用户验证基线与材料冻结记录

> 记录日期：2026-04-30
> 执行目标：完成真实用户验证第 1 周中的“基线与材料冻结”首轮落地。
> 2026-05-01 补记：Windows / MinIO 端口覆盖与试跑环境前提已同步写入 README、DEVELOPER_GUIDE 与 todo 看板。

---

## 1. 冻结结论

本轮已完成代码级与评测级基线验证，并冻结首轮真实用户验证材料。

当前结论：

- 自动化门禁已通过：pytest、M4-M6 regression、M9 control-plane、M8 live、web:typecheck、web:lint、web:build。
- 完整 infra 冒烟已通过，但当前 Windows 主机需要覆盖 MinIO 端口，不能直接使用默认 `9000/9001`。
- 本轮材料已冻结，可直接进入内部试跑。
- 仍有一个正式放行前缺口：`docs/QUALITY_BASELINE.md` 中 Core API HTTP 延迟仍是目标值，不是实测 P50 / P95。

---

## 2. 基线执行结果

### 2.1 Python 与评测基线

| 命令 | 结果 | 备注 |
|------|------|------|
| `uv run pytest -q` | 通过 | `71 passed, 71 warnings in 114.49s` |
| `corepack pnpm eval:regression` | 通过 | `3/3 cases passed`，`passRate=1.0`，`totalDurationMs=6838.51` |
| `corepack pnpm eval:m9:control-plane` | 通过 | `2/2 cases passed`，`passRate=1.0`，`totalDurationMs=1461.92` |
| `corepack pnpm eval:m8:live` | 通过 | `2/2 cases passed`，`passRate=1.0`，`totalDurationMs=33453.71` |

M8 live 最新结果文件：

- `.yggdrasil/evaluation-sandbox/state/evaluations/evalrun_f97c652ee2954510b90a.json`

### 2.2 Web 基线

| 命令 | 结果 | 备注 |
|------|------|------|
| `corepack pnpm web:typecheck` | 通过 | `tsc --noEmit` 无报错 |
| `corepack pnpm web:lint` | 通过 | `next lint` 无 warnings / errors |
| `corepack pnpm web:build` | 通过 | Next.js 15 生产构建成功 |

### 2.3 Infra 基线

| 命令 | 结果 | 备注 |
|------|------|------|
| `corepack pnpm infra:up` | 条件通过 | 需覆盖 MinIO 端口 |
| `corepack pnpm infra:smoke` | 通过 | 在端口覆盖条件下 `status=ok` |

本机端口例外：

- 默认 `9000` 与 `9001` 在当前 Windows 主机不可用。
- 本轮 E2 验证使用：
  - `YGGDRASIL_MINIO_API_PORT=19000`
  - `YGGDRASIL_MINIO_CONSOLE_PORT=19001`

对应执行方式：

```powershell
$env:YGGDRASIL_MINIO_API_PORT='19000'
$env:YGGDRASIL_MINIO_CONSOLE_PORT='19001'
corepack pnpm infra:up
corepack pnpm infra:smoke
```

---

## 3. 本轮为通过基线而落地的最小修复

### 3.1 评测 CLI 初始化修复

- 文件：`packages/python-sdk/src/yggdrasil_sdk/evaluation_cli.py`
- 变更：移除 CLI 入口处对默认数据库的过早初始化。
- 原因：`eval:*` 在进入隔离 SQLite 评测环境前就尝试连接默认 Postgres，导致命令直接超时失败。

### 3.2 Live 评测审计兼容修复

- 文件：`packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime.py`
- 变更：live tool case 同时兼容 `toolExecutions` 与 `toolExecutionSummaries`。
- 原因：默认审计级别下响应工件不保存完整 `toolExecutions`，原评测逻辑会误判。

### 3.3 Live suite 稳定性修复

- 文件：`packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime.py`
- 文件：`evaluation/suites/m8-live-llm.json`
- 变更：
  - 支持 case 级 `maxToolRounds`
  - 支持 case 级 `allowToolExecution`
  - 对非工具型 live case 关闭工具执行
  - 对工具型 live case 显式要求 `text_memory.retrieve` 与 `context_pruning.plan`
- 原因：原 M8 live smoke 在真实模型下存在无意义工具回环与必需工具遗漏，导致 suite 不稳定。

---

## 4. 材料冻结清单

首轮真实用户验证固定材料如下：

- 验证计划：`docs/research/real-user-validation-plan-2026-04-30.md`
- 任务包：`evaluation/fixtures/real-user-validation/task-pack-2026-04-30.md`
- 评分表模板：`evaluation/fixtures/real-user-validation/scorecard-template-2026-04-30.csv`

建议本轮试跑与竞品对照全部沿用上述三份材料，不再改题、不再改分栏。

---

## 5. 版本冻结锚点

### 5.1 Git 锚点

- 基础提交：`f89133cec58fce7c7d24b2800ee58d7c2aab41bf`

### 5.2 当前工作区状态

本轮验证不是在干净 worktree 上完成，而是在本地变更基础上完成。执行冻结时的工作区状态如下：

```text
M apps/web/tsconfig.tsbuildinfo
M docs/DIRECTORY_REFERENCE.md
M docs/research/test-suite-cpu-time-analysis-2026-04-29.md
M evaluation/suites/m8-live-llm.json
M packages/python-sdk/src/yggdrasil_sdk/evaluation_cli.py
M packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime.py
?? docs/research/real-user-validation-plan-2026-04-30.md
?? evaluation/fixtures/real-user-validation/
?? retain_plan.md
?? safe_stop_retain_plan.md
```

其中与本轮基线直接相关的关键变更为：

- `evaluation/suites/m8-live-llm.json`
- `packages/python-sdk/src/yggdrasil_sdk/evaluation_cli.py`
- `packages/python-sdk/src/yggdrasil_sdk/evaluation_runtime.py`

`retain_plan.md` 与 `safe_stop_retain_plan.md` 为 M8 live 评测过程中生成的工件。

---

## 6. 当前未闭合项

2026-05-01 补记：Windows 主机的 MinIO 端口覆盖与试跑前提说明已进入主文档，因此不再单列为未闭合项。

在进入外部真实用户前，仍需补齐下面事项：

1. 把 `docs/QUALITY_BASELINE.md` 中 Core API HTTP 路径延迟从目标值替换为实测 P50 / P95。
2. 若要对外复述本轮结果，建议先把本地关键改动整理成可追溯提交，避免“冻结版本”和“已验证版本”不一致。

---

## 7. 下一步建议

建议后续按下面顺序继续：

1. 先做 2 到 3 次内部试跑，验证任务包描述、录屏、评分表填写流程是否顺手。
2. 单独补一轮 Core API HTTP 链路的实测 P50 / P95，并回写 `docs/QUALITY_BASELINE.md`。
3. 再进入第 2 周的内部用户与竞品对照。
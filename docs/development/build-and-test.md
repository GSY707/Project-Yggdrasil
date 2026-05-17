# Build and Test

## Environment

- OS：Windows / Linux / macOS 均可（当前仓库有 `.sh` 与 `.ps1` 脚本）。
- Python：3.12（`pyproject.toml` 的 `tool.ruff.target-version = py312`）。
- Python 包管理：`uv`。
- Node 包管理：`pnpm`（`packageManager: pnpm@10.8.1`）。
- 前端：Next.js 15 + React 19（`apps/web`）。

## Install

```powershell
uv sync
corepack pnpm install
```

## Run

后端服务：

```powershell
uv run yggdrasil-core-api
uv run yggdrasil-agent-runtime
uv run yggdrasil-module-host
uv run yggdrasil-worker
```

前端：

```powershell
corepack pnpm web:dev
```

## Build

```powershell
corepack pnpm web:build
```

## Test

Python 测试入口（来自 `package.json` 与 `pytest.ini`）：

```powershell
uv run pytest
uv run pytest -q
corepack pnpm test:python
corepack pnpm test:python:fast
corepack pnpm test:python:slow
corepack pnpm test:python:postgres
```

评测入口：

```powershell
corepack pnpm eval:list
corepack pnpm eval:regression
corepack pnpm eval:m8:benchmark
corepack pnpm eval:m8:live
corepack pnpm eval:m9:control-plane
corepack pnpm eval:m9:acceptance
corepack pnpm eval:g2:regression
corepack pnpm eval:g4:multiscene
corepack pnpm eval:g4:provider-matrix
corepack pnpm eval:g4:provider-matrix:longform
corepack pnpm eval:g4:window-stress
corepack pnpm eval:g4:real-task-parity
```

## Lint / Type Check

```powershell
corepack pnpm check:python:syntax
corepack pnpm web:lint
corepack pnpm web:typecheck
```

## Infra and Ops

```powershell
corepack pnpm infra:up
corepack pnpm infra:down
corepack pnpm infra:smoke
corepack pnpm infra:langfuse:up
corepack pnpm infra:langfuse:down
corepack pnpm ops:backup
corepack pnpm ops:restore
```

## CI Workflow Baseline

以下口径来自 `.github/workflows/ci.yml`、`.github/workflows/pr.yml`、`.github/workflows/nightly.yml`：

- merge/pr smoke（CI 与 PR 一致）

```bash
uv sync --all-packages --group dev
pnpm run check:python:syntax
pnpm install --frozen-lockfile
pnpm run web:lint
pnpm run web:typecheck
pnpm run web:build
uv run pytest -m "not slow"
```

- nightly slow suite

```bash
uv sync --all-packages --group dev
uv run pytest -m slow -n auto --dist loadfile
```

说明：本地回归建议与 CI 保持同一命令口径，避免“本地通过但 CI 失败”。

## Notes

- 未发现 Makefile、tox、nox、cargo 或 go build 入口。
- 运行 live/paid provider 前需确认相关环境变量（如 API key、`YGGDRASIL_ALLOW_PAID_MODELS`）。
- `scripts/smoke_test.sh` 提供基础 smoke 流程（infra + migration + `/health`）。
- `pytest.ini` 定义 `slow` marker，默认 `testpaths = tests`。

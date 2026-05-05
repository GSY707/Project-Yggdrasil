# Project Yggdrasil

[中文版本](README.md)

Project Yggdrasil is the main engineering repository for 世界树计划. It has moved well beyond an early scaffold and now operates as a runnable, testable, resumable, and extensible long-running agent system.

## Overview

- FastAPI, SQLAlchemy, Alembic, and Redis power the backend control plane and persistence flow.
- Next.js 15 and React 19 provide the web workbench.
- The module layer already includes formal implementations for text memory, context pruning, pause and resume, shared memory, multimodal memory, relation discovery, training workflows, and sub-agent collaboration.
- The repository also includes evaluation suites, observability hooks, backup and restore flows, and local infrastructure orchestration.

## Core Capabilities

- Formal task execution lifecycle with pause, resume, safe stop, sub-agents, and PR collaboration.
- Persistent memory tree pipeline with retrieval, shared spaces, permissions, multimodal assets, relation discovery, and memory governance.
- PromptOps flow with PromptCompiler, seed templates, prompt artifacts, request and response audit trails, and tool execution traces.
- Evaluation and operations support including regression suites, benchmarks, compose smoke checks, backups, and restore flows.

## Architecture

The system keeps a Kernel / Module / Adapter split:

- Kernel provides the shared runtime, control plane, PromptOps, evaluation, and operational capabilities.
- Modules extend the platform through hook-based, independent packages.
- Adapters integrate external model providers and media capabilities.
- Applications compose scenario-specific agent behavior, prompts, and UI configuration on top of the platform.

## Open Source Collaboration

This repository is fully open source under AGPL-3.0. The repository-wide default is simple: anything committed here is assumed to be publicly distributable, except real credentials.

Read these first before contributing:

- [Contribution Guide](CONTRIBUTING.en.md)
- [Governance](GOVERNANCE.en.md)
- [Security Policy](SECURITY.en.md)
- [Code of Conduct](CODE_OF_CONDUCT.en.md)
- [Open Source Boundary](docs/OPEN_SOURCE_BOUNDARY.en.md)
- [RFC Process](docs/rfcs/README.en.md)

Major design changes must go through the RFC process before implementation if they affect architecture boundaries, public interfaces, protocols, module lifecycle, compatibility guarantees, or security boundaries.

## Quick Start

### Install dependencies

```powershell
uv sync
corepack pnpm install
```

Prepare a local `.env` from `.env.example` and configure at least one model provider API key. Never commit real credentials.

### Start the services

```powershell
uv run yggdrasil-core-api
uv run yggdrasil-agent-runtime
uv run yggdrasil-module-host
uv run yggdrasil-worker
corepack pnpm web:dev
```

### Baseline validation

```powershell
uv run pytest -q
corepack pnpm web:typecheck
corepack pnpm web:lint
corepack pnpm web:build
```

## Evaluation And Operations

Evaluation commands:

```powershell
corepack pnpm eval:list
corepack pnpm eval:regression
corepack pnpm eval:m8:benchmark
corepack pnpm eval:m8:live
corepack pnpm eval:m9:control-plane
```

Operations commands:

```powershell
corepack pnpm infra:up
corepack pnpm infra:down
corepack pnpm infra:smoke
corepack pnpm ops:backup
corepack pnpm ops:restore
corepack pnpm real-user:prepare
corepack pnpm real-user:scorecard --csv .\evaluation\fixtures\real-user-validation\scorecard-2026-05-04.csv
```

`real-user:prepare` creates an isolated sandbox outside the repository for pilot runs, including a copied workspace, isolated state root, frozen task materials, and activation scripts. Pilot runs should not write back into the engineering repository.

## Documentation Map

- The Chinese developer guide remains the deepest engineering reference: `docs/DEVELOPER_GUIDE.md`
- Full directory map: `docs/DIRECTORY_REFERENCE.md`
- Protocol index: `docs/protocols/README.md`
- Specs index: `docs/specs/README.md`
- Open source boundary and governance entry points are available in English

## Current Focus

The current project focus is now centered on Gate 2: productizing controlled autonomy, stabilizing repeated pilot runs, and closing the remaining latency and large-file regression gaps.
# User Adoption Surface Audit - 2026-06-03

## Purpose

This audit reviews the parts of Project Yggdrasil that decide whether a new user can and wants to use the system: user interface, Web workbench, settings, installation, local launch, packaging, and user-facing documentation.

The current product surface is still too command-line and operator-console oriented. The system has real capabilities, but an external user has to assemble too much context before reaching the first successful task.

## Executive Judgment

The codebase already contains the core ingredients of a usable product:

- A Next.js Web workbench at `apps/web`.
- A formal Core API with task, memory, asset, application, prompt, evaluation, observability, and runtime-control routes.
- Application packages under `applications/` with manifests, defaults, prompt profiles, memory assets, and dashboard metadata.
- Python console scripts for core services and operations.
- Docker Compose files for local dependencies.

The main gap is not raw capability. The main gap is the first-user path:

1. Install dependencies.
2. Start all required services.
3. Confirm health and model-provider settings.
4. Pick an application.
5. Create and start a task.
6. Watch progress.
7. Read the result and continue.

Today that path is split across README, developer docs, CLI commands, environment variables, service processes, and a Web UI that mostly assumes data already exists. The product needs to make the Web/app path the default and push CLI commands into an advanced mode.

## Current User-Facing Surfaces

### Web Workbench

Main files:

- `apps/web/app/components/sidebar-nav.tsx`
- `apps/web/app/components/overview-page.tsx`
- `apps/web/app/components/tasks-page.tsx`
- `apps/web/app/components/task-detail-page.tsx`
- `apps/web/app/components/applications-page.tsx`
- `apps/web/app/components/application-detail-page.tsx`
- `apps/web/app/components/assets-page.tsx`
- `apps/web/app/components/prompting-page.tsx`
- `apps/web/app/components/evaluations-page.tsx`
- `apps/web/app/api/core/[...path]/route.ts`

What exists:

- Navigation for overview, tasks, memory nodes, collaboration, assets, training, applications, MCP, prompting, evaluations, and observability.
- Task details support runtime control actions: Safe-Stop, pause, resume, retry, budget top-up, approve completion, and request revision.
- Assets page can ingest text into the formal asset/memory pipeline.
- Applications page can list and activate application packages.
- Application detail page can edit `importantConfig` and show effective config/dashboard metadata.
- Prompting page supports compile preview.
- Evaluations page can run suites from the Web UI.
- MCP page supports workspace/config sync and server enable/disable actions.

Main gap:

- The Web UI still behaves like an internal operations console. It is good for inspecting and controlling an already-running system, but it is not yet the default path for creating a meaningful first task.

Concrete mismatch:

- Core API exposes `POST /tasks` and `POST /tasks/{taskId}/start` in `services/core-api/src/yggdrasil_core_api/api/routes/tasks.py`.
- `apps/web/app/components/tasks-page.tsx` currently only lists, searches, filters, and opens existing tasks.
- `docs/USER_GUIDE.md` describes clicking "new task" in the task page, but the current task list page does not provide that first-run create/start flow.

### Application Packages

Main files:

- `applications/*/yggdrasil.app.yaml`
- `applications/*/config/defaults.json`
- `applications/*/web/dashboard.json`
- `docs/specs/application-package-interface-v0.1.md`

What exists:

- Application manifests define scene modules, capability modules, prompt profiles, seed templates, memory namespaces, defaults, and dashboard metadata.
- Example applications already communicate different user value propositions: `graduate-researcher`, `deep-research`, `coding-greenfield`, `knowledge-studio`, `learning-coach`, and others.
- The Web workbench can activate applications and show their dashboard quick actions.

Main gap:

- Application value is hidden behind technical IDs and JSON. For external users, applications should be first-class entry points with task templates, expected outputs, required tools, model/provider prerequisites, and a clear "start" action.

### Settings and Configuration

Main files:

- `.env.example`
- `applications/*/config/defaults.json`
- `apps/web/app/components/application-detail-page.tsx`
- `apps/web/app/components/mcp-bridge-page.tsx`
- `packages/python-sdk/src/yggdrasil_sdk/mcp_bridge.py`
- `services/core-api/src/yggdrasil_core_api/services/runtime_service.py`

What exists:

- Environment variables cover database, Redis, NATS, state root, Core API base URL, workspace paths, audit level, paid-model flag, Langfuse/OTel, and provider API keys.
- Application `importantConfig` can override defaults.
- MCP bridge workspace and server state can be managed from the Web UI.

Main gap:

- Settings are not yet user-grade. They are raw environment variables or raw JSON.
- There is no first-run settings checklist, provider key validation, test-call action, model availability view, budget warning, or guided fix when a dependency is missing.

### Installation and Local Launch

Main files:

- `README.md`
- `docs/DEVELOPER_GUIDE.md`
- `docs/development/build-and-test.md`
- `infra/docker-compose.yml`
- `infra/langfuse-compose.yml`
- `package.json`
- `pyproject.toml`
- service `pyproject.toml` files under `services/`

What exists:

- Python dependencies install with `uv sync`.
- Node dependencies install with `corepack pnpm install`.
- Infrastructure starts with `corepack pnpm infra:up`.
- Service scripts exist:
  - `uv run yggdrasil-core-api`
  - `uv run yggdrasil-agent-runtime`
  - `uv run yggdrasil-module-host`
  - `uv run yggdrasil-worker`
- Web starts with `corepack pnpm web:dev`.
- Ops scripts cover infra smoke, backup/restore, and real-user validation sandbox preparation.

Main gap:

- A user has to run too many commands in too many terminals.
- `infra/docker-compose.yml` starts dependencies, not the full product.
- There is no one-command local app launcher, no desktop installer, no complete Docker Compose product stack, and no packaged release artifact for the Web app plus services.

### Packaging and Release Surface

What exists:

- Python packages use Hatchling and console scripts.
- Frontend package is private and buildable with Next.js.
- Root `package.json` aggregates development, evaluation, infra, ops, and Web scripts.

Main gap:

- Packaging is developer-workspace packaging, not user-product packaging.
- There is no explicit release matrix for:
  - source developer mode,
  - local self-hosted product mode,
  - Docker Compose product mode,
  - desktop/local tray app mode,
  - hosted/SaaS mode.

## Adoption Risks

### P0 Risks

1. First task is not Web-native.
   The API can create/start tasks, but the Web task page does not expose a complete create/start wizard.

2. First-run setup is fragile.
   Users must infer which services, environment variables, model keys, database state, and ports are required.

3. Documentation overpromises some UI behavior.
   `docs/USER_GUIDE.md` describes a task creation flow that is not present in `tasks-page.tsx`.

4. Command documentation can drift from `package.json`.
   During this audit, stale `eval:g4:window-stress` and `eval:g4:real-task-parity` command references were found in user-facing docs even though the root scripts no longer expose those commands.

5. Product value is buried.
   The homepage says the control plane has switched to runtime data, but it does not immediately answer: "What can I do now?"

6. Settings are not safe for non-developers.
   Raw JSON and raw environment variables make common mistakes hard to see and hard to fix.

### P1 Risks

1. Application packages do not yet feel like products.
   They have manifests and dashboards, but not scenario-specific task launchers, examples, or outcome previews.

2. Installation is too manual.
   A multi-service, multi-terminal launch sequence is acceptable for contributors, not for ordinary users.

3. Web UI terminology is internal.
   Terms like M9, PromptOps, route decision, mailbox, side channel, and appId are useful for maintainers but should not dominate first-run user flows.

4. File ingestion is limited.
   The assets page accepts source text and metadata, but not a polished file upload/import workflow for common user material.

5. No onboarding evidence loop.
   The system needs a visible "setup complete -> task running -> result produced" path with health checks and clear recovery actions.

### P2 Risks

1. No clear external support boundary inside the product UI.
   Open-source boundary docs exist, but the UI does not explain local data, keys, privacy, or support expectations.

2. No opinionated default app.
   For most users, choosing among many internal application IDs is weaker than presenting 2-3 high-value workflows.

3. No product screenshots or demos in the main entry.
   README and user docs explain many systems but do not sell the first experience.

## Recommended Direction

The project should switch from "CLI-first system with a Web console" to "Web-first local product with CLI as advanced mode."

Do not add a thin compatibility layer around the old command-line path. Build a direct product path:

1. A first-run setup page.
2. A provider/settings page with validation.
3. An application picker.
4. A task creation and start wizard.
5. A task progress/result page.
6. A one-command product launcher.

## P0 Implementation Plan

### P0.1 Add Web Task Create/Start Flow

Owner files:

- `apps/web/app/components/tasks-page.tsx`
- `apps/web/app/components/applications-page.tsx`
- `apps/web/app/components/application-detail-page.tsx`
- `apps/web/app/lib/use-api-resource.ts`
- `packages/frontend-sdk/src/types.ts`
- `services/core-api/src/yggdrasil_core_api/api/routes/tasks.py`
- `services/core-api/src/yggdrasil_core_api/services/task_service.py`

Requirements:

- Add a prominent "New task" action from `/tasks`, `/applications`, and each application detail page.
- Let the user choose an application first.
- Present task templates from application dashboard/config metadata instead of raw empty fields.
- Submit `POST /tasks`.
- Immediately offer "Start now" using `POST /tasks/{taskId}/start`.
- After start, route to `/tasks/{taskId}`.
- Show launch errors with specific remediation: missing provider key, API unreachable, worker not running, database unavailable, or no active application.

Acceptance:

- A new user can create and start a task without using the CLI.
- `docs/USER_GUIDE.md` matches the implemented UI.

### P0.2 Add First-Run Setup and Health Page

Owner files:

- `apps/web/app/components/overview-page.tsx`
- `apps/web/app/components/workbench-primitives.tsx`
- `services/core-api/src/yggdrasil_core_api/api/routes/health.py`
- `services/core-api/src/yggdrasil_core_api/api/routes/workbench.py`
- `.env.example`

Requirements:

- Show a setup checklist when required dependencies are missing.
- Check Core API, database, Redis/coordination backend, worker queue, model provider key, state root, and workspace path.
- Provide direct actions/commands only as fallback text; the primary state should be visual and actionable.
- Keep internal metrics below the fold.

Acceptance:

- A user opening `http://localhost:3000` can immediately see what is ready and what blocks the first task.

### P0.3 Replace Raw Application JSON With Guided Important Settings

Owner files:

- `applications/*/config/defaults.json`
- `applications/*/web/dashboard.json`
- `apps/web/app/components/application-detail-page.tsx`
- `docs/specs/application-package-interface-v0.1.md`

Requirements:

- Extend dashboard/defaults metadata with a small settings schema for user-editable fields.
- Render typed controls for common fields: provider, model, budget, workspace, output style, memory namespace, tool permissions.
- Keep raw JSON behind an advanced toggle.
- Validate before saving.

Acceptance:

- A non-developer can configure an application without editing JSON.

### P0.4 Add One-Command Local Product Launch

Owner files:

- `packages/python-sdk/src/yggdrasil_sdk/ops_cli.py`
- `package.json`
- `infra/`
- `README.md`
- `docs/USER_GUIDE.md`
- `docs/DEVELOPER_GUIDE.md`

Requirements:

- Add a product-mode launcher command, for example `corepack pnpm yggdrasil:up` or `uv run yggdrasil-ops launch`.
- It should start infra, apply migrations, start Core API, Agent Runtime, Module Host, Worker, and Web.
- It should print a single final URL: `http://localhost:3000`.
- It should fail early with useful checks for Docker, ports, Python/Node dependencies, and missing provider keys.

Acceptance:

- A user can follow a short "install, configure key, launch, open URL" guide.

## P1 Implementation Plan

### P1.1 Turn Application Packages Into Scenario Launchers

- Add `taskTemplates` or equivalent dashboard metadata to application packages.
- For each top application, include 1-3 example tasks and expected outputs.
- Start with `graduate-researcher`, `deep-research`, `coding-greenfield`, and `knowledge-studio`.

### P1.2 Improve Assets Import

- Add file upload from browser.
- Show parsed segments, summary node, import status, and failures.
- Let users attach imported assets to a new task.

### P1.3 Rewrite User Docs Around First Success

- `README.md`: short value proposition, screenshot/demo, one-command launch, first task.
- `docs/USER_GUIDE.md`: user workflow, not control-plane inventory.
- `docs/DEVELOPER_GUIDE.md`: keep service internals and contributor setup.
- Delete stale UI claims after the actual Web flow lands.

### P1.4 Productize Runtime Status

- Rename internal labels in first-run pages.
- Keep route decisions, mailbox, side-channel, PromptOps, and M9 terms available in advanced/debug sections.

## P2 Implementation Plan

### P2.1 Release Packaging Matrix

Define supported modes:

- Developer workspace mode.
- Local product mode.
- Full Docker Compose product mode.
- Optional desktop wrapper mode.
- Optional hosted mode.

Each mode must state install commands, update commands, data location, backup/restore path, and support boundary.

### P2.2 Public Demo and Screenshots

- Add screenshots after the Web create/start flow exists.
- Add a short demo script that creates a real task with a low-cost provider.
- Keep internal evaluation material separate from product onboarding.

### P2.3 User Safety and Privacy Surface

- Show where local data, API keys, logs, traces, and artifacts are stored.
- Explain what leaves the machine when live providers are used.
- Add deletion/export actions before broad external use.

## Documentation Corrections From This Audit

The current code starts the local API services on:

- Core API: `5000`
- Agent Runtime: `5001`
- Module Host: `5002`

`apps/web/app/api/core/[...path]/route.ts` also defaults `YGGDRASIL_CORE_API_BASE_URL` to `http://127.0.0.1:5000`.

This audit updates the user-facing docs and `.env.example` to match the current service behavior. If the project later chooses `8000/8001/8002` as the official product port range, change the service startup code and Web proxy default in the same patch.

This audit also removes stale README command examples for `eval:g4:window-stress` and `eval:g4:real-task-parity`. Those suite files may remain as historical or specialist assets, but they should not be presented as runnable user commands unless root `package.json` exposes matching scripts.

## Bottom Line

The project is not missing ambition or backend capability. It is missing a product-shaped entrance.

The highest-leverage next step is not another CLI. It is a direct Web-first first-run path: setup, pick application, create task, start task, watch progress, read result.

# Contribution Guide

[中文版本](CONTRIBUTING.md)

Thanks for contributing to Project Yggdrasil.

This repository is fully open source under AGPL-3.0. The default rule is that code, docs, samples, evaluation materials, and implementation discussions committed here must be safe for public distribution. Do not submit real API keys, access tokens, passwords, private data, or third-party materials without redistribution rights.

## Read These First

- `docs/OPEN_SOURCE_BOUNDARY.en.md`: repository boundary, support matrix, and stability expectations
- `GOVERNANCE.en.md`: maintainer roles and decision model
- `SECURITY.en.md`: private vulnerability disclosure process
- `CODE_OF_CONDUCT.en.md`: community behavior expectations
- `docs/rfcs/README.en.md`: RFC flow for major design changes

## Changes That Can Go Directly Through A PR

These changes usually do not need an RFC first:

- clear bug fixes
- documentation improvements and typo fixes
- test coverage improvements
- refactors that do not change public interfaces or architecture boundaries
- clearly local and compatible performance improvements

## Changes That Must Go Through An RFC First

Submit an RFC before implementation if the change affects any of the following:

- Kernel / Module / Adapter boundaries
- public Core API behavior or cross-service contracts
- module manifests, hooks, events, protocols, or data specifications
- default behavior changes that break compatibility
- new core infrastructure dependencies, deployment models, or safety boundaries
- licensing, governance, or release model changes

See `docs/rfcs/README.en.md` for the full process.

## Local Development Setup

1. Install Python 3.12, uv, Node.js 20+, and Corepack.
2. Run `uv sync --all-packages --group dev`.
3. Run `corepack pnpm install`.
4. Prepare a local `.env` from `.env.example` and configure at least one working model provider API key.
5. For full local integration, run `corepack pnpm infra:up` and then `uv run alembic upgrade head`.

Common startup commands:

```powershell
uv run yggdrasil-core-api
uv run yggdrasil-agent-runtime
uv run yggdrasil-module-host
uv run yggdrasil-worker
corepack pnpm web:dev
```

## Minimum Validation Before Submission

Run the checks that match your change scope:

- Python: `uv run pytest -q`
- Web: `corepack pnpm web:typecheck`
- Web: `corepack pnpm web:lint`
- Web: `corepack pnpm web:build`
- Infrastructure-related changes: `corepack pnpm infra:smoke`
- Evaluation or protocol changes: add and report the relevant focused checks in the PR description

If a change is large, split it into multiple focused PRs instead of mixing unrelated topics.

## Review Expectations

- One PR should solve one clear problem.
- Update README, developer docs, or protocol docs when public behavior changes.
- Link the RFC in the PR whenever the change requires one.
- Reviews focus on observable behavior, compatibility, tests, and migration paths.
- Maintainers may ask large PRs to be split before continuing review.

## Testing And Documentation Expectations

- New features should come with tests or a clear explanation for why automation is not possible.
- Bug fixes should preferably include a regression test.
- User-visible changes must update documentation.
- New modules, applications, or adapters should include at least a minimal usage note and dependency summary.

## Security And Data Handling

- Never commit real keys, cookies, tokens, SSH private keys, or cloud credentials.
- Never commit third-party datasets, model weights, media, or client materials without redistribution rights.
- Do not open a public issue for security problems. Follow `SECURITY.en.md` instead.

## Community Workflow

- Use the GitHub issue templates for bug reports.
- Use the feature request template for normal feature ideas.
- Use RFCs for major design work instead of turning issues into long-lived design documents.

By contributing, you agree that your contributions can be distributed under the current repository license.
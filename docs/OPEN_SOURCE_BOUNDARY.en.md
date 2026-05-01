# Open Source Boundary

[中文版本](OPEN_SOURCE_BOUNDARY.md)

This repository is fully open source under AGPL-3.0.

## General Rule

- Anything committed to this repository is assumed to be public.
- Anything committed here should be safe to redistribute.
- Real API keys, access tokens, passwords, private keys, and other credentials are never part of the repository boundary.

If a material cannot be made public, cannot be redistributed, cannot be discussed in a PR, or cannot be used by tests and CI, it should not enter the repository.

## What Is Explicitly In Scope For Open Source

- source code, scripts, config templates, and CI configuration
- design docs, ADRs, protocol docs, data specs, and RFCs
- publicly distributable sample data, fixtures, evaluation cases, and baselines
- development and operations documentation
- sanitized traces, logs, and screenshots used to explain behavior

## What Must Not Enter The Repository

- real API keys, tokens, cookies, passwords, certificates, or SSH private keys
- third-party datasets, model assets, media, or client materials without redistribution rights
- raw data containing personal information, trade secrets, or sensitive system details
- private-environment-only operational playbooks or integration settings that cannot be described publicly

## Stable Surface Versus Non-Stable Surface

### Public Surfaces We Intend To Keep Compatible

- public protocols under `docs/protocols/`
- externally committed specs under `docs/specs/`
- the public field semantics of `applications/*/yggdrasil.app.yaml` and `modules/*/yggdrasil.module.yaml`
- CLI, API, and workflow entry points explicitly documented in README or public guides

### Public But Not Promised To Be Stable

- internal runtime artifact layout under `.yggdrasil/`
- debug output, artifact directory structure, and intermediate files
- exploratory material under `tmp/` and `docs/research/`
- internal classes, functions, or file layouts not documented as public contracts

## Support Boundary

The current open source support matrix is prioritized as follows:

- Tier 1: Ubuntu environments covered by GitHub Actions, treated as the canonical CI baseline
- Tier 2: documented Windows local development paths in this repository
- Tier 3: macOS and other environments on a best-effort basis

The project currently provides source code, documentation, and self-hosting paths. It does not provide an official hosted SaaS, commercial support, or uptime guarantees.

## Contribution Boundary

- Compatible bug fixes, documentation updates, test additions, and local optimizations can go through normal PR review.
- Changes affecting architecture boundaries, protocols, public interfaces, migration cost, or safety models must go through RFC first.
- Any change that expands permission scope, execution surface, or data exposure must document risks and migration implications in the PR or RFC.

## Data And Confidentiality Rule

- The repository follows a public-by-default, credentials-excluded policy.
- Contributors are responsible for ensuring that submissions do not include real credentials or unauthorized materials.
- Once content enters the repository, it should be assumed that the community can clone it, mirror it, inspect it, and redistribute it.
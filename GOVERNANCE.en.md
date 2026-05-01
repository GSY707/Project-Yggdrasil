# Governance

[中文版本](GOVERNANCE.md)

This repository currently follows a maintainer-led model with public discussion and permanent decision records.

## Roles

### Contributors

Anyone submitting issues, RFCs, documentation, tests, or code is a contributor.

### Maintainers

Maintainers are responsible for:

- reviewing and merging changes
- maintaining CI, documentation, releases, and the security baseline
- deciding whether RFCs are accepted
- handling community conduct issues and security escalations

The current default maintainer is the repository owner `@GSY707`. If the maintainer group grows later, ownership can be split by path or responsibility.

## Decision Model

- Everyday bug fixes, documentation updates, and compatible improvements are decided through normal PR review.
- Major design changes are decided through RFCs.
- The maintainer currently has final decision authority, but important conclusions should be recorded in PRs, issues, or RFCs.

## What Counts As A Major Design Change

The following normally require an RFC:

- changing Kernel / Module / Adapter responsibilities
- changing public interfaces, protocols, data contracts, or module lifecycle
- adding or replacing core infrastructure dependencies
- changing default behavior in ways that create meaningful migration cost
- changing safety boundaries, permission models, release models, or licensing policy

See `docs/rfcs/README.en.md` for the process.

## PR Merge Criteria

Before merging, a PR should usually satisfy all of the following:

- the change has a clear goal and reviewable scope
- relevant CI checks pass
- required documentation and tests are updated
- if an RFC is required, the PR links it and the RFC status allows implementation

## Roadmap And Prioritization

- Project direction is shaped through repository docs, issues, RFCs, and maintainer prioritization.
- Maintainers may decline proposals that do not fit the current phase, are too expensive to maintain, or lack a realistic validation path.
- A rejected proposal is not automatically a bad idea. It only means it is not being adopted right now.

## Dispute Handling

- Start with evidence: tests, baselines, performance data, compatibility impact, and migration cost.
- If a normal PR discussion expands into architecture or public contract territory, move it into an RFC instead of letting the PR absorb the whole design debate.
- If discussion does not converge, the maintainer makes the final call and should explain the main reasons.
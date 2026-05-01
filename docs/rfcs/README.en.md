# RFC Process

[中文版本](README.md)

This directory records major design decisions for Project Yggdrasil.

An RFC is not a replacement for a normal issue. It is the formal mechanism for discussing, reviewing, approving, and recording high-impact changes to architecture boundaries, protocols, public interfaces, compatibility promises, and safety boundaries.

## When An RFC Is Required

An RFC is normally required for changes that:

- change Kernel / Module / Adapter responsibilities
- change Core API behavior, module manifests, hooks, events, or public protocols
- change key data specifications, migration strategy, or compatibility commitments
- introduce new core infrastructure dependencies or deployment models
- change permission models, safety boundaries, release models, or licensing policy

## When An RFC Is Usually Not Required

These changes usually do not need an RFC:

- local bug fixes
- refactors that do not change public behavior
- documentation updates, typo fixes, and test additions
- clearly local and compatible performance improvements

If a PR discussion grows into an architecture or public contract discussion, stop direct implementation and add an RFC.

## File Naming

- Use `NNNN-short-title.md` for new RFCs.
- `NNNN` should be an increasing sequence number.
- Numbering starts at `0001`; `0000-template.en.md` is only a template and is not a formal RFC.

## Status Values

Every RFC should declare one of the following states near the top of the document:

- `Draft`: initial proposal, still being shaped
- `Review`: under formal review
- `Accepted`: approved and allowed to move into implementation
- `Rejected`: not adopted, kept only as history
- `Implemented`: core implementation has landed
- `Superseded`: replaced by a newer RFC

## Recommended Flow

1. Copy `0000-template.en.md` and create a new RFC document.
2. Submit the RFC in a draft PR and describe the problem, design, risks, and migration path.
3. Discuss the RFC itself before implementing the full change.
4. Once maintainers accept it, update the status to `Accepted`.
5. Implementation PRs must link the RFC. If implementation diverges, update the RFC first.
6. After the core work lands, update the RFC status to `Implemented`.

## Minimum Content

Each RFC should answer at least the following:

- what problem exists now and why it matters
- what is in scope and out of scope
- how the proposed design works and which public surfaces change
- what the compatibility and migration cost looks like
- what the risks, alternatives, and rollback path are
- how success will be validated

## Approval Rules

- At the current stage, maintainers decide whether an RFC is accepted.
- Maintainers may ask for a better test plan, migration plan, or risk mitigation before continuing review.
- An RFC that has not been accepted should not move straight into formal implementation.
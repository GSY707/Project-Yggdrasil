# Security Policy

[中文版本](SECURITY.md)

Project Yggdrasil can access workspaces, call models, execute long-running tasks, and coordinate across multiple services. Security issues can therefore affect user code, data, and runtime environments directly. Do not disclose vulnerability details through public issues.

## Supported Scope

Security fixes are currently handled with the following support priority:

| Branch / Version | Status |
| --- | --- |
| `main` | supported |
| latest public release | supported |
| older historical versions | best effort only |

## How To Report A Vulnerability

Prefer GitHub private vulnerability reporting or GitHub Security Advisories. If that path is not enabled yet, do not disclose the issue publicly. Contact the maintainer `@GSY707` directly and include `Security Report` in the title.

Please include as much of the following as possible:

- impact scope and preconditions
- reproduction steps or a minimal PoC
- expected severity and likely impact
- whether the issue involves credential leakage, arbitrary file writes, privilege escalation, sandbox escape, or remote code execution
- suggested mitigations if you already have them

## Response Targets

These are targets, not a legal or commercial SLA:

- acknowledge receipt within 5 business days
- provide an initial triage within 10 business days
- prioritize mitigation guidance or a fix plan for high-severity issues

## Coordinated Disclosure

- Do not publish reproducible vulnerability details before maintainers confirm a fix or mitigation path.
- If the issue is actively exploitable or has wide impact, maintainers may publish mitigations before the full fix lands.
- Once the issue is fixed, the project may disclose impact and resolution details through release notes, a security advisory, or the commit history.

## Current Security Baseline

- API keys must be injected through environment variables only.
- Real credentials, private data, and client data are not accepted into the repository.
- Pilot runs and evaluation runs must use isolated workspaces to avoid writing back into the engineering repository.
- Any change that expands workspace write access, external command execution scope, or data exposure should be treated as high risk and should normally go through an RFC first.
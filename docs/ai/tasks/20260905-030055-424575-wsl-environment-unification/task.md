# WSL 环境统一治理

Task ID: `20260905-030055-424575-wsl-environment-unification`

## 要做什么

Deliver the repository-side WSL environment unification system approved by the user so recurring cross-platform failures are prevented or stopped at task start.

## 不做什么

- /etc/wsl.conf
- Docker Desktop UI settings
- <CODEX_HOME>/config.toml live mutation
- system package installation
- mass project migration
- automatic deletion of .venv or node_modules
- hooks, daemons, per-command wrappers, platform fallbacks, and automatic retries

## 改哪些地方

- config/ai
- schemas/wsl-tool-baseline.schema.json
- schemas/project-environment.schema.json
- scripts/provision-wsl.py
- scripts/doctor-core.py
- scripts/project-env-doctor.py
- scripts/resolve-wsl-path.py
- scripts/bootstrap-local.py
- templates/project
- templates/codex/AGENTS.global.md
- rules/items
- rules/registry/RULES_INDEX.json
- docs/modules/wsl-environment
- docs/CODEX_COMPAT.md
- docs/INSTALL.md
- scripts/README.md
- tests/harness
- tests/fixtures/wsl-environment

## 怎么实现落地

Use layered WSL-native tooling rather than globally installing project packages.

## 怎么验收

- A clean fixture can load and validate the baseline and project declarations.
- Wrong-platform command paths, TEMP values, Python environments, Node artifacts, and Docker fallbacks are diagnosed before project tests run.
- Provisioning and doctor commands are idempotent, JSON-capable, and safe in read-only mode.
- Managed runtime sync is hash-verified and existing unrelated Codex files are preserved.
- The Windows path resolver handles drive paths, spaces, Unicode, malformed input, and missing files deterministically.
- Focused suites and one final full harness pass; independent review covers the latest scoped diff.

## 有什么风险

- Stop before any system-level mutation not already represented as repository code or documentation.
- Stop if a scoped write path overlaps unrelated dirty content and cannot be isolated without user direction.
- Stop if implementation would require guessing an undocumented Codex Local Environment file format.
- Stop if the same blocking condition recurs three goal turns without a safe in-scope alternative.

## 当前状态

- status: `completed`
- current_phase: `review`
- next_action: `none`

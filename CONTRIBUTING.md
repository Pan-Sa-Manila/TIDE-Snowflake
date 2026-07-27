# Contributing to TIDE — Snowflake CoCo Edition

Thank you for your interest in contributing to TIDE! This document provides guidelines and instructions for contributing to the project.

---

## 📋 Table of Contents

- [Code of Conduct](#-code-of-conduct)
- [Before You Start](#-before-you-start)
- [Development Setup](#-development-setup)
- [Architecture Overview](#-architecture-overview)
- [Branching Strategy](#-branching-strategy)
- [Making Changes](#-making-changes)
- [Code Standards](#-code-standards)
- [Commit Convention](#-commit-convention)
- [Pull Request Process](#-pull-request-process)
- [What Not To Do](#-what-not-to-do)

---

## 🤝 Code of Conduct

This project follows a standard Code of Conduct. Be respectful, constructive, and inclusive in all interactions. Harassment, discrimination, and abusive behavior will not be tolerated.

---

## 📖 Before You Start

> **Read [`AGENTS.md`](AGENTS.md) in full before writing any code.**

`AGENTS.md` is the single source of truth for all architectural decisions, coding guardrails, and operational boundaries. It defines:
- The strict "DO NOT" list
- The enforced tech stack (Streamlit, Snowpark, Cortex AI)
- Architecture — sync/async paths
- Naming conventions
- Security constraints

**In any conflict between your assumptions and `AGENTS.md`, the document wins.**

Also read:
- [`docs/DETAILS.md`](docs/DETAILS.md) — business rules (the law; code must match)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — end-to-end system design
- [`docs/SCHEMA.md`](docs/SCHEMA.md) — living schema reference

---

## 🛠️ Development Setup

### Prerequisites

| Tool                | Version     | Purpose                               |
|---------------------|-------------|---------------------------------------|
| **Python**          | 3.11+       | Decision engine, procedures, deploy   |
| **Snowflake CLI**   | Latest      | SQL execution, app deployment         |
| **CoCo CLI**        | Latest      | Build-time AI assistant               |
| **Snowflake Account** | —         | Database & AI (Cortex AI enabled)     |
| **Git**             | Latest      | Version control                       |

### Setup Steps

```bash
# 1. Fork and clone
git clone https://github.com/your-fork/TIDE-Snowflake.git
cd TIDE-Snowflake

# 2. Configure Snowflake connection
# Add to ~/.snowflake/connections.toml:
# [tide]
# account = "your_account"
# user = "your_user"
# password = "your_password"

# 3. Deploy everything (DDL → seed → procedures → agent → app)
python scripts/deploy.py --connection tide

# 4. Run decision engine tests (no Snowflake account needed)
pytest tests/decision -q
```

---

## 🏛️ Architecture Overview

TIDE follows a **two-speed architecture**: synchronous procedures for the chat path, async tasks for background work.

```
Streamlit in Snowflake (3 personas)
  → Stored procedures (sync: intake → investigate → adjudicate → execute)
  → Streams + Tasks (async: summaries, reports, timeout sweep)
  → Event-sourced tables → derived state views
```

| Layer | Responsibility | Key Rule |
|---|---|---|
| **Streamlit pages** | UI for three personas (Customer, Approver, Escalation) | Calls procedures only, never raw DML |
| **Procedures** | Business logic, state transitions, AI orchestration | Thin wrappers; validate with Pydantic, delegate to engine |
| **Decision Engine** | Deterministic adjudication (pure Python) | Zero Snowflake imports; testable locally |
| **SQL / DDL** | Schema, views, streams, tasks | Ordered, idempotent `CREATE OR REPLACE` |

> **Do not skip layers.** Streamlit should never execute DML on core tables directly.

Full details: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

---

## 🌿 Branching Strategy

| Branch        | Purpose                                              | Merge Target |
|---------------|------------------------------------------------------|--------------:|
| `main`        | Protected submission branch — always deployable       | —            |
| `dev`         | Primary integration branch                            | `main`       |
| `feature/*`   | Feature work (e.g., `feature/intake-procedure`)       | `dev`        |
| `fix/*`       | Bug fixes (e.g., `fix/guardrail-g03-ordering`)        | `dev`        |

### Workflow

1. Create a branch from `dev`:
   ```bash
   git checkout dev
   git pull origin dev
   git checkout -b feature/your-feature-name
   ```

2. Make your changes (see [Code Standards](#-code-standards)).

3. Push and open a PR against `dev`.

4. After review and merge to `dev`, changes are batched and merged to `main` for submission.

---

## ✏️ Making Changes

### Adding a New Procedure

1. **SQL Layer** — Add or modify DDL in `sql/` (numbered, idempotent).
2. **Procedure** — Write the Snowpark wrapper in `procedures/`.
3. **Engine** — If it touches adjudication, update `tide_decision/` and add tests.
4. **Streamlit** — Update the relevant page to call the procedure.
5. **Schema doc** — Update `docs/SCHEMA.md` with any new tables/columns.

### Adding a Schema Migration

1. Create or modify the appropriate `sql/NN_*.sql` file.
2. Ensure the migration is idempotent (`CREATE OR REPLACE` / `CREATE IF NOT EXISTS`).
3. Update `docs/SCHEMA.md` to reflect the change.
4. Update `scripts/deploy.py` if the execution order changes.

### Adding a Decision Path

1. Add the routing logic in `tide_decision/routing.py` or `guardrails.py`.
2. Add a test fixture in `tests/decision/bundles/`.
3. Add a test function in `tests/decision/test_routing.py` or `test_guardrails.py`.
4. Verify `test_coverage.py` still passes (it checks every path ID has a test).
5. Update `docs/DETAILS.md` §13 if the path is new.

---

## 📏 Code Standards

### File Naming

| Scope | Convention | Example |
|---|---|---|
| SQL scripts | Numbered prefix | `03_decision_ddl.sql` |
| Python modules | snake_case | `fact_derivation.py`, `intake_turn.py` |
| Streamlit pages | Numbered prefix | `1_Customer.py`, `2_Approver.py` |
| Test files | `test_` prefix | `test_guardrails.py` |

### Python

- **Type hints** on all function signatures.
- **Pydantic** for data validation in procedures.
- **No Snowflake imports** in `tide_decision/` — this is the engine's core constraint.
- **snake_case** for functions/variables, **PascalCase** for classes.
- Follow PEP 8.

### SQL

- **Parameterized queries only.** Use bind variables — never concatenate user input.
- **Snowflake identifiers** in `UPPER_SNAKE_CASE`.
- Always include comments in SQL files explaining the purpose of each statement.
- `CREATE OR REPLACE` for idempotency.

### Streamlit

- Custom CSS lives in **one place**: `ui/theme.py::inject_css()`. No page-local CSS.
- Session state keys in **snake_case**.
- Status conveyed by pill **text**, never color alone.

---

## 💬 Commit Convention

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

| Type       | Use Case                                      |
|------------|-----------------------------------------------|
| `feat`     | New feature                                   |
| `fix`      | Bug fix                                       |
| `docs`     | Documentation changes                         |
| `style`    | Formatting, no logic change                   |
| `refactor` | Code restructuring, no feature/fix            |
| `test`     | Adding or updating tests                      |
| `chore`    | Build process, tooling, dependencies          |
| `sql`      | Snowflake schema, migration, or seed changes  |

### Examples

```
feat(procedures): add intake_turn procedure with cortex classification
fix(engine): correct guardrail ordering — G-03 must precede G-04
docs(schema): update SCHEMA.md with new PROOF_FILES columns
sql(seed): add stale-in-transit scenario for E-13
chore(deploy): update deploy.py to handle agent creation
```

---

## 🔀 Pull Request Process

### Before Opening a PR

- [ ] Read `AGENTS.md` and confirm your changes comply with all rules.
- [ ] All Python uses snake_case naming.
- [ ] All SQL uses parameterized queries (bind variables).
- [ ] Decision engine has zero Snowflake imports.
- [ ] Every new BRL path has a pytest test.
- [ ] `docs/SCHEMA.md` is updated for any schema changes.
- [ ] Chat and event tables remain append-only (no UPDATE/DELETE).
- [ ] No secrets or credentials in committed code.
- [ ] No external HTTP calls or external LLM packages.

### PR Template

```markdown
## Summary
<!-- Brief description of what this PR does -->

## Type of Change
- [ ] Feature
- [ ] Bug Fix
- [ ] Documentation
- [ ] Schema Change
- [ ] Decision Engine
- [ ] Refactor

## Changes Made
<!-- List the specific changes -->

## Layer(s) Touched
- [ ] SQL / DDL (`sql/`)
- [ ] Decision Engine (`tide_decision/`)
- [ ] Procedures (`procedures/`)
- [ ] Streamlit (`streamlit/`)
- [ ] Tests (`tests/`)
- [ ] Docs (`docs/`)
- [ ] Configuration / Tooling

## Checklist
- [ ] Follows `AGENTS.md` guardrails
- [ ] Proper naming conventions
- [ ] Pydantic validation on all procedure inputs
- [ ] Parameterized SQL queries
- [ ] No hardcoded secrets
- [ ] Tests pass (`pytest tests/decision -q`)
- [ ] SCHEMA.md updated (if schema changed)
```

### Review Criteria

PRs will be reviewed for:
1. **Architecture compliance** — Does it follow the two-speed design?
2. **Security** — Are inputs validated? Are queries parameterized? RBAC respected?
3. **Code quality** — Proper types, snake_case, no Snowflake imports in engine?
4. **Test coverage** — Does every decision path have a test?
5. **Documentation** — Is SCHEMA.md updated? Is DETAILS.md still accurate?
6. **Functionality** — Does it work as described?

---

## 🚫 What NOT To Do

> These are hard stops. PRs violating these will be rejected.

- ❌ Do not use any ORM (Drizzle, Prisma, SQLAlchemy ORM mode)
- ❌ Do not use any database other than Snowflake
- ❌ Do not use external LLM endpoints (OpenAI, Anthropic)
- ❌ Do not use Next.js, React, or any external web framework
- ❌ Do not make external HTTP calls from the application
- ❌ Do not use `ACCOUNTADMIN` role in application code
- ❌ Do not concatenate user input into SQL strings
- ❌ Do not add UPDATE or DELETE operations for chat/event tables
- ❌ Do not hardcode business constants — they come from `RULE_CONSTANTS`
- ❌ Do not let an LLM decide refund amounts
- ❌ Do not use pip packages outside the Anaconda channel

---

## 💡 Questions?

If you're unsure about an architectural decision or how to implement something:

1. Check [`AGENTS.md`](AGENTS.md) first.
2. Check [`docs/DETAILS.md`](docs/DETAILS.md) for business rules.
3. Review existing code in the relevant layer for patterns.
4. Open a GitHub Discussion or reach out to the maintainers.

---

*Thank you for contributing to TIDE. Let's build something great on Snowflake. ❄️*

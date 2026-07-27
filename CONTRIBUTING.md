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
- The strict "DO NOT" list (teardown rules from the original stack)
- The enforced tech stack
- The 4-tier data flow pipeline
- Naming conventions
- Security constraints

**In any conflict between your assumptions and `AGENTS.md`, the document wins.**

---

## 🛠️ Development Setup

### Prerequisites

| Tool                | Version     | Purpose                               |
|---------------------|-------------|---------------------------------------|
| **Node.js**         | 20+ LTS     | Runtime                               |
| **npm**             | 10+         | Package management                    |
| **Snowflake Account** | —         | Database & AI (Cortex AI enabled)     |
| **CoCo CLI**        | Latest      | Snowflake provisioning                |
| **Git**             | Latest      | Version control                       |

### Setup Steps

```bash
# 1. Fork and clone
git clone https://github.com/your-fork/TIDE-Snowflake.git
cd TIDE-Snowflake

# 2. Install dependencies
npm install

# 3. Configure environment
cp .env.example .env.local
# Edit .env.local with your Snowflake credentials

# 4. Provision Snowflake (if needed)
cd snowflake
chmod +x init.sh
./init.sh
cd ..

# 5. Start the dev server
npm run dev
```

---

## 🏛️ Architecture Overview

TIDE follows a strict **4-tier unidirectional data flow**:

```
Services (src/services/) → Actions (src/actions/) → Hooks (src/hooks/) → Components (src/components/)
```

| Layer          | Responsibility                                     | Key Rule                                      |
|----------------|-----------------------------------------------------|-----------------------------------------------|
| **Services**   | Direct Snowflake queries via `snowflake-sdk`         | Only place `snowflake-sdk` is imported        |
| **Actions**    | Server Actions — auth + `zod` validation             | Security boundary; returns standardized JSON  |
| **Hooks**      | `@tanstack/react-query` for state/cache              | Wraps server actions, never calls services    |
| **Components** | React UI with `shadcn/ui`                             | Imports hooks, never raw fetch logic          |

> **Do not skip layers.** Components should never import services directly.

---

## 🌿 Branching Strategy

| Branch        | Purpose                                              | Merge Target |
|---------------|------------------------------------------------------|--------------|
| `main`        | Protected submission branch — always deployable       | —            |
| `dev`         | Primary integration branch                            | `main`       |
| `feature/*`   | Feature work (e.g., `feature/ticket-dashboard`)       | `dev`        |
| `fix/*`       | Bug fixes (e.g., `fix/query-param-validation`)        | `dev`        |

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

### Adding a New Feature

1. **Service Layer** — Write the Snowflake SQL query in `src/services/`.
2. **Action Layer** — Create a Server Action in `src/actions/` with `zod` validation.
3. **Hook Layer** — Wrap the action in a React Query hook in `src/hooks/`.
4. **Component Layer** — Build or update the UI in `src/components/`.
5. **Tests** — Verify the full flow works end-to-end.

### Adding a Snowflake Migration

1. Create a new numbered `.sql` file in `snowflake/` (e.g., `006-add-field.sql`).
2. Update `init.sh` to include the new file.
3. Document the schema change in your PR description.

### Adding a shadcn/ui Component

```bash
npx shadcn-ui@latest add <component-name>
```

Components are installed to `src/components/ui/`.

---

## 📏 Code Standards

### File Naming

| Scope                          | Convention      | Example                           |
|--------------------------------|-----------------|-----------------------------------|
| Files & directories in `src/`  | `kebab-case`    | `case-dashboard.tsx`              |
| SQL files                      | Numbered prefix | `003-roles.sql`                   |
| TypeScript types/interfaces    | PascalCase      | `CaseStatus`, `OrderDetails`     |
| React components (exports)     | PascalCase      | `export function CaseCard() {}`  |
| Hooks                          | camelCase       | `useCaseDetails`                  |
| Server Actions                 | camelCase       | `fetchCaseById`                   |

### TypeScript

- **Strict mode** is enforced.
- **No `any` types.** Define proper interfaces in `src/types/`.
- **No `console.log`** in production code.
- Use proper error handling with try/catch.

### SQL

- **Parameterized queries only.** Use the `binds` array — never concatenate user input.
- **Snowflake identifiers** in `UPPER_SNAKE_CASE`.
- Always include comments in SQL files explaining the purpose of each statement.

### Styling

- Use Tailwind CSS utility classes.
- Design tokens via CSS custom properties — **never hardcode hex values** in components.
- Follow `shadcn/ui` patterns for all interactive elements.
- Icons from `lucide-react` only.

### Server Actions

Every Server Action must:
1. Begin with `"use server"` directive.
2. Validate all input with a `zod` schema.
3. Verify user authentication/authorization.
4. Call the service layer (never query Snowflake directly).
5. Return standardized JSON: `{ success: true, data }` or `{ success: false, error }`.

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
| `chore`    | Build process, tooling, dependencies           |
| `sql`      | Snowflake schema, migration, or seed changes  |

### Examples

```
feat(services): add cortex summarize query for escalation cases
fix(actions): validate case-id as UUID before triage lookup
docs(agents): update data flow pipeline diagram
sql(snowflake): add replacement_requests table to SUPPORT schema
chore(deps): update @tanstack/react-query to v5.x
```

---

## 🔀 Pull Request Process

### Before Opening a PR

- [ ] Read `AGENTS.md` and confirm your changes comply with all rules.
- [ ] All files in `src/` use `kebab-case` naming.
- [ ] No `any` types in TypeScript.
- [ ] No `console.log` in production code.
- [ ] All Server Actions validate input with `zod`.
- [ ] All SQL uses parameterized queries.
- [ ] Data flow follows Services → Actions → Hooks → Components.
- [ ] No secrets or credentials in committed code.
- [ ] No external LLM packages imported.

### PR Template

```markdown
## Summary
<!-- Brief description of what this PR does -->

## Type of Change
- [ ] Feature
- [ ] Bug Fix
- [ ] Documentation
- [ ] Snowflake Schema Change
- [ ] Refactor

## Changes Made
<!-- List the specific changes -->

## Architecture Layer(s) Touched
- [ ] Services (`src/services/`)
- [ ] Actions (`src/actions/`)
- [ ] Hooks (`src/hooks/`)
- [ ] Components (`src/components/`)
- [ ] Snowflake SQL (`snowflake/`)
- [ ] Configuration / Tooling

## Checklist
- [ ] Follows `AGENTS.md` guardrails
- [ ] kebab-case file naming
- [ ] zod validation on all inputs
- [ ] Parameterized SQL queries
- [ ] No hardcoded secrets
- [ ] Tested locally
```

### Review Criteria

PRs will be reviewed for:
1. **Architecture compliance** — Does it follow the 4-tier pipeline?
2. **Security** — Are inputs validated? Are queries parameterized?
3. **Code quality** — Proper types, no `any`, no `console.log`?
4. **Naming** — kebab-case files, proper conventions?
5. **Functionality** — Does it work as described?

---

## 🚫 What NOT To Do

> These are hard stops. PRs violating these will be rejected.

- ❌ Do not use any ORM (Drizzle, Prisma, TypeORM, SQLAlchemy)
- ❌ Do not use any database other than Snowflake
- ❌ Do not use external LLM packages (`openai`, `anthropic`, `@ai-sdk/*`)
- ❌ Do not fetch data in Client Components
- ❌ Do not use `ACCOUNTADMIN` role in application code
- ❌ Do not concatenate user input into SQL strings
- ❌ Do not add delete or update operations for chat messages
- ❌ Do not add `console.log` to production code paths
- ❌ Do not use `PascalCase` or `camelCase` for filenames in `src/`
- ❌ Do not skip `zod` validation in Server Actions

---

## 💡 Questions?

If you're unsure about an architectural decision or how to implement something:

1. Check [`AGENTS.md`](AGENTS.md) first.
2. Review existing code in the relevant layer for patterns.
3. Open a GitHub Discussion or reach out to the maintainers.

---

*Thank you for contributing to TIDE. Let's build something great on Snowflake. ❄️*

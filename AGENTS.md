# AGENTS.md — TIDE: Snowflake CoCo Edition

> **Read this file in full before touching ANY code in this repository.**
> This document is the single source of truth for all architectural decisions, coding guardrails, and operational boundaries.

---

## 0. Project Identity

**TIDE** (Triage, Intelligence, and Dispute Engine) is a supervised agentic dispute-resolution platform for online retail support. This edition is a **complete re-architecture** of the original TIDE repository, purpose-built for the **Snowflake CoCo CLI Hackathon 2026**.

The system is a deeply integrated, AI-native data application built exclusively on the **Snowflake AI Data Cloud**, orchestrated via the **Snowflake CoCo CLI**, and powered by **Snowflake Cortex AI**.

---

## 1. Teardown Protocol — STRICT "DO NOT" LIST

> [!CAUTION]
> **Violating any rule below will break the architectural contract of this project.**

| #  | Rule |
|----|------|
| 1  | **DO NOT** use Drizzle ORM, Prisma, TypeORM, Sequelize, or any ORM / abstraction layer. |
| 2  | **DO NOT** use PostgreSQL, SQLite, MySQL, or any database other than **Snowflake**. |
| 3  | **DO NOT** use external LLM endpoints (e.g., `openai`, `anthropic`, `@ai-sdk/openai` npm packages). All AI is via **Snowflake Cortex AI** executed natively in SQL. |
| 4  | **DO NOT** retain the `n8n/` directory, n8n webhook patterns, or any n8n-related code. |
| 5  | **DO NOT** use FastAPI, Flask, Express, or any separate backend server. The backend is **Next.js Server Actions + `snowflake-sdk`**. |
| 6  | **DO NOT** fetch data directly inside Client Components (`"use client"` files). All data flows through hooks that call server actions. |
| 7  | **DO NOT** use `camelCase` or `PascalCase` for file or directory names inside `src/`. Use **kebab-case** exclusively (e.g., `ticket-dashboard.tsx`, `use-order-details.ts`). |
| 8  | **DO NOT** concatenate variables directly into SQL strings. Use **parameterized queries** with the Snowflake SDK's binds array. |
| 9  | **DO NOT** use the `ACCOUNTADMIN` role in any application-level query. All queries must assume `TIDE_APP_ROLE`. |
| 10 | **DO NOT** hardcode hex color values in components. Use CSS custom properties or Tailwind design tokens. |
| 11 | **DO NOT** use `any` as a TypeScript type. Define proper interfaces. |
| 12 | **DO NOT** leave `console.log` in production code. Use proper error handling. |

---

## 2. Enforced Technology Stack

| Layer            | Technology                                                              |
|------------------|-------------------------------------------------------------------------|
| **Frontend**     | Next.js 14+ (App Router), React 18, TypeScript (strict mode)           |
| **Styling**      | Tailwind CSS, `shadcn/ui`, Lucide Icons                                |
| **Backend / DB** | `snowflake-sdk` (Node.js official driver) — raw parameterized SQL only |
| **AI / ML**      | Snowflake Cortex AI (executed natively via SQL)                         |
| **State / Cache**| `@tanstack/react-query`                                                |
| **Validation**   | `zod` for all input validation                                         |
| **Auth**         | Session-based or JWT, validated in Server Actions                       |
| **Orchestration**| Snowflake CoCo CLI                                                     |

---

## 3. Naming Conventions

### 3.1 File & Directory Naming
| Scope                        | Convention       | Examples                                                |
|------------------------------|------------------|---------------------------------------------------------|
| All files/dirs inside `src/` | `kebab-case`     | `ticket-dashboard.tsx`, `case-schema.ts`                |
| SQL migration files          | Numbered prefix  | `001-create-tables.sql`, `002-seed-policies.sql`        |
| Environment files            | Standard         | `.env.local`, `.env.example`                            |
| Root config files            | Standard         | `next.config.mjs`, `tailwind.config.js`, `tsconfig.json`|

### 3.2 Code Naming
| Scope              | Convention     | Examples                                    |
|--------------------|----------------|---------------------------------------------|
| React Components   | PascalCase     | `CaseCard`, `TicketDashboard`               |
| Hooks              | camelCase      | `useOrderDetails`, `useCaseList`            |
| Server Actions     | camelCase      | `createCase`, `fetchCaseById`               |
| Service Functions  | camelCase      | `queryCases`, `insertChatMessage`           |
| TypeScript Types   | PascalCase     | `CaseStatus`, `OrderDetails`               |
| SQL Identifiers    | UPPER_SNAKE    | `TIDE_DB`, `SUPPORT`, `CASES`               |
| Constants          | UPPER_SNAKE    | `REFUND_AUTO_THRESHOLD`, `RETURN_WINDOW_DAYS`|

---

## 4. Project Structure

```text
TIDE-Snowflake/
├── src/
│   ├── app/                  # Next.js App Router pages & layouts
│   │   ├── layout.tsx        # Root layout (imports font + metadata + providers)
│   │   ├── metadata.ts       # Next.js <head> metadata (title, OG, description)
│   │   ├── font.ts           # next/font/google configuration (Inter / Geist)
│   │   ├── (customer)/       # Customer-facing routes
│   │   ├── (approver)/       # Approver dashboard routes
│   │   └── (escalation)/     # Escalation agent routes
│   ├── services/             # Layer 1: Direct Snowflake queries
│   ├── actions/              # Layer 2: Next.js Server Actions
│   ├── hooks/                # Layer 3: React Query hooks
│   ├── components/           # Layer 4: React UI components
│   │   └── ui/               # shadcn/ui components
│   ├── lib/                  # Shared utilities
│   │   └── snowflake-client.ts  # Singleton Snowflake connection pool
│   └── types/                # TypeScript type definitions
├── snowflake/                # CoCo CLI orchestration
│   ├── *.sql                 # DDL, DML, stored procedures
│   └── init.sh               # Bootstrap script via CoCo CLI
├── public/                   # Static assets
├── .env.example              # Required environment variables
├── AGENTS.md                 # ← You are here
├── README.md
├── SECURITY.md
├── CONTRIBUTING.md
└── LICENSE
```

---

## 5. The 4-Tier Data Flow Pipeline

> [!IMPORTANT]
> Data flows in ONE direction only: **Services → Actions → Hooks → Components**.
> Do not mix these layers. Do not skip layers.

### Tier 1 — Services (`src/services/`)

- **Sole responsibility:** Direct database interaction via `snowflake-sdk`.
- The **only** place where `snowflake-sdk` is imported.
- Export async functions that execute raw, parameterized SQL.
- Cortex AI functions are embedded directly into these SQL strings.

```typescript
// ✅ CORRECT — src/services/case-service.ts
import { executeQuery } from '@/lib/snowflake-client';

export async function getCaseSummary(caseId: string) {
  return executeQuery(
    `SELECT SNOWFLAKE.CORTEX.SUMMARIZE(CHAT_TRANSCRIPT) AS SUMMARY
     FROM SUPPORT.CASES WHERE CASE_ID = ?`,
    [caseId]
  );
}
```

### Tier 2 — Actions (`src/actions/`)

- **Sole responsibility:** Next.js Server Actions (files begin with `"use server"`).
- Receive client payloads and act as the **security boundary**.
- **Must** validate all input with `zod` before calling Services.
- **Must** verify user session / auth before processing.
- Return standardized JSON: `{ success: true, data: ... }` or `{ success: false, error: ... }`.

```typescript
// ✅ CORRECT — src/actions/case-actions.ts
"use server";
import { z } from 'zod';
import { getCaseSummary } from '@/services/case-service';

const CaseIdSchema = z.string().uuid();

export async function fetchCaseSummary(caseId: string) {
  const validated = CaseIdSchema.parse(caseId);
  const data = await getCaseSummary(validated);
  return { success: true, data };
}
```

### Tier 3 — Hooks (`src/hooks/`)

- **Sole responsibility:** Client-side state and cache management.
- Uses `@tanstack/react-query` exclusively.
- `useQuery` wraps server actions for fetching/caching.
- `useMutation` wraps POST/PUT/DELETE actions, calling `queryClient.invalidateQueries()` on success.

```typescript
// ✅ CORRECT — src/hooks/use-case-summary.ts
import { useQuery } from '@tanstack/react-query';
import { fetchCaseSummary } from '@/actions/case-actions';

export function useCaseSummary(caseId: string) {
  return useQuery({
    queryKey: ['case-summary', caseId],
    queryFn: () => fetchCaseSummary(caseId),
  });
}
```

### Tier 4 — Components (`src/components/`)

- **Sole responsibility:** React UI rendering.
- Import custom hooks; handle `isLoading`, `isError` states.
- Built with `shadcn/ui` primitives.
- **Never** contain raw fetch logic or direct service imports.

---

## 6. Frontend Architecture Rules

### 6.1 Server vs. Client Components (The Render Boundary)
| Component Type   | Directive       | Allowed Operations                             |
|------------------|-----------------|-------------------------------------------------|
| `page.tsx` files | Server (default)| Read URL params, pass initial data to children  |
| Leaf interactives| `"use client"`  | Buttons, forms, modals, charts, dropdowns       |

- Apply `"use client"` **only** to the lowest possible leaf components.
- All `page.tsx` files **must** remain Server Components.

### 6.2 Global Configuration Isolation
| File                     | Purpose                                                    |
|--------------------------|------------------------------------------------------------|
| `src/app/metadata.ts`   | Exports all `<head>` metadata (title, description, OG)     |
| `src/app/font.ts`       | Configures `next/font/google` (Inter or Geist)             |
| `react-query-provider.tsx` | Client Component wrapping `layout.tsx` with `QueryClientProvider` |

### 6.3 UI Library
- Install and use `shadcn/ui`.
- All shadcn components live in `src/components/ui/`.
- Icons: Lucide Icons (`lucide-react`).

---

## 7. Snowflake & Cortex AI Integration

### 7.1 Snowflake SDK — Connection Singleton
- File: `src/lib/snowflake-client.ts`
- Must implement **connection pooling**.
- Must handle hot-reload connection exhaustion in Next.js dev mode (use `globalThis` pattern).
- Raw SQL only — no ORM, no query builder.

```typescript
// Pattern for hot-reload safety
const globalForSnowflake = globalThis as unknown as {
  snowflakePool: SnowflakePool | undefined;
};

export const pool = globalForSnowflake.snowflakePool ?? createPool(config);

if (process.env.NODE_ENV !== 'production') {
  globalForSnowflake.snowflakePool = pool;
}
```

### 7.2 Cortex AI Functions (Replacing n8n + OpenAI)
These SQL-native Cortex AI functions replace the six n8n workflows:

| Original Workflow | Cortex AI Replacement                                               | Purpose                                  |
|-------------------|----------------------------------------------------------------------|------------------------------------------|
| WF1 — Intake      | `SNOWFLAKE.CORTEX.CLASSIFY_TEXT()` / `SNOWFLAKE.CORTEX.EXTRACT_ANSWER()` | Intent classification & follow-up generation |
| WF2 — Data Pull   | Standard `SELECT` queries against Snowflake tables                   | Compile `information_bundle`             |
| WF3 — Triage      | Deterministic SQL logic (no LLM for the math)                        | Threshold checks, rule evaluation        |
| WF4 — Summary     | `SNOWFLAKE.CORTEX.SUMMARIZE(chat_transcript)`                        | Escalation summaries                     |
| WF5 — Resolution  | `SNOWFLAKE.CORTEX.COMPLETE('model', prompt)`                         | Draft response templates                 |
| WF6 — Report      | `SNOWFLAKE.CORTEX.COMPLETE('model', prompt)`                         | Final case audit report                  |

### 7.3 SQL Safety Rules
- **Always** use parameterized queries with the `binds` array.
- **Never** string-interpolate user input into SQL.
- All input must be validated with `zod` before reaching the service layer.

---

## 8. Business Rules & System Constants

These are the canonical threshold values. They must match exactly in code.

| Constant                     | Value        | Context                                    |
|------------------------------|--------------|--------------------------------------------|
| `REFUND_AUTO_THRESHOLD`      | ฿500         | Triage — refund disputes                   |
| `RETURN_WINDOW_DAYS`         | 7 days       | Triage — from delivery date                |
| `DELIVERY_SLA_BREACH_DAYS`   | 3 days       | Triage — delivery disputes                 |
| `INACTIVITY_TIMEOUT_MINUTES` | 15 minutes   | Chat — auto-close after no customer message|
| `MAX_INTAKE_QUESTIONS`       | 3            | Intake — max follow-up questions           |
| `MIN_REJECTION_REASON_CHARS` | 50           | Approval — rejection reason minimum        |
| `CHAT_POLL_INTERVAL_MS`      | 4000         | Live chat — frontend polling interval      |

### 8.1 Case Status Lifecycle

```
pending_triage → awaiting_customer_proof → pending_triage
pending_triage → awaiting_customer_decision → pending_triage
pending_triage → awaiting_approval → approved_executing → resolved → closed
pending_triage → escalated_human_required → closed
awaiting_approval → rejected_human_required → closed
```

- Only the transitions listed above are valid.
- Server actions must validate every status transition. Invalid transitions return a structured error.
- `closed` is terminal — no further updates permitted.

---

## 9. Security Posture

### 9.1 Role-Based Access Control (RBAC)
- Application code **must not** use `ACCOUNTADMIN`.
- All server actions execute under `TIDE_APP_ROLE`.
- `TIDE_APP_ROLE` has **only** `SELECT`, `INSERT`, and `UPDATE` on the `SUPPORT` schema.
- No `DELETE` privileges at the application level.

### 9.2 Input Validation
- All client payloads **must** be validated with `zod` schemas in Server Actions.
- Validated values are passed to the `binds` array of `snowflake-sdk` — never concatenated.

### 9.3 Environment Variables
All secrets are stored in `.env.local` (never committed). See `.env.example` for the required variables:

```env
SNOWFLAKE_ACCOUNT="your_account_locator"
SNOWFLAKE_USERNAME="tide_service_user"
SNOWFLAKE_PASSWORD="your_password"
SNOWFLAKE_ROLE="TIDE_APP_ROLE"
SNOWFLAKE_WAREHOUSE="TIDE_COMPUTE_WH"
SNOWFLAKE_DATABASE="TIDE_DB"
SNOWFLAKE_SCHEMA="SUPPORT"
NEXT_PUBLIC_APP_URL="http://localhost:3000"
```

### 9.4 Chat Append-Only Rule
- Chat messages are **append-only**. There are no delete or update operations on chat messages.
- This ensures a complete, tamper-proof audit trail for every case.

---

## 10. CoCo CLI & Snowflake Setup

### 10.1 Directory: `snowflake/`
This directory contains all raw SQL scripts for Snowflake provisioning:
- Database creation (`TIDE_DB`)
- Schema creation (`SUPPORT`)
- Table DDL
- Cortex AI–powered stored procedures
- Role and privilege grants
- Seed data

### 10.2 Bootstrap Script: `snowflake/init.sh`
- Executes the SQL files in order via the CoCo CLI.
- Must be lightweight, readable in a terminal buffer.
- Avoids heavy GUI dependencies — designed for keyboard-driven workflows.

---

## 11. Git Branching Strategy

| Branch          | Purpose                                     |
|-----------------|---------------------------------------------|
| `main`          | Protected submission branch                 |
| `dev`           | Primary integration branch                  |
| `feature/*`     | Granular feature branches (e.g., `feature/ticket-dashboard`, `feature/snowflake-client`) |

---

## 12. Code Quality Checklist

Before committing any code, verify:

- [ ] No `console.log` in production code
- [ ] No `any` types in TypeScript
- [ ] All files in `src/` use kebab-case
- [ ] All server actions validate input with `zod`
- [ ] All SQL uses parameterized queries (binds array)
- [ ] Data flow follows: Service → Action → Hook → Component
- [ ] `"use client"` is only on leaf interactive components
- [ ] No direct `snowflake-sdk` imports outside `src/services/` and `src/lib/`
- [ ] No external LLM packages imported
- [ ] Environment variables are never hardcoded

---

*This document governs all development on TIDE: Snowflake CoCo Edition. When in doubt, refer here first.*

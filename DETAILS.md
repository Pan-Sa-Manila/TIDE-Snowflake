# ROAR Engine: Snowflake CoCo Edition (Antigravity IDE Instructions)

## 0. Context & Primary Directive
**ATTENTION IDE:** You are tasked with completely re-architecting the original ROAR repository (`https://github.com/keithruezyl1/ROAR`). This rebuild is specifically targeted for the Snowflake CoCo CLI Hackathon 2026. 

The original codebase relies heavily on a conventional web stack (PostgreSQL, Drizzle ORM, standard OpenAI APIs, and n8n). **You must strip this out entirely.** The new system must be a deeply integrated, AI-native data application built exclusively on the **Snowflake AI Data Cloud**, orchestrated via the **Snowflake CoCo CLI**, and powered by **Snowflake Cortex AI**.

Treat this document as your absolute source of truth for all architectural, structural, and syntactic decisions.

---

## 1. AGENTS.md (IDE Guardrails & Teardown Protocol)
Before scaffolding the project, create an `AGENTS.md` file in the root directory. This file dictates your operational boundaries. Populate it with the following strict rules:

### 🛑 STRICT "DO NOT" LIST (TEARDOWN INSTRUCTIONS)
1. **DO NOT** use Drizzle ORM, Prisma, TypeORM, or any abstraction layer.
2. **DO NOT** use PostgreSQL, SQLite, or any database other than Snowflake. 
3. **DO NOT** use external LLM endpoints (e.g., `openai` or `anthropic` npm packages).
4. **DO NOT** retain the `n8n/` directory or its webhooks.
5. **DO NOT** fetch data directly inside Client Components.
6. **DO NOT** use camelCase or PascalCase for filenames.

### ✅ ENFORCED TECH STACK
*   **Frontend:** Next.js 14+ (App Router), React 18.
*   **Styling:** Tailwind CSS, `shadcn/ui`, Lucide Icons.
*   **Backend/DB:** `snowflake-sdk` (Node.js official driver).
*   **AI/ML:** Snowflake Cortex AI (executed natively via SQL).
*   **State/Caching:** `@tanstack/react-query`.

---

## 2. Frontend Scaffolding & Next.js Architecture
The Next.js frontend must be highly optimized, utilizing a terminal-centric, performance-first approach suitable for enterprise dashboards. 

### A. Naming Conventions & Structure
*   **Kebab-Case Strictly:** Every single file and directory in `src/` must use `kebab-case` (e.g., `ticket-dashboard.tsx`, `use-order-details.ts`, `case-schema.ts`).
*   **Global Config Isolation:** 
    *   Create `src/app/metadata.ts` to export all standard Next.js `<head>` metadata (title, description, OpenGraph). Import this into the root `layout.tsx`.
    *   Create `src/app/font.ts` to configure `next/font/google` (e.g., Inter or Geist). Apply this to the `<body>` tag in the root layout.

### B. The Render Boundary (Server vs. Client)
*   **Pages:** All `page.tsx` files must strictly remain **Server Components**. They are responsible for reading URL parameters and passing initial data down. 
*   **Components:** Add the `"use client"` directive *only* to the lowest possible leaf components that require interactivity (e.g., buttons, forms, modals, or charts). 
*   **UI Library:** Install and utilize `shadcn/ui`. When adding components via the CLI, ensure they populate in a dedicated `src/components/ui/` directory.

---

## 3. The 4-Tier Data Flow Pipeline
You must implement a strict unidirectional data flow. Do not mix these layers under any circumstances.

### 1. Services (`src/services/`)
*   **Responsibility:** Direct database interaction.
*   **Implementation:** The only place where `snowflake-sdk` is imported. These files export async functions that execute raw, parameterized SQL strings against the Snowflake connection pool. Cortex AI functions are embedded directly into these SQL strings.

### 2. Actions (`src/actions/`)
*   **Responsibility:** Next.js Server Actions (using the `"use server"` directive).
*   **Implementation:** These functions receive client payloads and act as the security boundary. They must validate all incoming data strictly using `zod`, verify the user session/auth, and then call the Service layer. They return standardized JSON responses (e.g., `{ success: true, data: ... }`) or throw handled errors.

### 3. Hooks (`src/hooks/`)
*   **Responsibility:** Client-side React hooks for state and cache management.
*   **Implementation:** Exclusively uses `@tanstack/react-query`. 
    *   Use `useQuery` to wrap server actions for fetching and caching data.
    *   Use `useMutation` for POST/PUT/DELETE actions, ensuring `queryClient.invalidateQueries()` is called on success to keep the UI fresh.
    *   *Note to IDE:* Create a `react-query-provider.tsx` (Client Component) to wrap the `layout.tsx` children with the `QueryClientProvider`.

### 4. Components (`src/components/`)
*   **Responsibility:** The React UI.
*   **Implementation:** These components import the custom hooks, handle `isLoading` and `isError` states natively, and render the DOM using `shadcn/ui`. They do not contain raw fetch logic.

---

## 4. Backend Integration: Snowflake & Cortex AI

### A. The Snowflake Node.js SDK
*   Install the official `snowflake-sdk`. 
*   Create a singleton connection utility at `src/lib/snowflake-client.ts`. Ensure it handles connection pooling efficiently so the Next.js dev server doesn't exhaust connections upon hot-reloading.
*   **Raw SQL Only:** Write standard parameterized queries. Ensure that variables are never concatenated directly into strings to prevent SQL injection.

### B. Cortex AI Integration (Replacing n8n & OpenAI)
The original ROAR engine used n8n to orchestrate OpenAI calls. You must translate these logical steps into SQL queries leveraging Snowflake Cortex AI natively.

*   **Intake Classification (Replacing WF1):** Use `SNOWFLAKE.CORTEX.EXTRACT_ANSWER` or `SNOWFLAKE.CORTEX.CLASSIFY` directly in the SQL statement when a new customer message is logged to determine if the intent is "Refund", "Replacement", or "Status Update".
*   **Data Summarization (Replacing WF4):** When an agent opens an escalated case, fetch the summary dynamically using `SELECT SNOWFLAKE.CORTEX.SUMMARIZE(chat_transcript)`.
*   **Actionable Generation (Replacing WF5):** Use `SNOWFLAKE.CORTEX.COMPLETE` to draft response templates based on the specific enterprise context stored in the row.

---

## 5. Local Development Environment & CoCo CLI Setup
While the UI is handled by Next.js, the backend processing should be prepped for Snowflake CoCo CLI deployments. 

*   Create a `snowflake/` directory at the project root for terminal-first orchestration.
*   Write the raw `.sql` setup scripts required to define the `ROAR_DB`, schemas, tables, and Cortex AI-powered stored procedures. 
*   Create an `init.sh` bash script that executes these `.sql` files via the CoCo CLI. Ensure the script is lightweight, readable in a terminal buffer, and avoids heavy GUI dependencies, catering directly to a keyboard-driven workflow.

---

## 6. Security, Environment, and Branching

### A. Environment Configuration (`.env.example`)
Generate a `.env.example` containing strictly the following variables required for the Snowflake driver and Next.js routing:

```env
SNOWFLAKE_ACCOUNT="your_account_locator"
SNOWFLAKE_USERNAME="roar_service_user"
SNOWFLAKE_PASSWORD="your_password"
SNOWFLAKE_ROLE="ROAR_APP_ROLE"
SNOWFLAKE_WAREHOUSE="ROAR_COMPUTE_WH"
SNOWFLAKE_DATABASE="ROAR_DB"
SNOWFLAKE_SCHEMA="SUPPORT"
NEXT_PUBLIC_APP_URL="http://localhost:3000"
```

### B. Security & RBAC Posture
*   The application must not use the `ACCOUNTADMIN` role. 
*   All server actions must assume the `ROAR_APP_ROLE` which should only have `SELECT`, `INSERT`, and `UPDATE` privileges on the `SUPPORT` schema.
*   Input payloads must be sanitized via `zod` before being passed into the binds array of the Snowflake SDK.

### C. Git Branching Strategy
Initialize the git scaffolding with the following structure:
*   `main`: The protected submission branch. 
*   `dev`: The primary integration branch where you (the IDE) will commit your scaffolding.
*   `feature/*`: Use this prefix for granular component generation (e.g., `feature/ticket-dashboard`, `feature/snowflake-client`).
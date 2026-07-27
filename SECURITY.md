# Security Policy — TIDE: Snowflake CoCo Edition

## 🔒 Overview

TIDE handles customer dispute data, order information, payment records, and chat transcripts. Security is not an afterthought — it is a foundational architectural constraint enforced at every layer of the system.

This document outlines the security posture, data handling practices, and vulnerability reporting procedures for this project.

---

## 📋 Supported Versions

| Version         | Supported          |
|-----------------|--------------------:|
| `main` (latest) | ✅ Actively supported |
| `dev`           | ⚠️ Development only — not for production |
| `feature/*`     | ❌ No security support |

---

## 🛡️ Security Architecture

### 1. Snowflake RBAC (Role-Based Access Control)

| Principle | Implementation |
|-----------|----------------|
| **Least-privilege access** | Application code runs under persona-specific roles (`TIDE_CUSTOMER`, `TIDE_APPROVER`, `TIDE_ESCALATION`) — never `ACCOUNTADMIN` or `SYSADMIN`. |
| **Procedure-gated access** | Persona roles cannot DML core tables directly. All mutations flow through `EXECUTE AS OWNER` stored procedures that validate state transitions and business rules. |
| **Secure views** | Customer views filter by `CURRENT_USER()`. Approver views show only the approval queue. Escalation views show only claimed or unassigned escalated cases. |
| **Warehouse isolation** | `TIDE_WH_APP` is dedicated to interactive workloads; `TIDE_WH_TASKS` handles async tasks. No shared warehouse access. |

### 2. Data Protection

| Layer | Control |
|-------|---------|
| **Data residency** | All data resides within the Snowflake AI Data Cloud. No data is transmitted to external LLM providers (OpenAI, Anthropic, etc.). Cortex AI runs natively inside Snowflake. No external HTTP calls. |
| **Encryption at rest** | Managed by Snowflake — AES-256 encryption with automatic key rotation. |
| **Encryption in transit** | All connections to Snowflake use TLS 1.2+. |
| **SQL injection prevention** | All queries use parameterized bind variables. No string concatenation of user input into SQL. |
| **Input validation** | All payloads are validated with Pydantic models in stored procedures before reaching the data layer. |

### 3. Application Security

| Control | Detail |
|---------|--------|
| **Procedures as security boundary** | All state mutations flow through Snowpark Python stored procedures (`EXECUTE AS OWNER`) which validate auth, input, and state legality before writing. |
| **No client-side data mutation** | Streamlit pages call procedures; they never execute raw DML against core tables. |
| **Chat append-only** | Chat messages and case events are insert-only. No delete or update operations exist, ensuring tamper-proof audit trails. |
| **No secrets in the repo** | Connection credentials live in `~/.snowflake/connections.toml` (local-only). Nothing to leak: there are no external API keys because there are no external APIs. |
| **Proof storage** | Proof images are stored in an internal Snowflake stage (`SNOWFLAKE_SSE` encryption), never in tables. |

### 4. Authentication & Authorization

| Aspect | Implementation |
|--------|----------------|
| **User authentication** | Snowflake-native authentication. Streamlit in Snowflake runs as the authenticated Snowflake user. |
| **Role-based access** | User roles (customer, approver, escalation) map to Snowflake roles with specific procedure execute grants and secure view access. |
| **Status transition validation** | Every case status update is validated against the permitted transition map inside the procedure. Invalid transitions raise and write nothing. |
| **Claim-based escalation** | Opening an escalated case claims assignment; other agents see it as read-only. |

---

## 🚨 Reporting a Vulnerability

If you discover a security vulnerability in TIDE, **please do NOT open a public GitHub issue.**

### How to Report

1. **Email:** Send a detailed report to the project maintainers at the email address listed in the repository's contact information.
2. **Include:**
   - A description of the vulnerability
   - Steps to reproduce
   - Potential impact assessment
   - Any suggested fixes (optional but appreciated)

### Response Timeline

| Action | Timeline |
|--------|----------|
| Acknowledgment of report | Within **48 hours** |
| Initial triage and severity assessment | Within **5 business days** |
| Fix development and testing | Based on severity (Critical: 7 days, High: 14 days, Medium: 30 days) |
| Public disclosure | After fix is deployed and verified |

### Severity Classification

| Severity | Description | Examples |
|----------|-------------|----------|
| **Critical** | Remote code execution, data exfiltration, authentication bypass | SQL injection, exposed credentials, unauthenticated admin access |
| **High** | Privilege escalation, data corruption, denial of service | Unauthorized status transitions, bypassing RBAC, procedure grant escalation |
| **Medium** | Information disclosure, business logic bypass | Leaking case details to unauthorized users, circumventing triage rules |
| **Low** | UI-level issues, minor information leaks | Error messages exposing internal paths, missing rate limiting |

---

## 🔐 Security Best Practices for Contributors

When contributing to TIDE, ensure:

- [ ] **No secrets in code.** Never commit `connections.toml`, passwords, or account identifiers.
- [ ] **Parameterized queries only.** Every SQL query must use bind variables. No string interpolation.
- [ ] **Validate all input.** Every procedure must validate its payload with Pydantic before processing.
- [ ] **No `ACCOUNTADMIN`.** All Snowflake operations use persona-specific roles (`TIDE_CUSTOMER`, `TIDE_APPROVER`, `TIDE_ESCALATION`) or `TIDE_ADMIN` for deployment.
- [ ] **No external calls.** No external HTTP, no external LLMs. All AI goes through Cortex AI within Snowflake.
- [ ] **Audit trail integrity.** Never add delete or update operations for chat messages or case events.
- [ ] **Anaconda-only packages.** Only packages available in the Snowflake Anaconda channel may be used.

---

## 📝 Compliance Notes

- **Data Processing:** TIDE processes retail transaction data, customer identifiers, and dispute records. Ensure compliance with applicable data protection regulations in your deployment jurisdiction.
- **Snowflake Governance:** The application operates within Snowflake's built-in governance framework, including RBAC, data masking capabilities, and access audit logging.
- **Audit Trail:** Every case generates a complete, immutable case report. This supports internal audit requirements and regulatory compliance needs.
- **Zero External Surface:** The application makes no external HTTP calls and has no external API keys, eliminating an entire class of secret-management and egress risks.

---

*Security is a shared responsibility. If you see something, report it.*

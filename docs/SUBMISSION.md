# TIDE · Submission checklist

Requirements confirmed by the organizers in the participant WhatsApp group on 28 July 2026.
Everything here is mandatory unless marked otherwise. **Both dashboard sections must be
submitted** or the entry is not eligible for evaluation.

Dashboard: `hack2skill.com/event/cococlihack/dashboard/submissions`
Deadline: **6 August 2026**, confirmed by Aditya Misra (organizer). Submit in the morning —
once the period closes the entry cannot be changed.

---

## Section 1 — GitHub / Deployed Link

| Item | Owner | Status |
|---|---|---|
| Select challenge (Track 1, Intelligent Workflow Automation Agent) | Keith | |
| **Public** GitHub repository link | Porter → Keith | **done** — repo public, history reset 2 Aug: 34 commits, zero tainted diffs or messages, verified by a per-commit scan of the full history |
| Prototype deployed link — judges access it directly | Nico → Keith | **deployed 4 Aug**: `TIDE.TRIAGE.TIDE_APP` — `https://app.snowflake.com/ap-southeast-7.aws/gq85743/#/streamlit-apps/TIDE.TRIAGE.TIDE_APP` — granted to all three personas and `TIDE_JUDGE`. Still needs a human click-through; see *Judge access* below |

## Section 2 — Prototype / MVP Submission

| Item | Owner | Status |
|---|---|---|
| Select challenge (same track) | Keith | |
| Prototype / MVP brief | Keith | |
| **Public demo video link** | Keith | record Tue 4 off the matrix run |
| Prototype deck, **on the provided template** | Keith | template: `docs.google.com/presentation/d/1YgGFe4wiu3biXuRh2sdsUToRaf8F-gqTHxPrcylqHxU/export/pptx` |

---

## Judge access — the open constraint

Streamlit in Snowflake has **no anonymous access**: every viewer must authenticate as a user
in our Snowflake account. So a URL alone does not let an evaluator in.

**Status (2 Aug):** the accounts exist and the roles are verified. `TIDE_JUDGE` holds the union
of the three persona roles by role inheritance, and `ALLOWED_INTERFACES = ('STREAMLIT')` is
confirmed **not** to block Snowsight or MFA enrolment. See `sql/14_demo_access.sql`.

Two things remain, and both are worth knowing before the deadline:

- **Snowflake mandates MFA enrolment** for `TYPE = PERSON` users on password auth. This is a
  platform floor, not our configuration — no account-level authentication policy is set, and
  `MFA_ENROLLMENT = OPTIONAL` is silently coerced to `REQUIRED_SNOWFLAKE_UI_PASSWORD_ONLY`. The
  evaluator therefore enrols their own device on first login. **`TIDE_JUDGE` must reach them
  unenrolled** — an account enrolled against a team member's device demands that device at the
  judge's login. Do not log in as it.
- The organizer question below is still unanswered, and it matters: every Streamlit-in-Snowflake
  entry hits this identical wall, so there is likely an intended answer worth chasing.

**This has to be tested before the deadline, not attempted on the day.** A judge who cannot
open the link scores what they can see, which is nothing.

Related: the customer-facing views filter on `CURRENT_USER()`, so demo users must exist whose
usernames match the seeded `customer_id` values (`sofia.reyes@example.com` and the rest) or the
customer page renders empty rather than broken. Create those in the same pass as the judge
users.

---

## What the organizers said about architecture

Two clarifications, slightly different in emphasis. Both are satisfied by what we are building.

**Sreenivas (Hack2skill):** *"The CoCo CLI is mainly the development/orchestration tool. You
don't need to expose the CLI itself."* Deploy via Snowflake-native services, Streamlit in
Snowflake named first. Ideal flow: build and orchestrate with CoCo CLI → deploy using
Snowflake → submit the deployment URL. A screen recording is a good addition but **cannot
replace** the deployment link.

**Cnu (Hack2skill):** CoCo CLI is *"the primary environment for building and executing"*, and
the deployed interface should be *"a lightweight interface ... that invokes or demonstrates the
underlying workflow built with CoCo CLI."* Also: *"You are encouraged to include a screen
recording demonstrating the complete CoCo CLI execution flow as supplementary evidence."*

Consequence for us: CoCo sessions are a **named submission asset**, not just internal tooling.
Screen-record them as they happen rather than reconstructing later. The README must state the
build-time versus runtime split plainly, since that framing is now organizer-endorsed.

---

## Demo video — notes before recording

- Public link required (YouTube unlisted-but-public, or Drive set to anyone-with-link).
- Record **after** a clean full-matrix pass, so what is on screen is the verified system.
- Cover the three stories from the BRD: a sub-limit case resolving autonomously, a case landing
  in the approval queue and being approved, and a guardrail firing with cited evidence.
- Include a CoCo segment, per Cnu's note.
- Keep it tight. Judges are evaluating many entries.

---

## Pre-submission gates

- [x] `pytest tests/ -q` green, coverage test hard-asserting — 114 passed
- [/] `deploy.py` runs clean on the canonical account — exit 0. **From an *empty* schema is
      still untested**, and that is the harder claim: a re-deploy over existing objects proves
      much less than a cold build.
- [x] Full matrix pass, twice, second one uninterrupted — `python scripts/run_matrix.py`.
      Both runs identical: **14 pass · 7 blocked at the proof gate · 1 observation · 0 failures**,
      exit 0, account left clean (0 misowned orders, 0 leftover cases). This asserts the
      *deployed* system, not the engine: each seeded order is driven through
      `OPEN_CASE → ASSEMBLE_EVIDENCE → ADJUDICATE` and must land on the path the seed engineered,
      with the decision **persisted** to `V_CASE_CURRENT` rather than merely returned.
      Two findings recorded in `TASKS.md` E-2: G-06 is unreachable end to end, and
      `ineligible_order_state` is unenforced at `OPEN_CASE`.
- [ ] Judge access tested by someone outside the team — blocked on the app being deployed
- [x] Banned-token scan clean across the repo — clean-room rule holds in every tracked file and
      in the commit messages of both published branches. The only hits are on local, unpushed
      safety branches (`pre-rewrite-master`, `pre-rewrite-keith`, `keith-prerebase`); **delete
      those before or just after submission** so a later `git push --all` cannot resurrect them.
      Also scanned clean: credential literals, PAT/token shapes, and non-`example.com` emails.
- [x] Git history reset done — the repo goes out as a public link. 34 commits, zero tainted
      diffs or messages, verified per-commit across the full history (2 Aug). One residue
      accepted: the pre-rewrite commits remain reachable on GitHub by direct SHA.
- [ ] `PROVENANCE.md` current
- [ ] Deck on the provided template, not our own
- [ ] Video public and playable in an incognito window
- [ ] Both dashboard sections submitted, and confirmation screenshotted

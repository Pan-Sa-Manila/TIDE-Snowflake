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
| **Public** GitHub repository link | Porter | repo is public; history reset still outstanding |
| Prototype deployed link — judges access it directly | Nico | see *Judge access* below |

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

Expected approach, pending an organizer answer (asked in the group, no reply yet): create judge
users on the canonical account and supply credentials alongside the deployed link. Give each
the `TIDE_APPROVER` or a read-scoped role, and `ALLOWED_INTERFACES = (STREAMLIT)` so the
account surface stays closed.

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

- [ ] `pytest tests/ -q` green, coverage test hard-asserting
- [ ] `deploy.py` runs clean from an empty schema on the canonical account
- [ ] Full matrix pass, twice, second one uninterrupted
- [ ] Judge access tested by someone outside the team
- [ ] Banned-token scan clean across the repo
- [ ] Git history reset done — the repo goes out as a public link
- [ ] `PROVENANCE.md` current
- [ ] Deck on the provided template, not our own
- [ ] Video public and playable in an incognito window
- [ ] Both dashboard sections submitted, and confirmation screenshotted

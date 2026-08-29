# Implementation plan

## Purpose

This document turns the initial seven-day delivery outline into an implementation sequence
for the Employee Performance Tracking Agent. It is a working roadmap, not an agent
instruction: `AGENTS.md` remains the source of truth for architecture and coding rules.

The project should be built in dependency order. Each phase must meet its acceptance criteria
before its dependent phases are considered complete.

## Design decision: LLM-first analysis

Python is responsible for safe parsing, bounded data access, validation, and all arithmetic.
The LLM is responsible for interpreting a bounded workbook synopsis, selecting relevant
tables, classifying KPI families, and proposing approved calculator plans. Never place an entire workbook into a prompt.

For unfamiliar sheets or columns, the LLM returns a structured classification and calculation
plan. Python validates table roles, calculator-specific bindings, types, and relationships
before a named performance calculator uses them. Cached plans are only a convenience for
known structures, not the app’s core decision-maker.

## Phase 1: Parse and expose uploaded data

**Status: Complete.** CSV/XLSX acceptance, size/type safeguards, mechanical workbook
inspection, bounded synopsis generation, and one-shot classification through the upload API are
connected.

Build the upload path for supported CSV and Excel files. It should enforce the configured
file-type and size limits, parse usable files, and produce a canonical representation that
services can consume without depending on FastAPI types.

Build table names, headers, inferred types, row counts, duplicate counts, and at most two
sample rows per table into a compact synopsis. Keep the original upload unchanged and
request-scoped.

This phase is complete when the agent can classify an unfamiliar upload and bind approved calculators from bounded context
without receiving the entire workbook, and an unusable file receives a clear client error.

## Phase 2: Validate source data

**Status: Complete.** Deterministic Python validation is connected after agent mapping and
before scoring. The API returns severity, scoring impact, employee/source identifiers, and
supporting record IDs for duplicates, missing exits, missing or unverified evidence, missing
reports, overdue work, low accuracy, missing targets, and inconsistent relationships.
Duplicate attendance and invalid quality-review relationships are excluded from scoring,
while approved leave remains neutral. Validation is performed once in Python and is not sent
back through the model. The Cedar acceptance run processed 30 employees with no import errors,
flagged four duplicate-attendance cases and missing-evidence records. The verified one-shot
run preserved the same results while reducing usage from 34,904 to 6,113 tokens.

Build a validation service that checks the mapped data before scoring. It should identify
missing required values, invalid dates, duplicate attendance records, missing evidence, and
inconsistent identifiers. Row-level issues should be returned as results rather than causing
the entire usable upload to fail.

Approved leave must be identified as neutral for attendance and compliance. Duplicate
attendance records must be excluded before later calculations. Validation findings must retain
the source record IDs needed for evidence-based alerts.

This phase is complete when duplicate and missing-evidence cases are flagged with their
supporting records.

## Phase 3: Implement deterministic KPI calculations

**Status: Complete with a documented benchmark exception.** Deterministic Productivity,
Compliance, Quality, evidence-confidence, overall-score, and performance-tier calculations
are connected. The 70% confidence guardrail returns `Insufficient data` without an overall
score or tier. All 30 employee confidence values and result statuses match `Expected_KPI`,
and Productivity, Quality, and eligible Overall scores reproduce the benchmark within 0.1.

EMP-027 and EMP-029 Compliance remain the documented exception: QA-01 requires duplicate
attendance exclusion, while a controlled API parity run confirmed that their `Expected_KPI`
values include the duplicate rows. Production preserves QA-01. See `docs/benchmark.md` for
the reproduced values and conflict details.

Build calculation tools for Productivity, Compliance, Quality, evidence confidence, overall
score, and result status. The tools—not the model—own every numerical operation. Implement
the scoring policy from the specification workbook: Productivity is weighted at 35%,
Compliance at 30%, and Quality at 35%.

The calculation service must apply the confidence gate before returning an overall score or
performance band. When verified evidence is below the configured threshold, the result must
be `Insufficient data` rather than a low score. Ensure calculation inputs and outputs are
traceable for each employee and period.

This phase is complete when the calculation output reproduces the approved `Expected_KPI`
benchmark values within 0.1.

## Phase 4: Add filtering and trend analysis

**Status: Complete.** Employee, team, and reporting-period filters are connected through the
API and consistently update KPI results, summaries, trends, and supporting alerts. The
response identifies the applied filters and date range, returns deterministic weekly trend
points from Python, and preserves component scores as unavailable rather than treating
missing evidence as zero. The Vue dashboard presents these results with sortable employee-table
pagination, per-employee alert counts, a KPI trend chart, and a responsive employee detail
sheet for traceable alerts and on-demand AI guidance.

Support analysis by employee, team, and reporting period. Keep filtering and aggregation in
services so routes remain thin. Make it clear which records and date range were included in
each result.

Trend outputs should distinguish changes in delivery, attendance/report compliance, and
quality. They must not compare employees across incompatible roles, workloads, or periods
without stating the limitation.

This phase is complete when employee, team, and period filters consistently affect all
relevant metrics and supporting records.

## Phase 5: Add AI explanations and recommendations

**Status: Complete.** `/analyze` stores a compact validated
insight context in a 15-minute in-memory cache without calling the explanation model. The Vue
dashboard requests typed guidance for one selected employee through `/insights` and caches the
result in browser memory. Python rejects unknown employees and citations to records outside
the employee's validated findings. Acceptance checks covered missing-report guidance,
low-accuracy coaching, multi-finding explanations, and Insufficient-data evidence guidance.

Connect the Pydantic AI agent only after validation and calculation tools exist. The agent
should receive bounded, calculated results and validated findings and return evidence-backed
observations and constructive next steps. It does not receive raw rows or call calculation
tools.

Each alert must cite supporting record IDs and evidence links where available. The agent must
not invent calculations, fill missing data with assumptions, or make high-impact employment
decisions.

This phase is complete when every generated insight is traceable to supporting records, the
agent follows the prompt in `app/services/agent.py`, and the on-demand experience passes
acceptance testing.

## Phase 6: Run the QA suite

Turn the workbook's critical scenarios into automated tests. Cover duplicate attendance,
approved-leave neutrality, missing exit records, late or missing reports, overdue projects,
low accuracy, rework burden, insufficient evidence, calculation parity, filtering, and alert
evidence traces.

Use the benchmark data as a regression fixture where appropriate. Tests should exercise the
service layer directly and cover API behaviour where the response contract matters.

This phase is complete when all critical QA cases pass and calculation parity remains within
the accepted tolerance.

## Phase 7: Polish and hand over

Document local setup, environment variables, supported upload formats, API endpoints, and
known limitations. Confirm error responses are consistent, the API documentation is usable,
and the app starts without an API key while clearly reporting that AI analysis is unavailable.

Prepare a short demo flow: upload data, review validation findings, inspect KPI results, apply
filters, and request an evidence-backed explanation.

This phase is complete when the project can be run and demonstrated from a fresh checkout
using the documented setup steps.

## Updating this plan

Update the relevant phase when its scope, acceptance criteria, or status changes. Keep
implementation-specific rules in `AGENTS.md`; keep user-facing and operational details in
the README; keep this file focused on sequencing, dependencies, and completion criteria.

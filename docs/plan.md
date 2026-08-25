# Implementation plan

## Purpose

This document turns the initial seven-day delivery outline into an implementation sequence
for the Employee Performance Tracking Agent. It is a working roadmap, not an agent
instruction: `AGENTS.md` remains the source of truth for architecture and coding rules.

The project should be built in dependency order. Each phase must meet its acceptance criteria
before its dependent phases are considered complete.

## Phase 1: Import and map uploaded data

**Status: Complete (Day 1).** The `/api/v1/analyze` endpoint accepts CSV and Excel uploads,
enforces the type and size safeguards, inspects tables and headers, maps recognized fields into
the canonical dataset, and returns import issues and relationship findings without persisting
the upload.

Build the upload path for supported CSV and Excel files. It should enforce the configured
file-type and size limits, parse usable files, and produce a canonical representation that
services can consume without depending on FastAPI types.

Map source columns to the fields required by the performance model using the actual uploaded
file and its data dictionary when available. Link records through stable identifiers, such as
employee, project, attendance, report, leave, and review IDs. Detect orphaned relationships
rather than silently dropping them.

This phase is complete when uploaded records can be mapped and joined without unexplained
orphan records, and an unusable file receives a clear client error.

## Phase 2: Validate source data

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

Support analysis by employee, team, and reporting period. Keep filtering and aggregation in
services so routes remain thin. Make it clear which records and date range were included in
each result.

Trend outputs should distinguish changes in delivery, attendance/report compliance, and
quality. They must not compare employees across incompatible roles, workloads, or periods
without stating the limitation.

This phase is complete when employee, team, and period filters consistently affect all
relevant metrics and supporting records.

## Phase 5: Add AI explanations and recommendations

Connect the Pydantic AI agent only after validation and calculation tools exist. The agent
should inspect validated results, choose what is useful to explain, call tools for any values,
and return evidence-backed observations and constructive next steps.

Each alert must cite supporting record IDs and evidence links where available. The agent must
not invent calculations, fill missing data with assumptions, or make high-impact employment
decisions.

This phase is complete when every generated alert is traceable to supporting records and the
agent follows the prompt in `app/services/agent.py`.

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

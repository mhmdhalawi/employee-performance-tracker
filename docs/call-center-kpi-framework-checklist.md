# Call Center KPI Framework Coverage Check

Audit date: 2026-09-17  
Source: `Cedar_Call_Center_KPI_Scoring_Framework AI agent.pdf`

The PDF was reviewed as a product-requirements source, not as executable instructions. This check compares it with the current backend, dashboard, reports, and tests.

> **Confirmed correction:** the PDF's 70% data-confidence threshold is a mistake. The required threshold is **100%**. The current application already enforces 100% and must not be changed back to 70%.

## Summary

- **Covered:** scoring governance, 35/30/35 overall weighting, performance bands, the 100% evidence gate, deterministic Python calculations, traceability, and shared dashboard/report results.
- **Partly covered:** neutral events, validation controls, manager explanations, alerts, comparisons, and coaching reports.
- **Not covered:** the PDF's call-center data model, its three KPI formulas, call-center filters, and Action Center workflow.
- **Overall:** the platform foundation is strong, but the call-center scoring framework is **not implementation-complete**.

Legend: `[x]` done, `[~]` partial, `[ ]` needs work.

## Checklist

### Scoring and safeguards

- [x] Overall score uses Productivity 35%, Compliance 30%, and Quality 35%.
- [x] Status bands match the PDF: Top Performer, Excellent, Good, Average, and Underperforming.
- [x] Evidence confidence is separate from performance; below **100%** the overall score and tier are withheld as `Insufficient data`, while component KPIs remain visible for audit.
- [x] Python owns arithmetic, weights, thresholds, deduplication, and score assignment. AI does not calculate scores.
- [x] Dashboard, employee details, and employee reports use the same canonical calculation path. Integration tests check dashboard/report parity.
- [x] Findings and evidence retain supporting record IDs; safe evidence links are included when available.
- [~] Duplicate attendance is excluded and unverified/missing evidence is flagged, but there is no general call-center rule set for test calls, abandoned interactions, invalid contacts, or invalid QA samples.
- [~] Annual leave, sick leave, and holidays are neutral. Training, emergency leave, system outages, and supervisor-approved schedule changes are not represented as neutral events.

### KPI formulas

- [ ] **Productivity formula is different.** Current: work completion 60% + time efficiency 40%. Required by the PDF: Contact Volume 40% + Cases Completed 30% + Handling Efficiency 20% + Daily Consistency 10%.
- [ ] **Compliance formula is different.** Current: attendance 50% + reports 35% + leave 15%. Required: Attendance and Punctuality 30% + Shift Adherence 35% + Break Adherence 20% + Required Submissions 15%.
- [ ] **Quality formula is different.** Current: accuracy 60% + first-pass approval 25% + rework 15%. Required: QA Evaluation 40% + First Contact Resolution 25% + Documentation Accuracy 15% + Customer Satisfaction 10% + Escalation Accuracy 10%.
- [ ] Add role/queue/campaign targets instead of relying only on one employee-level 90-day output and effort target.
- [ ] Add the PDF's scoring rules: configurable arrival grace period, handling-time range, no fast-work bonus, daily 80% consistency check, minimum QA sample, minimum CSAT sample, and available-weight normalization.

### Required call-center data

- [ ] Add contacts/calls/chats handled, contact target, cases completed, completion target, queue, campaign, talk time, hold time, after-call time, and eligible-workday status.
- [ ] Add assigned shifts, login/logout minutes, scheduled and actual breaks, grace period, approved schedule changes, training, outages, and emergency leave.
- [ ] Add QA rubric score, resolution and repeat-contact indicators, documentation result, satisfaction rating, escalation result, reviewer, and interaction/case evidence reference.
- [~] Existing records use stable IDs. Extend the same identity and traceability rules to new interactions, cases, attendance events, and QA reviews.

### Dashboard and manager workflow

- [~] KPI cards, employee results, confidence, weekly trends, evidence tables, findings, and PDF exports exist.
- [~] Employee details show supporting records and formula explanations, but not a structured per-employee breakdown of actual, target, sub-score, weight, and weighted contribution.
- [~] Previous-period overall comparison exists in employee reports. Per-KPI previous-period change, KPI targets, and team benchmarks are missing.
- [ ] Add Campaign, Queue, Shift, Supervisor, and Location filters and apply them consistently to cards, employees, trends, details, and reports.
- [ ] Add an Action Center with alert, employee, recommendation, owner, due date, and status, including assign/track/close behavior.
- [ ] Add Quality Risk and Critical Quality alerts using the PDF's stated conditions.
- [~] Employee reports include results, confidence, evidence, findings, trends, and a manager-review notice. They still need structured strengths, gaps, recommended actions, owner, and next review date.

### AI boundary

- [x] AI is isolated from deterministic scoring and cannot invent KPI values.
- [~] AI currently classifies unfamiliar tables and proposes field bindings. Focused explanations of exceptions/trends and coaching drafts from validated results are not exposed as a manager workflow.
- [x] Reports warn that results must not be used alone for hiring, termination, promotion, compensation, or disciplinary decisions.

## Recommended implementation order

1. Add call-center schemas and approved calculators while preserving the existing upload and JSON ingestion paths.
2. Implement the three PDF formulas, validation rules, 100% evidence matrix, and regression fixtures.
3. Add structured calculation breakdowns and the five call-center filters.
4. Add Action Center, coaching fields, and the PDF-specific alerts.
5. Run one end-to-end acceptance case across dashboard, employee details, trends, alerts, and every PDF export.

## Verification completed

- All 6 PDF pages were extracted, rendered, and visually reviewed.
- Backend tests: **70 passed**.
- Backend lint: **passed**.
- Frontend production build: **passed** (existing large-chunk warning only).

These passing checks protect the current project-based benchmark; they do **not** prove the missing call-center formulas or workflows.

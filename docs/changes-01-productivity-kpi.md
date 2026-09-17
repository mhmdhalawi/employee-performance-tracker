# Productivity KPI - changes to make

## Target result

Keep Productivity at **35% of the overall score** and calculate it as:

`Contact volume 40% + Cases completed 30% + Handling efficiency 20% + Daily consistency 10%`

The calculation stays deterministic in Python. AI may explain the result, but must not calculate or change it.

## What is missing today

| Area | Current system | Required call-center version |
| --- | --- | --- |
| Output | Completed projects | Eligible calls, chats, requests, cases, or tickets |
| Targets | Per-employee 90-day output and effort targets | Targets by role, queue, or campaign and reporting period |
| Efficiency | Average project hours | Average handling time from talk + hold + after-call time |
| Consistency | Not calculated | Days reaching at least 80% of the daily target |
| Neutral events | Limited support | Leave, training, outages, and invalid interactions excluded |

## Work checklist

### 1. Add the call-center data contract

- [ ] Add interaction totals, case totals, work date, queue/campaign, and eligible-day status.
- [ ] Add contact, case, daily, and handling-time targets with effective dates.
- [ ] Store talk, hold, and after-call time or a validated total handling time.
- [ ] Keep stable record IDs and evidence links for every supporting record.

### 2. Add a versioned call-center calculator

- [ ] Calculate contact volume: `handled / target`, capped at 100.
- [ ] Calculate cases completed: `completed / target`, capped at 100.
- [ ] Score handling efficiency as 100 inside the approved range and reduce it only above the maximum.
- [ ] Do not reward handling time below the minimum; create a quality-risk finding instead.
- [ ] Calculate daily consistency: eligible days at or above 80% of target / eligible days.
- [ ] Apply the 40/30/20/10 weights above.

Do not silently reinterpret existing project records. Keep the current benchmark calculator available until stored data and benchmark tests are migrated deliberately.

### 3. Apply evidence and exclusion rules

- [ ] Exclude approved leave, training, outages, test records, and invalid interactions from both actuals and targets.
- [ ] Mark missing or unverified required inputs as incomplete evidence, not zero performance.
- [ ] Keep the component score visible for audit, but withhold the overall score unless evidence confidence is **100%**.

### 4. Update output and tests

- [ ] Show the four submetrics, actuals, targets, formula, and supporting records in employee details and reports.
- [ ] Add tests for caps, target selection, neutral days, short reporting periods, handling-time ranges, missing evidence, and duplicate records.
- [ ] Add the cross-KPI `high_productivity_low_quality` alert without changing either KPI score.

## Done when

- The worked example produces `87.0`.
- Role/queue/campaign targets resolve predictably for the selected period.
- Missing required evidence produces `Insufficient data` at anything below 100% confidence.
- Dashboard, employee details, trends, and PDFs use the same stored calculation snapshot.

## Implementation notes

Likely touchpoints: `app/schemas/performance.py`, `app/schemas/calculators.py`, `app/services/performance/`, evidence APIs, Vue evidence tables, PDF generators, migrations, and regression fixtures.

Decisions needed before coding: target precedence when several scopes match, the approved handling-time range, and whether chat/request work uses the same or separate targets.

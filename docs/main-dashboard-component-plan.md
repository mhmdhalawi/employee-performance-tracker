# Main dashboard component plan

Status: approved direction; call-center filter section implemented  
Reference: user-supplied `Main Dashboard.jpeg`  
Scope: dashboard structure above and around the existing trend chart and Employee Results table

## Purpose

This document divides the reference dashboard into implementation sections and compares them with the current Cedar Vue dashboard. It keeps the reference image's information hierarchy while respecting the product's actual KPI model and backend-owned arithmetic.

The app now supports Campaign, Queue, Shift, Supervisor, and Location as optional canonical employee-profile fields. The reference's contacts/day, cases/day, and handling-time metrics remain unsupported and must not be calculated in the browser without a typed backend contract.

## What already exists

- Shared Cedar product header and `Generate team report` action.
- Call-center reporting-period, Campaign, Queue, Shift, Supervisor, and Location filters with resilient loading and retry behavior.
- Four basic summary cards: Overall, Productivity, Compliance, and Quality.
- Employee Results table and responsive employee cards.
- Shared weekly KPI trend chart.
- Backend-provided alerts, although there is no dashboard Action Center presentation yet.

## Page structure at a glance

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Cedar / Employee performance                         Generate team report    │
├──────────────────────────────────────────────────────────────────────────────┤
│ 1. FILTERS: reporting period · employee · team · future source dimensions   │
├──────────────────────────────────────────────────────────────────────────────┤
│ 2. SUMMARY: Overall │ Productivity │ Compliance │ Quality                   │
├──────────────────────────────────────────────────────────────────────────────┤
│ 3. KPI BREAKDOWN: one expandable, tabbed component-detail table             │
├───────────────────────────────────────────────────┬──────────────────────────┤
│ 4. Weekly KPI trend — already implemented         │ 5. Action Center         │
├───────────────────────────────────────────────────┴──────────────────────────┤
│ 6. Employee Results — already implemented                                    │
└──────────────────────────────────────────────────────────────────────────────┘
```

The trend chart and Employee Results table are included only to show page placement. Their content and behavior are outside this plan.

## Section 1 — Filters

### Reference image

The image starts with a dense filter bar containing:

- Reporting period selector.
- Quick period actions: Today, This Week, and This Month.
- Campaign, Queue, Shift, Supervisor, and Location selectors.

### Current implementation

`CallCenterFilterBar.vue` now provides:

- Calendar date-range picker plus Today, This week, and This month.
- Campaign, Queue, Shift, Supervisor, and Location.
- Clear filters, updating state, retry behavior, and last-successful-result retention.

### Missing or different

| Item | Status | Recommendation |
| --- | --- | --- |
| Reporting period | Implemented | Calendar and typed date range; the three visible quick ranges send inclusive explicit dates. |
| Employee / Team | Removed from dashboard | Retained as API compatibility filters for employee detail and reports. |
| Today / This Week / This Month | Implemented | Anchored to the latest canonical evidence date. |
| Campaign / Queue / Shift / Supervisor / Location | Implemented | Optional canonical employee-profile dimensions; selectors show only All when source data omits a dimension. |
| Applied-filter summary | Implemented | Preserve the selected-period badge, population counts, score-window note, and Clear filters action. |

### Recommended component boundary

`CallCenterFilterBar.vue` is the business-named owner and composes `ReportingPeriodPicker.vue` with the existing shared Field, Select, and Button primitives. `App.vue` remains responsible for requests, cancellation, stale-response protection, and the last successful dashboard response.

### Responsive sketch

```text
Desktop
┌───────────────┬───────────────┬───────────────┬────────────────────────────┐
│ Employee      │ Team          │ Future facet  │ Reporting period           │
└───────────────┴───────────────┴───────────────┴────────────────────────────┘

Phone
┌────────────────────────────────┐
│ Employee                       │
├────────────────────────────────┤
│ Team                           │
├────────────────────────────────┤
│ Reporting period              │
└────────────────────────────────┘
```

Future facets should wrap into a second row on wide screens and stack on phones. Open listboxes must remain viewport-bounded and keyboard operable.

## Section 2 — Four summary cards

### Reference image

The cards communicate more than the headline score:

1. Overall Score.
2. Productivity.
3. Compliance.
4. Quality.

The KPI cards show target, change versus target, change versus the previous period, team benchmark, overall weight, status, and a `View breakdown` action. The supplied image shows `View breakdown` on the three KPI cards, not on the Overall Score card.

### Current implementation

The current cards contain:

- KPI name and colored marker.
- Average score.
- Scored-employee population.
- Overall weight for the three KPIs.
- A KPI PDF download icon on the three KPI cards.

### Missing

- Overall performance status badge such as Excellent or Insufficient data.
- KPI attention badge when a KPI misses its target.
- Goal/target value.
- Point difference versus target.
- Point difference versus a comparable prior period.
- Team or organizational benchmark.
- Visible `View breakdown` button for Productivity, Compliance, and Quality.
- Clear separation between the breakdown action and the existing download action.

### Important data rule

Targets, previous-period deltas, benchmark values, component scores, and contributions must be returned by Python. The Vue client may format backend values but must not reproduce KPI arithmetic.

The current `DashboardResponse` has average scores and population counts, but it does not expose structured dashboard targets, prior-period comparisons, team benchmarks, or component breakdown rows. The richer card design therefore needs an API-contract change before it can be complete.

### Recommended card anatomy

```text
┌──────────────────────────────────────┐
│ ● Productivity       [On target]     │
│ 87.3%                                │
│ Target 85%        +2.3 pts           │
│ Previous period   +3.2 pts           │
│ Team benchmark     84.6%             │
│ 35% of overall                       │
│ [View breakdown ▾]       [Download]  │
└──────────────────────────────────────┘
```

If a value is unavailable, show `Not available`; do not display a zero or hide the label in a way that implies success. If an overall score is withheld, show `—`, `Insufficient data`, and the scored/withheld population rather than assigning a low-score status.

### Recommended component boundary

- `KpiSummaryGrid.vue` owns layout.
- `KpiSummaryCard.vue` owns the shared visual anatomy.
- Business-named variants handle Overall versus a component KPI.
- Existing Card, Badge, Button, and Spinner primitives remain the canonical controls.

## Section 3 — KPI breakdown panel

This is the most important missing section. It is a compact KPI-component table opened from the summary cards; it is not the main Employee Results table.

### Interaction model

- The panel is collapsed by default.
- `View breakdown` is available on Productivity, Compliance, and Quality.
- Activating a card opens the panel directly below the four cards and selects that KPI.
- Activating another card switches the open panel to that KPI without creating a second panel.
- Activating the selected card again may collapse the panel.
- Tabs inside the panel allow direct movement among Productivity, Compliance, and Quality.
- The trigger exposes `aria-expanded` and `aria-controls`; the selected tab uses the standard keyboard tab pattern.
- During a filter refresh, keep the last successful breakdown visible, disable its controls, and show the existing Updating treatment. If the request fails, retain the old values with the dashboard's retry alert.

### Use Cedar's real KPI components

Do not copy the reference's call-center rows unless the actual customer data supports them. The Cedar component rows are:

| KPI | Breakdown rows | Weight within KPI |
| --- | --- | ---: |
| Productivity | Work completion; time efficiency | 60%; 40% |
| Compliance | Attendance; report submission; leave compliance | 50%; 35%; 15% |
| Quality | Accuracy; first-pass approval; rework | 60%; 25%; 15% |

Approved annual leave and approved sick leave remain neutral in attendance; sick-leave documentation still controls whether the leave-compliance requirement is satisfied. Unavailable required evidence lowers confidence and must not become zero performance.

### Suggested columns

| Column | Purpose |
| --- | --- |
| Component | Human-readable component name. |
| Observed result | Backend-provided count, duration, ratio, or status summary. |
| Target / rule | The applicable backend-provided target or deterministic rule. |
| Component score | Backend-calculated normalized score. |
| Weight | Documented weight within the selected KPI. |
| Contribution | Backend-calculated weighted contribution to the KPI. |
| Evidence | Record count or coverage note with a path to supporting detail. |

`Team average` from the reference can be included only if the backend defines and returns the comparison population. It should not be inferred from whichever employee rows happen to be loaded in the browser.

### Desktop visual

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Productivity breakdown       Selected period              [Prod] [Comp] [Q] │
├──────────────────┬──────────────┬──────────────┬────────┬────────┬───────────┤
│ Component        │ Observed     │ Target/rule  │ Score  │ Weight │ Contrib.  │
├──────────────────┼──────────────┼──────────────┼────────┼────────┼───────────┤
│ Work completion  │ …            │ …            │ …      │ 60%    │ …         │
│ Time efficiency  │ …            │ …            │ …      │ 40%    │ …         │
├──────────────────┴──────────────┴──────────────┴────────┴────────┴───────────┤
│ Final Productivity score                                             87.3%  │
├──────────────────────────────────────────────────────────────────────────────┤
│ ℹ Values come from deterministic calculations and supporting evidence.      │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Phone visual

Avoid a horizontally compressed seven-column table. Each component becomes a labeled record card while preserving every field.

```text
┌──────────────────────────────┐
│ Productivity breakdown      │
│ [Prod] [Comp] [Quality]     │
├──────────────────────────────┤
│ Work completion             │
│ Observed            …       │
│ Target              …       │
│ Component score     …       │
│ Weight             60%      │
│ Contribution        …       │
│ [View evidence]             │
├──────────────────────────────┤
│ Time efficiency             │
│ …                            │
├──────────────────────────────┤
│ Final score           87.3% │
└──────────────────────────────┘
```

### Required backend addition

Prefer a typed breakdown on `DashboardResponse`, keyed by KPI, rather than parsing the existing human-readable `*_reason` strings. A row needs stable identifiers and nullable typed values so missing evidence remains distinct from real zero.

Conceptual shape:

```text
kpi_breakdowns
  productivity
    score
    rows[]: key, label, observed, target, component_score, weight, contribution,
            evidence_count, evidence_status
  compliance
    ...
  quality
    ...
```

The exact schema should be defined in the Python/Pydantic contract first and mirrored in TypeScript.

## Section 4 — Weekly performance trend

Status: already implemented through `WeeklyKpiTrend.vue`; no redesign is requested here.

Placement recommendation: on wide screens, allow the chart to occupy roughly two-thirds of the row with Action Center beside it. On narrow screens, stack the chart above Action Center. Preserve missing-value gaps, distinct series patterns, the exact-values disclosure, and backend filter scope.

## Section 5 — Action Center

### Reference image

The Action Center shows a total open-action count, three summarized issues, a Review action for each, and a View all actions link.

### Current implementation

The API already returns typed `alerts` with severity, category, action, employee, occurrence count, record IDs, evidence links, and scoring impact. The dashboard currently uses these alerts only to count Data Issues and Performance Alerts per employee.

### Missing

- Dashboard Action Center card.
- Grouped top actions with severity icon and affected-employee count.
- Direct Review action.
- View-all experience.
- Empty and error states for the action list.

### Recommended behavior

- Use backend alert ordering or add an explicit backend priority; do not invent employment-impact priority in the browser.
- Show up to three groups in the dashboard card.
- Keep Data Issues and Performance Alerts visibly distinct with text and icon, not color alone.
- For a single-employee alert, Review can open that employee's detail route.
- For a multi-employee group, Review should open an accessible Action Center sheet listing affected employees and supporting records.
- `View all actions` opens the same sheet without preselecting a group.
- An empty state reads `No open actions for the selected filters.`
- Preserve safe HTTPS evidence links and backend-provided review actions.

### Visual

```text
┌──────────────────────────────────────┐
│ Action Center          [7 open]      │
├──────────────────────────────────────┤
│ ! Quality below target               │
│   4 employees               [Review] │
├──────────────────────────────────────┤
│ ! Missing evidence                   │
│   3 employees               [Review] │
├──────────────────────────────────────┤
│ i Repeated lateness                  │
│   2 employees               [Review] │
├──────────────────────────────────────┤
│                         View all →   │
└──────────────────────────────────────┘
```

Suggested owner: `DashboardActionCenter.vue`, composed from existing Card, Badge, Button, and Sheet primitives. The sheet must have an accessible title and description, Escape/focus restoration, a bounded scrolling body, and reachable actions.

## Section 6 — Employee Results

Status: already implemented and outside this plan. Keep the current desktop table, narrow-screen employee cards, sort, pagination, confidence presentation, separate finding counts, and View details action.

The reference image shows only three performers, but the current paginated full result set is more appropriate for the product and should not be reduced to a decorative top-three table.

## Current-to-reference gap summary

| Area | Current state | Work needed |
| --- | --- | --- |
| Header and team report | Implemented | Preserve. |
| Filters | Implemented | Reporting period and five call-center dimensions use typed backend filters. |
| Four cards | Basic version implemented | Add status, targets, comparisons, benchmark, and explicit breakdown actions through typed backend data. |
| KPI breakdown | Missing | Add one shared expandable panel with three KPI tabs and deterministic component rows. |
| Trend chart | Implemented | No detailed work in this plan. |
| Action Center | Data exists, UI missing | Add summarized card and accessible view-all sheet. |
| Employee Results | Implemented | No detailed work in this plan. |

## Suggested implementation order

1. Define the typed backend contract for summary-card comparisons and KPI breakdown rows.
2. Add deterministic aggregation for target, prior comparable period, benchmark population, components, and contributions.
3. Mirror the new schema in `web/src/types/analysis.ts`.
4. Extract the filter bar only if new supported dimensions are being added.
5. Build the shared summary grid/card and preserve the existing KPI download actions.
6. Build the single expandable KPI breakdown panel with desktop table and phone cards.
7. Build Action Center from the existing backend alerts and the shared Sheet primitive.
8. Verify loading, filter failure/retry, null values, withheld overall results, keyboard operation, phone layout, 200% zoom, and reduced motion.

## Acceptance criteria

- The three KPI cards have a clearly labeled `View breakdown` button; the Overall card remains a summary unless an explicit overall-breakdown requirement is added.
- Only one breakdown panel is open at a time and it always matches the active KPI card/tab.
- Every displayed number is supplied or calculated by Python; Vue performs formatting only.
- Missing data is distinct from zero and does not silently lower performance.
- An insufficient-data overall result remains withheld while component KPI values remain auditable.
- Filter changes update cards, breakdown, Action Center, chart, and Employee Results from one successful backend response.
- Failed filter requests retain the last successful dashboard and offer Retry.
- Desktop and phone presentations expose the same information without horizontal page scrolling.
- All interactive controls are native buttons/links or maintained accessible primitives with visible focus and useful names.
- The existing trend chart and Employee Results behavior remain intact.

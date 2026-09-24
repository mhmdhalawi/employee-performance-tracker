# Employee Details reference plan

Status: implemented in the Employee Details page on 2026-09-24. This document remains the reference-to-product decision record.

## Goal and source boundary

Give managers a faster way to read one employee's current result, understand which evidence needs review, and reach the full records. Use the supplied `Employee Details Page.jpeg` as a visual reference for hierarchy and density. Its names, numbers, dates, targets, team averages, strengths, and action workflow are illustrative image content, not instructions or verified product data.

This plan follows the current call-center dashboard, Cedar visual direction in `docs/design.md`, and shared behavior in `docs/ux-guidelines.md`. The current dashboard response and employee evidence endpoints remain the source of truth.

## Proposed page

```text
Shared Cedar header: Back to dashboard                         Generate report
Employee identity: name / ID / role / available call-center profile / actual tier
Reporting period: committed range and any different score-evidence window

Overall       Productivity       Compliance       Quality       Data confidence

How the result is formed (compact KPI scores, weights, evidence links)
Weekly KPI trend                         Findings requiring review

Productivity evidence
Compliance evidence
Quality evidence
```

At wide widths, the five summary tiles form one row and the trend/findings area uses two columns. At smaller widths, tiles wrap without shrinking their text; trend precedes findings; the three full-width evidence sections retain their existing desktop tables and phone record cards. The evidence remains below the summary so a manager can scan first, then inspect source records.

### Reference-to-product decisions

| In the image | Planned treatment |
| --- | --- |
| Cedar header, back link, report action | Reuse `PerformanceHeader.vue`, the existing back behavior, and the current report preview/download flow. |
| Avatar and rich employee heading | Add an initials avatar with a text fallback. Show only profile fields present on `EmployeeKpiResult`: employee ID, role, campaign, queue, shift, supervisor, and location. Omit missing fields rather than inventing values. |
| Top Performer pill | Show the backend `performance_tier` or `result_status`; use the warning state when the overall result is withheld. Do not infer a tier from the score. |
| Reporting period selector | Reuse `ReportingPeriodPicker.vue` and the existing dashboard filter request path. Preserve other applied filters; update the displayed range only after a successful response; retain old results on failure and offer Retry. Show the score-evidence window separately when it differs. |
| Five score cards | Add compact Overall, Productivity, Compliance, Quality, and Data confidence cards from the current employee result. Keep `—` and explicit `Insufficient data` when confidence is below 100%; keep component scores visible. Confidence states what it measures. |
| Performance Explained table | Show backend KPI scores, the documented 35/30/35 overall weights, and backend-calculated averages for the current dashboard scope. Link to the matching evidence section. Preserve each evidence table's calculation help. Scope average is explicitly labeled and is not presented as a team benchmark. Do not display target gaps or contribution points without an authoritative backend contract. |
| 12-week trend | Reuse `WeeklyKpiTrend.vue` and the existing employee-scoped backend trend request. Keep all three actual KPI series, visible legend, missing-data gaps, exact-values disclosure, and actual selected period. Do not fabricate target or team-average lines. |
| Manager Summary: strengths/watch point | Use actual backend findings and review actions in the existing `EmployeeAttentionSummary.vue`/evidence records. Retain Data Issues versus Performance Alerts and source record IDs/links. Do not generate praise or a “lowest component” judgment from score rank. |
| Recommended Action, owner, due, status, Assign button | Omit: there is no assignment, due-date, or action-status contract. Backend review-action text can be displayed as guidance beside its finding. |
| KPI Breakdown metrics such as calls/day and occupancy | Show the employee's backend-calculated component scores and within-KPI weights already present in `EmployeeKpiResult.components`. Keep the three existing evidence sections as the detailed drill-down; do not relabel project, attendance, report, leave, or quality records as call-center metrics. |
| Bottom evidence shortcuts | Add three in-page links with record counts when loaded, using the endpoint's selected-period counts. Preserve independent pagination and All records / Needs review modes. |
| Manager View dropdown | Omit: the app has no role-view or authorization feature. |

## Visual direction

Keep the existing white card surfaces, Geist text, Cedar teal actions, dark text, and restrained gold warnings. Use the dashboard's compact card spacing and table treatment so the detail page reads as its companion. The employee identity row is the visual anchor: initials, name, metadata, status, and period should remain legible before the dense score row. Use existing semantic tokens and shared components; do not copy colors or typography directly from the JPEG or change Cedar artwork. Preserve natural page scrolling and the shared 1920px content maximum.

## Implementation sequence completed

1. Update `EmployeeDetailPage.vue` layout and header content. Keep the existing report dialog, refresh alerts, confidence gate, trend request, and evidence loading behavior intact.
2. Compose the score row from the current `EmployeeKpiResult`. Move the current overall/confidence presentation into that row without losing its explanation and progress state. Add explicit withheld and missing-value labels.
3. Add the compact score explanation and in-page evidence links. Keep calculation help owned by `EmployeeEvidenceTable.vue`; avoid duplicate formula text.
4. Arrange the existing trend and findings components as the image-inspired review row. Preserve the shared chart behavior across dashboard and report preview.
5. Keep the three existing evidence tables full width and independently paginated. Add section IDs and record-count shortcuts without changing endpoint semantics or PDF export coverage.
6. Wire `ReportingPeriodPicker.vue` through `EmployeeDetailView.vue` and `App.vue` to the existing filter flow. Verify that a failed request retains the old committed range/results and that back navigation returns to the dashboard's preserved state.
7. Reconcile durable design/UX decisions in `docs/design.md` and `docs/ux-guidelines.md` during implementation. Keep the existing CSS token owner in `web/src/style.css`.

## Verification for the implementation pass

- Run `pnpm build` in `web/` and the frontend skill's applicable static audit.
- Inspect the employee page beside the current dashboard in a real browser at wide and phone widths, with long names and missing profile fields; check keyboard navigation, focus, zoom, and no horizontal overflow.
- Check scored and insufficient-data employees, null component scores, missing/interior-null trends, empty findings, and evidence load/retry states. Confirm no target, benchmark, or action status appears without a source.
- Exercise period changes: pending, success, failure/retry, evidence freshness, trend refresh, and return to the dashboard. Confirm displayed dates use `DD/MM/YYYY` and the score-evidence window remains distinct.
- Open each evidence disclosure and the report preview; verify complete PDF export still uses its snapshot and is unaffected by on-page pagination or collapsed sections.

## Data work reserved for a separate decision

The image's prior-period deltas, team benchmarks, per-KPI targets and contribution points would require an authoritative employee comparison/target contract and backend-calculated values. The report preview currently has an overall prior-period change, but the normal employee dashboard result does not expose comparable per-KPI deltas. `request.json` contains extra raw profile and target columns; the current canonical employee/target records in SQLite retain only the mapped fields, so those extra source values are not shown as if they were current canonical data. SQLite has an empty `performance_actions` table, but no application action workflow or API; assignment and status remain outside this layout pass.

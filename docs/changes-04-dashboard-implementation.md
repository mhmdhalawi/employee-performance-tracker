# Dashboard implementation - changes to make

This file covers the shared dashboard, workflow, reporting, and AI controls from the framework's final page. The three KPI formulas remain in their own files.

## Dashboard checklist

- [ ] KPI cards show score, target, previous-period change, and confidence.
- [x] Employee results show the three KPI scores, overall score, status, and evidence confidence.
- [ ] View details shows submetric actuals, targets, formulas, and supporting records.
- [ ] Add an Action Center with alert, employee, recommendation, owner, due date, and status.
- [ ] Add campaign, queue, shift, supervisor, and location filters alongside the existing employee, team, and period filters.
- [ ] Reports show strengths, gaps, evidence, actions, and the next review date.

## Calculation workflow

Keep one controlled flow:

`Client data -> Cedar format -> validation -> deterministic KPI calculation -> optional AI insight -> dashboard and reports`

- [x] Python owns arithmetic, weighting, thresholds, deduplication, and score assignment.
- [x] AI does not invent targets, evidence, scores, or employee conclusions.
- [x] Dashboard, employee details, and exports use the same validated calculation snapshot.
- [ ] Add an explicit calculation version to the snapshot and every export.
- [ ] Confirm every new filter is applied by the backend before the snapshot is returned.

## AI boundaries

AI may:

- Explain validated exceptions, trends, and repeated patterns.
- Draft focused coaching suggestions from validated results.
- Summarize selected evidence without processing every source record.

AI must not:

- Perform scoring or change deterministic results.
- Make hiring, termination, promotion, compensation, or disciplinary decisions.
- Present a recommendation without the supporting validated records.

## Evidence rule

- Keep component KPI values visible for audit.
- Require **100% evidence confidence** for an overall score and performance status.
- Below 100%, return `Insufficient data`; the PDF's original 70% threshold is not used.

## Done when

- All screens and PDFs show values from the same calculation snapshot and version.
- Filters produce matching dashboard, employee-detail, trend, and report results.
- Every alert or AI explanation links to supporting records.
- Managers can assign and track actions without AI making employment decisions.

## Implementation notes

Likely touchpoints: dashboard response schemas, filters, aggregation/report services, Vue KPI cards and detail views, Action Center components, and browser PDF generators.

# Cedar UX guidelines

The domain rules in [AGENTS.md](../AGENTS.md), [benchmark.md](benchmark.md), and the FastAPI schemas remain authoritative. Visual intent is maintained in [design.md](design.md). This document records the UI behavior implemented in the 2026-09-05 review pass.

## State and navigation

- `App.vue` owns the current successful `DashboardResponse`, request cancellation, and request errors. Check the request sequence after reading the response body so an older request cannot replace newer results.
- Dashboard employee/team/period controls derive their selected values from `analysis.applied_filters`. A select requests a new scope; it does not claim that scope until the response succeeds. Changing team clears the employee selection in that request.
- While a filter request runs, selectors and exports are disabled. Failure preserves both old controls and old results and offers Retry filters. Retry repeats the last attempted request. Clear filters requests the full dashboard.
- `KeepAlive` in `App.vue` preserves the dashboard's page, page size, sort, and local disclosure state while visiting employee and interpretation routes. A new successful dataset or page-size change resets the page. Name and overall sorting reset the page and keep missing overall scores last.
- Filter and view state intentionally remain in application memory for this employee-data dashboard; they are not copied into URLs or persistent browser storage. Reload starts with the full scope. This follows the existing response-in-memory architecture and avoids adding employee/team selections to shareable URLs in this pass.
- `useDashboardBack.ts` owns back navigation. Dashboard data is still supplied by the backend; frontend cards, counts, and weekly values do not recalculate KPI values.

## Canonical UI map

| Capability | Owner | Contract and verification |
| --- | --- | --- |
| Product header | `components/dashboard/PerformanceHeader.vue` | Same Cedar identity on each route; employee/interpretation headers expose Back to dashboard |
| Select/Listbox | `components/ui/select` and `FieldLabel` | Authored Reka select, associated visible labels, keyboard selection, Escape/focus restoration; verify open popup at narrow widths |
| Results navigation | `PerformanceDashboard.vue`, shared Table/Pagination | Desktop table and mobile employee cards use the same paginated/sorted rows; preserve all score/status fields |
| Report overlay | `ReportPreviewContent.vue`, shared Dialog | Accessible dialog title/description, contained body scroll, complete cards, reachable footer, Escape; verify desktop, phone, and short height |
| Confidence | `components/ui/progress/Progress.vue` | Warning tone for withheld employee results plus percentage and explicit status; no tier inference |
| Charts | Dashboard Unovis lines and weekly-values table | Map null to a non-numeric line gap, preserve real zero, no interpolated missing data; distinct series patterns and textual values |
| Failure feedback | Shared Alert/Button/Spinner | Inline recoverable errors and named Retry action; no native browser dialogs; retain last successful dashboard |
| Scrollbar/motion | `style.css` | Global semantic scrollbar colors, engine fallback, forced-colors default, reduced-motion override |

There are no create/edit/delete controls, bulk selection, authored date picker, or toast-based mutations in this workflow. Do not add those capabilities merely to fill a contract table.

## Presentation semantics

- “Findings” counts grouped employee alerts consistently on list/detail pages. Each detail finding separately labels its occurrence count.
- Overall averages show scored, withheld, and total counts from the response. Null scores remain a dash with a withheld-status explanation.
- Weekly chart values and coverage populations follow the filtered backend response. Missing values are labeled per KPI in the data table, never shown as zero.
- Dates are English, Gregorian, and UTC for date-only API fields. Display the reporting period on employee details and include the year for historical clarity.
- Source interpretation stays available after primary employee review. Its compact disclosure does not hide an attention warning. Source names and rationale get full width above their badges on phones.

## Boundaries and validation

Reports remain transient browser downloads with existing manager-review notices. This UI work does not implement authentication or change permission policy, raw-data ingestion, KPI formulas, API evidence, or PDF rendering.

Build with `pnpm build` in `web/`. Browser regression coverage must include trailing/interior null chart points versus real zero, team filter/back, page/sort return, failed filter/retry, employee preview failure/retry, dialog scrolling/focus at phone and short heights, long labels, and no-results display. Completed checks and verification limits are recorded in [the test handover](handover.md#frontend-verification--2026-09-05).

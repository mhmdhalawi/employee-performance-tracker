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
| Employee evidence | `EmployeeEvidenceTable.vue`, `EvidenceRecordDetails.vue`, shared Table/Collapsible | Three independently paginated tables; identical mobile records; keyboard disclosures; full source values and backend exclusion labels |
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

## Employee evidence and report snapshots — 2026-09-14

- `useEmployeeEvidence.ts` owns per-KPI fetching, cancellation, request sequences, pagination, and retry state. Each page contains five records. Scope changes clear old rows; a failed page request retains its last successful page and retries the attempted page.
- Evidence uses the dashboard's resolved dates. A differing `latest_submission_at` triggers a shared dashboard refresh; mismatched evidence is discarded. Successful refreshes reload all three tables even if dates and timestamp are unchanged.
- `App.vue` retains dashboard ownership. Employee Details routes refresh requests through the existing filter path. Failed refreshes retain current successful results and expose Retry results.
- Source statuses, attendance source confidence, missing values, real zero, and false first-pass approval retain distinct meanings. Python provides exclusions and finding impacts. Table counts include excluded audit records.
- Report preview receives complete evidence from one canonical read context, including prior comparison. Local pagination changes only presentation. Download uses that exact snapshot, including later pages and unopened details. Download failures retain the preview and allow retry.
- Evidence links must be absolute HTTPS URLs. Profile/evidence state remains in memory; report snapshots and PDFs are transient.

Completed API, browser, and PDF checks are recorded in
[employee review verification](#employee-review-verification--2026-09-14).

## Performance review presentation — 2026-09-14

`EmployeeAttentionSummary.vue` and `EmployeeAttentionItem.vue` own the page/report Needs attention summary. Informational findings with no scoring impact are omitted from this summary. The first three issue groups are visible; Show all reveals the rest, and Supporting records disclosures expose IDs and safe HTTPS links. These are presentation choices over backend findings, with no new business calculations.

`EmployeeCalculationDetails.vue` owns the optional, initially collapsed calculation reference on both views. Main table descriptions label work, attendance/report/leave, and quality data without formulas. PDF exports retain all performance records and relevant issues while omitting calculation explanations and metric definitions. Report payload values and download snapshot handling remain unchanged.

## Employee table content

| KPI | On-page columns |
| --- | --- |
| Productivity | Work record · Assigned / due · Completed · Status · Actual hours · Evidence · Details |
| Compliance | Type · Date / period · Record ID · Source outcome · Evidence summary · Details |
| Quality | Review ID · Work record · Review date · Accuracy · First pass · Rework · Evidence · Details |

Compliance uses one mixed table. Attendance details include scheduled/actual start and end,
lunch out/in, record status, and explicitly labeled source-record confidence. Submission
details include due/submitted dates, completeness, and verification. Leave details include
category, date range, outcome, and documentation completeness. Each type exposes its findings
and backend scoring impacts in the shared record disclosure.

Source outcomes do not imply calculated compliance. Source confidence is distinct from
employee evidence confidence. Missing values remain Not provided; real zero rework and
false first-pass approval remain visible. Work names and extra employee profile fields are
not invented. Quality records currently have no canonical evidence URL field.

The portrait A4 PDF groups the same printable values into five columns per KPI, replacing
Details buttons with full values, finding notes, and exclusion reasons. Short clickable HTTPS
labels and wrapped URLs preserve traceability. Section titles and column headings repeat;
ordinary rows stay together, while oversized notes can flow across pages. All records are
exported, including later preview pages and unopened disclosures. Empty evidence sections
are explicitly labeled, and insufficient-data exports retain withheld overall status.

## Employee review verification — 2026-09-14

- All 64 backend regression tests passed; `uv run ruff check app tests` and the frontend
  `pnpm build` passed. The frontend premium audit reported no findings.
- Integration coverage verifies upload/JSON evidence, employee isolation, pagination,
  typed errors, record-specific dates, overlapping leave, duplicate/orphan exclusions,
  unsafe-link filtering, complete report evidence, and one canonical read for current/prior
  report values. Existing benchmark, score parity, and confidence gating tests passed.
- Desktop 1440 × 1000 and phone 390 × 844 checks covered independent pagination,
  keyboard disclosures, error/retry, empty quality evidence, report dialog, and no horizontal
  overflow. A simulated freshness mismatch refreshed both results and evidence, including
  when the refreshed dashboard timestamp stayed unchanged.
- A scored employee without issues had no Needs attention section. An employee with ten
  issue groups showed three initially and all ten after keyboard activation of Show all.
  Supporting records and Calculation details opened correctly; calculations started collapsed
  on page and preview. Compliance calculation and standalone Findings were absent.
- Every page of final scored (12 pages) and insufficient-data (15 pages) exports was rendered
  and inspected. Formula/metric-definition sections were absent; relevant issues, complete
  records, exclusions, repeated headings, page numbers, and withheld status remained.
  Page counts depend on the selected evidence population.
- An earlier seven-page stress export used a long employee name/ID and a finding note
  repeated 150 times. Every occurrence survived export, oversized notes continued across
  pages, and empty sections and filename sanitization were verified. Stress data existed
  only in a transient browser snapshot.

PDF layout verification remains manual; there is no automated PDF layout regression suite.
Vite retains its large-chunk warning; PDF dependencies remain lazy-loaded. These checks
apply to read-only employee review and transient exports, without adding ingestion controls,
editing, per-record performance scores, saved reports, or server PDF generation.

# Cedar UX guidelines

The domain rules in [AGENTS.md](../AGENTS.md), [benchmark.md](benchmark.md), and the FastAPI schemas remain authoritative. Visual intent is maintained in [design.md](design.md). This document records the UI behavior implemented in the 2026-09-05 review pass.

## State and navigation

- `App.vue` owns the current successful `DashboardResponse`, request cancellation, and request errors. Check the request sequence after reading the response body so an older request cannot replace newer results.
- Dashboard controls derive their selected values from `analysis.applied_filters`.
  `App.vue` retains the request filters paired with the last successful response. A
  control requests a new scope; it does not claim that scope until the response succeeds.
- The main dashboard now exposes call-center Campaign, Queue, Shift, Supervisor, and
  Location selectors instead of employee/team selectors. The API retains employee/team
  filtering for employee detail, reports, and compatibility. Each operational selector is
  populated from unfiltered canonical employee profiles, and selecting one scopes scores,
  alerts, trends, and results through the same backend response. Unknown option values are
  rejected; valid combinations with no employees return the normal empty dashboard state.
- `CallCenterFilterBar.vue` owns the dashboard filter layout and composes
  `ReportingPeriodPicker.vue` for calendar and typed date ranges. Today / This week /
  This month remain visible shortcuts anchored to the latest evidence date and sent as
  explicit inclusive ISO dates. The picker also allows a full period or custom range.
  Employee details and report previews reuse the same committed range.
  Dates outside evidence coverage stay selected while a separate note identifies the
  evidence window used for scores. A wholly empty range returns withheld overall results.
- The four summary cards use backend averages over employees with reportable overall scores.
  `KpiBreakdownPanel.vue` presents backend-provided component averages and weights for that
  same population. View breakdown opens one panel below the cards; another KPI button or
  the panel tabs switches it, and the selected card button closes it. Filter refresh keeps
  the prior panel visible with controls disabled until the new response succeeds.
- Employee Details refresh reuses the last successful request's `period_preset`, legacy `period_weeks`, or explicit start/end dates. A full-scope refresh omits all three, preserving the backend's unbounded full-period calculation rules.
- While a filter request runs, selectors and exports are disabled. Failure preserves both old controls and old results and offers Retry filters. Retry repeats the last attempted request. Clear filters requests the full dashboard.
- `KeepAlive` in `App.vue` preserves the dashboard's page, page size, sort, and local disclosure state while visiting employee and interpretation routes. A new successful dataset or page-size change resets the page. Name and overall sorting reset the page and keep missing overall scores last.
- Filter and view state intentionally remain in application memory for this employee-data dashboard; they are not copied into URLs or persistent browser storage. Reload starts with the full scope. This follows the existing response-in-memory architecture and avoids adding operational employee dimensions to shareable URLs in this pass.
- `useDashboardBack.ts` sends Back to dashboard directly to the named dashboard route, regardless of browser history. Dashboard data is still supplied by the backend; frontend cards, counts, and weekly values do not recalculate KPI values.

## Canonical UI map

| Capability | Owner | Contract and verification |
| --- | --- | --- |
| Product header | `components/dashboard/PerformanceHeader.vue` | Same Cedar identity on each route; employee/interpretation headers expose Back to dashboard |
| Select/Listbox | `components/ui/select` and `FieldLabel` | Authored Reka select, associated visible labels, keyboard selection, Escape/focus restoration; verify open popup at narrow widths |
| Dashboard filters | `CallCenterFilterBar.vue`, `ReportingPeriodPicker.vue`, shared Select/Button/Field | Calendar and typed date range plus Today / This week / This month; Campaign, Queue, Shift, Supervisor, and Location; committed-response state and failed-request retention |
| KPI breakdown | `PerformanceDashboard.vue`, `KpiBreakdownPanel.vue`, shared Card/Tabs/Table | One disclosure under the four cards; server-calculated component averages, same scored population and filter scope; missing scores remain dashes |
| Dashboard Action Center | `DashboardActionCenter.vue`, shared Card/Badge/Button/Sheet | Group current backend alerts by category and scoring impact; Review and View all show source action, records, links, and employee navigation in a bounded sheet |
| Results navigation | `PerformanceDashboard.vue`, shared Table/Pagination | Desktop table and mobile employee cards use the same paginated/sorted rows; preserve all score/status fields |
| Report overlay | `ReportPreviewContent.vue`, shared Dialog | Accessible dialog title/description, viewport-bounded width up to 1400px, contained body scroll, complete cards, reachable footer, Escape; verify desktop, phone, and short height |
| Employee evidence | `EmployeeEvidenceTable.vue`, `EvidenceRecordDetails.vue`, shared Table/Collapsible | Three independently paginated tables; identical mobile records; keyboard disclosures; full source values and backend exclusion labels |
| Confidence | `components/ui/progress/Progress.vue` | Warning tone for withheld employee results plus percentage and explicit status; no tier inference |
| Charts | Shared Unovis chart | Map null to a non-numeric line gap, preserve real zero, no interpolated missing data; distinct series patterns and legend labels |
| Failure feedback | Shared Alert/Button/Spinner | Inline recoverable errors and named Retry action; no native browser dialogs; retain last successful dashboard |
| Scrollbar/motion | `style.css` | Global semantic scrollbar colors, engine fallback, forced-colors default, reduced-motion override |

There are no create/edit/delete controls, bulk selection, or toast-based mutations in this workflow. Do not add those capabilities merely to fill a contract table.

## Presentation semantics

- Employee results show separate Data Issues and Performance Alerts columns in the table and both counts on employee cards below `2xl`. The backend assigns one category and review action to each finding; record details, report previews, and PDFs preserve that classification.
- Overall averages show scored, withheld, and total counts from the response. Null scores remain a dash with a withheld-status explanation.
- Weekly chart values and coverage populations follow the filtered backend response. Missing values are labeled per KPI in the data table, never shown as zero.
- The weekly chart and Action Center sit above Employee Results. On phones the chart precedes the Action Center. The Action Center reports findings rather than open actions because resolution status is not available in the API; its counts sum backend occurrences and identify distinct affected employees.
- Screens and PDFs display Gregorian dates as `DD/MM/YYYY`; the API keeps UTC date-only `YYYY-MM-DD` fields. Display the reporting period on employee details and include the year for historical clarity.
- Source interpretation remains available at `/data-interpretation`. The main dashboard has no interpretation card; the routed page preserves full-width source names and rationale above their badges on phones.

## Boundaries and validation

Reports remain transient browser downloads with existing manager-review notices. This UI work does not implement authentication or change permission policy, raw-data ingestion, KPI formulas, API evidence, or PDF rendering.

Build with `pnpm build` in `web/`. Browser regression coverage must include trailing/interior null chart points versus real zero, call-center facet combinations, page/sort return, failed filter/retry, employee preview failure/retry, open Select popups at phone widths, long labels, and no-results display. Completed checks and verification limits are recorded in [the test handover](handover.md#frontend-verification--2026-09-05).

## Employee evidence and report snapshots — 2026-09-14

Employee Details now offers the shared `ReportingPeriodPicker.vue` beside the employee identity.
It preserves non-period dashboard filters, commits the selected range only after a successful
dashboard response, and retries the last attempted range after failure. Its Performance explained
table uses backend scores, component breakdowns, and scoped averages; `EmployeeManagerSummary.vue`
shows the two highest measured component scores and only actionable backend findings, with their
source record IDs and review action. Record-specific details remain in
their evidence tables. In-page evidence links use the full selected-period record counts. The
page retains natural scrolling, and report previews still export their complete snapshot.

- `useEmployeeEvidence.ts` owns per-KPI fetching, cancellation, request sequences, pagination, and retry state. Each page contains five records. Scope changes clear old rows; a failed page request retains its last successful page and retries the attempted page.
- Evidence uses the dashboard's resolved dates. A differing `latest_submission_at` triggers a shared dashboard refresh; mismatched evidence is discarded. Successful refreshes reload all three tables even if dates and timestamp are unchanged.
- `App.vue` retains dashboard ownership. Employee Details routes refresh requests through the existing filter path. Failed refreshes retain current successful results and expose Retry results.
- Source statuses, attendance source confidence, missing values, real zero, and false first-pass approval retain distinct meanings. Python provides exclusions and finding impacts. Table counts include excluded audit records.
- Report preview receives complete evidence from one canonical read context, including prior comparison. Local pagination changes only presentation. Download uses that exact snapshot, including later pages and unopened details. Download failures retain the preview and allow retry.
- Evidence links must be absolute HTTPS URLs. Profile/evidence state remains in memory; report snapshots and PDFs are transient.

Completed API, browser, and PDF checks are recorded in
[employee review verification](#employee-review-verification--2026-09-14).

## Performance review presentation — 2026-09-14

Record-specific attention now lives in its KPI evidence table. `EmployeeAttentionSummary.vue`
and `EmployeeAttentionItem.vue` remain only for findings not represented by evidence records,
such as employee-level data issues. Informational findings with no scoring impact remain
omitted. Page fallback uses validated record-family findings; report preview checks its
complete evidence snapshot. Supporting records retain safe HTTPS links and IDs.

Data Issues cover missing, unverified, duplicate, or disconnected source evidence, including
incomplete leave documentation even when it affects a score. Performance Alerts cover verified
overdue work, late submissions, and low accuracy. Each finding retains its reason, action,
record IDs, and scoring impact. Employee list counts, record labels, summary cards, and PDF
sections use the backend category. Unverified outcomes do not create performance alerts.

`EmployeeDetailPage.vue` owns a help icon in each compact Productivity, Compliance, and Quality score card. Its floating, initially closed calculation panel opens by click, tap, or keyboard and shows only the matching sentence; Escape closes it. On-page evidence headers show only the table name; report preview retains score, weight, and record description in its evidence headings because it has no compact KPI cards. The separate Calculation details card remains removed. PDF exports retain all performance records and relevant issues while omitting calculation explanations and metric definitions. Report payload values and download snapshot handling remain unchanged.

Each KPI-card calculation panel uses one short sentence for its documented component
weights. The Data confidence explanation, detailed arithmetic, and the
required-evidence checklist are omitted from this disclosure;
backend explanations, evidence, scores, and report payloads remain unchanged.

`WeeklyKpiTrend.vue` owns the shared chart, legend, and missing-score gaps on the dashboard,
Employee Details, and employee report preview. It has no weekly-values disclosure. Employee Details
requests employee-scoped trends with its current resolved dates and refreshes when the canonical
submission timestamp differs. Report preview and PDF use the report snapshot's own trends, so
the generated file cannot drift from the preview.
The chart plots a point for each measured week, including isolated values. Employee Details and
report preview use its labeled detail scale (60–100%) only when all measured values are at least
60%; a lower score retains the 0–100% scale. The dashboard always uses 0–100%, and missing weeks
remain gaps. On Employee Details, Performance explained links directly to the matching evidence
section; the manager summary links to the evidence region. KPI component tabs follow the chart
and manager summary, before the independently paginated evidence sections.

## Employee table content

| KPI | On-page columns |
| --- | --- |
| Productivity | Work record · Status · Due → completed · Hours worked · Issues · Details |
| Compliance | Type · Date / period · Source outcome · Issues / scoring note · Details |
| Quality | Work / review · Review date · Accuracy · First pass / rework · Issues · Details |

The simplified columns serve both Employee Details and report preview. All KPI tables use
View record / Hide record controls; Compliance IDs remain in the disclosure, accessible
button names, and mobile card titles. Mobile cards expose the same summary
fields and issues. `EvidenceRecordIssues.vue` shows plain labels for backend findings,
explicit exclusion reasons, or No findings; it does not infer new issues from dates or
source statuses. Each desktop table has a concise screen-reader caption; the repeated visible
explanatory note beneath the table and phone cards is omitted.

Assigned dates, verification, detailed attendance times, submission completeness, leave
documentation, full finding messages, and safe evidence links remain in View record.
`evidenceSummaryColumns`/`evidenceSummaryCells` own compact presentation;
`evidenceColumns`/`evidenceCells`/`evidenceDetails` retain complete source presentation
for the existing PDF generator. `evidenceDisclosureDetails` exposes individual attendance
times on page/preview; missing fields identified by backend findings receive a warning
surface and explicit Needs review text. Storage and calculation contracts are unchanged.

Every KPI table has All records / Needs review controls, with the affected-record count on
the Needs review toggle. The initial mode is All records. Server counts cover the complete
employee/period scope; switching modes requests page 1, with chronological ordering in
either mode. Each table has independent mode and pagination state. Mode changes are
committed only on successful fetch; failure retains the previous page/mode and Retry
repeats the attempted request. Paging always uses the visible committed mode. A new
dashboard scope resets modes and pages. Empty review scope says No records need review.

Report preview applies the same controls to its complete supplied snapshot before local
pagination, without modifying that snapshot or limiting PDF export. Actionable records
have a subtle warning surface on desktop and mobile. Multiple findings on one record
count once; source statuses alone do not become new findings.

Each evidence table uses the dashboard's range, page-size Select, and page-navigation
footer. Five rows remain the default; managers can choose 15, 30, or All independently
for Productivity, Compliance, and Quality. A page-size change starts at page 1 and is
committed only after a successful live fetch. All loads successive API pages of at most
50 rows, checks their canonical freshness, and shows the complete selected mode. The
report preview uses the same sizes locally against its complete snapshot; choosing a
preview size never changes which records the PDF exports.

Evidence updates keep the last successful rows and empty state visible. A reserved space
beside the filters in the evidence header shows Updating records only after 180 ms, so fast responses do not flash a
spinner or insert a large loading block. Open disclosures survive updates when their
record remains in the returned page. Controls remain disabled while fetching, with
`data-busy` preserving their opacity through shared Button/Toggle styles; genuinely
unavailable controls keep the usual disabled treatment.

Visited evidence pages are cached only in component memory for 30 seconds, bounded to
eight pages per KPI. Keys include employee, resolved dates, snapshot timestamp, mode,
and page. Cache hits avoid repeat requests. Scope/dashboard refresh, freshness mismatch,
and disposal clear caches; retries bypass them. Scores, review counts, and rows continue
to come from backend responses. Nothing is saved to browser storage or SQLite.

Compliance uses one mixed table. Attendance details include scheduled/actual start and end,
lunch out/in, record status, and explicitly labeled source-record confidence. Submission
details include due/submitted dates, completeness, and verification. Leave details include
category, date range, outcome, and documentation completeness. Each type exposes its findings
and backend scoring impacts in the shared record disclosure.

Source outcomes do not imply calculated compliance. Source confidence is distinct from
employee data confidence. Missing values remain Not provided; real zero rework and
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

## Simplified evidence table verification — 2026-09-14

The loading refinement passed the production build, strict UI audit, and live Vite
component read. Vue rendering checks confirmed that existing records and empty review
states remain visible during fetching, with reserved status space and opt-in busy
controls. Mocked-fetch checks covered cache revisits, 30-second expiry, eight-page
capacity, failed-request retry, freshness invalidation, and dashboard-refresh reloads.
Visual and keyboard checks still require a connected browser.

The subsequent table-local review change passed all 65 backend regression tests,
`uv run ruff check app tests`, `pnpm build`, and the strict premium audit. Live EMP-005
review reads returned ATT-00276 and ATT-00263 together on page 1, with two affected
records out of 78 Compliance records. Vue rendering verified counts, plain labels,
missing-field highlights, empty review scope, and non-record fallback. A mocked-fetch
composable smoke check verified failed-filter retention/retry and stale-response
protection. Browser visual and keyboard verification remained unavailable because no
browser surface was connected. API filters changed; SQLite storage, KPI calculations,
complete report snapshots, and PDF rendering did not.

- `pnpm build` passed, including TypeScript checks. The premium strict static audit
  reported zero findings; its JSON output is in `storage/employee-tables-premium-audit.json`.
- The local Vite page and transformed table component returned HTTP 200. A read-only Vue
  server-rendering smoke check used 15 live canonical records across the three tables and
  verified record disclosures, loading/error/empty states, exclusions, real zero, false
  first-pass approval, and the unchanged original cell formatter used by PDF export.
- No browser surface was connected to the session; the in-app browser was unavailable.
  Desktop/mobile visual layout and keyboard interaction were not verified in this pass.
  The PDF renderer, API, scoring, persistence, and fetch/pagination behavior were unchanged.

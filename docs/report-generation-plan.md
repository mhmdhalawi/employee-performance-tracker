# Report generation implementation plan

Status: Employee, team-summary, and KPI-summary report MVPs implemented; production authorization remains required

## Goal

Add trustworthy, Cedar-branded reports that reuse the app's validated dashboard results. Python
must prepare every number, chart point, confidence value, date range, and evidence reference. AI
may optionally write a short narrative from approved findings, but it must never calculate or
alter report values.

The employee report uses a manager-previewed modal. The dashboard also provides direct browser
downloads for the current filtered team snapshot and for Productivity, Compliance, and Quality.
The richer data-quality report remains a future phase.

## Decisions required before implementation

1. Browser-generated, on-demand PDF export is approved. Server-side PDF rendering remains out
   of scope.
2. Reports contain employee data. Do not expose report preview or download routes to a client
   deployment until the API has real authentication and authorization or the entire deployment
   is protected by an approved external access gateway.
3. Decide whether generated PDFs are transient or retained. The MVP should render on demand and
   avoid storing report files. Saved report history, retention, and scheduled delivery belong to
   a later phase.
4. Approve the Cedar logo, colors, typography, footer language, and manager-review disclaimer
   before freezing the template.

## Non-negotiable rules

- Report values come from the same deterministic Python services used by the filtered dashboard.
- The requested employee, team, and date scope must apply consistently to report cards, trends,
  findings, evidence, and summaries.
- A confidence value below the configured threshold withholds Overall and tier. Component KPI
  values remain visible and are explicitly labeled as audit-only.
- Missing evidence is described as a confidence gap, never converted into zero performance.
- Approved leave neutrality and duplicate-attendance exclusion remain unchanged.
- AI cannot create scores, infer missing facts, change severity, or make employment decisions.
- Every narrative claim about a finding must cite validated record IDs. Links are shown only when
  their URL scheme and destination satisfy the application's evidence-link policy.
- Every report includes the reporting period, generation timestamp, metric definitions, data
  confidence, and a manager-review notice.
- Reports support coaching and management review; they do not decide hiring, termination,
  promotion, compensation, or discipline.

## Delivery scope

### Phase 1 - Employee Performance Report

Deliver a two-page PDF for one employee and one reporting scope.

Page 1 - result overview:

- Cedar identity, report title, employee name/ID, team, role, and selected period.
- Overall result, tier, and evidence confidence.
- Clear insufficient-data treatment when Overall is withheld.
- Productivity, Compliance, and Quality cards with score, target or benchmark, confidence context,
  and current trend direction.
- Change versus the prior comparable period when enough evidence exists.
- Strongest evidence-backed driver and highest-priority attention item.

Page 2 - evidence and action:

- KPI explanations derived from deterministic calculation results.
- Findings separated by scoring impact: affects score, lowers confidence, excluded, blocks score,
  and informational.
- Supporting record IDs and approved evidence links.
- Evidence gaps and a plain-language confidence explanation.
- Optional, validated narrative and low-risk next steps.
- Manager-review disclaimer and metric-definition footer.

### Phase 2 - KPI-specific reports

The MVP adds one-page KPI summary reports for:

- Productivity: completed versus target outputs, time efficiency, overdue outputs, trend, and
  evidence coverage.

The current exports include the backend-calculated KPI average, configured weight, employee
scores, evidence confidence, overall status, and weekly trend. More detailed sub-score and
evidence breakdowns require additional typed backend fields and remain an enhancement.
- Compliance: attendance checks, submitted reports, leave documentation, missing records, and
  confidence impact.
- Quality: accuracy, first-pass approval, rework, recurring validated findings, reviewed outputs,
  and evidence coverage.

### Phase 3 - Manager and data-quality reports

- Manager/Owner Team Report: the MVP exports the filtered team summary, employee results, weekly
  KPI trend, confidence, and withheld statuses. Strengths, an attention queue, and deterministic
  priority grouping remain enhancements that require typed backend fields.
- Data Quality Report: invalid, missing, duplicate, orphaned, unsupported, and blocked records;
  affected employees/KPIs; confidence impact; exact record IDs; and correction guidance.

### Phase 4 - retained and scheduled reports

After access control and retention policy exist, add saved report metadata, report history,
scheduled delivery, audience rules, expiry, and a user activity audit trail. This phase is not
part of the on-demand MVP.

## Proposed user experience

1. A manager opens Employee Details from the current filtered dashboard.
2. The manager selects **Generate report**.
3. The app shows a report preview using the current employee and reporting period.
4. The preview shows whether an AI narrative is unavailable or omitted without blocking the
   deterministic report.
5. The manager confirms **Download Cedar PDF**.
6. The browser creates the PDF from the validated preview snapshot and downloads a safe filename such as
   `cedar-employee-performance-EMP-005-2026-06-01-to-2026-08-22.pdf`.

From the main dashboard, **Generate team report** downloads the current filtered team snapshot.
Each Productivity, Compliance, and Quality summary card also exposes an accessible PDF-download
action for that KPI and the same active filters.

The first version should not add an independent report filter form. It should inherit the
dashboard's employee and period scope to prevent the preview and dashboard from disagreeing.

## Backend design

### Report schemas

Create `app/schemas/reports.py` with typed models for:

- `EmployeeReportRequest`: employee ID plus either `period_weeks` or inclusive start/end dates,
  optional audience, and an explicit `include_ai_narrative` flag.
- `ReportPeriod`: resolved start/end dates and an optional prior comparable period.
- `ReportKpiSection`: KPI name, score, display status, target labels, deterministic explanation,
  trend points/delta, evidence coverage, and supporting records.
- `ReportFinding`: severity, scoring impact, message, record IDs, and validated evidence links.
- `EmployeeReportData`: the renderer-ready, fully validated snapshot for both preview and PDF.
- `EmployeeReportPreviewResponse`: report data plus narrative availability and generation metadata.

Keep the renderer input separate from `DashboardResponse`. This prevents layout code from
reinterpreting API values and gives preview and PDF one shared contract.

### Deterministic report-data service

Create `app/services/reports.py`. It should:

1. Load the canonical aggregation state using the existing persistence layer.
2. Resolve filters exactly as `/dashboard` does. Extract the shared filter/materialization path
   instead of calling an API handler or duplicating date logic.
3. Build one employee result from the deterministic calculation services.
4. Load that employee's performance targets and calculate the prior comparable period in Python.
5. Reuse weekly trend calculation for the employee scope.
6. Select findings and supporting evidence already validated for that employee.
7. Convert the result into `EmployeeReportData` without importing FastAPI or renderer concerns.
8. Raise typed `AppError` subclasses for missing canonical data, unknown employees, invalid
   periods, and reports that cannot be rendered safely.

Do not parse human-readable KPI reason strings to recover report values. Add typed KPI breakdown
fields to the deterministic result/report contract where the current response lacks target,
sub-score, or evidence-coverage values.

### Optional narrative

Only `app/services/agent.py` may call a model. If `include_ai_narrative` is true:

1. Pass only the bounded `EmployeeReportData` status and validated findings to the explanation
   agent; never pass raw source rows or complete calculation inputs.
2. Require structured output with a short summary, up to two next steps, and record IDs.
3. Validate every employee ID and record ID against the report snapshot.
4. Drop or reject unsupported statements before rendering.
5. Fall back to the deterministic report when AI is unconfigured, unavailable, or invalid. PDF
   generation must not depend on an API key.

### Browser PDF generator

Add a focused TypeScript generator that accepts only `EmployeeReportData` and creates PDF bytes
in the browser. The generator may format backend-provided values, but it must not calculate or
reinterpret KPI results.

- Build reusable header, footer, KPI card, finding, confidence, trend, and disclaimer sections.
- Use only backend-provided chart and table values.
- Bundle fonts and brand assets with the web app. Do not fetch assets at generation time.
- Keep output in browser memory only long enough to download it.
- Bound displayed text, sanitize filenames, and prevent imported values from controlling paths or markup.

### API contract

Add a thin `app/api/reports.py` router under `/api/v1/reports`:

- `POST /employee/preview` returns `EmployeeReportPreviewResponse`.
The browser uses this exact preview response to create the PDF, so preview and download cannot
use different calculations. The endpoint returns `Cache-Control: no-store`.

## Frontend design

Extend `EmployeeDetailPage.vue` and its parent orchestration:

- Show **Generate report** only when one employee is selected.
- Preserve the currently applied reporting period in the request.
- Open an accessible preview dialog or page with loading, API-error, AI-unavailable, and
  insufficient-data states.
- Display the exact resolved period and confidence gate before download.
- Create and download the PDF from the preview snapshot without recalculating or modifying report data.
- Disable duplicate submissions while previewing or downloading.
- Revoke temporary object URLs after download.
- Keep the action usable on mobile and by keyboard.

Add frontend report types in `web/src/types/` or split the growing analysis contract into focused
type modules when implementation begins. Do not add KPI arithmetic to Vue.

## Security and privacy requirements

- Require authorization for preview and PDF download; permission must be checked again on every
  download, not only when the employee page opens.
- Do not place sensitive employee values in URLs beyond the minimum opaque/stable identifier.
- Return `Cache-Control: no-store` and avoid CDN/browser caching of personalized PDFs.
- Do not log PDF bytes, AI narrative inputs, or full employee report payloads.
- Allow only approved `https` evidence destinations, or render record IDs as non-clickable text.
- Prevent cross-employee access by validating the requested employee against the caller's scope.
- Add size and rendering-time limits to protect the synchronous endpoint.
- If report persistence is later added, encrypt/secure stored files, define expiry and deletion,
  and record who generated and downloaded each report.

## Implementation sequence

### Milestone 1 - shared deterministic snapshot

- [x] Approve browser-generated PDF scope.
- [x] Add report request/response and renderer-data schemas.
- [x] Reuse aggregation/filter resolution used by the dashboard.
- [x] Add typed KPI, evidence coverage, and prior-period values without changing
  existing calculations.
- [x] Build `EmployeeReportData` and regression tests.

Exit condition: one service call produces a complete, deterministic report snapshot matching the
same filtered dashboard result.

### Milestone 2 - two-page employee PDF

- [x] Add the browser PDF dependency.
- [x] Implement the Cedar report generator with bundled fonts.
- [x] Add deterministic explanations and the required disclaimer.
- [x] Add the typed preview endpoint.
- [x] Render benchmark examples for scored and insufficient-data employees.

Exit condition: a manager can preview and download a readable two-page employee PDF with no API
key configured.

### Milestone 3 - frontend flow and hardening

- [x] Add Generate report, preview, and download controls to Employee Details.
- [ ] Add authenticated/authorized access controls or enforce the approved external gateway.
- [x] Validate filenames, evidence URLs, caching headers, and failure behavior.
- [ ] Verify desktop and mobile layouts and keyboard interaction in an interactive browser.

Exit condition: the end-to-end flow is safe for the intended pilot environment.

### Milestone 4 - report family expansion

- [x] Add the three KPI summary templates.
- [x] Add the manager/team summary template.
- [ ] Add the data-quality template.
- [x] Reuse the same deterministic dashboard snapshot and visual components.

Exit condition: every report family applies identical filters, confidence rules, and evidence
semantics.

## Testing and acceptance criteria

### Backend tests

- Preview values exactly match the filtered dashboard for employee, team, explicit-date, and
  4/8/12-week scopes.
- The prior period is comparable and non-overlapping, or clearly unavailable.
- Overall and tier are absent below the confidence threshold while component KPIs remain visible.
- Targets, trends, findings, supporting record IDs, and evidence links belong to the selected
  employee and period.
- Duplicate attendance and approved leave behave exactly as existing regression tests require.
- AI citations outside the validated snapshot are rejected; AI failure still produces a report.
- Unknown employee, invalid period, missing canonical state, rendering failure, and unauthorized
  access return consistent errors.
- The PDF starts with a valid PDF signature, has the expected page count, and contains required
  metadata and disclaimer text.

### Visual PDF verification

For every meaningful renderer change:

1. Generate at least one normal scored report and one insufficient-data report.
2. Render every PDF page to PNG with Poppler.
3. Inspect headers, footers, page numbers, wrapping, chart labels, evidence lists, long employee
   names, missing optional values, and page breaks.
4. Confirm there is no clipped text, overlap, unreadable glyph, or unexpected blank page.
5. Reopen the PDF with a parser and verify page count and extractable required text.

### Frontend acceptance

- Preview and download use the same employee and resolved period shown by the dashboard.
- Loading, empty, unauthorized, expired-session, API-error, and insufficient-data states are
  explicit.
- Repeated clicks do not start duplicate renders.
- The flow works at representative desktop and mobile widths without page-level overflow.
- Controls have accessible names, focus behavior, and keyboard operation.

### Final MVP acceptance

- A manager can open an employee, preview the report, and download a Cedar-branded two-page PDF.
- The report reproduces deterministic dashboard values and the 70% confidence guardrail.
- Every finding is traceable to validated record IDs; unsafe links are never clickable.
- The report works without AI and clearly labels optional AI narrative when present.
- No browser-side KPI calculation exists.
- The complete backend suite, new report tests, frontend build, and visual PDF checks pass.

## Explicitly deferred

- Email delivery and scheduling.
- Saved PDF files and report version history.
- Bulk ZIP exports.
- Custom client template builders.
- Electronic signatures or approval workflows.
- Automatic employment actions or recommendations.
- Multi-tenant report storage before tenant isolation exists.

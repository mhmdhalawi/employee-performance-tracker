# Cedar Employee Performance Dashboard - Required Fixes Audit

Audit date: 2026-09-17

Source: `Cedar_Employee_Performance_Dashboard_Required_Fixes.pdf`

This file extracts the issue list and acceptance checks from the PDF, then records the result of testing the current worktree. The PDF is treated as review evidence, not as repository instructions. Where it conflicts with the maintained product rules, the repository rules remain authoritative.

## Status summary

- Verified done: 2 of 14
- Partially implemented but still open: 5 of 14
- Not implemented or acceptance check failed: 7 of 14
- Critical release gate: **not passed**
- Manager success test: **not passed**
- Final call-center acceptance scenario: **blocked by missing call-center model and filters**

Legend:

- `[x]` means the completion check was verified in the running app.
- `[ ]` means work remains. A partial implementation stays unchecked.

## Critical fixes

### [x] 1. Dashboard and PDF show different Productivity scores

- Required solution: Use one scoring service and one calculation snapshot for the dashboard, employee page, and every exported report.
- Completion check: The same employee, period, and filters return identical values everywhere.
- Result: **Verified done.**
- Evidence: For EMP-001 over 2026-05-25 through 2026-08-21, the dashboard row, employee page, report preview, and downloaded 12-page PDF all showed Productivity `96.1%`. The employee page, report preview, and PDF all showed overall `96.3%`. The report-preview integration test also verifies dashboard/report KPI and overall parity.

### [ ] 2. Overall and KPI averages use different employee groups

- Required solution: Calculate all summary cards from scored employees only, or clearly label cards that include withheld employees.
- Completion check: Every card states its population and reconciles with the visible employee list.
- Result: **Not done.**
- Evidence: The live full-period response had 30 employees, with 7 scored and 23 withheld. Overall `91.11%` is calculated from the 7 scored employees, while component KPI cards use all 30 employees. The differences were:

  | KPI | Displayed / all employees | Scored employees only |
  | --- | ---: | ---: |
  | Productivity | 87.25% | 93.38% |
  | Compliance | 92.85% | 95.69% |
  | Quality | 74.29% | 84.90% |

- The Overall card says `Scored employees only`; the three KPI cards show only their overall weights and do not state that withheld employees are included.
- Remaining fix: Either calculate every summary card from scored employees, or explicitly label each KPI card and report summary with its population.

### [ ] 3. Dashboard is based on generic projects

- Required solution: Replace the demo model with call-center employees, calls, cases, shifts, queues, campaigns, and QA reviews.
- Completion check: A call-center manager recognizes the data and workflow without explanation.
- Result: **Not done.**
- Evidence: The live schema and UI still use Projects / work outputs, project targets, attendance, reports, leave, and quality reviews. There are no call, case, campaign, queue, shift, or supervisor records in the current model.

### [ ] 4. Findings mix data and performance problems

- Required solution: Create separate Data Issues and Performance Alerts categories.
- Completion check: Each issue appears in exactly one category with a clear reason and action.
- Result: **Not done.**
- Evidence: The dashboard exposes one `Findings` count and Employee Details uses one `Needs attention` presentation. Backend findings carry a `scoring_impact`, which may support a split, but the product does not present two manager-facing categories or actions.

### [ ] 5. KPI results are not fully explainable

- Required solution: Show target, actual result, sub-metric score, weight, and contribution to the final KPI in View Details.
- Completion check: A manager can reproduce the score without asking the developer.
- Result: **Partially implemented; still open.**
- Evidence: Employee Details shows each KPI score, its overall weight, source evidence, and a help popover containing only the generic formula (for example, `60% completion, 40% time efficiency`). It does not show a structured employee-specific target, actual, sub-metric scores, or weighted contribution. The backend reason string contains some of this information, but the current page and preview do not render it.
- Remaining fix: Return and render a structured deterministic calculation breakdown. Do not parse prose or recalculate KPI arithmetic in Vue.

### Critical release gate

The PDF says not to approve scoring release until all five critical checks pass and one employee reconciles across dashboard, details, and PDF. EMP-001 reconciliation passed, but checks 2-4 failed and check 5 is incomplete. The release gate therefore remains **closed**.

## Manager value improvements

### [ ] 6. No central management action list

- Required solution: Add an Action Center with employee, alert, recommendation, owner, deadline, and status.
- Completion check: Managers can assign, track, and close an action from one screen.
- Result: **Not done.**
- Evidence: No Action Center route, data model, assignment control, owner, deadline, or close workflow is present.

### [ ] 7. No target or period comparison

- Required solution: Show Actual vs Target, change from the previous period, and team benchmark for each KPI.
- Completion check: Each KPI immediately shows direction and performance gap.
- Result: **Partially implemented; still open.**
- Evidence: The employee report can show an overall change from a prior comparable period, and the app shows weekly KPI trends. It does not show previous-period change or team benchmark for each KPI. Employee-specific targets are not visible in the KPI sections.

### [ ] 8. Confidence may be mistaken for performance

- Required solution in the PDF: Rename it Data Confidence or Evidence Completeness and explain the threshold.
- Completion check: Users understand that confidence measures data reliability, not employee ability.
- Result: **Partially implemented; still open.**
- Evidence: Employee Details and report preview use `Evidence confidence`, show the required threshold, and explain that low evidence withholds the overall result. The main desktop table still says `Confidence`, and mobile rows say only `NN% confidence`.
- Important conflict: The PDF refers to a 70% threshold. The maintained product requirement supersedes this with a **100% evidence-confidence gate**. The live app correctly displays and enforces 100%; this must not be changed back to 70%.
- Remaining fix: Standardize the manager-facing label across every surface, preferably `Evidence completeness` or `Data confidence`, while keeping the 100% gate and explanation.

### [ ] 9. Reports lack a coaching plan

- Required solution: Add strengths, gaps, evidence, recommended actions, owner, and next review date.
- Completion check: The PDF can be used directly in a manager coaching discussion.
- Result: **Partially implemented; still open.**
- Evidence: The employee report includes KPI results, evidence, findings, trends, and a manager-review notice. It does not include a structured strengths/gaps section, recommended actions, action owner, or next review date.

### [ ] 10. Call-center filters are missing

- Required solution: Add Campaign, Queue, Shift, Supervisor, and Location filters.
- Completion check: Cards, employees, trends, and reports update consistently for every filter.
- Result: **Not done.**
- Evidence: The dashboard currently provides Employee, Team, and Reporting period filters only. Team and period filtering were verified to update the cards, employee population, trends, and team report preview, but none of the required call-center filter dimensions exist.

### Manager success test

The PDF expects a manager to identify a gap, verify evidence, assign an action, and export a coaching report from the main dashboard. Evidence review and report export work. Action assignment and a complete coaching plan do not, so the success test remains **open**.

## Client readiness checks

### [ ] 11. Data Interpretation is too technical for managers

- Required solution: Move calculator mappings to Admin or Audit and provide a short plain-language manager explanation.
- Completion check: Managers see business meaning while administrators retain technical traceability.
- Result: **Partially implemented; still open.**
- Evidence: The dashboard card provides a short description, but `View details` opens a manager-visible page containing calculator names, field bindings, source columns, and classification confidence. The technical mapping has not moved behind an Admin/Audit boundary.

### [ ] 12. No visible account controls

- Required solution: Add a clear account menu with Sign Out.
- Completion check: The user can end the session from every main page.
- Result: **Not done.**
- Evidence: No account menu or Sign Out control appears on the dashboard, employee details, or Data Interpretation pages. The current worktree also contains an existing uncommitted change setting `isAuth` to `true`, so the local sign-in screen is bypassed during this audit. There is no backend authorization layer.

### [ ] 13. Regional date format is unclear

- Required solution: Use `21 Aug 2026` or `21/08/2026` consistently across screens and PDFs.
- Completion check: No screen or report mixes regional and US date formats.
- Result: **Not done.**
- Evidence: The dashboard, employee page, report preview, and downloaded PDF use US-style dates such as `May 25, 2026` and `Aug 21, 2026`.

### [x] 14. Mobile usability is not confirmed

- Required solution: Test dashboard cards, filters, tables, employee details, and reports on common mobile widths.
- Completion check: No horizontal page overflow, clipped controls, or unreadable tables remain.
- Result: **Verified done for the browser UI at 390 x 844.**
- Evidence: Playwright checks found no horizontal document overflow on the dashboard, Employee Details, Data Interpretation, or the report-preview dialog. The dashboard uses mobile employee cards, evidence tables switch to labeled cards, and the report dialog keeps its controls inside a 358 px-wide scrollable surface.
- Scope note: The downloaded PDF has a separate pagination defect listed below; it does not invalidate the browser-width check.

## Recommended implementation order extracted from the PDF

1. **Accuracy:** Unify score calculations and aggregation populations so dashboard, details, and reports reconcile.
2. **Call-center model:** Replace generic project data and expose explainable sub-metrics so the demo matches call-center operations.
3. **Manager workflow:** Add alerts, actions, comparisons, filters, and coaching reports so insights lead to accountable actions.
4. **Release quality:** Simplify technical content and complete account, date, mobile, and export checks.

## Final acceptance scenario extracted from the PDF

Use one filtered call-center scenario: select a campaign, employee, and reporting period, then verify cards, trends, details, alerts, and PDF outputs before release.

Current result: **Blocked.** Employee, team, and reporting-period paths work, and a filtered AI Automation / Last month team preview correctly showed 6 employees for 2026-07-22 through 2026-08-21. The required Campaign filter and call-center data model do not exist.

## Additional defects found during testing

### [ ] A. Employee PDF continuation pages clip and overlap rows

- Severity: High, because it makes exported evidence hard to read and contradicts the report QA requirement.
- Evidence: The generated EMP-001 report contained 12 pages. Pages 4, 6, 8, and 10 began with clipped or overlapping continuation rows; text at the left edge was truncated (for example, `ttendance`), and the Compliance section/table headings were not repeated on every continuation page.
- Remaining fix: Repair pdfmake page-breaking so ordinary rows remain intact, continuation pages start below the header, and section/table headings repeat. Re-render and inspect every page of both scored and insufficient-data examples.

### [ ] B. Documented `127.0.0.1` frontend URL fails CORS by default

- Severity: Medium, development/release-readiness issue.
- Evidence: Loading `http://127.0.0.1:5173/` caused the dashboard request to be blocked because the backend default allows only `http://localhost:5173`. Loading `http://localhost:5173/` worked. The README and AGENTS development URLs use `127.0.0.1`, while `.env.example` includes both origins.
- Remaining fix: Make the default CORS origins and documented development URL agree, then add a small configuration regression test.

### [ ] C. Current local auth gate is bypassed

- Severity: Context-dependent; high if this state is deployed.
- Evidence: The current worktree has an existing uncommitted `web/src/App.vue` change from an undefined authentication state to `true`. This audit did not modify it.
- Remaining fix: Decide whether the bypass is intentional development-only behavior. Do not ship it as access control; the repository currently has no backend authorization layer.

## Verification performed

- PDF extraction: 4 source pages rendered and visually inspected; all 14 issue rows, their required solutions, completion checks, and three release/success/final gates were captured above.
- Live browser: Playwright MCP against the running FastAPI and Vite apps.
  - Desktop dashboard at 1440 x 1000.
  - Mobile dashboard, employee details, Data Interpretation, and report preview at 390 x 844.
  - Employee navigation, formula help/Escape behavior, Team filter, Last month period preset, filtered team report preview, report preview, and PDF download.
  - No horizontal overflow at 390 px on the tested browser surfaces.
  - EMP-001 score parity across dashboard, details, preview, and downloaded PDF.
- Generated PDF: all 12 EMP-001 pages rendered and visually inspected.
- Backend: `uv run python -m unittest discover -s tests -v` - **70 tests passed**.
- Backend lint: `uv run ruff check app tests` - **passed**.
- Frontend: `pnpm build` - **passed**; Vite reported the existing large-chunk warning.
- Static UI audit: strict frontend-premium audit - **0 findings**.
- Anti-pattern scan: no native `alert`/`confirm`/`prompt`, clickable `div`/`span`, clickable table header, unsafe HTML assignment, or local-storage matches. The only `!important` uses are the documented reduced-motion overrides.

## Test limitations

- No automated PDF visual-regression suite exists; the PDF pagination failure was found by manual rendering and inspection.
- Authentication/sign-out could not pass because no Sign Out workflow exists and the current local worktree bypasses the sign-in screen.
- Campaign, Queue, Shift, Supervisor, and Location scenarios cannot be exercised until their data and filter contracts exist.

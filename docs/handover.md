# Final test handover

## Reproducible command

From a fresh checkout with `uv` installed, run:

```bash
uv run python -m unittest discover -s tests -v
```

`uv run` restores the locked Python environment as needed. The acceptance suite does not
require `OPENAI_API_KEY`: it replaces only the planning-model call with a fixed, validated
calculation plan, while retaining the real multipart API, XLSX/CSV parsing, dataset binding,
validation, filtering, and deterministic scoring path.

## Committed benchmark package

- `tests/fixtures/cedar_30_sanitized.json` defines 30 fictional employees and the guardrail
  cohorts. Names and evidence URLs are generated placeholders.
- `tests/fixtures/cedar_30_expected.json` pins expected KPI outputs, the 0.1 parity tolerance,
  and the two accepted workbook discrepancies.
- `tests/benchmark_fixture.py` deterministically expands the specification into the seven
  source tables and an in-memory XLSX workbook.
- `tests/test_benchmark.py` verifies all 30 results, EMP-027 through EMP-030 confidence gating,
  duplicate exclusion, traceability, and the EMP-027/EMP-029 exception allowlist.
- `tests/test_api_integration.py` verifies XLSX and CSV uploads, incremental JSON aggregation,
  immutable audit history, idempotency, overlapping upserts, corrections, source-version ordering,
  concurrent identity protection, persisted plans, partial evidence batches that reuse canonical
  foundations, mixed-schema safeguards, backend period presets, employee/team/date filters,
  employee report parity and confidence gating, invalid rows, malformed files, and invalid filters.

The fixture is intentionally synthetic. It reproduces the agreed acceptance guardrails without
copying employee-level content from the confidential source workbook.

## Two-submission acceptance procedure

1. Start the API and submit one daily payload to
   `POST /api/v1/analyze-tables` with an `Idempotency-Key`. Confirm `201 Created` and retain its
   `submission_id`.
2. Submit the next daily payload with a different key. It may repeat prior stable record IDs;
   repeated IDs are upserts and new IDs extend canonical state.
3. Request `GET /api/v1/dashboard`. Confirm `included_submission_count`, `coverage_start`, and
   `coverage_end`, and verify evidence from both dates contributes to one recalculated result.
4. Request employee, team, explicit-date, and `period_weeks=4|8|12` views. Confirm returned
   `applied_filters`, summaries, alerts, confidence, supporting evidence, and trends use the same
   scope while filter options remain available.
5. Replay the first idempotency key and confirm the original receipt is returned without another
   submission. Send a changed existing record ID and confirm its one canonical row changes once.
6. Restart the API and repeat the dashboard reads. No mapping-model call should occur.
7. Request `POST /api/v1/reports/employee/preview` for a scored employee and an insufficient-data
   employee. Confirm the snapshot matches the same filtered dashboard values, carries
   `Cache-Control: no-store`, and withholds overall score and tier without hiding component KPIs.

In the browser, Employee Details previews and downloads the employee snapshot. The team-report
preview and the team/KPI download actions consume the current filtered dashboard response. All
PDFs are generated locally with `pdfmake`; no generated file is persisted by the backend.

`web/data/request.json` and `web/data/request2.json` are full manual fixtures for this flow;
`request2.json` contains changed evidence plus additional attendance duplicates.

The automated partial-submission regression first publishes employees, targets, and KPI evidence
without quality reviews, then submits a quality-only table. The second batch deliberately omits
employee and target tables. It must complete by reusing canonical foundations, and the dashboard
must retain the employee population while adding quality evidence and recalculating confidence and
overall results. A KPI-only first submission against an empty database must still fail plan
validation.

## Verified output

Aggregation run: 2026-09-03, Python 3.14, Windows.

```text
----------------------------------------------------------------------
Ran 53 tests

OK
```

The run reproduced 30 employee results, four duplicate-attendance exclusions, the partial-quality
submission flow, and the 60%
confidence gate for EMP-027 through EMP-030. EMP-027 and EMP-029 are the only allowed parity
exceptions: production retains duplicate exclusion, with documented workbook compliance
differences of 0.2304 and 0.3789 respectively.

`pnpm build` also passed on 2026-09-03. It type-checked the employee, team, and KPI browser PDF
generators and produced their lazy-loaded `pdfmake`/font chunks. Vite reports those PDF chunks as
larger than 500 kB; they remain dynamically imported and are loaded only when a report is created.
There is no automated PDF visual-regression suite, so renderer changes still require manual page
inspection for both scored and insufficient-data examples.

## Frontend verification — 2026-09-05

The dashboard fixes follow [the visual direction](design.md) and [UX guidelines](ux-guidelines.md). `pnpm build` passed TypeScript checking and the production build; Vite's large-chunk warning remains. The frontend-design-premium strict static audit reported zero findings, and `git diff --check` passed. These checks do not replace rendered accessibility or PDF testing.

Playwright checks ran against the local frontend and API at ports 5173 and 8000:

| Coverage | Observed result |
| --- | --- |
| Responsive dashboard at 390, 768, 1024, and 1440px widths | Filters fit; mobile employee cards preserve metrics; no document horizontal overflow |
| Team → employee → back; page 2 and overall-sort return | Applied team, result scope, page, and sort remain aligned |
| Failed filter request → Retry filters | Previous applied selection and results remain visible; retry applies the requested scope |
| Trend fixture `[0, 20, null, 40, 60, null]` | Two separate SVG line segments, real zero retained, and two explicit missing-data labels |
| Team and employee previews on desktop/phone | Cards display fully; body scrolls; footer remains reachable |
| Withheld employee preview at 390 × 520 | Settled dialog stays within the viewport with its download action contained |
| Failed employee preview → Retry preview | Snapshot reload succeeds |
| Empty dashboard and long employee-name fixtures | Explicit empty messages, disabled team export, wrapping names, and no page overflow |
| Select keyboard interaction | End/Enter selects a team; Escape returns focus to the trigger |
| Mobile interpretation | Source identity occupies full card width without document overflow |
| Reduced-motion emulation | Preference activates; global CSS override inspected |

Failure and edge-case fixtures used temporary browser response interception. All interceptions were removed; checks did not modify SQLite or source evidence and made no model requests. These were live browser checks, not a newly committed automated browser suite. The backend regression suite was not rerun for this frontend-only pass.

Actual PDF pages, sign-in, screen readers, a full 200% zoom matrix, physical touch devices, and dark mode were not verified in this pass. PDF generators were unchanged; future renderer changes still require every-page visual inspection of scored and insufficient-data exports. Remaining design proposals are maintained in `design.md`.

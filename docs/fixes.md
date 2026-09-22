# Selected dashboard fixes

Source: `Cedar_Employee_Performance_Dashboard_Required_Fixes.pdf`. Row numbers below count data rows after each table header. This file lists the remaining requested fixes.

## Critical fixes (page 2)

| Row | Issue | Required solution | Completion check |
| --- | --- | --- | --- |
| 4 | Findings mixes data and performance problems | Create two separate categories: Data Issues and Performance Alerts. | Each issue appears in only one category with a clear reason and action. |

## Manager value improvements (page 3)

| Row | Issue | Required solution | Completion check |
| --- | --- | --- | --- |
| 3 | Confidence may be mistaken for performance | Rename it Data Confidence or Evidence Completeness and explain the 70% threshold. | Users understand that confidence measures data reliability, not employee ability. |

**Project override:** The PDF's 70% threshold is superseded by the client's 100% evidence requirement in `AGENTS.md` and `docs/benchmark.md`. Any implementation or user-facing explanation should use 100%.

## Client readiness checks (page 4)

| Row | Issue | Required solution | Completion check |
| --- | --- | --- | --- |
| 1 | Data Interpretation is too technical for managers | Move calculator mappings to Admin or Audit and provide a short plain-language manager explanation. | Managers see business meaning; administrators retain technical traceability. |
| 3 | Regional date format is unclear | Use 21 Aug 2026 or 21/08/2026 consistently across screens and PDFs. | No screen or report mixes regional and US date formats. |

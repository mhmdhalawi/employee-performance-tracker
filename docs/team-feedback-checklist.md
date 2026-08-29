# Team Feedback Resolution Checklist

This checklist tracks the team's feedback against the latest verified response,
`response_1787848691720.json`. Use it to implement and verify each requirement individually.

## Status summary

- Resolved: 6
- Partially resolved: 4
- Not resolved: 3

Day 3 deterministic KPI work is complete with the documented QA-01/QA-10 benchmark
exception for EMP-027 and EMP-029.

## 1. Process all 30 employees

- [x] Return exactly 30 employee results.
- [x] Include EMP-001 through EMP-030.
- [x] Include EMP-030 and a complete top-level response after the employee results.

Verified: the latest JSON contains 30 results, beginning with EMP-001 and ending with EMP-030.

## 2. Apply confidence consistently to required evidence

- [x] Define which project, attendance, report, and quality records count as required evidence.
- [x] Make missing project evidence lower confidence.
- [x] Make missing required attendance evidence lower record confidence.
- [x] Make missing required report evidence lower confidence.
- [x] Make missing required quality evidence lower confidence.
- [x] Ensure validation findings describe the confidence impact consistently.

Verified: all 8 missing-project, 37 missing-exit, 3 missing-report-evidence, and 8
missing-quality-evidence findings use `scoring_impact: "lowers_confidence"`.

Acceptance criteria met: required project, submitted-report, and quality evidence contributes
to employee data confidence. Missing attendance exits lower record confidence under QA-03.

## 3. Return employee data confidence

- [x] Add a numeric `data_confidence` value to every employee result.
- [x] Add or expose the applicable `confidence_threshold` (70% by default).
- [x] Explain which available and missing evidence produced the confidence value.
- [x] Preserve supporting source record IDs for confidence deductions.

Verified: all 30 employee results contain `data_confidence`, `confidence_threshold`, a
source-level confidence explanation, and supporting record IDs.

Acceptance criteria: confidence is visible, reproducible from the evidence, and returned for all 30 employees.

## 4. Enforce the low-confidence guardrail

- [x] When confidence is below 70%, set the performance result to `Insufficient data`.
- [x] Do not return an overall score below the threshold.
- [x] Do not return a performance tier below the threshold.
- [x] Verify EMP-027, EMP-028, EMP-029, and EMP-030 are treated as insufficient when their confidence is 60%.
- [x] Retain component KPI calculations below the threshold, as required by `Expected_KPI`, while withholding the overall result and tier.

Verified: EMP-027 through EMP-030 each return 60% confidence, a 70% threshold,
`Insufficient data`, no overall score, and no performance tier.

Acceptance criteria: EMP-027 through EMP-030 return `Insufficient data`, with no overall score or tier.

## 5. Calculate overall performance

- [x] Add `overall_score` when confidence is at least 70%.
- [x] Calculate it deterministically in Python using:

  `Overall = Productivity × 35% + Compliance × 30% + Quality × 35%`

- [x] Round public score values to two decimal places consistently.
- [x] Preserve enough component values to reproduce the calculation.
- [x] Verify results against `Expected_KPI`; document the confirmed EMP-027 and EMP-029
  Compliance exception caused by benchmark duplicate inclusion conflicting with QA-01.

Verified: 26 eligible employees receive overall scores calculated from full-precision KPI
components. The four low-confidence employees do not receive overall scores.

Documented exception: QA-01 requires duplicate attendance exclusion, but a controlled API parity
run confirmed that the `Expected_KPI` values for EMP-027 and EMP-029 include the duplicate rows. Their compliance differences
are 0.2304 and 0.3789. Production preserves QA-01; the benchmark values require correction
or confirmation from their owner.

Acceptance criteria met: every eligible employee has a reproducible overall score, while
ineligible employees do not. The controlled parity test proved the only Compliance exception
comes from duplicate rows retained by the workbook benchmark.

## 6. Add performance tiers

- [ ] Define the tier names and numerical boundaries from an authoritative source.
- [x] Add `performance_tier` only when confidence is at least 70%.
- [x] Verify all current benchmark tier outputs match `Expected_KPI`.
- [ ] Do not infer tier boundaries if the benchmark or product specification does not define them.

Verified: all 26 eligible employees receive tiers matching the current `Expected_KPI`
statuses, while the four low-confidence employees receive no tier.

Acceptance criteria: eligible employees receive the correct tier; low-confidence employees receive no tier.

## 7. Produce a consistent final narrative

- [x] Add a structured team/executive summary if it is part of the expected response.
- [x] Generate the summary from the final validated results, not from an earlier workflow stage.
- [x] State the number of scored employees and the number marked `Insufficient data`.
- [x] Ensure the narrative never says that no scores were calculated when scores are present.

Verified in code: the deterministic summary reports total, scored, and insufficient-data
counts, affected employee IDs, tier counts, and a narrative generated from the final KPI
results. Against the latest response it reports 30 analyzed, 26 scored, and 4 insufficient.

Acceptance criteria: all narrative counts and claims match the structured response exactly.

## 8. Provide dashboard and filters

- [x] Build a working dashboard consuming the analysis response.
- [x] Add employee filtering.
- [x] Add team filtering when team information is available and mapped.
- [x] Clearly distinguish scored employees from `Insufficient data` employees.
- [x] Display overall score and tier only for eligible employees.

Verified in code: the Vue dashboard consumes the analysis response, applies employee, team,
and reporting-period filters through the API, distinguishes insufficient-data results, and
withholds overall scores and tiers when the backend returns them as unavailable.

Acceptance criteria: a user can filter and inspect employee and team performance through the working interface.

## 9. Add 12-week trends

- [x] Return or derive weekly KPI data covering the complete 12-week period.
- [x] Add employee-level trends.
- [x] Add team-level trends when team data is available.
- [x] Represent missing weekly evidence without treating it as a zero score.
- [ ] Preserve traceability from trend points to supporting records.

Current state: deterministic weekly series are returned and respond to employee, team, and
period filters. Missing component values remain unavailable rather than becoming zero. Trend
points include record counts, but do not yet return the supporting record IDs directly.

Acceptance criteria: the dashboard displays auditable 12-week trends without inventing values for missing evidence.

## 10. Add alerts

- [x] Convert relevant validation findings into explicit employee alerts.
- [x] Assign alert type and priority/severity.
- [x] Include supporting record IDs or evidence links.
- [ ] Distinguish data-quality alerts from performance alerts.
- [x] Avoid duplicating the same issue in findings and alerts without a clear reason.

Current state: the response contains grouped, prioritized employee alerts with supporting
record IDs and evidence links where available. The employee table shows per-employee alert
counts, and its responsive detail sheet presents the employee's alerts alongside on-demand AI
guidance. An explicit data-quality versus performance-alert category is still outstanding.

Acceptance criteria: actionable alerts are clearly presented and traceable to source evidence.

## 11. Add recommendations

- [ ] Add evidence-backed employee recommendations.
- [ ] Add team recommendations where supported.
- [ ] Do not generate recommendations from insufficient or unverified evidence.
- [ ] Link each recommendation to the KPI, alert, or records supporting it.

Current gap: no recommendations are returned.

Acceptance criteria: recommendations are specific, traceable, and never based on invented scores.

## 12. Add evidence links

- [x] Preserve record IDs already included in validation findings.
- [ ] Return evidence links when the source dataset provides them.
- [ ] Ensure KPI results, alerts, trends, and recommendations reference their supporting evidence.
- [ ] Do not fabricate links when only record IDs exist.

Current state: findings contain supporting record IDs, but no evidence links or URLs are returned.

Acceptance criteria: every displayed result can be traced to record IDs and, where available, source evidence links.

## 13. Expose validation and agent workflow

- [x] Keep the validation summary and detailed findings.
- [ ] Expose the important workflow stages: import, synopsis, mapping, mapping validation/repair, canonical validation, KPI calculation, and response assembly.
- [ ] Report mapping confidence separately from employee data confidence.
- [ ] Record whether a mapping repair request occurred.
- [ ] Record calculator execution and exclusion counts without exposing raw source rows or private model reasoning.
- [ ] Make the workflow suitable for display in the dashboard or an audit panel.

Current state: the response includes selected tables, model name, token count, model request count, cache status, a validation summary, and detailed findings. It does not provide a complete workflow trace or validation log.

Acceptance criteria: users can see which deterministic and agent-assisted stages ran, their outcomes, and the evidence exclusions applied.

## Recommended implementation order

1. Fix evidence-confidence rules.
2. Return confidence and enforce the 70% guardrail.
3. Add overall scores and performance tiers.
4. Verify all calculations against `Expected_KPI` and applicable QA cases.
5. Add a consistent structured summary.
6. Design trend, alert, recommendation, and evidence-link response models.
7. Add validation/workflow audit output.
8. Build the dashboard and employee/team filters on the stabilized API contract.

## Final completion check

- [x] All 30 employees are returned.
- [x] EMP-027 through EMP-030 are marked `Insufficient data` when confidence is 60%.
- [x] No low-confidence employee has an overall score or tier.
- [x] All required missing evidence lowers confidence consistently.
- [x] Eligible employees have verified overall scores and tiers.
- [x] The final narrative agrees with the structured results.
- [x] The dashboard supports employee/team filters and 12-week trends.
- [ ] Alerts, recommendations, evidence, validation, and workflow information are visible and traceable.

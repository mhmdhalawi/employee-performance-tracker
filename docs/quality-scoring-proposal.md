# Proposed adaptive Quality scoring plan

## Status

This document is a design proposal, not the current scoring contract. The current implementation
calculates Quality from accuracy, first-pass approval, and rework using the Cedar benchmark
formula. Adopting adaptive Quality profiles would change mapping, validation, confidence, API
responses, comparisons, and tests. The current benchmark path remains authoritative until an
explicit product decision approves a versioned migration.

## Problem

Customer quality data will vary. Some clients may provide a review score only. Others may provide
inspection totals and defect counts, first-pass results, rework hours, total effort, acceptance
results, or quality evidence distributed across several tables.

Requiring one exact source schema rejects useful evidence. Allowing the planning model to invent
a formula per dataset would make employee scores inconsistent and difficult to audit.

The proposed boundary is:

> The planning agent identifies which headers represent approved Quality concepts and proposes
> bindings. Python validates the bindings, derives supported components, selects a predefined
> profile, and performs all arithmetic.

## Goals

- Accept unfamiliar table and column names through semantic binding.
- Use relevant, validated Quality evidence from one or more tables.
- Support a limited Quality result when only a small number of useful fields exists.
- Prefer richer profiles when accuracy, first-pass, and rework evidence is available.
- Keep formulas, weights, caps, missing-value behavior, and thresholds deterministic.
- Expose which profile and evidence produced every score.
- Keep missing evidence separate from poor quality performance.

## Non-goals

- Letting the model generate or execute calculation code.
- Letting the model invent formulas, weights, thresholds, or interpretations per request.
- Treating arbitrary ratings, free text, or numeric columns as Quality evidence.
- Inferring defects, approval, or rework from descriptions or sentiment.
- Comparing different Quality profiles as though they measured identical evidence.
- Replacing the Cedar benchmark formula without an approved migration.

## Stable semantic roles

The source labels remain client-defined. The planning agent maps them to a bounded vocabulary of
normalized Quality roles.

| Semantic role | Purpose | Typical source labels |
| --- | --- | --- |
| `employee_id` | Joins quality evidence to an employee | `Employee_ID`, `Reviewer_Owner`, `Worker_No` |
| `quality_review_id` | Identifies and deduplicates a review | `Review_ID`, `Inspection_ID`, `Audit_Ref` |
| `work_output_id` | Links the review to a project or output | `Project_ID`, `Task_ID`, `Deliverable_Ref` |
| `occurred_on` | Places evidence in a reporting period | `Review_Date`, `Inspected_On`, `Audit_Date` |
| `accuracy_ratio` | Provides a normalized accuracy result | `Accuracy`, `Accuracy_Pct`, `Correctness_Rate` |
| `inspected_item_count` | Supplies the denominator for derived accuracy | `Items_Checked`, `Sample_Size` |
| `defect_count` | Supplies failures for derived accuracy | `Defects`, `Error_Count`, `Failed_Items` |
| `first_pass_approved` | Indicates acceptance without correction | `First_Pass`, `Approved_First_Time` |
| `rework_hours` | Measures correction effort | `Rework_Hours`, `Correction_Time` |
| `total_effort_hours` | Provides a baseline for proportional rework | `Total_Hours`, `Delivery_Effort` |
| `acceptance_status` | Records an approved or rejected outcome | `Acceptance`, `QA_Status`, `Review_Result` |
| `verification_status` | Determines whether evidence is eligible | `Verified`, `Record_Status` |

These roles form an approved vocabulary, not a requirement that every client provide all 12.
Only roles consumed by an approved component may affect the score. For example,
`acceptance_status` should remain supporting evidence until its eligibility rules and formula are
approved.

## Planning-agent output

The agent should return table classification and source-to-semantic bindings. Python, not the
agent, determines whether a component or profile is runnable.

Example with unfamiliar names:

```json
{
  "table": "Inspection_Log",
  "family": "quality",
  "confidence": 0.95,
  "bindings": {
    "employee_id": "Work_Owner",
    "quality_review_id": "Audit_Number",
    "work_output_id": "Delivery_Ref",
    "occurred_on": "Checked_At",
    "inspected_item_count": "Units_Reviewed",
    "defect_count": "Issues_Found",
    "first_pass_approved": "Accepted_First_Time",
    "rework_hours": "Fix_Hours",
    "verification_status": "Audit_State"
  }
}
```

The agent may bind roles across multiple tables when it can propose stable join keys. Python must
reject nonexistent columns, incompatible types, ambiguous bindings, invalid joins, and unsupported
roles.

## Deterministic measurement components

Python owns a registry of approved components. Each component declares its required roles,
eligibility rules, exact formula, output scale, and missing-value behavior.

### Direct accuracy

Required roles: `employee_id`, `quality_review_id`, and `accuracy_ratio`.

```text
Accuracy score = average validated accuracy ratio × 100
```

Input ratios must be normalized deterministically. A source using `95` for 95% and another using
`0.95` require validated scale metadata; Python must not guess the scale from individual values.

### Derived inspection accuracy

Required roles: `employee_id`, `quality_review_id`, `inspected_item_count`, and `defect_count`.

```text
Inspection accuracy =
  (inspected items - defective items) / inspected items × 100
```

Counts must be non-negative, inspected count must be greater than zero, and defect count must not
exceed inspected count. Direct and derived accuracy are alternative representations; they must
not both be counted as separate components for the same review.

### First-pass rate

Required roles: `employee_id`, `quality_review_id`, and `first_pass_approved`.

```text
First-pass rate = first-pass-approved reviews / eligible reviews × 100
```

Only validated boolean or explicitly normalized categorical values are eligible.

### Absolute rework score

Required roles: `employee_id`, `quality_review_id`, and `rework_hours`.

This preserves the current Cedar benchmark behavior:

```text
Rework score = max(0, 100 - average rework hours × 8)
```

The factor `8` is a versioned benchmark rule. It must not be inferred or changed by the model.

### Proportional rework score

Required roles: `employee_id`, `quality_review_id`, `rework_hours`, and `total_effort_hours`.

```text
Rework ratio = total rework hours / total effort hours
Proportional rework score = max(0, 100 - rework ratio × 100)
```

This may be more meaningful across differently sized outputs, but it is a proposed alternative
and is not interchangeable with the Cedar absolute-rework component.

## Predefined scoring profiles

Profiles are versioned Python contracts. The planning model supplies bindings but cannot choose
weights or construct new profiles.

| Profile | Required components | Proposed formula | Intended use |
| --- | --- | --- | --- |
| `cedar_quality_v1` | Accuracy, first-pass rate, absolute rework | Accuracy 60% + first pass 25% + rework 15% | Current benchmark-compatible path |
| `accuracy_first_pass_v1` | Accuracy, first-pass rate | Accuracy 70% + first pass 30% | No usable rework evidence |
| `accuracy_only_v1` | Accuracy | Accuracy 100% | Limited but validated review evidence |
| `proportional_quality_v1` | Accuracy, first-pass rate, proportional rework | Accuracy 60% + first pass 25% + proportional rework 15% | Reviews with effort baselines |

In this table, “Accuracy” may come from direct accuracy or derived inspection accuracy, but never
both for the same evidence record.

Profile selection must be deterministic and policy-driven. A proposed default is:

```text
if the deployment or dataset is pinned to the Cedar benchmark contract
and accuracy, first-pass, and absolute rework are available:
    use cedar_quality_v1
else if proportional rework, accuracy, and first-pass are available:
    use proportional_quality_v1
else if accuracy, first-pass, and absolute rework are available:
    use cedar_quality_v1
else if accuracy and first-pass are available:
    use accuracy_first_pass_v1
else if accuracy is available:
    use accuracy_only_v1
else:
    return insufficient Quality evidence
```

Profile choice should be consistent for a comparison population. It should not vary employee by
employee merely because individual records contain missing values. Missing required evidence
should reduce coverage and may withhold a score rather than silently switching one employee to a
more favorable profile.

## Validation and multi-table assembly

Before enabling a component, Python should:

1. Confirm every referenced table and source column exists.
2. Confirm each value can be parsed into the bound role's approved type and scale.
3. Require stable review IDs and exclude duplicate records deterministically.
4. Validate employee IDs and any work-output relationship.
5. Reject quality reviews linked to unknown work outputs where the profile requires that link.
6. Validate cross-table join cardinality and reject joins that multiply review rows.
7. Enforce numeric ranges and denominator rules.
8. Include only records allowed by the fixed verification policy.
9. Prevent direct and derived versions of the same concept from being double-counted.
10. Derive component availability and select the approved profile in Python.

Agent confidence describes confidence in semantic interpretation. It cannot repair invalid values,
override validation, or make an incomplete profile runnable.

## Example profile selection

### Client with three useful Quality bindings

```json
{
  "employee_id": "Owner_ID",
  "quality_review_id": "Check_ID",
  "accuracy_ratio": "Correctness"
}
```

Python can calculate `accuracy_only_v1`, subject to valid scale and evidence coverage.

### Client with defect and first-pass evidence

```json
{
  "employee_id": "Owner_ID",
  "quality_review_id": "Check_ID",
  "inspected_item_count": "Items_Checked",
  "defect_count": "Errors",
  "first_pass_approved": "Passed_First_Time"
}
```

Python derives inspection accuracy and can calculate `accuracy_first_pass_v1`.

### Client with the full benchmark evidence

```json
{
  "employee_id": "Employee_ID",
  "quality_review_id": "Review_ID",
  "work_output_id": "Project_ID",
  "occurred_on": "Review_Date",
  "accuracy_ratio": "Accuracy_Ratio",
  "first_pass_approved": "First_Pass_Approved",
  "rework_hours": "Rework_Hours",
  "verification_status": "Verification_Status"
}
```

Python can calculate `cedar_quality_v1`.

## Result contract

The response should expose the exact profile and evidence used:

```json
{
  "quality_score": 91.4,
  "scoring_profile": "accuracy_first_pass_v1",
  "profile_version": 1,
  "components": {
    "accuracy": 92.0,
    "first_pass_rate": 90.0
  },
  "accuracy_source": "derived_inspection_accuracy",
  "used_roles": [
    "employee_id",
    "quality_review_id",
    "inspected_item_count",
    "defect_count",
    "first_pass_approved"
  ],
  "unavailable_components": {
    "absolute_rework": ["rework_hours"],
    "proportional_rework": ["rework_hours", "total_effort_hours"]
  },
  "limitations": [
    "The source did not provide usable rework evidence."
  ]
}
```

The existing `quality_reason` may summarize these deterministic fields, but structured output is
preferable for audit, reporting, and UI behavior.

## Confidence and comparability

Quality evidence confidence should measure coverage of the selected profile's required evidence,
not the numerical Quality result. Missing reviews or missing component values lower confidence;
they do not automatically create a zero score.

Scores using different profiles are not automatically comparable. The dashboard should:

- show the profile and version used;
- rank employees only when they share the same profile and version;
- use a common profile for team aggregation;
- disclose unavailable components and excluded records; and
- avoid implying that an accuracy-only score includes first-pass or rework behavior.

The conservative default is to keep limited-profile Quality components visible while withholding
mixed-profile rankings and team averages.

## API and persistence implications

- Extend calculation plans with the approved Quality semantic roles and validated join paths.
- Persist scale interpretation for ratios and percentages as part of the validated plan.
- Persist normalized categorical mappings used for boolean and verification fields.
- Store the selected Quality profile and version in immutable plan snapshots.
- Return component scores, accuracy representation, unavailable components, and limitations.
- Ensure dashboards, trends, insights, report previews, and PDF generators use the same
  backend-provided profile and values.
- Include profile and normalization metadata in mapping-cache compatibility rules.
- Define whether later evidence can change the selected profile for historical periods.

## Migration plan

1. **Specify the vocabulary.** Approve semantic roles, types, scales, status mappings, eligibility,
   and join rules.
2. **Version the current formula.** Name the existing calculation `cedar_quality_v1` and preserve
   all benchmark results and QA expectations.
3. **Extend planning output.** Allow the agent to bind additional approved Quality roles without
   defining formulas or declaring calculations runnable.
4. **Add structural validation.** Validate columns, types, scales, categorical mappings, record
   identities, and cross-table joins.
5. **Extract deterministic components.** Implement direct accuracy, derived inspection accuracy,
   first-pass rate, absolute rework, and proportional rework as independently tested functions.
6. **Add profile selection.** Select a complete, approved profile consistently for the requested
   comparison scope.
7. **Update confidence.** Calculate profile-specific evidence coverage and preserve the overall
   confidence gate.
8. **Update contracts and consumers.** Expose profile metadata and prevent invalid comparisons in
   dashboards, trends, insights, and reports.
9. **Add regression tests.** Cover unfamiliar headers, direct and derived accuracy, scale
   ambiguity, missing evidence, duplicates, orphan work outputs, unsafe joins, invalid counts,
   mixed profiles, and benchmark parity.

## Required decisions before implementation

- Whether limited Quality profiles may contribute to the overall performance score.
- Whether profile selection is fixed per client, submission schema, reporting period, or team.
- Whether employees with different profiles may appear in one ranking or aggregate.
- Whether derived defect accuracy is considered equivalent to a supplied accuracy ratio.
- How percentage-versus-ratio scale metadata is supplied and approved.
- Whether proportional rework should supersede absolute rework outside the Cedar benchmark.
- Whether quality evidence must always link to a known work output.
- Which verification and acceptance values make a review eligible.
- How later, richer submissions affect historical profile selection and comparisons.

Until these decisions are approved, the current Cedar Quality formula remains authoritative:

```text
Quality = accuracy × 60% + first-pass approval × 25% + rework score × 15%
Rework score = max(0, 100 - average rework hours × 8)
```

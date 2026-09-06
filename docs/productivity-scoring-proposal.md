# Proposed adaptive Productivity scoring plan

## Status

This document is a design proposal, not the current scoring contract. The current implementation
requires employee performance targets and calculates Productivity from target achievement and
time efficiency. Adopting this proposal would change KPI formulas, validation, confidence,
benchmark expectations, API output, and tests. It must not replace the existing benchmark path
without explicit product approval and a versioned migration.

## Problem

Customer datasets will not always contain the same tables or headers. One dataset may contain
only an employee identifier, work-output identifier, and completion status. Another may also
contain due dates, completion dates, actual effort, expected effort, output targets, or useful
evidence split across several tables.

A fixed mapping that recognizes only a small set of source columns discards useful evidence. A
formula invented by the planning model would create the opposite problem: inconsistent,
non-comparable, and difficult-to-audit employee scores.

The proposed boundary is:

> The planning agent identifies the meaning of available columns and proposes bindings. Python
> validates those bindings, selects a predefined scoring profile, and performs all arithmetic.

## Goals

- Accept unfamiliar table and column names without relying on literal header matches.
- Use all relevant, validated Productivity evidence, including evidence distributed across
  tables.
- Produce a useful result when target data is absent.
- Prefer richer evidence when target, deadline, and effort data is available.
- Keep formulas deterministic, versioned, explainable, and testable.
- Make scores calculated from different evidence profiles visibly distinguishable.
- Preserve missing evidence as uncertainty rather than silently converting it to poor
  performance.

## Non-goals

- Letting the model write or execute Python.
- Letting the model invent formulas, weights, thresholds, or status meanings per request.
- Treating every numeric column as Productivity evidence.
- Comparing scores from materially different scoring profiles as if they were equivalent.
- Replacing the existing Cedar benchmark formula without a deliberate migration decision.

## Stable semantic roles

Source headers remain customer-defined. The planning agent maps them to stable normalized roles.

| Semantic role | Purpose | Typical source labels |
| --- | --- | --- |
| `employee_id` | Joins evidence to an employee | `Employee_ID`, `Worker_No`, `Owner` |
| `work_output_id` | Identifies and deduplicates a work item | `Project_ID`, `Task_Ref`, `Job_Code` |
| `completion_status` | Identifies completed and incomplete work | `Status`, `Task_State`, `Outcome` |
| `assigned_date` | Establishes assignment and period eligibility | `Assigned_Date`, `Opened_On` |
| `due_date` | Enables deadline evaluation | `Due_Date`, `Deadline` |
| `completed_date` | Establishes completion and timeliness | `Completed_Date`, `Closed_On` |
| `actual_effort_hours` | Measures actual effort | `Actual_Hours`, `Hours_Spent` |
| `expected_effort_hours` | Provides an effort baseline | `Budgeted_Hours`, `Planned_Effort` |
| `output_target` | Provides an expected output count | `Target_Outputs`, `Quarterly_Goal` |
| `complexity_weight` | Optionally weights unlike work items | `Story_Points`, `Complexity` |
| `verification_status` | Identifies evidence eligible for scoring | `Verified`, `Record_Status` |

The initial implementation should support only roles consumed by approved profiles. Additional
roles should not affect scores until their meaning, validation rules, and formula are approved.

## Planning-agent output

The agent should classify tables and return source-to-semantic bindings with confidence. It
should not claim that a calculation is runnable; Python derives that from validated bindings.

Example for unfamiliar names:

```json
{
  "table": "Delivery_Log_2026",
  "family": "productivity",
  "confidence": 0.94,
  "bindings": {
    "employee_id": "Worker_Number",
    "work_output_id": "Task_Reference",
    "completion_status": "Task_State",
    "due_date": "Deadline",
    "completed_date": "Closed_At",
    "actual_effort_hours": "Hours_Used"
  }
}
```

Bindings may refer to multiple tables. Cross-table evidence must include a validated join path,
normally `employee_id` and, where required, `work_output_id`. The agent may propose semantic
matches, but Python must reject missing columns, incompatible types, ambiguous duplicate
bindings, unsafe joins, and unsupported roles.

## Deterministic measurement components

Python owns a registry of approved measurement components. Each component declares required
roles, fixed eligibility rules, missing-value behavior, and exact arithmetic.

### Completion rate

Required roles: `employee_id`, `work_output_id`, and `completion_status`.

```text
Completion rate = completed eligible outputs / all eligible outputs × 100
```

Cancelled work and work not yet eligible for evaluation must be handled by a fixed policy rather
than model interpretation. Stable record identities are required for duplicate exclusion.

### On-time completion rate

Required roles: `employee_id`, `work_output_id`, `due_date`, and `completed_date`.

```text
On-time rate = outputs completed by due date / completed outputs with valid due dates × 100
```

Missing or invalid dates lower evidence coverage and do not become late results automatically.

### Effort efficiency

Required roles: `employee_id`, `actual_effort_hours`, and `expected_effort_hours`. A
`work_output_id` is also required when the values are stored at work-output granularity.

```text
Effort efficiency = expected effort / actual effort × 100
```

The result is capped at 100. Actual effort without expected effort remains descriptive evidence
and does not establish efficiency.

### Target achievement

Required roles: `employee_id`, `completion_status`, and `output_target`, plus a stable work-output
identity for deduplication.

```text
Target achievement = completed outputs / period-adjusted output target × 100
```

The result is capped at 100. Target period and prorating rules must be explicit metadata rather
than inferred from a header.

## Predefined scoring profiles

Python selects the richest valid approved profile. Profiles are versioned calculation contracts,
not model-generated formulas.

| Priority | Profile | Required components | Proposed formula |
| ---: | --- | --- | --- |
| 1 | `target_effort_v1` | Target achievement, effort efficiency | Target achievement 60% + effort efficiency 40% |
| 2 | `completion_timeliness_v1` | Completion rate, on-time rate | Completion rate 60% + on-time rate 40% |
| 3 | `completion_only_v1` | Completion rate | Completion rate 100% |

The first profile matches the shape of the current Productivity calculation and should remain
the Cedar benchmark profile. The target-free profiles provide explicitly different alternatives
when targets are unavailable.

Selection is deterministic:

```text
if target achievement and effort efficiency are available:
    use target_effort_v1
else if completion rate and on-time rate are available:
    use completion_timeliness_v1
else if completion rate is available:
    use completion_only_v1
else:
    return insufficient Productivity evidence
```

An unavailable component must never be silently assigned a zero. Within a selected profile,
the initial proposal does not renormalize around missing required components; Python falls back
to the next complete profile instead. This makes profile selection predictable and visible.

## Validation and multi-table assembly

Python should perform these checks before selecting a profile:

1. Confirm every referenced table exists in the request-scoped catalog or canonical state.
2. Confirm every bound source column exists in that table.
3. Confirm inferred and parsed values are compatible with the semantic role.
4. Reject duplicate semantic bindings when they create ambiguity.
5. Validate employee and work-output identities and exclude duplicates deterministically.
6. Validate cross-table join cardinality; reject joins that multiply work-output records.
7. Normalize approved completion-status values using a validated, versioned status mapping.
8. Determine available measurement components from their required roles.
9. Select the highest-priority complete profile in Python.

The agent's confidence describes semantic certainty. It does not override structural validation
or make an incomplete profile runnable.

## Result contract

Every result should expose how it was produced:

```json
{
  "productivity_score": 84.5,
  "scoring_profile": "completion_timeliness_v1",
  "profile_version": 1,
  "components": {
    "completion_rate": 82.0,
    "on_time_rate": 88.25
  },
  "used_roles": [
    "employee_id",
    "work_output_id",
    "completion_status",
    "due_date",
    "completed_date"
  ],
  "unavailable_components": {
    "effort_efficiency": ["expected_effort_hours"],
    "target_achievement": ["output_target"]
  },
  "limitations": [
    "The source did not provide an output target or expected effort baseline."
  ]
}
```

The existing `productivity_reason` can summarize the same deterministic information, but the
structured fields are preferable for auditing and UI presentation.

## Confidence and comparability

Productivity evidence confidence should be calculated separately from the Productivity score.
It should describe coverage of the fields required by the selected profile and must remain part
of the overall evidence-confidence gate.

Scores from different profiles are not automatically comparable. The dashboard should:

- display the profile used for each score;
- compare or rank employees only when the same profile and version were used;
- use one common profile when producing a team aggregate;
- report excluded employees or unavailable common profiles clearly; and
- never imply that a completion-only score includes target or efficiency evidence.

A product decision is required on whether mixed-profile employees should receive an overall KPI
score at all. The conservative default is to keep the component Productivity result visible but
withhold cross-employee ranking and mixed-profile team averages.

## Status vocabulary

Status normalization is a prerequisite for completion calculations. Python should use an
approved mapping such as:

```text
completed: completed, completed on time, completed late, done, closed
incomplete: assigned, in progress, blocked, overdue
neutral/excluded: cancelled, duplicate
unknown: any unapproved value
```

The planning agent may propose which source values correspond to these categories only during a
bounded repair step with safe low-cardinality examples. Python must validate and persist the
approved mapping. Unknown values should lower coverage or block the affected calculation rather
than being guessed as completed or incomplete.

## API and persistence implications

- Extend the calculation plan with semantic Productivity bindings and optional validated join
  paths across tables.
- Store the selected profile name and version with immutable submission plan snapshots.
- Preserve canonical source records required by every approved component.
- Return component scores, selected profile, unavailable components, and limitations.
- Ensure `/dashboard`, report previews, trends, and browser-generated reports reuse the same
  selected profile and backend-provided values.
- Include profile identity in mapping-cache compatibility decisions where relevant.
- Do not allow a later partial submission to silently change historical score meaning without a
  documented recalculation policy.

## Migration plan

1. **Specify contracts.** Finalize semantic roles, eligibility rules, status normalization,
   profile formulas, confidence coverage, and mixed-profile comparison policy.
2. **Preserve the benchmark.** Name and version the existing target-based formula as
   `target_effort_v1`; verify that its results remain within the benchmark tolerance.
3. **Extend planning output.** Allow the agent to bind the additional approved semantic roles
   without allowing it to define formulas or mark calculations runnable.
4. **Add Python validation.** Validate bindings, types, join paths, status mappings, and component
   requirements.
5. **Add component calculators.** Implement completion rate and on-time rate as small deterministic
   functions while retaining the current target and effort behavior.
6. **Add profile selection.** Select the richest complete profile deterministically and return its
   name and version.
7. **Relax foundation requirements carefully.** Permit target-free ingestion only when a complete
   target-free profile is available. Keep employee identity as a required foundation.
8. **Update confidence and responses.** Expose profile-specific evidence coverage, component
   results, limitations, and insufficient-data behavior.
9. **Update consumers.** Show profile labels and prevent invalid mixed-profile comparisons in the
   dashboard, trends, insights, and reports.
10. **Run acceptance testing.** Preserve all existing benchmark tests and add target-free,
    multi-table, missing-field, invalid-binding, duplicate, unsafe-join, and mixed-profile tests.

## Required decisions before implementation

- Whether target-free scores may contribute to the overall performance score.
- Whether employees with different profiles may appear in the same ranking or team aggregate.
- Which work outputs are eligible in a period, especially assigned-before-period and not-yet-due
  work.
- The authoritative completion, cancellation, and neutral status vocabulary.
- Whether on-time rate should divide by all eligible outputs or only completed outputs.
- Whether complexity weighting is needed and, if so, which source values are authoritative.
- Whether profile selection may change when later submissions add richer evidence, and how that
  affects historical comparisons.

Until these decisions are approved, the current target-required Productivity calculation and
Cedar benchmark remain authoritative.

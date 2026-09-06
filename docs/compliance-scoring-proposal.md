# Proposed adaptive Compliance scoring plan

## Status

This document is a design proposal, not the current scoring contract. The current Cedar
implementation combines attendance, reporting, and leave compliance at 50%, 35%, and 15%.
Adopting an extensible Compliance model would change semantic mapping, validation, confidence,
scoring, API output, comparisons, persistence, and tests. The current benchmark path remains
authoritative until a versioned migration is explicitly approved.

## Problem

Compliance is not universally defined by attendance, reporting, and leave. A client may provide
only attendance logs, one or two of the Cedar evidence families, all three, or different evidence
such as mandatory training, certifications, policy acknowledgements, timesheets, safety checks,
required approvals, or audit remediation.

The system must distinguish these cases:

- an obligation is applicable and compliant;
- an obligation is applicable and non-compliant;
- an obligation is applicable but its evidence is missing;
- an evidence family is not applicable to the client's compliance policy;
- a table appears compliance-related but no approved calculator supports it; and
- no recognizable Compliance evidence exists.

Missing evidence must never become zero compliance automatically. Equally, an absent table must
not be treated as “not applicable” merely because the client omitted required evidence.

The proposed boundary is:

> The planning agent identifies compliance-related tables and binds source headers to approved
> semantic roles. Python validates the bindings, matches them to approved compliance components,
> applies a versioned client or benchmark policy, and performs all arithmetic.

## Goals

- Support one, several, or many approved Compliance components.
- Accept unfamiliar table and column names through semantic binding.
- Allow useful evidence to come from one or multiple tables.
- Extend Compliance beyond the original attendance, reporting, and leave families.
- Keep formulas, eligibility, weights, neutral states, and thresholds deterministic.
- Separate policy applicability from evidence availability.
- Return insufficient evidence when no supported component can be evaluated.
- Show exactly which obligations and source evidence produced the result.
- Preserve the current Cedar calculation as a benchmark-compatible policy.

## Non-goals

- Letting the model invent formulas, weights, obligations, or penalties per request.
- Letting the model generate or execute calculation code.
- Treating any compliance-sounding header as sufficient evidence.
- Treating missing evidence as proof of non-compliance.
- Treating omitted evidence as automatically not applicable.
- Applying legal or regulatory meaning without an approved client policy.
- Comparing scores calculated from materially different policies as if they were equivalent.

## Core model: components plus policy

Compliance should use an extensible registry of independently approved components rather than a
fixed requirement that every dataset contain three specific tables.

```text
Compliance component registry
├── attendance
│   ├── arrival
│   ├── shift end
│   └── lunch return
├── reporting timeliness
├── leave documentation
├── training completion
├── certification validity
├── policy acknowledgement
├── timesheet submission
├── safety checks
└── future approved components
```

A separate versioned Compliance policy defines which registered components apply to a client or
benchmark and how they are weighted. The source dataset supplies evidence; it does not define the
policy by omission.

Example policies:

```json
{
  "policy_id": "cedar_compliance_v1",
  "components": {
    "attendance": 0.50,
    "reporting_timeliness": 0.35,
    "leave_documentation": 0.15
  }
}
```

```json
{
  "policy_id": "attendance_only_v1",
  "components": {
    "attendance": 1.0
  }
}
```

```json
{
  "policy_id": "operations_compliance_v1",
  "components": {
    "attendance": 0.30,
    "training_completion": 0.25,
    "certification_validity": 0.25,
    "safety_checks": 0.20
  }
}
```

Weights are approved configuration owned by Python and persisted policy metadata. The planning
agent must not choose or modify them.

## Semantic-role vocabulary

Roles should be grouped by component instead of treated as one permanent maximum. Clients provide
only the roles present in their data; the vocabulary can grow when a new deterministic component
is approved.

### Shared roles

| Semantic role | Purpose | Typical source labels |
| --- | --- | --- |
| `employee_id` | Joins evidence to an employee | `Employee_ID`, `Worker_No`, `Staff_Ref` |
| `compliance_record_id` | Identifies and deduplicates evidence | `Record_ID`, `Log_ID`, `Event_Ref` |
| `occurred_on` | Places evidence in a reporting period | `Date`, `Event_Date`, `Recorded_On` |
| `verification_status` | Determines evidence eligibility | `Verified`, `Record_Status` |
| `evidence_link` | Supports traceability | `Evidence_URL`, `Source_Link` |

### Attendance roles

| Semantic role | Purpose |
| --- | --- |
| `scheduled_start` | Expected arrival time |
| `actual_start` | Recorded arrival time |
| `scheduled_end` | Expected shift-end time |
| `actual_end` | Recorded shift-end time |
| `lunch_out` | Lunch check-out time |
| `lunch_in` | Lunch return time |
| `attendance_outcome` | Identifies working, leave, or holiday records |

### Reporting roles

| Semantic role | Purpose |
| --- | --- |
| `submission_due_date` | Required submission deadline |
| `submission_date` | Actual submission date |
| `submission_required` | Identifies applicable submissions |
| `submission_complete` | Indicates required content was complete |

### Leave roles

| Semantic role | Purpose |
| --- | --- |
| `leave_category` | Distinguishes annual, sick, and other leave |
| `leave_start_date` | Beginning of leave period |
| `leave_end_date` | End of leave period |
| `leave_approval_status` | Records approval or rejection |
| `documentation_complete` | Indicates required documentation exists |

### Extensible obligation roles

| Semantic role | Example component |
| --- | --- |
| `requirement_id` | Training, certification, policy, or safety requirement |
| `requirement_applicable` | Whether an obligation applies to the employee |
| `requirement_due_date` | Training, acknowledgement, or remediation deadline |
| `requirement_completed_date` | Completion or acknowledgement date |
| `requirement_status` | Completed, pending, failed, expired, or waived |
| `expiration_date` | Certification validity |
| `waiver_status` | Approved exception or neutral state |

Generic requirement roles may be used only with an approved component whose categorical meanings
and formula are defined. They are not a license for the agent to invent a new compliance rule.

## Planning-agent output

The planning agent should classify evidence, identify a registered component when possible, and
return bindings with semantic confidence.

Example for an attendance-only source with unfamiliar headers:

```json
{
  "table": "Clocking_History",
  "family": "compliance",
  "component": "attendance",
  "confidence": 0.96,
  "bindings": {
    "employee_id": "Badge_Number",
    "compliance_record_id": "Clock_Record",
    "occurred_on": "Work_Day",
    "scheduled_start": "Rostered_In",
    "actual_start": "Clocked_In",
    "scheduled_end": "Rostered_Out",
    "actual_end": "Clocked_Out",
    "attendance_outcome": "Day_Type"
  }
}
```

Example for an unfamiliar compliance-related table that has no approved component:

```json
{
  "table": "Equipment_Attestations",
  "family": "compliance",
  "component": null,
  "confidence": 0.82,
  "classification_status": "recognized_but_unsupported",
  "reason": "The table appears to contain equipment-policy attestations, but no approved component consumes these roles."
}
```

Python, not the model, decides whether bindings are valid and a component is runnable.

## Initially approved deterministic components

### Attendance

Attendance can be calculated from one, two, or all three approved checks.

```text
Arrival check = actual_start <= scheduled_start
Shift-end check = actual_end >= scheduled_end
Lunch check = lunch_in > lunch_out

Attendance score = equal average of available approved checks
```

Each check requires its complete field pair. An actual time without its scheduled comparison does
not establish compliance. Missing values lower evidence coverage rather than becoming failed
checks. Approved leave and holidays are neutral and excluded under the fixed Cedar rules.

The policy may require particular attendance checks. A dataset containing arrival fields only can
support an arrival-based attendance profile, but it must be labelled accordingly and must not
claim to have evaluated shift end or lunch behavior.

### Reporting timeliness

```text
Reporting score = verified submissions on or before due date
                  / eligible verified submissions × 100
```

Required roles are `employee_id`, a stable record identity, `submission_due_date`, and
`submission_date`. A missing submission date lowers evidence coverage; it does not automatically
become late under the current contract.

### Leave documentation

The current Cedar behavior evaluates sick-leave documentation:

```text
Leave score = approved and documented sick-leave requests
              / eligible sick-leave requests × 100
```

When there are no sick-leave requests, the current calculator returns 100. Approved annual leave
and holidays are neutral. These are policy rules, not meanings the model may infer.

### Training completion

A proposed future component could use:

```text
Training score = applicable requirements completed by due date
                 / applicable requirements × 100
```

Required roles would include employee identity, requirement identity, applicability, due date,
completion date, and any approved waiver status. This component must not become active until its
eligibility and neutral-state rules are approved and tested.

### Certification validity

A proposed future component could use:

```text
Certification score = applicable certifications valid on evaluation date
                      / applicable certifications × 100
```

An approved waiver may be neutral. Expiration, renewal, and grace-period policies must be explicit
and versioned.

### Policy acknowledgement or timesheet submission

These can use the generic obligation pattern only after separate component approval:

```text
Component score = applicable obligations satisfied by due date
                  / applicable obligations × 100
```

The shared mathematical shape does not make their business meanings interchangeable. Each
component still needs its own eligibility, status, waiver, and evidence rules.

## Combining available components

There are two different situations that must not be confused.

### Policy-scoped calculation

When the client has an approved Compliance policy, Python evaluates the components declared by
that policy.

```text
Compliance = sum(component score × configured weight)
```

If the policy declares three components but the upload contains only one, the other two are
missing required evidence, not automatically inapplicable. Python should lower confidence and,
when coverage is below the configured threshold, withhold the Compliance or overall result.

### Evidence-only exploratory calculation

When no approved client policy exists, Python may calculate supported components individually:

```json
{
  "compliance_score": null,
  "policy_status": "not_configured",
  "available_components": {
    "attendance": 92.5
  },
  "result_status": "Compliance policy required"
}
```

This is safer than averaging whatever tables happened to be uploaded. A later upload should not
silently change the meaning of the official Compliance score by adding another evidence family.

If the product explicitly approves an available-components profile, it may calculate a labelled
score by normalizing configured registry weights across supported components. Such a score must be
marked `adaptive_available_components_v1`, must expose its component set, and must not be compared
with another score that used a different set.

## Cedar benchmark policy

The existing calculation should be named and preserved as `cedar_compliance_v1`:

```text
Attendance = equal average of available mapped arrival, shift-end, and lunch checks
Reporting = on-time verified submissions / eligible verified submissions × 100
Leave = approved and documented sick-leave requests / sick-leave requests × 100

Compliance = Attendance × 50% + Reporting × 35% + Leave × 15%
```

The current implementation normalizes the remaining top-level weights when attendance or
reporting is unavailable, while leave always returns a value. Any migration must preserve this
behavior for benchmark compatibility or deliberately version a replacement. Duplicate attendance
exclusion and approved-leave neutrality remain mandatory.

## Validation and multi-table assembly

Before calculating any component, Python should:

1. Confirm every referenced table and source column exists.
2. Validate each bound value against the semantic role's type and range.
3. Require stable record identities and exclude duplicates deterministically.
4. Validate employee identities and report orphan evidence.
5. Validate cross-table join keys and reject joins that multiply evidence rows.
6. Validate timestamp pairs and chronological order.
7. Normalize categorical values only through an approved, persisted mapping.
8. Apply neutral states, waivers, holidays, and approved leave through policy rules.
9. Determine component support from complete required-role sets.
10. Distinguish missing applicable evidence from policy-defined non-applicability.
11. Apply only the active policy's approved components and weights.
12. Preserve record IDs and evidence links for findings and audit output.

The agent's semantic confidence cannot override these checks or turn unsupported evidence into a
score.

## Example outcomes

### Attendance is the client's entire approved policy

```json
{
  "compliance_score": 92.5,
  "policy_id": "attendance_only_v1",
  "policy_version": 1,
  "components": {
    "attendance": {
      "score": 92.5,
      "checks": {
        "arrival": 95.0,
        "shift_end": 90.0,
        "lunch": null
      }
    }
  },
  "limitations": [
    "The approved policy evaluates attendance only.",
    "Lunch compliance was not evaluated because no complete lunch timestamp pair was bound."
  ]
}
```

### Attendance is present but other required policy evidence is missing

```json
{
  "compliance_score": null,
  "policy_id": "cedar_compliance_v1",
  "available_components": {
    "attendance": 92.5
  },
  "missing_applicable_components": [
    "reporting_timeliness",
    "leave_documentation"
  ],
  "result_status": "Insufficient compliance evidence"
}
```

### Multiple non-Cedar components are available

```json
{
  "compliance_score": 94.0,
  "policy_id": "operations_compliance_v1",
  "policy_version": 1,
  "components": {
    "attendance": 90.0,
    "training_completion": 100.0,
    "certification_validity": 100.0,
    "safety_checks": 85.0
  },
  "used_component_weights": {
    "attendance": 0.30,
    "training_completion": 0.25,
    "certification_validity": 0.25,
    "safety_checks": 0.20
  }
}
```

### No supported Compliance evidence exists

```json
{
  "compliance_score": null,
  "available_components": {},
  "recognized_unsupported_evidence": [
    "Equipment_Attestations"
  ],
  "result_status": "Insufficient compliance evidence"
}
```

No evidence is not a zero score.

## Confidence and comparability

Compliance evidence confidence should be calculated against the obligations declared by the
active policy. It should measure valid evidence coverage separately from compliance performance.

For example:

```text
Policy requires attendance and training.
Attendance coverage = 90%
Training coverage = 60%
Compliance evidence confidence = lowest required-component coverage = 60%
```

The exact aggregation rule must be versioned, but the current product principle should remain:
missing required evidence lowers confidence and does not become poor performance.

Scores are comparable only when they use the same policy ID and version, or when an explicit
cross-policy comparison rule exists. The dashboard should:

- show the active policy and evaluated components;
- distinguish not applicable, missing, unsupported, neutral, and non-compliant states;
- rank employees only under the same policy and component scope;
- use one policy for team aggregation;
- expose missing and unsupported components; and
- never label an attendance-only result as comprehensive organizational compliance without a
  visible scope statement.

## API and persistence implications

- Add a versioned Compliance component registry and policy model.
- Extend calculation plans with component classification, semantic bindings, and validated join
  paths.
- Persist categorical normalization, applicability, neutral-state, and waiver mappings.
- Store the active policy ID/version and evaluated component set with immutable plan snapshots.
- Return component scores, weights, evidence coverage, missing applicable components, unsupported
  evidence, and limitations.
- Ensure `/dashboard`, trends, insights, report previews, and PDFs reuse the same backend policy
  and calculated values.
- Include policy and component schema in cache compatibility decisions.
- Prevent partial submissions from silently redefining the active Compliance policy.
- Define whether canonical evidence added later recalculates earlier reporting periods.

## Migration plan

1. **Define the registry contract.** Specify component identifiers, semantic roles, types,
   eligibility, neutral states, formulas, and evidence requirements.
2. **Version the current policy.** Preserve the existing calculation as
   `cedar_compliance_v1` and maintain benchmark parity, including documented duplicate exceptions.
3. **Define policy ownership.** Decide how a client policy is selected, approved, persisted, and
   changed.
4. **Extend planning output.** Allow the agent to classify registered Compliance components and
   bind approved roles without defining formulas or weights.
5. **Add Python validation.** Validate bindings, types, categorical mappings, applicability,
   identities, neutral states, and cross-table joins.
6. **Extract deterministic components.** Isolate attendance, reporting, and leave calculations
   behind the registry without changing current outputs.
7. **Add new components incrementally.** Approve and test training, certification, or other
   components one at a time.
8. **Add policy evaluation.** Calculate only declared obligations, distinguish missing from not
   applicable, and apply versioned weights.
9. **Update confidence and contracts.** Return policy-specific coverage, components, limitations,
   and insufficient-evidence states.
10. **Update consumers.** Display component scope and prevent invalid cross-policy comparisons in
    dashboards, trends, insights, and reports.
11. **Add regression tests.** Cover one-component, multi-component, no-component, unsupported,
    missing-applicable, neutral, waived, duplicate, orphan, unsafe-join, mixed-policy, and Cedar
    benchmark cases.

## Required decisions before implementation

- Whether an approved client policy is mandatory for an official Compliance score.
- Whether an adaptive available-components score is allowed and where it may be displayed.
- Who defines and approves policy components, weights, applicability, waivers, and grace periods.
- Whether limited-scope Compliance scores may contribute to overall performance.
- Whether different Compliance policies may ever be compared or aggregated.
- Which attendance checks are required for each attendance policy.
- Whether a missing required submission is a performance failure, an evidence gap, or both.
- How obligations and applicability are established when the source lacks explicit requirement
  records.
- Which future compliance components should be approved first.
- How policy changes and later evidence affect historical calculations.

Until these decisions are approved, the existing Cedar attendance, reporting, and leave formula
remains authoritative.

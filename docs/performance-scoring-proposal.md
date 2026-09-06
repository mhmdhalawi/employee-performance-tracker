# Proposed adaptive performance-scoring behavior

## Status

This document summarizes the proposed future behavior for Productivity, Compliance, and Quality.
It does not describe or modify the current implementation. Detailed designs are available in:

- [Productivity scoring proposal](productivity-scoring-proposal.md)
- [Compliance scoring proposal](compliance-scoring-proposal.md)
- [Quality scoring proposal](quality-scoring-proposal.md)

## Shared behavior

Clients may use unfamiliar table and column names and may provide sparse or rich evidence. The
proposed workflow is the same for every KPI family:

```text
Source table headers and metadata
→ planning agent identifies the family and binds headers to approved semantic roles
→ Python validates tables, columns, types, values, identities, and joins
→ Python determines which approved components are supported
→ Python applies a predefined, versioned profile or policy
→ Python returns the score, components, evidence coverage, and limitations
```

The planning agent interprets meaning but does not invent formulas, weights, or thresholds. A
table title is only a clue; it is never the calculation contract. Python runs only registered
deterministic calculations.

No supported evidence produces an insufficient-evidence result, not a score of zero.

## Productivity

Productivity measures completed work, timeliness, target achievement, or effort efficiency,
depending on which validated evidence is available.

### Example

A client provides a table named `Delivery_Log`:

```text
Worker_No, Job_Code, Job_State, Deadline, Closed_On
```

The planning agent proposes:

```json
{
  "family": "productivity",
  "bindings": {
    "employee_id": "Worker_No",
    "work_output_id": "Job_Code",
    "completion_status": "Job_State",
    "due_date": "Deadline",
    "completed_date": "Closed_On"
  }
}
```

Python validates the bindings and finds that completion rate and on-time rate are supported. It
selects the predefined `completion_timeliness_v1` profile:

```text
Completion rate = completed eligible outputs / eligible outputs × 100
On-time rate = outputs completed by due date / completed outputs with due dates × 100

Productivity = Completion rate × 60% + On-time rate × 40%
```

If the client provides only employee, work-output, and status fields, Python can use the approved
completion-only profile. If output targets and effort baselines are also present, Python can use
the richer target-and-effort profile. The returned profile name makes these results visibly
different.

## Compliance

Compliance is an extensible collection of approved obligations rather than a permanent set of
three table types. A client's versioned policy may contain one component, several components, or
future approved components such as training, certification, safety, or timesheet compliance.

### Example

A client whose policy covers attendance only provides `Clocking_History`:

```text
Badge_No, Work_Day, Rostered_In, Clocked_In, Rostered_Out, Clocked_Out
```

The planning agent proposes attendance bindings. Python validates the timestamp pairs and applies
the approved `attendance_only_v1` policy:

```text
Arrival score = on-time arrivals / valid arrival checks × 100
Shift-end score = compliant shift ends / valid shift-end checks × 100
Attendance score = equal average of available approved checks

Compliance = Attendance score × 100%
```

If the active policy also requires reporting or training but those tables are absent, Python
marks that evidence as missing. It does not assume the obligations are inapplicable. If another
table looks compliance-related but has no registered component, the result identifies it as
recognized but unsupported rather than inventing a calculation.

## Quality

Quality measures validated review outcomes. It can use direct accuracy, accuracy derived from
inspection and defect counts, first-pass approval, and absolute or proportional rework evidence.

### Example

A client provides `Inspection_Log`:

```text
Owner_ID, Check_ID, Items_Checked, Errors, Passed_First_Time
```

The planning agent proposes:

```json
{
  "family": "quality",
  "bindings": {
    "employee_id": "Owner_ID",
    "quality_review_id": "Check_ID",
    "inspected_item_count": "Items_Checked",
    "defect_count": "Errors",
    "first_pass_approved": "Passed_First_Time"
  }
}
```

Python validates the counts and derives accuracy:

```text
Accuracy = (inspected items - defective items) / inspected items × 100
First-pass rate = first-pass-approved reviews / eligible reviews × 100

Quality = Accuracy × 70% + First-pass rate × 30%
```

Python selects the predefined `accuracy_first_pass_v1` profile. With accuracy alone it may use an
approved accuracy-only profile. With validated accuracy, first-pass, and rework evidence it can
use a richer profile. Direct and defect-derived accuracy are alternative representations and are
never counted twice for the same review.

## Comparability and confidence

The proposed system returns a profile or policy identifier with every score. Two scores are
directly comparable only when they use the same family, profile or policy, version, and component
scope.

Evidence confidence remains separate from performance:

```text
Performance score = result calculated from valid available evidence
Evidence confidence = coverage of evidence required by the active profile or policy
```

Missing required evidence lowers confidence and may withhold the KPI or overall result. It does
not automatically lower the employee's performance score.

An illustrative response is:

```json
{
  "family": "quality",
  "score": 91.4,
  "profile": "accuracy_first_pass_v1",
  "profile_version": 1,
  "components": {
    "accuracy": 92.0,
    "first_pass_rate": 90.0
  },
  "evidence_confidence": 85.0,
  "unavailable_components": ["rework"],
  "limitations": [
    "Rework was not evaluated because no usable rework evidence was supplied."
  ]
}
```

## Summary

Under the proposal, clients do not need identical table titles or the maximum set of bindings:

- the planning agent maps the evidence that actually exists;
- Python validates every proposed binding;
- Python selects only a complete, approved profile or policy;
- richer evidence can support a richer calculation;
- sparse evidence may support a narrower, clearly labelled calculation;
- unsupported or absent evidence never causes an invented formula; and
- profile and policy metadata prevents unlike scores from being presented as equivalent.

# How the LLM classifies tables into KPI families

The LLM does not calculate KPI scores. Its job is to recognize what each table appears to
represent and map its source columns to fields understood by the approved Python calculators.
Python validates that mapping and performs all calculations.

## What the LLM receives

For every uploaded table, the LLM receives a compact synopsis containing information such as:

- the table name and column names;
- the number of rows;
- inferred column types, such as text, number, date, or boolean;
- structural hints, such as likely identifier, date, and numeric columns;
- numeric ranges, cardinality, and sparsity signals;
- the approved calculators and the fields required by each calculator.

The initial request does not include all source rows. The LLM must classify a table from the
meaning and structure of its columns, not from the table name alone.

## Productivity classification

A table looks like **Productivity** when its columns describe assigned work, completed work,
deadlines, completion status, and effort or hours spent.

Example source table:

| Task_No | Worker_No | Assigned | Deadline | Finished | Status | Hours | Verified |
| --- | --- | --- | --- | --- | --- | ---: | --- |
| JOB-101 | EMP-001 | 2026-06-01 | 2026-06-07 | 2026-06-06 | Complete | 30 | Verified |

The LLM can propose:

```json
{
  "kpi_family": "productivity",
  "calculator": "calculate_productivity",
  "field_bindings": {
    "record_id": "Task_No",
    "employee_id": "Worker_No",
    "assigned_date": "Assigned",
    "due_date": "Deadline",
    "completed_date": "Finished",
    "completion_status": "Status",
    "actual_effort_hours": "Hours",
    "verification_status": "Verified"
  }
}
```

The names do not need to match exactly. For example, `Hours` can be mapped to
`actual_effort_hours` because they have the same business meaning.

## Compliance classification

Compliance has three types of evidence, so a table can use one or more of three approved
calculators.

### Attendance compliance

An attendance table normally contains an employee, a date, scheduled and actual working
times, lunch times, and a record status.

Example columns:

```text
Attendance_ID, Employee, Date, Scheduled_In, Actual_In,
Lunch_Out, Lunch_In, Scheduled_Out, Actual_Out, Status, Confidence
```

The LLM classifies it as `compliance`, selects
`calculate_attendance_compliance`, and maps fields such as:

```text
Attendance_ID -> record_id
Employee      -> employee_id
Date          -> occurred_on
Scheduled_In  -> scheduled_start
Actual_In     -> actual_start
Scheduled_Out -> scheduled_end
Actual_Out    -> actual_end
```

### Report-submission compliance

A table containing report deadlines, submission dates, completeness, and verification looks
like submission-compliance evidence.

Example columns:

```text
Report_ID, Employee, Due_Date, Submitted_Date, Result,
Completeness, Verification
```

The LLM classifies it as `compliance` and selects
`calculate_submission_compliance`.

### Leave compliance

A table containing leave categories, start and end dates, approval outcomes, and documentation
status looks like leave-compliance evidence.

Example columns:

```text
Leave_ID, Employee, Leave_Type, Start, End, Approval, Documents_Complete
```

The LLM classifies it as `compliance` and selects `calculate_leave_compliance`.
Approved annual and sick leave is handled neutrally by Python; the LLM does not decide the
score.

## Quality classification

A table looks like **Quality** when it describes the accuracy of completed work, first-pass
approval, rework, and review or verification status.

Example source table:

| Review_No | Task_No | Worker_No | Review_Date | Accuracy | First_Pass | Rework_Hours | Verified |
| --- | --- | --- | --- | ---: | --- | ---: | --- |
| REV-501 | JOB-101 | EMP-001 | 2026-06-08 | 0.96 | true | 1.5 | Verified |

The LLM can propose:

```json
{
  "kpi_family": "quality",
  "calculator": "calculate_quality",
  "field_bindings": {
    "record_id": "Review_No",
    "related_output_id": "Task_No",
    "employee_id": "Worker_No",
    "occurred_on": "Review_Date",
    "accuracy_ratio": "Accuracy",
    "first_pass_approved": "First_Pass",
    "rework_hours": "Rework_Hours",
    "verification_status": "Verified"
  }
}
```

## Shared and non-KPI tables

Some tables are necessary but do not belong to one KPI family:

- An employee directory is classified as `shared` and uses `load_employees`.
- A performance-target table is classified as `shared` and uses
  `load_performance_targets`.
- Instructions, documentation, or unrelated business data are classified as `irrelevant`.
- A table that might contain KPI evidence but cannot satisfy an approved calculator contract
  is classified as `unsupported` instead of being forced into a KPI family.

## How Python keeps the classification safe

After the LLM returns its proposal, Python checks that:

- every source table has exactly one classification;
- the selected calculator belongs to the proposed KPI family;
- all required calculator fields are bound;
- every bound source column actually exists;
- one source column is not incorrectly bound more than once;
- the records satisfy the expected data types and validation rules.

If the structure is invalid, the system can make one targeted repair request. If the mapping
still does not pass validation, it is not used for scoring.

In short:

> The LLM recognizes the business meaning of the tables and columns. Python verifies the
> mapping and calculates the KPI results deterministically.

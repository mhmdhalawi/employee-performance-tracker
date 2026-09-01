# Deterministic KPI data dictionary

This file records the normalized fields consumed by Python calculators after the planning
agent's source-column bindings have passed structural validation. Source labels may differ;
the normalized meaning and formulas below do not.

## Required-evidence matrix

Missing required evidence changes evidence confidence, never employee performance. The
employee confidence value is the lowest coverage across the required source families below.
When it falls below the configured threshold (70% by default), component KPIs remain visible
for auditability but the overall score and performance tier are withheld as
`Insufficient data`.

| KPI family | Required evidence | Missing-evidence behavior |
| --- | --- | --- |
| Productivity | Verified `completion_status`; `actual_effort_hours` for completed work | Lower productivity evidence coverage; do not substitute zero effort or performance |
| Compliance | Mapped scheduled/actual arrival and shift-end pairs; mapped lunch check-out/return pair; verified report `submitted_date`; complete approved sick-leave documentation | Lower compliance evidence coverage; exclude the missing check from performance arithmetic |
| Quality | Verified `accuracy_ratio`, `first_pass_approved`, and `rework_hours` | Lower quality evidence coverage; do not create a zero quality result |

Every employee and evidence record must have a non-empty identifier. Duplicate employee IDs
or duplicate record IDs block the affected overall result; orphan evidence is reported and is
not silently joined to another employee.

## Compliance evidence

| Normalized field | Type | Required behavior |
| --- | --- | --- |
| `scheduled_start` | time, optional binding | Enables arrival calculation when paired with `actual_start` |
| `actual_start` | time, optional binding | Missing mapped value lowers confidence; never becomes zero performance |
| `scheduled_end` | time, optional binding | Enables shift-end calculation when paired with `actual_end` |
| `actual_end` | time, optional value | Missing value lowers confidence except for neutral leave or holidays |
| `lunch_out` | time, optional binding | Enables lunch calculation when paired with `lunch_in` |
| `lunch_in` | time, optional binding | Missing mapped value lowers confidence; return must be after check-out |
| `due_date` | date | Report deadline |
| `submitted_date` | date, optional value | Missing value lowers confidence; present value is compared with `due_date` |
| `verification_status` | text | Only verified submitted reports enter report performance |
| `category` | text | Identifies annual leave, sick leave, or holiday evidence |
| `outcome` | text | Identifies approved leave; not used to infer timestamp or report timeliness |
| `documentation_complete` | boolean | Required for approved sick leave to satisfy leave compliance |

## Compliance formulas

```text
Arrival = actual_start <= scheduled_start
Shift end = actual_end >= scheduled_end
Lunch = lunch_in > lunch_out, with both timestamps present
Attendance = equal average of available mapped arrival, shift-end, and lunch checks
Report = submitted_date <= due_date for verified, submitted reports
Leave = approved and documented sick-leave requests / sick-leave requests
Compliance = Attendance × 50% + Reports × 35% + Leave × 15%
```

Unavailable subcomponents are excluded and the remaining weights are normalized. Missing
required evidence lowers confidence. Approved annual leave and holidays are neutral, and no
arrival or departure grace period applies in the MVP.

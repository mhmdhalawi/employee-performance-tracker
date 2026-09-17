# Compliance KPI - changes to make

## Target result

Keep Compliance at **30% of the overall score** and calculate it as:

`Attendance and punctuality 30% + Shift adherence 35% + Break adherence 20% + Required submissions 15%`

Within Attendance and punctuality, use `attendance rate 60% + on-time rate 40%`.

## What is missing today

| Area | Current system | Required call-center version |
| --- | --- | --- |
| Formula | Attendance 50%, reports 35%, leave 15% | Four components weighted 30/35/20/15 |
| Attendance | Arrival, shift end, and lunch pass/fail checks | Presence rate plus on-time arrival rate |
| Shift adherence | Shift end pass/fail only | Correct worked minutes / required minutes |
| Breaks | Lunch timestamp order only | Compliant breaks / scheduled breaks |
| Timing policy | No grace period | Client-configured arrival grace period |
| Neutral events | Leave and holidays | Also training, outages, emergency leave, and approved schedule changes |

## Work checklist

### 1. Expand attendance and schedule evidence

- [ ] Add scheduled minutes, correct/adherent minutes, scheduled breaks, and compliant breaks.
- [ ] Record scheduled-day status, presence, arrival time, login/logout, and approved schedule changes.
- [ ] Add neutral-event types for training, outages, and policy-approved emergency leave.
- [ ] Combine reports, leave documents, and other required forms into one required-submissions measure.

### 2. Replace the compliance calculation

- [ ] Attendance rate: present scheduled days / eligible scheduled days.
- [ ] On-time rate: on-time arrivals / eligible arrivals, using the configured grace period.
- [ ] Attendance and punctuality: `attendance rate 60% + on-time rate 40%`.
- [ ] Shift adherence: `correct minutes / required minutes`, capped at 100.
- [ ] Break adherence: `compliant breaks / scheduled breaks`, capped at 100.
- [ ] Required submissions: `compliant / required`, capped at 100.
- [ ] Apply the 30/35/20/15 weights above; early login or skipped breaks must not earn bonus points.

Keep this as a versioned call-center calculation so historical benchmark records retain their existing meaning.

### 3. Preserve and extend controls

- [x] Duplicate attendance records are already excluded before scoring.
- [x] Missing clock values already lower confidence instead of becoming a performance failure.
- [ ] Send a missing clock record to review before applying any penalty.
- [ ] Exclude all approved neutral events from both expected and actual attendance measures.
- [ ] Require complete core attendance evidence for a scorable overall result.
- [ ] Keep component values auditable, but withhold the overall score below **100%** evidence confidence.

### 4. Update output and tests

- [ ] Show actual/required minutes, attendance counts, break counts, submission counts, and applied grace period.
- [ ] Add tests for grace-period boundaries, neutral events, schedule changes, missing clocks, duplicates, early login, skipped breaks, and missing submissions.
- [ ] Update dashboard/report calculation text and supporting-record displays.

## Done when

- The worked example produces `87.75`.
- Approved neutral events never reduce Compliance.
- Missing core evidence cannot be converted into a zero or a valid overall result.
- Any confidence below 100% returns `Insufficient data` for the overall result.

## Implementation notes

Likely touchpoints: attendance/submission schemas, calculator registry, validation, scoring metrics, evidence scope, employee evidence API, Vue evidence table, PDF generators, migrations, and tests.

Decisions needed before coding: arrival grace period, definition of "correct minutes," allowed break tolerance, and the list of required forms for each role/campaign.

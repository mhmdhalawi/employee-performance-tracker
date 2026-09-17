# Quality KPI - changes to make

## Target result

Keep Quality at **35% of the overall score** and calculate it as:

`QA evaluation 40% + First-contact resolution 25% + Documentation accuracy 15% + Customer satisfaction 10% + Escalation accuracy 10%`

## What is missing today

| Area | Current system | Required call-center version |
| --- | --- | --- |
| Formula | Accuracy 60%, first-pass 25%, rework 15% | Five call-center components weighted 40/25/15/10/10 |
| QA | One accuracy ratio | Calibrated rubric score and rubric version |
| Resolution | First-pass approval | Same-issue first-contact resolution |
| Documentation | Not separate | Correct records / reviewed records |
| Customer feedback | Not captured | Rating normalized to 100 with a minimum sample |
| Escalations | Not captured | Correct actions / reviewed actions |

## Work checklist

### 1. Add quality evidence

- [ ] Store interaction/case ID, review date, reviewer, rubric version, QA score, and evidence reference.
- [ ] Add resolution status and a same-issue repeat-contact indicator.
- [ ] Add documentation result, satisfaction rating plus rating scale, and escalation result.
- [ ] Mark invalid, abandoned, and test interactions so they can be excluded.

### 2. Replace the quality calculation

- [ ] QA evaluation: average valid calibrated review score.
- [ ] First-contact resolution: first-time resolutions / eligible cases.
- [ ] Documentation accuracy: correct records / reviewed records.
- [ ] Customer satisfaction: average rating / maximum rating.
- [ ] Escalation accuracy: correct actions / reviewed actions.
- [ ] Apply the 40/25/15/10/10 weights above and cap each component at 100.

Keep this as a versioned call-center calculator; do not reinterpret existing accuracy/first-pass/rework evidence.

### 3. Add sample and evidence controls

- [ ] Require at least five valid reviewed interactions per employee per month; flag fewer than ten as below the preferred sample.
- [ ] Define a minimum customer-satisfaction response sample.
- [ ] When the satisfaction sample is too small, omit that component, normalize the available weights, and lower confidence.
- [ ] Because the production gate is **100%**, any lowered confidence must withhold the overall score as `Insufficient data`; the Quality component may remain visible for audit.
- [ ] Exclude unverified, invalid, abandoned, and test interactions from scoring.

### 4. Add alerts and tests

- [ ] Create a critical alert for serious incorrect information or unresolved critical requests.
- [ ] Create a quality-risk alert when high productivity is paired with low quality.
- [ ] Add tests for sample thresholds, repeat-contact matching, rating normalization, missing optional components, excluded records, critical alerts, and the 100% gate.
- [ ] Show submetrics, sample sizes, reviewer/evidence links, and exclusions in employee details and reports.

## Done when

- The worked example produces `84.5`.
- Repeat contact counts only for the same unresolved issue.
- Small QA or satisfaction samples cannot produce an eligible overall result.
- Dashboard, employee details, trends, and PDFs show the same validated Quality result.

## Implementation notes

Likely touchpoints: quality schemas, calculator registry, scoring/validation, canonical evidence, employee evidence API, Vue evidence table, PDF generators, migrations, and test fixtures.

Decisions needed before coding: QA rubric fields and critical-failure rules, customer-satisfaction minimum sample, repeat-contact matching window, and the threshold for "low quality" in the cross-KPI alert.

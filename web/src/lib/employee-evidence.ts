import type { EmployeeEvidenceRow, EvidenceKpi } from '@/types/employee-evidence'

export const evidenceLabels: Record<EvidenceKpi, string> = {
  productivity: 'Productivity', compliance: 'Compliance', quality: 'Quality',
}
export const evidenceWeights: Record<EvidenceKpi, number> = {
  productivity: 35, compliance: 30, quality: 35,
}
export const evidenceDescriptions: Record<EvidenceKpi, string> = {
  productivity: 'Work completed, delivery dates, and hours worked.',
  compliance: 'Attendance, report submissions, and leave records.',
  quality: 'Work accuracy, first-pass approval, and rework.',
}
export const evidenceCalculations: Record<EvidenceKpi, string> = {
  productivity: '60% completion, 40% time efficiency.',
  compliance: '50% attendance, 35% reporting, 15% leave compliance.',
  quality: '60% accuracy, 25% first-pass approval, 15% rework.',
}
export function evidenceDate(value: string | null): string {
  return value === null ? 'Not provided' : new Intl.DateTimeFormat('en', {
    dateStyle: 'medium', timeZone: 'UTC',
  }).format(new Date(`${value}T00:00:00Z`))
}
export function evidencePercent(value: number): string {
  return `${Number((value * 100).toFixed(2))}%`
}
function hours(value: number | null): string {
  return value === null ? 'Not provided' : `${value} h`
}
function time(value: string | null): string {
  return value === null ? 'Not provided' : value.slice(0, 5)
}
export function evidenceSummaryColumns(kpi: EvidenceKpi): string[] {
  if (kpi === 'productivity') return ['Work record', 'Status', 'Due → completed', 'Hours worked']
  if (kpi === 'compliance') return ['Type', 'Date / period', 'Source outcome']
  return ['Work / review', 'Review date', 'Accuracy', 'First pass / rework']
}
export function evidenceSummaryCells(row: EmployeeEvidenceRow): string[] {
  switch (row.record_type) {
    case 'work_output':
      return [row.record_id, row.record.completion_status,
        `${evidenceDate(row.record.due_date)} → ${evidenceDate(row.record.completed_date)}`, hours(row.record.actual_effort_hours)]
    case 'attendance':
      return ['Attendance', evidenceDate(row.record.occurred_on), row.record.outcome]
    case 'submission':
      return ['Report', `Due ${evidenceDate(row.record.due_date)}`, row.record.outcome]
    case 'leave':
      return ['Leave', `${evidenceDate(row.record.start_date)} – ${evidenceDate(row.record.end_date)}`, row.record.outcome]
    case 'quality':
      return [`${row.record.related_output_id} · ${row.record_id}`, evidenceDate(row.record.occurred_on),
        evidencePercent(row.record.accuracy_ratio), `${row.record.first_pass_approved ? 'Approved' : 'Not approved'} · ${hours(row.record.rework_hours)}`]
  }
}
export function evidenceColumns(kpi: EvidenceKpi): string[] {
  if (kpi === 'productivity')
    return ['Work record', 'Assigned / due', 'Completed', 'Status', 'Actual hours', 'Evidence']
  if (kpi === 'compliance')
    return ['Type', 'Date / period', 'Record ID', 'Source outcome', 'Evidence summary']
  return ['Review ID', 'Work record', 'Review date', 'Accuracy', 'First pass', 'Rework', 'Evidence']
}
export function evidenceCells(row: EmployeeEvidenceRow): string[] {
  switch (row.record_type) {
    case 'work_output': {
      const r = row.record
      return [row.record_id, `${evidenceDate(r.assigned_date)} / ${evidenceDate(r.due_date)}`,
        evidenceDate(r.completed_date), r.completion_status, hours(r.actual_effort_hours), r.verification_status]
    }
    case 'attendance': {
      const r = row.record
      return ['Attendance', evidenceDate(r.occurred_on), row.record_id, r.outcome,
        `Start ${time(r.actual_start)} / scheduled ${time(r.scheduled_start)}; end ${time(r.actual_end)} / scheduled ${time(r.scheduled_end)}`]
    }
    case 'submission': {
      const r = row.record
      return ['Report', `Due ${evidenceDate(r.due_date)}`, row.record_id, r.outcome,
        `Submitted ${evidenceDate(r.submitted_date)}; completeness ${evidencePercent(r.completeness_ratio)}; ${r.verification_status}`]
    }
    case 'leave': {
      const r = row.record
      return ['Leave', `${evidenceDate(r.start_date)} – ${evidenceDate(r.end_date)}`, row.record_id,
        r.outcome, `${r.category}; documentation ${r.documentation_complete ? 'complete' : 'incomplete'}`]
    }
    case 'quality': {
      const r = row.record
      return [row.record_id, r.related_output_id, evidenceDate(r.occurred_on), evidencePercent(r.accuracy_ratio),
        r.first_pass_approved ? 'Approved' : 'Not approved', hours(r.rework_hours), r.verification_status]
    }
  }
}
export function evidenceDetails(row: EmployeeEvidenceRow): [string, string][] {
  const columns = evidenceColumns(row.record_type === 'work_output' ? 'productivity' : row.record_type === 'quality' ? 'quality' : 'compliance')
  const result = evidenceCells(row).map<[string, string]>((value, index) => [columns[index]!, value])
  if (row.record_type === 'attendance') {
    result.push(['Record status', row.record.record_status], ['Lunch out', time(row.record.lunch_out)],
      ['Lunch in', time(row.record.lunch_in)], ['Source-record confidence', evidencePercent(row.record.confidence_score)])
  }
  return result
}
export function evidenceLink(row: EmployeeEvidenceRow): string | null {
  if (row.record_type !== 'work_output' || !row.record.evidence_link)
    return null
  try {
    const url = new URL(row.record.evidence_link)
    return url.protocol === 'https:' && url.hostname ? url.href : null
  }
  catch { return null }
}
export function evidenceImpact(value: string): string {
  const labels: Record<string, string> = {
    none: 'No scoring impact', lowers_confidence: 'Lowers confidence', affects_score: 'Affects score',
    excluded_from_scoring: 'Excluded from scoring', blocks_score: 'Blocks score',
  }
  return labels[value] ?? value.replaceAll('_', ' ')
}

export function evidenceNeedsReview(row: EmployeeEvidenceRow): boolean {
  return row.excluded_from_scoring || row.validation_findings.some(finding => finding.severity !== 'info' || finding.scoring_impact !== 'none')
}

export function evidenceIssueLabel(code: string): string {
  const labels: Record<string, string> = {
    missing_actual_start: 'Missing arrival time',
    missing_actual_end: 'Missing shift end time',
    missing_lunch_in: 'Missing lunch return time',
    missing_lunch_out: 'Missing lunch check-out time',
    missing_scheduled_start: 'Missing scheduled start time',
    missing_scheduled_end: 'Missing scheduled end time',
    missing_actual_effort: 'Missing hours worked',
    missing_productivity_evidence: 'Work evidence needs verification',
    overdue_work_output: 'Work past due date',
    missing_submission: 'Missing report submission',
    missing_submission_evidence: 'Report evidence needs verification',
    late_submission: 'Report submitted late',
    incomplete_sick_leave_documentation: 'Incomplete sick-leave documentation',
    orphan_quality_evidence: 'Related work record missing',
    low_accuracy: 'Low accuracy',
    missing_quality_evidence: 'Quality evidence needs verification',
    duplicate_attendance: 'Duplicate attendance record',
    duplicate_record_id: 'Duplicate record ID',
  }
  return labels[code] ?? code.replaceAll('_', ' ')
}

export function evidenceDisclosureDetails(row: EmployeeEvidenceRow): [string, string][] {
  if (row.record_type !== 'attendance') return evidenceDetails(row)
  const r = row.record
  return [
    ['Type', 'Attendance'], ['Date', evidenceDate(r.occurred_on)], ['Record ID', row.record_id],
    ['Source outcome', r.outcome], ['Record status', r.record_status],
    ['Scheduled start', time(r.scheduled_start)], ['Actual start', time(r.actual_start)],
    ['Scheduled end', time(r.scheduled_end)], ['Actual end', time(r.actual_end)],
    ['Lunch out', time(r.lunch_out)], ['Lunch in', time(r.lunch_in)],
    ['Source-record confidence', evidencePercent(r.confidence_score)],
  ]
}

export function evidenceFieldHasFinding(row: EmployeeEvidenceRow, label: string): boolean {
  const fields: Record<string, string> = {
    missing_actual_start: 'Actual start', missing_actual_end: 'Actual end',
    missing_scheduled_start: 'Scheduled start', missing_scheduled_end: 'Scheduled end',
    missing_lunch_in: 'Lunch in', missing_lunch_out: 'Lunch out', missing_actual_effort: 'Actual hours',
  }
  return row.validation_findings.some(finding => fields[finding.code] === label)
}

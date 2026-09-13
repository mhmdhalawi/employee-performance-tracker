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

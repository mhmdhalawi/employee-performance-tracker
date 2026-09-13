import type { AnalysisFilters, ValidationFinding } from '@/types/analysis'

export type EvidenceKpi = 'productivity' | 'compliance' | 'quality'

interface EvidenceRecord {
  record_id: string
  employee_id: string
}
export interface WorkOutputRecord extends EvidenceRecord {
  assigned_date: string
  due_date: string
  completed_date: string | null
  completion_status: string
  actual_effort_hours: number | null
  verification_status: string
  evidence_link: string | null
}
export interface AttendanceRecord extends EvidenceRecord {
  occurred_on: string
  outcome: string
  record_status: string
  scheduled_start: string | null
  actual_start: string | null
  lunch_out: string | null
  lunch_in: string | null
  scheduled_end: string | null
  actual_end: string | null
  confidence_score: number
}
export interface SubmissionRecord extends EvidenceRecord {
  due_date: string
  submitted_date: string | null
  outcome: string
  completeness_ratio: number
  verification_status: string
}
export interface LeaveRecord extends EvidenceRecord {
  category: string
  start_date: string
  end_date: string
  outcome: string
  documentation_complete: boolean
}
export interface QualityRecord extends EvidenceRecord {
  related_output_id: string
  occurred_on: string
  accuracy_ratio: number
  first_pass_approved: boolean
  rework_hours: number
  verification_status: string
}
interface EvidenceRow<Type, Record> {
  record_type: Type
  record_id: string
  record: Record
  validation_findings: ValidationFinding[]
  excluded_from_scoring: boolean
  exclusion_reason: string | null
}
export type WorkOutputRow = EvidenceRow<'work_output', WorkOutputRecord>
export type AttendanceRow = EvidenceRow<'attendance', AttendanceRecord>
export type SubmissionRow = EvidenceRow<'submission', SubmissionRecord>
export type LeaveRow = EvidenceRow<'leave', LeaveRecord>
export type QualityRow = EvidenceRow<'quality', QualityRecord>
export type ComplianceRow = AttendanceRow | SubmissionRow | LeaveRow
export type EmployeeEvidenceRow = WorkOutputRow | ComplianceRow | QualityRow
export interface EvidenceTable<Row = EmployeeEvidenceRow> {
  total_count: number
  rows: Row[]
}
export interface EmployeeEvidenceTables {
  productivity: EvidenceTable<WorkOutputRow>
  compliance: EvidenceTable<ComplianceRow>
  quality: EvidenceTable<QualityRow>
}
export interface EmployeeEvidenceResponse extends EvidenceTable {
  employee: { employee_id: string, employee_name: string | null, team: string | null, role: string | null }
  kpi: EvidenceKpi
  applied_filters: AnalysisFilters
  latest_submission_at: string
  page: number
  page_size: number
}

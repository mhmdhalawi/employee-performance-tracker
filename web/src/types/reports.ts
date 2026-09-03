import type { KpiTrendPoint } from '@/types/analysis'

export interface EmployeeReportRequest {
  employee_id: string
  start_date: string
  end_date: string
}

export interface ReportPeriod {
  start_date: string
  end_date: string
  prior_start_date: string | null
  prior_end_date: string | null
}

export interface ReportKpiSection {
  name: 'Productivity' | 'Compliance' | 'Quality'
  score: number
  weight: number
  explanation: string
}

export interface ReportFinding {
  code: string
  severity: 'error' | 'warning' | 'info'
  scoring_impact: string
  message: string
  occurrence_count: number
  record_ids: string[]
  evidence_links: string[]
}

export interface EmployeeReportData {
  employee_id: string
  employee_name: string | null
  team: string | null
  role: string | null
  period: ReportPeriod
  generated_at: string
  overall_score: number | null
  result_status: string
  performance_tier: string | null
  data_confidence: number
  confidence_threshold: number
  confidence_explanation: string
  kpis: ReportKpiSection[]
  trends: KpiTrendPoint[]
  prior_overall_score: number | null
  overall_score_change: number | null
  findings: ReportFinding[]
  supporting_record_ids: string[]
  metric_definitions: string[]
  manager_review_notice: string
}

export interface EmployeeReportPreviewResponse {
  report: EmployeeReportData
  pdf_generated_by: 'browser'
}

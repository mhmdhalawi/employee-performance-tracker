export interface AnalysisSummary {
  total_employee_count: number
  scored_employee_count: number
  insufficient_data_count: number
  average_overall_score: number | null
  average_productivity_score: number | null
  average_compliance_score: number | null
  average_quality_score: number | null
  narrative: string
}

export interface AnalysisFilters {
  employee_id: string | null
  team: string | null
  start_date: string | null
  end_date: string | null
  period_weeks: 4 | 8 | 12 | null
}

export interface DatasetOverview {
  employee_count: number
  date_start: string | null
  date_end: string | null
  record_counts: Record<string, number>
  teams: string[]
}

export interface ValidationFinding {
  code: string
  severity: 'error' | 'warning' | 'info'
  message: string
  record_ids: string[]
  employee_id: string | null
  source_type: string | null
  scoring_impact: string
}

export interface EmployeeKpiResult {
  employee_id: string
  employee_name: string | null
  team: string | null
  role: string | null
  productivity_score: number | null
  productivity_reason: string
  compliance_score: number | null
  compliance_reason: string
  quality_score: number | null
  quality_reason: string
  data_confidence: number
  confidence_threshold: number
  confidence_reason: string
  overall_score: number | null
  result_status: string
  performance_tier: string | null
  supporting_record_ids: string[]
  evidence_links: string[]
  validation_findings: ValidationFinding[]
}

export interface KpiTrendPoint {
  period_start: string
  period_end: string
  employee_count: number
  scored_employee_count: number
  productivity_employee_count: number
  compliance_employee_count: number
  quality_employee_count: number
  productivity_score: number | null
  compliance_score: number | null
  quality_score: number | null
  overall_score: number | null
  data_confidence: number | null
  record_count: number
}

export interface PerformanceAlert {
  code: string
  severity: 'error' | 'warning' | 'info'
  message: string
  employee_id: string | null
  employee_name: string | null
  team: string | null
  occurrence_count: number
  record_ids: string[]
  evidence_links: string[]
  scoring_impact: string
}

export interface AIInsightStatement {
  message: string
  record_ids: string[]
}

export interface EmployeeAIInsight {
  employee_id: string
  explanation: AIInsightStatement
  recommendations: AIInsightStatement[]
}

export interface AIInsightResponse {
  insight: EmployeeAIInsight
  model: string
  total_tokens: number
  model_requests: number
}

export interface DashboardFilters {
  employee_id?: string
  team?: string
  start_date?: string
  end_date?: string
  period_weeks?: 4 | 8 | 12
}

export interface EmployeeFilterOption {
  employee_id: string
  employee_name: string | null
  team: string | null
}

export interface SchemaMappingSummary {
  schema_fingerprint: string
  included_submission_count: number
  selected_tables: string[]
  table_classifications: TableClassification[]
}

export interface DashboardResponse {
  analysis_id: string
  results: EmployeeKpiResult[]
  summary: AnalysisSummary
  dataset_overview: DatasetOverview
  applied_filters: AnalysisFilters
  available_employees: EmployeeFilterOption[]
  available_teams: string[]
  trends: KpiTrendPoint[]
  alerts: PerformanceAlert[]
  limitations: string[]
  coverage_start: string | null
  coverage_end: string | null
  included_submission_count: number
  latest_submission_at: string
  mapping_summaries: SchemaMappingSummary[]
}

export interface TableClassification {
  source_name: string
  kpi_family: 'productivity' | 'compliance' | 'quality' | 'shared' | 'irrelevant' | 'unsupported'
  calculator_invocations: Array<{
    calculator:
      | 'load_employees'
      | 'load_performance_targets'
      | 'calculate_productivity'
      | 'calculate_attendance_compliance'
      | 'calculate_submission_compliance'
      | 'calculate_leave_compliance'
      | 'calculate_quality'
    field_bindings: Record<string, string>
  }>
  confidence: 'low' | 'medium' | 'high'
  rationale: string
}

export interface ErrorPayload {
  error?: {
    message?: string
  }
}

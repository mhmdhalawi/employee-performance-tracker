export interface AnalysisSummary {
  total_employee_count: number
  scored_employee_count: number
  insufficient_data_count: number
  narrative: string
}

export interface EmployeeKpiResult {
  employee_id: string
  employee_name: string | null
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
  validation_findings: unknown[]
}

export interface AnalyzeResponse {
  file_name: string
  file_type: string
  byte_size: number
  results: EmployeeKpiResult[]
  summary: AnalysisSummary
  limitations: string[]
  selected_tables: string[]
  model: string | null
  total_tokens: number
  model_requests: number
  mapping_cache_hit: boolean
}

export interface ErrorPayload {
  error?: {
    message?: string
  }
}

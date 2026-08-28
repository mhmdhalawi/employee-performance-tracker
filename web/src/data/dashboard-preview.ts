import type { EmployeeKpiResult } from '@/types/analysis'

export const previewResults: EmployeeKpiResult[] = [
  { employee_id: 'EMP-003', employee_name: 'Avery Chen', productivity_score: 91, productivity_reason: 'Strong completion and time efficiency.', compliance_score: 96, compliance_reason: 'Attendance and reporting evidence are complete.', quality_score: 94, quality_reason: 'High accuracy with low rework.', data_confidence: 98, confidence_threshold: 70, confidence_reason: 'All required evidence is present.', overall_score: 93.5, result_status: 'Scored', performance_tier: 'Exceptional', supporting_record_ids: ['PRJ-1042', 'ATT-2203', 'QA-883'], validation_findings: [] },
  { employee_id: 'EMP-011', employee_name: 'Jordan Patel', productivity_score: 84, productivity_reason: 'Consistent delivery across the period.', compliance_score: 88, compliance_reason: 'Required reports were submitted.', quality_score: 86, quality_reason: 'Good first-pass approval rate.', data_confidence: 92, confidence_threshold: 70, confidence_reason: 'Evidence coverage is sufficient.', overall_score: 85.9, result_status: 'Scored', performance_tier: 'Strong', supporting_record_ids: ['PRJ-1118', 'REP-431', 'QA-912'], validation_findings: [] },
  { employee_id: 'EMP-018', employee_name: 'Sam Rivera', productivity_score: 78, productivity_reason: 'Completion is healthy; efficiency can improve.', compliance_score: 82, compliance_reason: 'One late report reduced compliance.', quality_score: 80, quality_reason: 'Accuracy is stable.', data_confidence: 86, confidence_threshold: 70, confidence_reason: 'Evidence coverage is sufficient.', overall_score: 79.9, result_status: 'Scored', performance_tier: 'Solid', supporting_record_ids: ['PRJ-1150', 'REP-448', 'QA-936'], validation_findings: [] },
  { employee_id: 'EMP-024', employee_name: 'Morgan Lee', productivity_score: 73, productivity_reason: 'Some projects exceeded planned hours.', compliance_score: 76, compliance_reason: 'Attendance evidence is mostly complete.', quality_score: 89, quality_reason: 'Strong accuracy and first-pass approval.', data_confidence: 81, confidence_threshold: 70, confidence_reason: 'Evidence coverage is sufficient.', overall_score: 79.6, result_status: 'Scored', performance_tier: 'Solid', supporting_record_ids: ['PRJ-1204', 'ATT-2294', 'QA-970'], validation_findings: [] },
  { employee_id: 'EMP-029', employee_name: 'Taylor Brooks', productivity_score: 69, productivity_reason: 'Completion evidence is available.', compliance_score: 71, compliance_reason: 'Available records were validated.', quality_score: 74, quality_reason: 'Quality reviews are partially available.', data_confidence: 64, confidence_threshold: 70, confidence_reason: 'Verified evidence coverage is below the threshold.', overall_score: null, result_status: 'Insufficient data', performance_tier: null, supporting_record_ids: ['PRJ-1237', 'QA-991'], validation_findings: [] },
]

export const previewTeams: Record<string, string> = {
  'EMP-003': 'Operations',
  'EMP-011': 'Operations',
  'EMP-018': 'Delivery',
  'EMP-024': 'Quality',
  'EMP-029': 'Delivery',
}

export const previewTrends = [
  { week: 'W1', productivity: 76, compliance: 84, quality: 80 },
  { week: 'W2', productivity: 79, compliance: 85, quality: 82 },
  { week: 'W3', productivity: 78, compliance: 87, quality: 83 },
  { week: 'W4', productivity: 82, compliance: 86, quality: 84 },
  { week: 'W5', productivity: 84, compliance: 89, quality: 85 },
  { week: 'W6', productivity: 83, compliance: 90, quality: 87 },
  { week: 'W7', productivity: 86, compliance: 91, quality: 88 },
  { week: 'W8', productivity: 87, compliance: 90, quality: 89 },
  { week: 'W9', productivity: 85, compliance: 92, quality: 90 },
  { week: 'W10', productivity: 88, compliance: 93, quality: 91 },
  { week: 'W11', productivity: 90, compliance: 94, quality: 92 },
  { week: 'W12', productivity: 91, compliance: 95, quality: 93 },
]

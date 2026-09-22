import type { FindingCategory, PerformanceAlert, ValidationFinding } from '@/types/analysis'

export type AttentionItem = Pick<PerformanceAlert, 'code' | 'severity' | 'scoring_impact' | 'message' | 'category' | 'action' | 'occurrence_count' | 'record_ids' | 'evidence_links'>

export const findingCategoryLabel: Record<FindingCategory, string> = {
  data_issue: 'Data Issues',
  performance_alert: 'Performance Alerts',
}

export function needsAttention<T extends AttentionItem>(items: T[]): T[] {
  return items.filter(item => item.severity !== 'info' || item.scoring_impact !== 'none')
}

export function attentionOutsideRecords<T extends AttentionItem>(items: T[], findings: ValidationFinding[]): T[] {
  return needsAttention(items).filter(item => !item.record_ids.length || item.record_ids.some(id =>
    !findings.some(finding => finding.code === item.code && finding.category === item.category && finding.record_ids.includes(id))))
}

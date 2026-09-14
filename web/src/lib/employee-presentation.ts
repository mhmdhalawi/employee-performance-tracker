import type { PerformanceAlert, ValidationFinding } from '@/types/analysis'

export type AttentionItem = Pick<PerformanceAlert, 'code' | 'severity' | 'scoring_impact' | 'message' | 'occurrence_count' | 'record_ids' | 'evidence_links'>

export function needsAttention<T extends AttentionItem>(items: T[]): T[] {
  return items.filter(item => item.severity !== 'info' || item.scoring_impact !== 'none')
}

export function attentionOutsideRecords<T extends AttentionItem>(items: T[], findings: ValidationFinding[]): T[] {
  return needsAttention(items).filter(item => !item.record_ids.length || item.record_ids.some(id =>
    !findings.some(finding => finding.code === item.code && finding.record_ids.includes(id))))
}

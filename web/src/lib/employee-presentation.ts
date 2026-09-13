import type { PerformanceAlert } from '@/types/analysis'

export type AttentionItem = Pick<PerformanceAlert, 'code' | 'severity' | 'scoring_impact' | 'message' | 'occurrence_count' | 'record_ids' | 'evidence_links'>

export function needsAttention<T extends AttentionItem>(items: T[]): T[] {
  return items.filter(item => item.severity !== 'info' || item.scoring_impact !== 'none')
}

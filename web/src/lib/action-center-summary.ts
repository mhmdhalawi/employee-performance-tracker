import type { PerformanceAlert } from '@/types/analysis'

export const actionGroupDefinitions = [
  { key: 'evidence', label: 'Evidence gaps', description: 'Records lowering data confidence' },
  { key: 'performance', label: 'Performance alerts', description: 'Findings affecting KPI scores' },
  { key: 'excluded', label: 'Excluded records', description: 'Records left out of scoring' },
  { key: 'other', label: 'Other data issues', description: 'Findings requiring source review' },
] as const

export type ActionGroupKey = (typeof actionGroupDefinitions)[number]['key']

export interface ActionGroupSummary {
  key: ActionGroupKey
  label: string
  description: string
  alerts: PerformanceAlert[]
  findingCount: number
  employeeCount: number
}

export function countFindings(alerts: PerformanceAlert[]): number {
  return alerts.reduce((total, alert) => total + alert.occurrence_count, 0)
}

export function countAffectedEmployees(alerts: PerformanceAlert[]): number {
  return new Set(alerts.map(alert => alert.employee_id).filter(Boolean)).size
}

export function summarizeActionCenter(alerts: PerformanceAlert[]): {
  totalFindings: number
  affectedEmployees: number
  groups: ActionGroupSummary[]
} {
  const groups = actionGroupDefinitions.map((definition) => {
    const groupAlerts = alerts.filter(alert => groupKey(alert) === definition.key)
    return {
      ...definition,
      alerts: groupAlerts,
      findingCount: countFindings(groupAlerts),
      employeeCount: countAffectedEmployees(groupAlerts),
    }
  }).filter(group => group.alerts.length)
  return {
    totalFindings: countFindings(alerts),
    affectedEmployees: countAffectedEmployees(alerts),
    groups,
  }
}

function groupKey(alert: PerformanceAlert): ActionGroupKey {
  if (alert.category === 'performance_alert') return 'performance'
  if (alert.scoring_impact === 'lowers_confidence') return 'evidence'
  if (alert.scoring_impact === 'excluded_from_scoring') return 'excluded'
  return 'other'
}

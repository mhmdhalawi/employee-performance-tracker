import type { CanvasElement, Content, TableCell, TDocumentDefinitions } from 'pdfmake/interfaces'
import { formatDate, formatDateTime } from '@/lib/date-format'
import { summarizeActionCenter } from '@/lib/action-center-summary'
import type { DashboardResponse, EmployeeKpiResult, KpiTrendPoint, PerformanceAlert } from '@/types/analysis'

export type DashboardKpi = 'productivity' | 'compliance' | 'quality'

const cedar = '#078181'
const cedarLight = '#E7F3F3'
const ink = '#0D0D0D'
const muted = '#555B59'
const line = '#D8DDDC'
const compliance = '#C18426'

function scoredPopulation(count: number): string {
  return `${count} scored employee${count === 1 ? '' : 's'}`
}

const kpiDetails: Record<DashboardKpi, { label: string, weight: number, description: string }> = {
  productivity: {
    label: 'Productivity',
    weight: 35,
    description: 'Completion and time-efficiency evidence for the selected employees and period.',
  },
  compliance: {
    label: 'Compliance',
    weight: 30,
    description: 'Attendance, report-submission, and leave-compliance evidence for the selected employees and period.',
  },
  quality: {
    label: 'Quality',
    weight: 35,
    description: 'Accuracy, first-pass approval, and rework evidence for the selected employees and period.',
  },
}

export async function downloadTeamReportPdf(analysis: DashboardResponse): Promise<void> {
  const bytes = await createTeamReportPdfBytes(analysis)
  downloadPdf(bytes, reportFilename(analysis, 'call-center-performance'))
}

export async function downloadKpiReportPdf(analysis: DashboardResponse, kpi: DashboardKpi): Promise<void> {
  const bytes = await createKpiReportPdfBytes(analysis, kpi)
  downloadPdf(bytes, reportFilename(analysis, `${kpi}-performance`))
}

export async function createTeamReportPdfBytes(analysis: DashboardResponse): Promise<Uint8Array> {
  return createPdf(teamDocumentDefinition(analysis))
}

export async function createKpiReportPdfBytes(
  analysis: DashboardResponse,
  kpi: DashboardKpi,
): Promise<Uint8Array> {
  return createPdf(kpiDocumentDefinition(analysis, kpi))
}

async function createPdf(definition: TDocumentDefinitions): Promise<Uint8Array> {
  const [{ default: pdfMake }, { default: pdfFonts }] = await Promise.all([
    import('pdfmake/build/pdfmake'),
    import('pdfmake/build/vfs_fonts'),
  ])
  pdfMake.addVirtualFileSystem(pdfFonts)
  return pdfMake.createPdf(definition).getBuffer()
}

function downloadPdf(bytes: Uint8Array, filename: string): void {
  const blob = new Blob([new Uint8Array(bytes)], { type: 'application/pdf' })
  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = filename
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0)
}

function teamDocumentDefinition(analysis: DashboardResponse): TDocumentDefinitions {
  const team = analysis.applied_filters.team || 'All employees'
  const population = scoredPopulation(analysis.summary.scored_employee_count)
  const content: Content[] = [
    reportHeading('Call-center performance', team, analysis),
    {
      table: {
        widths: ['*', '*', '*', '*'],
        body: [[
          metricCell('Overall average', optionalScore(analysis.summary.average_overall_score), population),
          metricCell('Productivity', optionalScore(analysis.summary.average_productivity_score), `${population} · 35% of overall`),
          metricCell('Compliance', optionalScore(analysis.summary.average_compliance_score), `${population} · 30% of overall`),
          metricCell('Quality', optionalScore(analysis.summary.average_quality_score), `${population} · 35% of overall`),
        ]],
      },
      layout: cardLayout(),
      margin: [0, 0, 0, 16],
    },
    { text: 'Coverage', style: 'sectionTitle' },
    {
      text: `${analysis.summary.total_employee_count} employees · ${analysis.summary.scored_employee_count} scored · ${analysis.summary.insufficient_data_count} withheld for insufficient data`,
      color: muted,
      margin: [0, 4, 0, 14],
    },
    actionCenterSummaryBlock(analysis.alerts),
    teamTrendChart(analysis.trends),
    { text: 'Employee results', style: 'sectionTitle', ...(analysis.trends.length ? { pageBreak: 'before' as const } : {}) },
    employeeResultsTable(analysis.results),
    ...(analysis.trends.length ? [teamTrendTable(analysis.trends)] : []),
  ]
  return baseDocument('CALL-CENTER PERFORMANCE REPORT', content)
}

function kpiDocumentDefinition(analysis: DashboardResponse, kpi: DashboardKpi): TDocumentDefinitions {
  const details = kpiDetails[kpi]
  const average = analysis.summary[`average_${kpi}_score`]
  const team = analysis.applied_filters.team || 'All teams'
  const content: Content[] = [
    reportHeading(`${details.label} report`, team, analysis),
    {
      table: {
        widths: ['*', '*', '*'],
        body: [[
          metricCell('Average score', optionalScore(average), scoredPopulation(analysis.summary.scored_employee_count)),
          metricCell('Overall weight', `${details.weight}%`, 'Configured contribution'),
          metricCell('Reporting status', `${analysis.summary.scored_employee_count} scored`, `${analysis.summary.insufficient_data_count} withheld`),
        ]],
      },
      layout: cardLayout(),
      margin: [0, 0, 0, 16],
    },
    { text: 'What this KPI covers', style: 'sectionTitle' },
    { text: details.description, color: muted, margin: [0, 4, 0, 14] },
    { text: `${details.label} by employee`, style: 'sectionTitle' },
    kpiEmployeeTable(analysis.results, kpi),
    { text: `${details.label} trend`, style: 'sectionTitle', margin: [0, 16, 0, 4] },
    kpiTrendTable(analysis.trends, kpi),
  ]
  return baseDocument(`${details.label.toUpperCase()} REPORT`, content)
}

function baseDocument(reportLabel: string, content: Content[]): TDocumentDefinitions {
  return {
    pageSize: 'A4',
    pageOrientation: 'landscape',
    pageMargins: [38, 46, 38, 34],
    defaultStyle: { font: 'Roboto', fontSize: 7.5, color: ink, lineHeight: 1.08 },
    header: () => ({
      margin: [38, 19, 38, 0],
      columns: [
        { text: 'CEDAR', bold: true, color: cedar, fontSize: 14, characterSpacing: 1.2 },
        { text: reportLabel, alignment: 'right', color: muted, fontSize: 8 },
      ],
    }),
    footer: (currentPage: number, pageCount: number) => ({
      margin: [38, 10, 38, 0],
      columns: [
        { text: `Generated ${formatDateTime(new Date().toISOString())}`, color: muted, fontSize: 7 },
        { text: `${currentPage} / ${pageCount}`, alignment: 'right', color: muted, fontSize: 7 },
      ],
    }),
    content,
    styles: {
      title: { fontSize: 20, bold: true, color: cedar, margin: [0, 0, 0, 3] },
      sectionTitle: { fontSize: 11, bold: true, color: cedar },
    },
  }
}

function reportHeading(title: string, team: string, analysis: DashboardResponse): Content {
  const filters = analysis.applied_filters
  const scope = ([
    ['Campaign', filters.campaign],
    ['Queue', filters.queue],
    ['Shift', filters.shift],
    ['Supervisor', filters.supervisor],
    ['Location', filters.location],
  ] as const).filter(([, value]) => Boolean(value)).map(([label, value]) => `${label}: ${value}`).join('  |  ')
  const scorePeriod = filters.score_period_start_date && filters.score_period_end_date
    && (filters.score_period_start_date !== filters.start_date || filters.score_period_end_date !== filters.end_date)
    ? `Scores use available evidence: ${formatDate(filters.score_period_start_date)} - ${formatDate(filters.score_period_end_date)}.`
    : ''
  return {
    stack: [
      { text: title, style: 'title' },
      { text: `${team} · ${formatPeriod(analysis)} · Current filtered dashboard`, color: muted },
      ...(scope ? [{ text: scope, color: muted, margin: [0, 4, 0, 0] } as Content] : []),
      ...(scorePeriod ? [{ text: scorePeriod, color: muted, margin: [0, 4, 0, 0] } as Content] : []),
    ],
    margin: [0, 0, 0, 12],
  }
}

function employeeResultsTable(results: EmployeeKpiResult[]): Content {
  if (!results.length)
    return emptyState('No employees match the current filters.')

  return dataTable(
    ['Employee', 'Campaign / Queue', 'Productivity', 'Compliance', 'Quality', 'Data confidence', 'Overall', 'Status'],
    results.map(row => [
      `${row.employee_name || row.employee_id}\n${row.employee_id}`,
      `${row.campaign || 'Campaign not provided'}\n${row.queue || 'Queue not provided'}`,
      optionalScore(row.productivity_score),
      optionalScore(row.compliance_score),
      optionalScore(row.quality_score),
      score(row.data_confidence),
      row.overall_score === null ? 'Withheld' : score(row.overall_score),
      row.performance_tier || row.result_status,
    ]),
    ['*', 115, 57, 57, 57, 54, 54, 70],
  )
}

function kpiEmployeeTable(results: EmployeeKpiResult[], kpi: DashboardKpi): Content {
  if (!results.length)
    return emptyState('No employees match the current filters.')

  return dataTable(
    ['Employee', 'Team', `${kpiDetails[kpi].label} score`, 'Data confidence', 'Overall status'],
    results.map(row => [
      `${row.employee_name || row.employee_id}\n${row.employee_id}`,
      row.team || 'Not provided',
      optionalScore(row[`${kpi}_score`]),
      score(row.data_confidence),
      row.performance_tier || row.result_status,
    ]),
    ['*', '*', 90, 90, 110],
  )
}

function teamTrendTable(trends: KpiTrendPoint[]): Content {
  return dataTable(
    ['Week ending', 'Employees', 'Productivity', 'Compliance', 'Quality', 'Overall', 'Data confidence'],
    trends.map(point => [
      formatDate(point.period_end),
      String(point.employee_count),
      optionalScore(point.productivity_score),
      optionalScore(point.compliance_score),
      optionalScore(point.quality_score),
      optionalScore(point.overall_score),
      optionalScore(point.data_confidence),
    ]),
    ['*', 55, 65, 65, 65, 60, 65],
    'Weekly values',
    trends.length >= 8,
  )
}

function actionCenterSummaryBlock(alerts: PerformanceAlert[]): Content {
  const summary = summarizeActionCenter(alerts)
  if (!summary.groups.length) {
    return {
      stack: [
        { text: 'Action Center', style: 'sectionTitle' },
        { text: 'No findings for the selected filters.', color: muted, margin: [0, 4, 0, 0] },
      ],
    }
  }
  return {
    stack: [
      {
        columns: [
          { text: 'Action Center', style: 'sectionTitle' },
          { text: `${summary.totalFindings} findings · ${summary.affectedEmployees} affected employees`, alignment: 'right', color: muted, fontSize: 8 },
        ],
        margin: [0, 0, 0, 6],
      },
      {
        table: {
          widths: summary.groups.map(() => '*'),
          body: [summary.groups.map<TableCell>(group => ({
            fillColor: group.key === 'evidence' ? '#FFF8EB' : group.key === 'performance' ? cedarLight : '#F3F5F5',
            stack: [
              { text: group.label, bold: true, color: group.key === 'evidence' ? '#80520B' : cedar, fontSize: 8 },
              { text: `${group.findingCount} ${group.findingCount === 1 ? 'finding' : 'findings'}`, bold: true, margin: [0, 4, 0, 2] },
              { text: `${group.employeeCount} affected ${group.employeeCount === 1 ? 'employee' : 'employees'}`, color: muted, fontSize: 7 },
            ],
          }))],
        },
        layout: {
          hLineWidth: () => 0,
          vLineWidth: (index: number) => index > 0 && index < summary.groups.length ? 5 : 0,
          vLineColor: () => '#FFFFFF',
          paddingLeft: () => 8,
          paddingRight: () => 8,
          paddingTop: () => 7,
          paddingBottom: () => 7,
        },
      },
    ],
  }
}

function teamTrendChart(trends: KpiTrendPoint[]): Content {
  if (!trends.length)
    return { stack: [
      { text: 'Weekly KPI trend', style: 'sectionTitle' },
      emptyState('No trend data is available for this period.'),
    ], margin: [0, 16, 0, 0] }

  const left = 6
  const right = 720
  const top = 8
  const bottom = 180
  const x = (index: number) => trends.length === 1 ? (left + right) / 2
    : left + (right - left) * index / (trends.length - 1)
  const y = (value: number) => bottom - Math.max(0, Math.min(100, value)) * (bottom - top) / 100
  const canvas: CanvasElement[] = [
    ...[0, 25, 50, 75, 100].map(value => ({
      type: 'line' as const, x1: left, y1: y(value), x2: right, y2: y(value),
      lineColor: line, lineWidth: 0.5,
    })),
  ]
  const series: {
    field: 'productivity_score' | 'compliance_score' | 'quality_score'
    color: string
    dash?: { length: number, space: number }
  }[] = [
    { field: 'productivity_score', color: cedar },
    { field: 'compliance_score', color: compliance, dash: { length: 6, space: 3 } },
    { field: 'quality_score', color: ink, dash: { length: 2, space: 3 } },
  ]
  for (const item of series) {
    for (let index = 0; index < trends.length; index++) {
      const value = trends[index]![item.field]
      if (value === null) continue
      if (index > 0) {
        const previous = trends[index - 1]![item.field]
        if (previous !== null) {
          canvas.push({
            type: 'line', x1: x(index - 1), y1: y(previous), x2: x(index), y2: y(value),
            lineColor: item.color, lineWidth: 1.8, dash: item.dash,
          })
        }
      }
      canvas.push({ type: 'ellipse', x: x(index), y: y(value), r1: 3.2, color: '#FFFFFF' })
      canvas.push({ type: 'ellipse', x: x(index), y: y(value), r1: 2.4, color: item.color })
    }
  }
  const dateIndexes = [...new Set([0, Math.round((trends.length - 1) / 5), Math.round(2 * (trends.length - 1) / 5), Math.round(3 * (trends.length - 1) / 5), Math.round(4 * (trends.length - 1) / 5), trends.length - 1])]

  return {
    unbreakable: true,
    stack: [
      { text: 'Weekly KPI trend', style: 'sectionTitle', margin: [0, 0, 0, 5] },
      { text: 'Scores across the selected employees. Gaps mean no score is available.', color: muted, fontSize: 8, margin: [0, 0, 0, 7] },
      {
        columns: [
          { text: 'Productivity · solid', color: cedar },
          { text: 'Compliance · dashed', color: compliance },
          { text: 'Quality · dotted', color: ink },
        ],
        fontSize: 8,
        margin: [0, 0, 0, 5],
      },
      {
        columns: [
          { width: 29, stack: [
            { text: '100%', margin: [0, 3, 0, 76] },
            { text: '50%', margin: [0, 0, 0, 76] },
            { text: '0%' },
          ], fontSize: 7, color: muted },
          { width: '*', canvas },
        ],
        columnGap: 4,
      },
      {
        columns: [
          { width: 33, text: '' },
          { width: '*', columns: dateIndexes.map((index, position) => ({
            width: '*', text: formatDate(trends[index]!.period_end),
            alignment: position === 0 ? 'left' : position === dateIndexes.length - 1 ? 'right' : 'center',
          })), columnGap: 0 },
        ],
        columnGap: 0,
        color: muted,
        fontSize: 7,
        margin: [0, 2, 0, 0],
      },
    ],
    margin: [0, 16, 0, 0],
  }
}

function kpiTrendTable(trends: KpiTrendPoint[], kpi: DashboardKpi): Content {
  if (!trends.length)
    return emptyState('No trend data is available for this period.')

  return dataTable(
    ['Week ending', 'Employees with evidence', `${kpiDetails[kpi].label} score`, 'Data confidence'],
    trends.map(point => [
      formatDate(point.period_end),
      String(point[`${kpi}_employee_count`]),
      optionalScore(point[`${kpi}_score`]),
      optionalScore(point.data_confidence),
    ]),
    ['*', 120, 110, 110],
  )
}

function dataTable(headers: string[], rows: string[][], widths: (string | number)[], sectionTitle?: string, startOnNewPage = false): Content {
  const titleRow: TableCell[] = sectionTitle
    ? [{ text: sectionTitle, style: 'sectionTitle', colSpan: headers.length }, ...Array.from({ length: headers.length - 1 }, () => ({}))]
    : []
  return {
    table: {
      headerRows: sectionTitle ? 2 : 1,
      dontBreakRows: true,
      widths,
      body: [
        ...(titleRow.length ? [titleRow] : []),
        headers.map<TableCell>(header => ({ text: header, bold: true, color: cedar })),
        ...rows,
      ],
    },
    layout: tableLayout(sectionTitle ? 1 : 0),
    fontSize: 7,
    margin: [0, sectionTitle ? 16 : 5, 0, 0],
    ...(startOnNewPage ? { pageBreak: 'before' as const } : {}),
  }
}

function metricCell(label: string, value: string, detail: string): Content {
  return {
    stack: [
      { text: label, color: muted, fontSize: 8 },
      { text: value, bold: true, fontSize: 15, margin: [0, 3, 0, 2] },
      { text: detail, color: muted, fontSize: 7 },
    ],
    margin: [9, 7, 9, 7],
  }
}

function emptyState(message: string): Content {
  return { text: message, color: muted, margin: [0, 6, 0, 0] }
}

function cardLayout() {
  return {
    fillColor: () => cedarLight,
    hLineColor: () => cedarLight,
    vLineColor: () => '#FFFFFF',
    vLineWidth: () => 4,
  }
}

function tableLayout(headerRow = 0) {
  return {
    fillColor: (rowIndex: number) => rowIndex === headerRow ? cedarLight : null,
    hLineColor: () => line,
    vLineColor: () => line,
    paddingLeft: () => 5,
    paddingRight: () => 5,
    paddingTop: () => 3,
    paddingBottom: () => 3,
  }
}

function score(value: number): string {
  return `${value.toFixed(1)}%`
}

function optionalScore(value: number | null): string {
  return value === null ? '-' : score(value)
}

function formatPeriod(analysis: DashboardResponse): string {
  const { start_date: start, end_date: end } = analysis.applied_filters
  return start && end ? `${formatDate(start)} - ${formatDate(end)}` : 'Full available period'
}

function reportFilename(analysis: DashboardResponse, report: string): string {
  const scope = (analysis.applied_filters.team || analysis.applied_filters.campaign || 'all-employees').replaceAll(/[^a-zA-Z0-9_-]/g, '-')
  const start = analysis.applied_filters.start_date || 'full'
  const end = analysis.applied_filters.end_date || 'period'
  return `cedar-${report}-${scope}-${start}-to-${end}.pdf`
}

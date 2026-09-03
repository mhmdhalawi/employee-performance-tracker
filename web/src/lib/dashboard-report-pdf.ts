import type { Content, TableCell, TDocumentDefinitions } from 'pdfmake/interfaces'
import type { DashboardResponse, EmployeeKpiResult, KpiTrendPoint } from '@/types/analysis'

export type DashboardKpi = 'productivity' | 'compliance' | 'quality'

const cedar = '#174C3C'
const cedarLight = '#E8F0ED'
const ink = '#17201D'
const muted = '#5F6D67'
const line = '#D8E1DD'

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
  downloadPdf(bytes, reportFilename(analysis, 'team-performance'))
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
  const team = analysis.applied_filters.team || 'All teams'
  const content: Content[] = [
    reportHeading('Team performance', team, analysis),
    {
      table: {
        widths: ['*', '*', '*', '*'],
        body: [[
          metricCell('Overall average', optionalScore(analysis.summary.average_overall_score), 'Scored employees only'),
          metricCell('Productivity', optionalScore(analysis.summary.average_productivity_score), '35% of overall'),
          metricCell('Compliance', optionalScore(analysis.summary.average_compliance_score), '30% of overall'),
          metricCell('Quality', optionalScore(analysis.summary.average_quality_score), '35% of overall'),
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
    { text: 'Employee results', style: 'sectionTitle' },
    employeeResultsTable(analysis.results),
    { text: 'Weekly KPI trend', style: 'sectionTitle', margin: [0, 16, 0, 4] },
    teamTrendTable(analysis.trends),
    managerNotice(),
  ]
  return baseDocument('TEAM PERFORMANCE REPORT', content)
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
          metricCell('Average score', optionalScore(average), `${analysis.summary.total_employee_count} employees`),
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
    managerNotice(),
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
      notice: { fillColor: cedarLight, color: ink, margin: [8, 7, 8, 7] },
    },
  }
}

function reportHeading(title: string, team: string, analysis: DashboardResponse): Content {
  return {
    stack: [
      { text: title, style: 'title' },
      { text: `${team} · ${formatPeriod(analysis)} · Current filtered dashboard`, color: muted },
    ],
    margin: [0, 0, 0, 12],
  }
}

function employeeResultsTable(results: EmployeeKpiResult[]): Content {
  if (!results.length)
    return emptyState('No employees match the current filters.')

  return dataTable(
    ['Employee', 'Team', 'Productivity', 'Compliance', 'Quality', 'Confidence', 'Overall', 'Status'],
    results.map(row => [
      `${row.employee_name || row.employee_id}\n${row.employee_id}`,
      row.team || 'Not provided',
      optionalScore(row.productivity_score),
      optionalScore(row.compliance_score),
      optionalScore(row.quality_score),
      score(row.data_confidence),
      row.overall_score === null ? 'Withheld' : score(row.overall_score),
      row.performance_tier || row.result_status,
    ]),
    ['*', 70, 57, 57, 57, 54, 54, 70],
  )
}

function kpiEmployeeTable(results: EmployeeKpiResult[], kpi: DashboardKpi): Content {
  if (!results.length)
    return emptyState('No employees match the current filters.')

  return dataTable(
    ['Employee', 'Team', `${kpiDetails[kpi].label} score`, 'Evidence confidence', 'Overall status'],
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
  if (!trends.length)
    return emptyState('No trend data is available for this period.')

  return dataTable(
    ['Week ending', 'Employees', 'Productivity', 'Compliance', 'Quality', 'Overall', 'Confidence'],
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
  )
}

function kpiTrendTable(trends: KpiTrendPoint[], kpi: DashboardKpi): Content {
  if (!trends.length)
    return emptyState('No trend data is available for this period.')

  return dataTable(
    ['Week ending', 'Employees with evidence', `${kpiDetails[kpi].label} score`, 'Evidence confidence'],
    trends.map(point => [
      formatDate(point.period_end),
      String(point[`${kpi}_employee_count`]),
      optionalScore(point[`${kpi}_score`]),
      optionalScore(point.data_confidence),
    ]),
    ['*', 120, 110, 110],
  )
}

function dataTable(headers: string[], rows: string[][], widths: (string | number)[]): Content {
  return {
    table: {
      headerRows: 1,
      dontBreakRows: true,
      widths,
      body: [
        headers.map<TableCell>(header => ({ text: header, bold: true, color: cedar })),
        ...rows,
      ],
    },
    layout: tableLayout(),
    fontSize: 7,
    margin: [0, 5, 0, 0],
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

function managerNotice(): Content {
  return {
    text: 'This report supports coaching and manager review. It must not be used alone for hiring, termination, promotion, compensation, or disciplinary decisions.',
    style: 'notice',
    margin: [0, 16, 0, 0],
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

function tableLayout() {
  return {
    fillColor: (rowIndex: number) => rowIndex === 0 ? cedarLight : null,
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

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeZone: 'UTC' })
    .format(new Date(`${value}T00:00:00Z`))
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeStyle: 'short' })
    .format(new Date(value))
}

function reportFilename(analysis: DashboardResponse, report: string): string {
  const team = (analysis.applied_filters.team || 'all-teams').replaceAll(/[^a-zA-Z0-9_-]/g, '-')
  const start = analysis.applied_filters.start_date || 'full'
  const end = analysis.applied_filters.end_date || 'period'
  return `cedar-${report}-${team}-${start}-to-${end}.pdf`
}

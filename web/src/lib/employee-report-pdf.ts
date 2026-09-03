import type { Content, ContentColumns, TDocumentDefinitions } from 'pdfmake/interfaces'
import type { EmployeeReportData, ReportFinding } from '@/types/reports'

const cedar = '#078181'
const cedarLight = '#E7F3F3'
const ink = '#0D0D0D'
const muted = '#555B59'
const line = '#D8DDDC'

export async function downloadEmployeeReportPdf(report: EmployeeReportData): Promise<void> {
  const bytes = await createEmployeeReportPdfBytes(report)
  const blob = new Blob([new Uint8Array(bytes)], { type: 'application/pdf' })
  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = reportFilename(report)
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0)
}

export async function createEmployeeReportPdfBytes(report: EmployeeReportData): Promise<Uint8Array> {
  const [{ default: pdfMake }, { default: pdfFonts }] = await Promise.all([
    import('pdfmake/build/pdfmake'),
    import('pdfmake/build/vfs_fonts'),
  ])
  pdfMake.addVirtualFileSystem(pdfFonts)
  return pdfMake.createPdf(documentDefinition(report)).getBuffer()
}

function documentDefinition(report: EmployeeReportData): TDocumentDefinitions {
  const employeeName = report.employee_name || report.employee_id
  const period = `${formatDate(report.period.start_date)} - ${formatDate(report.period.end_date)}`
  const overall = report.overall_score === null ? 'Withheld' : score(report.overall_score)
  const status = report.performance_tier || report.result_status
  const kpiExplanations = report.kpis.map<Content>(kpi => ({
    stack: [
      { text: `${kpi.name} - ${score(kpi.score)}`, bold: true },
      { text: kpi.explanation, color: muted, margin: [0, 2, 0, 8] },
    ],
  }))
  const findingBlocks = report.findings.length
    ? report.findings.map<Content>(findingBlock)
    : [{
        text: 'No validated findings for this employee and reporting period.',
        color: muted,
        margin: [0, 2, 0, 10] as [number, number, number, number],
      }]

  return {
    pageSize: 'A4',
    pageMargins: [42, 56, 42, 48],
    defaultStyle: { font: 'Roboto', fontSize: 9, color: ink, lineHeight: 1.18 },
    header: (_currentPage: number) => ({
      margin: [42, 22, 42, 0],
      columns: [
        { text: 'CEDAR', bold: true, color: cedar, fontSize: 15, characterSpacing: 1.2 },
        { text: 'EMPLOYEE PERFORMANCE REPORT', alignment: 'right', color: muted, fontSize: 8 },
      ],
    }),
    footer: (currentPage: number, pageCount: number) => ({
      margin: [42, 12, 42, 0],
      columns: [
        { text: `Generated ${formatDateTime(report.generated_at)}`, color: muted, fontSize: 7 },
        { text: `${currentPage} / ${pageCount}`, alignment: 'right', color: muted, fontSize: 7 },
      ],
    }),
    content: [
      { text: employeeName, style: 'title' },
      { text: `${report.employee_id}  |  ${report.team || 'Team not provided'}${report.role ? `  |  ${report.role}` : ''}`, color: muted },
      { text: period, margin: [0, 4, 0, 18], color: muted },
      {
        table: {
          widths: ['*', '*', '*'],
          body: [[
            metricCell('Overall result', overall, status),
            metricCell('Evidence confidence', score(report.data_confidence), `Required: ${score(report.confidence_threshold)}`),
            metricCell('Change vs prior period', change(report.overall_score_change), priorPeriodLabel(report)),
          ]],
        },
        layout: cardLayout(),
      },
      report.overall_score === null
        ? {
            text: 'Overall performance and tier are withheld because evidence confidence is below the required threshold. Component KPI values are shown for auditability only.',
            style: 'notice',
            margin: [0, 14, 0, 14],
          }
        : { text: '', margin: [0, 6] },
      { text: 'KPI overview', style: 'sectionTitle' },
      {
        columns: report.kpis.map(kpi => ({
          width: '*',
          stack: [
            { text: kpi.name, bold: true, color: cedar },
            { text: score(kpi.score), fontSize: 19, bold: true, margin: [0, 5, 0, 3] },
            { text: `${kpi.weight}% of overall`, color: muted, fontSize: 8 },
          ],
          margin: [10, 10, 10, 10],
        })) as ContentColumns['columns'],
        columnGap: 8,
        margin: [0, 6, 0, 16],
      },
      { text: 'Evidence confidence', style: 'sectionTitle' },
      { text: report.confidence_explanation, margin: [0, 5, 0, 14] },
      { text: 'Weekly trend', style: 'sectionTitle' },
      trendTable(report),
      { text: 'Evidence and action', style: 'title', pageBreak: 'before' },
      { text: 'Deterministic KPI explanations', style: 'sectionTitle', margin: [0, 12, 0, 5] },
      ...kpiExplanations,
      { text: 'Validated findings', style: 'sectionTitle', margin: [0, 8, 0, 5] },
      ...findingBlocks,
      { text: 'Supporting records', style: 'sectionTitle', margin: [0, 8, 0, 4] },
      {
        text: report.supporting_record_ids.length
          ? report.supporting_record_ids.join(', ')
          : 'No supporting record IDs are available.',
        color: muted,
        fontSize: 8,
      },
      { text: 'Metric definitions', style: 'sectionTitle', margin: [0, 12, 0, 4] },
      { ul: report.metric_definitions, color: muted, fontSize: 8 },
      { text: report.manager_review_notice, style: 'notice', margin: [0, 12, 0, 0] },
    ],
    styles: {
      title: { fontSize: 22, bold: true, color: cedar, margin: [0, 0, 0, 4] },
      sectionTitle: { fontSize: 12, bold: true, color: cedar },
      notice: { fillColor: cedarLight, color: ink, margin: [9, 8, 9, 8] },
    },
  }
}

function metricCell(label: string, value: string, detail: string): Content {
  return {
    stack: [
      { text: label, color: muted, fontSize: 8 },
      { text: value, bold: true, fontSize: 17, margin: [0, 5, 0, 3] },
      { text: detail, color: muted, fontSize: 8 },
    ],
    margin: [10, 9, 10, 9],
  }
}

function trendTable(report: EmployeeReportData): Content {
  if (!report.trends.length)
    return { text: 'No trend data is available for this period.', color: muted, margin: [0, 5, 0, 0] }

  return {
    table: {
      headerRows: 1,
      widths: ['*', 'auto', 'auto', 'auto', 'auto'],
      body: [
        ['Week ending', 'Productivity', 'Compliance', 'Quality', 'Confidence'],
        ...report.trends.map(point => [
          formatDate(point.period_end),
          optionalScore(point.productivity_score),
          optionalScore(point.compliance_score),
          optionalScore(point.quality_score),
          optionalScore(point.data_confidence),
        ]),
      ],
    },
    layout: {
      fillColor: (rowIndex: number) => rowIndex === 0 ? cedarLight : null,
      hLineColor: () => line,
      vLineColor: () => line,
      paddingLeft: () => 5,
      paddingRight: () => 5,
      paddingTop: () => 4,
      paddingBottom: () => 4,
    },
    fontSize: 7,
    margin: [0, 5, 0, 0],
  }
}

function findingBlock(finding: ReportFinding): Content {
  const stack: Content[] = [
    { text: `${finding.code.replaceAll('_', ' ')} - ${impactLabel(finding.scoring_impact)}`, bold: true },
    { text: finding.message, color: muted, margin: [0, 2, 0, 1] },
    { text: `Records: ${finding.record_ids.join(', ') || 'None'}`, color: muted, fontSize: 7 },
    ...finding.evidence_links.map<Content>(link => ({
      text: link,
      link,
      color: cedar,
      decoration: 'underline',
      fontSize: 7,
    })),
  ]
  return {
    stack,
    margin: [0, 2, 0, 7],
  }
}

function cardLayout() {
  return {
    fillColor: () => cedarLight,
    hLineColor: () => cedarLight,
    vLineColor: () => '#FFFFFF',
    vLineWidth: () => 4,
  }
}

function score(value: number): string {
  return `${value.toFixed(1)}%`
}

function optionalScore(value: number | null): string {
  return value === null ? '-' : score(value)
}

function change(value: number | null): string {
  if (value === null)
    return 'Unavailable'
  return `${value > 0 ? '+' : ''}${value.toFixed(1)} pts`
}

function priorPeriodLabel(report: EmployeeReportData): string {
  const { prior_start_date: start, prior_end_date: end } = report.period
  return start && end ? `${formatDate(start)} - ${formatDate(end)}` : 'No comparable period'
}

function impactLabel(value: string): string {
  return value.replaceAll('_', ' ')
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeZone: 'UTC' })
    .format(new Date(`${value}T00:00:00Z`))
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeStyle: 'short' })
    .format(new Date(value))
}

function reportFilename(report: EmployeeReportData): string {
  const employeeId = report.employee_id.replaceAll(/[^a-zA-Z0-9_-]/g, '-')
  return `cedar-employee-performance-${employeeId}-${report.period.start_date}-to-${report.period.end_date}.pdf`
}

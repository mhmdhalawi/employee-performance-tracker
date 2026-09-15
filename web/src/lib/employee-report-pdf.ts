import type { CanvasElement, Content, ContentColumns, TableCell, TDocumentDefinitions } from 'pdfmake/interfaces'
import type { EmployeeReportData, ReportFinding } from '@/types/reports'
import type { KpiTrendPoint } from '@/types/analysis'
import type { EmployeeEvidenceRow, EvidenceKpi } from '@/types/employee-evidence'
import { needsAttention } from '@/lib/employee-presentation'
import { evidenceCells, evidenceDetails, evidenceImpact, evidenceDescriptions, evidenceLabels, evidenceLink } from '@/lib/employee-evidence'

const cedar = '#078181'
const cedarLight = '#E7F3F3'
const ink = '#0D0D0D'
const muted = '#555B59'
const line = '#D8DDDC'
const compliance = '#C18426'

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
  const scorePeriod = report.period.score_period_start_date && report.period.score_period_end_date
    && (report.period.score_period_start_date !== report.period.start_date || report.period.score_period_end_date !== report.period.end_date)
    ? `Scores use available evidence: ${formatDate(report.period.score_period_start_date)} - ${formatDate(report.period.score_period_end_date)}.`
    : ''
  const overall = report.overall_score === null ? 'Withheld' : score(report.overall_score)
  const status = report.performance_tier || report.result_status
  const attention = needsAttention(report.findings)
  const attentionBlocks: Content[] = attention.length
    ? [{ text: 'Needs attention', style: 'sectionTitle', margin: [0, 12, 0, 5] }, ...attention.map(findingBlock)]
    : []

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
        { text: `Generated ${formatDateTime(report.generated_at)} | ${report.employee_id}`, color: muted, fontSize: 7 },
        { text: `${currentPage} / ${pageCount}`, alignment: 'right', color: muted, fontSize: 7 },
      ],
    }),
    content: [
      { text: employeeName, style: 'title' },
      { text: `${report.employee_id}  |  ${report.team || 'Team not provided'}${report.role ? `  |  ${report.role}` : ''}`, color: muted },
      { text: period, margin: [0, 4, 0, scorePeriod ? 3 : 18], color: muted },
      ...(scorePeriod ? [{ text: scorePeriod, margin: [0, 0, 0, 14], color: muted } as Content] : []),
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
      ...attentionBlocks,
      trendChart(report.trends),
      trendTable(report),
      { text: report.manager_review_notice, style: 'notice', margin: [0, 12, 0, 0] },
      { text: 'Employee performance records', style: 'title', pageBreak: 'before' },
      { text: 'All selected-period records are included. Excluded records are labeled for auditability; source statuses do not replace calculated results.', color: muted, margin: [0, 4, 0, 12] },
      ...(['productivity', 'compliance', 'quality'] as EvidenceKpi[]).flatMap(kpi => evidenceSection(report, kpi)),
    ],
    styles: {
      title: { fontSize: 22, bold: true, color: cedar, margin: [0, 0, 0, 4] },
      sectionTitle: { fontSize: 12, bold: true, color: cedar },
      notice: { fillColor: cedarLight, color: ink, margin: [9, 8, 9, 8] },
    },
  }
}

function wrapLongWords(value: string): string {
  return value.replace(/\S{24,}/g, word => word.replace(/(.{18})/g, '$1\u200b'))
}

function evidenceNotes(row: EmployeeEvidenceRow): Content {
  const stack: Content[] = []
  if (row.excluded_from_scoring)
    stack.push({ text: wrapLongWords(`Excluded from scoring: ${row.exclusion_reason}`), bold: true })
  for (const finding of row.validation_findings) {
    stack.push({ text: wrapLongWords(`${evidenceImpact(finding.scoring_impact)}: ${finding.message} Records: ${finding.record_ids.join(', ')}`), margin: [0, 3, 0, 0] })
  }
  const link = evidenceLink(row)
  if (link) {
    stack.push({ text: 'Open evidence', link, color: cedar, decoration: 'underline', margin: [0, 3, 0, 0] })
    stack.push({ text: wrapLongWords(link), color: muted, fontSize: 7 })
  }
  return { stack: stack.length ? stack : [{ text: 'No additional findings.', color: muted }] }
}

function evidenceSection(report: EmployeeReportData, kpi: EvidenceKpi): Content[] {
  const section = report.evidence_tables[kpi]
  const metric = report.kpis.find(item => item.name === evidenceLabels[kpi])!
  const title: Content = {
    unbreakable: true,
    stack: [
      { text: `${evidenceLabels[kpi]} evidence - ${score(metric.score)} | ${metric.weight}% of overall`, style: 'sectionTitle' },
      { text: `${section.total_count} records | ${evidenceDescriptions[kpi]}`, color: muted, fontSize: 8, margin: [0, 4, 0, 6] },
    ],
    margin: [0, 12, 0, 0],
  }
  if (!section.rows.length)
    return [title, { text: `No ${evidenceLabels[kpi].toLowerCase()} evidence records for this reporting period.`, color: muted, margin: [0, 4, 0, 12] }]

  const headers = kpi === 'productivity'
    ? ['Work record', 'Assigned / due / completed', 'Source status', 'Actual hours', 'Verification / evidence / notes']
    : kpi === 'compliance'
      ? ['Type / record ID', 'Date / period', 'Source outcome', 'Record details', 'Findings / exclusion notes']
      : ['Review / work IDs', 'Review date', 'Accuracy / first pass', 'Rework hours', 'Verification / notes']
  const body: TableCell[][] = [
    [{ colSpan: 5, stack: [
      { text: `${evidenceLabels[kpi]} evidence - ${score(metric.score)} | ${metric.weight}% of overall`, style: 'sectionTitle' },
      { text: `${section.total_count} records | ${evidenceDescriptions[kpi]}`, color: muted, fontSize: 8, margin: [0, 4, 0, 2] },
    ] }, {}, {}, {}, {}],
    headers.map(text => ({ text, bold: true, color: ink })),
  ]
  for (const row of section.rows) {
    const cells = evidenceCells(row)
    let values: (string | Content)[]
    if (row.record_type === 'work_output') {
      values = [row.record_id, `Assigned: ${formatDate(row.record.assigned_date)}\nDue: ${formatDate(row.record.due_date)}\nCompleted: ${cells[2]}`,
        cells[3]!, cells[4]!, { stack: [{ text: wrapLongWords(row.record.verification_status) }, evidenceNotes(row)] }]
    }
    else if (row.record_type === 'quality') {
      values = [`${row.record_id}\nWork: ${row.record.related_output_id}`, cells[2]!, `${cells[3]}\n${cells[4]}`, cells[5]!,
        { stack: [{ text: wrapLongWords(row.record.verification_status) }, evidenceNotes(row)] }]
    }
    else {
      const details = evidenceDetails(row).filter(([label]) => !['Type', 'Date / period', 'Record ID', 'Source outcome'].includes(label))
      values = [`${cells[0]}\n${row.record_id}`, cells[1]!, cells[3]!, details.map(([label, value]) => `${label}: ${value}`).join('\n'), evidenceNotes(row)]
    }
    body.push(values.map(value => typeof value === 'string' ? { text: wrapLongWords(value) } : value))
  }
  const ordinaryRows = section.rows.every(row => JSON.stringify(row).length < 2000)
  return [{
    table: {
      // Repeating the section title with its columns also keeps it with the first record.
      headerRows: 2, keepWithHeaderRows: ordinaryRows ? 1 : 0,
      // Ordinary records stay intact; unusually long source text/notes may flow across pages.
      dontBreakRows: ordinaryRows,
      widths: kpi === 'productivity' ? [70, 100, 65, 45, '*']
        : kpi === 'compliance' ? [80, 65, 55, 170, '*'] : [95, 70, 95, 45, '*'],
      body,
    },
    layout: {
      fillColor: (rowIndex: number) => rowIndex === 1 ? cedarLight : null,
      hLineColor: () => line, vLineColor: () => line,
      paddingLeft: () => 5, paddingRight: () => 5, paddingTop: () => 6, paddingBottom: () => 6,
    },
    fontSize: 8,
    margin: [0, 0, 0, 12],
  }]
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
      paddingTop: () => 2,
      paddingBottom: () => 2,
    },
    fontSize: 7,
    margin: [0, 5, 0, 0],
  }
}

function trendChart(trends: KpiTrendPoint[]): Content {
  if (!trends.length)
    return { text: 'Weekly KPI trend', style: 'sectionTitle' }

  const left = 8
  const right = 450
  const top = 8
  const bottom = 98
  const x = (index: number) => trends.length === 1 ? (left + right) / 2
    : left + (right - left) * index / (trends.length - 1)
  const y = (value: number) => bottom - Math.max(0, Math.min(100, value)) * (bottom - top) / 100
  const canvas: CanvasElement[] = [
    ...[top, (top + bottom) / 2, bottom].map(position => ({
      type: 'line' as const, x1: left, y1: position, x2: right, y2: position,
      lineColor: line, lineWidth: 0.5,
    })),
  ]
  const series: { field: 'productivity_score' | 'compliance_score' | 'quality_score', color: string, dash?: { length: number, space: number } }[] = [
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
      canvas.push({ type: 'ellipse', x: x(index), y: y(value), r1: 1.7, color: item.color })
    }
  }

  return {
    unbreakable: true,
    stack: [
      { text: 'Weekly KPI trend', style: 'sectionTitle', margin: [0, 0, 0, 5] },
      { text: 'Employee scores by week. Gaps mean no score is available.', color: muted, fontSize: 8, margin: [0, 0, 0, 5] },
      {
        columns: [
          { text: 'Productivity · solid', color: cedar },
          { text: 'Compliance · dashed', color: muted },
          { text: 'Quality · dotted', color: ink },
        ],
        fontSize: 8,
        margin: [0, 0, 0, 5],
      },
      {
        columns: [
          { width: 27, stack: [
            { text: '100%', margin: [0, 4, 0, 37] },
            { text: '50%', margin: [0, 0, 0, 37] },
            { text: '0%' },
          ], fontSize: 7, color: muted },
          { width: '*', canvas },
        ],
      },
      {
        columns: [
          { text: formatDate(trends[0]!.period_end) },
          { text: formatDate(trends[trends.length - 1]!.period_end), alignment: 'right' },
        ],
        color: muted,
        fontSize: 7,
        margin: [27, 1, 0, 7],
      },
    ],
  }
}

function findingBlock(finding: ReportFinding): Content {
  const stack: Content[] = [
    { text: `${finding.code.replaceAll('_', ' ')} - ${finding.occurrence_count} occurrences`, bold: true },
    { text: wrapLongWords(finding.message), color: muted, margin: [0, 2, 0, 1] },
    { text: wrapLongWords(`Records: ${finding.record_ids.join(', ') || 'None'}`), color: muted, fontSize: 7 },
    ...finding.evidence_links.map<Content>(link => ({
      text: wrapLongWords(link),
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

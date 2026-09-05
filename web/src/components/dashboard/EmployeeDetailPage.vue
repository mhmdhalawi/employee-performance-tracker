<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  CalendarDaysIcon,
  CircleAlertIcon,
  Clock3Icon,
  DatabaseIcon,
  DownloadIcon,
  FileTextIcon,
  FileSpreadsheetIcon,
  LightbulbIcon,
  MinusIcon,
  ShieldCheckIcon,
  SparklesIcon,
  TrendingDownIcon,
  TrendingUpIcon,
  TriangleAlertIcon,
} from '@lucide/vue'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import ReportPreviewContent from '@/components/dashboard/ReportPreviewContent.vue'
import PerformanceHeader from '@/components/dashboard/PerformanceHeader.vue'
import { Progress } from '@/components/ui/progress'
import { Separator } from '@/components/ui/separator'
import { Spinner } from '@/components/ui/spinner'
import { downloadEmployeeReportPdf } from '@/lib/employee-report-pdf'
import type { AnalysisFilters, EmployeeAIInsight, EmployeeKpiResult, ErrorPayload, PerformanceAlert } from '@/types/analysis'
import type { EmployeeReportData, EmployeeReportPreviewResponse, EmployeeReportRequest } from '@/types/reports'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

const props = defineProps<{
  employee: EmployeeKpiResult
  alerts: PerformanceAlert[]
  insight: EmployeeAIInsight | null
  insightLoading: boolean
  insightError?: string
  reportingPeriod: AnalysisFilters
}>()
const emit = defineEmits<{
  back: []
  generateInsight: [employeeId: string]
}>()

const reportPreviewOpen = ref(false)
const reportPreview = ref<EmployeeReportData | null>(null)
const reportLoading = ref(false)
const reportDownloading = ref(false)
const reportError = ref('')

const complianceBreakdown = computed(() => {
  const match = props.employee.compliance_reason.match(
    /attendance \(([^:]+): arrival ([^,]+), shift end ([^,]+), lunch ([^)]+)\), 35% reporting \(([^)]+)\), and 15% leave compliance \(([^)]+)\)/,
  )
  if (!match)
    return null

  return {
    attendance: match[1],
    arrival: match[2],
    shiftEnd: match[3],
    lunch: match[4],
    reporting: match[5],
    leave: match[6],
  }
})

const kpiCards = computed(() => [
  {
    label: 'Productivity',
    score: props.employee.productivity_score,
    reason: props.employee.productivity_reason,
    weight: '35% of overall',
  },
  {
    label: 'Compliance',
    score: props.employee.compliance_score,
    reason: props.employee.compliance_reason,
    weight: '30% of overall',
  },
  {
    label: 'Quality',
    score: props.employee.quality_score,
    reason: props.employee.quality_reason,
    weight: '35% of overall',
  },
])

function score(value: number | null): string {
  return value === null ? '—' : `${value.toFixed(1)}%`
}

function alertCodeLabel(code: string): string {
  return code.replaceAll('_', ' ')
}

function impactLabel(impact: string): string {
  const labels: Record<string, string> = {
    lowers_confidence: 'Lowers confidence',
    affects_score: 'Affects score',
    excluded_from_scoring: 'Excluded from scoring',
    blocks_score: 'Blocks score',
    none: 'No scoring impact',
  }
  return labels[impact] ?? alertCodeLabel(impact)
}

function impactVariant(impact: string): 'destructive' | 'outline' | 'secondary' | 'warning' {
  if (impact === 'blocks_score')
    return 'destructive'
  if (impact === 'lowers_confidence')
    return 'warning'
  if (impact === 'affects_score')
    return 'secondary'
  return 'outline'
}

function reportRequest(): EmployeeReportRequest | null {
  if (!props.reportingPeriod.start_date || !props.reportingPeriod.end_date)
    return null
  return {
    employee_id: props.employee.employee_id,
    start_date: props.reportingPeriod.start_date,
    end_date: props.reportingPeriod.end_date,
  }
}

async function generateReportPreview(): Promise<void> {
  reportPreviewOpen.value = true
  reportLoading.value = true
  reportError.value = ''
  reportPreview.value = null
  const request = reportRequest()
  if (!request) {
    reportError.value = 'The dashboard has no resolved reporting period for this employee.'
    reportLoading.value = false
    return
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/reports/employee/preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    })
    if (!response.ok) {
      const payload = await response.json() as ErrorPayload
      throw new Error(payload.error?.message ?? 'The report preview could not be generated.')
    }
    const payload = await response.json() as EmployeeReportPreviewResponse
    reportPreview.value = payload.report
  }
  catch (error) {
    reportError.value = error instanceof TypeError
      ? 'The report service is temporarily unavailable. Please try again shortly.'
      : error instanceof Error ? error.message : 'The report preview could not be generated.'
  }
  finally {
    reportLoading.value = false
  }
}

async function downloadReport(): Promise<void> {
  if (!reportPreview.value || reportDownloading.value)
    return
  reportDownloading.value = true
  reportError.value = ''
  try {
    await downloadEmployeeReportPdf(reportPreview.value)
  }
  catch {
    reportError.value = 'The PDF could not be created in this browser.'
  }
  finally {
    reportDownloading.value = false
  }
}

function formatReportDate(value: string): string {
  return new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeZone: 'UTC' })
    .format(new Date(`${value}T00:00:00Z`))
}

function scoreChange(value: number | null): string {
  if (value === null)
    return 'Earlier-period data is unavailable'
  return `${value > 0 ? '+' : ''}${value.toFixed(1)} pts`
}
</script>

<template>
  <main class="min-h-svh bg-muted/30">
    <PerformanceHeader back @back="emit('back')">
          <Button :disabled="reportLoading" @click="generateReportPreview">
            <Spinner v-if="reportLoading" data-icon="inline-start" />
            <FileTextIcon v-else data-icon="inline-start" />
            Generate report
          </Button>
          <Badge :variant="employee.overall_score === null ? 'warning' : 'success'">
            {{ employee.performance_tier ?? employee.result_status }}
          </Badge>
    </PerformanceHeader>

    <div class="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8">
      <header class="flex flex-col gap-2">
        <p class="text-sm font-medium text-muted-foreground">Employee performance details</p>
        <h1 class="text-3xl font-semibold tracking-tight">
          {{ employee.employee_name || employee.employee_id }}
        </h1>
        <p class="text-sm text-muted-foreground">
          {{ employee.employee_id }} · {{ employee.team ?? 'Team not provided' }}<template v-if="employee.role"> · {{ employee.role }}</template>
        </p>
      </header>

      <p v-if="reportingPeriod.start_date && reportingPeriod.end_date" class="text-sm text-muted-foreground">Reporting period: {{ formatReportDate(reportingPeriod.start_date) }} – {{ formatReportDate(reportingPeriod.end_date) }}</p>

      <Card>
        <CardHeader class="gap-4 sm:flex sm:flex-row sm:items-center sm:justify-between">
          <div class="flex flex-col gap-1">
            <CardDescription>Overall score</CardDescription>
            <CardTitle class="text-4xl tabular-nums">{{ score(employee.overall_score) }}</CardTitle>
          </div>
          <div class="flex w-full max-w-md flex-col gap-2">
            <div class="flex items-center justify-between gap-3 text-sm">
              <span class="text-muted-foreground">Evidence confidence</span>
              <span class="font-medium tabular-nums">{{ employee.data_confidence.toFixed(1) }}%</span>
            </div>
            <Progress :model-value="employee.data_confidence" :tone="employee.overall_score === null ? 'warning' : 'default'" aria-label="Evidence confidence" />
            <p class="text-xs text-muted-foreground">
              Required threshold: {{ employee.confidence_threshold.toFixed(1) }}%
            </p>
          </div>
        </CardHeader>
      </Card>

      <Alert v-if="employee.overall_score === null" variant="warning">
        <TriangleAlertIcon aria-hidden="true" />
        <AlertTitle>Insufficient evidence for an overall result</AlertTitle>
        <AlertDescription>
          Overall performance and tier were withheld because evidence confidence is below the
          required threshold. Component KPI values remain visible for auditability and should
          not be treated as a complete performance assessment.
        </AlertDescription>
      </Alert>

      <section aria-label="KPI scores" class="grid gap-4 md:grid-cols-3">
        <Card v-for="item in kpiCards" :key="item.label">
          <CardHeader>
            <CardDescription>{{ item.label }} · {{ item.weight }}</CardDescription>
            <CardTitle class="text-3xl tabular-nums">{{ score(item.score) }}</CardTitle>
          </CardHeader>
          <CardContent class="text-sm text-muted-foreground">{{ item.reason }}</CardContent>
        </Card>
      </section>

      <div class="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(22rem,0.9fr)]">
        <div class="grid min-w-0 content-start gap-6">
          <Card class="lg:min-h-44">
            <CardHeader>
              <CardTitle class="flex items-center gap-2">
                <FileSpreadsheetIcon aria-hidden="true" />
                Evidence confidence
              </CardTitle>
              <CardDescription>
                Confidence is the lowest coverage across the required evidence sources.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p class="text-sm leading-6 text-muted-foreground">{{ employee.confidence_reason }}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle class="flex items-center gap-2">
                <Clock3Icon aria-hidden="true" />
                Compliance calculation
              </CardTitle>
              <CardDescription>Attendance, reporting, and leave evidence used in the score.</CardDescription>
            </CardHeader>
            <CardContent class="flex min-w-0 flex-col gap-4">
              <template v-if="complianceBreakdown">
                <section class="flex flex-col gap-3">
                  <div class="flex items-center justify-between gap-3">
                    <div class="flex min-w-0 items-center gap-2">
                      <span class="font-medium">Attendance</span>
                      <Badge variant="secondary">50%</Badge>
                    </div>
                    <strong class="shrink-0 text-lg tabular-nums">{{ complianceBreakdown.attendance }}%</strong>
                  </div>
                  <dl class="grid grid-cols-3 gap-3 text-sm text-muted-foreground">
                    <div class="flex flex-col gap-0.5"><dt>Arrival</dt><dd class="font-medium tabular-nums text-foreground">{{ complianceBreakdown.arrival }}%</dd></div>
                    <div class="flex flex-col gap-0.5"><dt>Shift end</dt><dd class="font-medium tabular-nums text-foreground">{{ complianceBreakdown.shiftEnd }}%</dd></div>
                    <div class="flex flex-col gap-0.5"><dt>Lunch</dt><dd class="font-medium tabular-nums text-foreground">{{ complianceBreakdown.lunch }}%</dd></div>
                  </dl>
                  <p class="text-sm text-muted-foreground">Actual arrival and shift end are compared with the schedule; lunch requires a valid check-out and return.</p>
                </section>

                <Separator />

                <section class="flex flex-col gap-1">
                  <div class="flex items-center justify-between gap-3">
                    <div class="flex min-w-0 items-center gap-2"><span class="font-medium">Reporting</span><Badge variant="secondary">35%</Badge></div>
                    <strong class="shrink-0 text-lg tabular-nums">{{ complianceBreakdown.reporting }}%</strong>
                  </div>
                  <p class="text-sm text-muted-foreground">Submitted date is compared with the due date.</p>
                </section>

                <Separator />

                <section class="flex flex-col gap-1">
                  <div class="flex items-center justify-between gap-3">
                    <div class="flex min-w-0 items-center gap-2"><span class="font-medium">Leave</span><Badge variant="secondary">15%</Badge></div>
                    <strong class="shrink-0 text-lg tabular-nums">{{ complianceBreakdown.leave }}%</strong>
                  </div>
                  <p class="text-sm text-muted-foreground">Approved annual leave and holidays are neutral; sick leave requires complete documentation.</p>
                </section>
              </template>
              <p v-else class="text-sm text-muted-foreground">{{ employee.compliance_reason }}</p>
              <p class="text-sm font-medium">Missing required evidence lowers confidence—it never becomes zero performance.</p>
            </CardContent>
          </Card>
        </div>

        <div class="grid min-w-0 content-start gap-6">
          <Card class="lg:min-h-44">
            <CardHeader>
              <CardTitle>AI guidance</CardTitle>
              <CardDescription>Generated on demand from this employee’s validated findings.</CardDescription>
            </CardHeader>
            <CardContent class="flex flex-col gap-4">
              <Button
                v-if="alerts.length && !insight"
                class="w-full sm:w-fit"
                :disabled="insightLoading"
                @click="emit('generateInsight', employee.employee_id)"
              >
                <Spinner v-if="insightLoading" data-icon="inline-start" />
                <SparklesIcon v-else data-icon="inline-start" />
                {{ insightLoading ? 'Generating guidance…' : 'Generate AI guidance' }}
              </Button>
              <Alert v-if="insightError" variant="destructive">
                <CircleAlertIcon aria-hidden="true" />
                <AlertTitle>AI guidance could not be generated</AlertTitle>
                <AlertDescription>{{ insightError }}</AlertDescription>
              </Alert>
              <Alert v-if="insight">
                <LightbulbIcon aria-hidden="true" />
                <AlertTitle>Explanation</AlertTitle>
                <AlertDescription class="flex flex-col gap-4">
                  <div class="flex flex-col gap-2">
                    <p>{{ insight.explanation.message }}</p>
                    <div class="flex flex-wrap gap-1">
                      <Badge v-for="recordId in insight.explanation.record_ids" :key="recordId" variant="secondary">{{ recordId }}</Badge>
                    </div>
                  </div>
                  <div>
                    <p class="font-medium text-foreground">Recommended next steps</p>
                    <ul class="mt-1 flex list-disc flex-col gap-2 pl-5">
                      <li v-for="recommendation in insight.recommendations" :key="recommendation.message">
                        {{ recommendation.message }}
                        <span class="mt-1 flex flex-wrap gap-1">
                          <Badge v-for="recordId in recommendation.record_ids" :key="recordId" variant="outline">{{ recordId }}</Badge>
                        </span>
                      </li>
                    </ul>
                  </div>
                </AlertDescription>
              </Alert>
              <p v-if="!alerts.length" class="text-sm text-muted-foreground">AI guidance is available only when validated findings exist.</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Findings</CardTitle>
              <CardDescription>Validated findings and their supporting evidence.</CardDescription>
              <CardAction><Badge variant="secondary">{{ alerts.length }}</Badge></CardAction>
            </CardHeader>
            <CardContent class="flex flex-col gap-3">
              <Alert v-for="alert in alerts" :key="alert.code" :variant="alert.severity === 'info' ? 'default' : 'warning'">
                <TriangleAlertIcon v-if="alert.severity !== 'info'" aria-hidden="true" />
                <FileSpreadsheetIcon v-else aria-hidden="true" />
                <AlertTitle class="capitalize">
                  {{ alertCodeLabel(alert.code) }}
                  <Badge variant="outline">{{ alert.occurrence_count }} occurrences</Badge>
                </AlertTitle>
                <AlertDescription class="flex flex-col gap-2 [&_p]:mb-0">
                  <Badge :variant="impactVariant(alert.scoring_impact)">{{ impactLabel(alert.scoring_impact) }}</Badge>
                  <p>{{ alert.message }}</p>
                  <details v-if="alert.record_ids.length">
                    <summary class="cursor-pointer text-xs font-medium text-foreground">Supporting records ({{ alert.record_ids.length }})</summary>
                    <div class="mt-2 flex flex-wrap gap-1">
                      <Badge v-for="recordId in alert.record_ids" :key="recordId" variant="secondary">{{ recordId }}</Badge>
                    </div>
                  </details>
                  <a v-if="alert.evidence_links[0]" class="text-primary underline-offset-4 hover:underline" :href="alert.evidence_links[0]" target="_blank" rel="noreferrer">Open evidence</a>
                </AlertDescription>
              </Alert>
              <p v-if="!alerts.length" class="py-8 text-center text-sm text-muted-foreground">No findings for this employee.</p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>

    <Dialog v-model:open="reportPreviewOpen">
      <ReportPreviewContent>
      <template #header>
        <DialogHeader class="px-6 pt-6 pb-5">
          <div class="flex items-center gap-3">
            <div class="flex size-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <FileTextIcon aria-hidden="true" />
            </div>
            <div class="flex flex-col gap-1">
              <DialogTitle>Employee performance report</DialogTitle>
              <DialogDescription>
                Review the report snapshot before creating the PDF in your browser.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>
      </template>


          <div v-if="reportLoading" class="flex min-h-64 items-center justify-center gap-3 text-sm text-muted-foreground">
            <Spinner />
            Preparing report preview…
          </div>

          <Alert v-else-if="reportError" variant="destructive">
            <CircleAlertIcon aria-hidden="true" />
            <AlertTitle>Report unavailable</AlertTitle>
            <AlertDescription class="flex flex-col gap-2"><p>{{ reportError }}</p><Button variant="outline" class="w-fit" @click="generateReportPreview">Retry preview</Button></AlertDescription>
          </Alert>

          <template v-else-if="reportPreview">
            <Alert v-if="reportPreview.overall_score === null" variant="warning">
              <TriangleAlertIcon aria-hidden="true" />
              <AlertTitle>Overall result withheld</AlertTitle>
              <AlertDescription>
                Evidence confidence is below the required threshold. Component KPI values remain
                visible for auditability only.
              </AlertDescription>
            </Alert>

            <Card>
              <CardHeader class="gap-4 sm:flex sm:flex-row sm:items-start sm:justify-between">
                <div class="flex flex-col gap-1">
                  <div class="flex flex-wrap items-center gap-2">
                    <p class="text-sm font-medium text-muted-foreground">CEDAR PERFORMANCE</p>
                    <Badge :variant="reportPreview.overall_score === null ? 'warning' : 'success'">
                      {{ reportPreview.performance_tier ?? reportPreview.result_status }}
                    </Badge>
                  </div>
                  <CardTitle class="text-3xl">
                    {{ reportPreview.employee_name || reportPreview.employee_id }}
                  </CardTitle>
                  <CardDescription>
                    {{ reportPreview.employee_id }} · {{ reportPreview.team ?? 'Team not provided' }}<template v-if="reportPreview.role"> · {{ reportPreview.role }}</template>
                  </CardDescription>
                </div>
                <Badge variant="outline" class="w-fit whitespace-normal">
                  <CalendarDaysIcon data-icon="inline-start" />
                  {{ formatReportDate(reportPreview.period.start_date) }} – {{ formatReportDate(reportPreview.period.end_date) }}
                </Badge>
              </CardHeader>
              <CardContent class="grid gap-6 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
                <section class="flex flex-col justify-between gap-6 rounded-lg bg-primary p-5 text-primary-foreground">
                  <div class="flex flex-col gap-1">
                    <p class="text-sm text-primary-foreground">Overall performance</p>
                    <p class="text-5xl font-semibold tracking-tight tabular-nums">
                      {{ score(reportPreview.overall_score) }}
                    </p>
                  </div>
                  <div class="flex flex-wrap items-center gap-2">
                    <Badge v-if="reportPreview.overall_score_change !== null" variant="secondary">
                      <TrendingUpIcon v-if="reportPreview.overall_score_change !== null && reportPreview.overall_score_change > 0" data-icon="inline-start" />
                      <TrendingDownIcon v-else-if="reportPreview.overall_score_change !== null && reportPreview.overall_score_change < 0" data-icon="inline-start" />
                      <MinusIcon v-else data-icon="inline-start" />
                      {{ scoreChange(reportPreview.overall_score_change) }}
                    </Badge>
                    <span class="text-xs text-primary-foreground">
                      {{ reportPreview.overall_score_change === null ? scoreChange(null) : 'versus prior comparable period' }}
                    </span>
                  </div>
                </section>

                <section class="flex flex-col justify-center gap-4">
                  <div class="flex items-end justify-between gap-4">
                    <div class="flex flex-col gap-1">
                      <p class="text-sm text-muted-foreground">Evidence confidence</p>
                      <p class="text-3xl font-semibold tabular-nums">{{ score(reportPreview.data_confidence) }}</p>
                    </div>
                    <Badge variant="secondary">Required {{ score(reportPreview.confidence_threshold) }}</Badge>
                  </div>
                  <Progress :model-value="reportPreview.data_confidence" :tone="reportPreview.overall_score === null ? 'warning' : 'default'" aria-label="Report evidence confidence" />
                  <p class="text-sm leading-6 text-muted-foreground">
                    {{ reportPreview.confidence_explanation }}
                  </p>
                </section>
              </CardContent>
            </Card>

            <div class="grid gap-5 lg:grid-cols-[minmax(0,1.25fr)_minmax(18rem,0.75fr)]">
              <Card>
                <CardHeader>
                  <CardTitle>KPI profile</CardTitle>
                  <CardDescription>Component scores and their contribution to the overall result.</CardDescription>
                </CardHeader>
                <CardContent class="flex flex-col gap-5">
                  <section v-for="kpi in reportPreview.kpis" :key="kpi.name" class="flex flex-col gap-2">
                    <div class="flex items-end justify-between gap-4">
                      <div class="flex flex-col gap-0.5">
                        <h3 class="font-medium">{{ kpi.name }}</h3>
                        <p class="text-xs text-muted-foreground">{{ kpi.weight }}% of overall</p>
                      </div>
                      <strong class="text-2xl tabular-nums">{{ score(kpi.score) }}</strong>
                    </div>
                    <Progress :model-value="kpi.score" />
                  </section>
                </CardContent>
              </Card>

              <div class="flex flex-col gap-5">
                <Card>
                  <CardHeader>
                    <CardTitle>Evidence snapshot</CardTitle>
                    <CardDescription>Traceability included in the report.</CardDescription>
                  </CardHeader>
                  <CardContent class="flex flex-col gap-4">
                    <div class="flex items-center justify-between gap-4">
                      <div class="flex items-center gap-2 text-sm text-muted-foreground">
                        <DatabaseIcon aria-hidden="true" />
                        Supporting records
                      </div>
                      <strong class="text-xl tabular-nums">{{ reportPreview.supporting_record_ids.length }}</strong>
                    </div>
                    <Separator />
                    <div class="flex items-center justify-between gap-4">
                      <div class="flex items-center gap-2 text-sm text-muted-foreground">
                        <TriangleAlertIcon aria-hidden="true" />
                        Validated findings
                      </div>
                      <Badge :variant="reportPreview.findings.length ? 'warning' : 'outline'">
                        {{ reportPreview.findings.length }}
                      </Badge>
                    </div>
                    <div v-if="reportPreview.findings.length" class="flex flex-wrap gap-2">
                      <Badge v-for="finding in reportPreview.findings.slice(0, 3)" :key="finding.code" variant="outline" class="capitalize">
                        {{ impactLabel(finding.scoring_impact) }}
                      </Badge>
                    </div>
                  </CardContent>
                </Card>

                <Alert>
                  <ShieldCheckIcon aria-hidden="true" />
                  <AlertTitle>Manager review required</AlertTitle>
                  <AlertDescription>{{ reportPreview.manager_review_notice }}</AlertDescription>
                </Alert>
              </div>
            </div>
          </template>
        <template #footer>
        <DialogFooter v-if="reportPreview" class="m-0 rounded-none">
          <Button :disabled="reportDownloading" @click="downloadReport">
            <Spinner v-if="reportDownloading" data-icon="inline-start" />
            <DownloadIcon v-else data-icon="inline-start" />
            {{ reportDownloading ? 'Creating PDF…' : 'Download Cedar PDF' }}
          </Button>
        </DialogFooter>
      </template>
      </ReportPreviewContent>
    </Dialog>
  </main>
</template>

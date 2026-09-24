<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from 'vue'
import {
  CircleAlertIcon,
  CircleHelpIcon,
  DownloadIcon,
  FileTextIcon,
} from '@lucide/vue'
import { PopoverContent, PopoverPortal, PopoverRoot, PopoverTrigger } from 'reka-ui'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Field, FieldLabel } from '@/components/ui/field'
import ReportPreviewContent from '@/components/dashboard/ReportPreviewContent.vue'
import EmployeeReportOverview from '@/components/dashboard/EmployeeReportOverview.vue'
import PerformanceHeader from '@/components/dashboard/PerformanceHeader.vue'
import ReportingPeriodPicker from '@/components/dashboard/ReportingPeriodPicker.vue'
import EmployeePerformanceBreakdown from '@/components/dashboard/EmployeePerformanceBreakdown.vue'
import EmployeeKpiComponents from '@/components/dashboard/EmployeeKpiComponents.vue'
import EmployeeManagerSummary from '@/components/dashboard/EmployeeManagerSummary.vue'
import EmployeeEvidenceTable from '@/components/dashboard/EmployeeEvidenceTable.vue'
import EmployeeAttentionSummary from '@/components/dashboard/EmployeeAttentionSummary.vue'
import WeeklyKpiTrend from '@/components/dashboard/WeeklyKpiTrend.vue'
import { evidenceCalculations } from '@/lib/employee-evidence'
import { formatDate as formatReportDate } from '@/lib/date-format'
import { attentionOutsideRecords } from '@/lib/employee-presentation'
import { useEmployeeEvidence } from '@/composables/useEmployeeEvidence'
import type { EvidenceKpi } from '@/types/employee-evidence'
import { Progress } from '@/components/ui/progress'
import { Spinner } from '@/components/ui/spinner'
import { downloadEmployeeReportPdf } from '@/lib/employee-report-pdf'
import type { AnalysisFilters, AnalysisSummary, DashboardFilters, DashboardResponse, EmployeeKpiResult, ErrorPayload, KpiTrendPoint, PerformanceAlert } from '@/types/analysis'
import type { EmployeeReportData, EmployeeReportPreviewResponse, EmployeeReportRequest } from '@/types/reports'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

const props = defineProps<{
  employee: EmployeeKpiResult
  alerts: PerformanceAlert[]
  reportingPeriod: AnalysisFilters
  requestedFilters: DashboardFilters
  summary: AnalysisSummary
  coverageStart: string | null
  coverageEnd: string | null
  latestSubmissionAt: string
  isRefreshing: boolean
  refreshError: string
}>()
const emit = defineEmits<{
  back: []
  refresh: []
  periodChange: [selection: Pick<DashboardFilters, 'period_preset' | 'start_date' | 'end_date'>]
}>()

const reportPreviewOpen = ref(false)
const reportPreview = ref<EmployeeReportData | null>(null)
const reportLoading = ref(false)
const reportDownloading = ref(false)
const reportError = ref('')
const reportDownloadError = ref('')
const employeeTrends = ref<KpiTrendPoint[] | null>(null)
const trendsLoading = ref(false)
const trendsError = ref('')
const trendsStale = ref(false)
let reportController: AbortController | null = null
let reportSequence = 0
let trendsController: AbortController | null = null
let trendsSequence = 0
let trendsRefreshRequested = false
const { states: evidenceStates, load: loadEvidence } = useEmployeeEvidence(
  () => ({ employeeId: props.employee.employee_id, period: props.reportingPeriod, latestSubmissionAt: props.latestSubmissionAt }),
  () => emit('refresh'),
)
watch(() => `${props.employee.employee_id}:${JSON.stringify(props.reportingPeriod)}`, () => {
  reportSequence++
  reportController?.abort()
  reportPreviewOpen.value = false
  reportPreview.value = null
  reportLoading.value = false
})
watch(() => [props.employee.employee_id, props.reportingPeriod, props.latestSubmissionAt], () => {
  trendsRefreshRequested = false
  employeeTrends.value = null
  void loadEmployeeTrends()
}, { immediate: true })
onScopeDispose(() => {
  reportSequence++
  reportController?.abort()
  trendsSequence++
  trendsController?.abort()
})

const kpiSections = computed(() => [
  {
    kpi: 'productivity' as EvidenceKpi,
    label: 'Productivity',
    score: props.employee.productivity_score,
    weight: 35,
  },
  {
    kpi: 'compliance' as EvidenceKpi,
    label: 'Compliance',
    score: props.employee.compliance_score,
    weight: 30,
  },
  {
    kpi: 'quality' as EvidenceKpi,
    label: 'Quality',
    score: props.employee.quality_score,
    weight: 35,
  },
])

const employeeInitials = computed(() => {
  const name = props.employee.employee_name?.trim() || props.employee.employee_id
  return name.split(/\s+/).slice(0, 2).map(part => part[0]?.toUpperCase()).join('')
})
const profileDetails = computed(() => [
  { label: 'Team', value: props.employee.team },
  { label: 'Role', value: props.employee.role },
  { label: 'Campaign', value: props.employee.campaign },
  { label: 'Queue', value: props.employee.queue },
  { label: 'Shift', value: props.employee.shift },
  { label: 'Supervisor', value: props.employee.supervisor },
  { label: 'Location', value: props.employee.location },
].filter(item => item.value))
const periodMode = computed<'full' | 'month' | 'six-months' | 'year' | 'range'>(() => {
  if (props.requestedFilters.period_preset)
    return props.requestedFilters.period_preset
  if (props.requestedFilters.start_date || props.requestedFilters.end_date || props.requestedFilters.period_weeks)
    return 'range'
  return 'full'
})
interface ScoreCard {
  label: string
  score: number | null
  detail: string
  tone: string
  kpi: EvidenceKpi | null
}
const scoreCards = computed<ScoreCard[]>(() => [
  { label: 'Overall score', score: props.employee.overall_score, detail: props.employee.overall_score === null ? props.employee.result_status : props.employee.performance_tier ?? props.employee.result_status, tone: 'bg-primary', kpi: null },
  ...kpiSections.value.map(item => ({ label: item.label, score: item.score, detail: `${item.weight}% of overall`, tone: item.kpi === 'compliance' ? 'bg-chart-2' : item.kpi === 'quality' ? 'bg-chart-3' : 'bg-chart-1', kpi: item.kpi })),
])
const generalAttention = computed(() => attentionOutsideRecords(props.alerts,
  props.employee.validation_findings.filter(finding => ['productivity_evidence', 'attendance', 'submission_evidence', 'leave_evidence', 'quality_evidence', 'source_records'].includes(finding.source_type ?? ''))))
const reportGeneralAttention = computed(() => reportPreview.value ? attentionOutsideRecords(reportPreview.value.findings,
  Object.values(reportPreview.value.evidence_tables).flatMap(table => table.rows.flatMap(row => row.validation_findings))) : [])

function score(value: number | null): string {
  return value === null ? '—' : `${value.toFixed(1)}%`
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

async function loadEmployeeTrends(): Promise<void> {
  const sequence = ++trendsSequence
  trendsController?.abort()
  const controller = new AbortController()
  trendsController = controller
  trendsLoading.value = true
  trendsError.value = ''
  trendsStale.value = false
  const employeeId = props.employee.employee_id
  const latestSubmissionAt = props.latestSubmissionAt
  const query = new URLSearchParams({ employee_id: employeeId })
  if (props.reportingPeriod.start_date) query.set('start_date', props.reportingPeriod.start_date)
  if (props.reportingPeriod.end_date) query.set('end_date', props.reportingPeriod.end_date)
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/dashboard?${query}`, { signal: controller.signal })
    if (!response.ok) {
      const payload = await response.json() as ErrorPayload
      throw new Error(payload.error?.message ?? 'Weekly trends could not be loaded.')
    }
    const payload = await response.json() as DashboardResponse
    if (sequence !== trendsSequence) return
    if (new Date(payload.latest_submission_at).getTime() !== new Date(latestSubmissionAt).getTime()) {
      employeeTrends.value = null
      trendsStale.value = true
      trendsError.value = 'Employee data has changed. Refreshing the results and trends.'
      if (!trendsRefreshRequested) { trendsRefreshRequested = true; emit('refresh') }
      return
    }
    employeeTrends.value = payload.trends
  }
  catch (error) {
    if (sequence !== trendsSequence || controller.signal.aborted) return
    trendsError.value = error instanceof TypeError
      ? 'Weekly trends are temporarily unavailable. Retry to load them.'
      : error instanceof Error ? error.message : 'Weekly trends could not be loaded.'
  }
  finally { if (sequence === trendsSequence) trendsLoading.value = false }
}

async function generateReportPreview(): Promise<void> {
  const sequence = ++reportSequence
  reportController?.abort()
  const controller = new AbortController()
  reportController = controller
  reportPreviewOpen.value = true
  reportLoading.value = true
  reportError.value = ''
  reportDownloadError.value = ''
  reportPreview.value = null
  const request = reportRequest()
  if (!request) {
    reportError.value = 'The dashboard has no resolved reporting period for this employee.'
    reportLoading.value = false
    return
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/reports/employee/preview`, {
      signal: controller.signal,
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    })
    if (!response.ok) {
      const payload = await response.json() as ErrorPayload
      throw new Error(payload.error?.message ?? 'The report preview could not be generated.')
    }
    const payload = await response.json() as EmployeeReportPreviewResponse
    if (sequence !== reportSequence) return
    reportPreview.value = payload.report
  }
  catch (error) {
    if (sequence !== reportSequence || controller.signal.aborted) return
    reportError.value = error instanceof TypeError
      ? 'The report service is temporarily unavailable. Please try again shortly.'
      : error instanceof Error ? error.message : 'The report preview could not be generated.'
  }
  finally {
    if (sequence === reportSequence) reportLoading.value = false
  }
}

async function downloadReport(): Promise<void> {
  if (!reportPreview.value || reportDownloading.value)
    return
  reportDownloading.value = true
  reportDownloadError.value = ''
  try {
    await downloadEmployeeReportPdf(reportPreview.value)
  }
  catch {
    reportDownloadError.value = 'The PDF could not be created in this browser. Try downloading again.'
  }
  finally {
    reportDownloading.value = false
  }
}

</script>

<template>
  <main class="min-h-svh bg-muted/30">
    <PerformanceHeader back @back="emit('back')">
      <Button :disabled="reportLoading || isRefreshing" @click="generateReportPreview">
        <Spinner v-if="reportLoading" data-icon="inline-start" />
        <FileTextIcon v-else data-icon="inline-start" />
        Generate report
      </Button>
    </PerformanceHeader>

    <div class="mx-auto flex max-w-[var(--app-content-max-width)] flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8">
      <header class="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
        <div class="flex min-w-0 items-start gap-4">
          <div class="flex size-16 shrink-0 items-center justify-center rounded-full bg-secondary text-lg font-semibold text-secondary-foreground" aria-hidden="true">{{ employeeInitials }}</div>
          <div class="flex min-w-0 flex-col gap-2">
            <p class="text-sm font-medium text-muted-foreground">Employee performance details</p>
            <div class="flex flex-wrap items-center gap-3">
              <h1 class="wrap-break-word text-3xl font-semibold tracking-tight">{{ employee.employee_name || employee.employee_id }}</h1>
              <Badge :variant="employee.overall_score === null ? 'warning' : 'success'">{{ employee.performance_tier ?? employee.result_status }}</Badge>
            </div>
            <p class="text-sm text-muted-foreground">{{ employee.employee_id }}</p>
            <dl v-if="profileDetails.length" class="flex flex-wrap gap-x-4 gap-y-1 text-sm">
              <div v-for="item in profileDetails" :key="item.label" class="flex min-w-0 gap-1"><dt class="text-muted-foreground">{{ item.label }}:</dt><dd class="wrap-break-word font-medium">{{ item.value }}</dd></div>
            </dl>
          </div>
        </div>
        <Field class="w-full gap-2 xl:w-72 xl:shrink-0">
          <FieldLabel for="period-filter">Reporting period</FieldLabel>
          <ReportingPeriodPicker :mode="periodMode" :filters="reportingPeriod" :coverage-start="coverageStart" :coverage-end="coverageEnd" :disabled="isRefreshing" @change="emit('periodChange', $event)" />
          <p v-if="reportingPeriod.start_date && reportingPeriod.end_date" class="text-xs text-muted-foreground">{{ formatReportDate(reportingPeriod.start_date) }} – {{ formatReportDate(reportingPeriod.end_date) }}</p>
        </Field>
      </header>

      <p v-if="reportingPeriod.score_period_start_date && reportingPeriod.score_period_end_date && (reportingPeriod.score_period_start_date !== reportingPeriod.start_date || reportingPeriod.score_period_end_date !== reportingPeriod.end_date)" class="text-sm text-muted-foreground">Scores use available evidence: {{ formatReportDate(reportingPeriod.score_period_start_date) }} – {{ formatReportDate(reportingPeriod.score_period_end_date) }}.</p>

      <section aria-label="Employee score summary" class="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
        <Card v-for="item in scoreCards" :key="item.label" class="min-w-0 justify-between">
          <CardHeader class="gap-2">
            <CardDescription class="flex items-center gap-2">
              <span class="size-2 shrink-0 rounded-full" :class="item.tone" aria-hidden="true" />
              <span class="min-w-0">{{ item.label }}</span>
              <PopoverRoot v-if="item.kpi">
                <PopoverTrigger as-child>
                  <Button variant="ghost" size="icon-sm" class="ml-auto size-6 shrink-0 rounded-full"
                    :aria-label="`How ${item.label} score is calculated`">
                    <CircleHelpIcon aria-hidden="true" class="size-4" />
                  </Button>
                </PopoverTrigger>
                <PopoverPortal>
                  <PopoverContent side="bottom" align="start" :side-offset="6" class="z-60 w-56 max-w-[calc(100vw-2rem)] rounded-md border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md outline-none"
                    :aria-label="`${item.label} calculation`">
                    {{ evidenceCalculations[item.kpi] }}
                  </PopoverContent>
                </PopoverPortal>
              </PopoverRoot>
            </CardDescription>
            <CardTitle class="text-2xl tabular-nums sm:text-3xl">{{ score(item.score) }}</CardTitle>
          </CardHeader>
          <CardContent class="text-xs text-muted-foreground">{{ item.detail }}</CardContent>
        </Card>
        <Card class="col-span-2 min-w-0 justify-between sm:col-span-1">
          <CardHeader class="gap-2"><CardDescription>Data confidence</CardDescription><CardTitle class="text-2xl tabular-nums sm:text-3xl">{{ score(employee.data_confidence) }}</CardTitle></CardHeader>
          <CardContent class="flex flex-col gap-2">
            <Progress :model-value="employee.data_confidence" :tone="employee.overall_score === null ? 'warning' : 'default'" aria-label="Data confidence" />
            <p class="text-xs text-muted-foreground">{{ employee.overall_score === null ? 'Overall score withheld' : 'Overall scoring eligible' }} · {{ score(employee.confidence_threshold) }} required</p>
          </CardContent>
        </Card>
      </section>
      <Alert v-if="refreshError" variant="destructive">
        <AlertTitle>Employee results could not refresh</AlertTitle>
        <AlertDescription class="flex flex-col gap-2"><p>{{ refreshError }}</p><Button variant="outline" class="w-fit" :disabled="isRefreshing" @click="emit('refresh')">Retry results</Button></AlertDescription>
      </Alert>
      <p v-if="isRefreshing" role="status" class="flex items-center gap-2 text-sm text-muted-foreground"><Spinner />Refreshing employee results and evidence…</p>
      <div class="grid items-start gap-3 xl:items-stretch xl:grid-cols-[minmax(0,2fr)_minmax(20rem,1fr)]">
        <div class="flex min-w-0 flex-col gap-3 xl:h-full">
          <EmployeePerformanceBreakdown :employee="employee" :summary="summary" />
          <div v-if="trendsLoading && employeeTrends === null" role="status" class="flex min-h-96 items-center justify-center gap-2 text-sm text-muted-foreground">
            <Spinner />Loading employee trends…
          </div>
          <Alert v-else-if="trendsError" :variant="trendsStale ? 'warning' : 'destructive'">
            <AlertTitle>Weekly trend unavailable</AlertTitle>
            <AlertDescription class="flex flex-col gap-2">
              <p>{{ trendsError }}</p>
              <Button variant="outline" class="w-fit" :disabled="trendsLoading || isRefreshing" @click="trendsStale ? emit('refresh') : loadEmployeeTrends()">
                {{ trendsStale ? 'Retry results' : 'Retry trend' }}
              </Button>
            </AlertDescription>
          </Alert>
          <WeeklyKpiTrend v-else-if="employeeTrends !== null" :trends="employeeTrends" scale="detail" compact-on-desktop
            description="This employee and the selected reporting period apply. Gaps mean no score is available." />
        </div>
        <EmployeeManagerSummary :employee="employee" :alerts="alerts" />
      </div>
      <EmployeeKpiComponents :employee="employee" />
      <EmployeeAttentionSummary :items="generalAttention" />
      <section id="employee-evidence" aria-label="KPI evidence" class="flex min-w-0 scroll-mt-4 flex-col gap-6">
        <EmployeeEvidenceTable v-for="item in kpiSections" :id="`${item.kpi}-evidence`" :key="item.kpi"
          :kpi="item.kpi"
          :rows="evidenceStates[item.kpi].data?.rows ?? []" :total="evidenceStates[item.kpi].data?.total_count ?? 0"
          :all-records-count="evidenceStates[item.kpi].data?.all_records_count" :needs-review-count="evidenceStates[item.kpi].data?.needs_review_count"
          :review-only="evidenceStates[item.kpi].data?.review_only ?? false"
          :page="evidenceStates[item.kpi].data?.page ?? 1" :page-size="evidenceStates[item.kpi].committedPageSize" :loading="evidenceStates[item.kpi].loading"
          :error="evidenceStates[item.kpi].error" :disabled="isRefreshing"
          @page-change="loadEvidence(item.kpi, $event, evidenceStates[item.kpi].data?.review_only ?? false, evidenceStates[item.kpi].committedPageSize)" @review-change="loadEvidence(item.kpi, 1, $event, evidenceStates[item.kpi].committedPageSize)" @page-size-change="loadEvidence(item.kpi, 1, evidenceStates[item.kpi].data?.review_only ?? false, $event)" @retry="loadEvidence(item.kpi)" />
      </section>

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
                Review the snapshot before creating the PDF. All selected-period records are included.
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
            <Alert v-if="reportDownloadError" variant="destructive">
              <AlertTitle>PDF could not be created</AlertTitle>
              <AlertDescription>{{ reportDownloadError }}</AlertDescription>
            </Alert>
            <EmployeeReportOverview :report="reportPreview" />
            <EmployeeAttentionSummary :items="reportGeneralAttention" />
            <section id="report-evidence" aria-label="Report KPI evidence" class="flex min-w-0 scroll-mt-4 flex-col gap-5">
              <EmployeeEvidenceTable v-for="kpi in reportPreview.kpis" :id="`report-${kpi.name.toLowerCase()}-evidence`" :key="kpi.name"
                :kpi="kpi.name.toLowerCase() as EvidenceKpi"
                :rows="reportPreview.evidence_tables[kpi.name.toLowerCase() as EvidenceKpi].rows"
                :total="reportPreview.evidence_tables[kpi.name.toLowerCase() as EvidenceKpi].total_count" report />
            </section>
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

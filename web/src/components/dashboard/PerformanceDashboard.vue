<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowDownIcon, ArrowUpDownIcon, ArrowUpIcon, ChevronDownIcon, ChevronUpIcon, DownloadIcon, EyeIcon, FileTextIcon, TriangleAlertIcon } from '@lucide/vue'
import CallCenterFilterBar from '@/components/dashboard/CallCenterFilterBar.vue'
import DashboardActionCenter from '@/components/dashboard/DashboardActionCenter.vue'
import KpiBreakdownPanel from '@/components/dashboard/KpiBreakdownPanel.vue'
import PerformanceHeader from '@/components/dashboard/PerformanceHeader.vue'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationFirst,
  PaginationItem,
  PaginationLast,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination'
import { Progress } from '@/components/ui/progress'
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import TeamReportPreviewDialog from '@/components/dashboard/TeamReportPreviewDialog.vue'
import WeeklyKpiTrend from '@/components/dashboard/WeeklyKpiTrend.vue'
import { downloadKpiReportPdf, type DashboardKpi } from '@/lib/dashboard-report-pdf'
import { formatDate } from '@/lib/date-format'
import type { DashboardFilters, DashboardResponse, EmployeeKpiResult } from '@/types/analysis'

const props = defineProps<{
  analysis: DashboardResponse
  requestedFilters: DashboardFilters
  isFiltering?: boolean
  filterError?: string
}>()
const emit = defineEmits<{
  filtersChange: [filters: DashboardFilters]
}>()
const router = useRouter()
const lastAttempt = ref<DashboardFilters>({})
const currentPage = ref(1)
const pageSize = ref('10')
const sortKey = ref<'name' | 'performance' | null>(null)
const sortDirection = ref<'asc' | 'desc'>('asc')
const teamReportPreviewOpen = ref(false)
const reportLoading = ref<DashboardKpi | null>(null)
const reportError = ref('')
const activeBreakdown = ref<DashboardKpi | null>(null)

const filteredRows = computed(() => props.analysis.results)
const sortedRows = computed(() => {
  if (!sortKey.value)
    return filteredRows.value

  return [...filteredRows.value].sort((left, right) => {
    if (sortKey.value === 'name') {
      const comparison = employeeLabel(left).localeCompare(employeeLabel(right), undefined, { sensitivity: 'base' })
      return sortDirection.value === 'asc' ? comparison : -comparison
    }

    if (left.overall_score === null)
      return right.overall_score === null ? 0 : 1
    if (right.overall_score === null)
      return -1

    const comparison = left.overall_score - right.overall_score
    return sortDirection.value === 'asc' ? comparison : -comparison
  })
})
const numericPageSize = computed(() => Number(pageSize.value))
const paginatedRows = computed(() => {
  const start = (currentPage.value - 1) * numericPageSize.value
  return sortedRows.value.slice(start, start + numericPageSize.value)
})
const firstVisibleRow = computed(() => filteredRows.value.length
  ? (currentPage.value - 1) * numericPageSize.value + 1
  : 0)
const lastVisibleRow = computed(() => Math.min(
  currentPage.value * numericPageSize.value,
  filteredRows.value.length,
))
const summaryCards = computed(() => {
  const count = props.analysis.summary.scored_employee_count
  const withheld = props.analysis.summary.insufficient_data_count
  const population = `${count} scored · ${withheld} withheld`
  return [
    { label: 'Overall score', value: props.analysis.summary.average_overall_score, detail: population, weight: null, color: 'var(--primary)', kpi: null },
    { label: 'Productivity', value: props.analysis.summary.average_productivity_score, detail: population, weight: 35, color: 'var(--chart-1)', kpi: 'productivity' as const },
    { label: 'Compliance', value: props.analysis.summary.average_compliance_score, detail: population, weight: 30, color: 'var(--chart-2)', kpi: 'compliance' as const },
    { label: 'Quality', value: props.analysis.summary.average_quality_score, detail: population, weight: 35, color: 'var(--chart-3)', kpi: 'quality' as const },
  ]
})

const alertCountsByEmployee = computed(() => props.analysis.alerts.reduce<Record<string, { data_issue: number, performance_alert: number }>>(
  (counts, alert) => {
    if (alert.employee_id) {
      counts[alert.employee_id] ??= { data_issue: 0, performance_alert: 0 }
      counts[alert.employee_id][alert.category] += 1
    }
    return counts
  },
  {},
))
const appliedPeriod = computed(() => {
  const filters = props.analysis.applied_filters
  const presetLabel = props.requestedFilters.period_preset === 'month' ? 'Last month'
    : props.requestedFilters.period_preset === 'six-months' ? 'Last 6 months'
      : props.requestedFilters.period_preset === 'year' ? 'Last year' : ''
  if (filters.start_date && filters.start_date === filters.end_date)
    return `${presetLabel ? `${presetLabel} · ` : ''}${formatDate(filters.start_date)}`
  const dates = filters.start_date && filters.end_date
    ? `${formatDate(filters.start_date)} – ${formatDate(filters.end_date)}`
    : 'Full available period'
  return presetLabel ? `${presetLabel} · ${dates}` : dates
})

const scoreScopeNotice = computed(() => {
  const filters = props.analysis.applied_filters
  const scoreStart = filters.score_period_start_date
  const scoreEnd = filters.score_period_end_date
  if (!hasPeriodFilter.value) return ''
  if (!scoreStart || !scoreEnd)
    return 'No evidence is on file in the selected range. Overall scores are withheld.'
  if (scoreStart !== filters.start_date || scoreEnd !== filters.end_date)
    return `Dates without evidence remain in the selected range. Scores use available evidence from ${formatDate(scoreStart)} to ${formatDate(scoreEnd)}.`
  return ''
})

const hasPeriodFilter = computed(() => Boolean(
  props.requestedFilters.period_preset
  || props.requestedFilters.period_weeks
  || (props.requestedFilters.start_date && props.requestedFilters.end_date),
))
const hasActiveFilters = computed(() => Boolean(
  hasPeriodFilter.value
  || props.analysis.applied_filters.campaign
  || props.analysis.applied_filters.queue
  || props.analysis.applied_filters.shift
  || props.analysis.applied_filters.supervisor
  || props.analysis.applied_filters.location,
))


watch([filteredRows, pageSize], () => {
  currentPage.value = 1
})

function buildFilters(): DashboardFilters {
  const filters: DashboardFilters = {}
  for (const key of ['campaign', 'queue', 'shift', 'supervisor', 'location'] as const) {
    const value = props.analysis.applied_filters[key]
    if (value)
      filters[key] = value
  }
  if (props.requestedFilters.start_date && props.requestedFilters.end_date) {
    filters.start_date = props.requestedFilters.start_date
    filters.end_date = props.requestedFilters.end_date
  }
  else if (props.requestedFilters.period_preset) {
    filters.period_preset = props.requestedFilters.period_preset
  }
  else if (props.requestedFilters.period_weeks) {
    filters.period_weeks = props.requestedFilters.period_weeks
  }
  return filters
}

function score(value: number | null): string {
  return value === null ? '—' : `${value.toFixed(1)}%`
}

function employeeLabel(row: { employee_id: string, employee_name: string | null }): string {
  return row.employee_name || row.employee_id
}

function toggleSort(key: 'name' | 'performance'): void {
  if (sortKey.value === key) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  }
  else {
    sortKey.value = key
    sortDirection.value = key === 'performance' ? 'desc' : 'asc'
  }
  currentPage.value = 1
}

function ariaSort(key: 'name' | 'performance'): 'ascending' | 'descending' | 'none' {
  if (sortKey.value !== key)
    return 'none'
  return sortDirection.value === 'asc' ? 'ascending' : 'descending'
}

function alertCount(employeeId: string, category: 'data_issue' | 'performance_alert'): number {
  return alertCountsByEmployee.value[employeeId]?.[category] ?? 0
}

async function generateKpiReport(kpi: DashboardKpi): Promise<void> {
  reportLoading.value = kpi
  reportError.value = ''
  try {
    await downloadKpiReportPdf(props.analysis, kpi)
  }
  catch {
    reportError.value = `The ${kpi} report could not be generated. Please try again.`
  }
  finally {
    reportLoading.value = null
  }
}

function openEmployeeDetails(row: EmployeeKpiResult): void {
  void router.push({ name: 'employee-detail', params: { employeeId: row.employee_id } })
}

function applyFacet(key: 'campaign' | 'queue' | 'shift' | 'supervisor' | 'location', value: string): void {
  const filters = buildFilters()
  if (value === 'all') delete filters[key]
  else filters[key] = value
  requestFilters(filters)
}

function applyPeriodFilter(selection: Pick<DashboardFilters, 'period_preset' | 'start_date' | 'end_date'>): void {
  const filters = buildFilters()
  delete filters.period_weeks
  delete filters.period_preset
  delete filters.start_date
  delete filters.end_date
  requestFilters({ ...filters, ...selection })
}

function requestFilters(filters: DashboardFilters): void {
  lastAttempt.value = { ...filters }
  emit('filtersChange', filters)
}

</script>

<template>
  <main class="min-h-svh bg-muted/30">
    <PerformanceHeader>
        <Button :disabled="isFiltering || !filteredRows.length" @click="teamReportPreviewOpen = true">
          <FileTextIcon data-icon="inline-start" />
          Generate report
        </Button>
    </PerformanceHeader>

    <div class="mx-auto flex max-w-[var(--app-content-max-width)] flex-col gap-6 px-4 py-6 sm:px-6">
      <section class="flex flex-col gap-2">
        <div class="flex flex-col gap-2">
          <div class="flex flex-wrap items-center gap-2"><h1 class="text-2xl font-semibold tracking-tight">Call-center performance</h1><Badge variant="outline">{{ appliedPeriod }}</Badge><Badge v-if="isFiltering" variant="secondary"><Spinner data-icon="inline-start" />Updating</Badge></div>
          <p class="text-sm text-muted-foreground">Monitor agent performance across campaigns, queues, shifts, supervisors, and locations. Data confidence measures required evidence completeness, not employee performance.</p>
        </div>
      </section>

      <CallCenterFilterBar
        :filters="analysis.applied_filters"
        :requested-filters="requestedFilters"
        :coverage-start="analysis.coverage_start"
        :coverage-end="analysis.coverage_end"
        :campaigns="analysis.available_campaigns"
        :queues="analysis.available_queues"
        :shifts="analysis.available_shifts"
        :supervisors="analysis.available_supervisors"
        :locations="analysis.available_locations"
        :disabled="isFiltering"
        @facet-change="applyFacet"
        @period-change="applyPeriodFilter"
      />

      <div class="flex flex-wrap items-center justify-between gap-2 text-sm" aria-live="polite">
        <div class="flex flex-col gap-1">
          <p>{{ analysis.summary.scored_employee_count }} scored · {{ analysis.summary.insufficient_data_count }} withheld · {{ analysis.summary.total_employee_count }} employees</p>
          <p v-if="scoreScopeNotice" class="text-muted-foreground">{{ scoreScopeNotice }}</p>
        </div>
        <Button v-if="hasActiveFilters" variant="ghost" size="sm" :disabled="isFiltering" @click="requestFilters({})">Clear filters</Button>
      </div>

      <Alert v-if="filterError" variant="destructive"><TriangleAlertIcon aria-hidden="true" /><AlertTitle>Dashboard could not update</AlertTitle><AlertDescription class="flex flex-col gap-2"><p>{{ filterError }} Showing the last successfully applied filters.</p><Button variant="outline" size="sm" class="w-fit" :disabled="isFiltering" @click="requestFilters(lastAttempt)">Retry filters</Button></AlertDescription></Alert>
      <Alert v-if="reportError" variant="destructive"><TriangleAlertIcon aria-hidden="true" /><AlertTitle>Report could not be created</AlertTitle><AlertDescription>{{ reportError }}</AlertDescription></Alert>

      <section aria-label="Performance summary" class="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <Card v-for="item in summaryCards" :key="item.label" class="justify-between">
          <CardHeader class="gap-2">
            <CardDescription class="flex items-center gap-2"><span class="size-2 rounded-full" :style="{ backgroundColor: item.color }" />{{ item.label }}</CardDescription>
            <CardAction v-if="item.kpi"><Button variant="ghost" size="icon-sm" :disabled="isFiltering || reportLoading !== null || !filteredRows.length" :aria-label="`Download ${item.label} report`" :title="`Download ${item.label} report`" @click="generateKpiReport(item.kpi)"><Spinner v-if="reportLoading === item.kpi" /><DownloadIcon v-else /><span class="sr-only">Download {{ item.label }} report</span></Button></CardAction>
            <CardTitle class="text-2xl tabular-nums sm:text-3xl">{{ score(item.value) }}</CardTitle>
          </CardHeader>
          <CardContent class="flex flex-col gap-1 text-xs text-muted-foreground">
            <span>{{ item.detail }}</span>
            <span v-if="item.weight">{{ item.weight }}% of overall</span>
            <span v-else>100% evidence required for an overall score</span>
          </CardContent>
          <CardFooter v-if="item.kpi" class="border-0 bg-transparent p-3 pt-0 sm:p-4 sm:pt-0">
            <Button type="button" :variant="activeBreakdown === item.kpi ? 'default' : 'outline'" size="sm" class="w-full justify-between" :aria-expanded="activeBreakdown === item.kpi" aria-controls="kpi-breakdown" :disabled="isFiltering" @click="activeBreakdown = activeBreakdown === item.kpi ? null : item.kpi">
              {{ activeBreakdown === item.kpi ? 'Hide breakdown' : 'View breakdown' }}
              <ChevronUpIcon v-if="activeBreakdown === item.kpi" data-icon="inline-end" /><ChevronDownIcon v-else data-icon="inline-end" />
            </Button>
          </CardFooter>
        </Card>
      </section>
      <KpiBreakdownPanel v-if="activeBreakdown" :selected="activeBreakdown" :breakdowns="analysis.kpi_breakdowns" :disabled="isFiltering" @select="activeBreakdown = $event" />

      <section aria-label="Trends and actions" class="grid items-start gap-3 xl:grid-cols-[minmax(0,2fr)_minmax(20rem,1fr)] xl:items-stretch">
        <WeeklyKpiTrend :trends="analysis.trends" description="" />
        <DashboardActionCenter :alerts="analysis.alerts" :disabled="isFiltering" />
      </section>

      <Card>
        <CardHeader><div class="flex flex-wrap items-start justify-between gap-3"><div><CardTitle>Employee results</CardTitle><CardDescription>Component scores remain visible when overall scoring is withheld.</CardDescription></div><Badge variant="outline">{{ filteredRows.length }} employees</Badge></div></CardHeader>
        <CardContent class="hidden 2xl:block">
          <Table class="table-fixed">
            <colgroup>
              <col style="width: 9.5%">
              <col style="width: 11%">
              <col style="width: 7.25%">
              <col style="width: 7.25%">
              <col style="width: 6.25%">
              <col style="width: 11.5%">
              <col style="width: 7%">
              <col style="width: 10%">
              <col style="width: 8%">
              <col style="width: 11%">
              <col style="width: 11.25%">
            </colgroup>
            <TableHeader><TableRow><TableHead :aria-sort="ariaSort('name')"><Button variant="ghost" size="sm" class="-ml-2.5" @click="toggleSort('name')">Employee<ArrowUpIcon v-if="sortKey === 'name' && sortDirection === 'asc'" data-icon="inline-end" /><ArrowDownIcon v-else-if="sortKey === 'name'" data-icon="inline-end" /><ArrowUpDownIcon v-else data-icon="inline-end" /></Button></TableHead><TableHead>Campaign / Queue</TableHead><TableHead class="text-right">Productivity</TableHead><TableHead class="text-right">Compliance</TableHead><TableHead class="text-right">Quality</TableHead><TableHead>Data confidence</TableHead><TableHead :aria-sort="ariaSort('performance')" class="text-right"><Button variant="ghost" size="sm" @click="toggleSort('performance')">Overall<ArrowUpIcon v-if="sortKey === 'performance' && sortDirection === 'asc'" data-icon="inline-end" /><ArrowDownIcon v-else-if="sortKey === 'performance'" data-icon="inline-end" /><ArrowUpDownIcon v-else data-icon="inline-end" /></Button></TableHead><TableHead>Status</TableHead><TableHead class="text-center">Data Issues</TableHead><TableHead class="text-center">Performance Alerts</TableHead><TableHead class="text-right">Actions</TableHead></TableRow></TableHeader>
            <TableBody>
              <TableRow v-for="row in paginatedRows" :key="row.employee_id"><TableCell class="whitespace-normal break-words"><div class="font-medium">{{ employeeLabel(row) }}</div><div class="text-xs text-muted-foreground">{{ row.employee_id }}</div></TableCell><TableCell class="whitespace-normal break-words"><div>{{ row.campaign ?? 'Campaign not provided' }}</div><div class="text-xs text-muted-foreground">{{ row.queue ?? 'Queue not provided' }}</div></TableCell><TableCell class="text-right tabular-nums">{{ score(row.productivity_score) }}</TableCell><TableCell class="text-right tabular-nums">{{ score(row.compliance_score) }}</TableCell><TableCell class="text-right tabular-nums">{{ score(row.quality_score) }}</TableCell><TableCell><div class="flex items-center gap-2"><Progress :model-value="row.data_confidence" class="w-20" /><span class="text-xs tabular-nums">{{ row.data_confidence.toFixed(0) }}%</span></div></TableCell><TableCell class="text-right font-medium tabular-nums">{{ score(row.overall_score) }}</TableCell><TableCell><Badge :variant="row.overall_score === null ? 'warning' : 'success'">{{ row.performance_tier ?? row.result_status }}</Badge></TableCell><TableCell class="text-center"><Badge :variant="alertCount(row.employee_id, 'data_issue') ? 'warning' : 'outline'">{{ alertCount(row.employee_id, 'data_issue') }}</Badge></TableCell><TableCell class="text-center"><Badge :variant="alertCount(row.employee_id, 'performance_alert') ? 'warning' : 'outline'">{{ alertCount(row.employee_id, 'performance_alert') }}</Badge></TableCell><TableCell class="text-right"><Button variant="outline" size="sm" @click="openEmployeeDetails(row)"><EyeIcon data-icon="inline-start" />View details</Button></TableCell></TableRow>
              <TableRow v-if="!filteredRows.length"><TableCell colspan="11" class="h-24 text-center text-muted-foreground">No employees match these filters.</TableCell></TableRow>
            </TableBody>
          </Table>
        </CardContent>
        <CardContent class="flex flex-col gap-4 2xl:hidden">
          <div class="flex flex-wrap gap-2" aria-label="Sort employees">
            <Button variant="outline" size="sm" @click="toggleSort('name')">Name {{ sortKey === 'name' ? (sortDirection === 'asc' ? '↑' : '↓') : '' }}</Button>
            <Button variant="outline" size="sm" @click="toggleSort('performance')">Overall {{ sortKey === 'performance' ? (sortDirection === 'asc' ? '↑' : '↓') : '' }}</Button>
          </div>
          <article v-for="row in paginatedRows" :key="row.employee_id" class="flex flex-col gap-3 border-b pb-4 last:border-0 last:pb-0">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0"><h3 class="wrap-break-word font-medium">{{ employeeLabel(row) }}</h3><p class="text-xs text-muted-foreground">{{ row.employee_id }} · {{ row.campaign ?? 'Campaign not provided' }} · {{ row.queue ?? 'Queue not provided' }}</p></div>
              <div class="shrink-0 text-right"><p class="text-xs text-muted-foreground">Overall</p><p class="font-semibold tabular-nums">{{ score(row.overall_score) }}</p></div>
            </div>
            <div class="flex flex-wrap items-center gap-2"><Badge :variant="row.overall_score === null ? 'warning' : 'success'">{{ row.performance_tier ?? row.result_status }}</Badge><span class="text-xs">{{ row.data_confidence.toFixed(0) }}% data confidence · {{ alertCount(row.employee_id, 'data_issue') }} data issues · {{ alertCount(row.employee_id, 'performance_alert') }} performance alerts</span></div>
            <dl class="grid grid-cols-3 gap-2 text-xs"><div><dt class="text-muted-foreground">Productivity</dt><dd class="mt-1 tabular-nums">{{ score(row.productivity_score) }}</dd></div><div><dt class="text-muted-foreground">Compliance</dt><dd class="mt-1 tabular-nums">{{ score(row.compliance_score) }}</dd></div><div><dt class="text-muted-foreground">Quality</dt><dd class="mt-1 tabular-nums">{{ score(row.quality_score) }}</dd></div></dl>
            <Button variant="outline" size="sm" class="w-fit" :aria-label="`View details for ${employeeLabel(row)}`" @click="openEmployeeDetails(row)"><EyeIcon data-icon="inline-start" />View details</Button>
          </article>
          <p v-if="!filteredRows.length" class="py-8 text-center text-muted-foreground">No employees match these filters. Clear filters to see all employees.</p>
        </CardContent>
        <CardFooter class="flex-col gap-4 border-t sm:flex-row sm:justify-between">
          <div class="flex items-center gap-3 text-sm text-muted-foreground">
            <span>{{ firstVisibleRow }}–{{ lastVisibleRow }} of {{ filteredRows.length }}</span>
            <Select v-model="pageSize">
              <SelectTrigger class="w-20" aria-label="Rows per page"><SelectValue /></SelectTrigger>
              <SelectContent><SelectGroup><SelectItem value="10">10</SelectItem><SelectItem value="25">25</SelectItem><SelectItem value="50">50</SelectItem></SelectGroup></SelectContent>
            </Select>
            <span>rows per page</span>
          </div>
          <Pagination v-model:page="currentPage" :items-per-page="numericPageSize" :total="filteredRows.length" :sibling-count="1" show-edges class="mx-0 w-auto">
            <PaginationContent v-slot="{ items }">
              <PaginationFirst />
              <PaginationPrevious />
              <template v-for="(item, index) in items" :key="index">
                <PaginationItem v-if="item.type === 'page'" :value="item.value" :is-active="item.value === currentPage">{{ item.value }}</PaginationItem>
                <PaginationEllipsis v-else :index="index" />
              </template>
              <PaginationNext />
              <PaginationLast />
            </PaginationContent>
          </Pagination>
        </CardFooter>
      </Card>
    </div>

    <TeamReportPreviewDialog
      v-model:open="teamReportPreviewOpen"
      :analysis="analysis"
    />
  </main>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowDownIcon, ArrowUpDownIcon, ArrowUpIcon, DownloadIcon, EyeIcon, FileTextIcon, TriangleAlertIcon } from '@lucide/vue'
import PerformanceHeader from '@/components/dashboard/PerformanceHeader.vue'
import ReportingPeriodPicker from '@/components/dashboard/ReportingPeriodPicker.vue'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field'
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
type PeriodChoice = 'full' | 'month' | 'six-months' | 'year' | 'range'

const employee = computed(() => props.analysis.applied_filters.employee_id ?? 'all')
const team = computed(() => props.analysis.applied_filters.team ?? 'all')
const period = computed<PeriodChoice>(() => {
  const filters = props.requestedFilters
  if (filters.period_preset)
    return filters.period_preset
  if (filters.start_date && filters.end_date)
    return 'range'
  return 'full'
})
const lastAttempt = ref<DashboardFilters>({})
const currentPage = ref(1)
const pageSize = ref('10')
const sortKey = ref<'name' | 'performance' | null>(null)
const sortDirection = ref<'asc' | 'desc'>('asc')
const teamReportPreviewOpen = ref(false)
const reportLoading = ref<DashboardKpi | null>(null)
const reportError = ref('')

const employeeOptions = computed(() => props.analysis.available_employees.filter(row =>
  team.value === 'all' || row.team === team.value,
))
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
const teams = computed(() => props.analysis.available_teams)
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
  const population = `${count} scored employee${count === 1 ? '' : 's'}`
  return [
    { label: 'Overall score', value: props.analysis.summary.average_overall_score, detail: population, color: 'var(--primary)', kpi: null },
    { label: 'Productivity', value: props.analysis.summary.average_productivity_score, detail: `${population} · 35% of overall`, color: 'var(--chart-1)', kpi: 'productivity' as const },
    { label: 'Compliance', value: props.analysis.summary.average_compliance_score, detail: `${population} · 30% of overall`, color: 'var(--chart-2)', kpi: 'compliance' as const },
    { label: 'Quality', value: props.analysis.summary.average_quality_score, detail: `${population} · 35% of overall`, color: 'var(--chart-3)', kpi: 'quality' as const },
  ]
})

const alertCountsByEmployee = computed(() => props.analysis.alerts.reduce<Record<string, number>>(
  (counts, alert) => {
    if (alert.employee_id)
      counts[alert.employee_id] = (counts[alert.employee_id] ?? 0) + 1
    return counts
  },
  {},
))
const appliedPeriod = computed(() => {
  const filters = props.analysis.applied_filters
  const presetLabel = period.value === 'month' ? 'Last month'
    : period.value === 'six-months' ? 'Last 6 months'
      : period.value === 'year' ? 'Last year' : ''
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
  if (period.value === 'full') return ''
  if (!scoreStart || !scoreEnd)
    return 'No evidence is on file in the selected range. Overall scores are withheld.'
  if (scoreStart !== filters.start_date || scoreEnd !== filters.end_date)
    return `Dates without evidence remain in the selected range. Scores use available evidence from ${formatDate(scoreStart)} to ${formatDate(scoreEnd)}.`
  return ''
})


watch([filteredRows, pageSize], () => {
  currentPage.value = 1
})

function buildFilters(): DashboardFilters {
  const filters: DashboardFilters = {}
  if (employee.value !== 'all')
    filters.employee_id = employee.value
  if (team.value !== 'all')
    filters.team = team.value
  if (period.value === 'range') {
    filters.start_date = props.requestedFilters.start_date
    filters.end_date = props.requestedFilters.end_date
  }
  else if (period.value !== 'full')
    filters.period_preset = period.value
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

function alertCount(employeeId: string): number {
  return alertCountsByEmployee.value[employeeId] ?? 0
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

function applyFilter(key: 'employee_id' | 'team', value: unknown): void {
  const filters = buildFilters()
  const selected = String(value)
  if (key === 'team') {
    delete filters.employee_id
    if (selected === 'all') delete filters.team
    else filters.team = selected
  }
  else if (key === 'employee_id') {
    if (selected === 'all') delete filters.employee_id
    else filters.employee_id = selected
  }
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
          Generate team report
        </Button>
    </PerformanceHeader>

    <div class="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6">
      <section class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div class="flex flex-col gap-2">
          <div class="flex flex-wrap items-center gap-2"><h1 class="text-2xl font-semibold tracking-tight">Employee performance</h1><Badge variant="outline">{{ appliedPeriod }}</Badge><Badge v-if="isFiltering" variant="secondary"><Spinner data-icon="inline-start" />Updating</Badge></div>
          <p class="text-sm text-muted-foreground">Review KPI scores, trends, and findings. Data confidence measures required evidence completeness, not employee performance.</p>
        </div>
        <FieldGroup class="grid w-full gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.4fr)] lg:w-152 lg:shrink-0">
          <Field class="min-w-0 gap-1.5"><FieldLabel for="employee-filter">Employee</FieldLabel><Select :model-value="employee" :disabled="isFiltering" @update:model-value="applyFilter('employee_id', $event)"><SelectTrigger id="employee-filter" class="w-full bg-background"><SelectValue /></SelectTrigger><SelectContent><SelectGroup><SelectItem value="all">All employees</SelectItem><SelectItem v-for="row in employeeOptions" :key="row.employee_id" :value="row.employee_id">{{ employeeLabel(row) }}</SelectItem></SelectGroup></SelectContent></Select></Field>
          <Field class="min-w-0 gap-1.5"><FieldLabel for="team-filter">Team</FieldLabel><Select :model-value="team" :disabled="isFiltering" @update:model-value="applyFilter('team', $event)"><SelectTrigger id="team-filter" class="w-full bg-background"><SelectValue /></SelectTrigger><SelectContent><SelectGroup><SelectItem value="all">All teams</SelectItem><SelectItem v-for="item in teams" :key="item" :value="item">{{ item }}</SelectItem></SelectGroup></SelectContent></Select></Field>
          <Field class="min-w-0 gap-1.5"><FieldLabel for="period-filter">Reporting period</FieldLabel><ReportingPeriodPicker :mode="period" :filters="analysis.applied_filters" :coverage-start="analysis.coverage_start" :coverage-end="analysis.coverage_end" :disabled="isFiltering" @change="applyPeriodFilter" /></Field>
        </FieldGroup>
      </section>

      <div class="flex flex-wrap items-center justify-between gap-2 text-sm" aria-live="polite">
        <div class="flex flex-col gap-1">
          <p>{{ analysis.summary.scored_employee_count }} scored · {{ analysis.summary.insufficient_data_count }} withheld · {{ analysis.summary.total_employee_count }} employees</p>
          <p v-if="scoreScopeNotice" class="text-muted-foreground">{{ scoreScopeNotice }}</p>
        </div>
        <Button v-if="employee !== 'all' || team !== 'all' || period !== 'full'" variant="ghost" size="sm" :disabled="isFiltering" @click="requestFilters({})">Clear filters</Button>
      </div>

      <Alert v-if="filterError" variant="destructive"><TriangleAlertIcon aria-hidden="true" /><AlertTitle>Dashboard could not update</AlertTitle><AlertDescription class="flex flex-col gap-2"><p>{{ filterError }} Showing the last successfully applied filters.</p><Button variant="outline" size="sm" class="w-fit" :disabled="isFiltering" @click="requestFilters(lastAttempt)">Retry filters</Button></AlertDescription></Alert>
      <Alert v-if="reportError" variant="destructive"><TriangleAlertIcon aria-hidden="true" /><AlertTitle>Report could not be created</AlertTitle><AlertDescription>{{ reportError }}</AlertDescription></Alert>

      <section class="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <Card v-for="item in summaryCards" :key="item.label"><CardHeader class="pb-2"><CardDescription class="flex items-center gap-2"><span class="size-2 rounded-full" :style="{ backgroundColor: item.color }" />{{ item.label }}</CardDescription><CardAction v-if="item.kpi"><Button variant="ghost" size="icon-sm" :disabled="isFiltering || reportLoading !== null || !filteredRows.length" :aria-label="`Download ${item.label} report`" :title="`Download ${item.label} report`" @click="generateKpiReport(item.kpi)"><Spinner v-if="reportLoading === item.kpi" /><DownloadIcon v-else /><span class="sr-only">Download {{ item.label }} report</span></Button></CardAction><CardTitle class="text-2xl tabular-nums sm:text-3xl">{{ score(item.value) }}</CardTitle></CardHeader><CardContent class="text-xs text-muted-foreground">{{ item.detail }}</CardContent></Card>
      </section>

      <Card>
        <CardHeader><div class="flex flex-wrap items-start justify-between gap-3"><div><CardTitle>Employee results</CardTitle><CardDescription>Component scores remain visible when overall scoring is withheld.</CardDescription></div><Badge variant="outline">{{ filteredRows.length }} employees</Badge></div></CardHeader>
        <CardContent class="hidden overflow-x-auto lg:block">
          <Table>
            <TableHeader><TableRow><TableHead :aria-sort="ariaSort('name')"><Button variant="ghost" size="sm" @click="toggleSort('name')">Employee<ArrowUpIcon v-if="sortKey === 'name' && sortDirection === 'asc'" data-icon="inline-end" /><ArrowDownIcon v-else-if="sortKey === 'name'" data-icon="inline-end" /><ArrowUpDownIcon v-else data-icon="inline-end" /></Button></TableHead><TableHead>Team</TableHead><TableHead class="text-right">Productivity</TableHead><TableHead class="text-right">Compliance</TableHead><TableHead class="text-right">Quality</TableHead><TableHead class="min-w-36">Data confidence</TableHead><TableHead :aria-sort="ariaSort('performance')" class="text-right"><Button variant="ghost" size="sm" @click="toggleSort('performance')">Overall<ArrowUpIcon v-if="sortKey === 'performance' && sortDirection === 'asc'" data-icon="inline-end" /><ArrowDownIcon v-else-if="sortKey === 'performance'" data-icon="inline-end" /><ArrowUpDownIcon v-else data-icon="inline-end" /></Button></TableHead><TableHead>Status</TableHead><TableHead class="text-center">Findings</TableHead><TableHead class="text-right">Actions</TableHead></TableRow></TableHeader>
            <TableBody>
              <TableRow v-for="row in paginatedRows" :key="row.employee_id"><TableCell><div class="font-medium">{{ employeeLabel(row) }}</div><div class="text-xs text-muted-foreground">{{ row.employee_id }}</div></TableCell><TableCell>{{ row.team ?? 'Not provided' }}</TableCell><TableCell class="text-right tabular-nums">{{ score(row.productivity_score) }}</TableCell><TableCell class="text-right tabular-nums">{{ score(row.compliance_score) }}</TableCell><TableCell class="text-right tabular-nums">{{ score(row.quality_score) }}</TableCell><TableCell><div class="flex items-center gap-2"><Progress :model-value="row.data_confidence" class="w-20" /><span class="text-xs tabular-nums">{{ row.data_confidence.toFixed(0) }}%</span></div></TableCell><TableCell class="text-right font-medium tabular-nums">{{ score(row.overall_score) }}</TableCell><TableCell><Badge :variant="row.overall_score === null ? 'warning' : 'success'">{{ row.performance_tier ?? row.result_status }}</Badge></TableCell><TableCell class="text-center"><Badge :variant="alertCount(row.employee_id) ? 'warning' : 'outline'">{{ alertCount(row.employee_id) }}</Badge></TableCell><TableCell class="text-right"><Button variant="outline" size="sm" @click="openEmployeeDetails(row)"><EyeIcon data-icon="inline-start" />View details</Button></TableCell></TableRow>
              <TableRow v-if="!filteredRows.length"><TableCell colspan="10" class="h-24 text-center text-muted-foreground">No employees match these filters.</TableCell></TableRow>
            </TableBody>
          </Table>
        </CardContent>
        <CardContent class="flex flex-col gap-4 lg:hidden">
          <div class="flex flex-wrap gap-2" aria-label="Sort employees">
            <Button variant="outline" size="sm" @click="toggleSort('name')">Name {{ sortKey === 'name' ? (sortDirection === 'asc' ? '↑' : '↓') : '' }}</Button>
            <Button variant="outline" size="sm" @click="toggleSort('performance')">Overall {{ sortKey === 'performance' ? (sortDirection === 'asc' ? '↑' : '↓') : '' }}</Button>
          </div>
          <article v-for="row in paginatedRows" :key="row.employee_id" class="flex flex-col gap-3 border-b pb-4 last:border-0 last:pb-0">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0"><h3 class="wrap-break-word font-medium">{{ employeeLabel(row) }}</h3><p class="text-xs text-muted-foreground">{{ row.employee_id }} · {{ row.team ?? 'Team not provided' }}</p></div>
              <div class="shrink-0 text-right"><p class="text-xs text-muted-foreground">Overall</p><p class="font-semibold tabular-nums">{{ score(row.overall_score) }}</p></div>
            </div>
            <div class="flex flex-wrap items-center gap-2"><Badge :variant="row.overall_score === null ? 'warning' : 'success'">{{ row.performance_tier ?? row.result_status }}</Badge><span class="text-xs">{{ row.data_confidence.toFixed(0) }}% data confidence · {{ alertCount(row.employee_id) }} findings</span></div>
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

      <WeeklyKpiTrend :trends="analysis.trends" description="Current employee, team, and period filters apply. Gaps mean no score is available." />
    </div>

    <TeamReportPreviewDialog
      v-model:open="teamReportPreviewOpen"
      :analysis="analysis"
    />
  </main>
</template>

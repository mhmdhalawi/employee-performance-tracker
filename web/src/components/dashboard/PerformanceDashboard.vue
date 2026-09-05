<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { VisAxis, VisLine, VisXYContainer } from '@unovis/vue'
import { ArrowDownIcon, ArrowUpDownIcon, ArrowUpIcon, DownloadIcon, EyeIcon, FileTextIcon, TriangleAlertIcon } from '@lucide/vue'
import PerformanceHeader from '@/components/dashboard/PerformanceHeader.vue'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartContainer, type ChartConfig } from '@/components/ui/chart'
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
import DataInterpretationCard from '@/components/dashboard/DataInterpretationCard.vue'
import TeamReportPreviewDialog from '@/components/dashboard/TeamReportPreviewDialog.vue'
import { downloadKpiReportPdf, type DashboardKpi } from '@/lib/dashboard-report-pdf'
import type { DashboardFilters, DashboardResponse, EmployeeKpiResult } from '@/types/analysis'

const props = defineProps<{
  analysis: DashboardResponse
  isFiltering?: boolean
  filterError?: string
}>()
const emit = defineEmits<{
  filtersChange: [filters: DashboardFilters]
}>()
const router = useRouter()

const employee = computed(() => props.analysis.applied_filters.employee_id ?? 'all')
const team = computed(() => props.analysis.applied_filters.team ?? 'all')
const period = computed(() => String(props.analysis.applied_filters.period_weeks ?? 'full'))
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
const summaryCards = computed(() => [
  { label: 'Overall score', value: props.analysis.summary.average_overall_score, detail: 'Scored employees only', color: 'var(--primary)', kpi: null },
  { label: 'Productivity', value: props.analysis.summary.average_productivity_score, detail: '35% of overall', color: 'var(--chart-1)', kpi: 'productivity' as const },
  { label: 'Compliance', value: props.analysis.summary.average_compliance_score, detail: '30% of overall', color: 'var(--chart-2)', kpi: 'compliance' as const },
  { label: 'Quality', value: props.analysis.summary.average_quality_score, detail: '35% of overall', color: 'var(--chart-3)', kpi: 'quality' as const },
])

interface DashboardTrendPoint {
  label: string
  productivity: number | null
  compliance: number | null
  quality: number | null
}

const trendData = computed<DashboardTrendPoint[]>(() => props.analysis.trends.map(point => ({
  label: formatDate(point.period_end),
  productivity: point.productivity_score,
  compliance: point.compliance_score,
  quality: point.quality_score,
})))
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
  return filters?.start_date && filters.end_date
    ? `${formatDate(filters.start_date)} – ${formatDate(filters.end_date)}`
    : 'Full available period'
})

const chartConfig = {
  productivity: { label: 'Productivity', color: 'var(--chart-1)' },
  compliance: { label: 'Compliance', color: 'var(--chart-2)' },
  quality: { label: 'Quality', color: 'var(--chart-3)' },
} satisfies ChartConfig

const trendX = (_point: DashboardTrendPoint, index: number) => index
// Unovis treats null as zero; NaN deliberately breaks the line at missing evidence.
const productivityY = (point: DashboardTrendPoint) => point.productivity ?? Number.NaN
const complianceY = (point: DashboardTrendPoint) => point.compliance ?? Number.NaN
const qualityY = (point: DashboardTrendPoint) => point.quality ?? Number.NaN
const weekTick = (index: number) => trendData.value[index]?.label ?? ''
const percentTick = (value: number) => `${value}%`

watch([filteredRows, pageSize], () => {
  currentPage.value = 1
})

function buildFilters(): DashboardFilters {
  const filters: DashboardFilters = {}
  if (employee.value !== 'all')
    filters.employee_id = employee.value
  if (team.value !== 'all')
    filters.team = team.value
  if (period.value !== 'full')
    filters.period_weeks = Number.parseInt(period.value, 10) as 4 | 8 | 12
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

function applyFilter(key: 'employee_id' | 'team' | 'period_weeks', value: unknown): void {
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
  else {
    if (selected === 'full') delete filters.period_weeks
    else filters.period_weeks = Number(selected) as 4 | 8 | 12
  }
  requestFilters(filters)
}

function requestFilters(filters: DashboardFilters): void {
  lastAttempt.value = { ...filters }
  emit('filtersChange', filters)
}

function openDataInterpretation(): void {
  void router.push({ name: 'data-interpretation' })
}

function parseDate(value: string): Date {
  return new Date(`${value}T00:00:00Z`)
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' }).format(parseDate(value))
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
          <p class="text-sm text-muted-foreground">Review KPI scores, evidence confidence, trends, and findings.</p>
        </div>
        <FieldGroup class="grid w-full gap-3 sm:grid-cols-3 lg:w-[34rem] lg:shrink-0">
          <Field class="min-w-0 gap-1.5"><FieldLabel for="employee-filter">Employee</FieldLabel><Select :model-value="employee" :disabled="isFiltering" @update:model-value="applyFilter('employee_id', $event)"><SelectTrigger id="employee-filter" class="w-full"><SelectValue /></SelectTrigger><SelectContent><SelectGroup><SelectItem value="all">All employees</SelectItem><SelectItem v-for="row in employeeOptions" :key="row.employee_id" :value="row.employee_id">{{ employeeLabel(row) }}</SelectItem></SelectGroup></SelectContent></Select></Field>
          <Field class="min-w-0 gap-1.5"><FieldLabel for="team-filter">Team</FieldLabel><Select :model-value="team" :disabled="isFiltering" @update:model-value="applyFilter('team', $event)"><SelectTrigger id="team-filter" class="w-full"><SelectValue /></SelectTrigger><SelectContent><SelectGroup><SelectItem value="all">All teams</SelectItem><SelectItem v-for="item in teams" :key="item" :value="item">{{ item }}</SelectItem></SelectGroup></SelectContent></Select></Field>
          <Field class="min-w-0 gap-1.5"><FieldLabel for="period-filter">Reporting period</FieldLabel><Select :model-value="period" :disabled="isFiltering" @update:model-value="applyFilter('period_weeks', $event)"><SelectTrigger id="period-filter" class="w-full"><SelectValue /></SelectTrigger><SelectContent><SelectGroup><SelectItem value="full">Full period</SelectItem><SelectItem value="4">Last 4 weeks</SelectItem><SelectItem value="8">Last 8 weeks</SelectItem><SelectItem value="12">Last 12 weeks</SelectItem></SelectGroup></SelectContent></Select></Field>
        </FieldGroup>
      </section>

      <div class="flex flex-wrap items-center justify-between gap-2 text-sm" aria-live="polite">
        <p>{{ analysis.summary.scored_employee_count }} scored · {{ analysis.summary.insufficient_data_count }} withheld · {{ analysis.summary.total_employee_count }} employees</p>
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
            <TableHeader><TableRow><TableHead :aria-sort="ariaSort('name')"><Button variant="ghost" size="sm" @click="toggleSort('name')">Employee<ArrowUpIcon v-if="sortKey === 'name' && sortDirection === 'asc'" data-icon="inline-end" /><ArrowDownIcon v-else-if="sortKey === 'name'" data-icon="inline-end" /><ArrowUpDownIcon v-else data-icon="inline-end" /></Button></TableHead><TableHead>Team</TableHead><TableHead class="text-right">Productivity</TableHead><TableHead class="text-right">Compliance</TableHead><TableHead class="text-right">Quality</TableHead><TableHead class="min-w-36">Confidence</TableHead><TableHead :aria-sort="ariaSort('performance')" class="text-right"><Button variant="ghost" size="sm" @click="toggleSort('performance')">Overall<ArrowUpIcon v-if="sortKey === 'performance' && sortDirection === 'asc'" data-icon="inline-end" /><ArrowDownIcon v-else-if="sortKey === 'performance'" data-icon="inline-end" /><ArrowUpDownIcon v-else data-icon="inline-end" /></Button></TableHead><TableHead>Status</TableHead><TableHead class="text-center">Findings</TableHead><TableHead class="text-right">Actions</TableHead></TableRow></TableHeader>
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
              <div class="min-w-0"><h3 class="break-words font-medium">{{ employeeLabel(row) }}</h3><p class="text-xs text-muted-foreground">{{ row.employee_id }} · {{ row.team ?? 'Team not provided' }}</p></div>
              <div class="shrink-0 text-right"><p class="text-xs text-muted-foreground">Overall</p><p class="font-semibold tabular-nums">{{ score(row.overall_score) }}</p></div>
            </div>
            <div class="flex flex-wrap items-center gap-2"><Badge :variant="row.overall_score === null ? 'warning' : 'success'">{{ row.performance_tier ?? row.result_status }}</Badge><span class="text-xs">{{ row.data_confidence.toFixed(0) }}% confidence · {{ alertCount(row.employee_id) }} findings</span></div>
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

      <Card>
        <CardHeader><div class="flex items-start justify-between gap-3"><div><CardTitle>Weekly KPI trend</CardTitle><CardDescription>Current employee, team, and period filters apply. Gaps mean no score is available.</CardDescription></div><Badge variant="outline">{{ trendData.length }} periods</Badge></div></CardHeader>
        <CardContent>
          <div class="mb-4 flex flex-wrap gap-4 text-xs" aria-label="Chart legend">
            <span v-for="(item, key) in chartConfig" :key="key" class="flex items-center gap-2"><svg class="h-2 w-6" aria-hidden="true"><line x1="0" y1="4" x2="24" y2="4" :stroke="item.color" stroke-width="2" :stroke-dasharray="key === 'compliance' ? '6 3' : key === 'quality' ? '2 3' : undefined" /></svg>{{ item.label }}</span>
          </div>
          <ChartContainer v-if="trendData.length" :config="chartConfig" class="h-72 w-full" aria-label="Weekly KPI chart; exact values in the table below"><VisXYContainer :data="trendData" :duration="0" :y-domain="[0, 100]"><VisAxis type="x" :x="trendX" :tick-format="weekTick" /><VisAxis type="y" :tick-format="percentTick" /><VisLine :x="trendX" :y="productivityY" :fallback-value="undefined" :color="chartConfig.productivity.color" /><VisLine :x="trendX" :y="complianceY" :fallback-value="undefined" :line-dash-array="[6, 3]" :color="chartConfig.compliance.color" /><VisLine :x="trendX" :y="qualityY" :fallback-value="undefined" :line-dash-array="[2, 3]" :color="chartConfig.quality.color" /></VisXYContainer></ChartContainer>
          <p v-else class="py-16 text-center text-sm text-muted-foreground">No trend data is available for this filter.</p>
          <details v-if="trendData.length" class="mt-4"><summary class="cursor-pointer text-sm font-medium">View weekly values</summary><div class="mt-3 overflow-x-auto"><Table><TableHeader><TableRow><TableHead>Week ending</TableHead><TableHead>Productivity</TableHead><TableHead>Compliance</TableHead><TableHead>Quality</TableHead></TableRow></TableHeader><TableBody><TableRow v-for="point in trendData" :key="point.label"><TableCell>{{ point.label }}</TableCell><TableCell>{{ point.productivity === null ? 'No productivity data' : score(point.productivity) }}</TableCell><TableCell>{{ point.compliance === null ? 'No compliance data' : score(point.compliance) }}</TableCell><TableCell>{{ point.quality === null ? 'No quality data' : score(point.quality) }}</TableCell></TableRow></TableBody></Table></div></details>
        </CardContent>
      </Card>

      <DataInterpretationCard :mapping-summaries="analysis.mapping_summaries" @view-details="openDataInterpretation" />

    </div>

    <TeamReportPreviewDialog
      v-model:open="teamReportPreviewOpen"
      :analysis="analysis"
    />
  </main>
</template>

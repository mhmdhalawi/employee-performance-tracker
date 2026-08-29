<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { VisAxis, VisLine, VisXYContainer } from '@unovis/vue'
import { ArrowDownIcon, ArrowLeftIcon, ArrowUpDownIcon, ArrowUpIcon, FileSpreadsheetIcon, ListFilterIcon, ShieldCheckIcon, TriangleAlertIcon } from '@lucide/vue'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from '@/components/ui/chart'
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
import AIInsights from '@/components/dashboard/AIInsights.vue'
import PerformanceAlerts from '@/components/dashboard/PerformanceAlerts.vue'
import type { AIInsightResponse, AnalyzeResponse, DashboardFilters, EmployeeAIInsight, EmployeeKpiResult, ErrorPayload, PerformanceAlert } from '@/types/analysis'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

const props = defineProps<{
  analysis: AnalyzeResponse
  isFiltering?: boolean
  filterError?: string
}>()
const emit = defineEmits<{
  back: []
  filtersChange: [filters: DashboardFilters]
}>()

const employee = ref('all')
const team = ref('all')
const period = ref('full')
const currentPage = ref(1)
const pageSize = ref('10')
const showAlerts = ref(false)
const sortKey = ref<'name' | 'performance' | null>(null)
const sortDirection = ref<'asc' | 'desc'>('asc')
const allEmployeeOptions = ref<EmployeeKpiResult[]>(props.analysis.results)
const insightsByEmployee = ref<Record<string, EmployeeAIInsight>>({})
const insightLoadingEmployeeId = ref<string | null>(null)
const insightError = ref('')
let filterTimer: number | undefined

const employeeOptions = computed(() => allEmployeeOptions.value.filter(row =>
  team.value === 'all' || row.team === team.value,
))
const filteredRows = computed(() => props.analysis.results.filter(row =>
  (employee.value === 'all' || row.employee_id === employee.value)
  && (team.value === 'all' || row.team === team.value),
))
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
const scoredRows = computed(() => filteredRows.value.filter(row => row.overall_score !== null))
const averages = computed(() => ({
  overall: average(scoredRows.value.map(row => row.overall_score)),
  productivity: average(filteredRows.value.map(row => row.productivity_score)),
  compliance: average(filteredRows.value.map(row => row.compliance_score)),
  quality: average(filteredRows.value.map(row => row.quality_score)),
}))
const summaryCards = computed(() => [
  { label: 'Overall score', value: averages.value.overall, detail: 'Scored employees only', color: 'var(--primary)' },
  { label: 'Productivity', value: averages.value.productivity, detail: '35% of overall', color: 'var(--chart-1)' },
  { label: 'Compliance', value: averages.value.compliance, detail: '30% of overall', color: 'var(--chart-2)' },
  { label: 'Quality', value: averages.value.quality, detail: '35% of overall', color: 'var(--chart-3)' },
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
const scopedAlerts = computed(() => props.analysis.alerts.filter(alert => {
  const isGlobal = !alert.employee_id && !alert.team
  const matchesEmployee = employee.value === 'all' || alert.employee_id === employee.value
  const matchesTeam = team.value === 'all' || alert.team === team.value
  return isGlobal || (matchesEmployee && matchesTeam)
}))
const visibleAlerts = computed(() => scopedAlerts.value.slice(0, 3))
const insightEmployees = computed(() => filteredRows.value.filter(
  row => row.validation_findings.some(finding => finding.record_ids.length > 0),
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
const productivityY = (point: DashboardTrendPoint) => point.productivity
const complianceY = (point: DashboardTrendPoint) => point.compliance
const qualityY = (point: DashboardTrendPoint) => point.quality
const weekTick = (index: number) => trendData.value[index]?.label ?? ''
const percentTick = (value: number) => `${value}%`

watch(team, () => {
  if (employee.value !== 'all')
    employee.value = 'all'
})

watch(period, () => {
  window.clearTimeout(filterTimer)
  filterTimer = window.setTimeout(() => emit('filtersChange', buildFilters()), 250)
}, { flush: 'post' })

watch([filteredRows, pageSize], () => {
  currentPage.value = 1
})

watch(() => props.analysis.analysis_id, () => {
  insightsByEmployee.value = {}
  insightLoadingEmployeeId.value = null
  insightError.value = ''
})

function buildFilters(): DashboardFilters {
  const filters: DashboardFilters = {}
  if (period.value !== 'full' && props.analysis.dataset_overview.date_end) {
    const weeks = Number.parseInt(period.value, 10)
    const end = parseDate(props.analysis.dataset_overview.date_end)
    const start = new Date(end)
    start.setUTCDate(start.getUTCDate() - weeks * 7 + 1)
    const datasetStart = props.analysis.dataset_overview.date_start
      ? parseDate(props.analysis.dataset_overview.date_start)
      : start
    filters.start_date = formatIsoDate(start < datasetStart ? datasetStart : start)
    filters.end_date = props.analysis.dataset_overview.date_end
  }
  return filters
}

function average(values: Array<number | null>): number | null {
  const valid = values.filter((value): value is number => value !== null)
  return valid.length ? valid.reduce((sum, value) => sum + value, 0) / valid.length : null
}

function score(value: number | null): string {
  return value === null ? '—' : `${value.toFixed(1)}%`
}

function employeeLabel(row: EmployeeKpiResult): string {
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

function alertTitle(alert: PerformanceAlert): string {
  return `${alert.employee_name || alert.employee_id || 'Dataset'} · ${alertCodeLabel(alert.code)}`
}

function alertCodeLabel(code: string): string {
  return code.replaceAll('_', ' ')
}

function alertRecords(alert: PerformanceAlert): string {
  const preview = alert.record_ids.slice(0, 4).join(', ')
  const remaining = alert.record_ids.length - 4
  return remaining > 0 ? `${preview} +${remaining} more` : preview
}

async function generateInsight(employeeId: string): Promise<void> {
  if (insightsByEmployee.value[employeeId])
    return

  insightLoadingEmployeeId.value = employeeId
  insightError.value = ''
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/insights`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        analysis_id: props.analysis.analysis_id,
        employee_id: employeeId,
      }),
    })
    if (!response.ok) {
      const payload = await response.json() as ErrorPayload
      throw new Error(payload.error?.message ?? 'AI guidance could not be generated.')
    }
    const payload = await response.json() as AIInsightResponse
    insightsByEmployee.value = {
      ...insightsByEmployee.value,
      [employeeId]: payload.insight,
    }
  }
  catch (error) {
    insightError.value = error instanceof TypeError
      ? 'The API could not be reached. Confirm the FastAPI server is running.'
      : error instanceof Error ? error.message : 'AI guidance could not be generated.'
  }
  finally {
    insightLoadingEmployeeId.value = null
  }
}

function parseDate(value: string): Date {
  return new Date(`${value}T00:00:00Z`)
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric', timeZone: 'UTC' }).format(parseDate(value))
}

function formatIsoDate(value: Date): string {
  return value.toISOString().slice(0, 10)
}
</script>

<template>
  <PerformanceAlerts
    v-if="showAlerts && analysis"
    :alerts="scopedAlerts"
    :file-name="analysis.file_name"
    @back="showAlerts = false"
  />
  <main v-else class="min-h-svh bg-muted/30">
    <header class="border-b bg-background">
      <div class="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
        <div class="flex items-center gap-3">
          <div class="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground"><ShieldCheckIcon class="size-4" aria-hidden="true" /></div>
          <div><p class="font-semibold">Performance dashboard</p><p class="text-xs text-muted-foreground">{{ analysis.file_name }}</p></div>
        </div>
        <Button variant="outline" @click="emit('back')"><ArrowLeftIcon data-icon="inline-start" />New analysis</Button>
      </div>
    </header>

    <div class="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6">
      <section class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div class="flex flex-col gap-2">
          <div class="flex flex-wrap items-center gap-2"><h1 class="text-2xl font-semibold tracking-tight">Employee performance</h1><Badge variant="outline">{{ appliedPeriod }}</Badge><Badge v-if="isFiltering" variant="secondary"><Spinner data-icon="inline-start" />Updating</Badge></div>
          <p class="text-sm text-muted-foreground">Review KPI scores, evidence confidence, trends, and findings.</p>
        </div>
        <div class="grid gap-3 sm:grid-cols-3">
          <Select v-model="employee" :disabled="isFiltering"><SelectTrigger class="w-full sm:w-48"><SelectValue placeholder="Employee" /></SelectTrigger><SelectContent><SelectGroup><SelectItem value="all">All employees</SelectItem><SelectItem v-for="row in employeeOptions" :key="row.employee_id" :value="row.employee_id">{{ employeeLabel(row) }}</SelectItem></SelectGroup></SelectContent></Select>
          <Select v-model="team" :disabled="isFiltering"><SelectTrigger class="w-full sm:w-44"><SelectValue placeholder="Team" /></SelectTrigger><SelectContent><SelectGroup><SelectItem value="all">All teams</SelectItem><SelectItem v-for="item in teams" :key="item" :value="item">{{ item }}</SelectItem></SelectGroup></SelectContent></Select>
          <Select v-model="period" :disabled="isFiltering"><SelectTrigger class="w-full sm:w-40"><SelectValue placeholder="Period" /></SelectTrigger><SelectContent><SelectGroup><SelectItem value="full">Full period</SelectItem><SelectItem value="4">Last 4 weeks</SelectItem><SelectItem value="8">Last 8 weeks</SelectItem><SelectItem value="12">Last 12 weeks</SelectItem></SelectGroup></SelectContent></Select>
        </div>
      </section>

      <Alert v-if="filterError" variant="destructive"><TriangleAlertIcon aria-hidden="true" /><AlertTitle>Dashboard could not update</AlertTitle><AlertDescription>{{ filterError }}</AlertDescription></Alert>

      <section class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card v-for="item in summaryCards" :key="item.label"><CardHeader class="pb-2"><CardDescription class="flex items-center gap-2"><span class="size-2 rounded-full" :style="{ backgroundColor: item.color }" />{{ item.label }}</CardDescription><CardTitle class="text-3xl" :style="{ color: item.color }">{{ score(item.value) }}</CardTitle></CardHeader><CardContent class="text-xs text-muted-foreground">{{ item.detail }}</CardContent></Card>
      </section>

      <Card>
        <CardHeader><div class="flex flex-wrap items-start justify-between gap-3"><div><CardTitle>Employee results</CardTitle><CardDescription>Component scores remain visible when overall scoring is withheld.</CardDescription></div><Badge variant="outline">{{ filteredRows.length }} employees</Badge></div></CardHeader>
        <CardContent class="overflow-x-auto">
          <Table>
            <TableHeader><TableRow><TableHead :aria-sort="ariaSort('name')"><Button variant="ghost" size="sm" @click="toggleSort('name')">Employee<ArrowUpIcon v-if="sortKey === 'name' && sortDirection === 'asc'" data-icon="inline-end" /><ArrowDownIcon v-else-if="sortKey === 'name'" data-icon="inline-end" /><ArrowUpDownIcon v-else data-icon="inline-end" /></Button></TableHead><TableHead>Team</TableHead><TableHead class="text-right">Productivity</TableHead><TableHead class="text-right">Compliance</TableHead><TableHead class="text-right">Quality</TableHead><TableHead class="min-w-36">Confidence</TableHead><TableHead :aria-sort="ariaSort('performance')" class="text-right"><Button variant="ghost" size="sm" @click="toggleSort('performance')">Overall<ArrowUpIcon v-if="sortKey === 'performance' && sortDirection === 'asc'" data-icon="inline-end" /><ArrowDownIcon v-else-if="sortKey === 'performance'" data-icon="inline-end" /><ArrowUpDownIcon v-else data-icon="inline-end" /></Button></TableHead><TableHead>Status</TableHead></TableRow></TableHeader>
            <TableBody>
              <TableRow v-for="row in paginatedRows" :key="row.employee_id"><TableCell><div class="font-medium">{{ employeeLabel(row) }}</div><div class="text-xs text-muted-foreground">{{ row.employee_id }}</div></TableCell><TableCell>{{ row.team ?? 'Not provided' }}</TableCell><TableCell class="text-right tabular-nums">{{ score(row.productivity_score) }}</TableCell><TableCell class="text-right tabular-nums">{{ score(row.compliance_score) }}</TableCell><TableCell class="text-right tabular-nums">{{ score(row.quality_score) }}</TableCell><TableCell><div class="flex items-center gap-2"><Progress :model-value="row.data_confidence" class="w-20" /><span class="text-xs tabular-nums">{{ row.data_confidence.toFixed(0) }}%</span></div></TableCell><TableCell class="text-right font-medium tabular-nums">{{ score(row.overall_score) }}</TableCell><TableCell><Badge :variant="row.overall_score === null ? 'warning' : 'success'">{{ row.performance_tier ?? row.result_status }}</Badge></TableCell></TableRow>
              <TableRow v-if="!filteredRows.length"><TableCell colspan="8" class="h-24 text-center text-muted-foreground">No employees match these filters.</TableCell></TableRow>
            </TableBody>
          </Table>
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

      <section class="grid items-start gap-6 xl:grid-cols-[2fr_1fr]">
        <Card>
          <CardHeader><div class="flex items-start justify-between gap-3"><div><CardTitle>Weekly KPI trend</CardTitle><CardDescription>All employees for the selected reporting period. Employee and team filters apply to results and alerts.</CardDescription></div><Badge variant="outline">{{ trendData.length }} periods</Badge></div></CardHeader>
          <CardContent>
            <ChartContainer v-if="trendData.length" :config="chartConfig" class="h-72 w-full"><VisXYContainer :data="trendData" :y-domain="[0, 100]"><VisAxis type="x" :x="trendX" :tick-format="weekTick" /><VisAxis type="y" :tick-format="percentTick" /><VisLine :x="trendX" :y="productivityY" :color="chartConfig.productivity.color" /><VisLine :x="trendX" :y="complianceY" :color="chartConfig.compliance.color" /><VisLine :x="trendX" :y="qualityY" :color="chartConfig.quality.color" /><ChartTooltip /></VisXYContainer><ChartTooltipContent /></ChartContainer>
            <p v-else class="py-16 text-center text-sm text-muted-foreground">No trend data is available for this filter.</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><div class="flex items-start justify-between gap-3"><div><CardTitle>Priority alerts</CardTitle><CardDescription>Highest-priority grouped findings.</CardDescription></div><Badge variant="outline">{{ scopedAlerts.length }} alerts</Badge></div></CardHeader>
          <CardContent class="flex flex-col gap-4">
            <Alert v-for="alert in visibleAlerts" :key="`${alert.employee_id}-${alert.code}`" :variant="alert.severity === 'info' ? 'default' : 'warning'"><TriangleAlertIcon v-if="alert.severity !== 'info'" aria-hidden="true" /><FileSpreadsheetIcon v-else aria-hidden="true" /><AlertTitle class="capitalize">{{ alertTitle(alert) }} <Badge variant="outline">{{ alert.occurrence_count }}</Badge></AlertTitle><AlertDescription>{{ alert.message }}<span v-if="alert.record_ids.length" class="block">Records: {{ alertRecords(alert) }}</span><a v-if="alert.evidence_links[0]" class="text-primary underline-offset-4 hover:underline" :href="alert.evidence_links[0]" target="_blank" rel="noreferrer">Open evidence</a></AlertDescription></Alert>
            <p v-if="!visibleAlerts.length" class="py-8 text-center text-sm text-muted-foreground">No findings require attention for this filter.</p>
          </CardContent>
          <CardFooter v-if="scopedAlerts.length > 0" class="border-t">
            <Button class="w-full" variant="outline" @click="showAlerts = true"><ListFilterIcon data-icon="inline-start" />View all {{ scopedAlerts.length }} alerts</Button>
          </CardFooter>
        </Card>
      </section>

      <AIInsights
        :employees="insightEmployees"
        :insights="insightsByEmployee"
        :loading-employee-id="insightLoadingEmployeeId"
        :error="insightError"
        @generate="generateInsight"
      />
    </div>
  </main>
</template>

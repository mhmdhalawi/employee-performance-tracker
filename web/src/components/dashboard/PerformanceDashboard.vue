<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { VisAxis, VisLine, VisXYContainer } from '@unovis/vue'
import { ArrowLeftIcon, FileSpreadsheetIcon, ShieldCheckIcon, TriangleAlertIcon } from '@lucide/vue'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from '@/components/ui/chart'
import { Progress } from '@/components/ui/progress'
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { previewResults, previewTeams, previewTrends } from '@/data/dashboard-preview'
import type { AnalyzeResponse, DashboardFilters, EmployeeKpiResult, PerformanceAlert } from '@/types/analysis'

const props = defineProps<{
  analysis: AnalyzeResponse | null
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
const employeeOptions = ref<EmployeeKpiResult[]>(props.analysis?.results ?? previewResults)
let filterTimer: number | undefined

const isPreview = computed(() => !props.analysis)
const sourceRows = computed(() => props.analysis?.results ?? previewResults)
const teams = computed(() => props.analysis?.available_teams ?? [...new Set(Object.values(previewTeams))])
const filteredRows = computed(() => isPreview.value
  ? sourceRows.value.filter(row =>
      (employee.value === 'all' || row.employee_id === employee.value)
      && (team.value === 'all' || previewTeams[row.employee_id] === team.value),
    )
  : sourceRows.value)
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

const trendData = computed<DashboardTrendPoint[]>(() => props.analysis
  ? props.analysis.trends.map(point => ({
      label: formatDate(point.period_end),
      productivity: point.productivity_score,
      compliance: point.compliance_score,
      quality: point.quality_score,
    }))
  : previewTrends.map(point => ({
      label: point.week,
      productivity: point.productivity,
      compliance: point.compliance,
      quality: point.quality,
    })))
const visibleAlerts = computed(() => props.analysis?.alerts.slice(0, 6) ?? [])
const appliedPeriod = computed(() => {
  const filters = props.analysis?.applied_filters
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

watch([employee, team, period], () => {
  if (isPreview.value)
    return

  window.clearTimeout(filterTimer)
  filterTimer = window.setTimeout(() => emit('filtersChange', buildFilters()), 250)
}, { flush: 'post' })

function buildFilters(): DashboardFilters {
  const filters: DashboardFilters = {}
  if (employee.value !== 'all')
    filters.employee_id = employee.value
  if (team.value !== 'all')
    filters.team = team.value

  if (period.value !== 'full' && props.analysis?.dataset_overview.date_end) {
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

function alertTitle(alert: PerformanceAlert): string {
  return `${alert.employee_name || alert.employee_id || 'Dataset'} · ${alert.code.replaceAll('_', ' ')}`
}

function alertRecords(alert: PerformanceAlert): string {
  const preview = alert.record_ids.slice(0, 4).join(', ')
  const remaining = alert.record_ids.length - 4
  return remaining > 0 ? `${preview} +${remaining} more` : preview
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
  <main class="min-h-svh bg-muted/30">
    <header class="border-b bg-background">
      <div class="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
        <div class="flex items-center gap-3">
          <div class="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground"><ShieldCheckIcon class="size-4" aria-hidden="true" /></div>
          <div><p class="font-semibold">Performance dashboard</p><p class="text-xs text-muted-foreground">{{ analysis?.file_name ?? 'Dashboard design preview' }}</p></div>
        </div>
        <Button variant="outline" @click="emit('back')"><ArrowLeftIcon data-icon="inline-start" />New analysis</Button>
      </div>
    </header>

    <div class="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6">
      <section class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div class="flex flex-col gap-2">
          <div class="flex flex-wrap items-center gap-2"><h1 class="text-2xl font-semibold tracking-tight">Employee performance</h1><Badge v-if="isPreview" variant="secondary">Preview data</Badge><Badge v-else variant="outline">{{ appliedPeriod }}</Badge><Badge v-if="isFiltering" variant="secondary"><Spinner data-icon="inline-start" />Updating</Badge></div>
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
            <TableHeader><TableRow><TableHead>Employee</TableHead><TableHead>Team</TableHead><TableHead class="text-right">Productivity</TableHead><TableHead class="text-right">Compliance</TableHead><TableHead class="text-right">Quality</TableHead><TableHead class="min-w-36">Confidence</TableHead><TableHead class="text-right">Overall</TableHead><TableHead>Status</TableHead></TableRow></TableHeader>
            <TableBody>
              <TableRow v-for="row in filteredRows" :key="row.employee_id"><TableCell><div class="font-medium">{{ employeeLabel(row) }}</div><div class="text-xs text-muted-foreground">{{ row.employee_id }}</div></TableCell><TableCell>{{ row.team ?? previewTeams[row.employee_id] ?? 'Not provided' }}</TableCell><TableCell class="text-right tabular-nums">{{ score(row.productivity_score) }}</TableCell><TableCell class="text-right tabular-nums">{{ score(row.compliance_score) }}</TableCell><TableCell class="text-right tabular-nums">{{ score(row.quality_score) }}</TableCell><TableCell><div class="flex items-center gap-2"><Progress :model-value="row.data_confidence" class="w-20" /><span class="text-xs tabular-nums">{{ row.data_confidence.toFixed(0) }}%</span></div></TableCell><TableCell class="text-right font-medium tabular-nums">{{ score(row.overall_score) }}</TableCell><TableCell><Badge :variant="row.overall_score === null ? 'warning' : 'success'">{{ row.performance_tier ?? row.result_status }}</Badge></TableCell></TableRow>
              <TableRow v-if="!filteredRows.length"><TableCell colspan="8" class="h-24 text-center text-muted-foreground">No employees match these filters.</TableCell></TableRow>
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <section class="grid gap-6 xl:grid-cols-[2fr_1fr]">
        <Card>
          <CardHeader><div class="flex items-start justify-between gap-3"><div><CardTitle>Weekly KPI trend</CardTitle><CardDescription>Independent weekly component averages for the selected population.</CardDescription></div><Badge v-if="isPreview" variant="secondary">Preview data</Badge><Badge v-else variant="outline">{{ trendData.length }} periods</Badge></div></CardHeader>
          <CardContent>
            <ChartContainer v-if="trendData.length" :config="chartConfig" class="h-72 w-full"><VisXYContainer :data="trendData" :y-domain="[0, 100]"><VisAxis type="x" :x="trendX" :tick-format="weekTick" /><VisAxis type="y" :tick-format="percentTick" /><VisLine :x="trendX" :y="productivityY" :color="chartConfig.productivity.color" /><VisLine :x="trendX" :y="complianceY" :color="chartConfig.compliance.color" /><VisLine :x="trendX" :y="qualityY" :color="chartConfig.quality.color" /><ChartTooltip /></VisXYContainer><ChartTooltipContent /></ChartContainer>
            <p v-else class="py-16 text-center text-sm text-muted-foreground">No trend data is available for this filter.</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><div class="flex items-start justify-between gap-3"><div><CardTitle>Attention needed</CardTitle><CardDescription>Grouped findings with supporting records.</CardDescription></div><Badge v-if="isPreview" variant="secondary">Preview data</Badge><Badge v-else variant="outline">{{ analysis?.alerts.length ?? 0 }} alerts</Badge></div></CardHeader>
          <CardContent class="flex flex-col gap-4">
            <template v-if="isPreview"><Alert variant="warning"><TriangleAlertIcon aria-hidden="true" /><AlertTitle>EMP-029 has insufficient evidence</AlertTitle><AlertDescription>Overall score and tier are withheld. Supporting records: PRJ-1237, QA-991.</AlertDescription></Alert><Alert><FileSpreadsheetIcon aria-hidden="true" /><AlertTitle>Reporting gap detected</AlertTitle><AlertDescription>One submitted-report period needs review for EMP-018.</AlertDescription></Alert></template>
            <Alert v-for="alert in visibleAlerts" v-else :key="`${alert.employee_id}-${alert.code}`" :variant="alert.severity === 'info' ? 'default' : 'warning'"><TriangleAlertIcon v-if="alert.severity !== 'info'" aria-hidden="true" /><FileSpreadsheetIcon v-else aria-hidden="true" /><AlertTitle class="capitalize">{{ alertTitle(alert) }} <Badge variant="outline">{{ alert.occurrence_count }}</Badge></AlertTitle><AlertDescription>{{ alert.message }}<span v-if="alert.record_ids.length" class="block">Records: {{ alertRecords(alert) }}</span><a v-if="alert.evidence_links[0]" class="text-primary underline-offset-4 hover:underline" :href="alert.evidence_links[0]" target="_blank" rel="noreferrer">Open evidence</a></AlertDescription></Alert>
            <p v-if="!isPreview && !visibleAlerts.length" class="py-8 text-center text-sm text-muted-foreground">No findings require attention for this filter.</p>
            <p v-if="!isPreview && (analysis?.alerts.length ?? 0) > visibleAlerts.length" class="text-xs text-muted-foreground">Showing the first {{ visibleAlerts.length }} grouped alerts.</p>
          </CardContent>
        </Card>
      </section>
    </div>
  </main>
</template>

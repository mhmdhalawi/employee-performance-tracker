<script setup lang="ts">
import { computed, ref } from 'vue'
import { VisAxis, VisLine, VisXYContainer } from '@unovis/vue'
import { ArrowLeftIcon, FileSpreadsheetIcon, ShieldCheckIcon, TriangleAlertIcon } from '@lucide/vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from '@/components/ui/chart'
import { Progress } from '@/components/ui/progress'
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { previewResults, previewTeams, previewTrends } from '@/data/dashboard-preview'
import type { AnalyzeResponse, EmployeeKpiResult } from '@/types/analysis'

const props = defineProps<{ analysis: AnalyzeResponse | null }>()
defineEmits<{ back: [] }>()

const employee = ref('all')
const team = ref('all')
const period = ref('12-weeks')
const isPreview = computed(() => !props.analysis)
const sourceRows = computed(() => props.analysis?.results ?? previewResults)
const teams = computed(() => [...new Set(sourceRows.value.map(row => previewTeams[row.employee_id]).filter(Boolean))])
const filteredRows = computed(() => sourceRows.value.filter(row =>
  (employee.value === 'all' || row.employee_id === employee.value)
  && (team.value === 'all' || previewTeams[row.employee_id] === team.value),
))
const scoredRows = computed(() => filteredRows.value.filter(row => row.overall_score !== null))
const averages = computed(() => ({
  overall: average(scoredRows.value.map(row => row.overall_score)),
  productivity: average(filteredRows.value.map(row => row.productivity_score)),
  compliance: average(filteredRows.value.map(row => row.compliance_score)),
  quality: average(filteredRows.value.map(row => row.quality_score)),
}))

const chartConfig = {
  productivity: { label: 'Productivity', color: 'var(--chart-1)' },
  compliance: { label: 'Compliance', color: 'var(--chart-2)' },
  quality: { label: 'Quality', color: 'var(--chart-3)' },
} satisfies ChartConfig

type TrendPoint = (typeof previewTrends)[number]
const trendX = (_point: TrendPoint, index: number) => index
const productivityY = (point: TrendPoint) => point.productivity
const complianceY = (point: TrendPoint) => point.compliance
const qualityY = (point: TrendPoint) => point.quality
const weekTick = (index: number) => previewTrends[index]?.week ?? ''
const percentTick = (value: number) => `${value}%`

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
</script>

<template>
  <main class="min-h-svh bg-muted/30">
    <header class="border-b bg-background">
      <div class="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
        <div class="flex items-center gap-3">
          <div class="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <ShieldCheckIcon class="size-4" aria-hidden="true" />
          </div>
          <div>
            <p class="font-semibold">Performance dashboard</p>
            <p class="text-xs text-muted-foreground">{{ analysis?.file_name ?? 'Dashboard design preview' }}</p>
          </div>
        </div>
        <Button variant="outline" @click="$emit('back')">
          <ArrowLeftIcon data-icon="inline-start" />
          New analysis
        </Button>
      </div>
    </header>

    <div class="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6">
      <section class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div class="flex flex-col gap-2">
          <div class="flex flex-wrap items-center gap-2">
            <h1 class="text-2xl font-semibold tracking-tight">Employee performance</h1>
            <Badge v-if="isPreview" variant="secondary">Preview data</Badge>
          </div>
          <p class="text-sm text-muted-foreground">Review KPI scores, evidence confidence, trends, and findings.</p>
        </div>
        <div class="grid gap-3 sm:grid-cols-3">
          <Select v-model="employee">
            <SelectTrigger class="w-full sm:w-48"><SelectValue placeholder="Employee" /></SelectTrigger>
            <SelectContent><SelectGroup><SelectItem value="all">All employees</SelectItem><SelectItem v-for="row in sourceRows" :key="row.employee_id" :value="row.employee_id">{{ employeeLabel(row) }}</SelectItem></SelectGroup></SelectContent>
          </Select>
          <Select v-model="team">
            <SelectTrigger class="w-full sm:w-44"><SelectValue placeholder="Team" /></SelectTrigger>
            <SelectContent><SelectGroup><SelectItem value="all">All teams</SelectItem><SelectItem v-for="item in teams" :key="item" :value="item">{{ item }}</SelectItem></SelectGroup></SelectContent>
          </Select>
          <Select v-model="period">
            <SelectTrigger class="w-full sm:w-40"><SelectValue placeholder="Period" /></SelectTrigger>
            <SelectContent><SelectGroup><SelectItem value="4-weeks">Last 4 weeks</SelectItem><SelectItem value="8-weeks">Last 8 weeks</SelectItem><SelectItem value="12-weeks">Last 12 weeks</SelectItem></SelectGroup></SelectContent>
          </Select>
        </div>
      </section>

      <p class="text-xs text-muted-foreground">
        <Badge variant="outline" class="mr-2">Contract pending</Badge>
        Team assignments and period-based recalculation are UI placeholders until the API returns those fields.
      </p>

      <section class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card v-for="item in [
          ['Overall score', averages.overall, 'Scored employees only'],
          ['Productivity', averages.productivity, '35% of overall'],
          ['Compliance', averages.compliance, '30% of overall'],
          ['Quality', averages.quality, '35% of overall'],
        ]" :key="item[0] as string">
          <CardHeader class="pb-2"><CardDescription>{{ item[0] }}</CardDescription><CardTitle class="text-3xl">{{ score(item[1] as number | null) }}</CardTitle></CardHeader>
          <CardContent class="text-xs text-muted-foreground">{{ item[2] }}</CardContent>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div><CardTitle>Employee results</CardTitle><CardDescription>Component scores remain visible when overall scoring is withheld.</CardDescription></div>
            <Badge variant="outline">{{ filteredRows.length }} employees</Badge>
          </div>
        </CardHeader>
        <CardContent class="overflow-x-auto">
          <Table>
            <TableHeader><TableRow><TableHead>Employee</TableHead><TableHead>Team</TableHead><TableHead class="text-right">Productivity</TableHead><TableHead class="text-right">Compliance</TableHead><TableHead class="text-right">Quality</TableHead><TableHead class="min-w-36">Confidence</TableHead><TableHead class="text-right">Overall</TableHead><TableHead>Status</TableHead></TableRow></TableHeader>
            <TableBody>
              <TableRow v-for="row in filteredRows" :key="row.employee_id">
                <TableCell><div class="font-medium">{{ employeeLabel(row) }}</div><div class="text-xs text-muted-foreground">{{ row.employee_id }}</div></TableCell>
                <TableCell><span v-if="previewTeams[row.employee_id]">{{ previewTeams[row.employee_id] }}</span><span v-else class="text-muted-foreground">Not provided</span></TableCell>
                <TableCell class="text-right tabular-nums">{{ score(row.productivity_score) }}</TableCell>
                <TableCell class="text-right tabular-nums">{{ score(row.compliance_score) }}</TableCell>
                <TableCell class="text-right tabular-nums">{{ score(row.quality_score) }}</TableCell>
                <TableCell><div class="flex items-center gap-2"><Progress :model-value="row.data_confidence" class="w-20" /><span class="text-xs tabular-nums">{{ row.data_confidence.toFixed(0) }}%</span></div></TableCell>
                <TableCell class="text-right font-medium tabular-nums">{{ score(row.overall_score) }}</TableCell>
                <TableCell><Badge :variant="row.overall_score === null ? 'secondary' : 'outline'">{{ row.performance_tier ?? row.result_status }}</Badge></TableCell>
              </TableRow>
              <TableRow v-if="!filteredRows.length"><TableCell colspan="8" class="h-24 text-center text-muted-foreground">No employees match these filters.</TableCell></TableRow>
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <section class="grid gap-6 xl:grid-cols-[2fr_1fr]">
        <Card>
          <CardHeader><div class="flex items-start justify-between gap-3"><div><CardTitle>12-week KPI trend</CardTitle><CardDescription>Weekly team averages across the selected period.</CardDescription></div><Badge variant="secondary">Preview data</Badge></div></CardHeader>
          <CardContent>
            <ChartContainer :config="chartConfig" class="h-72 w-full">
              <VisXYContainer :data="previewTrends" :y-domain="[60, 100]">
                <VisAxis type="x" :x="trendX" :tick-format="weekTick" />
                <VisAxis type="y" :tick-format="percentTick" />
                <VisLine :x="trendX" :y="productivityY" :color="chartConfig.productivity.color" />
                <VisLine :x="trendX" :y="complianceY" :color="chartConfig.compliance.color" />
                <VisLine :x="trendX" :y="qualityY" :color="chartConfig.quality.color" />
                <ChartTooltip />
              </VisXYContainer>
              <ChartTooltipContent />
            </ChartContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><div class="flex items-start justify-between gap-3"><div><CardTitle>Attention needed</CardTitle><CardDescription>Evidence-backed findings to review.</CardDescription></div><Badge variant="secondary">Preview data</Badge></div></CardHeader>
          <CardContent class="flex flex-col gap-4">
            <div class="flex gap-3 rounded-lg border p-3"><TriangleAlertIcon class="mt-0.5 size-4 shrink-0 text-amber-600" /><div class="flex flex-col gap-1"><p class="text-sm font-medium">EMP-029 has insufficient evidence</p><p class="text-xs text-muted-foreground">Overall score and tier are withheld. Supporting records: PRJ-1237, QA-991.</p></div></div>
            <div class="flex gap-3 rounded-lg border p-3"><FileSpreadsheetIcon class="mt-0.5 size-4 shrink-0 text-muted-foreground" /><div class="flex flex-col gap-1"><p class="text-sm font-medium">Reporting gap detected</p><p class="text-xs text-muted-foreground">One submitted-report period needs review for EMP-018.</p></div></div>
          </CardContent>
        </Card>
      </section>
    </div>
  </main>
</template>

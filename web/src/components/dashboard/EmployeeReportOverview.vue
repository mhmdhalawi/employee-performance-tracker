<script setup lang="ts">
import { computed } from 'vue'
import { CalendarDaysIcon } from '@lucide/vue'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import EmployeeManagerSummary from '@/components/dashboard/EmployeeManagerSummary.vue'
import WeeklyKpiTrend from '@/components/dashboard/WeeklyKpiTrend.vue'
import { formatDate } from '@/lib/date-format'
import type { EvidenceKpi } from '@/types/employee-evidence'
import type { EmployeeReportData } from '@/types/reports'

const props = defineProps<{ report: EmployeeReportData }>()

const initials = computed(() => {
  const name = props.report.employee_name?.trim() || props.report.employee_id
  return name.split(/\s+/).slice(0, 2).map(part => part[0]?.toUpperCase()).join('')
})
const scoreCards = computed(() => [
  { label: 'Overall score', score: props.report.overall_score, detail: props.report.performance_tier ?? props.report.result_status, tone: 'bg-primary' },
  ...props.report.kpis.map(kpi => ({
    label: kpi.name,
    score: kpi.score,
    detail: `${kpi.weight}% of overall`,
    tone: kpi.name === 'Compliance' ? 'bg-chart-2' : kpi.name === 'Quality' ? 'bg-chart-3' : 'bg-chart-1',
  })),
])

function score(value: number | null): string {
  return value === null ? '—' : `${value.toFixed(1)}%`
}

function evidenceCount(name: string): number {
  return props.report.evidence_tables[name.toLowerCase() as EvidenceKpi].total_count
}
</script>

<template>
  <div class="flex min-w-0 flex-col gap-5">
    <header class="flex flex-col gap-4 rounded-xl border bg-background p-5 xl:flex-row xl:items-start xl:justify-between">
      <div class="flex min-w-0 items-start gap-4">
        <div class="flex size-14 shrink-0 items-center justify-center rounded-full bg-secondary text-base font-semibold text-secondary-foreground" aria-hidden="true">{{ initials }}</div>
        <div class="flex min-w-0 flex-col gap-1">
          <p class="text-sm font-medium text-muted-foreground">Employee performance details</p>
          <div class="flex flex-wrap items-center gap-2">
            <h3 class="wrap-break-word text-2xl font-semibold tracking-tight">{{ report.employee_name || report.employee_id }}</h3>
            <Badge :variant="report.overall_score === null ? 'warning' : 'success'">{{ report.performance_tier ?? report.result_status }}</Badge>
          </div>
          <p class="text-sm text-muted-foreground">{{ report.employee_id }}<template v-if="report.team"> · {{ report.team }}</template><template v-if="report.role"> · {{ report.role }}</template></p>
        </div>
      </div>
      <div class="flex shrink-0 flex-col gap-1 text-sm xl:items-end">
        <span class="text-xs text-muted-foreground">Reporting period</span>
        <span class="flex items-center gap-2 font-medium"><CalendarDaysIcon class="size-4 text-muted-foreground" aria-hidden="true" />{{ formatDate(report.period.start_date) }} – {{ formatDate(report.period.end_date) }}</span>
        <span v-if="report.period.score_period_start_date && report.period.score_period_end_date && (report.period.score_period_start_date !== report.period.start_date || report.period.score_period_end_date !== report.period.end_date)" class="text-xs text-muted-foreground">Scores use {{ formatDate(report.period.score_period_start_date) }} – {{ formatDate(report.period.score_period_end_date) }}</span>
      </div>
    </header>

    <section aria-label="Report score summary" class="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
      <Card v-for="item in scoreCards" :key="item.label" class="min-w-0 justify-between">
        <CardHeader class="gap-2">
          <CardDescription class="flex items-center gap-2"><span class="size-2 shrink-0 rounded-full" :class="item.tone" aria-hidden="true" />{{ item.label }}</CardDescription>
          <CardTitle class="text-2xl tabular-nums sm:text-3xl">{{ score(item.score) }}</CardTitle>
        </CardHeader>
        <CardContent class="text-xs text-muted-foreground">{{ item.detail }}</CardContent>
      </Card>
      <Card class="col-span-2 min-w-0 justify-between sm:col-span-1">
        <CardHeader class="gap-2"><CardDescription>Data confidence</CardDescription><CardTitle class="text-2xl tabular-nums sm:text-3xl">{{ score(report.data_confidence) }}</CardTitle></CardHeader>
        <CardContent class="flex flex-col gap-2">
          <Progress :model-value="report.data_confidence" :tone="report.overall_score === null ? 'warning' : 'default'" aria-label="Report data confidence" />
          <p class="text-xs text-muted-foreground">{{ report.overall_score === null ? 'Overall score withheld' : 'Overall scoring eligible' }} · {{ score(report.confidence_threshold) }} required</p>
        </CardContent>
      </Card>
    </section>

    <div class="grid items-start gap-3 xl:items-stretch xl:grid-cols-[minmax(0,2fr)_minmax(20rem,1fr)]">
      <div class="flex min-w-0 flex-col gap-3 xl:h-full">
        <Card aria-label="Performance explained">
          <CardHeader>
            <CardTitle><h3>Performance explained</h3></CardTitle>
            <CardDescription>Snapshot KPI scores, overall weights, and selected-period records.</CardDescription>
          </CardHeader>
          <CardContent>
            <div class="overflow-x-auto">
              <Table class="min-w-lg">
                <TableHeader><TableRow><TableHead>KPI</TableHead><TableHead class="text-right">Employee</TableHead><TableHead class="text-right">Overall weight</TableHead><TableHead class="text-right">Records</TableHead></TableRow></TableHeader>
                <TableBody>
                  <TableRow v-for="kpi in report.kpis" :key="kpi.name">
                    <TableCell class="font-medium">{{ kpi.name }}</TableCell>
                    <TableCell class="text-right tabular-nums">{{ score(kpi.score) }}</TableCell>
                    <TableCell class="text-right tabular-nums">{{ kpi.weight }}%</TableCell>
                    <TableCell class="text-right"><a :href="`#report-${kpi.name.toLowerCase()}-evidence`" class="text-primary underline underline-offset-4 focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-ring">View evidence ({{ evidenceCount(kpi.name) }})</a></TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell class="font-semibold">Overall result</TableCell>
                    <TableCell class="text-right font-semibold tabular-nums">{{ score(report.overall_score) }}</TableCell>
                    <TableCell class="text-right tabular-nums">100%</TableCell>
                    <TableCell class="text-right text-muted-foreground">—</TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
        <WeeklyKpiTrend :trends="report.trends" scale="detail" compact-on-desktop description="This employee and the report period apply. Gaps mean no score is available." />
      </div>
      <EmployeeManagerSummary :employee="report" :alerts="report.findings" :show-evidence-link="false" />
    </div>
  </div>
</template>

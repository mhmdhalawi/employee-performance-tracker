<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  CalendarDaysIcon,
  CircleAlertIcon,
  DownloadIcon,
  FileTextIcon,
  ShieldCheckIcon,
  TriangleAlertIcon,
  UsersIcon,
} from '@lucide/vue'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import ReportPreviewContent from '@/components/dashboard/ReportPreviewContent.vue'
import WeeklyKpiTrend from '@/components/dashboard/WeeklyKpiTrend.vue'
import { Spinner } from '@/components/ui/spinner'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { downloadTeamReportPdf } from '@/lib/dashboard-report-pdf'
import { formatDate } from '@/lib/date-format'
import type { DashboardResponse } from '@/types/analysis'

const props = defineProps<{
  analysis: DashboardResponse
  open: boolean
}>()
const emit = defineEmits<{
  'update:open': [open: boolean]
}>()

const downloading = ref(false)
const error = ref('')

const kpis = [
  { key: 'average_productivity_score', label: 'Productivity', weight: '35% of overall', tone: 'bg-chart-1' },
  { key: 'average_compliance_score', label: 'Compliance', weight: '30% of overall', tone: 'bg-chart-2' },
  { key: 'average_quality_score', label: 'Quality', weight: '35% of overall', tone: 'bg-chart-3' },
] as const
const activeScope = computed(() => (
  [
    ['Team', props.analysis.applied_filters.team],
    ['Campaign', props.analysis.applied_filters.campaign],
    ['Queue', props.analysis.applied_filters.queue],
    ['Shift', props.analysis.applied_filters.shift],
    ['Supervisor', props.analysis.applied_filters.supervisor],
    ['Location', props.analysis.applied_filters.location],
  ] as const
).filter(([, value]) => Boolean(value)))

watch(() => props.open, (open) => {
  if (open)
    error.value = ''
})

async function downloadReport(): Promise<void> {
  if (downloading.value)
    return

  downloading.value = true
  error.value = ''
  try {
    await downloadTeamReportPdf(props.analysis)
  }
  catch {
    error.value = 'The team PDF could not be created in this browser.'
  }
  finally {
    downloading.value = false
  }
}

function score(value: number | null): string {
  return value === null ? '—' : `${value.toFixed(1)}%`
}

function employeeLabel(employeeName: string | null, employeeId: string): string {
  return employeeName || employeeId
}
</script>

<template>
  <Dialog :open="open" @update:open="emit('update:open', $event)">
    <ReportPreviewContent>
      <template #header>
      <DialogHeader class="px-6 pt-6 pb-5">
        <div class="flex items-center gap-3">
          <div class="flex size-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <FileTextIcon aria-hidden="true" />
          </div>
          <div class="flex flex-col gap-1">
            <DialogTitle>Call-center performance report</DialogTitle>
            <DialogDescription>Review the current filtered dashboard snapshot before downloading.</DialogDescription>
          </div>
        </div>
      </DialogHeader>
      </template>


        <Alert v-if="error" variant="destructive">
          <CircleAlertIcon aria-hidden="true" />
          <AlertTitle>Report unavailable</AlertTitle>
          <AlertDescription>{{ error }}</AlertDescription>
        </Alert>

        <Alert v-if="analysis.summary.insufficient_data_count" variant="warning">
          <TriangleAlertIcon aria-hidden="true" />
          <AlertTitle>{{ analysis.summary.insufficient_data_count }} result{{ analysis.summary.insufficient_data_count === 1 ? '' : 's' }} withheld</AlertTitle>
          <AlertDescription>
            Employees below the required data confidence threshold keep their component KPIs, but no overall result or tier is shown.
          </AlertDescription>
        </Alert>

        <Card>
          <CardHeader class="gap-3 sm:flex sm:flex-row sm:items-start sm:justify-between">
            <div class="flex min-w-0 flex-col gap-2">
              <div class="flex flex-wrap items-center gap-2">
                <CardTitle class="text-2xl">{{ analysis.applied_filters.team || 'Call-center performance' }}</CardTitle>
                <Badge variant="secondary"><UsersIcon data-icon="inline-start" />{{ analysis.summary.total_employee_count }} employees</Badge>
              </div>
              <CardDescription>{{ analysis.summary.scored_employee_count }} scored · {{ analysis.summary.insufficient_data_count }} withheld · Current dashboard snapshot</CardDescription>
              <div v-if="activeScope.length" class="flex flex-wrap gap-2" aria-label="Applied report filters">
                <Badge v-for="[label, value] in activeScope" :key="label" variant="outline" class="max-w-full whitespace-normal wrap-break-word">{{ label }}: {{ value }}</Badge>
              </div>
              <CardDescription v-if="analysis.applied_filters.score_period_start_date && analysis.applied_filters.score_period_end_date && (analysis.applied_filters.score_period_start_date !== analysis.applied_filters.start_date || analysis.applied_filters.score_period_end_date !== analysis.applied_filters.end_date)">
                Scores use available evidence: {{ formatDate(analysis.applied_filters.score_period_start_date) }} – {{ formatDate(analysis.applied_filters.score_period_end_date) }}.
              </CardDescription>
            </div>
            <Badge v-if="analysis.applied_filters.start_date && analysis.applied_filters.end_date" variant="outline" class="w-fit shrink-0 whitespace-normal">
              <CalendarDaysIcon data-icon="inline-start" />
              {{ formatDate(analysis.applied_filters.start_date) }} – {{ formatDate(analysis.applied_filters.end_date) }}
            </Badge>
          </CardHeader>
        </Card>

        <section aria-label="Team KPI averages" class="grid grid-cols-2 gap-3 xl:grid-cols-4">
          <Card class="min-w-0 justify-between">
            <CardHeader class="gap-2">
              <CardDescription class="flex items-center gap-2"><span class="size-2 shrink-0 rounded-full bg-primary" aria-hidden="true" />Overall score</CardDescription>
              <CardTitle class="text-2xl tabular-nums sm:text-3xl">{{ score(analysis.summary.average_overall_score) }}</CardTitle>
            </CardHeader>
            <CardContent class="text-xs text-muted-foreground">{{ analysis.summary.scored_employee_count }} scored · {{ analysis.summary.insufficient_data_count }} withheld</CardContent>
          </Card>
          <Card v-for="kpi in kpis" :key="kpi.key" class="min-w-0 justify-between">
            <CardHeader class="gap-2">
              <CardDescription class="flex items-center gap-2"><span class="size-2 shrink-0 rounded-full" :class="kpi.tone" aria-hidden="true" />{{ kpi.label }}</CardDescription>
              <CardTitle class="text-2xl tabular-nums sm:text-3xl">{{ score(analysis.summary[kpi.key]) }}</CardTitle>
            </CardHeader>
            <CardContent class="text-xs text-muted-foreground">{{ analysis.summary.scored_employee_count }} scored · {{ kpi.weight }}</CardContent>
          </Card>
        </section>

        <WeeklyKpiTrend :trends="analysis.trends" description="Scores across the selected employees and reporting period. Gaps mean no score is available." />

        <Card>
          <CardHeader>
            <CardTitle>Employee results</CardTitle>
            <CardDescription>All employees in the current dashboard filters are included in the download.</CardDescription>
          </CardHeader>
          <CardContent class="overflow-x-auto">
            <Table class="min-w-220">
              <TableHeader>
                <TableRow>
                  <TableHead>Employee</TableHead>
                  <TableHead>Campaign / Queue</TableHead>
                  <TableHead class="text-right">Productivity</TableHead>
                  <TableHead class="text-right">Compliance</TableHead>
                  <TableHead class="text-right">Quality</TableHead>
                  <TableHead>Data confidence</TableHead>
                  <TableHead class="text-right">Overall</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow v-for="employee in analysis.results" :key="employee.employee_id">
                  <TableCell><p class="font-medium">{{ employeeLabel(employee.employee_name, employee.employee_id) }}</p><p class="text-xs text-muted-foreground">{{ employee.employee_id }}</p></TableCell>
                  <TableCell class="whitespace-normal wrap-break-word"><span>{{ employee.campaign || 'Campaign not provided' }}</span><span class="block text-xs text-muted-foreground">{{ employee.queue || 'Queue not provided' }}</span></TableCell>
                  <TableCell class="text-right tabular-nums">{{ score(employee.productivity_score) }}</TableCell>
                  <TableCell class="text-right tabular-nums">{{ score(employee.compliance_score) }}</TableCell>
                  <TableCell class="text-right tabular-nums">{{ score(employee.quality_score) }}</TableCell>
                  <TableCell class="tabular-nums">{{ score(employee.data_confidence) }}</TableCell>
                  <TableCell class="text-right font-medium tabular-nums">{{ score(employee.overall_score) }}</TableCell>
                  <TableCell><Badge :variant="employee.overall_score === null ? 'warning' : 'success'">{{ employee.performance_tier || employee.result_status }}</Badge></TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </CardContent>
        </Card>

      <template #footer>
      <DialogFooter class="m-0 rounded-none">
        <Button :disabled="downloading" @click="downloadReport">
          <Spinner v-if="downloading" data-icon="inline-start" />
          <DownloadIcon v-else data-icon="inline-start" />
          {{ downloading ? 'Creating PDF…' : 'Download Cedar PDF' }}
        </Button>
      </DialogFooter>
      </template>
    </ReportPreviewContent>
  </Dialog>
</template>

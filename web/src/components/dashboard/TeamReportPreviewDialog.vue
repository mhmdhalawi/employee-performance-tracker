<script setup lang="ts">
import { ref, watch } from 'vue'
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
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Progress } from '@/components/ui/progress'
import { Spinner } from '@/components/ui/spinner'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { downloadTeamReportPdf } from '@/lib/dashboard-report-pdf'
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
  { key: 'average_productivity_score', label: 'Productivity', weight: '35% of overall' },
  { key: 'average_compliance_score', label: 'Compliance', weight: '30% of overall' },
  { key: 'average_quality_score', label: 'Quality', weight: '35% of overall' },
] as const

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

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeZone: 'UTC' })
    .format(new Date(`${value}T00:00:00Z`))
}

function employeeLabel(employeeName: string | null, employeeId: string): string {
  return employeeName || employeeId
}
</script>

<template>
  <Dialog :open="open" @update:open="emit('update:open', $event)">
    <DialogContent class="max-h-[92svh] gap-0 overflow-hidden p-0 sm:max-w-6xl">
      <DialogHeader class="px-6 pt-6 pb-5">
        <div class="flex items-center gap-3">
          <div class="flex size-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <FileTextIcon aria-hidden="true" />
          </div>
          <div class="flex flex-col gap-1">
            <DialogTitle>Team performance report</DialogTitle>
            <DialogDescription>Review the current filtered dashboard snapshot before downloading.</DialogDescription>
          </div>
        </div>
      </DialogHeader>

      <div class="flex max-h-[calc(92svh-9rem)] flex-col gap-5 overflow-y-auto bg-muted/30 p-6">
        <Alert v-if="error" variant="destructive">
          <CircleAlertIcon aria-hidden="true" />
          <AlertTitle>Report unavailable</AlertTitle>
          <AlertDescription>{{ error }}</AlertDescription>
        </Alert>

        <Alert v-if="analysis.summary.insufficient_data_count" variant="warning">
          <TriangleAlertIcon aria-hidden="true" />
          <AlertTitle>{{ analysis.summary.insufficient_data_count }} result{{ analysis.summary.insufficient_data_count === 1 ? '' : 's' }} withheld</AlertTitle>
          <AlertDescription>
            Employees below the evidence threshold keep their component KPIs, but no overall result or tier is shown.
          </AlertDescription>
        </Alert>

        <Card>
          <CardHeader class="gap-4 sm:flex sm:flex-row sm:items-start sm:justify-between">
            <div class="flex flex-col gap-1">
              <div class="flex flex-wrap items-center gap-2">
                <p class="text-sm font-medium text-muted-foreground">CEDAR PERFORMANCE</p>
                <Badge variant="secondary">
                  <UsersIcon data-icon="inline-start" />
                  {{ analysis.summary.total_employee_count }} employees
                </Badge>
              </div>
              <CardTitle class="text-3xl">{{ analysis.applied_filters.team || 'All teams' }}</CardTitle>
              <CardDescription>Current dashboard filters are applied to every value in this preview.</CardDescription>
            </div>
            <Badge v-if="analysis.applied_filters.start_date && analysis.applied_filters.end_date" variant="outline" class="w-fit">
              <CalendarDaysIcon data-icon="inline-start" />
              {{ formatDate(analysis.applied_filters.start_date) }} – {{ formatDate(analysis.applied_filters.end_date) }}
            </Badge>
          </CardHeader>
          <CardContent class="grid gap-4 md:grid-cols-[minmax(0,1.1fr)_repeat(2,minmax(0,0.7fr))]">
            <section class="flex flex-col justify-between gap-5 rounded-lg bg-primary p-5 text-primary-foreground">
              <div class="flex flex-col gap-1">
                <p class="text-sm text-primary-foreground/75">Average overall score</p>
                <p class="text-5xl font-semibold tracking-tight tabular-nums">{{ score(analysis.summary.average_overall_score) }}</p>
              </div>
              <p class="text-xs text-primary-foreground/80">Scored employees only</p>
            </section>
            <section class="flex flex-col justify-center gap-2 rounded-lg border p-5">
              <p class="text-sm text-muted-foreground">Scored results</p>
              <p class="text-3xl font-semibold tabular-nums">{{ analysis.summary.scored_employee_count }}</p>
              <Progress :model-value="analysis.summary.total_employee_count ? analysis.summary.scored_employee_count / analysis.summary.total_employee_count * 100 : 0" />
            </section>
            <section class="flex flex-col justify-center gap-2 rounded-lg border p-5">
              <p class="text-sm text-muted-foreground">Withheld results</p>
              <p class="text-3xl font-semibold tabular-nums">{{ analysis.summary.insufficient_data_count }}</p>
              <p class="text-xs text-muted-foreground">Insufficient evidence</p>
            </section>
          </CardContent>
        </Card>

        <section aria-label="Team KPI averages" class="grid gap-4 md:grid-cols-3">
          <Card v-for="kpi in kpis" :key="kpi.key">
            <CardHeader>
              <CardDescription>{{ kpi.label }}</CardDescription>
              <CardTitle class="text-3xl tabular-nums">{{ score(analysis.summary[kpi.key]) }}</CardTitle>
            </CardHeader>
            <CardContent class="text-xs text-muted-foreground">{{ kpi.weight }}</CardContent>
          </Card>
        </section>

        <Card>
          <CardHeader>
            <CardTitle>Employee results</CardTitle>
            <CardDescription>The downloaded report also includes the complete weekly KPI trend.</CardDescription>
          </CardHeader>
          <CardContent class="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Employee</TableHead>
                  <TableHead>Team</TableHead>
                  <TableHead class="text-right">Productivity</TableHead>
                  <TableHead class="text-right">Compliance</TableHead>
                  <TableHead class="text-right">Quality</TableHead>
                  <TableHead class="text-right">Overall</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow v-for="employee in analysis.results" :key="employee.employee_id">
                  <TableCell><p class="font-medium">{{ employeeLabel(employee.employee_name, employee.employee_id) }}</p><p class="text-xs text-muted-foreground">{{ employee.employee_id }}</p></TableCell>
                  <TableCell>{{ employee.team || 'Not provided' }}</TableCell>
                  <TableCell class="text-right tabular-nums">{{ score(employee.productivity_score) }}</TableCell>
                  <TableCell class="text-right tabular-nums">{{ score(employee.compliance_score) }}</TableCell>
                  <TableCell class="text-right tabular-nums">{{ score(employee.quality_score) }}</TableCell>
                  <TableCell class="text-right font-medium tabular-nums">{{ score(employee.overall_score) }}</TableCell>
                  <TableCell><Badge :variant="employee.overall_score === null ? 'warning' : 'success'">{{ employee.performance_tier || employee.result_status }}</Badge></TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Alert>
          <ShieldCheckIcon aria-hidden="true" />
          <AlertTitle>Manager review required</AlertTitle>
          <AlertDescription>
            This report supports coaching and manager review. It must not be used alone for hiring, termination, promotion, compensation, or disciplinary decisions.
          </AlertDescription>
        </Alert>
      </div>

      <DialogFooter class="m-0 rounded-none">
        <Button :disabled="downloading" @click="downloadReport">
          <Spinner v-if="downloading" data-icon="inline-start" />
          <DownloadIcon v-else data-icon="inline-start" />
          {{ downloading ? 'Creating PDF…' : 'Download Cedar PDF' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

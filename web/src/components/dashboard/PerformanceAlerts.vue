<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ArrowLeftIcon, FileSpreadsheetIcon, ShieldCheckIcon, TriangleAlertIcon } from '@lucide/vue'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Pagination, PaginationContent, PaginationNext, PaginationPrevious } from '@/components/ui/pagination'
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import type { PerformanceAlert } from '@/types/analysis'

const props = defineProps<{
  alerts: PerformanceAlert[]
  fileName: string
}>()
const emit = defineEmits<{
  back: []
}>()

const page = ref(1)
const severity = ref('all')
const team = ref('all')
const employee = ref('all')
const code = ref('all')
const pageSize = 10

const teams = computed(() => [...new Set(
  props.alerts.map(alert => alert.team).filter((value): value is string => Boolean(value)),
)].sort())
const employees = computed(() => {
  const options = new Map<string, string>()
  for (const alert of props.alerts) {
    if (alert.employee_id)
      options.set(alert.employee_id, alert.employee_name || alert.employee_id)
  }
  return [...options.entries()].sort((left, right) => left[1].localeCompare(right[1]))
})
const codes = computed(() => [...new Set(props.alerts.map(alert => alert.code))].sort())
const filteredAlerts = computed(() => props.alerts.filter(alert =>
  (severity.value === 'all' || alert.severity === severity.value)
  && (team.value === 'all' || alert.team === team.value)
  && (employee.value === 'all' || alert.employee_id === employee.value)
  && (code.value === 'all' || alert.code === code.value),
))
const paginatedAlerts = computed(() => {
  const start = (page.value - 1) * pageSize
  return filteredAlerts.value.slice(start, start + pageSize)
})
const occurrenceCount = computed(() => filteredAlerts.value.reduce(
  (total, alert) => total + alert.occurrence_count,
  0,
))
const firstVisibleAlert = computed(() => filteredAlerts.value.length ? (page.value - 1) * pageSize + 1 : 0)
const lastVisibleAlert = computed(() => Math.min(page.value * pageSize, filteredAlerts.value.length))
const pageCount = computed(() => Math.max(1, Math.ceil(filteredAlerts.value.length / pageSize)))

watch([severity, team, employee, code], () => {
  page.value = 1
})

function alertTitle(alert: PerformanceAlert): string {
  return `${alert.employee_name || alert.employee_id || 'Dataset'} · ${alertCodeLabel(alert.code)}`
}

function alertCodeLabel(value: string): string {
  return value.replaceAll('_', ' ')
}

function alertRecords(alert: PerformanceAlert): string {
  const preview = alert.record_ids.slice(0, 4).join(', ')
  const remaining = alert.record_ids.length - 4
  return remaining > 0 ? `${preview} +${remaining} more` : preview
}
</script>

<template>
  <main class="min-h-svh bg-muted/30">
    <header class="border-b bg-background">
      <div class="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
        <div class="flex min-w-0 items-center gap-3">
          <div class="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <ShieldCheckIcon aria-hidden="true" />
          </div>
          <div class="min-w-0">
            <p class="font-semibold">Performance alerts</p>
            <p class="truncate text-xs text-muted-foreground">{{ fileName }}</p>
          </div>
        </div>
        <Button variant="outline" @click="emit('back')">
          <ArrowLeftIcon data-icon="inline-start" />
          Back to dashboard
        </Button>
      </div>
    </header>

    <div class="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6">
      <section class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div class="flex flex-col gap-2">
          <div class="flex flex-wrap items-center gap-2">
            <h1 class="text-2xl font-semibold tracking-tight">All performance alerts</h1>
            <Badge variant="outline">{{ filteredAlerts.length }} grouped</Badge>
            <Badge variant="secondary">{{ occurrenceCount }} occurrences</Badge>
          </div>
          <p class="text-sm text-muted-foreground">
            Filter findings and inspect their supporting record IDs and evidence links.
          </p>
        </div>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Filter alerts</CardTitle>
          <CardDescription>Narrow the findings by severity, team, employee, or issue type.</CardDescription>
        </CardHeader>
        <CardContent class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Select v-model="severity">
            <SelectTrigger class="w-full" aria-label="Filter alerts by severity"><SelectValue placeholder="Severity" /></SelectTrigger>
            <SelectContent><SelectGroup><SelectItem value="all">All severities</SelectItem><SelectItem value="error">Error</SelectItem><SelectItem value="warning">Warning</SelectItem><SelectItem value="info">Information</SelectItem></SelectGroup></SelectContent>
          </Select>
          <Select v-model="team">
            <SelectTrigger class="w-full" aria-label="Filter alerts by team"><SelectValue placeholder="Team" /></SelectTrigger>
            <SelectContent><SelectGroup><SelectItem value="all">All teams</SelectItem><SelectItem v-for="item in teams" :key="item" :value="item">{{ item }}</SelectItem></SelectGroup></SelectContent>
          </Select>
          <Select v-model="employee">
            <SelectTrigger class="w-full" aria-label="Filter alerts by employee"><SelectValue placeholder="Employee" /></SelectTrigger>
            <SelectContent><SelectGroup><SelectItem value="all">All employees</SelectItem><SelectItem v-for="item in employees" :key="item[0]" :value="item[0]">{{ item[1] }}</SelectItem></SelectGroup></SelectContent>
          </Select>
          <Select v-model="code">
            <SelectTrigger class="w-full" aria-label="Filter alerts by issue type"><SelectValue placeholder="Issue type" /></SelectTrigger>
            <SelectContent><SelectGroup><SelectItem value="all">All issue types</SelectItem><SelectItem v-for="item in codes" :key="item" :value="item" class="capitalize">{{ alertCodeLabel(item) }}</SelectItem></SelectGroup></SelectContent>
          </Select>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle>Findings</CardTitle>
              <CardDescription>Grouped alerts with traceable supporting evidence.</CardDescription>
            </div>
            <Badge variant="outline">{{ filteredAlerts.length }} results</Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div class="mx-auto flex w-full max-w-5xl flex-col gap-3">
            <Alert v-for="alert in paginatedAlerts" :key="`${alert.employee_id}-${alert.code}`" :variant="alert.severity === 'info' ? 'default' : 'warning'">
              <TriangleAlertIcon v-if="alert.severity !== 'info'" aria-hidden="true" />
              <FileSpreadsheetIcon v-else aria-hidden="true" />
              <AlertTitle class="capitalize">{{ alertTitle(alert) }} <Badge variant="outline">{{ alert.occurrence_count }}</Badge></AlertTitle>
              <AlertDescription>
                {{ alert.message }}
                <span v-if="alert.record_ids.length" class="block">Records: {{ alertRecords(alert) }}</span>
                <a v-if="alert.evidence_links[0]" class="text-primary underline-offset-4 hover:underline" :href="alert.evidence_links[0]" target="_blank" rel="noreferrer">Open evidence</a>
              </AlertDescription>
            </Alert>
            <p v-if="!paginatedAlerts.length" class="py-16 text-center text-sm text-muted-foreground">No alerts match these filters.</p>
          </div>
        </CardContent>
        <CardFooter class="flex-col gap-3 border-t sm:flex-row sm:items-center sm:justify-between">
          <span class="whitespace-nowrap text-sm text-muted-foreground">{{ firstVisibleAlert }}–{{ lastVisibleAlert }} of {{ filteredAlerts.length }}</span>
          <Pagination v-model:page="page" :items-per-page="pageSize" :total="filteredAlerts.length" class="mx-0 w-auto">
            <PaginationContent>
              <PaginationPrevious />
              <span class="min-w-28 text-center text-sm text-muted-foreground">Page {{ page }} of {{ pageCount }}</span>
              <PaginationNext />
            </PaginationContent>
          </Pagination>
        </CardFooter>
      </Card>
    </div>
  </main>
</template>

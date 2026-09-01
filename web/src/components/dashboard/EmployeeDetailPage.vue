<script setup lang="ts">
import { computed } from 'vue'
import {
  ArrowLeftIcon,
  CircleAlertIcon,
  Clock3Icon,
  FileSpreadsheetIcon,
  LightbulbIcon,
  SparklesIcon,
  TriangleAlertIcon,
} from '@lucide/vue'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Separator } from '@/components/ui/separator'
import { Spinner } from '@/components/ui/spinner'
import type { EmployeeAIInsight, EmployeeKpiResult, PerformanceAlert } from '@/types/analysis'

const props = defineProps<{
  employee: EmployeeKpiResult
  alerts: PerformanceAlert[]
  insight: EmployeeAIInsight | null
  insightLoading: boolean
  insightError?: string
}>()
const emit = defineEmits<{
  back: []
  generateInsight: [employeeId: string]
}>()

const complianceBreakdown = computed(() => {
  const match = props.employee.compliance_reason.match(
    /attendance \(([^:]+): arrival ([^,]+), shift end ([^,]+), lunch ([^)]+)\), 35% reporting \(([^)]+)\), and 15% leave compliance \(([^)]+)\)/,
  )
  if (!match)
    return null

  return {
    attendance: match[1],
    arrival: match[2],
    shiftEnd: match[3],
    lunch: match[4],
    reporting: match[5],
    leave: match[6],
  }
})

const kpiCards = computed(() => [
  {
    label: 'Productivity',
    score: props.employee.productivity_score,
    reason: props.employee.productivity_reason,
    weight: '35% of overall',
  },
  {
    label: 'Compliance',
    score: props.employee.compliance_score,
    reason: props.employee.compliance_reason,
    weight: '30% of overall',
  },
  {
    label: 'Quality',
    score: props.employee.quality_score,
    reason: props.employee.quality_reason,
    weight: '35% of overall',
  },
])

function score(value: number | null): string {
  return value === null ? '—' : `${value.toFixed(1)}%`
}

function alertCodeLabel(code: string): string {
  return code.replaceAll('_', ' ')
}

function impactLabel(impact: string): string {
  const labels: Record<string, string> = {
    lowers_confidence: 'Lowers confidence',
    affects_score: 'Affects score',
    excluded_from_scoring: 'Excluded from scoring',
    blocks_score: 'Blocks score',
    none: 'No scoring impact',
  }
  return labels[impact] ?? alertCodeLabel(impact)
}

function impactVariant(impact: string): 'destructive' | 'outline' | 'secondary' | 'warning' {
  if (impact === 'blocks_score')
    return 'destructive'
  if (impact === 'lowers_confidence')
    return 'warning'
  if (impact === 'affects_score')
    return 'secondary'
  return 'outline'
}
</script>

<template>
  <main class="min-h-svh bg-muted/30">
    <header class="border-b bg-background">
      <div class="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
        <Button variant="ghost" @click="emit('back')">
          <ArrowLeftIcon data-icon="inline-start" />
          Back to dashboard
        </Button>
        <Badge :variant="employee.overall_score === null ? 'warning' : 'success'">
          {{ employee.performance_tier ?? employee.result_status }}
        </Badge>
      </div>
    </header>

    <div class="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8">
      <header class="flex flex-col gap-2">
        <p class="text-sm font-medium text-muted-foreground">Employee performance details</p>
        <h1 class="text-3xl font-semibold tracking-tight">
          {{ employee.employee_name || employee.employee_id }}
        </h1>
        <p class="text-sm text-muted-foreground">
          {{ employee.employee_id }} · {{ employee.team ?? 'Team not provided' }}<template v-if="employee.role"> · {{ employee.role }}</template>
        </p>
      </header>

      <Card>
        <CardHeader class="gap-4 sm:flex sm:flex-row sm:items-center sm:justify-between">
          <div class="flex flex-col gap-1">
            <CardDescription>Overall score</CardDescription>
            <CardTitle class="text-4xl tabular-nums">{{ score(employee.overall_score) }}</CardTitle>
          </div>
          <div class="flex w-full max-w-md flex-col gap-2">
            <div class="flex items-center justify-between gap-3 text-sm">
              <span class="text-muted-foreground">Evidence confidence</span>
              <span class="font-medium tabular-nums">{{ employee.data_confidence.toFixed(1) }}%</span>
            </div>
            <Progress :model-value="employee.data_confidence" />
            <p class="text-xs text-muted-foreground">
              Required threshold: {{ employee.confidence_threshold.toFixed(1) }}%
            </p>
          </div>
        </CardHeader>
      </Card>

      <Alert v-if="employee.overall_score === null" variant="warning">
        <TriangleAlertIcon aria-hidden="true" />
        <AlertTitle>Insufficient evidence for an overall result</AlertTitle>
        <AlertDescription>
          Overall performance and tier were withheld because evidence confidence is below the
          required threshold. Component KPI values remain visible for auditability and should
          not be treated as a complete performance assessment.
        </AlertDescription>
      </Alert>

      <section aria-label="KPI scores" class="grid gap-4 md:grid-cols-3">
        <Card v-for="item in kpiCards" :key="item.label">
          <CardHeader>
            <CardDescription>{{ item.label }} · {{ item.weight }}</CardDescription>
            <CardTitle class="text-3xl tabular-nums">{{ score(item.score) }}</CardTitle>
          </CardHeader>
          <CardContent class="text-sm text-muted-foreground">{{ item.reason }}</CardContent>
        </Card>
      </section>

      <div class="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(22rem,0.9fr)]">
        <div class="grid min-w-0 content-start gap-6">
          <Card class="lg:min-h-44">
            <CardHeader>
              <CardTitle class="flex items-center gap-2">
                <FileSpreadsheetIcon aria-hidden="true" />
                Evidence confidence
              </CardTitle>
              <CardDescription>
                Confidence is the lowest coverage across the required evidence sources.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p class="text-sm leading-6 text-muted-foreground">{{ employee.confidence_reason }}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle class="flex items-center gap-2">
                <Clock3Icon aria-hidden="true" />
                Compliance calculation
              </CardTitle>
              <CardDescription>Attendance, reporting, and leave evidence used in the score.</CardDescription>
            </CardHeader>
            <CardContent class="flex min-w-0 flex-col gap-4">
              <template v-if="complianceBreakdown">
                <section class="flex flex-col gap-3">
                  <div class="flex items-center justify-between gap-3">
                    <div class="flex min-w-0 items-center gap-2">
                      <span class="font-medium">Attendance</span>
                      <Badge variant="secondary">50%</Badge>
                    </div>
                    <strong class="shrink-0 text-lg tabular-nums">{{ complianceBreakdown.attendance }}%</strong>
                  </div>
                  <dl class="grid grid-cols-3 gap-3 text-sm text-muted-foreground">
                    <div class="flex flex-col gap-0.5"><dt>Arrival</dt><dd class="font-medium tabular-nums text-foreground">{{ complianceBreakdown.arrival }}%</dd></div>
                    <div class="flex flex-col gap-0.5"><dt>Shift end</dt><dd class="font-medium tabular-nums text-foreground">{{ complianceBreakdown.shiftEnd }}%</dd></div>
                    <div class="flex flex-col gap-0.5"><dt>Lunch</dt><dd class="font-medium tabular-nums text-foreground">{{ complianceBreakdown.lunch }}%</dd></div>
                  </dl>
                  <p class="text-sm text-muted-foreground">Actual arrival and shift end are compared with the schedule; lunch requires a valid check-out and return.</p>
                </section>

                <Separator />

                <section class="flex flex-col gap-1">
                  <div class="flex items-center justify-between gap-3">
                    <div class="flex min-w-0 items-center gap-2"><span class="font-medium">Reporting</span><Badge variant="secondary">35%</Badge></div>
                    <strong class="shrink-0 text-lg tabular-nums">{{ complianceBreakdown.reporting }}%</strong>
                  </div>
                  <p class="text-sm text-muted-foreground">Submitted date is compared with the due date.</p>
                </section>

                <Separator />

                <section class="flex flex-col gap-1">
                  <div class="flex items-center justify-between gap-3">
                    <div class="flex min-w-0 items-center gap-2"><span class="font-medium">Leave</span><Badge variant="secondary">15%</Badge></div>
                    <strong class="shrink-0 text-lg tabular-nums">{{ complianceBreakdown.leave }}%</strong>
                  </div>
                  <p class="text-sm text-muted-foreground">Approved annual leave and holidays are neutral; sick leave requires complete documentation.</p>
                </section>
              </template>
              <p v-else class="text-sm text-muted-foreground">{{ employee.compliance_reason }}</p>
              <p class="text-sm font-medium">Missing required evidence lowers confidence—it never becomes zero performance.</p>
            </CardContent>
          </Card>
        </div>

        <div class="grid min-w-0 content-start gap-6">
          <Card class="lg:min-h-44">
            <CardHeader>
              <CardTitle>AI guidance</CardTitle>
              <CardDescription>Generated on demand from this employee’s validated findings.</CardDescription>
            </CardHeader>
            <CardContent class="flex flex-col gap-4">
              <Button
                v-if="alerts.length && !insight"
                class="w-full sm:w-fit"
                :disabled="insightLoading"
                @click="emit('generateInsight', employee.employee_id)"
              >
                <Spinner v-if="insightLoading" data-icon="inline-start" />
                <SparklesIcon v-else data-icon="inline-start" />
                {{ insightLoading ? 'Generating guidance…' : 'Generate AI guidance' }}
              </Button>
              <Alert v-if="insightError" variant="destructive">
                <CircleAlertIcon aria-hidden="true" />
                <AlertTitle>AI guidance could not be generated</AlertTitle>
                <AlertDescription>{{ insightError }}</AlertDescription>
              </Alert>
              <Alert v-if="insight">
                <LightbulbIcon aria-hidden="true" />
                <AlertTitle>Explanation</AlertTitle>
                <AlertDescription class="flex flex-col gap-4">
                  <div class="flex flex-col gap-2">
                    <p>{{ insight.explanation.message }}</p>
                    <div class="flex flex-wrap gap-1">
                      <Badge v-for="recordId in insight.explanation.record_ids" :key="recordId" variant="secondary">{{ recordId }}</Badge>
                    </div>
                  </div>
                  <div>
                    <p class="font-medium text-foreground">Recommended next steps</p>
                    <ul class="mt-1 flex list-disc flex-col gap-2 pl-5">
                      <li v-for="recommendation in insight.recommendations" :key="recommendation.message">
                        {{ recommendation.message }}
                        <span class="mt-1 flex flex-wrap gap-1">
                          <Badge v-for="recordId in recommendation.record_ids" :key="recordId" variant="outline">{{ recordId }}</Badge>
                        </span>
                      </li>
                    </ul>
                  </div>
                </AlertDescription>
              </Alert>
              <p v-if="!alerts.length" class="text-sm text-muted-foreground">AI guidance is available only when validated findings exist.</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Alerts</CardTitle>
              <CardDescription>Validated findings and their supporting evidence.</CardDescription>
              <CardAction><Badge variant="secondary">{{ alerts.length }}</Badge></CardAction>
            </CardHeader>
            <CardContent class="flex flex-col gap-3">
              <Alert v-for="alert in alerts" :key="alert.code" :variant="alert.severity === 'info' ? 'default' : 'warning'">
                <TriangleAlertIcon v-if="alert.severity !== 'info'" aria-hidden="true" />
                <FileSpreadsheetIcon v-else aria-hidden="true" />
                <AlertTitle class="capitalize">
                  {{ alertCodeLabel(alert.code) }}
                  <Badge variant="outline">{{ alert.occurrence_count }}</Badge>
                </AlertTitle>
                <AlertDescription class="flex flex-col gap-2 [&_p]:mb-0">
                  <Badge :variant="impactVariant(alert.scoring_impact)">{{ impactLabel(alert.scoring_impact) }}</Badge>
                  <p>{{ alert.message }}</p>
                  <details v-if="alert.record_ids.length">
                    <summary class="cursor-pointer text-xs font-medium text-foreground">Supporting records ({{ alert.record_ids.length }})</summary>
                    <div class="mt-2 flex flex-wrap gap-1">
                      <Badge v-for="recordId in alert.record_ids" :key="recordId" variant="secondary">{{ recordId }}</Badge>
                    </div>
                  </details>
                  <a v-if="alert.evidence_links[0]" class="text-primary underline-offset-4 hover:underline" :href="alert.evidence_links[0]" target="_blank" rel="noreferrer">Open evidence</a>
                </AlertDescription>
              </Alert>
              <p v-if="!alerts.length" class="py-8 text-center text-sm text-muted-foreground">No alerts for this employee.</p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  </main>
</template>

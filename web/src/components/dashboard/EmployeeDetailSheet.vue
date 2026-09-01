<script setup lang="ts">
import { CircleAlertIcon, FileSpreadsheetIcon, LightbulbIcon, SparklesIcon, TriangleAlertIcon } from '@lucide/vue'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Spinner } from '@/components/ui/spinner'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { EmployeeAIInsight, EmployeeKpiResult, PerformanceAlert } from '@/types/analysis'

const props = defineProps<{
  employee: EmployeeKpiResult | null
  alerts: PerformanceAlert[]
  insight: EmployeeAIInsight | null
  insightLoading: boolean
  insightError?: string
}>()
const emit = defineEmits<{
  close: []
  generateInsight: [employeeId: string]
}>()

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
  <Sheet :open="Boolean(employee)" @update:open="value => !value && emit('close')">
    <SheetContent v-if="employee" class="w-full gap-0 sm:w-[min(70vw,56rem)] sm:max-w-none">
      <SheetHeader class="gap-4 border-b border-primary/15 bg-primary/5 px-5 py-5 sm:px-6">
        <div class="pr-8">
          <SheetTitle class="tracking-tight">Employee performance details</SheetTitle>
          <SheetDescription class="mt-1">KPIs, alerts, and AI guidance for this employee.</SheetDescription>
        </div>
        <div class="flex items-center justify-between gap-4 pr-8">
          <div class="min-w-0">
            <h2 class="truncate text-lg font-semibold tracking-tight">{{ employee.employee_name || employee.employee_id }}</h2>
            <p class="truncate text-sm text-muted-foreground">
              {{ employee.employee_id }} · {{ employee.team ?? 'Team not provided' }}<template v-if="employee.role"> · {{ employee.role }}</template>
            </p>
          </div>
          <Badge class="shrink-0" :variant="employee.overall_score === null ? 'warning' : 'success'">
            {{ employee.performance_tier ?? employee.result_status }}
          </Badge>
        </div>
        <div class="grid gap-4 rounded-xl border bg-background p-4 shadow-xs sm:grid-cols-[auto_1fr] sm:items-center sm:gap-6">
          <div>
            <p class="text-xs font-medium text-muted-foreground">Overall score</p>
            <p class="text-3xl font-semibold tracking-tight tabular-nums">{{ score(employee.overall_score) }}</p>
          </div>
          <div class="flex flex-col gap-1">
            <div class="flex items-center justify-between gap-3 text-xs">
              <span class="text-muted-foreground">Evidence confidence</span>
              <span class="font-medium tabular-nums">{{ employee.data_confidence.toFixed(1) }}%</span>
            </div>
            <Progress :model-value="employee.data_confidence" />
            <p class="text-xs text-muted-foreground">
              Required threshold: {{ employee.confidence_threshold.toFixed(1) }}%
            </p>
          </div>
        </div>
      </SheetHeader>

      <div class="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-5 py-5 sm:px-6">
        <Alert v-if="employee.overall_score === null" variant="warning">
          <TriangleAlertIcon aria-hidden="true" />
          <AlertTitle>Insufficient evidence for an overall result</AlertTitle>
          <AlertDescription>
            Overall performance and tier were withheld because evidence confidence is below
            the required threshold. Component KPI values remain visible for auditability and
            should not be treated as a complete performance assessment.
          </AlertDescription>
        </Alert>

        <section class="grid grid-cols-3 gap-2 sm:gap-3">
          <div class="flex min-w-0 flex-col gap-1 rounded-xl border bg-card p-3 shadow-xs sm:p-4">
            <p class="truncate text-xs font-medium text-muted-foreground">Productivity</p>
            <p class="text-lg font-semibold tracking-tight tabular-nums sm:text-xl">{{ score(employee.productivity_score) }}</p>
          </div>
          <div class="flex min-w-0 flex-col gap-1 rounded-xl border bg-card p-3 shadow-xs sm:p-4">
            <p class="truncate text-xs font-medium text-muted-foreground">Compliance</p>
            <p class="text-lg font-semibold tracking-tight tabular-nums sm:text-xl">{{ score(employee.compliance_score) }}</p>
          </div>
          <div class="flex min-w-0 flex-col gap-1 rounded-xl border bg-card p-3 shadow-xs sm:p-4">
            <p class="truncate text-xs font-medium text-muted-foreground">Quality</p>
            <p class="text-lg font-semibold tracking-tight tabular-nums sm:text-xl">{{ score(employee.quality_score) }}</p>
          </div>
        </section>

        <Alert>
          <FileSpreadsheetIcon aria-hidden="true" />
          <AlertTitle>How evidence confidence was determined</AlertTitle>
          <AlertDescription class="flex flex-col gap-2">
            <p>{{ employee.confidence_reason }}</p>
            <p class="text-xs">
              Missing required evidence reduces confidence; it is not converted into zero
              employee performance.
            </p>
          </AlertDescription>
        </Alert>

        <Tabs default-value="alerts" class="min-h-0 flex-1">
          <TabsList variant="line" class="grid w-full grid-cols-2 border-b">
            <TabsTrigger value="alerts">Alerts <Badge variant="secondary">{{ alerts.length }}</Badge></TabsTrigger>
            <TabsTrigger value="guidance"><SparklesIcon aria-hidden="true" />AI guidance</TabsTrigger>
          </TabsList>

          <TabsContent value="alerts" class="mt-4 flex flex-col gap-3">
            <Alert v-for="alert in alerts" :key="alert.code" :variant="alert.severity === 'info' ? 'default' : 'warning'">
              <TriangleAlertIcon v-if="alert.severity !== 'info'" aria-hidden="true" />
              <FileSpreadsheetIcon v-else aria-hidden="true" />
              <AlertTitle class="capitalize">
                {{ alertCodeLabel(alert.code) }}
                <Badge variant="outline">{{ alert.occurrence_count }}</Badge>
              </AlertTitle>
              <AlertDescription class="flex flex-col gap-2 [&_p]:mb-0">
                <Badge :variant="impactVariant(alert.scoring_impact)">
                  {{ impactLabel(alert.scoring_impact) }}
                </Badge>
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
            <p v-if="!alerts.length" class="py-10 text-center text-sm text-muted-foreground">No alerts for this employee.</p>
          </TabsContent>

          <TabsContent value="guidance" class="mt-4 flex flex-col gap-3">
            <p class="text-sm text-muted-foreground">Generated on demand from this employee’s validated findings.</p>
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
          </TabsContent>
        </Tabs>
      </div>
    </SheetContent>
  </Sheet>
</template>

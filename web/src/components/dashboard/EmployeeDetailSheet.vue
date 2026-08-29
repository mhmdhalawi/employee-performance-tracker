<script setup lang="ts">
import { CircleAlertIcon, FileSpreadsheetIcon, LightbulbIcon, SparklesIcon, TriangleAlertIcon } from '@lucide/vue'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Separator } from '@/components/ui/separator'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Spinner } from '@/components/ui/spinner'
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
</script>

<template>
  <Sheet :open="Boolean(employee)" @update:open="value => !value && emit('close')">
    <SheetContent v-if="employee" class="w-full overflow-y-auto sm:max-w-2xl">
      <SheetHeader>
        <div class="flex flex-wrap items-center gap-2 pr-8">
          <SheetTitle>{{ employee.employee_name || employee.employee_id }}</SheetTitle>
          <Badge :variant="employee.overall_score === null ? 'warning' : 'success'">
            {{ employee.performance_tier ?? employee.result_status }}
          </Badge>
        </div>
        <SheetDescription>
          {{ employee.employee_id }} · {{ employee.team ?? 'Team not provided' }}<template v-if="employee.role"> · {{ employee.role }}</template>
        </SheetDescription>
      </SheetHeader>

      <div class="flex flex-col gap-6 px-4 pb-6">
        <section class="grid gap-3 sm:grid-cols-2">
          <Card>
            <CardHeader><CardDescription>Overall score</CardDescription><CardTitle>{{ score(employee.overall_score) }}</CardTitle></CardHeader>
            <CardContent class="text-xs text-muted-foreground">{{ employee.result_status }}</CardContent>
          </Card>
          <Card>
            <CardHeader><CardDescription>Evidence confidence</CardDescription><CardTitle>{{ employee.data_confidence.toFixed(1) }}%</CardTitle></CardHeader>
            <CardContent><Progress :model-value="employee.data_confidence" /></CardContent>
          </Card>
          <Card>
            <CardHeader><CardDescription>Productivity</CardDescription><CardTitle>{{ score(employee.productivity_score) }}</CardTitle></CardHeader>
            <CardContent class="text-xs text-muted-foreground">{{ employee.productivity_reason }}</CardContent>
          </Card>
          <Card>
            <CardHeader><CardDescription>Compliance</CardDescription><CardTitle>{{ score(employee.compliance_score) }}</CardTitle></CardHeader>
            <CardContent class="text-xs text-muted-foreground">{{ employee.compliance_reason }}</CardContent>
          </Card>
          <Card class="sm:col-span-2">
            <CardHeader><CardDescription>Quality</CardDescription><CardTitle>{{ score(employee.quality_score) }}</CardTitle></CardHeader>
            <CardContent class="text-xs text-muted-foreground">{{ employee.quality_reason }}</CardContent>
          </Card>
        </section>

        <Separator />

        <section class="flex flex-col gap-3">
          <div>
            <h3 class="font-semibold">Employee alerts</h3>
            <p class="text-sm text-muted-foreground">Validated findings and their supporting records.</p>
          </div>
          <Alert v-for="alert in alerts" :key="alert.code" :variant="alert.severity === 'info' ? 'default' : 'warning'">
            <TriangleAlertIcon v-if="alert.severity !== 'info'" aria-hidden="true" />
            <FileSpreadsheetIcon v-else aria-hidden="true" />
            <AlertTitle class="capitalize">
              {{ alertCodeLabel(alert.code) }}
              <Badge variant="outline">{{ alert.occurrence_count }}</Badge>
            </AlertTitle>
            <AlertDescription class="flex flex-col gap-2">
              <p>{{ alert.message }}</p>
              <div v-if="alert.record_ids.length" class="flex flex-wrap gap-1">
                <Badge v-for="recordId in alert.record_ids" :key="recordId" variant="secondary">{{ recordId }}</Badge>
              </div>
              <a v-if="alert.evidence_links[0]" class="text-primary underline-offset-4 hover:underline" :href="alert.evidence_links[0]" target="_blank" rel="noreferrer">Open evidence</a>
            </AlertDescription>
          </Alert>
          <p v-if="!alerts.length" class="py-6 text-center text-sm text-muted-foreground">No alerts for this employee.</p>
        </section>

        <Separator />

        <section class="flex flex-col gap-3">
          <div>
            <h3 class="flex items-center gap-2 font-semibold"><SparklesIcon aria-hidden="true" />AI guidance</h3>
            <p class="text-sm text-muted-foreground">Generated on demand from this employee’s validated findings.</p>
          </div>
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
        </section>
      </div>
    </SheetContent>
  </Sheet>
</template>

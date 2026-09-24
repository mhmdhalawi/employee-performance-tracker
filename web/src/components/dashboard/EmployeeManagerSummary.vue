<script setup lang="ts">
import { computed } from 'vue'
import { ArrowRightIcon, CircleCheckIcon, ClipboardListIcon, StarIcon, TriangleAlertIcon } from '@lucide/vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { needsAttention, type AttentionItem } from '@/lib/employee-presentation'
import type { EmployeeKpiResult } from '@/types/analysis'

type Kpi = 'productivity' | 'compliance' | 'quality'

const props = withDefaults(defineProps<{
  employee: Pick<EmployeeKpiResult, 'components' | 'overall_score'>
  alerts: AttentionItem[]
  evidenceHref?: string
  showEvidenceLink?: boolean
}>(), { evidenceHref: '#employee-evidence', showEvidenceLink: true })

const kpiLabels: Record<Kpi, string> = {
  productivity: 'Productivity',
  compliance: 'Compliance',
  quality: 'Quality',
}

const highlights = computed(() => (Object.entries(props.employee.components) as [Kpi, EmployeeKpiResult['components'][Kpi]][])
  .flatMap(([kpi, components]) => components.map(component => ({ ...component, kpi })))
  .filter(component => component.score !== null)
  .sort((left, right) => (right.score ?? 0) - (left.score ?? 0))
  .slice(0, 2))

const reviewFindings = computed(() => needsAttention(props.alerts))
const findingCount = computed(() => reviewFindings.value.reduce((total, alert) => total + alert.occurrence_count, 0))
const featuredFinding = computed(() => reviewFindings.value.find(alert => alert.scoring_impact === 'lowers_confidence')
  ?? reviewFindings.value.find(alert => alert.category === 'performance_alert')
  ?? reviewFindings.value[0]
  ?? null)

function score(value: number | null): string {
  return value === null ? '—' : `${value.toFixed(1)}%`
}
</script>

<template>
  <Card aria-label="Manager summary" class="min-w-0 xl:h-full">
    <CardHeader class="gap-2">
      <div class="flex flex-wrap items-start justify-between gap-2">
        <div class="flex flex-col gap-1">
          <CardTitle><h2>Manager summary</h2></CardTitle>
          <CardDescription>Measured components and findings for this reporting period.</CardDescription>
        </div>
        <Badge :variant="findingCount ? 'warning' : 'success'">{{ findingCount ? `${findingCount} ${findingCount === 1 ? 'finding' : 'findings'}` : 'No findings' }}</Badge>
      </div>
    </CardHeader>
    <CardContent class="flex flex-col gap-3 xl:grow">
      <section class="rounded-xl border border-primary/20 bg-primary/8 p-4 xl:grow" aria-labelledby="manager-highlights-title">
        <div class="flex items-center gap-3">
          <span class="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary"><StarIcon class="size-4" aria-hidden="true" /></span>
          <div>
            <h3 id="manager-highlights-title" class="font-semibold text-primary">Highest component scores</h3>
            <p class="text-xs text-muted-foreground">Relative to this employee's other measured components</p>
          </div>
        </div>
        <ul v-if="highlights.length" class="mt-3 flex flex-col gap-2">
          <li v-for="component in highlights" :key="`${component.kpi}-${component.key}`" class="flex items-start justify-between gap-3 text-sm">
            <span class="min-w-0"><span class="font-medium">{{ component.label }}</span><span class="block text-xs text-muted-foreground">{{ kpiLabels[component.kpi] }}</span></span>
            <strong class="shrink-0 tabular-nums text-primary">{{ score(component.score) }}</strong>
          </li>
        </ul>
        <p v-else class="mt-3 text-sm text-muted-foreground">No component scores are available for this period.</p>
        <p v-if="employee.overall_score === null" class="mt-3 text-xs text-warning-foreground">Overall scoring is withheld; these component values are partial evidence.</p>
      </section>

      <section :class="featuredFinding ? 'border-warning/30 bg-warning/10' : 'border-border bg-muted/50'" class="rounded-xl border p-4 xl:grow" aria-labelledby="manager-watch-title">
        <div class="flex items-center gap-3">
          <span :class="featuredFinding ? 'bg-warning/20 text-warning-foreground' : 'bg-success/12 text-success-foreground'" class="flex size-9 shrink-0 items-center justify-center rounded-full">
            <TriangleAlertIcon v-if="featuredFinding" class="size-4" aria-hidden="true" />
            <CircleCheckIcon v-else class="size-4" aria-hidden="true" />
          </span>
          <div>
            <h3 id="manager-watch-title" class="font-semibold">{{ featuredFinding ? 'Watch point' : 'No watch points' }}</h3>
            <p class="text-xs text-muted-foreground">{{ featuredFinding ? (featuredFinding.category === 'data_issue' ? 'Data issue requiring source review' : 'Performance finding requiring review') : 'No backend findings for this period' }}</p>
          </div>
        </div>
        <template v-if="featuredFinding">
          <p class="mt-3 text-sm">{{ featuredFinding.message }}</p>
          <p v-if="featuredFinding.record_ids.length" class="mt-2 wrap-break-word text-xs text-muted-foreground">Supporting {{ featuredFinding.record_ids.length === 1 ? 'record' : 'records' }}: {{ featuredFinding.record_ids.slice(0, 3).join(', ') }}<template v-if="featuredFinding.record_ids.length > 3"> and {{ featuredFinding.record_ids.length - 3 }} more</template></p>
          <p v-if="findingCount > featuredFinding.occurrence_count" class="mt-2 text-xs text-muted-foreground">{{ findingCount - featuredFinding.occurrence_count }} additional {{ findingCount - featuredFinding.occurrence_count === 1 ? 'finding' : 'findings' }} appear in the evidence below.</p>
        </template>
        <p v-else class="mt-3 text-sm text-muted-foreground">No data issues or performance alerts were returned. The records remain available for review.</p>
      </section>

      <section class="rounded-xl border border-primary/15 bg-secondary p-4 xl:grow" aria-labelledby="manager-next-title">
        <div class="flex items-center gap-3">
          <span class="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/12 text-primary"><ClipboardListIcon class="size-4" aria-hidden="true" /></span>
          <div>
            <h3 id="manager-next-title" class="font-semibold">Next review step</h3>
            <p class="text-xs text-muted-foreground">{{ featuredFinding ? 'Based on the finding above' : 'For a manager-led review' }}</p>
          </div>
        </div>
        <p class="mt-3 text-sm">{{ featuredFinding?.action ?? 'Review the supporting records before discussing this result with the employee.' }}</p>
        <Button v-if="showEvidenceLink" as-child variant="default" size="sm" class="mt-3">
          <a :href="evidenceHref">Review evidence <ArrowRightIcon data-icon="inline-end" /></a>
        </Button>
      </section>
    </CardContent>
  </Card>
</template>

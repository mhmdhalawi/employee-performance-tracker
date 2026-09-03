<script setup lang="ts">
import type { CSSProperties } from 'vue'
import { computed } from 'vue'
import { ArrowRightIcon, DatabaseIcon, TriangleAlertIcon } from '@lucide/vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { SchemaMappingSummary } from '@/types/analysis'

const props = defineProps<{
  mappingSummaries: SchemaMappingSummary[]
}>()
const emit = defineEmits<{
  viewDetails: []
}>()

const classifications = computed(() => props.mappingSummaries.flatMap(item => item.table_classifications))
const relevant = computed(() => classifications.value.filter(item =>
  item.kpi_family !== 'irrelevant' && item.kpi_family !== 'unsupported',
))
const needsAttention = computed(() => classifications.value.filter(item =>
  item.kpi_family === 'unsupported' || item.confidence !== 'high',
))

function familyLabel(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1)
}

function familyVariant(family: string): 'default' | 'secondary' | 'outline' | 'warning' {
  if (['productivity', 'compliance', 'quality'].includes(family))
    return 'outline'
  if (family === 'unsupported')
    return 'warning'
  if (family === 'irrelevant')
    return 'outline'
  if (family === 'shared')
    return 'secondary'
  return 'default'
}

function familyStyle(family: string): CSSProperties | undefined {
  const colors: Record<string, string> = {
    productivity: 'var(--chart-1)',
    compliance: 'var(--chart-2)',
    quality: 'var(--chart-3)',
  }
  const color = colors[family]
  if (!color)
    return undefined
  return {
    color,
    backgroundColor: `color-mix(in oklab, ${color} 14%, transparent)`,
    borderColor: `color-mix(in oklab, ${color} 28%, transparent)`,
  }
}
</script>

<template>
  <Card>
    <CardHeader>
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="flex flex-col gap-1">
          <CardTitle class="flex items-center gap-2">
            <DatabaseIcon class="size-4" aria-hidden="true" />
            Data interpretation
          </CardTitle>
          <CardDescription>
            See how uploaded tables were classified before deterministic calculation.
          </CardDescription>
        </div>

        <Button variant="outline" size="sm" @click="emit('viewDetails')">
          View details
          <ArrowRightIcon data-icon="inline-end" />
        </Button>
      </div>
    </CardHeader>

    <CardContent class="flex flex-col gap-4">
      <div class="flex flex-wrap gap-2">
        <Badge v-for="(item, index) in relevant" :key="`${item.source_name}-${index}`" :variant="familyVariant(item.kpi_family)" :style="familyStyle(item.kpi_family)">
          {{ item.source_name }} · {{ familyLabel(item.kpi_family) }}
        </Badge>
      </div>
      <div v-if="needsAttention.length" class="flex items-start gap-2 text-sm text-warning-foreground">
        <TriangleAlertIcon class="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <p>{{ needsAttention.length }} table{{ needsAttention.length === 1 ? '' : 's' }} need review because classification confidence is below high or the evidence is unsupported.</p>
      </div>
      <p v-else class="text-sm text-muted-foreground">
        {{ relevant.length }} relevant table{{ relevant.length === 1 ? '' : 's' }} matched approved calculation inputs with high confidence.
      </p>
    </CardContent>
  </Card>
</template>

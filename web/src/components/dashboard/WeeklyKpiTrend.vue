<script setup lang="ts">
import { computed } from 'vue'
import { VisAxis, VisLine, VisScatter, VisXYContainer } from '@unovis/vue'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartContainer, type ChartConfig } from '@/components/ui/chart'
import { formatDate } from '@/lib/date-format'
import type { KpiTrendPoint } from '@/types/analysis'

const props = withDefaults(defineProps<{
  trends: KpiTrendPoint[]
  description?: string
  scale?: 'full' | 'detail'
  compactOnDesktop?: boolean
}>(), {
  description: 'Gaps mean no score is available.',
  scale: 'full',
  compactOnDesktop: false,
})

interface ChartPoint {
  weekIndex: number
  label: string
  productivity: number | null
  compliance: number | null
  quality: number | null
}

const trendData = computed<ChartPoint[]>(() => props.trends.map((point, weekIndex) => ({
  weekIndex,
  label: formatDate(point.period_end),
  productivity: point.productivity_score,
  compliance: point.compliance_score,
  quality: point.quality_score,
})))

const yDomain = computed<[number, number]>(() => {
  if (props.scale !== 'detail') return [0, 100]
  const scores = trendData.value.flatMap(point => [point.productivity, point.compliance, point.quality])
    .filter((value): value is number => value !== null && Number.isFinite(value))
  return scores.length && Math.min(...scores) >= 60 ? [60, 100] : [0, 100]
})
const chartLabel = computed(() => `Weekly KPI chart, ${yDomain.value[0]} to 100 percent scale`)

const chartConfig = {
  productivity: { label: 'Productivity', color: 'var(--chart-1)' },
  compliance: { label: 'Compliance', color: 'var(--chart-2)' },
  quality: { label: 'Quality', color: 'var(--chart-3)' },
} satisfies ChartConfig

const trendX = (point: ChartPoint) => point.weekIndex

const productivityPoints = computed(() => trendData.value.filter(point => point.productivity !== null))
const compliancePoints = computed(() => trendData.value.filter(point => point.compliance !== null))
const qualityPoints = computed(() => trendData.value.filter(point => point.quality !== null))
// Unovis treats null as zero; NaN breaks the line at missing evidence.
const productivityY = (point: ChartPoint) => point.productivity ?? Number.NaN
const complianceY = (point: ChartPoint) => point.compliance ?? Number.NaN
const qualityY = (point: ChartPoint) => point.quality ?? Number.NaN
const weekTick = (index: number) => trendData.value[index]?.label ?? ''
const percentTick = (value: number) => `${value}%`

</script>

<template>
  <Card :class="compactOnDesktop ? 'xl:grow' : undefined">
    <CardHeader>
      <div class="flex items-start justify-between gap-3">
        <div>
          <CardTitle>Weekly KPI trend</CardTitle>
          <CardDescription v-if="description">{{ description }}</CardDescription>
        </div>
        <div class="flex flex-wrap justify-end gap-2">
          <Badge variant="outline">{{ trendData.length }} periods</Badge>
          <Badge v-if="scale === 'detail' && yDomain[0] > 0" variant="secondary">{{ yDomain[0] }}–100% scale</Badge>
        </div>
      </div>
    </CardHeader>
    <CardContent :class="compactOnDesktop ? 'xl:flex xl:grow xl:flex-col' : undefined">
      <div class="mb-4 flex flex-wrap gap-4 text-xs" aria-label="Chart legend">
        <span v-for="(item, key) in chartConfig" :key="key" class="flex items-center gap-2">
          <svg class="h-2 w-6" aria-hidden="true">
            <line x1="0" y1="4" x2="24" y2="4" :stroke="item.color" stroke-width="2"
              :stroke-dasharray="key === 'compliance' ? '6 3' : key === 'quality' ? '2 3' : undefined" />
          </svg>{{ item.label }}
        </span>
      </div>
      <ChartContainer v-if="trendData.length" :config="chartConfig"
        :class="compactOnDesktop ? 'h-72 w-full xl:aspect-auto xl:h-60 2xl:h-48' : 'h-72 w-full'"
        :aria-label="chartLabel">
        <VisXYContainer :data="trendData" :duration="0" :y-domain="yDomain">
          <VisAxis type="x" :x="trendX" :tick-format="weekTick" />
          <VisAxis type="y" :tick-format="percentTick" />
          <VisLine :x="trendX" :y="productivityY" :fallback-value="undefined" :color="chartConfig.productivity.color" />
          <VisLine :x="trendX" :y="complianceY" :fallback-value="undefined" :line-dash-array="[6, 3]" :color="chartConfig.compliance.color" />
          <VisLine :x="trendX" :y="qualityY" :fallback-value="undefined" :line-dash-array="[2, 3]" :color="chartConfig.quality.color" />
          <VisScatter :data="productivityPoints" :x="trendX" :y="productivityY" :size="7" :color="chartConfig.productivity.color" />
          <VisScatter :data="compliancePoints" :x="trendX" :y="complianceY" :size="7" :color="chartConfig.compliance.color" />
          <VisScatter :data="qualityPoints" :x="trendX" :y="qualityY" :size="7" :color="chartConfig.quality.color" />
        </VisXYContainer>
      </ChartContainer>
      <p v-else class="py-16 text-center text-sm text-muted-foreground">No trend data is available for this filter.</p>
    </CardContent>
  </Card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { VisAxis, VisLine, VisXYContainer } from '@unovis/vue'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartContainer, type ChartConfig } from '@/components/ui/chart'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { formatDate } from '@/lib/date-format'
import type { KpiTrendPoint } from '@/types/analysis'

const props = withDefaults(defineProps<{
  trends: KpiTrendPoint[]
  description?: string
  showWeeklyValues?: boolean
}>(), {
  description: 'Gaps mean no score is available.',
  showWeeklyValues: true,
})

interface ChartPoint {
  label: string
  productivity: number | null
  compliance: number | null
  quality: number | null
}

const trendData = computed<ChartPoint[]>(() => props.trends.map(point => ({
  label: formatDate(point.period_end),
  productivity: point.productivity_score,
  compliance: point.compliance_score,
  quality: point.quality_score,
})))

const chartConfig = {
  productivity: { label: 'Productivity', color: 'var(--chart-1)' },
  compliance: { label: 'Compliance', color: 'var(--chart-2)' },
  quality: { label: 'Quality', color: 'var(--chart-3)' },
} satisfies ChartConfig

const trendX = (_point: ChartPoint, index: number) => index
// Unovis treats null as zero; NaN breaks the line at missing evidence.
const productivityY = (point: ChartPoint) => point.productivity ?? Number.NaN
const complianceY = (point: ChartPoint) => point.compliance ?? Number.NaN
const qualityY = (point: ChartPoint) => point.quality ?? Number.NaN
const weekTick = (index: number) => trendData.value[index]?.label ?? ''
const percentTick = (value: number) => `${value}%`

function score(value: number): string {
  return `${value.toFixed(1)}%`
}
</script>

<template>
  <Card>
    <CardHeader>
      <div class="flex items-start justify-between gap-3">
        <div>
          <CardTitle>Weekly KPI trend</CardTitle>
          <CardDescription v-if="description">{{ description }}</CardDescription>
        </div>
        <Badge variant="outline">{{ trendData.length }} periods</Badge>
      </div>
    </CardHeader>
    <CardContent>
      <div class="mb-4 flex flex-wrap gap-4 text-xs" aria-label="Chart legend">
        <span v-for="(item, key) in chartConfig" :key="key" class="flex items-center gap-2">
          <svg class="h-2 w-6" aria-hidden="true">
            <line x1="0" y1="4" x2="24" y2="4" :stroke="item.color" stroke-width="2"
              :stroke-dasharray="key === 'compliance' ? '6 3' : key === 'quality' ? '2 3' : undefined" />
          </svg>{{ item.label }}
        </span>
      </div>
      <ChartContainer v-if="trendData.length" :config="chartConfig" class="h-72 w-full"
        :aria-label="showWeeklyValues ? 'Weekly KPI chart; exact values in the table below' : 'Weekly KPI chart'">
        <VisXYContainer :data="trendData" :duration="0" :y-domain="[0, 100]">
          <VisAxis type="x" :x="trendX" :tick-format="weekTick" />
          <VisAxis type="y" :tick-format="percentTick" />
          <VisLine :x="trendX" :y="productivityY" :fallback-value="undefined" :color="chartConfig.productivity.color" />
          <VisLine :x="trendX" :y="complianceY" :fallback-value="undefined" :line-dash-array="[6, 3]" :color="chartConfig.compliance.color" />
          <VisLine :x="trendX" :y="qualityY" :fallback-value="undefined" :line-dash-array="[2, 3]" :color="chartConfig.quality.color" />
        </VisXYContainer>
      </ChartContainer>
      <p v-else class="py-16 text-center text-sm text-muted-foreground">No trend data is available for this filter.</p>
      <details v-if="showWeeklyValues && trendData.length" class="mt-4">
        <summary class="cursor-pointer text-sm font-medium">View weekly values</summary>
        <div class="mt-3 overflow-x-auto">
          <Table>
            <TableHeader><TableRow><TableHead>Week ending</TableHead><TableHead>Productivity</TableHead><TableHead>Compliance</TableHead><TableHead>Quality</TableHead></TableRow></TableHeader>
            <TableBody>
              <TableRow v-for="point in trendData" :key="point.label">
                <TableCell>{{ point.label }}</TableCell>
                <TableCell>{{ point.productivity === null ? 'No productivity data' : score(point.productivity) }}</TableCell>
                <TableCell>{{ point.compliance === null ? 'No compliance data' : score(point.compliance) }}</TableCell>
                <TableCell>{{ point.quality === null ? 'No quality data' : score(point.quality) }}</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>
      </details>
    </CardContent>
  </Card>
</template>

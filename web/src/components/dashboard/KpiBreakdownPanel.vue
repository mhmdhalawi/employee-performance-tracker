<script setup lang="ts">
import { computed } from 'vue'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { DashboardKpiBreakdown } from '@/types/analysis'

type Kpi = 'productivity' | 'compliance' | 'quality'

const props = defineProps<{
  selected: Kpi
  breakdowns: Record<Kpi, DashboardKpiBreakdown>
  disabled?: boolean
}>()
const emit = defineEmits<{ select: [kpi: Kpi] }>()

const current = computed(() => props.breakdowns[props.selected])
const labels: Record<Kpi, string> = {
  productivity: 'Productivity',
  compliance: 'Compliance',
  quality: 'Quality',
}

function select(value: string | number): void {
  if (value === 'productivity' || value === 'compliance' || value === 'quality')
    emit('select', value)
}

function formatScore(value: number | null): string {
  return value === null ? '—' : `${value.toFixed(1)}%`
}
</script>

<template>
  <Card id="kpi-breakdown" aria-label="KPI breakdown" class="scroll-mt-4">
    <Tabs :model-value="selected" class="gap-0" @update:model-value="select">
      <CardHeader class="gap-3 sm:flex sm:flex-row sm:items-start sm:justify-between">
        <div class="min-w-0">
          <CardTitle>{{ labels[selected] }} breakdown</CardTitle>
          <CardDescription v-if="current.scored_employee_count">Average component scores for the {{ current.scored_employee_count }} employees with a reportable overall result.</CardDescription>
          <CardDescription v-else>No employees have a reportable overall result in this period.</CardDescription>
        </div>
        <TabsList aria-label="KPI breakdown category" class="w-full sm:w-auto">
          <TabsTrigger v-for="(label, kpi) in labels" :key="kpi" :value="kpi" :disabled="disabled">{{ label }}</TabsTrigger>
        </TabsList>
      </CardHeader>
      <TabsContent v-for="(label, kpi) in labels" :key="kpi" :value="kpi">
        <CardContent class="flex flex-col gap-4">
          <Table class="table-fixed">
            <TableHeader>
              <TableRow>
                <TableHead>Component</TableHead>
                <TableHead class="text-right">Average score</TableHead>
                <TableHead class="text-right">Weight</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="component in breakdowns[kpi].components" :key="component.key">
                <TableCell class="whitespace-normal font-medium">{{ component.label }}</TableCell>
                <TableCell class="text-right tabular-nums">{{ formatScore(component.score) }}</TableCell>
                <TableCell class="text-right tabular-nums">{{ component.weight }}%</TableCell>
              </TableRow>
              <TableRow>
                <TableCell class="font-semibold">{{ label }} score</TableCell>
                <TableCell class="text-right font-semibold tabular-nums">{{ formatScore(breakdowns[kpi].score) }}</TableCell>
                <TableCell class="text-right text-muted-foreground">—</TableCell>
              </TableRow>
            </TableBody>
          </Table>
          <p class="text-xs text-muted-foreground">Weights are within this KPI. Component averages and the final score use the same scored employee population. A missing value is shown as —. No shared KPI target or prior-period benchmark is configured.</p>
        </CardContent>
      </TabsContent>
    </Tabs>
  </Card>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { EmployeeKpiResult } from '@/types/analysis'

type Kpi = 'productivity' | 'compliance' | 'quality'

defineProps<{ employee: EmployeeKpiResult }>()
const selected = ref<Kpi>('productivity')
const labels: Record<Kpi, string> = {
  productivity: 'Productivity',
  compliance: 'Compliance',
  quality: 'Quality',
}

function select(value: string | number): void {
  if (value === 'productivity' || value === 'compliance' || value === 'quality')
    selected.value = value
}

function score(value: number | null): string {
  return value === null ? '—' : `${value.toFixed(1)}%`
}
</script>

<template>
  <Card aria-label="Employee KPI breakdown" class="min-w-0">
    <Tabs :model-value="selected" class="gap-0" @update:model-value="select">
      <CardHeader class="gap-3 sm:flex sm:flex-row sm:items-start sm:justify-between">
        <div class="min-w-0">
          <CardTitle><h2>KPI breakdown</h2></CardTitle>
          <CardDescription>Backend-calculated components of each KPI score.</CardDescription>
        </div>
        <TabsList aria-label="Employee KPI breakdown category" class="w-full sm:w-auto">
          <TabsTrigger v-for="(label, kpi) in labels" :key="kpi" :value="kpi">{{ label }}</TabsTrigger>
        </TabsList>
      </CardHeader>
      <TabsContent v-for="(label, kpi) in labels" :key="kpi" :value="kpi">
        <CardContent class="flex flex-col gap-3">
          <div class="overflow-x-auto">
            <Table class="min-w-md">
              <TableHeader><TableRow><TableHead>Component</TableHead><TableHead class="text-right">Score</TableHead><TableHead class="text-right">Within-KPI weight</TableHead></TableRow></TableHeader>
              <TableBody>
                <TableRow v-for="component in employee.components[kpi] ?? []" :key="component.key">
                  <TableCell class="whitespace-normal">{{ component.label }}</TableCell>
                  <TableCell class="text-right tabular-nums">{{ score(component.score) }}</TableCell>
                  <TableCell class="text-right tabular-nums">{{ component.weight }}%</TableCell>
                </TableRow>
                <TableRow v-if="!employee.components[kpi]?.length"><TableCell colspan="3" class="text-muted-foreground">No component scores are available for this KPI.</TableCell></TableRow>
              </TableBody>
            </Table>
          </div>
          <p class="text-xs text-muted-foreground">Weights are within {{ label }}, which is {{ kpi === 'compliance' ? '30' : '35' }}% of the overall result. The KPI score appears in the summary above.</p>
        </CardContent>
      </TabsContent>
    </Tabs>
  </Card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { AnalysisSummary, EmployeeKpiResult } from '@/types/analysis'

const props = defineProps<{ employee: EmployeeKpiResult, summary: AnalysisSummary }>()
const rows = computed(() => [
  { key: 'productivity' as const, label: 'Productivity', score: props.employee.productivity_score, average: props.summary.average_productivity_score, weight: 35 },
  { key: 'compliance' as const, label: 'Compliance', score: props.employee.compliance_score, average: props.summary.average_compliance_score, weight: 30 },
  { key: 'quality' as const, label: 'Quality', score: props.employee.quality_score, average: props.summary.average_quality_score, weight: 35 },
])

function formatScore(value: number | null): string {
  return value === null ? '—' : `${value.toFixed(1)}%`
}

</script>

<template>
  <Card aria-label="Performance explained">
    <CardHeader>
      <CardTitle><h2>Performance explained</h2></CardTitle>
      <CardDescription>Current KPI scores and their share of the overall result. Scope averages include only employees eligible for an overall score.</CardDescription>
    </CardHeader>
    <CardContent class="flex flex-col gap-3">
      <div class="overflow-x-auto">
        <Table class="min-w-xl">
          <TableHeader><TableRow><TableHead>KPI</TableHead><TableHead class="text-right">Employee</TableHead><TableHead class="text-right">Scope average</TableHead><TableHead class="text-right">Overall weight</TableHead><TableHead class="text-right">Records</TableHead></TableRow></TableHeader>
          <TableBody>
            <TableRow v-for="row in rows" :key="row.key">
              <TableCell class="font-medium">{{ row.label }}</TableCell>
              <TableCell class="text-right tabular-nums">{{ formatScore(row.score) }}</TableCell>
              <TableCell class="text-right tabular-nums">{{ summary.scored_employee_count > 1 ? formatScore(row.average) : '—' }}</TableCell>
              <TableCell class="text-right tabular-nums">{{ row.weight }}%</TableCell>
              <TableCell class="text-right"><a :href="`#${row.key}-evidence`" class="text-primary underline underline-offset-4 focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-ring">View evidence</a></TableCell>
            </TableRow>
            <TableRow>
              <TableCell class="font-semibold">Overall result</TableCell>
              <TableCell class="text-right font-semibold tabular-nums">{{ formatScore(employee.overall_score) }}</TableCell>
              <TableCell class="text-right tabular-nums">{{ summary.scored_employee_count > 1 ? formatScore(summary.average_overall_score) : '—' }}</TableCell>
              <TableCell class="text-right tabular-nums">100%</TableCell>
              <TableCell class="text-right text-muted-foreground">—</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
      <p class="text-xs text-muted-foreground">Scope average: {{ summary.scored_employee_count }} scored {{ summary.scored_employee_count === 1 ? 'employee' : 'employees' }} in the current dashboard filters. A missing score is shown as —.</p>
    </CardContent>
  </Card>
</template>

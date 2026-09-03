<script setup lang="ts">
import type { CSSProperties } from 'vue'
import { ArrowLeftIcon, DatabaseIcon } from '@lucide/vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { SchemaMappingSummary, TableClassification } from '@/types/analysis'

defineProps<{
  mappingSummaries: SchemaMappingSummary[]
}>()
const emit = defineEmits<{
  back: []
}>()

function familyLabel(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1)
}

function calculatorLabel(value: string): string {
  return value
    .replace(/^calculate_/, '')
    .replace(/^load_/, 'load ')
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

function confidenceVariant(confidence: TableClassification['confidence']): 'success' | 'warning' {
  return confidence === 'high' ? 'success' : 'warning'
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
  <main class="min-h-svh bg-muted/30">
    <header class="border-b bg-background">
      <div class="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
        <Button variant="ghost" @click="emit('back')">
          <ArrowLeftIcon data-icon="inline-start" />
          Back to dashboard
        </Button>
        <Badge variant="outline">{{ mappingSummaries.length }} source schema{{ mappingSummaries.length === 1 ? '' : 's' }}</Badge>
      </div>
    </header>

    <div class="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8">
      <header class="flex flex-col gap-2">
        <p class="text-sm font-medium text-muted-foreground">Combined canonical evidence</p>
        <h1 class="flex items-center gap-2 text-3xl font-semibold tracking-tight">
          <DatabaseIcon aria-hidden="true" />
          Data interpretation
        </h1>
        <p class="max-w-3xl text-sm text-muted-foreground">
          Source tables, KPI classifications, approved calculators, and validated field bindings used for this analysis.
        </p>
      </header>

      <section v-for="summary in mappingSummaries" :key="summary.schema_fingerprint" class="flex flex-col gap-4" aria-label="Interpreted source schema">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="min-w-0">
            <h2 class="font-semibold">Schema {{ summary.schema_fingerprint.slice(0, 12) }}</h2>
            <p class="text-sm text-muted-foreground">{{ summary.included_submission_count }} contributing submission{{ summary.included_submission_count === 1 ? '' : 's' }}</p>
          </div>
          <Badge variant="secondary">{{ summary.table_classifications.length }} tables</Badge>
        </div>
        <div class="columns-1 gap-6 lg:columns-2">
        <Card v-for="item in summary.table_classifications" :key="item.source_name" class="mb-6 inline-block w-full break-inside-avoid">
          <CardHeader>
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div class="min-w-0 flex-1">
                <CardTitle class="break-words">{{ item.source_name }}</CardTitle>
                <CardDescription class="mt-1 leading-6">{{ item.rationale }}</CardDescription>
              </div>
              <div class="flex flex-wrap gap-2">
                <Badge :variant="familyVariant(item.kpi_family)" :style="familyStyle(item.kpi_family)">
                  {{ familyLabel(item.kpi_family) }}
                </Badge>
                <Badge :variant="confidenceVariant(item.confidence)">
                  {{ familyLabel(item.confidence) }} confidence
                </Badge>
              </div>
            </div>
          </CardHeader>

          <CardContent class="flex min-w-0 flex-col gap-5">
            <div v-for="invocation in item.calculator_invocations" :key="invocation.calculator" class="flex min-w-0 flex-col gap-2">
              <p class="text-sm font-medium">{{ calculatorLabel(invocation.calculator) }}</p>
              <div class="overflow-x-auto rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Calculator input</TableHead>
                      <TableHead>Source column</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    <TableRow v-for="(sourceColumn, inputField) in invocation.field_bindings" :key="inputField">
                      <TableCell class="font-mono text-xs">{{ inputField }}</TableCell>
                      <TableCell class="font-mono text-xs">{{ sourceColumn }}</TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </div>
            </div>
            <p v-if="!item.calculator_invocations.length" class="text-sm text-muted-foreground">
              No calculator was invoked for this table.
            </p>
          </CardContent>
        </Card>
        </div>
      </section>
    </div>
  </main>
</template>

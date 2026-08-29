<script setup lang="ts">
import { computed } from 'vue'
import { ArrowRightIcon, DatabaseIcon, TriangleAlertIcon } from '@lucide/vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { TableClassification } from '@/types/analysis'

const props = defineProps<{
  classifications: TableClassification[]
}>()

const relevant = computed(() => props.classifications.filter(item =>
  item.kpi_family !== 'irrelevant' && item.kpi_family !== 'unsupported',
))
const needsAttention = computed(() => props.classifications.filter(item =>
  item.kpi_family === 'unsupported' || item.confidence !== 'high',
))

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
  if (family === 'unsupported')
    return 'warning'
  if (family === 'irrelevant')
    return 'outline'
  if (family === 'shared')
    return 'secondary'
  return 'default'
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

        <Sheet>
          <SheetTrigger as-child>
            <Button variant="outline" size="sm">
              View details
              <ArrowRightIcon data-icon="inline-end" />
            </Button>
          </SheetTrigger>
          <SheetContent class="w-full overflow-y-auto sm:max-w-2xl">
            <SheetHeader>
              <SheetTitle>Data interpretation details</SheetTitle>
              <SheetDescription>
                Source tables, KPI classifications, approved calculators, and validated field bindings for this analysis.
              </SheetDescription>
            </SheetHeader>

            <div class="flex flex-col gap-5 px-4 pb-6">
              <div v-for="item in classifications" :key="item.source_name" class="flex flex-col gap-3 rounded-lg border p-4">
                <div class="flex flex-wrap items-start justify-between gap-3">
                  <div class="flex flex-col gap-1">
                    <p class="font-medium">{{ item.source_name }}</p>
                    <p class="text-sm text-muted-foreground">{{ item.rationale }}</p>
                  </div>
                  <div class="flex flex-wrap gap-2">
                    <Badge :variant="familyVariant(item.kpi_family)">{{ familyLabel(item.kpi_family) }}</Badge>
                    <Badge :variant="confidenceVariant(item.confidence)">{{ familyLabel(item.confidence) }} confidence</Badge>
                  </div>
                </div>

                <div v-if="item.calculator_invocations.length" class="flex flex-col gap-4">
                  <div v-for="invocation in item.calculator_invocations" :key="invocation.calculator" class="flex flex-col gap-2">
                    <p class="text-sm font-medium">{{ calculatorLabel(invocation.calculator) }}</p>
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
                <p v-else class="text-sm text-muted-foreground">No calculator was invoked for this table.</p>
              </div>
            </div>
          </SheetContent>
        </Sheet>
      </div>
    </CardHeader>

    <CardContent class="flex flex-col gap-4">
      <div class="flex flex-wrap gap-2">
        <Badge v-for="item in relevant" :key="item.source_name" :variant="familyVariant(item.kpi_family)">
          {{ item.source_name }} · {{ familyLabel(item.kpi_family) }}
        </Badge>
      </div>
      <div v-if="needsAttention.length" class="flex items-start gap-2 text-sm text-warning-foreground">
        <TriangleAlertIcon class="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <p>{{ needsAttention.length }} table{{ needsAttention.length === 1 ? '' : 's' }} need review because classification confidence is below high or the evidence is unsupported.</p>
      </div>
      <p v-else class="text-sm text-muted-foreground">
        {{ relevant.length }} relevant tables were matched to approved calculation inputs with high confidence.
      </p>
    </CardContent>
  </Card>
</template>

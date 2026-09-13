<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ChevronDownIcon, ChevronLeftIcon, ChevronRightIcon } from '@lucide/vue'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Spinner } from '@/components/ui/spinner'
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import EvidenceRecordDetails from '@/components/dashboard/EvidenceRecordDetails.vue'
import { evidenceCells, evidenceColumns, evidenceLabels, evidenceLink } from '@/lib/employee-evidence'
import type { EmployeeEvidenceRow, EvidenceKpi } from '@/types/employee-evidence'

const props = withDefaults(defineProps<{
  kpi: EvidenceKpi
  score: number | null
  weight: number
  explanation: string
  rows: EmployeeEvidenceRow[]
  total: number
  page?: number
  pageSize?: number
  loading?: boolean
  error?: string
  report?: boolean
  disabled?: boolean
}>(), { page: 1, pageSize: 5, loading: false, error: '', report: false, disabled: false })
const emit = defineEmits<{ pageChange: [page: number], retry: [] }>()
const openRows = ref<Record<string, boolean>>({})
const previewPage = ref(1)
const columns = computed(() => evidenceColumns(props.kpi))
const activePage = computed(() => props.report ? previewPage.value : props.page)
const visibleRows = computed(() => props.report
  ? props.rows.slice((previewPage.value - 1) * props.pageSize, previewPage.value * props.pageSize)
  : props.rows)
const range = computed(() => props.total === 0 ? '0 records' : `Records ${(activePage.value - 1) * props.pageSize + 1}–${Math.min(activePage.value * props.pageSize, props.total)} of ${props.total}`)
function rowKey(row: EmployeeEvidenceRow): string { return `${row.record_type}:${row.record_id}` }
function changePage(page: number): void {
  if (props.report) previewPage.value = page
  else emit('pageChange', page)
}
watch(() => props.rows, () => { openRows.value = {}; if (props.report) previewPage.value = 1 })
</script>

<template>
  <Card class="min-w-0" :aria-label="`${evidenceLabels[kpi]} evidence`">
    <CardHeader>
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="flex min-w-0 flex-col gap-1">
          <CardTitle><h2>{{ evidenceLabels[kpi] }} evidence</h2></CardTitle>
          <CardDescription>{{ weight }}% of overall</CardDescription>
        </div>
        <strong class="text-3xl tabular-nums" :aria-label="`${evidenceLabels[kpi]} score`">{{ score === null ? '—' : `${score.toFixed(1)}%` }}</strong>
      </div>
      <CardDescription class="whitespace-normal break-words">{{ explanation }}</CardDescription>
    </CardHeader>
    <CardContent class="flex min-w-0 flex-col gap-4" :aria-busy="loading">
      <p v-if="report" class="text-sm text-muted-foreground">All {{ total }} records are included in the PDF. Browse the preview below.</p>
      <Alert v-if="error" variant="destructive">
        <AlertTitle>{{ evidenceLabels[kpi] }} evidence unavailable</AlertTitle>
        <AlertDescription class="flex flex-col gap-2">
          <p>{{ error }}</p>
          <Button variant="outline" class="w-fit" :disabled="loading || disabled" @click="emit('retry')">Retry evidence</Button>
        </AlertDescription>
      </Alert>
      <div v-if="loading" class="flex min-h-24 items-center gap-3 text-sm text-muted-foreground" role="status"><Spinner />Loading {{ evidenceLabels[kpi].toLowerCase() }} evidence…</div>
      <p v-if="!loading && !error && !total" class="py-8 text-sm text-muted-foreground">No {{ evidenceLabels[kpi].toLowerCase() }} evidence records for this reporting period.</p>
      <template v-if="visibleRows.length && !disabled">
        <div class="hidden md:block">
          <Table class="table-fixed">
            <TableCaption>{{ evidenceLabels[kpi] }} records for the active reporting period. Source statuses do not replace calculated results.</TableCaption>
            <TableHeader><TableRow>
              <TableHead v-for="column in columns" :key="column" class="whitespace-normal">{{ column }}</TableHead>
              <TableHead class="w-28">Details</TableHead>
            </TableRow></TableHeader>
            <Collapsible v-for="row in visibleRows" :key="rowKey(row)" v-model:open="openRows[rowKey(row)]" as-child>
              <TableBody>
                <TableRow>
                  <TableCell v-for="(cell, index) in evidenceCells(row)" :key="index" class="align-top whitespace-normal break-words">
                    {{ cell }}
                    <template v-if="index === columns.length - 1">
                      <Badge v-if="row.excluded_from_scoring" variant="warning" class="mt-2 whitespace-normal">Excluded from scoring</Badge>
                      <Badge v-if="row.validation_findings.length" variant="outline" class="mt-2 whitespace-normal">{{ row.validation_findings.length }} findings</Badge>
                      <Button v-if="evidenceLink(row)" as-child variant="link" size="sm" class="mt-1 max-w-full whitespace-normal">
                        <a :href="evidenceLink(row)!" target="_blank" rel="noopener noreferrer">Open evidence</a>
                      </Button>
                    </template>
                  </TableCell>
                  <TableCell class="align-top"><CollapsibleTrigger as-child><Button variant="ghost" size="sm" :aria-label="`Details for ${row.record_type} ${row.record_id}`">Details<ChevronDownIcon data-icon="inline-end" /></Button></CollapsibleTrigger></TableCell>
                </TableRow>
                <CollapsibleContent as-child><TableRow><TableCell :colspan="columns.length + 1" class="bg-muted/30 p-4"><EvidenceRecordDetails :row="row" /></TableCell></TableRow></CollapsibleContent>
              </TableBody>
            </Collapsible>
          </Table>
        </div>
        <div class="flex flex-col gap-3 md:hidden">
          <Collapsible v-for="row in visibleRows" :key="rowKey(row)" v-model:open="openRows[rowKey(row)]" as-child>
            <Card class="min-w-0">
              <CardHeader><CardTitle class="break-words">{{ row.record_id }}</CardTitle>
                <Badge v-if="row.excluded_from_scoring" variant="warning" class="w-fit">Excluded from scoring</Badge>
              </CardHeader>
              <CardContent class="flex min-w-0 flex-col gap-4">
                <dl class="grid grid-cols-2 gap-3 text-sm"><div v-for="(cell, index) in evidenceCells(row)" :key="index" class="min-w-0"><dt class="text-muted-foreground">{{ columns[index] }}</dt><dd class="break-words">{{ cell }}</dd></div></dl>
                <CollapsibleTrigger as-child><Button variant="outline" class="w-fit" :aria-label="`Details for ${row.record_type} ${row.record_id}`">{{ openRows[rowKey(row)] ? 'Hide details' : 'View details' }}<ChevronDownIcon data-icon="inline-end" /></Button></CollapsibleTrigger>
                <CollapsibleContent><EvidenceRecordDetails :row="row" /></CollapsibleContent>
              </CardContent>
            </Card>
          </Collapsible>
        </div>
      </template>
    </CardContent>
    <CardFooter class="flex flex-wrap items-center justify-between gap-3">
      <p class="text-sm text-muted-foreground" aria-live="polite">{{ range }}</p>
      <nav class="flex gap-2" :aria-label="`${evidenceLabels[kpi]} evidence pages`">
        <Button variant="outline" size="sm" :disabled="loading || disabled || activePage <= 1" @click="changePage(activePage - 1)"><ChevronLeftIcon data-icon="inline-start" />Previous</Button>
        <Button variant="outline" size="sm" :disabled="loading || disabled || activePage * pageSize >= total" @click="changePage(activePage + 1)">Next<ChevronRightIcon data-icon="inline-end" /></Button>
      </nav>
    </CardFooter>
  </Card>
</template>

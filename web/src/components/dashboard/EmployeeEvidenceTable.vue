<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from 'vue'
import { ChevronDownIcon, ChevronLeftIcon, ChevronRightIcon, TriangleAlertIcon } from '@lucide/vue'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Spinner } from '@/components/ui/spinner'
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import EvidenceRecordDetails from '@/components/dashboard/EvidenceRecordDetails.vue'
import EvidenceRecordIssues from '@/components/dashboard/EvidenceRecordIssues.vue'
import { evidenceSummaryCells, evidenceSummaryColumns, evidenceLabels, evidenceNeedsReview } from '@/lib/employee-evidence'
import { cn } from '@/lib/utils'
import type { EmployeeEvidenceRow, EvidenceKpi, EvidencePageSize } from '@/types/employee-evidence'

const props = withDefaults(defineProps<{
  kpi: EvidenceKpi
  rows: EmployeeEvidenceRow[]
  total: number
  allRecordsCount?: number
  needsReviewCount?: number
  reviewOnly?: boolean
  page?: number
  pageSize?: EvidencePageSize
  loading?: boolean
  error?: string
  report?: boolean
  disabled?: boolean
}>(), { page: 1, pageSize: 5, loading: false, error: '', report: false, disabled: false, reviewOnly: false })
const emit = defineEmits<{ pageChange: [page: number], reviewChange: [reviewOnly: boolean], pageSizeChange: [pageSize: EvidencePageSize], retry: [] }>()
const openRows = ref<Record<string, boolean>>({})
const previewPage = ref(1)
const previewReviewOnly = ref(false)
const previewPageSize = ref<EvidencePageSize>(5)
const showUpdating = ref(false)
let indicatorTimer: ReturnType<typeof setTimeout> | undefined
watch(() => props.loading, loading => {
  clearTimeout(indicatorTimer)
  showUpdating.value = false
  if (loading) indicatorTimer = setTimeout(() => { showUpdating.value = true }, 180)
}, { immediate: true })
onScopeDispose(() => clearTimeout(indicatorTimer))
const columns = computed(() => evidenceSummaryColumns(props.kpi))
const sectionTones: Record<EvidenceKpi, { header: string, marker: string }> = {
  productivity: { header: 'bg-primary/5', marker: 'bg-primary' },
  compliance: { header: 'bg-warning/8', marker: 'bg-chart-2' },
  quality: { header: 'bg-muted/40', marker: 'bg-foreground' },
}
const sectionTone = computed(() => sectionTones[props.kpi])
const selectedFilterClass = 'h-9 rounded-none border-b-2 border-transparent bg-transparent! px-1.5 text-muted-foreground hover:text-foreground data-[state=on]:border-foreground data-[state=on]:text-foreground'
const issuesLabel = computed(() => props.kpi === 'compliance' ? 'Issues / scoring note' : 'Issues')
const activePage = computed(() => props.report ? previewPage.value : props.page)
const activePageSize = computed(() => props.report ? previewPageSize.value : props.pageSize)
const numericPageSize = computed(() => activePageSize.value === 'all' ? Math.max(1, selectedTotal.value) : activePageSize.value)
const activeReviewOnly = computed(() => props.report ? previewReviewOnly.value : props.reviewOnly)
const reviewCount = computed(() => props.report ? props.rows.filter(evidenceNeedsReview).length : props.needsReviewCount)
const allCount = computed(() => props.allRecordsCount ?? props.total)
const previewRows = computed(() => previewReviewOnly.value ? props.rows.filter(evidenceNeedsReview) : props.rows)
const selectedTotal = computed(() => props.report ? previewRows.value.length : props.total)
const visibleRows = computed(() => props.report
  ? previewRows.value.slice((previewPage.value - 1) * numericPageSize.value, previewPage.value * numericPageSize.value)
  : props.rows)
const range = computed(() => selectedTotal.value === 0 ? '0–0 of 0' : `${(activePage.value - 1) * numericPageSize.value + 1}–${Math.min(activePage.value * numericPageSize.value, selectedTotal.value)} of ${selectedTotal.value}${activeReviewOnly.value ? ' needing review' : ''}`)
function rowKey(row: EmployeeEvidenceRow): string { return `${row.record_type}:${row.record_id}` }
function recordLabel(row: EmployeeEvidenceRow): string {
  return `${openRows.value[rowKey(row)] ? 'Hide' : 'View'} record`
}
function changePage(page: number): void {
  if (props.report) previewPage.value = page
  else emit('pageChange', page)
}
function changePageSize(value: unknown): void {
  if (value !== '5' && value !== '15' && value !== '30' && value !== 'all') return
  const size = value === 'all' ? 'all' : Number(value) as 5 | 15 | 30
  if (props.loading || props.disabled || size === activePageSize.value) return
  if (props.report) { previewPageSize.value = size; previewPage.value = 1 }
  else emit('pageSizeChange', size)
}
function changeFilter(value: unknown): void {
  if (value !== 'all' && value !== 'review') return
  const reviewOnly = value === 'review'
  if (props.loading || props.disabled || (reviewOnly === activeReviewOnly.value && !props.error)) return
  if (props.report) { previewReviewOnly.value = reviewOnly; previewPage.value = 1 }
  else emit('reviewChange', reviewOnly)
}
watch(() => props.rows, rows => {
  const visibleKeys = new Set(rows.map(rowKey))
  openRows.value = Object.fromEntries(Object.entries(openRows.value).filter(([key]) => visibleKeys.has(key)))
  if (props.report) { previewPage.value = 1; previewReviewOnly.value = false }
})
</script>

<template>
  <Card class="min-w-0 gap-0 py-0" :aria-label="`${evidenceLabels[kpi]} evidence`">
    <CardHeader :class="cn('gap-2 border-b py-3', sectionTone.header)">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="min-w-0">
          <CardTitle>
            <h2 :aria-label="`${evidenceLabels[kpi]} evidence`" class="flex flex-wrap items-center gap-2">
              <span class="size-2.5 shrink-0 rounded-full" :class="sectionTone.marker" aria-hidden="true" />
              {{ evidenceLabels[kpi] }} evidence
            </h2>
          </CardTitle>
        </div>
        <div class="flex flex-wrap items-center gap-3">
          <ToggleGroup type="single" variant="default" :spacing="2" class="order-1 sm:order-2" :model-value="activeReviewOnly ? 'review' : 'all'" :data-busy="loading && !disabled && reviewCount !== undefined" :disabled="loading || disabled || reviewCount === undefined" :aria-label="`${evidenceLabels[kpi]} record filter`" @update:model-value="changeFilter">
            <ToggleGroupItem value="all" :class="selectedFilterClass">All records ({{ reviewCount === undefined ? '…' : allCount }})</ToggleGroupItem>
            <ToggleGroupItem value="review" :class="selectedFilterClass"><TriangleAlertIcon v-if="reviewCount" data-icon="inline-start" />Needs review ({{ reviewCount ?? '…' }})</ToggleGroupItem>
          </ToggleGroup>
          <div class="order-2 flex min-h-4 w-4 items-center gap-2 text-xs text-muted-foreground sm:order-1 sm:w-36" role="status" aria-live="polite">
            <template v-if="showUpdating && reviewCount !== undefined"><Spinner /><span class="sr-only sm:not-sr-only">Updating records…</span></template>
          </div>
        </div>
      </div>
    </CardHeader>
    <CardContent class="min-w-0 px-0" :aria-busy="loading">
      <Alert v-if="error" variant="destructive" class="m-4">
        <AlertTitle>{{ evidenceLabels[kpi] }} evidence unavailable</AlertTitle>
        <AlertDescription class="flex flex-col gap-2">
          <p>{{ error }}</p>
          <Button variant="outline" class="w-fit" :disabled="loading || disabled" @click="emit('retry')">Retry evidence</Button>
        </AlertDescription>
      </Alert>
      <div v-if="loading && reviewCount === undefined" class="flex min-h-24 items-center gap-3 px-4 py-6 text-sm text-muted-foreground" role="status"><Spinner />Loading {{ evidenceLabels[kpi].toLowerCase() }} evidence…</div>
      <p v-if="reviewCount !== undefined && !error && !selectedTotal" class="px-4 py-8 text-sm text-muted-foreground">{{ activeReviewOnly ? 'No records need review for this reporting period.' : `No ${evidenceLabels[kpi].toLowerCase()} evidence records for this reporting period.` }}</p>
      <template v-if="visibleRows.length && !disabled">
        <div class="hidden md:block">
          <Table class="table-fixed">
            <TableCaption class="sr-only">{{ evidenceLabels[kpi] }} records</TableCaption>
            <TableHeader class="bg-muted/30"><TableRow>
              <TableHead v-for="column in columns" :key="column" class="px-4 whitespace-normal">{{ column }}</TableHead>
              <TableHead class="w-1/4 px-4 whitespace-normal">{{ issuesLabel }}</TableHead>
              <TableHead class="w-36 px-4">Details</TableHead>
            </TableRow></TableHeader>
            <Collapsible v-for="(row, rowIndex) in visibleRows" :key="rowKey(row)" v-model:open="openRows[rowKey(row)]" as-child>
              <TableBody>
                <TableRow :class="cn(rowIndex % 2 === 1 && 'bg-muted/15', evidenceNeedsReview(row) && 'bg-warning/10 hover:bg-warning/15')">
                  <TableCell v-for="(cell, index) in evidenceSummaryCells(row)" :key="index" :class="cn('px-4 py-2.5 align-top whitespace-normal wrap-break-word', index === 0 && 'font-medium', index === 0 && evidenceNeedsReview(row) && 'border-l-2 border-l-warning')">
                    {{ cell }}
                  </TableCell>
                  <TableCell class="px-4 py-2.5 align-top whitespace-normal"><EvidenceRecordIssues :row="row" /></TableCell>
                  <TableCell class="px-4 py-2.5 align-top"><CollapsibleTrigger as-child><Button variant="ghost" size="sm" class="h-auto max-w-full whitespace-normal wrap-break-word" :aria-label="`${openRows[rowKey(row)] ? 'Hide' : 'View'} record ${row.record_type} ${row.record_id}`">{{ recordLabel(row) }}<ChevronDownIcon data-icon="inline-end" /></Button></CollapsibleTrigger></TableCell>
                </TableRow>
                <CollapsibleContent as-child><TableRow><TableCell :colspan="columns.length + 2" class="bg-muted/30 p-4"><EvidenceRecordDetails :row="row" /></TableCell></TableRow></CollapsibleContent>
              </TableBody>
            </Collapsible>
          </Table>
        </div>
        <div class="flex flex-col gap-3 px-4 py-4 md:hidden">
          <Collapsible v-for="row in visibleRows" :key="rowKey(row)" v-model:open="openRows[rowKey(row)]" as-child>
            <Card :class="cn('min-w-0', evidenceNeedsReview(row) && 'bg-warning/10')">
              <CardHeader :class="cn('border-b', evidenceNeedsReview(row) ? 'bg-warning/15' : 'bg-muted/30')"><CardTitle class="wrap-break-words">{{ row.record_id }}</CardTitle></CardHeader>
              <CardContent class="flex min-w-0 flex-col gap-4">
                <dl class="grid grid-cols-2 gap-3 text-sm"><div v-for="(cell, index) in evidenceSummaryCells(row)" :key="index" class="min-w-0"><dt class="text-muted-foreground">{{ columns[index] }}</dt><dd class="wrap-break-word">{{ cell }}</dd></div><div class="col-span-2 min-w-0"><dt class="text-muted-foreground">{{ issuesLabel }}</dt><dd><EvidenceRecordIssues :row="row" /></dd></div></dl>
                <CollapsibleTrigger as-child><Button variant="outline" class="h-auto w-fit max-w-full whitespace-normal wrap-break-word" :aria-label="`${openRows[rowKey(row)] ? 'Hide' : 'View'} record ${row.record_type} ${row.record_id}`">{{ recordLabel(row) }}<ChevronDownIcon data-icon="inline-end" /></Button></CollapsibleTrigger>
                <CollapsibleContent><EvidenceRecordDetails :row="row" /></CollapsibleContent>
              </CardContent>
            </Card>
          </Collapsible>
        </div>
      </template>
    </CardContent>
    <CardFooter class="flex flex-col gap-3 py-3 sm:flex-row sm:justify-between">
      <div class="flex flex-wrap items-center gap-3 text-sm text-muted-foreground" aria-live="polite">
        <span>{{ range }}</span>
        <Select :model-value="String(activePageSize)" :disabled="loading || disabled" @update:model-value="changePageSize">
          <SelectTrigger class="w-20" :aria-label="`${evidenceLabels[kpi]} rows per page`"><SelectValue /></SelectTrigger>
          <SelectContent><SelectGroup><SelectItem value="5">5</SelectItem><SelectItem value="15">15</SelectItem><SelectItem value="30">30</SelectItem><SelectItem value="all">All</SelectItem></SelectGroup></SelectContent>
        </Select>
        <span>rows per page</span>
      </div>
      <nav class="flex gap-2" :aria-label="`${evidenceLabels[kpi]} evidence pages`">
        <Button variant="outline" size="sm" :data-busy="loading && !disabled && activePage > 1" :disabled="loading || disabled || activePage <= 1" @click="changePage(activePage - 1)"><ChevronLeftIcon data-icon="inline-start" />Previous</Button>
        <Button variant="outline" size="sm" :data-busy="loading && !disabled && activePage * numericPageSize < selectedTotal" :disabled="loading || disabled || activePage * numericPageSize >= selectedTotal" @click="changePage(activePage + 1)">Next<ChevronRightIcon data-icon="inline-end" /></Button>
      </nav>
    </CardFooter>
  </Card>
</template>

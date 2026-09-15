<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from 'vue'
import { ChevronDownIcon, ChevronLeftIcon, ChevronRightIcon, CircleHelpIcon, TriangleAlertIcon } from '@lucide/vue'
import { PopoverContent, PopoverPortal, PopoverRoot, PopoverTrigger } from 'reka-ui'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Spinner } from '@/components/ui/spinner'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import EvidenceRecordDetails from '@/components/dashboard/EvidenceRecordDetails.vue'
import EvidenceRecordIssues from '@/components/dashboard/EvidenceRecordIssues.vue'
import { evidenceSummaryCells, evidenceSummaryColumns, evidenceLabels, evidenceNeedsReview, evidenceCalculations } from '@/lib/employee-evidence'
import { cn } from '@/lib/utils'
import type { EmployeeEvidenceRow, EvidenceKpi } from '@/types/employee-evidence'

const props = withDefaults(defineProps<{
  kpi: EvidenceKpi
  score: number | null
  weight: number
  explanation: string
  rows: EmployeeEvidenceRow[]
  total: number
  allRecordsCount?: number
  needsReviewCount?: number
  reviewOnly?: boolean
  page?: number
  pageSize?: number
  loading?: boolean
  error?: string
  report?: boolean
  disabled?: boolean
}>(), { page: 1, pageSize: 5, loading: false, error: '', report: false, disabled: false, reviewOnly: false })
const emit = defineEmits<{ pageChange: [page: number], reviewChange: [reviewOnly: boolean], retry: [] }>()
const openRows = ref<Record<string, boolean>>({})
const calculationOpen = ref(false)
const previewPage = ref(1)
const previewReviewOnly = ref(false)
const showUpdating = ref(false)
let indicatorTimer: ReturnType<typeof setTimeout> | undefined
watch(() => props.loading, loading => {
  clearTimeout(indicatorTimer)
  showUpdating.value = false
  if (loading) indicatorTimer = setTimeout(() => { showUpdating.value = true }, 180)
}, { immediate: true })
onScopeDispose(() => clearTimeout(indicatorTimer))
const columns = computed(() => evidenceSummaryColumns(props.kpi))
const issuesLabel = computed(() => props.kpi === 'compliance' ? 'Issues / scoring note' : 'Issues')
const activePage = computed(() => props.report ? previewPage.value : props.page)
const activeReviewOnly = computed(() => props.report ? previewReviewOnly.value : props.reviewOnly)
const reviewCount = computed(() => props.report ? props.rows.filter(evidenceNeedsReview).length : props.needsReviewCount)
const allCount = computed(() => props.allRecordsCount ?? props.total)
const previewRows = computed(() => previewReviewOnly.value ? props.rows.filter(evidenceNeedsReview) : props.rows)
const selectedTotal = computed(() => props.report ? previewRows.value.length : props.total)
const visibleRows = computed(() => props.report
  ? previewRows.value.slice((previewPage.value - 1) * props.pageSize, previewPage.value * props.pageSize)
  : props.rows)
const range = computed(() => selectedTotal.value === 0 ? '0 records' : `Records ${(activePage.value - 1) * props.pageSize + 1}–${Math.min(activePage.value * props.pageSize, selectedTotal.value)} of ${selectedTotal.value}${activeReviewOnly.value ? ' needing review' : ''}`)
function rowKey(row: EmployeeEvidenceRow): string { return `${row.record_type}:${row.record_id}` }
function recordLabel(row: EmployeeEvidenceRow): string {
  return `${openRows.value[rowKey(row)] ? 'Hide' : 'View'} record`
}
function changePage(page: number): void {
  if (props.report) previewPage.value = page
  else emit('pageChange', page)
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
  <Card class="min-w-0" :aria-label="`${evidenceLabels[kpi]} evidence`">
    <CardHeader>
      <div class="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3">
        <div class="flex min-w-0 flex-col gap-1">
          <CardTitle>
            <h2 :aria-label="`${evidenceLabels[kpi]} evidence`">
              {{ evidenceLabels[kpi] }}
              <span class="inline-flex items-center gap-0.5 align-middle">
                evidence
                <PopoverRoot v-if="!report" v-model:open="calculationOpen">
                  <PopoverTrigger as-child>
                    <Button variant="ghost" size="icon-sm" class="size-7 rounded-full"
                      :aria-label="`How ${evidenceLabels[kpi]} score is calculated`">
                      <CircleHelpIcon aria-hidden="true" class="size-4" />
                    </Button>
                  </PopoverTrigger>
                  <PopoverPortal>
                    <PopoverContent side="bottom" align="start" :side-offset="6" class="z-[60] w-56 max-w-[calc(100vw-2rem)] rounded-md border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md outline-none"
                      :aria-label="`${evidenceLabels[kpi]} calculation`">
                      {{ evidenceCalculations[kpi] }}
                    </PopoverContent>
                  </PopoverPortal>
                </PopoverRoot>
              </span>
            </h2>
          </CardTitle>
          <CardDescription>{{ weight }}% of overall</CardDescription>
        </div>
        <strong class="text-3xl tabular-nums" :aria-label="`${evidenceLabels[kpi]} score`">{{ score === null ? '—' : `${score.toFixed(1)}%` }}</strong>
      </div>
      <CardDescription class="whitespace-normal break-words">{{ explanation }}</CardDescription>
      <Button v-if="reviewCount" variant="link" size="sm" class="h-auto w-fit max-w-full whitespace-normal" :data-busy="loading && !disabled" :disabled="loading || disabled" @click="changeFilter('review')">
        <TriangleAlertIcon data-icon="inline-start" />{{ reviewCount }} {{ reviewCount === 1 ? 'record needs' : 'records need' }} review
      </Button>
    </CardHeader>
    <CardContent class="flex min-w-0 flex-col gap-4" :aria-busy="loading">
      <p v-if="report" class="text-sm text-muted-foreground">All {{ total }} records are included in the PDF. Browse the preview below.</p>
      <ToggleGroup type="single" variant="outline" :model-value="activeReviewOnly ? 'review' : 'all'" :data-busy="loading && !disabled && reviewCount !== undefined" :disabled="loading || disabled || reviewCount === undefined" :aria-label="`${evidenceLabels[kpi]} record filter`" @update:model-value="changeFilter">
        <ToggleGroupItem value="all">All records ({{ reviewCount === undefined ? '…' : allCount }})</ToggleGroupItem>
        <ToggleGroupItem value="review">Needs review ({{ reviewCount ?? '…' }})</ToggleGroupItem>
      </ToggleGroup>
      <div class="flex min-h-5 items-center gap-2 text-xs text-muted-foreground" role="status" aria-live="polite">
        <template v-if="showUpdating && reviewCount !== undefined"><Spinner />Updating records…</template>
      </div>
      <Alert v-if="error" variant="destructive">
        <AlertTitle>{{ evidenceLabels[kpi] }} evidence unavailable</AlertTitle>
        <AlertDescription class="flex flex-col gap-2">
          <p>{{ error }}</p>
          <Button variant="outline" class="w-fit" :disabled="loading || disabled" @click="emit('retry')">Retry evidence</Button>
        </AlertDescription>
      </Alert>
      <div v-if="loading && reviewCount === undefined" class="flex min-h-24 items-center gap-3 text-sm text-muted-foreground" role="status"><Spinner />Loading {{ evidenceLabels[kpi].toLowerCase() }} evidence…</div>
      <p v-if="reviewCount !== undefined && !error && !selectedTotal" class="py-8 text-sm text-muted-foreground">{{ activeReviewOnly ? 'No records need review for this reporting period.' : `No ${evidenceLabels[kpi].toLowerCase()} evidence records for this reporting period.` }}</p>
      <template v-if="visibleRows.length && !disabled">
        <div class="hidden md:block">
          <Table class="table-fixed">
            <TableCaption>{{ evidenceLabels[kpi] }} records for the active reporting period. No findings does not imply perfect performance or scoring eligibility. Source statuses do not replace calculated results.<template v-if="kpi === 'compliance'"> Approved annual and sick leave are neutral.</template></TableCaption>
            <TableHeader><TableRow>
              <TableHead v-for="column in columns" :key="column" class="whitespace-normal">{{ column }}</TableHead>
              <TableHead class="w-1/4 whitespace-normal">{{ issuesLabel }}</TableHead>
              <TableHead class="w-36">Details</TableHead>
            </TableRow></TableHeader>
            <Collapsible v-for="row in visibleRows" :key="rowKey(row)" v-model:open="openRows[rowKey(row)]" as-child>
              <TableBody>
                <TableRow :class="cn(evidenceNeedsReview(row) && 'bg-warning/10 hover:bg-warning/15')">
                  <TableCell v-for="(cell, index) in evidenceSummaryCells(row)" :key="index" class="align-top whitespace-normal break-words">
                    {{ cell }}
                  </TableCell>
                  <TableCell class="align-top whitespace-normal"><EvidenceRecordIssues :row="row" /></TableCell>
                  <TableCell class="align-top"><CollapsibleTrigger as-child><Button variant="ghost" size="sm" class="h-auto max-w-full whitespace-normal break-words" :aria-label="`${openRows[rowKey(row)] ? 'Hide' : 'View'} record ${row.record_type} ${row.record_id}`">{{ recordLabel(row) }}<ChevronDownIcon data-icon="inline-end" /></Button></CollapsibleTrigger></TableCell>
                </TableRow>
                <CollapsibleContent as-child><TableRow><TableCell :colspan="columns.length + 2" class="bg-muted/30 p-4"><EvidenceRecordDetails :row="row" /></TableCell></TableRow></CollapsibleContent>
              </TableBody>
            </Collapsible>
          </Table>
        </div>
        <div class="flex flex-col gap-3 md:hidden">
          <Collapsible v-for="row in visibleRows" :key="rowKey(row)" v-model:open="openRows[rowKey(row)]" as-child>
            <Card :class="cn('min-w-0', evidenceNeedsReview(row) && 'bg-warning/10')">
              <CardHeader><CardTitle class="break-words">{{ row.record_id }}</CardTitle></CardHeader>
              <CardContent class="flex min-w-0 flex-col gap-4">
                <dl class="grid grid-cols-2 gap-3 text-sm"><div v-for="(cell, index) in evidenceSummaryCells(row)" :key="index" class="min-w-0"><dt class="text-muted-foreground">{{ columns[index] }}</dt><dd class="break-words">{{ cell }}</dd></div><div class="col-span-2 min-w-0"><dt class="text-muted-foreground">{{ issuesLabel }}</dt><dd><EvidenceRecordIssues :row="row" /></dd></div></dl>
                <CollapsibleTrigger as-child><Button variant="outline" class="h-auto w-fit max-w-full whitespace-normal break-words" :aria-label="`${openRows[rowKey(row)] ? 'Hide' : 'View'} record ${row.record_type} ${row.record_id}`">{{ recordLabel(row) }}<ChevronDownIcon data-icon="inline-end" /></Button></CollapsibleTrigger>
                <CollapsibleContent><EvidenceRecordDetails :row="row" /></CollapsibleContent>
              </CardContent>
            </Card>
          </Collapsible>
        </div>
        <p class="text-xs text-muted-foreground md:hidden">No findings does not imply perfect performance or scoring eligibility. Source statuses do not replace calculated results.<template v-if="kpi === 'compliance'"> Approved annual and sick leave are neutral.</template></p>
      </template>
    </CardContent>
    <CardFooter class="flex flex-wrap items-center justify-between gap-3">
      <p class="text-sm text-muted-foreground" aria-live="polite">{{ range }}</p>
      <nav class="flex gap-2" :aria-label="`${evidenceLabels[kpi]} evidence pages`">
        <Button variant="outline" size="sm" :data-busy="loading && !disabled && activePage > 1" :disabled="loading || disabled || activePage <= 1" @click="changePage(activePage - 1)"><ChevronLeftIcon data-icon="inline-start" />Previous</Button>
        <Button variant="outline" size="sm" :data-busy="loading && !disabled && activePage * pageSize < selectedTotal" :disabled="loading || disabled || activePage * pageSize >= selectedTotal" @click="changePage(activePage + 1)">Next<ChevronRightIcon data-icon="inline-end" /></Button>
      </nav>
    </CardFooter>
  </Card>
</template>

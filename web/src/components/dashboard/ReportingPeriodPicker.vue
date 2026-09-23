<script setup lang="ts">
import { computed, nextTick, ref, shallowRef, watch } from 'vue'
import { useMediaQuery } from '@vueuse/core'
import type { DateValue } from '@internationalized/date'
import { parseDate } from '@internationalized/date'
import type { DateRange } from 'reka-ui'
import { CalendarDaysIcon } from '@lucide/vue'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel, FieldLegend, FieldSet } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { RangeCalendar } from '@/components/ui/range-calendar'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { formatDate, parseDisplayDate } from '@/lib/date-format'
import type { AnalysisFilters, DashboardFilters } from '@/types/analysis'

type PeriodMode = 'full' | 'month' | 'six-months' | 'year' | 'range'
type DraftChoice = Exclude<PeriodMode, 'range'> | 'custom'
type PeriodSelection = Pick<DashboardFilters, 'period_preset' | 'start_date' | 'end_date'>

const quickRanges: { value: DraftChoice, label: string }[] = [
  { value: 'full', label: 'Full period' },
  { value: 'month', label: 'Last month' },
  { value: 'six-months', label: 'Last 6 months' },
  { value: 'year', label: 'Last year' },
  { value: 'custom', label: 'Custom range' },
]

const props = defineProps<{
  mode: PeriodMode
  filters: AnalysisFilters
  coverageStart: string | null
  coverageEnd: string | null
  disabled?: boolean
}>()

const emit = defineEmits<{
  change: [filters: PeriodSelection]
}>()

const open = ref(false)
const choice = ref<DraftChoice>('full')
const draftRange = shallowRef<DateRange>({ start: undefined, end: undefined })
const startText = ref('')
const endText = ref('')
const error = ref('')
const invalidField = ref<'start' | 'end' | null>(null)
const calendarPlaceholder = shallowRef<DateValue>(parseDate(new Date().toISOString().slice(0, 10)))
const twoMonths = useMediaQuery('(min-width: 768px)')

const triggerLabel = computed(() => {
  if (props.mode === 'range')
    return props.filters.start_date && props.filters.end_date
      ? props.filters.start_date === props.filters.end_date
        ? formatDate(props.filters.start_date)
        : `${formatDate(props.filters.start_date)} – ${formatDate(props.filters.end_date)}`
      : 'Custom range'
  if (props.mode === 'month') return 'Last month'
  if (props.mode === 'six-months') return 'Last 6 months'
  if (props.mode === 'year') return 'Last year'
  return 'Full period'
})

const selectedSummary = computed(() => {
  const start = parseDisplayDate(startText.value)
  const end = parseDisplayDate(endText.value)
  if (!start || !end || start > end)
    return 'Choose a start and end date'
  const label = quickRanges.find(item => item.value === choice.value)?.label
  const dates = start === end
    ? formatDate(start)
    : `${formatDate(start)} – ${formatDate(end)}`
  return choice.value === 'custom' ? dates : `${label}: ${dates}`
})


watch(open, (isOpen) => {
  if (!isOpen)
    return
  choice.value = props.mode === 'range' ? 'custom' : props.mode
  const range = props.mode === 'range'
    && props.filters.start_date && props.filters.end_date
    ? { start: parseDate(props.filters.start_date), end: parseDate(props.filters.end_date) }
    : previewRange(choice.value)
  setDraftRange(range)
  showRangeEnd(range)
  error.value = ''
  invalidField.value = null
})

function validIsoDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value))
    return false
  const parsed = new Date(`${value}T00:00:00Z`)
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value
}

function previewRange(value: DraftChoice): DateRange {
  const end = props.coverageEnd
  if (!end || !validIsoDate(end))
    return { start: undefined, end: undefined }
  if (value === 'custom')
    return draftRange.value.start && draftRange.value.end
      ? draftRange.value : previewRange('month')
  if (value === 'full')
    return { start: parseDate(props.coverageStart && validIsoDate(props.coverageStart) ? props.coverageStart : end), end: parseDate(end) }

  const months = value === 'month' ? 1 : value === 'six-months' ? 6 : 12
  const previewStart = parseDate(end).subtract({ months }).add({ days: 1 }).toString()
  return {
    start: parseDate(previewStart),
    end: parseDate(end),
  }
}

function setDraftRange(value: DateRange): void {
  draftRange.value = value
  startText.value = value.start ? formatDate(value.start.toString()) : ''
  endText.value = value.end ? formatDate(value.end.toString()) : ''
}

function showRangeEnd(value: DateRange): void {
  const end = value.end ?? (props.coverageEnd && validIsoDate(props.coverageEnd)
    ? parseDate(props.coverageEnd) : undefined)
  if (end)
    calendarPlaceholder.value = twoMonths.value ? end.subtract({ months: 1 }) : end
}

function setChoice(value: unknown): void {
  if (typeof value !== 'string' || !quickRanges.some(item => item.value === value))
    return
  const next = value as DraftChoice
  choice.value = next
  if (next !== 'custom') {
    const range = previewRange(next)
    setDraftRange(range)
    void nextTick(() => showRangeEnd(range))
  }
  error.value = ''
  invalidField.value = null
}

function handleCalendarChange(value: DateRange): void {
  choice.value = 'custom'
  setDraftRange(value)
  error.value = ''
  invalidField.value = null
}

function handleTypedDateChange(field: 'start' | 'end', value: string | number): void {
  if (field === 'start')
    startText.value = String(value)
  else
    endText.value = String(value)
  choice.value = 'custom'
  const start = parseDisplayDate(startText.value)
  const end = parseDisplayDate(endText.value)
  draftRange.value = {
    start: start ? parseDate(start) : undefined,
    end: end ? parseDate(end) : undefined,
  }
  if (end)
    showRangeEnd(draftRange.value)
  error.value = ''
  invalidField.value = null
}

function showError(field: 'start' | 'end', message: string): void {
  invalidField.value = field
  error.value = message
  document.getElementById(`${field}-date`)?.focus()
}

function apply(): void {
  if (props.disabled)
    return
  if (choice.value === 'full') {
    emit('change', {})
    open.value = false
    return
  }
  if (choice.value === 'month' || choice.value === 'six-months' || choice.value === 'year') {
    emit('change', { period_preset: choice.value })
    open.value = false
    return
  }
  const start = parseDisplayDate(startText.value)
  const end = parseDisplayDate(endText.value)
  if (!start) {
    showError('start', 'Enter a valid start date in DD/MM/YYYY format.')
    return
  }
  if (!end) {
    showError('end', 'Enter a valid end date in DD/MM/YYYY format.')
    return
  }
  if (start > end) {
    showError('end', 'End on or after the start date.')
    return
  }
  emit('change', { start_date: start, end_date: end })
  open.value = false
}
</script>

<template>
  <Dialog v-model:open="open">
    <DialogTrigger as-child>
      <Button
        id="period-filter"
        type="button"
        variant="outline"
        class="w-full justify-between font-normal"
        :disabled="disabled"
        :aria-label="`Reporting period: ${triggerLabel}`"
      >
        <span class="truncate">{{ triggerLabel }}</span>
        <CalendarDaysIcon data-icon="inline-end" aria-hidden="true" />
      </Button>
    </DialogTrigger>

    <DialogContent class="grid max-h-[calc(100dvh-2rem)] grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden sm:max-w-208">
      <DialogHeader>
        <DialogTitle>Reporting period</DialogTitle>
        <DialogDescription>Quick ranges end on the latest evidence date. Or select inclusive dates from the calendar.</DialogDescription>
      </DialogHeader>

      <div class="min-h-0 overflow-y-auto">
        <div class="grid gap-5 md:grid-cols-[10.5rem_minmax(0,1fr)]">
          <FieldSet class="gap-2">
            <FieldLegend class="text-sm">Quick ranges</FieldLegend>
            <ToggleGroup
              type="single"
              orientation="vertical"
              variant="outline"
              tone="brand"
              :spacing="1"
              :model-value="choice"
              class="w-full"
              aria-label="Quick reporting ranges"
              @update:model-value="setChoice"
            >
              <ToggleGroupItem
                v-for="item in quickRanges"
                :key="item.value"
                :value="item.value"
                class="w-full justify-start"
                :disabled="(item.value === 'month' || item.value === 'six-months' || item.value === 'year') && !coverageEnd"
              >
                {{ item.label }}
              </ToggleGroupItem>
            </ToggleGroup>
          </FieldSet>

          <div class="flex min-w-0 flex-col gap-4">
            <div class="min-w-0 overflow-x-auto">
              <RangeCalendar
                :model-value="draftRange"
                v-model:placeholder="calendarPlaceholder"
                :number-of-months="twoMonths ? 2 : 1"
                locale="en-GB"
                :week-starts-on="1"
                weekday-format="short"
                calendar-label="Reporting date range"
                class="w-fit rounded-lg border border-border bg-background"
                @update:model-value="handleCalendarChange"
              />
            </div>

            <FieldGroup class="grid gap-3 sm:grid-cols-2">
              <Field :data-invalid="invalidField === 'start'" class="gap-1.5">
                <FieldLabel for="start-date">Start date</FieldLabel>
                <Input
                  id="start-date"
                  :model-value="startText"
                  type="text"
                  inputmode="numeric"
                  placeholder="DD/MM/YYYY"
                  autocomplete="off"
                  :aria-invalid="invalidField === 'start'"
                  :aria-describedby="invalidField === 'start' ? 'range-date-help start-date-error' : 'range-date-help'"
                  @update:model-value="handleTypedDateChange('start', $event)"
                />
                <FieldError v-if="invalidField === 'start'" id="start-date-error">{{ error }}</FieldError>
              </Field>
              <Field :data-invalid="invalidField === 'end'" class="gap-1.5">
                <FieldLabel for="end-date">End date</FieldLabel>
                <Input
                  id="end-date"
                  :model-value="endText"
                  type="text"
                  inputmode="numeric"
                  placeholder="DD/MM/YYYY"
                  autocomplete="off"
                  :aria-invalid="invalidField === 'end'"
                  :aria-describedby="invalidField === 'end' ? 'range-date-help end-date-error' : 'range-date-help'"
                  @update:model-value="handleTypedDateChange('end', $event)"
                />
                <FieldError v-if="invalidField === 'end'" id="end-date-error">{{ error }}</FieldError>
              </Field>
            </FieldGroup>
            <FieldDescription id="range-date-help">
              Dates use DD/MM/YYYY. Set both dates to the same day for one day. Evidence on file: {{ coverageStart ? formatDate(coverageStart) : 'unknown' }} – {{ coverageEnd ? formatDate(coverageEnd) : 'unknown' }}. You can select dates without evidence.
            </FieldDescription>
          </div>
        </div>

        <div class="mt-4 flex flex-wrap items-start justify-between gap-2 border-t border-border pt-4 text-sm">
          <div class="flex flex-col gap-1" aria-live="polite">
            <p class="font-medium">{{ selectedSummary }}</p>
          </div>
        </div>
      </div>

      <DialogFooter>
        <Button type="button" variant="outline" @click="open = false">Cancel</Button>
        <Button type="button" :disabled="disabled || ((choice === 'month' || choice === 'six-months' || choice === 'year') && !coverageEnd)" @click="apply">Apply period</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

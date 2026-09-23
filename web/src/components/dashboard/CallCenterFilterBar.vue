<script setup lang="ts">
import { computed } from 'vue'
import ReportingPeriodPicker from '@/components/dashboard/ReportingPeriodPicker.vue'
import { Button } from '@/components/ui/button'
import { Field, FieldLabel } from '@/components/ui/field'
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import type { AnalysisFilters, DashboardFilters } from '@/types/analysis'

type FacetKey = 'campaign' | 'queue' | 'shift' | 'supervisor' | 'location'
type PeriodSelection = Pick<DashboardFilters, 'period_preset' | 'start_date' | 'end_date'>

const props = defineProps<{
  filters: AnalysisFilters
  requestedFilters: DashboardFilters
  coverageStart: string | null
  coverageEnd: string | null
  campaigns: string[]
  queues: string[]
  shifts: string[]
  supervisors: string[]
  locations: string[]
  disabled?: boolean
}>()

const emit = defineEmits<{
  facetChange: [key: FacetKey, value: string]
  periodChange: [selection: PeriodSelection]
}>()

const facetFields = computed(() => [
  { key: 'campaign' as const, label: 'Campaign', allLabel: 'All campaigns', options: props.campaigns },
  { key: 'queue' as const, label: 'Queue', allLabel: 'All queues', options: props.queues },
  { key: 'shift' as const, label: 'Shift', allLabel: 'All shifts', options: props.shifts },
  { key: 'supervisor' as const, label: 'Supervisor', allLabel: 'All supervisors', options: props.supervisors },
  { key: 'location' as const, label: 'Location', allLabel: 'All locations', options: props.locations },
])

const periodMode = computed<'full' | 'month' | 'six-months' | 'year' | 'range'>(() => {
  if (props.requestedFilters.period_preset)
    return props.requestedFilters.period_preset
  if (props.requestedFilters.start_date || props.requestedFilters.end_date || props.requestedFilters.period_weeks)
    return 'range'
  return 'full'
})

function parseIso(value: string): Date | null {
  const parsed = new Date(`${value}T00:00:00Z`)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

function isoDate(value: Date): string {
  return value.toISOString().slice(0, 10)
}

function calendarMonthRange(anchor: string): PeriodSelection | null {
  const date = parseIso(anchor)
  if (!date)
    return null
  const year = date.getUTCFullYear()
  const month = date.getUTCMonth()
  return {
    start_date: isoDate(new Date(Date.UTC(year, month, 1))),
    end_date: isoDate(new Date(Date.UTC(year, month + 1, 0))),
  }
}

function quickRange(kind: 'today' | 'week' | 'month'): PeriodSelection | null {
  if (!props.coverageEnd)
    return null
  const anchor = parseIso(props.coverageEnd)
  if (!anchor)
    return null
  if (kind === 'today') {
    return { start_date: props.coverageEnd, end_date: props.coverageEnd }
  }
  if (kind === 'month')
    return calendarMonthRange(props.coverageEnd)
  const mondayOffset = (anchor.getUTCDay() + 6) % 7
  const start = new Date(anchor)
  start.setUTCDate(start.getUTCDate() - mondayOffset)
  const end = new Date(start)
  end.setUTCDate(end.getUTCDate() + 6)
  return { start_date: isoDate(start), end_date: isoDate(end) }
}

function isQuickRangeActive(kind: 'today' | 'week' | 'month'): boolean {
  const range = quickRange(kind)
  return Boolean(
    range
    && range.start_date === props.requestedFilters.start_date
    && range.end_date === props.requestedFilters.end_date,
  )
}

function selectQuickRange(kind: 'today' | 'week' | 'month'): void {
  const range = quickRange(kind)
  if (range)
    emit('periodChange', range)
}

function selectFacet(key: FacetKey, value: unknown): void {
  emit('facetChange', key, String(value))
}
</script>

<template>
  <section aria-label="Dashboard filters" class="rounded-xl border bg-background p-4">
    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-[minmax(34rem,2.5fr)_repeat(5,minmax(0,1fr))]">
      <Field class="min-w-0 gap-1.5 sm:col-span-2 lg:col-span-3 2xl:col-span-1 2xl:border-r 2xl:border-border 2xl:pr-3">
        <FieldLabel for="period-filter">Reporting period</FieldLabel>
        <div class="grid min-w-0 grid-cols-3 gap-2 sm:grid-cols-[minmax(9rem,1fr)_auto_auto_auto]">
          <div class="col-span-3 min-w-0 sm:col-span-1">
            <ReportingPeriodPicker
              :mode="periodMode"
              :filters="filters"
              :coverage-start="coverageStart"
              :coverage-end="coverageEnd"
              :disabled="disabled"
              @change="emit('periodChange', $event)"
            />
          </div>
          <Button type="button" size="sm" :variant="isQuickRangeActive('today') ? 'default' : 'outline'" :aria-pressed="isQuickRangeActive('today')" :disabled="disabled || !coverageEnd" @click="selectQuickRange('today')">Today</Button>
          <Button type="button" size="sm" :variant="isQuickRangeActive('week') ? 'default' : 'outline'" :aria-pressed="isQuickRangeActive('week')" :disabled="disabled || !coverageEnd" @click="selectQuickRange('week')">This week</Button>
          <Button type="button" size="sm" :variant="isQuickRangeActive('month') ? 'default' : 'outline'" :aria-pressed="isQuickRangeActive('month')" :disabled="disabled || !coverageEnd" @click="selectQuickRange('month')">This month</Button>
        </div>
      </Field>

      <Field v-for="field in facetFields" :key="field.key" class="min-w-0 gap-1.5">
        <FieldLabel :for="`${field.key}-filter`">{{ field.label }}</FieldLabel>
        <Select :model-value="filters[field.key] ?? 'all'" :disabled="disabled" @update:model-value="selectFacet(field.key, $event)">
          <SelectTrigger :id="`${field.key}-filter`" class="w-full bg-background"><SelectValue /></SelectTrigger>
          <SelectContent :body-lock="false">
            <SelectGroup>
              <SelectItem value="all">{{ field.allLabel }}</SelectItem>
              <SelectItem v-for="option in field.options" :key="option" :value="option">{{ option }}</SelectItem>
            </SelectGroup>
          </SelectContent>
        </Select>
      </Field>
    </div>
  </section>
</template>

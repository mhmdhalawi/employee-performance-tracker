<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import EmployeeDetailPage from '@/components/dashboard/EmployeeDetailPage.vue'
import { useDashboardBack } from '@/composables/useDashboardBack'
import type { DashboardFilters, DashboardResponse } from '@/types/analysis'

defineOptions({ inheritAttrs: false })

const props = defineProps<{
  analysis: DashboardResponse
  requestedFilters: DashboardFilters
  isFiltering: boolean
  filterError: string
}>()
const emit = defineEmits<{ filtersChange: [filters: DashboardFilters] }>()
const lastPeriodAttempt = ref<DashboardFilters | null>(null)

function refresh(): void {
  emit('filtersChange', props.filterError && lastPeriodAttempt.value
    ? { ...lastPeriodAttempt.value }
    : { ...props.requestedFilters })
}

function changePeriod(selection: Pick<DashboardFilters, 'period_preset' | 'start_date' | 'end_date'>): void {
  const filters = { ...props.requestedFilters }
  delete filters.period_weeks
  delete filters.period_preset
  delete filters.start_date
  delete filters.end_date
  lastPeriodAttempt.value = { ...filters, ...selection }
  emit('filtersChange', lastPeriodAttempt.value)
}

watch(() => props.requestedFilters, () => { lastPeriodAttempt.value = null })

const route = useRoute()
const router = useRouter()
const returnToDashboard = useDashboardBack()

const employeeId = computed(() => String(route.params.employeeId))
const employee = computed(() => props.analysis.results.find(row => row.employee_id === employeeId.value) ?? null)
const alerts = computed(() => props.analysis.alerts.filter(alert => alert.employee_id === employeeId.value))

watch(employee, (currentEmployee) => {
  if (!currentEmployee)
    void router.replace({ name: 'dashboard' })
}, { immediate: true })
</script>

<template>
  <EmployeeDetailPage
    v-if="employee"
    :employee="employee"
    :alerts="alerts"
    :reporting-period="analysis.applied_filters"
    :requested-filters="requestedFilters"
    :summary="analysis.summary"
    :coverage-start="analysis.coverage_start"
    :coverage-end="analysis.coverage_end"
    :latest-submission-at="analysis.latest_submission_at"
    :is-refreshing="isFiltering"
    :refresh-error="filterError"
    @refresh="refresh"
    @period-change="changePeriod"
    @back="returnToDashboard"
  />
</template>

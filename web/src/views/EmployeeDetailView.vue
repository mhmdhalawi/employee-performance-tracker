<script setup lang="ts">
import { computed, watch } from 'vue'
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

function refresh(): void {
  const filters = props.analysis.applied_filters
  emit('filtersChange', {
    employee_id: filters.employee_id ?? undefined,
    team: filters.team ?? undefined,
    period_weeks: props.requestedFilters.period_weeks,
    period_preset: props.requestedFilters.period_preset,
    start_date: props.requestedFilters.start_date,
    end_date: props.requestedFilters.end_date,
  })
}

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
    :latest-submission-at="analysis.latest_submission_at"
    :is-refreshing="isFiltering"
    :refresh-error="filterError"
    @refresh="refresh"
    @back="returnToDashboard"
  />
</template>

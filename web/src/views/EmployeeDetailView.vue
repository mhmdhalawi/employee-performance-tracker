<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import EmployeeDetailPage from '@/components/dashboard/EmployeeDetailPage.vue'
import { useDashboardBack } from '@/composables/useDashboardBack'
import type { DashboardResponse } from '@/types/analysis'

defineOptions({ inheritAttrs: false })

const props = defineProps<{
  analysis: DashboardResponse
}>()

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
    @back="returnToDashboard"
  />
</template>

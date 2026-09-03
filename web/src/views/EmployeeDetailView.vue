<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import EmployeeDetailPage from '@/components/dashboard/EmployeeDetailPage.vue'
import { useDashboardBack } from '@/composables/useDashboardBack'
import type { AIInsightResponse, DashboardResponse, EmployeeAIInsight, ErrorPayload } from '@/types/analysis'

defineOptions({ inheritAttrs: false })

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

const props = defineProps<{
  analysis: DashboardResponse
}>()

const route = useRoute()
const router = useRouter()
const returnToDashboard = useDashboardBack()
const insight = ref<EmployeeAIInsight | null>(null)
const insightLoading = ref(false)
const insightError = ref('')

const employeeId = computed(() => String(route.params.employeeId))
const employee = computed(() => props.analysis.results.find(row => row.employee_id === employeeId.value) ?? null)
const alerts = computed(() => props.analysis.alerts.filter(alert => alert.employee_id === employeeId.value))

watch(employee, (currentEmployee) => {
  if (!currentEmployee)
    void router.replace({ name: 'dashboard' })
}, { immediate: true })

async function generateInsight(): Promise<void> {
  if (insight.value || insightLoading.value)
    return

  insightLoading.value = true
  insightError.value = ''
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/insights`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        analysis_id: props.analysis.analysis_id,
        employee_id: employeeId.value,
      }),
    })
    if (!response.ok) {
      const payload = await response.json() as ErrorPayload
      throw new Error(payload.error?.message ?? 'AI guidance could not be generated.')
    }

    const payload = await response.json() as AIInsightResponse
    insight.value = payload.insight
  }
  catch (error) {
    insightError.value = error instanceof TypeError
      ? 'The guidance service is temporarily unavailable. Please try again shortly.'
      : error instanceof Error ? error.message : 'AI guidance could not be generated.'
  }
  finally {
    insightLoading.value = false
  }
}
</script>

<template>
  <EmployeeDetailPage
    v-if="employee"
    :employee="employee"
    :alerts="alerts"
    :insight="insight"
    :insight-loading="insightLoading"
    :insight-error="insightError"
    :reporting-period="analysis.applied_filters"
    @back="returnToDashboard"
    @generate-insight="generateInsight"
  />
</template>

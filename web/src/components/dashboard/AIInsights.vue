<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { CircleAlertIcon, LightbulbIcon, SparklesIcon } from '@lucide/vue'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'
import type { EmployeeAIInsight, EmployeeKpiResult } from '@/types/analysis'

const props = defineProps<{
  employees: EmployeeKpiResult[]
  insights: Record<string, EmployeeAIInsight>
  loadingEmployeeId: string | null
  error?: string
}>()
const emit = defineEmits<{
  generate: [employeeId: string]
}>()

const selectedEmployeeId = ref('')
const selectedEmployee = computed(() => props.employees.find(
  employee => employee.employee_id === selectedEmployeeId.value,
) ?? null)
const selectedInsight = computed(() => props.insights[selectedEmployeeId.value] ?? null)
const isLoading = computed(() => props.loadingEmployeeId === selectedEmployeeId.value)

watch(
  () => props.employees,
  (employees) => {
    if (!employees.some(employee => employee.employee_id === selectedEmployeeId.value))
      selectedEmployeeId.value = employees[0]?.employee_id ?? ''
  },
  { immediate: true },
)

function employeeLabel(employee: EmployeeKpiResult): string {
  return employee.employee_name || employee.employee_id
}
</script>

<template>
  <Card>
    <CardHeader>
      <div class="flex items-start justify-between gap-3">
        <div>
          <CardTitle class="flex items-center gap-2">
            <SparklesIcon aria-hidden="true" />
            AI explanations and recommendations
          </CardTitle>
          <CardDescription>
            Generate guidance for one employee from validated findings. Results are cached in this browser until the reporting period changes.
          </CardDescription>
        </div>
        <Badge variant="outline">On demand</Badge>
      </div>
    </CardHeader>
    <CardContent class="flex flex-col gap-4">
      <div v-if="employees.length" class="flex flex-col gap-3 sm:flex-row">
        <Select v-model="selectedEmployeeId" :disabled="Boolean(loadingEmployeeId)">
          <SelectTrigger class="w-full sm:max-w-sm" aria-label="Employee for AI guidance">
            <SelectValue placeholder="Select an employee" />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectItem v-for="employee in employees" :key="employee.employee_id" :value="employee.employee_id">
                {{ employeeLabel(employee) }}
              </SelectItem>
            </SelectGroup>
          </SelectContent>
        </Select>
        <Button
          :disabled="!selectedEmployeeId || Boolean(loadingEmployeeId) || Boolean(selectedInsight)"
          @click="emit('generate', selectedEmployeeId)"
        >
          <Spinner v-if="isLoading" data-icon="inline-start" />
          <SparklesIcon v-else data-icon="inline-start" />
          {{ isLoading ? 'Generating guidance…' : selectedInsight ? 'Guidance generated' : 'Generate AI guidance' }}
        </Button>
      </div>

      <Alert v-if="error" variant="destructive">
        <CircleAlertIcon aria-hidden="true" />
        <AlertTitle>AI guidance could not be generated</AlertTitle>
        <AlertDescription>{{ error }}</AlertDescription>
      </Alert>

      <Alert v-if="selectedInsight && selectedEmployee">
        <LightbulbIcon aria-hidden="true" />
        <AlertTitle>{{ employeeLabel(selectedEmployee) }}</AlertTitle>
        <AlertDescription class="flex flex-col gap-3">
          <div class="flex flex-col gap-2">
            <p>{{ selectedInsight.explanation.message }}</p>
            <div class="flex flex-wrap gap-1">
              <Badge v-for="recordId in selectedInsight.explanation.record_ids" :key="recordId" variant="secondary">
                {{ recordId }}
              </Badge>
            </div>
          </div>
          <div>
            <p class="font-medium text-foreground">Recommended next steps</p>
            <ul class="mt-1 flex list-disc flex-col gap-2 pl-5">
              <li v-for="recommendation in selectedInsight.recommendations" :key="recommendation.message">
                {{ recommendation.message }}
                <span class="mt-1 flex flex-wrap gap-1">
                  <Badge v-for="recordId in recommendation.record_ids" :key="recordId" variant="outline">
                    {{ recordId }}
                  </Badge>
                </span>
              </li>
            </ul>
          </div>
        </AlertDescription>
      </Alert>

      <p v-if="!employees.length" class="py-8 text-center text-sm text-muted-foreground">
        No employees with validated findings are available for this selection.
      </p>
    </CardContent>
  </Card>
</template>

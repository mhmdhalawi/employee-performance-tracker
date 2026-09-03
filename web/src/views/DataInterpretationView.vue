<script setup lang="ts">
import DataInterpretationPage from '@/components/dashboard/DataInterpretationPage.vue'
import { useDashboardBack } from '@/composables/useDashboardBack'
import type { DashboardResponse } from '@/types/analysis'

defineOptions({ inheritAttrs: false })

const props = defineProps<{
  analysis: DashboardResponse
}>()

const returnToDashboard = useDashboardBack()
</script>

<template>
  <DataInterpretationPage
    :mapping-summaries="props.analysis.mapping_summaries"
    @back="returnToDashboard"
  />
</template>

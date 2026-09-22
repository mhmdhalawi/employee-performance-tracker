<script setup lang="ts">
import { computed } from 'vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import EmployeeAttentionItem from '@/components/dashboard/EmployeeAttentionItem.vue'
import { findingCategoryLabel, needsAttention, type AttentionItem } from '@/lib/employee-presentation'
import type { FindingCategory } from '@/types/analysis'

const props = defineProps<{ items: AttentionItem[] }>()
const issues = computed(() => needsAttention(props.items))
const categories: FindingCategory[] = ['data_issue', 'performance_alert']
function inCategory(category: FindingCategory): AttentionItem[] {
  return issues.value.filter(issue => issue.category === category)
}
</script>

<template>
  <Card v-if="issues.length" aria-label="Findings requiring review">
    <CardHeader>
      <CardTitle><h2>Findings requiring review</h2></CardTitle>
      <CardDescription>Review the reason and action for each issue in this reporting period.</CardDescription>
    </CardHeader>
    <CardContent class="flex flex-col gap-6">
      <section v-for="category in categories.filter(value => inCategory(value).length)" :key="category" class="flex flex-col gap-3" :aria-label="findingCategoryLabel[category]">
        <h3 class="font-medium">{{ findingCategoryLabel[category] }} <Badge variant="warning">{{ inCategory(category).length }}</Badge></h3>
        <Collapsible v-slot="{ open }" class="flex flex-col gap-3">
          <EmployeeAttentionItem v-for="issue in inCategory(category).slice(0, 3)" :key="`${issue.code}-${issue.record_ids.join(',')}`" :issue="issue" />
          <CollapsibleContent v-if="inCategory(category).length > 3" class="flex flex-col gap-3">
            <EmployeeAttentionItem v-for="issue in inCategory(category).slice(3)" :key="`${issue.code}-${issue.record_ids.join(',')}`" :issue="issue" />
          </CollapsibleContent>
          <CollapsibleTrigger v-if="inCategory(category).length > 3" as-child>
            <Button variant="outline" class="w-fit">{{ open ? 'Show fewer issues' : `Show all ${inCategory(category).length} issues` }}</Button>
          </CollapsibleTrigger>
        </Collapsible>
      </section>
    </CardContent>
  </Card>
</template>

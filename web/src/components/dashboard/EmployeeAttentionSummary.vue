<script setup lang="ts">
import { computed } from 'vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import EmployeeAttentionItem from '@/components/dashboard/EmployeeAttentionItem.vue'
import { needsAttention, type AttentionItem } from '@/lib/employee-presentation'

const props = defineProps<{ items: AttentionItem[] }>()
const issues = computed(() => needsAttention(props.items))
</script>

<template>
  <Card v-if="issues.length" aria-label="Needs attention">
    <CardHeader>
      <CardTitle><h2>Needs attention <Badge variant="warning">{{ issues.length }}</Badge></h2></CardTitle>
      <CardDescription>Issues to review for this employee and reporting period.</CardDescription>
    </CardHeader>
    <CardContent>
      <Collapsible v-slot="{ open }" class="flex flex-col gap-3">
        <EmployeeAttentionItem v-for="issue in issues.slice(0, 3)" :key="issue.code" :issue="issue" />
        <CollapsibleContent v-if="issues.length > 3" class="flex flex-col gap-3">
          <EmployeeAttentionItem v-for="issue in issues.slice(3)" :key="issue.code" :issue="issue" />
        </CollapsibleContent>
        <CollapsibleTrigger v-if="issues.length > 3" as-child>
          <Button variant="outline" class="w-fit">{{ open ? 'Show fewer issues' : `Show all ${issues.length} issues` }}</Button>
        </CollapsibleTrigger>
      </Collapsible>
    </CardContent>
  </Card>
</template>

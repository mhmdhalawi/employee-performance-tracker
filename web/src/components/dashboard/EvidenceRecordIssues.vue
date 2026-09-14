<script setup lang="ts">
import { Badge } from '@/components/ui/badge'
import { evidenceIssueLabel } from '@/lib/employee-evidence'
import type { EmployeeEvidenceRow } from '@/types/employee-evidence'

defineProps<{ row: EmployeeEvidenceRow }>()
</script>

<template>
  <div class="flex min-w-0 flex-col gap-2">
    <template v-if="row.excluded_from_scoring">
      <Badge variant="warning">Excluded from scoring</Badge>
      <p class="break-words">{{ row.exclusion_reason }}</p>
    </template>
    <div v-for="(finding, index) in row.validation_findings" :key="`${finding.code}-${index}`" class="flex flex-col gap-1">
      <p class="break-words">{{ evidenceIssueLabel(finding.code) }}</p>
    </div>
    <p v-if="!row.excluded_from_scoring && !row.validation_findings.length" class="text-muted-foreground">No findings</p>
  </div>
</template>

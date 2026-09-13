<script setup lang="ts">
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { evidenceDetails, evidenceImpact, evidenceLink } from '@/lib/employee-evidence'
import type { EmployeeEvidenceRow } from '@/types/employee-evidence'

defineProps<{ row: EmployeeEvidenceRow }>()
</script>

<template>
  <div class="flex min-w-0 flex-col gap-4">
    <dl class="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
      <div v-for="[label, value] in evidenceDetails(row)" :key="label" class="min-w-0">
        <dt class="text-muted-foreground">{{ label }}</dt>
        <dd class="whitespace-normal break-words">{{ value }}</dd>
      </div>
    </dl>
    <p v-if="row.excluded_from_scoring" class="text-sm font-medium">Excluded from scoring: {{ row.exclusion_reason }}</p>
    <Button v-if="evidenceLink(row)" as-child variant="link" class="w-fit">
      <a :href="evidenceLink(row)!" target="_blank" rel="noopener noreferrer">Open evidence for {{ row.record_id }}</a>
    </Button>
    <Alert v-for="(finding, index) in row.validation_findings" :key="`${finding.code}-${index}`" :variant="finding.severity === 'info' ? 'default' : 'warning'">
      <AlertTitle>{{ finding.code.replaceAll('_', ' ') }}</AlertTitle>
      <AlertDescription class="flex flex-col gap-2">
        <p>{{ finding.message }}</p>
        <Badge variant="outline" class="w-fit">{{ evidenceImpact(finding.scoring_impact) }}</Badge>
        <p class="break-words">Records: {{ finding.record_ids.join(', ') }}</p>
      </AlertDescription>
    </Alert>
  </div>
</template>

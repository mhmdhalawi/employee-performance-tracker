<script setup lang="ts">
import { TriangleAlertIcon } from '@lucide/vue'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import type { AttentionItem } from '@/lib/employee-presentation'

defineProps<{ issue: AttentionItem }>()
function safeLinks(item: AttentionItem): string[] {
  return item.evidence_links.filter(link => {
    try { const url = new URL(link); return url.protocol === 'https:' && !!url.hostname }
    catch { return false }
  })
}
</script>

<template>
  <Alert :variant="issue.severity === 'error' ? 'destructive' : 'warning'">
    <TriangleAlertIcon aria-hidden="true" />
    <AlertTitle class="capitalize">{{ issue.code.replaceAll('_', ' ') }} <Badge variant="outline">{{ issue.occurrence_count }} occurrences</Badge></AlertTitle>
    <AlertDescription class="flex min-w-0 flex-col gap-2 [&_p]:mb-0">
      <p class="break-words">{{ issue.message }}</p>
      <Collapsible v-if="issue.record_ids.length || safeLinks(issue).length">
        <CollapsibleTrigger as-child><Button variant="link" size="sm" class="max-w-full whitespace-normal">Supporting records for {{ issue.code.replaceAll('_', ' ') }}</Button></CollapsibleTrigger>
        <CollapsibleContent class="flex flex-col gap-2 pt-2">
          <p class="break-words text-xs">{{ issue.record_ids.join(', ') }}</p>
          <a v-for="(link, linkIndex) in safeLinks(issue)" :key="link" :href="link" target="_blank" rel="noopener noreferrer" class="text-primary underline underline-offset-4">Open evidence {{ linkIndex + 1 }}</a>
        </CollapsibleContent>
      </Collapsible>
    </AlertDescription>
  </Alert>
</template>

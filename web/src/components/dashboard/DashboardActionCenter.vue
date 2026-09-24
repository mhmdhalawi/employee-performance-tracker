<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRightIcon, CircleAlertIcon, CircleCheckIcon, InfoIcon, TriangleAlertIcon } from '@lucide/vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { countAffectedEmployees, countFindings, summarizeActionCenter, type ActionGroupKey, type ActionGroupSummary } from '@/lib/action-center-summary'
import type { PerformanceAlert } from '@/types/analysis'

interface ActionGroup extends ActionGroupSummary {
  icon: typeof TriangleAlertIcon
  iconClass: string
}

const props = defineProps<{
  alerts: PerformanceAlert[]
  disabled?: boolean
}>()

const router = useRouter()
const sheetOpen = ref(false)
const selectedGroup = ref<ActionGroupKey | null>(null)

const groupPresentation: Record<ActionGroupKey, Pick<ActionGroup, 'icon' | 'iconClass'>> = {
  evidence: { icon: TriangleAlertIcon, iconClass: 'bg-warning/15 text-warning-foreground' },
  performance: { icon: CircleAlertIcon, iconClass: 'bg-secondary text-primary' },
  excluded: { icon: InfoIcon, iconClass: 'bg-muted text-muted-foreground' },
  other: { icon: InfoIcon, iconClass: 'bg-muted text-muted-foreground' },
}

function employeeLabel(count: number): string {
  return count === 1 ? '1 employee' : `${count} employees`
}

const summary = computed(() => summarizeActionCenter(props.alerts))
const groups = computed<ActionGroup[]>(() => summary.value.groups.map(group => ({ ...group, ...groupPresentation[group.key] })))
const totalFindings = computed(() => summary.value.totalFindings)
const activeGroup = computed(() => groups.value.find(group => group.key === selectedGroup.value))
const visibleAlerts = computed(() => selectedGroup.value ? activeGroup.value?.alerts ?? [] : props.alerts)
const sheetTitle = computed(() => activeGroup.value?.label ?? 'All findings')

function openSheet(group: ActionGroupKey | null): void {
  selectedGroup.value = group
  sheetOpen.value = true
}

function safeEvidenceLinks(alert: PerformanceAlert): string[] {
  return alert.evidence_links.filter((value) => {
    try {
      return new URL(value).protocol === 'https:'
    }
    catch {
      return false
    }
  })
}

function viewEmployee(employeeId: string): void {
  sheetOpen.value = false
  void router.push({ name: 'employee-detail', params: { employeeId } })
}
</script>

<template>
  <Card aria-label="Action Center" class="xl:h-full">
    <CardHeader class="gap-1">
      <div class="flex items-start justify-between gap-3">
        <div>
          <CardTitle>Action Center</CardTitle>
          <CardDescription>Findings for the selected filters</CardDescription>
        </div>
        <Badge variant="outline">{{ totalFindings }} findings</Badge>
      </div>
    </CardHeader>
    <CardContent class="flex flex-col xl:flex-1">
      <p v-if="!groups.length" class="flex items-center gap-2 py-6 text-sm text-muted-foreground">
        <CircleCheckIcon aria-hidden="true" /> No findings for the selected filters.
      </p>
      <div v-for="group in groups" :key="group.key" class="flex items-center gap-3 border-b border-border py-3 first:pt-0 last:border-0 last:pb-0 xl:flex-1 xl:first:pt-3 xl:last:pb-3">
        <span class="flex size-9 shrink-0 items-center justify-center rounded-full" :class="group.iconClass"><component :is="group.icon" class="size-4" aria-hidden="true" /></span>
        <div class="min-w-0 flex-1">
          <p class="font-medium">{{ group.label }}</p>
          <p class="text-xs text-muted-foreground">{{ group.findingCount }} findings · {{ employeeLabel(group.employeeCount) }}</p>
          <p class="text-xs text-muted-foreground">{{ group.description }}</p>
        </div>
        <Button type="button" variant="outline" size="sm" :disabled="disabled" :aria-label="`Review ${group.label.toLowerCase()}`" @click="openSheet(group.key)">Review</Button>
      </div>
      <Button v-if="groups.length" type="button" variant="ghost" size="sm" class="mt-4 self-end text-primary" :disabled="disabled" @click="openSheet(null)">
        View all findings <ArrowRightIcon data-icon="inline-end" />
      </Button>
    </CardContent>
  </Card>

  <Sheet v-model:open="sheetOpen">
    <SheetContent class="data-[side=right]:w-full data-[side=right]:sm:max-w-xl">
      <SheetHeader class="pr-12">
        <SheetTitle>Action Center · {{ sheetTitle }}</SheetTitle>
        <SheetDescription>{{ countFindings(visibleAlerts) }} findings affecting {{ employeeLabel(countAffectedEmployees(visibleAlerts)) }}. Review the supporting records and source action for each finding.</SheetDescription>
      </SheetHeader>
      <div class="min-h-0 flex-1 overflow-y-auto px-4 pb-4">
        <p v-if="!visibleAlerts.length" class="py-8 text-center text-muted-foreground">No findings for the selected filters.</p>
        <div v-else class="flex flex-col gap-3">
          <article v-for="(alert, index) in visibleAlerts" :key="`${alert.employee_id ?? 'global'}:${alert.code}:${index}`" class="flex flex-col gap-2 rounded-lg border border-border p-3">
            <div class="flex flex-wrap items-center gap-2">
              <Badge :variant="alert.category === 'data_issue' ? 'warning' : 'secondary'">{{ alert.category === 'data_issue' ? 'Data issue' : 'Performance alert' }}</Badge>
              <span class="text-xs text-muted-foreground">{{ alert.occurrence_count }} {{ alert.occurrence_count === 1 ? 'finding' : 'findings' }}</span>
            </div>
            <p class="font-medium">{{ alert.employee_name || alert.employee_id || 'Unmatched source record' }}</p>
            <p>{{ alert.message }}</p>
            <p class="text-xs text-muted-foreground"><span class="font-medium text-foreground">Review action:</span> {{ alert.action }}</p>
            <p v-if="alert.record_ids.length" class="break-all text-xs text-muted-foreground"><span class="font-medium text-foreground">Records:</span> {{ alert.record_ids.join(', ') }}</p>
            <div v-if="safeEvidenceLinks(alert).length" class="flex flex-wrap gap-2 text-xs">
              <a v-for="(link, linkIndex) in safeEvidenceLinks(alert)" :key="link" :href="link" target="_blank" rel="noopener noreferrer" class="text-primary underline underline-offset-2">Open source evidence {{ linkIndex + 1 }}</a>
            </div>
            <Button v-if="alert.employee_id" type="button" variant="outline" size="sm" class="self-start" :disabled="disabled" @click="viewEmployee(alert.employee_id)">View employee details</Button>
          </article>
        </div>
      </div>
    </SheetContent>
  </Sheet>
</template>

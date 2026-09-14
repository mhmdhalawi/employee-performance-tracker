<script setup lang="ts">
import { ChevronDownIcon } from '@lucide/vue'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'

const items = [
  { name: 'Productivity', explanation: '60% completion, 40% time efficiency.' },
  { name: 'Compliance', explanation: '50% attendance, 35% reporting, 15% leave compliance.' },
  { name: 'Quality', explanation: '60% accuracy, 25% first-pass approval, 15% rework.' },
]
</script>

<template>
  <Collapsible as-child>
    <Card>
      <CardHeader>
        <CardTitle><CollapsibleTrigger as-child><Button variant="ghost" class="w-fit">Calculation details<ChevronDownIcon data-icon="inline-end" /></Button></CollapsibleTrigger></CardTitle>
      </CardHeader>
      <CollapsibleContent as-child>
        <CardContent class="flex flex-col gap-4">
          <section v-for="item in items" :key="item.name" class="flex min-w-0 flex-col gap-1">
            <h3 class="font-medium">{{ item.name }}</h3>
            <p class="break-words text-sm text-muted-foreground">{{ item.explanation }}</p>
          </section>
        </CardContent>
      </CollapsibleContent>
    </Card>
  </Collapsible>
</template>

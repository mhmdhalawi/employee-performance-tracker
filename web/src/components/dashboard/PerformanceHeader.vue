<script setup lang="ts">
import { ArrowLeftIcon } from '@lucide/vue'
import cedarLogo from '@/assets/cedar-logo.png'
import { Button } from '@/components/ui/button'

defineProps<{ back?: boolean }>()
const emit = defineEmits<{ back: [] }>()
</script>

<template>
  <header class="border-b bg-background">
    <div class="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
      <div class="flex min-w-0 items-center gap-3">
        <img :src="cedarLogo" alt="Cedar Digital Solutions" class="w-16 shrink-0" />
        <div class="min-w-0">
          <p class="font-semibold">Employee performance</p>
          <Button v-if="back" variant="link" size="sm" @click="emit('back')"><ArrowLeftIcon data-icon="inline-start" />Back to dashboard</Button>
          <p v-else class="text-xs text-muted-foreground">Evidence-backed KPI review</p>
        </div>
      </div>
      <div class="flex flex-wrap items-center gap-2"><slot /></div>
    </div>
  </header>
</template>

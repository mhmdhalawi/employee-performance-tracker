<script setup lang="ts">
import { ArrowLeftIcon } from '@lucide/vue'
import cedarLogo from '@/assets/cedar-logo.png'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

defineProps<{ back?: boolean, wide?: boolean }>()
const emit = defineEmits<{ back: [] }>()
</script>

<template>
  <header class="border-b bg-background">
    <div :class="cn('mx-auto flex flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6', wide ? 'max-w-[1600px]' : 'max-w-7xl')">
      <div class="flex min-w-0 items-center gap-3">
        <img :src="cedarLogo" alt="Cedar Digital Solutions" class="w-16 shrink-0" />
        <div class="min-w-0">
          <p class="font-semibold">Employee performance</p>
          <Button v-if="back" variant="link" size="sm" @click="emit('back')"><ArrowLeftIcon data-icon="inline-start" />Back to dashboard</Button>
          <p v-else class="text-xs text-muted-foreground">Evidence-backed KPI review</p>
        </div>
      </div>
      <div class="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:justify-end"><slot /></div>
    </div>
  </header>
</template>

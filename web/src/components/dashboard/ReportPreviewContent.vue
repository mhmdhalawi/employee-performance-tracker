<script setup lang="ts">
import { DialogContent } from '@/components/ui/dialog'
</script>

<template>
  <DialogContent class="flex max-h-[calc(100svh-2rem)] flex-col gap-0 overflow-hidden p-0 sm:max-w-6xl">
    <div class="shrink-0 pr-6">
      <slot name="header" />
    </div>
    <div class="min-h-0 flex-1 overflow-y-auto bg-muted/30 p-4 sm:p-6" tabindex="0" aria-label="Report preview content">
      <div class="flex flex-col gap-5 [&>*]:shrink-0">
        <slot />
      </div>
    </div>
    <div v-if="$slots.footer" class="shrink-0">
      <slot name="footer" />
    </div>
  </DialogContent>
</template>

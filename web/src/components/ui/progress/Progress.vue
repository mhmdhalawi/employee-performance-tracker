<script setup lang="ts">
import type { ProgressRootProps } from 'reka-ui'
import type { HTMLAttributes } from 'vue'
import { reactiveOmit } from '@vueuse/core'
import {
  ProgressIndicator,
  ProgressRoot,
} from 'reka-ui'
import { cn } from '@/lib/utils'

const props = withDefaults(
  defineProps<ProgressRootProps & { class?: HTMLAttributes['class'], tone?: 'default' | 'warning' }>(),
  {
    modelValue: 0,
  },
)

const delegatedProps = reactiveOmit(props, 'class', 'tone')
</script>

<template>
  <ProgressRoot
    data-slot="progress"
    v-bind="delegatedProps"
    :class="
      cn(
        'bg-muted h-1 rounded-full relative flex w-full items-center overflow-x-hidden',
        props.class,
      )
    "
  >
    <ProgressIndicator
      data-slot="progress-indicator"
      :class="cn('size-full flex-1 transition-transform motion-reduce:transition-none', props.tone === 'warning' ? 'bg-warning' : 'bg-primary')"
      :style="`transform: translateX(-${100 - (props.modelValue ?? 0)}%);`"
    />
  </ProgressRoot>
</template>

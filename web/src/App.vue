<script setup lang="ts">
import { ref, watch } from 'vue'
import { CircleAlertIcon } from '@lucide/vue'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Spinner } from '@/components/ui/spinner'
import LoginScreen from '@/components/auth/LoginScreen.vue'
import PerformanceDashboard from '@/components/dashboard/PerformanceDashboard.vue'
import type { DashboardFilters, DashboardResponse, ErrorPayload } from '@/types/analysis'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

const isAuth = ref<boolean | undefined>(true)
const dashboardRequestError = ref('')
const analysis = ref<DashboardResponse | null>(null)
const isSubmitting = ref(false)
const isFiltering = ref(false)
const filterError = ref('')
let requestSequence = 0
let requestController: AbortController | null = null

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const payload = await response.json() as ErrorPayload
    return payload.error?.message ?? 'The request could not be completed.'
  }
  catch {
    return 'The request could not be completed.'
  }
}

async function requestStoredDashboard(
  filters: DashboardFilters = {},
  filtering = false,
): Promise<void> {
  const sequence = ++requestSequence
  requestController?.abort()
  requestController = new AbortController()
  if (filtering) {
    isFiltering.value = true
    filterError.value = ''
  }
  else {
    isSubmitting.value = true
    dashboardRequestError.value = ''
    analysis.value = null
  }

  try {
    const query = new URLSearchParams()
    for (const [key, value] of Object.entries(filters)) {
      if (value)
        query.set(key, value)
    }
    const endpoint = `${API_BASE_URL}/api/v1/dashboard${query.size ? `?${query}` : ''}`
    const response = await fetch(endpoint, {
      signal: requestController.signal,
    })

    if (!response.ok)
      throw new Error(await readErrorMessage(response))
    if (sequence !== requestSequence)
      return

    analysis.value = await response.json() as DashboardResponse
  }
  catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError')
      return

    const message = error instanceof TypeError
      ? 'The dashboard service is temporarily unavailable. Please try again shortly.'
      : error instanceof Error ? error.message : 'The dashboard could not be loaded.'
    if (filtering)
      filterError.value = message
    else
      dashboardRequestError.value = message
  }
  finally {
    if (sequence === requestSequence) {
      isSubmitting.value = false
      isFiltering.value = false
      requestController = null
    }
  }
}

watch(isAuth, (authenticated) => {
  if (authenticated && !analysis.value && !isSubmitting.value)
    void requestStoredDashboard()
}, { immediate: true })
</script>

<template>
  <LoginScreen v-if="isAuth !== true" @authenticated="isAuth = true" />
  <PerformanceDashboard
    v-else-if="analysis"
    :analysis="analysis"
    :is-filtering="isFiltering"
    :filter-error="filterError"
    @filters-change="requestStoredDashboard($event, true)"
  />
  <main v-else class="flex min-h-svh items-center bg-muted/30 px-4 py-8 sm:px-6">
    <Card class="mx-auto w-full max-w-lg">
      <CardHeader>
        <CardTitle>
          {{ dashboardRequestError ? 'Performance table unavailable' : 'Loading performance table' }}
        </CardTitle>
        <CardDescription>
          Fetching the latest analyzed results from the performance service.
        </CardDescription>
      </CardHeader>

      <CardContent>
        <Alert v-if="dashboardRequestError" variant="destructive">
          <CircleAlertIcon aria-hidden="true" />
          <AlertTitle>Dashboard could not load</AlertTitle>
          <AlertDescription>{{ dashboardRequestError }}</AlertDescription>
        </Alert>
        <div v-else class="flex items-center gap-3 text-sm text-muted-foreground">
          <Spinner />
          <span>Loading the latest completed submission…</span>
        </div>
      </CardContent>

      <CardFooter v-if="dashboardRequestError">
        <Button class="w-full" type="button" :disabled="isSubmitting" @click="requestStoredDashboard()">
          <Spinner v-if="isSubmitting" data-icon="inline-start" />
          Retry
        </Button>
      </CardFooter>
    </Card>
  </main>
</template>

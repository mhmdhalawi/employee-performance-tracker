<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  CircleAlertIcon,
  DatabaseIcon,
  FileSpreadsheetIcon,
  ShieldCheckIcon,
  UploadCloudIcon,
  XIcon,
} from '@lucide/vue'
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
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Spinner } from '@/components/ui/spinner'
import LoginScreen from '@/components/auth/LoginScreen.vue'
import PerformanceDashboard from '@/components/dashboard/PerformanceDashboard.vue'
import { cn } from '@/lib/utils'
import type { AnalyzeResponse, DashboardFilters, ErrorPayload } from '@/types/analysis'

const MAX_FILE_SIZE = 10 * 1024 * 1024
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'
const SAMPLE_REQUEST_URL = new URL('../data/request.json', import.meta.url)
// Temporary entry mode: set to true when manual upload access should return.
const SHOW_DATA_SOURCE_PAGE = false

type AnalysisSource = 'upload' | 'sample'

const isAuth = ref<boolean | undefined>(undefined)
const fileInput = ref<HTMLInputElement | null>(null)
const selectedFile = ref<File | null>(null)
const fileError = ref('')
const requestError = ref('')
const sampleRequestError = ref('')
const dashboardRequestError = ref('')
const analysis = ref<AnalyzeResponse | null>(null)
const isDragging = ref(false)
const isSubmitting = ref(false)
const showDashboard = ref(false)
const isFiltering = ref(false)
const filterError = ref('')
const activeSource = ref<AnalysisSource>('upload')
let requestSequence = 0
let requestController: AbortController | null = null
let sampleRequestBody: string | null = null

const selectedFileSize = computed(() => {
  if (!selectedFile.value)
    return ''

  const megabytes = selectedFile.value.size / (1024 * 1024)
  return megabytes >= 0.1 ? `${megabytes.toFixed(1)} MB` : `${Math.ceil(selectedFile.value.size / 1024)} KB`
})

function validateFile(file: File): string {
  const extension = file.name.split('.').pop()?.toLowerCase()

  if (extension !== 'csv' && extension !== 'xlsx')
    return 'Choose a CSV or XLSX file.'

  if (file.size > MAX_FILE_SIZE)
    return 'The file must be 10 MB or smaller.'

  if (file.size === 0)
    return 'The selected file is empty.'

  return ''
}

function selectFile(file: File | undefined): void {
  if (!file)
    return

  const validationError = validateFile(file)
  fileError.value = validationError
  requestError.value = ''
  sampleRequestError.value = ''
  analysis.value = null
  selectedFile.value = validationError ? null : file

  if (validationError && fileInput.value)
    fileInput.value.value = ''
}

function onFileChange(event: Event): void {
  const input = event.target as HTMLInputElement
  selectFile(input.files?.[0])
}

function onDrop(event: DragEvent): void {
  isDragging.value = false
  selectFile(event.dataTransfer?.files[0])
}

function clearFile(): void {
  selectedFile.value = null
  fileError.value = ''
  requestError.value = ''
  analysis.value = null

  if (fileInput.value)
    fileInput.value.value = ''
}

async function loadSampleRequest(signal: AbortSignal): Promise<string> {
  if (sampleRequestBody)
    return sampleRequestBody

  const response = await fetch(SAMPLE_REQUEST_URL, { signal })
  if (!response.ok)
    throw new Error('The bundled sample data could not be loaded.')

  sampleRequestBody = await response.text()
  return sampleRequestBody
}

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

    const result = await response.json() as AnalyzeResponse
    analysis.value = {
      ...result,
      file_name: 'Latest stored submission',
      file_type: 'json',
      byte_size: 0,
    }
    showDashboard.value = true
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

async function requestAnalysis(filters: DashboardFilters = {}, filtering = false): Promise<void> {
  const source = activeSource.value
  if (source === 'upload' && !selectedFile.value) {
    fileError.value = 'Select a CSV or XLSX file before submitting.'
    return
  }

  const sequence = ++requestSequence
  requestController?.abort()
  requestController = new AbortController()
  if (filtering) {
    isFiltering.value = true
    filterError.value = ''
  }
  else {
    isSubmitting.value = true
    if (source === 'sample')
      sampleRequestError.value = ''
    else
      requestError.value = ''
    analysis.value = null
  }

  try {
    const query = new URLSearchParams()
    for (const [key, value] of Object.entries(filters)) {
      if (value)
        query.set(key, value)
    }
    let body: BodyInit
    let headers: HeadersInit | undefined
    let endpointPath: string
    let sampleByteSize = 0

    if (source === 'sample') {
      body = await loadSampleRequest(requestController.signal)
      headers = { 'Content-Type': 'application/json' }
      endpointPath = '/api/v1/analyze-tables'
      sampleByteSize = new Blob([body]).size
    }
    else {
      const formData = new FormData()
      formData.append('file', selectedFile.value as File)
      body = formData
      endpointPath = '/api/v1/analyze'
    }

    const endpoint = `${API_BASE_URL}${endpointPath}${query.size ? `?${query}` : ''}`
    const response = await fetch(endpoint, {
      method: 'POST',
      body,
      headers,
      signal: requestController.signal,
    })

    if (!response.ok)
      throw new Error(await readErrorMessage(response))

    if (sequence !== requestSequence)
      return

    const result = await response.json() as AnalyzeResponse
    analysis.value = source === 'sample'
      ? {
          ...result,
          file_name: 'Cedar sample dataset',
          file_type: 'json',
          byte_size: sampleByteSize,
        }
      : result
    showDashboard.value = true
  }
  catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError')
      return

    const message = error instanceof TypeError
      ? 'The analysis service is temporarily unavailable. Please try again shortly.'
      : error instanceof Error ? error.message : 'The file could not be analyzed.'
    if (filtering)
      filterError.value = message
    else if (source === 'sample')
      sampleRequestError.value = message
    else
      requestError.value = message
  }
  finally {
    if (sequence === requestSequence) {
      isSubmitting.value = false
      isFiltering.value = false
      requestController = null
    }
  }
}

async function submitAnalysis(): Promise<void> {
  activeSource.value = 'upload'
  sampleRequestError.value = ''
  await requestAnalysis()
}

async function submitSampleAnalysis(): Promise<void> {
  activeSource.value = 'sample'
  requestError.value = ''
  await requestAnalysis()
}

async function requestDashboard(
  filters: DashboardFilters = {},
  filtering = false,
): Promise<void> {
  if (SHOW_DATA_SOURCE_PAGE)
    await requestAnalysis(filters, filtering)
  else
    await requestStoredDashboard(filters, filtering)
}

watch(isAuth, (authenticated) => {
  if (authenticated && !SHOW_DATA_SOURCE_PAGE && !analysis.value && !isSubmitting.value)
    void requestStoredDashboard()
}, { immediate: true })
</script>

<template>
  <LoginScreen v-if="isAuth !== true" @authenticated="isAuth = true" />
  <PerformanceDashboard
    v-else-if="showDashboard && analysis"
    :analysis="analysis"
    :is-filtering="isFiltering"
    :filter-error="filterError"
    :show-new-analysis="SHOW_DATA_SOURCE_PAGE"
    @back="showDashboard = false"
    @filters-change="requestDashboard($event, true)"
  />
  <main v-else-if="!SHOW_DATA_SOURCE_PAGE" class="flex min-h-svh items-center bg-muted/30 px-4 py-8 sm:px-6">
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
  <main v-else class="min-h-svh bg-muted/30 px-4 py-8 sm:px-6 sm:py-12">
    <div class="mx-auto flex w-full max-w-2xl flex-col gap-8">
      <header class="flex flex-col items-center gap-3 text-center">
        <div class="flex size-11 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
          <ShieldCheckIcon class="size-5" aria-hidden="true" />
        </div>
        <div class="flex flex-col gap-2">
          <p class="text-sm font-medium text-muted-foreground">
            Employee performance
          </p>
          <h1 class="text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
            Turn performance data into a clear, evidence-backed view
          </h1>
          <p class="mx-auto max-w-xl text-pretty text-sm leading-6 text-muted-foreground sm:text-base">
            Upload one CSV or Excel workbook. The service classifies its evidence, validates
            calculator inputs, and calculates every KPI deterministically.
          </p>
        </div>
      </header>

      <Card class="shadow-lg shadow-foreground/5">
        <CardHeader class="border-b">
          <CardTitle class="text-lg">
            Upload performance data
          </CardTitle>
          <CardDescription>
            Your file is processed for this analysis only and is not persisted.
          </CardDescription>
        </CardHeader>

        <form @submit.prevent="submitAnalysis">
          <CardContent class="py-2">
            <FieldGroup>
              <Field :data-invalid="Boolean(fileError)" :data-disabled="isSubmitting">
                <FieldLabel for="performance-file">
                  Data file
                </FieldLabel>

                <label
                  for="performance-file"
                  :class="cn(
                    'flex min-h-52 cursor-pointer flex-col items-center justify-center gap-4 rounded-xl border border-dashed bg-muted/30 px-6 py-8 text-center transition-colors hover:bg-muted/60',
                    isDragging && 'border-primary bg-primary/5',
                    fileError && 'border-destructive/60',
                    isSubmitting && 'pointer-events-none opacity-60',
                  )"
                  @dragenter.prevent="isDragging = true"
                  @dragover.prevent="isDragging = true"
                  @dragleave.prevent="isDragging = false"
                  @drop.prevent="onDrop"
                >
                  <input
                    id="performance-file"
                    ref="fileInput"
                    class="sr-only"
                    type="file"
                    accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    :disabled="isSubmitting"
                    :aria-invalid="Boolean(fileError)"
                    aria-describedby="file-help file-error"
                    @change="onFileChange"
                  >

                  <template v-if="selectedFile">
                    <div class="flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
                      <FileSpreadsheetIcon class="size-6" aria-hidden="true" />
                    </div>
                    <div class="flex max-w-full flex-col gap-1">
                      <span class="max-w-full truncate font-medium">{{ selectedFile.name }}</span>
                      <span class="text-sm text-muted-foreground">{{ selectedFileSize }} · Ready to analyze</span>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      :disabled="isSubmitting"
                      @click.prevent="clearFile"
                    >
                      <XIcon data-icon="inline-start" />
                      Remove
                    </Button>
                  </template>

                  <template v-else>
                    <div class="flex size-12 items-center justify-center rounded-xl bg-background text-muted-foreground ring-1 ring-border">
                      <UploadCloudIcon class="size-6" aria-hidden="true" />
                    </div>
                    <div class="flex flex-col gap-1">
                      <span class="font-medium">Drop your file here or browse</span>
                      <span class="text-sm text-muted-foreground">CSV or XLSX, up to 10 MB</span>
                    </div>
                  </template>
                </label>

                <FieldDescription id="file-help">
                  Use the original export where possible so source record IDs and evidence links remain traceable.
                </FieldDescription>
                <FieldError id="file-error" :errors="fileError ? [fileError] : []" />
              </Field>

              <Alert v-if="requestError" variant="destructive">
                <CircleAlertIcon aria-hidden="true" />
                <AlertTitle>Analysis could not start</AlertTitle>
                <AlertDescription>{{ requestError }}</AlertDescription>
              </Alert>

            </FieldGroup>
          </CardContent>

          <CardFooter class="flex-col items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p class="text-center text-xs text-muted-foreground sm:text-left">
              Analysis may take a few seconds while we identify relevant data and validate the evidence.
            </p>
            <Button class="w-full shrink-0 sm:w-auto" type="submit" size="lg" :disabled="isSubmitting || !selectedFile">
              <Spinner v-if="isSubmitting" data-icon="inline-start" />
              <UploadCloudIcon v-else data-icon="inline-start" />
              {{ isSubmitting ? 'Analyzing file…' : 'Submit for analysis' }}
            </Button>
          </CardFooter>
        </form>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle class="text-lg">
            Try the Cedar sample data
          </CardTitle>
          <CardDescription>
            Send the bundled JSON request through the same classification and KPI workflow.
          </CardDescription>
        </CardHeader>

        <CardContent>
          <Alert v-if="sampleRequestError" variant="destructive">
            <CircleAlertIcon aria-hidden="true" />
            <AlertTitle>Sample analysis could not start</AlertTitle>
            <AlertDescription>{{ sampleRequestError }}</AlertDescription>
          </Alert>
          <p v-else class="text-sm leading-6 text-muted-foreground">
            The request contains the Cedar workbook's 11 tables and 2,787 rows, already converted to the webhook JSON schema.
          </p>
        </CardContent>

        <CardFooter>
          <Button class="w-full" type="button" size="lg" :disabled="isSubmitting" @click="submitSampleAnalysis">
            <Spinner v-if="isSubmitting && activeSource === 'sample'" data-icon="inline-start" />
            <DatabaseIcon v-else data-icon="inline-start" />
            {{ isSubmitting && activeSource === 'sample' ? 'Analyzing sample…' : 'Analyze sample data' }}
          </Button>
        </CardFooter>
      </Card>

    </div>
  </main>
</template>

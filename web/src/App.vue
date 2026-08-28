<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  CircleAlertIcon,
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
import PerformanceDashboard from '@/components/dashboard/PerformanceDashboard.vue'
import { cn } from '@/lib/utils'
import type { AnalyzeResponse, ErrorPayload } from '@/types/analysis'

const MAX_FILE_SIZE = 10 * 1024 * 1024
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

const fileInput = ref<HTMLInputElement | null>(null)
const selectedFile = ref<File | null>(null)
const fileError = ref('')
const requestError = ref('')
const analysis = ref<AnalyzeResponse | null>(null)
const isDragging = ref(false)
const isSubmitting = ref(false)
const showDashboard = ref(false)

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

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const payload = await response.json() as ErrorPayload
    return payload.error?.message ?? 'The file could not be analyzed.'
  }
  catch {
    return 'The file could not be analyzed.'
  }
}

async function submitAnalysis(): Promise<void> {
  if (!selectedFile.value) {
    fileError.value = 'Select a CSV or XLSX file before submitting.'
    return
  }

  isSubmitting.value = true
  requestError.value = ''
  analysis.value = null

  const formData = new FormData()
  formData.append('file', selectedFile.value)

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/analyze`, {
      method: 'POST',
      body: formData,
    })

    if (!response.ok)
      throw new Error(await readErrorMessage(response))

    analysis.value = await response.json() as AnalyzeResponse
    showDashboard.value = true
  }
  catch (error) {
    requestError.value = error instanceof TypeError
      ? 'The API could not be reached. Confirm the FastAPI server is running on port 8000.'
      : error instanceof Error ? error.message : 'The file could not be analyzed.'
  }
  finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <PerformanceDashboard v-if="showDashboard" :analysis="analysis" @back="showDashboard = false" />
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
            Upload one CSV or Excel workbook. The service maps the data, validates its evidence,
            and calculates every KPI deterministically.
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

          <CardFooter class="flex-col gap-3 sm:flex-row sm:justify-between">
            <p class="text-center text-xs text-muted-foreground sm:text-left">
              KPI calculations run in Python—not in the browser or AI model.
            </p>
            <Button class="w-full sm:w-auto" type="submit" size="lg" :disabled="isSubmitting || !selectedFile">
              <Spinner v-if="isSubmitting" data-icon="inline-start" />
              <UploadCloudIcon v-else data-icon="inline-start" />
              {{ isSubmitting ? 'Analyzing file…' : 'Submit for analysis' }}
            </Button>
          </CardFooter>
        </form>
      </Card>

      <div class="flex flex-col items-center gap-2 text-center">
        <p class="text-sm text-muted-foreground">Want to review the Day 4 dashboard before connecting backend fields?</p>
        <Button variant="outline" @click="showDashboard = true">View dashboard preview</Button>
      </div>
    </div>
  </main>
</template>

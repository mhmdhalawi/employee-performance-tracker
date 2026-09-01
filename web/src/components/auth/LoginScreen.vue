<script setup lang="ts">
import { ref } from 'vue'
import { CircleAlertIcon, LockKeyholeIcon, LogInIcon } from '@lucide/vue'
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
import { Field, FieldError, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'

const emit = defineEmits<{
  authenticated: []
}>()

const AUTH_EMAIL = import.meta.env.VITE_AUTH_EMAIL
const AUTH_PASSWORD = import.meta.env.VITE_AUTH_PASSWORD

const email = ref('')
const password = ref('')
const loginError = ref('')

function clearLoginError(): void {
  loginError.value = ''
}

function submitLogin(): void {
  if (email.value.trim() !== AUTH_EMAIL || password.value !== AUTH_PASSWORD) {
    loginError.value = 'The email or password is incorrect.'
    return
  }

  loginError.value = ''
  emit('authenticated')
}
</script>

<template>
  <main class="flex min-h-svh items-center bg-muted/30 px-4 py-8 sm:px-6">
    <div class="mx-auto flex w-full max-w-md flex-col gap-6">
      <header class="flex flex-col items-center gap-3 text-center">
        <div class="flex size-11 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
          <LockKeyholeIcon class="size-5" aria-hidden="true" />
        </div>
        <div class="flex flex-col gap-1">
          <p class="text-sm font-medium text-muted-foreground">
            Employee performance
          </p>
          <h1 class="text-2xl font-semibold tracking-tight sm:text-3xl">
            Welcome back
          </h1>
        </div>
      </header>

      <Card class="shadow-lg shadow-foreground/5">
        <CardHeader>
          <CardTitle>Sign in</CardTitle>
          <CardDescription>
            Enter your Cedar Digital Solutions credentials to continue.
          </CardDescription>
        </CardHeader>

        <form @submit.prevent="submitLogin">
          <CardContent>
            <FieldGroup>
              <Field :data-invalid="Boolean(loginError)">
                <FieldLabel for="login-email">
                  Email
                </FieldLabel>
                <Input
                  id="login-email"
                  v-model="email"
                  type="email"
                  autocomplete="username"
                  placeholder="name@company.com"
                  required
                  :aria-invalid="Boolean(loginError)"
                  aria-describedby="login-error"
                  autofocus
                  @input="clearLoginError"
                />
              </Field>

              <Field :data-invalid="Boolean(loginError)">
                <FieldLabel for="login-password">
                  Password
                </FieldLabel>
                <Input
                  id="login-password"
                  v-model="password"
                  type="password"
                  autocomplete="current-password"
                  placeholder="Enter your password"
                  required
                  :aria-invalid="Boolean(loginError)"
                  aria-describedby="login-error"
                  @input="clearLoginError"
                />
                <FieldError id="login-error" :errors="loginError ? [loginError] : []" />
              </Field>

              <Alert v-if="loginError" variant="destructive">
                <CircleAlertIcon aria-hidden="true" />
                <AlertTitle>Unable to sign in</AlertTitle>
                <AlertDescription>{{ loginError }}</AlertDescription>
              </Alert>
            </FieldGroup>
          </CardContent>

          <CardFooter>
            <Button class="w-full" type="submit" size="lg">
              <LogInIcon data-icon="inline-start" />
              Sign in
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  </main>
</template>

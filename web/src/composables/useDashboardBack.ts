import { useRouter } from 'vue-router'

export function useDashboardBack(): () => void {
  const router = useRouter()

  return () => {
    const previousPath = window.history.state?.back
    if (
      typeof previousPath === 'string'
      && (previousPath === '/' || previousPath.startsWith('/?') || previousPath.startsWith('/dashboard'))
    ) {
      router.back()
      return
    }

    void router.replace({ name: 'dashboard' })
  }
}

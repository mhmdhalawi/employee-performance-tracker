import { useRouter } from 'vue-router'

export function useDashboardBack(): () => void {
  const router = useRouter()

  return () => {
    void router.replace({ name: 'dashboard' })
  }
}

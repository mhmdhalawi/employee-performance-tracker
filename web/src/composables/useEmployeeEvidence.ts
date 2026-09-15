import { onScopeDispose, reactive, watch } from 'vue'
import type { AnalysisFilters, ErrorPayload } from '@/types/analysis'
import type { EmployeeEvidenceResponse, EvidenceKpi, EvidencePageSize } from '@/types/employee-evidence'

interface EvidenceState {
  data: EmployeeEvidenceResponse | null
  loading: boolean
  error: string
  requestedPage: number
  requestedReviewOnly: boolean
  requestedPageSize: EvidencePageSize
  committedPageSize: EvidencePageSize
}
export function useEmployeeEvidence(
  scope: () => { employeeId: string, period: AnalysisFilters, latestSubmissionAt: string },
  refresh: () => void,
) {
  const states = reactive<Record<EvidenceKpi, EvidenceState>>({
    productivity: { data: null, loading: false, error: '', requestedPage: 1, requestedReviewOnly: false, requestedPageSize: 5, committedPageSize: 5 },
    compliance: { data: null, loading: false, error: '', requestedPage: 1, requestedReviewOnly: false, requestedPageSize: 5, committedPageSize: 5 },
    quality: { data: null, loading: false, error: '', requestedPage: 1, requestedReviewOnly: false, requestedPageSize: 5, committedPageSize: 5 },
  })
  const controllers: Partial<Record<EvidenceKpi, AbortController>> = {}
  const sequences: Record<EvidenceKpi, number> = { productivity: 0, compliance: 0, quality: 0 }
  const pageCaches: Record<EvidenceKpi, Map<string, { data: EmployeeEvidenceResponse, expiresAt: number }>> = {
    productivity: new Map(), compliance: new Map(), quality: new Map(),
  }
  let refreshRequested = false
  let disposed = false

  async function load(kpi: EvidenceKpi, page = states[kpi].requestedPage, reviewOnly = states[kpi].requestedReviewOnly, pageSize = states[kpi].requestedPageSize): Promise<void> {
    const state = states[kpi]
    const retrying = !!state.error
    const sequence = ++sequences[kpi]
    controllers[kpi]?.abort()
    const controller = new AbortController()
    controllers[kpi] = controller
    state.error = ''
    state.requestedPage = page
    state.requestedReviewOnly = reviewOnly
    state.requestedPageSize = pageSize
    const current = scope()
    const cache = pageCaches[kpi]
    const cacheKey = JSON.stringify([current.employeeId, current.period.start_date, current.period.end_date, current.latestSubmissionAt, reviewOnly, page, pageSize])
    const cached = cache.get(cacheKey)
    if (!retrying && !refreshRequested && cached && cached.expiresAt > Date.now()) {
      state.data = cached.data
      state.committedPageSize = pageSize
      state.loading = false
      return
    }
    state.loading = true
    const query = new URLSearchParams({ kpi, page: String(pageSize === 'all' ? 1 : page), page_size: String(pageSize === 'all' ? 50 : pageSize), review_only: String(reviewOnly) })
    if (current.period.start_date) query.set('start_date', current.period.start_date)
    if (current.period.end_date) query.set('end_date', current.period.end_date)
    try {
      const base = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'
      async function fetchPage(): Promise<EmployeeEvidenceResponse> {
        const response = await fetch(`${base}/api/v1/employees/${encodeURIComponent(current.employeeId)}/evidence?${query}`, { signal: controller.signal })
        if (!response.ok) {
          const payload = await response.json() as ErrorPayload
          throw new Error(payload.error?.message ?? 'Evidence could not be loaded.')
        }
        return await response.json() as EmployeeEvidenceResponse
      }
      const payload = await fetchPage()
      if (sequence !== sequences[kpi] || disposed) return
      if (new Date(payload.latest_submission_at).getTime() !== new Date(current.latestSubmissionAt).getTime()) {
        Object.values(pageCaches).forEach(pageCache => pageCache.clear())
        state.data = null
        state.error = 'Employee data has changed. Refreshing the results and evidence.'
        if (!refreshRequested) { refreshRequested = true; refresh() }
        return
      }
      if (pageSize === 'all') {
        const rows = [...payload.rows]
        for (let nextPage = 2; rows.length < payload.total_count; nextPage++) {
          query.set('page', String(nextPage))
          const next = await fetchPage()
          if (sequence !== sequences[kpi] || disposed) return
          if (next.latest_submission_at !== payload.latest_submission_at || next.total_count !== payload.total_count) {
            Object.values(pageCaches).forEach(pageCache => pageCache.clear())
            state.data = null
            state.error = 'Employee data has changed. Refreshing the results and evidence.'
            if (!refreshRequested) { refreshRequested = true; refresh() }
            return
          }
          rows.push(...next.rows)
        }
        payload.rows = rows
        payload.page_size = Math.max(1, payload.total_count)
      }
      state.data = payload
      state.committedPageSize = pageSize
      cache.delete(cacheKey)
      cache.set(cacheKey, { data: payload, expiresAt: Date.now() + 30_000 })
      if (cache.size > 8) cache.delete(cache.keys().next().value!)
    }
    catch (error) {
      if (sequence !== sequences[kpi] || disposed || controller.signal.aborted) return
      state.error = error instanceof TypeError ? 'Evidence is temporarily unavailable. Retry to load it.'
        : error instanceof Error ? error.message : 'Evidence could not be loaded.'
    }
    finally { if (sequence === sequences[kpi] && !disposed) state.loading = false }
  }
  // A successful dashboard refresh replaces its filters even if the dates/timestamp match.
  watch(() => [scope().employeeId, scope().period, scope().latestSubmissionAt], () => {
    refreshRequested = false
    for (const kpi of Object.keys(states) as EvidenceKpi[]) {
      pageCaches[kpi].clear()
      states[kpi].data = null
      states[kpi].committedPageSize = 5
      void load(kpi, 1, false, 5)
    }
  }, { immediate: true })
  onScopeDispose(() => {
    disposed = true
    Object.values(controllers).forEach(controller => controller.abort())
    Object.values(pageCaches).forEach(cache => cache.clear())
  })
  return { states, load }
}

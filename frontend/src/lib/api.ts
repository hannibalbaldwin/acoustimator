import type {
  EstimateResponse,
  UpdateScopeRequest,
  PaginatedResponse,
  ProjectResponse,
} from './types'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? '/api'

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`API error ${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

export async function createEstimate(formData: FormData): Promise<EstimateResponse> {
  const res = await fetch(`${API_BASE}/estimates`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`API error ${res.status}: ${text}`)
  }
  return res.json() as Promise<EstimateResponse>
}

export async function getEstimate(id: string): Promise<EstimateResponse> {
  return apiFetch<EstimateResponse>(`/estimates/${id}`)
}

export async function updateScope(
  estimateId: string,
  scopeId: string,
  data: UpdateScopeRequest
): Promise<EstimateResponse> {
  return apiFetch<EstimateResponse>(`/estimates/${estimateId}/scopes/${scopeId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function getProjects(params?: {
  scope_type?: string
  gc_name?: string
  limit?: number
  offset?: number
}): Promise<PaginatedResponse<ProjectResponse>> {
  const qs = new URLSearchParams()
  if (params?.scope_type) qs.set('scope_type', params.scope_type)
  if (params?.gc_name) qs.set('gc_name', params.gc_name)
  if (params?.limit != null) qs.set('limit', String(params.limit))
  if (params?.offset != null) qs.set('offset', String(params.offset))
  const query = qs.toString() ? `?${qs.toString()}` : ''
  return apiFetch<PaginatedResponse<ProjectResponse>>(`/projects${query}`)
}

export async function getProject(id: string): Promise<ProjectResponse> {
  return apiFetch<ProjectResponse>(`/projects/${id}`)
}

export async function exportEstimate(id: string): Promise<Blob> {
  const res = await fetch(`${API_BASE}/estimates/${id}/export`)
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`API error ${res.status}: ${text}`)
  }
  return res.blob()
}

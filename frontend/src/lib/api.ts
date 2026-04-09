import type {
  EstimateResponse,
  ScopeResponse,
  UpdateScopeRequest,
  PaginatedResponse,
  ProjectResponse,
  TrendDataPoint,
  ComparableProject,
  ConfidenceLevel,
  VendorPriceSummary,
  CatalogProduct,
} from './types'

// ── API wire types ────────────────────────────────────────────────────────────

interface ApiScopeResponse {
  id: string
  scope_type: string
  product_name: string | null
  square_footage: number | null
  material_cost: number | null
  markup_pct: number | null
  man_days: number | null
  total: number | null
  confidence_score: number | null
  manually_adjusted: boolean
  unknown_product?: boolean
}

interface ApiComparableProjectResponse {
  id: string
  folder_name: string
  scope_type: string
  area_sf: number
  cost_per_sf: number
  total_cost: number
  year: number | null
  similarity_score: number
}

interface ApiEstimateResponse {
  id: string
  project_name: string
  gc_name: string | null
  address: string | null
  status: string
  total_cost: number | null
  total_sf: number | null
  cost_per_sf: number | null
  man_days: number | null
  confidence_score: number | null
  confidence_level: string | null
  scopes: ApiScopeResponse[]
  created_at: string
  comparable_projects: ApiComparableProjectResponse[]
  // Phase 7.1
  actual_total_cost?: number | null
  actual_cost_date?: string | null
  accuracy_note?: string | null
  variance_pct?: number | null
  // Phase 7.4
  unknown_products?: string[]
}

export interface EstimateListItem {
  id: string
  project_name: string
  gc_name: string | null
  status: string
  total_cost: number | null
  confidence_level: string | null
  created_at: string
  scope_types: string[]
}

// ── Mapping helpers ───────────────────────────────────────────────────────────

function deriveConfidenceLevel(score: number | null): ConfidenceLevel {
  if (score == null) return 'low'
  if (score >= 0.8) return 'high'
  if (score >= 0.5) return 'medium'
  return 'low'
}

function mapScope(raw: ApiScopeResponse): ScopeResponse {
  const material_cost_per_sf =
    raw.material_cost != null && raw.square_footage != null && raw.square_footage > 0
      ? raw.material_cost / raw.square_footage
      : null

  return {
    id: raw.id,
    scope_type: raw.scope_type as ScopeResponse['scope_type'],
    product_name: raw.product_name,
    area_sf: raw.square_footage,
    material_cost_per_sf,
    markup_pct: raw.markup_pct,
    labor_days: raw.man_days,
    total_cost: raw.total,
    confidence_score: raw.confidence_score,
    confidence_level: deriveConfidenceLevel(raw.confidence_score),
    is_ai_suggested: false,
    is_accepted: raw.manually_adjusted,
    unknown_product: raw.unknown_product ?? false,
  }
}

function mapEstimate(raw: ApiEstimateResponse): EstimateResponse {
  const comparable_projects: ComparableProject[] = raw.comparable_projects.map((c) => ({
    id: c.id,
    folder_name: c.folder_name,
    scope_type: c.scope_type as ComparableProject['scope_type'],
    area_sf: c.area_sf,
    cost_per_sf: c.cost_per_sf,
    total_cost: c.total_cost,
    year: c.year,
    similarity_score: c.similarity_score,
  }))

  return {
    id: raw.id,
    project_name: raw.project_name,
    gc_name: raw.gc_name,
    address: raw.address,
    status: raw.status as EstimateResponse['status'],
    total_cost: raw.total_cost,
    total_sf: raw.total_sf,
    cost_per_sf: raw.cost_per_sf,
    man_days: raw.man_days,
    confidence_score: raw.confidence_score,
    confidence_level: raw.confidence_level
      ? (raw.confidence_level as ConfidenceLevel)
      : deriveConfidenceLevel(raw.confidence_score),
    scopes: raw.scopes.map(mapScope),
    created_at: raw.created_at,
    comparable_projects,
    actual_total_cost: raw.actual_total_cost ?? null,
    actual_cost_date: raw.actual_cost_date ?? null,
    accuracy_note: raw.accuracy_note ?? null,
    variance_pct: raw.variance_pct ?? null,
    unknown_products: raw.unknown_products ?? [],
  }
}

// ── Base fetch ────────────────────────────────────────────────────────────────

const BASE = process.env.NEXT_PUBLIC_API_URL ?? ''
const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? ''

function apiHeaders(extra?: HeadersInit): HeadersInit {
  const headers: Record<string, string> = {}
  if (API_KEY) headers['X-API-Key'] = API_KEY
  if (extra) Object.assign(headers, extra)
  return headers
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: apiHeaders(init?.headers),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`API ${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

// ── Exported API functions ────────────────────────────────────────────────────

export async function createEstimate(formData: FormData): Promise<EstimateResponse> {
  const res = await fetch(`${BASE}/api/estimates`, {
    method: 'POST',
    headers: apiHeaders(),
    body: formData,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`API ${res.status}: ${text}`)
  }
  const raw: ApiEstimateResponse = await res.json()
  return mapEstimate(raw)
}

export async function listEstimates(params?: {
  status?: string
  limit?: number
  offset?: number
}): Promise<PaginatedResponse<EstimateListItem>> {
  const qs = new URLSearchParams()
  if (params?.status) qs.set('status', params.status)
  if (params?.limit != null) qs.set('limit', String(params.limit))
  if (params?.offset != null) qs.set('offset', String(params.offset))
  const query = qs.toString() ? `?${qs.toString()}` : ''
  return apiFetch<PaginatedResponse<EstimateListItem>>(`/api/estimates${query}`)
}

export async function getEstimate(id: string): Promise<EstimateResponse> {
  const raw = await apiFetch<ApiEstimateResponse>(`/api/estimates/${id}`)
  return mapEstimate(raw)
}

export async function updateScope(
  estimateId: string,
  scopeId: string,
  body: UpdateScopeRequest
): Promise<EstimateResponse> {
  const raw = await apiFetch<ApiEstimateResponse>(`/api/estimates/${estimateId}/scopes/${scopeId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return mapEstimate(raw)
}

export async function exportEstimate(id: string): Promise<void> {
  const res = await fetch(`${BASE}/api/estimates/${id}/export`, {
    headers: apiHeaders(),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`API ${res.status}: ${text}`)
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  const disposition = res.headers.get('Content-Disposition') ?? ''
  const match = disposition.match(/filename="?([^"]+)"?/)
  a.download = match ? match[1] : `estimate-${id}.xlsx`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export async function getProject(id: string): Promise<ProjectResponse> {
  return apiFetch<ProjectResponse>(`/api/projects/${id}`)
}

export async function getProjectGcNames(): Promise<string[]> {
  return apiFetch<string[]>('/api/projects/gc-names')
}

export async function listProjects(params?: {
  scope_type?: string
  gc_name?: string
  year?: string
  limit?: number
  offset?: number
}): Promise<PaginatedResponse<ProjectResponse>> {
  const qs = new URLSearchParams()
  if (params?.scope_type) qs.set('scope_type', params.scope_type)
  if (params?.gc_name) qs.set('gc_name', params.gc_name)
  if (params?.year) {
    qs.set('year_from', params.year)
    qs.set('year_to', params.year)
  }
  if (params?.limit != null) qs.set('limit', String(params.limit))
  if (params?.offset != null) qs.set('offset', String(params.offset))
  const query = qs.toString() ? `?${qs.toString()}` : ''
  const raw = await apiFetch<PaginatedResponse<ProjectResponse>>(`/api/projects${query}`)
  // Ensure scope_types is always an array (guard against old API responses)
  raw.items = raw.items.map((p) => ({
    ...p,
    scope_types: p.scope_types ?? [],
    scopes: (p.scopes ?? []).map((s) => ({
      ...s,
      area_sf: (s as unknown as { area_sf?: number | null; square_footage?: number | null }).area_sf
        ?? (s as unknown as { square_footage?: number | null }).square_footage
        ?? null,
    })),
  }))
  return raw
}

export async function getCostTrends(granularity: 'year' | 'quarter' | 'month' = 'year'): Promise<TrendDataPoint[]> {
  return apiFetch<TrendDataPoint[]>(`/api/stats/cost-trends?granularity=${granularity}`)
}

export interface DashboardStats {
  total_projects: number
  active_estimates: number
  avg_act_cost_per_sf: number | null
  total_historical_sf: number | null
}

export async function getDashboardStats(): Promise<DashboardStats> {
  return apiFetch<DashboardStats>('/api/stats/summary')
}

export async function deleteEstimate(id: string): Promise<void> {
  const res = await fetch(`${BASE}/api/estimates/${id}`, {
    method: 'DELETE',
    headers: apiHeaders(),
  })
  if (!res.ok && res.status !== 204) {
    const text = await res.text().catch(() => '')
    throw new Error(`API ${res.status}: ${text}`)
  }
}

export async function deleteScope(estimateId: string, scopeId: string): Promise<void> {
  try {
    await apiFetch<void>(`/api/estimates/${estimateId}/scopes/${scopeId}`, {
      method: 'DELETE',
    })
  } catch {
    // Ignore errors (endpoint may not exist yet or scope may already be gone)
  }
}

export async function recordActual(
  estimateId: string,
  data: { actual_total_cost: number; actual_cost_date: string; accuracy_note?: string }
): Promise<EstimateResponse> {
  const raw = await apiFetch<ApiEstimateResponse>(`/api/estimates/${estimateId}/actual`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  return mapEstimate(raw)
}

export interface AccuracyStats {
  total_with_actuals: number
  mean_absolute_pct_error: number | null
  mean_bias_pct: number | null
  by_scope_type: Record<string, { mape: number; n: number }>
}

export async function getAccuracyStats(): Promise<AccuracyStats> {
  return apiFetch<AccuracyStats>('/api/stats/accuracy')
}

export async function getVendorPriceSummary(): Promise<VendorPriceSummary[]> {
  return apiFetch<VendorPriceSummary[]>('/api/vendors/price-summary')
}

export interface ModelStatusEntry {
  scope_type: string
  mape: number | null
  n_train: number | null
  algorithm: string | null
  model_family: string | null
}

export interface ModelStatus {
  last_retrain: string | null
  models: ModelStatusEntry[]
  needs_retrain: boolean
  retrain_reason: string
}

export async function getModelStatus(): Promise<ModelStatus> {
  return apiFetch<ModelStatus>('/api/stats/model-status')
}

export async function getProducts(): Promise<CatalogProduct[]> {
  return apiFetch<CatalogProduct[]>('/api/products')
}

export interface AddProductRequest {
  name: string
  canonical_name: string
  category: string
  aliases: string[]
}

export async function addProduct(data: AddProductRequest): Promise<CatalogProduct> {
  return apiFetch<CatalogProduct>('/api/products', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

// ── Admin User Management ─────────────────────────────────────────────────────

export interface AdminUser {
  id: string
  email: string
  name: string | null
  role: string
  created_at: string
}

export async function listAdminUsers(): Promise<AdminUser[]> {
  return apiFetch<AdminUser[]>('/api/admin/users')
}

export async function createAdminUser(data: {
  email: string
  name?: string
  password: string
  role: string
}): Promise<AdminUser> {
  return apiFetch<AdminUser>('/api/admin/users', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function updateAdminUser(
  userId: string,
  data: { name?: string; role?: string; password?: string }
): Promise<AdminUser> {
  return apiFetch<AdminUser>(`/api/admin/users/${userId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function deleteAdminUser(userId: string): Promise<void> {
  return apiFetch<void>(`/api/admin/users/${userId}`, { method: 'DELETE' })
}

export async function updateEstimateStatus(id: string, status: string): Promise<EstimateResponse> {
  const res = await apiFetch<ApiEstimateResponse>(`/api/estimates/${id}`, {
    method: 'PATCH',
    headers: apiHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ status }),
  })
  return mapEstimate(res)
}

export async function generateQuote(
  estimateId: string,
  template: 'T-004A' | 'T-004B' | 'T-004E' = 'T-004B'
): Promise<void> {
  const res = await fetch(`${BASE}/api/estimates/${estimateId}/quote`, {
    method: 'POST',
    headers: apiHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ template }),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`Quote generation failed: ${text}`)
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  const disposition = res.headers.get('Content-Disposition') ?? ''
  const match = disposition.match(/filename="?([^"]+)"?/)
  a.download = match ? match[1] : `quote-${estimateId}.pdf`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

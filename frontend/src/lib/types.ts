export type ScopeType = 'ACT' | 'AWP' | 'AP' | 'Baffles' | 'FW' | 'SM' | 'WW' | 'RPG' | 'Other'
export type EstimateStatus = 'draft' | 'reviewed' | 'finalized' | 'exported'
export type ConfidenceLevel = 'high' | 'medium' | 'low'

export interface ScopeResponse {
  id: string
  scope_type: ScopeType
  product_name: string | null
  area_sf: number | null
  material_cost_per_sf: number | null
  markup_pct: number | null
  labor_days: number | null
  total_cost: number | null
  confidence_score: number | null
  confidence_level: ConfidenceLevel
  is_ai_suggested: boolean
  is_accepted: boolean
  unknown_product?: boolean
}

export interface CatalogProduct {
  name: string
  canonical_name: string
  category: string
  alias_count: number
}

export interface ComparableProject {
  id: string
  folder_name: string
  scope_type: ScopeType
  area_sf: number
  cost_per_sf: number
  total_cost: number
  year: number | null
  similarity_score: number
}

export interface EstimateResponse {
  id: string
  project_name: string
  gc_name: string | null
  address: string | null
  status: EstimateStatus
  total_cost: number | null
  total_sf: number | null
  cost_per_sf: number | null
  man_days: number | null
  confidence_score: number | null
  confidence_level: ConfidenceLevel
  scopes: ScopeResponse[]
  created_at: string
  comparable_projects: ComparableProject[]
  // Phase 7.1: actual cost tracking
  actual_total_cost?: number | null
  actual_cost_date?: string | null
  accuracy_note?: string | null
  variance_pct?: number | null
  // Phase 7.4: unknown product flagging
  unknown_products?: string[]
}

export interface ProjectScopeSummary {
  id: string
  scope_type: string | null
  product_name: string | null
  area_sf: number | null
  cost_per_sf: number | null
  total: number | null
}

export interface ProjectResponse {
  id: string
  name: string
  gc_name: string | null
  address: string | null
  status: string | null
  project_type?: string | null
  quote_date: string | null
  created_at: string
  scopes: ProjectScopeSummary[]
  scope_types: string[]
  total_cost: number | null
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface UpdateScopeRequest {
  product_name?: string
  area_sf?: number
  material_cost_per_sf?: number
  markup_pct?: number
  labor_days?: number
  is_accepted?: boolean
}

export interface TrendDataPoint {
  date: string
  ACT?: number | null
  AWP?: number | null
  FW?: number | null
  SM?: number | null
  _count?: number
}

export interface VendorPriceSummary {
  vendor_name: string
  canonical_name: string
  quote_count: number
  avg_total: number | null
  recent_avg: number | null
  baseline_avg: number | null
  pct_change: number | null
  alert: boolean
  alert_message: string | null
}

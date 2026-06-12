import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import type {
  User,
  Incident,
  RiskScore,
  RouteResult,
  RouteOption,
  SOSEvent,
  CommunityPost,
  Comment,
  DashboardStats,
  CrimeTrend,
  DistrictAnalytics,
  HeatmapPoint,
  HeatmapResponse,
  ReverseGeocodeResult,
  MapBounds,
  ApiResponse,
  EmergencyContact,
  SystemHealth,
  ServiceHealth,
  PipelineAgent,
  PipelineRunResult,
} from '@/types'

const RAW = import.meta.env.VITE_API_URL || ''
const API_URL = RAW.endsWith('/api/v1') ? RAW : RAW ? `${RAW}/api/v1` : '/api/v1'
const BASE_URL = API_URL.replace(/\/api\/v1$/, '')

let isRefreshing = false
let failedQueue: Array<{
  resolve: (value: unknown) => void
  reject: (reason: unknown) => void
}> = []

function processQueue(error: unknown, token: string | null = null) {
  failedQueue.forEach((p) => {
    if (error) {
      p.reject(error)
    } else {
      p.resolve(token)
    }
  })
  failedQueue = []
}

const api = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
})

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('avana_token')
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then((token) => {
          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${token}`
          }
          return api(originalRequest)
        })
      }
      originalRequest._retry = true
      isRefreshing = true
      const refreshToken = localStorage.getItem('avana_refresh_token')
      if (refreshToken) {
        try {
          const { data: raw } = await api.post('/auth/refresh', { refresh_token: refreshToken })
          const inner = (raw.data || raw) as Record<string, unknown>
          const newToken = String(inner.token || '')
          const newRefresh = String(inner.refresh_token || '')
          localStorage.setItem('avana_token', newToken)
          if (newRefresh) localStorage.setItem('avana_refresh_token', newRefresh)
          processQueue(null, newToken)
          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${newToken}`
          }
          return api(originalRequest)
        } catch (refreshError) {
          processQueue(refreshError, null)
          localStorage.removeItem('avana_token')
          localStorage.removeItem('avana_refresh_token')
          localStorage.removeItem('avana_user')
          window.location.href = '/login'
          return Promise.reject(refreshError)
        } finally {
          isRefreshing = false
        }
      }
      localStorage.removeItem('avana_token')
      localStorage.removeItem('avana_refresh_token')
      localStorage.removeItem('avana_user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

function handleError(error: unknown): never {
  if (error instanceof AxiosError) {
    const body = error.response?.data
    let detail: unknown
    if (body && typeof body === 'object') {
      detail = (body as Record<string, unknown>).detail || (body as Record<string, unknown>).message || error.message
    } else {
      detail = error.message
    }
    if (typeof detail === 'object') {
      throw new Error(JSON.stringify(detail))
    }
    throw new Error(String(detail))
  }
  throw error
}

function mapUser(u: Record<string, unknown>): User {
  return {
    id: String(u.id || ''),
    email: String(u.email || ''),
    name: String(u.name || ''),
    phone: u.phone ? String(u.phone) : undefined,
    avatar: u.avatar_url ? String(u.avatar_url) : undefined,
    role: (String(u.role || 'user') as User['role']),
    emergencyContacts: [],
    isVerified: Boolean(u.is_verified),
    createdAt: u.created_at ? String(u.created_at) : new Date().toISOString(),
    updatedAt: u.updated_at ? String(u.updated_at) : new Date().toISOString(),
  }
}

function mapEmergencyContact(c: Record<string, unknown>): EmergencyContact {
  return {
    id: String(c.id || ''),
    name: String(c.name || ''),
    phone: String(c.phone || ''),
    relationship: String(c.relationship || ''),
    isPrimary: Boolean(c.is_primary),
    notifyOnSOS: Boolean(c.is_primary),
  }
}

// Backend source values: news, user_report (not user_reported)
function mapIncident(i: Record<string, unknown>): Incident {
  const rawSource = String(i.source || 'user_report')
  return {
    id: String(i.id || ''),
    type: (String(i.incident_type || 'other') as Incident['type']),
    severity: (String(i.severity || 'medium') as Incident['severity']),
    source: (rawSource as Incident['source']),
    status: (String(i.status || 'pending') as Incident['status']),
    title: String(i.title || ''),
    description: String(i.description || ''),
    location: {
      lat: Number(i.latitude || 0),
      lng: Number(i.longitude || 0),
      address: i.address ? String(i.address) : undefined,
    },
    district: i.district ? String(i.district) : undefined,
    city: i.city ? String(i.city) : undefined,
    confidenceScore: i.confidence_score != null ? Number(i.confidence_score) : undefined,
    reportedBy: String(i.user_id || ''),
    reportedAt: i.created_at ? String(i.created_at) : new Date().toISOString(),
    updatedAt: i.updated_at ? String(i.updated_at) : new Date().toISOString(),
    isVerified: Boolean(i.is_verified),
    upvotes: 0,
    downvotes: 0,
  }
}

function mapCategory(cat: string): RiskScore['category'] {
  const m: Record<string, RiskScore['category']> = {
    'Safe': 'safe', 'Low': 'low', 'Moderate': 'moderate',
    'High': 'high', 'Critical': 'critical', 'High Risk': 'high',
    'safe': 'safe', 'low': 'low', 'moderate': 'moderate',
    'high': 'high', 'critical': 'critical',
  }
  return m[cat] || 'moderate'
}

function mapBackendRouteOption(opt: Record<string, unknown>): RouteOption {
  return {
    type: String(opt.type || ''),
    geometry: (opt.geometry || []) as [number, number][],
    segments: ((opt.segments || []) as Record<string, unknown>[]).map((s) => ({
      startIndex: 0,
      endIndex: 0,
      safetyScore: Number(s.safety_score || 0),
      riskCategory: String(s.risk_category || ''),
      riskLevel: (s.risk_category === 'High Risk' || s.risk_category === 'Critical' ? 'high' :
                  s.risk_category === 'Moderate' ? 'medium' : 'low') as 'low' | 'medium' | 'high',
      incidents: [],
    })),
    duration: Number(opt.duration_minutes || 0),
    distance: Number(opt.distance_km || 0),
    safetyScore: Number(opt.safety_score || 0),
  }
}

function mapPost(p: Record<string, unknown>): CommunityPost {
  const userData = (p.user || {}) as Record<string, unknown>
  return {
    id: String(p.id || ''),
    userId: String(userData.id || ''),
    userName: String(userData.name || 'Unknown'),
    userAvatar: userData.avatar_url ? String(userData.avatar_url) : undefined,
    title: '',
    content: String(p.content || ''),
    postType: p.post_type ? String(p.post_type) : undefined,
    location: p.latitude ? {
      lat: Number(p.latitude || 0),
      lng: Number(p.longitude || 0),
      address: p.location_name ? String(p.location_name) : undefined,
    } : undefined,
    tags: p.post_type ? [String(p.post_type)] : [],
    upvotes: Number(p.upvotes || 0),
    downvotes: Number(p.downvotes || 0),
    commentCount: Number(p.comment_count || 0),
    isIncident: false,
    isVerified: Boolean(p.is_verified),
    createdAt: p.created_at ? String(p.created_at) : new Date().toISOString(),
    updatedAt: p.updated_at ? String(p.updated_at) : new Date().toISOString(),
  }
}

function mapComment(c: Record<string, unknown>): Comment {
  const userData = (c.user || {}) as Record<string, unknown>
  return {
    id: String(c.id || ''),
    postId: String(c.post_id || ''),
    userId: String(userData.id || ''),
    userName: String(userData.name || 'Unknown'),
    userAvatar: userData.avatar_url ? String(userData.avatar_url) : undefined,
    content: String(c.content || ''),
    upvotes: Number(c.upvotes || 0),
    createdAt: c.created_at ? String(c.created_at) : new Date().toISOString(),
    replies: c.replies
      ? ((c.replies as Record<string, unknown>[]) || []).map(mapComment)
      : undefined,
  }
}

function mapSOS(e: Record<string, unknown>): SOSEvent {
  return {
    id: String(e.id || ''),
    userId: String(e.user_id || ''),
    location: { lat: Number(e.latitude || 0), lng: Number(e.longitude || 0) },
    timestamp: e.created_at ? String(e.created_at) : new Date().toISOString(),
    // Backend values: triggered, acknowledged, resolved, false_alarm
    status: (String(e.status || 'triggered') as SOSEvent['status']),
    notes: e.message ? String(e.message) : undefined,
    notifiedContacts: e.notified_contacts
      ? ((e.notified_contacts as Record<string, unknown>[]) || []).map((c) => ({
          name: String(c.name || ''),
          phone: String(c.phone || ''),
          relationship: String(c.relationship || ''),
        }))
      : undefined,
  }
}

function storeAuth(inner: Record<string, unknown>): { token: string; user: User } {
  const token = String(inner.token || inner.access_token || '')
  const refreshToken = String(inner.refresh_token || '')
  const user = mapUser(inner.user as Record<string, unknown>)
  if (token) localStorage.setItem('avana_token', token)
  if (refreshToken) localStorage.setItem('avana_refresh_token', refreshToken)
  if (user) localStorage.setItem('avana_user', JSON.stringify(user))
  return { token, user }
}

// ── Auth API ─────────────────────────────────────────────────────────────────

export const authApi = {
  login: async (email: string, password: string): Promise<{ token: string; user: User }> => {
    try {
      const { data: raw } = await api.post('/auth/login', { email, password })
      return storeAuth((raw.data || raw) as Record<string, unknown>)
    } catch (error) { handleError(error) }
  },

  signup: async (userData: { email: string; password: string; name: string; phone?: string }): Promise<{ token: string; user: User }> => {
    try {
      const { data: raw } = await api.post('/auth/signup', userData)
      return storeAuth((raw.data || raw) as Record<string, unknown>)
    } catch (error) { handleError(error) }
  },

  refreshToken: async (): Promise<{ token: string; user: User }> => {
    try {
      const refreshToken = localStorage.getItem('avana_refresh_token')
      if (!refreshToken) throw new Error('No refresh token')
      const { data: raw } = await api.post('/auth/refresh', { refresh_token: refreshToken })
      return storeAuth((raw.data || raw) as Record<string, unknown>)
    } catch (error) { handleError(error) }
  },

  logout: async (): Promise<void> => {
    try {
      await api.post('/auth/logout')
    } finally {
      localStorage.removeItem('avana_token')
      localStorage.removeItem('avana_refresh_token')
      localStorage.removeItem('avana_user')
    }
  },

  getProfile: async (): Promise<User> => {
    try {
      const { data: raw } = await api.get('/auth/me')
      return mapUser((raw.data || raw) as Record<string, unknown>)
    } catch (error) { handleError(error) }
  },

  updateProfile: async (updates: Partial<User>): Promise<User> => {
    try {
      const { data: raw } = await api.put('/auth/me', updates)
      return mapUser((raw.data || raw) as Record<string, unknown>)
    } catch (error) { handleError(error) }
  },

  getEmergencyContacts: async (): Promise<EmergencyContact[]> => {
    try {
      const { data: raw } = await api.get('/auth/emergency-contacts')
      const items = (raw.data || raw) as Record<string, unknown>[]
      return (Array.isArray(items) ? items : []).map(mapEmergencyContact)
    } catch (error) { handleError(error) }
  },

  addEmergencyContact: async (contact: {
    name: string
    phone: string
    relationship: string
    is_primary?: boolean
  }): Promise<EmergencyContact> => {
    try {
      const { data: raw } = await api.post('/auth/emergency-contacts', contact)
      return mapEmergencyContact((raw.data || raw) as Record<string, unknown>)
    } catch (error) { handleError(error) }
  },

  deleteEmergencyContact: async (id: string): Promise<void> => {
    try {
      await api.delete(`/auth/emergency-contacts/${id}`)
    } catch (error) { handleError(error) }
  },
}

// ── Incident API ──────────────────────────────────────────────────────────────

export const incidentApi = {
  getIncidents: async (params?: {
    page?: number; limit?: number; type?: string; severity?: string; status?: string
    lat?: number; lng?: number; radius?: number
  }): Promise<ApiResponse<Incident[]>> => {
    try {
      const bp: Record<string, string | number> = {}
      if (params?.page) bp['page'] = params.page
      if (params?.limit) bp['page_size'] = params.limit
      if (params?.radius) bp['radius_km'] = params.radius
      if (params?.lat) bp['lat'] = params.lat
      if (params?.lng) bp['lng'] = params.lng
      if (params?.type) bp['incident_type'] = params.type
      if (params?.severity) bp['severity'] = params.severity
      if (params?.status) bp['status'] = params.status
      const { data: raw } = await api.get('/incidents', { params: bp })
      const inner = (raw.data || raw) as Record<string, unknown>
      const items = (inner.items || []) as Record<string, unknown>[]
      return {
        data: items.map(mapIncident),
        status: 'success',
        pagination: {
          page: Number(inner.page || 1),
          limit: Number(inner.page_size || 20),
          total: Number(inner.total || 0),
          totalPages: Math.ceil(Number(inner.total || 0) / Number(inner.page_size || 20)),
        },
      }
    } catch (error) { handleError(error) }
  },

  getIncident: async (id: string): Promise<Incident> => {
    try {
      const { data: raw } = await api.get(`/incidents/${id}`)
      return mapIncident((raw.data || raw) as Record<string, unknown>)
    } catch (error) { handleError(error) }
  },

  createReport: async (report: Record<string, unknown>): Promise<Record<string, unknown>> => {
    try {
      const params = new URLSearchParams()
      for (const [key, value] of Object.entries(report)) {
        if (value !== undefined && value !== null) params.append(key, String(value))
      }
      const { data } = await api.post('/reports', null, { params })
      return (data.data || data) as Record<string, unknown>
    } catch (error) { handleError(error) }
  },
}

// ── Risk API ──────────────────────────────────────────────────────────────────

export const riskApi = {
  getRiskScore: async (lat: number, lng: number): Promise<RiskScore> => {
    try {
      const { data: raw } = await api.post('/risk/score', { latitude: lat, longitude: lng })
      const inner = (raw.data || raw) as Record<string, unknown>
      const score01 = Number(inner.score || 0) / 100
      return {
        score: score01,
        category: mapCategory(String(inner.category || 'moderate')),
        factors: [],
        location: { lat, lng },
        timestamp: new Date().toISOString(),
        recommendations: (inner.recommendations || []) as string[],
      }
    } catch (error) { handleError(error) }
  },

  // Returns the full heatmap response including generated_at and district_summaries
  getHeatmapBounds: async (bounds: MapBounds, zoom: number): Promise<HeatmapResponse> => {
    try {
      const { data: raw } = await api.post('/risk/heatmap', {
        sw_lat: bounds.south, sw_lng: bounds.west,
        ne_lat: bounds.north, ne_lng: bounds.east,
        zoom,
      })
      const inner = (raw.data || raw) as Record<string, unknown>
      const points = (inner.points || []) as Record<string, unknown>[]
      const summaries = (inner.district_summaries || []) as Record<string, unknown>[]
      return {
        points: points.map((p) => ({
          lat: Number(p.latitude || 0),
          lng: Number(p.longitude || 0),
          weight: Number(p.weight || 0),
          riskCategory: p.risk_category ? String(p.risk_category) : undefined,
        })),
        generatedAt: inner.generated_at ? String(inner.generated_at) : null,
        districtSummaries: summaries.map((s) => ({
          district: String(s.district || ''),
          avgScore: Number(s.avg_score || 0),
          totalIncidents: Number(s.total_incidents || 0),
          trend: (String(s.trend || 'stable') as 'improving' | 'stable' | 'worsening'),
        })),
      }
    } catch (error) { handleError(error) }
  },

  // Legacy points-only accessor for components that don't need metadata
  getHeatmapPoints: async (bounds: MapBounds, zoom: number): Promise<HeatmapPoint[]> => {
    const resp = await riskApi.getHeatmapBounds(bounds, zoom)
    return resp.points
  },
}

// ── Location API ──────────────────────────────────────────────────────────────

export const locationApi = {
  reverseGeocode: async (lat: number, lng: number): Promise<ReverseGeocodeResult> => {
    try {
      const { data: raw } = await api.post('/location/reverse-geocode', { latitude: lat, longitude: lng })
      const inner = (raw.data || raw) as Record<string, unknown>
      return {
        displayName: String(inner.display_name || ''),
        locality: String(inner.locality || ''),
        suburb: String(inner.suburb || ''),
        district: String(inner.district || ''),
        city: String(inner.city || ''),
        state: String(inner.state || ''),
        country: String(inner.country || ''),
        latitude: Number(inner.latitude || lat),
        longitude: Number(inner.longitude || lng),
        cached: Boolean(inner.cached),
        responseTimeMs: Number(inner.response_time_ms || 0),
      }
    } catch (error) { handleError(error) }
  },
}

// ── Route API ─────────────────────────────────────────────────────────────────

export const routeApi = {
  getSafeRoute: async (source: { lat: number; lng: number }, destination: { lat: number; lng: number }): Promise<RouteResult> => {
    try {
      const { data: raw } = await api.post('/route/safe', {
        source_lat: source.lat, source_lng: source.lng,
        dest_lat: destination.lat, dest_lng: destination.lng,
      })
      const inner = (raw.data || raw) as Record<string, unknown>
      return {
        safest: mapBackendRouteOption((inner.safest || {}) as Record<string, unknown>),
        fastest: mapBackendRouteOption((inner.fastest || {}) as Record<string, unknown>),
        balanced: mapBackendRouteOption((inner.balanced || {}) as Record<string, unknown>),
      }
    } catch (error) { handleError(error) }
  },

  getHealth: async (): Promise<{ status: string; service: string; provider: string }> => {
    try {
      const { data: raw } = await api.get('/route/health')
      return (raw.data || raw) as { status: string; service: string; provider: string }
    } catch (error) { handleError(error) }
  },
}

// ── SOS API ───────────────────────────────────────────────────────────────────

export const sosApi = {
  triggerSOS: async (location: { lat: number; lng: number }, message?: string): Promise<SOSEvent> => {
    try {
      const { data } = await api.post('/sos', {
        latitude: location.lat,
        longitude: location.lng,
        message: message || 'SOS triggered',
        emergency_type: 'safety_threat',
      })
      return mapSOS((data.data || data) as Record<string, unknown>)
    } catch (error) { handleError(error) }
  },

  getSOSHistory: async (): Promise<SOSEvent[]> => {
    try {
      const { data } = await api.get('/sos/history')
      const items = (data.data || data) as Record<string, unknown>[]
      return (Array.isArray(items) ? items : []).map(mapSOS)
    } catch (error) { handleError(error) }
  },
}

// ── Community API ─────────────────────────────────────────────────────────────

export const communityApi = {
  getPosts: async (params?: { page?: number; limit?: number; tag?: string }): Promise<ApiResponse<CommunityPost[]>> => {
    try {
      const bp: Record<string, string | number> = {}
      if (params?.page) bp['page'] = params.page
      if (params?.limit) bp['page_size'] = params.limit
      if (params?.tag) bp['post_type'] = params.tag
      const { data } = await api.get('/community/posts', { params: bp })
      const arr = data.data && Array.isArray(data.data) ? data.data : []
      return { data: arr.map(mapPost), status: 'success' }
    } catch (error) { handleError(error) }
  },

  createPost: async (post: Record<string, unknown>): Promise<CommunityPost> => {
    try {
      const { data } = await api.post('/community/posts', post)
      return mapPost((data.data || data) as Record<string, unknown>)
    } catch (error) { handleError(error) }
  },

  getComments: async (postId: string): Promise<Comment[]> => {
    try {
      const { data } = await api.get(`/community/posts/${postId}/comments`)
      const items = (data.data || data) as Record<string, unknown>[]
      return (Array.isArray(items) ? items : []).map(mapComment)
    } catch (error) { handleError(error) }
  },

  createComment: async (postId: string, content: string, parentId?: string): Promise<Comment> => {
    try {
      const { data } = await api.post(`/community/posts/${postId}/comments`, { content, parent_id: parentId || null })
      return mapComment((data.data || data) as Record<string, unknown>)
    } catch (error) { handleError(error) }
  },

  vote: async (postId: string, voteType: 'up' | 'down'): Promise<{ upvotes: number; downvotes: number }> => {
    try {
      const { data } = await api.post(`/community/posts/${postId}/vote`, null, { params: { vote_type: voteType } })
      const inner = (data.data || data) as Record<string, unknown>
      return { upvotes: Number(inner.upvotes || 0), downvotes: Number(inner.downvotes || 0) }
    } catch (error) { handleError(error) }
  },
}

// ── Admin API ─────────────────────────────────────────────────────────────────

export type PipelineName = 'intelligence' | 'community' | 'risk'

export const adminApi = {
  listUsers: async (p?: { page?: number; page_size?: number }): Promise<{ items: User[]; total: number; page: number; page_size: number }> => {
    try {
      const { data: raw } = await api.get('/admin/users', { params: p })
      const inner = (raw.data || raw) as Record<string, unknown>
      return {
        items: ((inner.items || []) as Record<string, unknown>[]).map(mapUser),
        total: Number(inner.total || 0),
        page: Number(inner.page || 1),
        page_size: Number(inner.page_size || 20),
      }
    } catch (error) { handleError(error) }
  },

  getDashboardStats: async (): Promise<DashboardStats> => {
    try {
      const { data: raw } = await api.get('/admin/dashboard')
      const inner = (raw.data || raw) as Record<string, unknown>
      return {
        totalIncidents: Number(inner.total_incidents || 0),
        activeIncidents: Number(inner.verified_reports || 0),
        resolvedIncidents: 0,
        sosTriggers: Number(inner.sos_events || 0),
        activeUsers: Number(inner.active_users || 0),
        riskScore: 0,
        incidentsByType: Object.fromEntries(
          ((inner.incidents_by_type || []) as Record<string, unknown>[]).map((t) => [String(t.incident_type || ''), Number(t.count || 0)])
        ),
        incidentsBySeverity: {},
        recentIncidents: ((inner.recent_alerts || []) as Record<string, unknown>[]).map((a) => ({
          id: String(a.id || ''),
          type: (String(a.type || 'other') as Incident['type']),
          severity: (String(a.severity || 'medium') as Incident['severity']),
          source: 'user_report' as Incident['source'],
          status: (String(a.status || 'pending') as Incident['status']),
          title: '',
          description: '',
          location: { lat: 0, lng: 0 },
          reportedBy: '',
          reportedAt: a.time ? String(a.time) : new Date().toISOString(),
          updatedAt: a.time ? String(a.time) : new Date().toISOString(),
          isVerified: false,
          upvotes: 0,
          downvotes: 0,
        })),
        districtAnalytics: ((inner.incidents_by_district || []) as Record<string, unknown>[]).map((d) => ({
          district: String(d.district || ''),
          total: Number(d.total || 0),
          highRisk: Number(d.high_risk || 0),
          mediumRisk: Number(d.medium_risk || 0),
          lowRisk: Number(d.low_risk || 0),
          critical: Number(d.critical || 0),
        })),
        crimeTrends: ((inner.risk_trend || []) as Record<string, unknown>[]).map((t) => ({
          date: String(t.date || ''),
          count: Number(t.value || 0),
        })),
      }
    } catch (error) { handleError(error) }
  },

  moderateIncident: async (incidentId: string, action: string, notes?: string): Promise<Incident> => {
    try {
      const { data } = await api.put(`/admin/incidents/${incidentId}/moderate`, {
        incident_id: incidentId,
        status: action,
        moderation_notes: notes,
      })
      const d = (data.data || data) as Record<string, unknown>
      return {
        id: String(d.id || incidentId),
        type: 'other' as Incident['type'],
        severity: 'medium' as Incident['severity'],
        source: 'user_report' as Incident['source'],
        status: (String(d.status || action) as Incident['status']),
        title: '', description: '',
        location: { lat: 0, lng: 0 },
        reportedBy: '', reportedAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        isVerified: false, upvotes: 0, downvotes: 0,
      }
    } catch (error) { handleError(error) }
  },

  manageUser: async (userId: string, action: string): Promise<User> => {
    try {
      if (action === 'promote' || action === 'demote') {
        const role = action === 'promote' ? 'admin' : 'user'
        await api.put(`/admin/users/${userId}/role`, null, { params: { role } })
      } else {
        const isActive = action === 'activate'
        await api.put(`/admin/users/${userId}/status`, null, { params: { is_active: isActive } })
      }
      return { id: userId, email: '', name: '', role: 'user', emergencyContacts: [], isVerified: false, createdAt: '', updatedAt: '' }
    } catch (error) { handleError(error) }
  },

  // GET /admin/pipeline/status — real backend endpoint
  getPipelineStatus: async (): Promise<PipelineAgent[]> => {
    try {
      const { data: raw } = await api.get('/admin/pipeline/status')
      const inner = (raw.data || raw) as Record<string, unknown>
      const pipelines = (inner.pipelines || []) as Record<string, unknown>[]
      return pipelines.map((p) => ({
        name: String(p.name || ''),
        status: (String(p.status || 'idle') as PipelineAgent['status']),
        scheduledMinutes: p.schedule_minutes != null ? Number(p.schedule_minutes) : null,
      }))
    } catch (error) { handleError(error) }
  },

  // POST /admin/pipeline/run/{pipeline_name}
  // Valid names: intelligence, community, risk
  runPipeline: async (pipelineName: PipelineName): Promise<PipelineRunResult> => {
    try {
      const { data: raw } = await api.post(`/admin/pipeline/run/${pipelineName}`)
      const outer = (raw.data || raw) as Record<string, unknown>
      const result = (outer.result || {}) as Record<string, unknown>
      const summary = (result.summary || {}) as Record<string, unknown>
      const status = String(outer.status || 'completed')
      const runResult: PipelineRunResult = {
        name: pipelineName,
        status: (status as PipelineRunResult['status']),
        incidentsSaved: Number(summary.incidents_saved || result.incidents_saved || 0),
        errors: (result.errors || summary.errors || []) as string[],
        durationSeconds: Number(summary.duration_seconds || result.duration_seconds || 0),
        articlesProcessed: Number(summary.articles_fetched || result.articles_fetched || 0),
        ranAt: String(summary.completed_at || new Date().toISOString()),
        reason: status === 'skipped' ? String(result.reason || 'gemini_unavailable') : undefined,
      }
      // Persist to localStorage so HomeScreen can show last run info
      if (pipelineName === 'intelligence') {
        localStorage.setItem('avana_last_intel_run', JSON.stringify(runResult))
      }
      return runResult
    } catch (error) { handleError(error) }
  },
}

// ── Chat API ──────────────────────────────────────────────────────────────────

export const chatApi = {
  sendMessage: async (message: string, context?: { lat?: number; lng?: number; incidentId?: string }): Promise<string> => {
    try {
      const body: Record<string, unknown> = { message }
      if (context?.lat && context?.lng) {
        body.location = { latitude: context.lat, longitude: context.lng }
      }
      const { data } = await api.post('/chat/message', body)
      const inner = (data.data || data) as Record<string, unknown>
      return String(inner.response || '')
    } catch (error) { handleError(error) }
  },

  getTestResponse: async (): Promise<{ status: string; response?: string; detail?: string }> => {
    try {
      const { data } = await api.get('/chat/test')
      const inner = (data.data || data) as Record<string, unknown>
      return {
        status: String(inner.status || 'unavailable'),
        response: inner.response ? String(inner.response) : undefined,
        detail: inner.detail ? String(inner.detail) : undefined,
      }
    } catch (error) { handleError(error) }
  },
}

// ── Analytics API ─────────────────────────────────────────────────────────────

export const analyticsApi = {
  getDistrictAnalytics: async (): Promise<DistrictAnalytics[]> => {
    try {
      const { data } = await api.get('/analytics/districts')
      const items = (data.data || data) as Record<string, unknown>[]
      return (Array.isArray(items) ? items : []).map((d) => ({
        district: String(d.district || ''),
        total: Number(d.total_incidents || d.total || 0),
        highRisk: Number(d.high_risk || 0),
        mediumRisk: Number(d.medium_risk || 0),
        lowRisk: Number(d.low_risk || 0),
        critical: Number(d.critical || 0),
      }))
    } catch (error) { handleError(error) }
  },

  getCrimeTrends: async (p?: { days?: number; type?: string }): Promise<CrimeTrend[]> => {
    try {
      const bp: Record<string, string | number> = {}
      if (p?.days) bp['days'] = p.days
      const { data: raw } = await api.get('/analytics/trends', { params: bp })
      const inner = (raw.data || raw) as Record<string, unknown>
      const items = (inner.data || []) as Record<string, unknown>[]
      return (Array.isArray(items) ? items : []).map((t) => ({
        date: String(t.date || ''),
        count: Number(t.total || 0),
        type: t.high_risk && Number(t.high_risk) > 0 ? 'high_risk' : undefined,
      }))
    } catch (error) { handleError(error) }
  },
}

// ── Health API ────────────────────────────────────────────────────────────────

export const healthApi = {
  // GET /health — overall backend health
  getBackendHealth: async (): Promise<ServiceHealth> => {
    const checkedAt = new Date().toISOString()
    const t0 = Date.now()
    try {
      const { data: raw } = await axios.get(`${BASE_URL}/health`, { timeout: 5000 })
      const responseMs = Date.now() - t0
      const inner = (raw.data || raw) as Record<string, unknown>
      const status = String(inner.status || 'healthy')
      return {
        name: 'Backend',
        status: status === 'healthy' ? (responseMs > 2000 ? 'degraded' : 'healthy') : 'degraded',
        responseMs,
        checkedAt,
        detail: `v${String(inner.version || '?')}`,
      }
    } catch {
      return { name: 'Backend', status: 'offline', checkedAt, detail: 'Unreachable' }
    }
  },

  // GET /api/v1/route/health — route engine / OSRM
  getRouteHealth: async (): Promise<ServiceHealth> => {
    const checkedAt = new Date().toISOString()
    const t0 = Date.now()
    try {
      const { data: raw } = await api.get('/route/health', { timeout: 8000 })
      const responseMs = Date.now() - t0
      const inner = (raw.data || raw) as Record<string, unknown>
      const backendStatus = String(inner.status || 'healthy')
      // Use backend-measured response_ms if available, else our round-trip
      const probeMs = inner.response_ms != null ? Number(inner.response_ms) : responseMs
      const status: ServiceHealth['status'] =
        backendStatus === 'healthy' ? (probeMs > 2000 ? 'degraded' : 'healthy')
        : backendStatus === 'offline' ? 'offline'
        : 'degraded'
      return {
        name: 'Route Engine',
        status,
        responseMs: probeMs,
        checkedAt,
        detail: inner.detail ? String(inner.detail) : String(inner.provider || 'OSRM'),
      }
    } catch (err: unknown) {
      const responseMs = Date.now() - t0
      // Axios surfaces 503 as an error — check response body for status
      const errResp = (err as { response?: { data?: Record<string, unknown>; status?: number } }).response
      if (errResp?.status === 503) {
        const body = errResp.data || {}
        return {
          name: 'Route Engine',
          status: 'offline',
          responseMs,
          checkedAt,
          detail: String(body.detail || 'OSRM unreachable'),
        }
      }
      return { name: 'Route Engine', status: 'offline', responseMs, checkedAt, detail: 'OSRM unreachable' }
    }
  },

  // GET /api/v1/chat/test — Gemini AI availability
  getAIHealth: async (): Promise<ServiceHealth> => {
    const checkedAt = new Date().toISOString()
    const t0 = Date.now()
    try {
      const { data: raw } = await api.get('/chat/test', { timeout: 8000 })
      const responseMs = Date.now() - t0
      const inner = (raw.data || raw) as Record<string, unknown>
      const status = String(inner.status || 'unavailable')
      return {
        name: 'Gemini AI',
        status: status === 'ok' ? (responseMs > 3000 ? 'degraded' : 'healthy') : 'degraded',
        responseMs,
        checkedAt,
        detail: status === 'ok' ? 'Operational' : (String(inner.detail || 'Not configured')),
      }
    } catch {
      return { name: 'Gemini AI', status: 'offline', checkedAt, detail: 'Service unavailable' }
    }
  },

  getSystemHealth: async (): Promise<SystemHealth> => {
    const [backend, routeEngine, aiService] = await Promise.allSettled([
      healthApi.getBackendHealth(),
      healthApi.getRouteHealth(),
      healthApi.getAIHealth(),
    ])
    const now = new Date().toISOString()
    const offline: ServiceHealth = { name: 'Unknown', status: 'offline', checkedAt: now }
    return {
      backend: backend.status === 'fulfilled' ? backend.value : { ...offline, name: 'Backend' },
      routeEngine: routeEngine.status === 'fulfilled' ? routeEngine.value : { ...offline, name: 'Route Engine' },
      aiService: aiService.status === 'fulfilled' ? aiService.value : { ...offline, name: 'Gemini AI' },
      lastChecked: now,
    }
  },
}

export default api

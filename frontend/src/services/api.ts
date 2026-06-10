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
  MapBounds,
  ApiResponse,
} from '@/types'

const API_URL = import.meta.env.VITE_API_URL || '/api/v1'

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
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('avana_token')
      localStorage.removeItem('avana_user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

function handleError(error: unknown): never {
  if (error instanceof AxiosError) {
    const body = error.response?.data
    const detail = body && typeof body === 'object'
      ? (body as Record<string, unknown>).detail || (body as Record<string, unknown>).message || error.message
      : error.message
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

function mapIncident(i: Record<string, unknown>): Incident {
  return {
    id: String(i.id || ''),
    type: (String(i.incident_type || 'other') as Incident['type']),
    severity: (String(i.severity || 'medium') as Incident['severity']),
    source: (String(i.source || 'user_reported') as Incident['source']),
    status: (String(i.status || 'reported') as Incident['status']),
    title: String(i.title || ''),
    description: String(i.description || ''),
    location: {
      lat: Number(i.latitude || 0),
      lng: Number(i.longitude || 0),
      address: i.address ? String(i.address) : undefined,
    },
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
    geometry: (opt.geometry || []) as [number, number][],
    segments: ((opt.segments || []) as Record<string, unknown>[]).map((s) => ({
      startIndex: 0,
      endIndex: 0,
      safetyScore: Number(s.safety_score || 0),
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
  }
}

function mapSOS(e: Record<string, unknown>): SOSEvent {
  return {
    id: String(e.id || ''),
    userId: String(e.user_id || ''),
    location: { lat: Number(e.latitude || 0), lng: Number(e.longitude || 0) },
    timestamp: e.created_at ? String(e.created_at) : new Date().toISOString(),
    status: (String(e.status || 'active') as SOSEvent['status']),
    notes: e.message ? String(e.message) : undefined,
  }
}

// Backend has a middleware that wraps all JSON responses in { data: ..., status: 'success' }.
// So we always extract .data first.

export const authApi = {
  login: async (email: string, password: string): Promise<{ token: string; user: User }> => {
    try {
      const { data: raw } = await api.post('/auth/login', { email, password })
      const inner = (raw.data || raw) as Record<string, unknown>
      return { token: String(inner.token || ''), user: mapUser(inner.user as Record<string, unknown>) }
    } catch (error) { handleError(error) }
  },

  signup: async (userData: { email: string; password: string; name: string; phone?: string }): Promise<{ token: string; user: User }> => {
    try {
      const { data: raw } = await api.post('/auth/signup', userData)
      const inner = (raw.data || raw) as Record<string, unknown>
      return { token: String(inner.token || ''), user: mapUser(inner.user as Record<string, unknown>) }
    } catch (error) { handleError(error) }
  },

  logout: async (): Promise<void> => {
    try {
      await api.post('/auth/logout')
    } catch (error) { handleError(error) }
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
}

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

  getHeatmapBounds: async (bounds: MapBounds, zoom: number): Promise<HeatmapPoint[]> => {
    try {
      const { data: raw } = await api.post('/risk/heatmap', {
        sw_lat: bounds.south, sw_lng: bounds.west,
        ne_lat: bounds.north, ne_lng: bounds.east,
        zoom,
      })
      const inner = (raw.data || raw) as Record<string, unknown>
      const points = (inner.points || []) as Record<string, unknown>[]
      return points.map((p) => ({
        lat: Number(p.latitude || 0),
        lng: Number(p.longitude || 0),
        weight: Number(p.weight || 0),
      }))
    } catch (error) { handleError(error) }
  },
}

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
}

export const sosApi = {
  triggerSOS: async (location: { lat: number; lng: number }, contacts?: string[]): Promise<SOSEvent> => {
    try {
      const { data } = await api.post('/sos', { latitude: location.lat, longitude: location.lng })
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

export const communityApi = {
  getPosts: async (params?: { page?: number; limit?: number; tag?: string }): Promise<ApiResponse<CommunityPost[]>> => {
    try {
      const bp: Record<string, string | number> = {}
      if (params?.page) bp['page'] = params.page
      if (params?.limit) bp['page_size'] = params.limit
      if (params?.tag) bp['post_type'] = params.tag
      const { data } = await api.get('/community/posts', { params: bp })
      if (data.data && Array.isArray(data.data)) {
        return { data: data.data.map(mapPost), status: 'success' }
      }
      if (Array.isArray(data.data)) {
        return { data: data.data.map(mapPost), status: 'success' }
      }
      const inner = (data.data || data) as Record<string, unknown>
      const items = (inner.items || data || []) as Record<string, unknown>[]
      return {
        data: (Array.isArray(items) ? items : []).map(mapPost),
        status: 'success',
      }
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

  createComment: async (postId: string, content: string): Promise<Comment> => {
    try {
      const { data } = await api.post(`/community/posts/${postId}/comments`, { content })
      return mapComment((data.data || data) as Record<string, unknown>)
    } catch (error) { handleError(error) }
  },
}

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
          source: 'user_reported' as Incident['source'],
          status: (String(a.status || 'reported') as Incident['status']),
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
      const { data } = await api.put(`/admin/incidents/${incidentId}/moderate`, { status: action, moderation_notes: notes })
      const d = (data.data || data) as Record<string, unknown>
      return {
        id: String(d.id || incidentId),
        type: 'other' as Incident['type'],
        severity: 'medium' as Incident['severity'],
        source: 'user_reported' as Incident['source'],
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
}

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

  getTestResponse: async (): Promise<string> => {
    try {
      const { data } = await api.get('/chat/test')
      const inner = (data.data || data) as Record<string, unknown>
      return String(inner.response || inner.detail || 'AI unavailable')
    } catch (error) { handleError(error) }
  },
}

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

export default api

import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import type {
  User,
  Incident,
  RiskScore,
  RouteResult,
  SOSEvent,
  CommunityPost,
  Comment,
  DashboardStats,
  Analytics,
  CrimeTrend,
  DistrictAnalytics,
  HeatmapPoint,
  SafetyReport,
  MapBounds,
  ApiResponse,
} from '@/types'

const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
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
    const message = error.response?.data && typeof error.response.data === 'object'
      ? (error.response.data as Record<string, unknown>).message || error.message
      : error.message
    throw new Error(String(message))
  }
  throw error
}

export const authApi = {
  login: async (email: string, password: string): Promise<{ token: string; user: User }> => {
    try {
      const { data } = await api.post<ApiResponse<{ token: string; user: User }>>('/auth/login', { email, password })
      return data.data
    } catch (error) { handleError(error) }
  },

  signup: async (userData: { email: string; password: string; name: string; phone?: string }): Promise<{ token: string; user: User }> => {
    try {
      const { data } = await api.post<ApiResponse<{ token: string; user: User }>>('/auth/signup', userData)
      return data.data
    } catch (error) { handleError(error) }
  },

  logout: async (): Promise<void> => {
    try {
      await api.post('/auth/logout')
    } catch (error) { handleError(error) }
  },

  getProfile: async (): Promise<User> => {
    try {
      const { data } = await api.get<ApiResponse<User>>('/auth/profile')
      return data.data
    } catch (error) { handleError(error) }
  },

  updateProfile: async (updates: Partial<User>): Promise<User> => {
    try {
      const { data } = await api.put<ApiResponse<User>>('/auth/profile', updates)
      return data.data
    } catch (error) { handleError(error) }
  },
}

export const incidentApi = {
  getIncidents: async (params?: {
    page?: number
    limit?: number
    type?: string
    severity?: string
    status?: string
    lat?: number
    lng?: number
    radius?: number
  }): Promise<ApiResponse<Incident[]>> => {
    try {
      const { data } = await api.get<ApiResponse<Incident[]>>('/incidents', { params })
      return data
    } catch (error) { handleError(error) }
  },

  getIncident: async (id: string): Promise<Incident> => {
    try {
      const { data } = await api.get<ApiResponse<Incident>>(`/incidents/${id}`)
      return data.data
    } catch (error) { handleError(error) }
  },

  createReport: async (report: Omit<SafetyReport, 'id' | 'createdAt' | 'updatedAt'>): Promise<SafetyReport> => {
    try {
      const { data } = await api.post<ApiResponse<SafetyReport>>('/incidents/report', report)
      return data.data
    } catch (error) { handleError(error) }
  },
}

export const riskApi = {
  getRiskScore: async (lat: number, lng: number): Promise<RiskScore> => {
    try {
      const { data } = await api.get<ApiResponse<RiskScore>>('/risk/score', { params: { lat, lng } })
      return data.data
    } catch (error) { handleError(error) }
  },

  getHeatmapBounds: async (bounds: MapBounds, zoom: number): Promise<HeatmapPoint[]> => {
    try {
      const { data } = await api.get<ApiResponse<HeatmapPoint[]>>('/risk/heatmap', {
        params: { ...bounds, zoom },
      })
      return data.data
    } catch (error) { handleError(error) }
  },
}

export const routeApi = {
  getSafeRoute: async (source: { lat: number; lng: number }, destination: { lat: number; lng: number }): Promise<RouteResult> => {
    try {
      const { data } = await api.post<ApiResponse<RouteResult>>('/route/safe', { source, destination })
      return data.data
    } catch (error) { handleError(error) }
  },
}

export const sosApi = {
  triggerSOS: async (location: { lat: number; lng: number }, contacts?: string[]): Promise<SOSEvent> => {
    try {
      const { data } = await api.post<ApiResponse<SOSEvent>>('/sos/trigger', { location, contacts })
      return data.data
    } catch (error) { handleError(error) }
  },

  getSOSHistory: async (): Promise<SOSEvent[]> => {
    try {
      const { data } = await api.get<ApiResponse<SOSEvent[]>>('/sos/history')
      return data.data
    } catch (error) { handleError(error) }
  },
}

export const communityApi = {
  getPosts: async (params?: { page?: number; limit?: number; tag?: string }): Promise<ApiResponse<CommunityPost[]>> => {
    try {
      const { data } = await api.get<ApiResponse<CommunityPost[]>>('/community/posts', { params })
      return data
    } catch (error) { handleError(error) }
  },

  createPost: async (post: Omit<CommunityPost, 'id' | 'userId' | 'userName' | 'userAvatar' | 'upvotes' | 'downvotes' | 'commentCount' | 'createdAt' | 'updatedAt'>): Promise<CommunityPost> => {
    try {
      const { data } = await api.post<ApiResponse<CommunityPost>>('/community/posts', post)
      return data.data
    } catch (error) { handleError(error) }
  },

  getComments: async (postId: string): Promise<Comment[]> => {
    try {
      const { data } = await api.get<ApiResponse<Comment[]>>(`/community/posts/${postId}/comments`)
      return data.data
    } catch (error) { handleError(error) }
  },

  createComment: async (postId: string, content: string): Promise<Comment> => {
    try {
      const { data } = await api.post<ApiResponse<Comment>>(`/community/posts/${postId}/comments`, { content })
      return data.data
    } catch (error) { handleError(error) }
  },
}

export const adminApi = {
  getDashboardStats: async (): Promise<DashboardStats> => {
    try {
      const { data } = await api.get<ApiResponse<DashboardStats>>('/admin/dashboard')
      return data.data
    } catch (error) { handleError(error) }
  },

  moderateIncident: async (incidentId: string, action: 'verify' | 'dismiss' | 'resolve', notes?: string): Promise<Incident> => {
    try {
      const { data } = await api.put<ApiResponse<Incident>>(`/admin/incidents/${incidentId}/moderate`, { action, notes })
      return data.data
    } catch (error) { handleError(error) }
  },

  manageUser: async (userId: string, action: 'suspend' | 'activate' | 'promote' | 'demote'): Promise<User> => {
    try {
      const { data } = await api.put<ApiResponse<User>>(`/admin/users/${userId}`, { action })
      return data.data
    } catch (error) { handleError(error) }
  },
}

export const chatApi = {
  sendMessage: async (message: string, context?: { lat?: number; lng?: number; incidentId?: string }): Promise<string> => {
    try {
      const { data } = await api.post<ApiResponse<{ response: string }>>('/chat/message', { message, context })
      return data.data.response
    } catch (error) { handleError(error) }
  },

  getTestResponse: async (): Promise<string> => {
    try {
      const { data } = await api.get<ApiResponse<{ response: string }>>('/chat/test')
      return data.data.response
    } catch (error) { handleError(error) }
  },
}

export const analyticsApi = {
  getDistrictAnalytics: async (): Promise<DistrictAnalytics[]> => {
    try {
      const { data } = await api.get<ApiResponse<DistrictAnalytics[]>>('/analytics/districts')
      return data.data
    } catch (error) { handleError(error) }
  },

  getCrimeTrends: async (params?: { days?: number; type?: string }): Promise<CrimeTrend[]> => {
    try {
      const { data } = await api.get<ApiResponse<CrimeTrend[]>>('/analytics/crime-trends', { params })
      return data.data
    } catch (error) { handleError(error) }
  },
}

export default api

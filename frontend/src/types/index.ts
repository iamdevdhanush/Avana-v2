export interface User {
  id: string
  email: string
  name: string
  phone?: string
  avatar?: string
  role: 'user' | 'admin' | 'moderator'
  emergencyContacts: EmergencyContact[]
  isVerified: boolean
  createdAt: string
  updatedAt: string
}

export interface EmergencyContact {
  id: string
  name: string
  phone: string
  relationship: string
  notifyOnSOS: boolean
}

export enum IncidentType {
  THEFT = 'theft',
  ASSAULT = 'assault',
  HARASSMENT = 'harassment',
  ROBBERY = 'robbery',
  VANDALISM = 'vandalism',
  SUSPICIOUS = 'suspicious',
  TRAFFIC = 'traffic',
  NATURAL_DISASTER = 'natural_disaster',
  FIRE = 'fire',
  MEDICAL = 'medical',
  OTHER = 'other',
}

export enum IncidentSeverity {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  CRITICAL = 'critical',
}

export enum IncidentSource {
  USER_REPORTED = 'user_reported',
  OFFICIAL = 'official',
  NEWS = 'news',
  SOCIAL_MEDIA = 'social_media',
  CCTV = 'cctv',
}

export enum IncidentStatus {
  REPORTED = 'reported',
  VERIFIED = 'verified',
  INVESTIGATING = 'investigating',
  RESOLVED = 'resolved',
  DISMISSED = 'dismissed',
}

export interface Incident {
  id: string
  type: IncidentType
  severity: IncidentSeverity
  source: IncidentSource
  status: IncidentStatus
  title: string
  description: string
  location: {
    lat: number
    lng: number
    address?: string
  }
  reportedBy: string
  reportedAt: string
  updatedAt: string
  resolvedAt?: string
  mediaUrls?: string[]
  upvotes: number
  downvotes: number
  isVerified: boolean
}

export interface RiskScore {
  score: number
  category: 'safe' | 'low' | 'moderate' | 'high' | 'critical'
  factors: RiskFactor[]
  location: {
    lat: number
    lng: number
  }
  timestamp: string
  recommendations: string[]
}

export interface RiskFactor {
  name: string
  weight: number
  value: number
  description: string
}

export interface SafetyReport {
  id: string
  userId: string
  incidentId?: string
  title: string
  description: string
  location: {
    lat: number
    lng: number
    address?: string
  }
  severity: IncidentSeverity
  status: IncidentStatus
  createdAt: string
  updatedAt: string
}

export interface SOSEvent {
  id: string
  userId: string
  location: {
    lat: number
    lng: number
  }
  timestamp: string
  status: 'active' | 'responded' | 'resolved' | 'cancelled'
  acknowledgedBy?: string[]
  notes?: string
}

export interface NewsArticle {
  id: string
  title: string
  description: string
  url: string
  source: string
  imageUrl?: string
  publishedAt: string
  location?: {
    lat: number
    lng: number
    address?: string
  }
  categories: string[]
  isSafetyRelated: boolean
}

export interface PoliceStation {
  id: string
  name: string
  location: {
    lat: number
    lng: number
  }
  address: string
  phone: string
  jurisdiction?: string
  isOpen24Hours: boolean
  rating?: number
}

export interface Hospital {
  id: string
  name: string
  location: {
    lat: number
    lng: number
  }
  address: string
  phone: string
  emergency: boolean
  traumaCenter: boolean
  bedsAvailable?: number
  rating?: number
}

export interface CommunityPost {
  id: string
  userId: string
  userName: string
  userAvatar?: string
  title: string
  content: string
  location?: {
    lat: number
    lng: number
    address?: string
  }
  tags: string[]
  upvotes: number
  downvotes: number
  commentCount: number
  isIncident: boolean
  createdAt: string
  updatedAt: string
}

export interface Comment {
  id: string
  postId: string
  userId: string
  userName: string
  userAvatar?: string
  content: string
  upvotes: number
  createdAt: string
}

export interface HeatmapPoint {
  lat: number
  lng: number
  weight: number
}

export interface RouteOption {
  geometry: [number, number][]
  segments: RouteSegment[]
  duration: number
  distance: number
  safetyScore: number
}

export interface RouteSegment {
  startIndex: number
  endIndex: number
  safetyScore: number
  riskLevel: 'low' | 'medium' | 'high'
  incidents: Incident[]
}

export interface RouteResult {
  safest: RouteOption
  fastest: RouteOption
  balanced: RouteOption
}

export interface SafetyRecommendation {
  id: string
  title: string
  description: string
  category: 'route' | 'behavior' | 'preparedness' | 'awareness'
  priority: 'low' | 'medium' | 'high'
  location?: {
    lat: number
    lng: number
  }
  createdAt: string
}

export interface Analytics {
  total: number
  highRisk: number
  mediumRisk: number
  lowRisk: number
  critical: number
}

export interface DashboardStats {
  totalIncidents: number
  activeIncidents: number
  resolvedIncidents: number
  sosTriggers: number
  activeUsers: number
  riskScore: number
  incidentsByType: Record<string, number>
  incidentsBySeverity: Record<string, number>
  recentIncidents: Incident[]
  districtAnalytics: DistrictAnalytics[]
  crimeTrends: CrimeTrend[]
}

export interface DistrictAnalytics {
  district: string
  total: number
  highRisk: number
  mediumRisk: number
  lowRisk: number
  critical: number
}

export interface CrimeTrend {
  date: string
  count: number
  type?: string
}

export interface ApiResponse<T> {
  data: T
  message?: string
  status: 'success' | 'error'
  pagination?: {
    page: number
    limit: number
    total: number
    totalPages: number
  }
}

export type MapType = 'heatmap' | 'incidents' | 'safe_zones' | 'traffic'

export interface MapBounds {
  north: number
  south: number
  east: number
  west: number
}

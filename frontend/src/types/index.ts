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
  isPrimary: boolean
  // Keep notifyOnSOS for UI convenience (maps to isPrimary)
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

// Backend enum values: news, user_report (NOT user_reported)
export enum IncidentSource {
  USER_REPORT = 'user_report',
  NEWS = 'news',
  OFFICIAL = 'official',
  SOCIAL_MEDIA = 'social_media',
  CCTV = 'cctv',
}

// Backend enum values: pending, verified, dismissed, duplicate, spam
export enum IncidentStatus {
  PENDING = 'pending',
  VERIFIED = 'verified',
  DISMISSED = 'dismissed',
  DUPLICATE = 'duplicate',
  SPAM = 'spam',
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
  district?: string
  city?: string
  confidenceScore?: number
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

// Backend SOS statuses: triggered, acknowledged, resolved, false_alarm
export interface SOSEvent {
  id: string
  userId: string
  location: {
    lat: number
    lng: number
  }
  timestamp: string
  status: 'triggered' | 'acknowledged' | 'resolved' | 'false_alarm'
  acknowledgedBy?: string[]
  notes?: string
  notifiedContacts?: { name: string; phone: string; relationship: string }[]
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
  postType?: string
  tags: string[]
  upvotes: number
  downvotes: number
  commentCount: number
  isIncident: boolean
  isVerified: boolean
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
  replies?: Comment[]
}

export interface HeatmapPoint {
  lat: number
  lng: number
  weight: number
  riskCategory?: string
  intensity?: number
  radius?: number
}

export interface DistrictSummary {
  district: string
  avgScore: number
  totalIncidents: number
  trend: 'improving' | 'stable' | 'worsening'
}

export interface HeatmapResponse {
  points: HeatmapPoint[]
  generatedAt: string | null
  districtSummaries: DistrictSummary[]
}

export interface ReverseGeocodeResult {
  displayName: string
  locality: string
  suburb: string
  district: string
  city: string
  state: string
  country: string
  latitude: number
  longitude: number
  cached: boolean
  responseTimeMs: number
}

export interface RouteOption {
  geometry: [number, number][]
  segments: RouteSegment[]
  duration: number
  distance: number
  safetyScore: number
  type?: string
}

export interface RouteSegment {
  startIndex: number
  endIndex: number
  safetyScore: number
  riskLevel: 'low' | 'medium' | 'high'
  riskCategory?: string
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

// ── System Health Types ──────────────────────────────────────────────────────

export type HealthStatus = 'healthy' | 'degraded' | 'offline'

export interface ServiceHealth {
  name: string
  status: HealthStatus
  responseMs?: number
  checkedAt: string
  detail?: string
}

export interface SystemHealth {
  backend: ServiceHealth
  routeEngine: ServiceHealth
  aiService: ServiceHealth
  lastChecked: string
}

// ── Pipeline Types ────────────────────────────────────────────────────────────

export interface PipelineAgent {
  name: string
  status: 'idle' | 'running' | 'available'
  scheduledMinutes: number | null
}

export interface PipelineRunResult {
  name: string
  status: 'completed' | 'failed' | 'triggered' | 'skipped'
  incidentsSaved?: number
  errors?: string[]
  durationSeconds?: number
  articlesProcessed?: number
  ranAt: string
  reason?: string
}

export interface LastIntelligenceRun {
  ranAt: string
  incidentsSaved: number
  durationSeconds: number
  errors: string[]
  name: string
}

// ── Risk Explainability ──────────────────────────────────────────────────────

export interface ExplainSourceItem {
  title?: string
  incident_type: string
  severity: string
  date: string
  source: string
  source_url?: string
  distance_meters: number
  publisher?: string
  dataset_name?: string
  dataset_year?: number
  dataset_district?: string
}

export interface ExplainResponse {
  risk_score: number
  risk_category: string
  incident_count: number
  sources: ExplainSourceItem[]
}

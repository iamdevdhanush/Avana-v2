import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Navigation, Flag, AlertTriangle, Map as MapIcon,
  TrendingUp, TrendingDown, Minus, ChevronRight,
  Loader2, Shield, Activity,
} from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { useGeolocation } from '@/hooks/useGeolocation'
import { riskApi, incidentApi, analyticsApi } from '@/services/api'
import type { RiskScore, Incident, CrimeTrend } from '@/types'
import { formatRelativeTime } from '@/lib/utils'

const SEVERITY_CONFIG = {
  low:      { color: '#22C55E', bg: 'rgba(34,197,94,0.12)',    dot: '#22C55E' },
  medium:   { color: '#F59E0B', bg: 'rgba(245,158,11,0.12)',   dot: '#F59E0B' },
  high:     { color: '#EF4444', bg: 'rgba(239,68,68,0.12)',    dot: '#EF4444' },
  critical: { color: '#7C3AED', bg: 'rgba(124,58,237,0.12)',   dot: '#7C3AED' },
}

const CATEGORY_CONFIG = {
  safe:     { label: 'SAFE',     color: '#22C55E', bg: 'rgba(34,197,94,0.12)',    ring: '#22C55E' },
  low:      { label: 'LOW RISK', color: '#22C55E', bg: 'rgba(34,197,94,0.12)',    ring: '#22C55E' },
  moderate: { label: 'MODERATE', color: '#F59E0B', bg: 'rgba(245,158,11,0.12)',   ring: '#F59E0B' },
  high:     { label: 'HIGH RISK',color: '#EF4444', bg: 'rgba(239,68,68,0.12)',    ring: '#EF4444' },
  critical: { label: 'CRITICAL', color: '#7C3AED', bg: 'rgba(124,58,237,0.12)',   ring: '#7C3AED' },
}

const TYPE_LABELS: Record<string, string> = {
  theft: 'Theft', assault: 'Assault', harassment: 'Harassment',
  robbery: 'Robbery', vandalism: 'Vandalism', suspicious: 'Suspicious Activity',
  traffic: 'Traffic Incident', medical: 'Medical Emergency', other: 'Incident',
}

export function HomeScreen() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const { position, isLoading: geoLoading } = useGeolocation()

  const [riskScore, setRiskScore] = React.useState<RiskScore | null>(null)
  const [riskLoading, setRiskLoading] = React.useState(true)
  const [incidents, setIncidents] = React.useState<Incident[]>([])
  const [incidentsLoading, setIncidentsLoading] = React.useState(true)
  const [trends, setTrends] = React.useState<CrimeTrend[]>([])
  const [trendsLoading, setTrendsLoading] = React.useState(true)
  const [prevWeekTotal, setPrevWeekTotal] = React.useState<number | null>(null)

  const firstName = user?.name?.split(' ')[0] || 'there'
  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'

  // Fetch risk score when location is available
  React.useEffect(() => {
    if (!position.latitude || !position.longitude) return
    setRiskLoading(true)
    riskApi.getRiskScore(position.latitude, position.longitude)
      .then(setRiskScore)
      .catch(() => {})
      .finally(() => setRiskLoading(false))
  }, [position.latitude, position.longitude])

  // Fetch nearby incidents when location is available
  React.useEffect(() => {
    if (!position.latitude || !position.longitude) return
    setIncidentsLoading(true)
    incidentApi.getIncidents({
      lat: position.latitude,
      lng: position.longitude,
      radius: 5,
      limit: 5,
    })
      .then((res) => setIncidents(res.data))
      .catch(() => {})
      .finally(() => setIncidentsLoading(false))
  }, [position.latitude, position.longitude])

  // Fetch 14-day trends to compute weekly comparison
  React.useEffect(() => {
    setTrendsLoading(true)
    analyticsApi.getCrimeTrends({ days: 14 })
      .then((data) => {
        setTrends(data)
        // Compare last 7 days vs previous 7 days
        if (data.length >= 14) {
          const thisWeek = data.slice(-7).reduce((s, d) => s + d.count, 0)
          const lastWeek = data.slice(-14, -7).reduce((s, d) => s + d.count, 0)
          setPrevWeekTotal(lastWeek - thisWeek) // positive = safer
        }
      })
      .catch(() => {})
      .finally(() => setTrendsLoading(false))
  }, [])

  // Derived stats from trends
  const thisWeekTotal = trends.slice(-7).reduce((s, d) => s + d.count, 0)
  const thisWeekHigh = trends.slice(-7).filter(d => (d.type === 'high_risk')).length

  // Risk ring values
  const catConfig = riskScore
    ? CATEGORY_CONFIG[riskScore.category] || CATEGORY_CONFIG.moderate
    : null
  const scoreVal = riskScore ? Math.round(riskScore.score * 100) : null
  const circumference = 2 * Math.PI * 44 // r=44
  const offset = riskScore
    ? circumference - (riskScore.score * circumference)
    : circumference

  return (
    <div className="min-h-full pb-safe">
      <div className="max-w-lg mx-auto px-4 pt-5 pb-6 space-y-4">

        {/* Greeting */}
        <div className="flex items-center justify-between animate-fade-in-up">
          <div>
            <h1 className="text-2xl font-bold text-[#F9FAFB]">{greeting}, {firstName}</h1>
            <p className="text-xs text-[#6B7280] mt-0.5">
              {geoLoading
                ? 'Detecting your location...'
                : position.latitude
                  ? 'Location detected'
                  : 'Enable location for safety data'}
            </p>
          </div>
          <div
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-full text-xs font-medium"
            style={{ background: '#1A1A24', border: '1px solid #1F2937', color: '#6B7280' }}
          >
            <div className="w-1.5 h-1.5 rounded-full bg-[#22C55E] animate-pulse" />
            Live
          </div>
        </div>

        {/* ── SECTION 1: Current Safety Status ── */}
        <div
          className="rounded-2xl p-5 animate-fade-in-up"
          style={{
            background: '#1A1A24',
            border: `1px solid ${catConfig ? catConfig.ring + '30' : '#1F2937'}`,
            animationDelay: '60ms',
            animationFillMode: 'both',
          }}
        >
          <p className="text-xs font-semibold text-[#6B7280] uppercase tracking-widest mb-4">
            Current Safety Status
          </p>

          {riskLoading || (!position.latitude && geoLoading) ? (
            <div className="flex items-center gap-5">
              <div className="w-24 h-24 rounded-full bg-[#111827] animate-shimmer shrink-0" />
              <div className="space-y-2 flex-1">
                <div className="h-4 w-24 rounded bg-[#111827] animate-shimmer" />
                <div className="h-8 w-16 rounded bg-[#111827] animate-shimmer" />
                <div className="h-3 w-32 rounded bg-[#111827] animate-shimmer" />
              </div>
            </div>
          ) : riskScore ? (
            <div className="flex items-center gap-5">
              {/* Score ring */}
              <div className="relative shrink-0">
                <svg className="w-24 h-24 -rotate-90" viewBox="0 0 100 100">
                  <circle
                    cx="50" cy="50" r="44"
                    fill="none" stroke="#1F2937" strokeWidth="8"
                  />
                  <circle
                    cx="50" cy="50" r="44"
                    fill="none"
                    stroke={catConfig?.ring || '#A855F7'}
                    strokeWidth="8"
                    strokeDasharray={circumference}
                    strokeDashoffset={offset}
                    strokeLinecap="round"
                    style={{ transition: 'stroke-dashoffset 1.2s cubic-bezier(0.4,0,0.2,1)' }}
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-2xl font-black text-[#F9FAFB]">{scoreVal}</span>
                  <span className="text-[10px] text-[#6B7280] font-medium">/ 100</span>
                </div>
              </div>

              <div className="flex-1">
                <span
                  className="inline-block px-3 py-1.5 rounded-full text-sm font-black tracking-wide mb-2"
                  style={{
                    background: catConfig?.bg,
                    color: catConfig?.color,
                    boxShadow: `0 0 12px ${catConfig?.ring}30`,
                  }}
                >
                  {catConfig?.label}
                </span>
                {/* Trend indicator */}
                {prevWeekTotal !== null && (
                  <div className="flex items-center gap-1.5 mt-1">
                    {prevWeekTotal > 0 ? (
                      <>
                        <TrendingUp className="h-3.5 w-3.5 text-[#22C55E]" />
                        <span className="text-xs text-[#22C55E] font-medium">Safer than last week</span>
                      </>
                    ) : prevWeekTotal < 0 ? (
                      <>
                        <TrendingDown className="h-3.5 w-3.5 text-[#EF4444]" />
                        <span className="text-xs text-[#EF4444] font-medium">More incidents this week</span>
                      </>
                    ) : (
                      <>
                        <Minus className="h-3.5 w-3.5 text-[#6B7280]" />
                        <span className="text-xs text-[#6B7280] font-medium">Similar to last week</span>
                      </>
                    )}
                  </div>
                )}
                {riskScore.recommendations.length > 0 && (
                  <p className="text-xs text-[#6B7280] mt-2 leading-relaxed line-clamp-2">
                    {riskScore.recommendations[0]}
                  </p>
                )}
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-3 py-2">
              <div className="w-12 h-12 rounded-full bg-[#1F2937] flex items-center justify-center">
                <Shield className="h-6 w-6 text-[#6B7280]" />
              </div>
              <div>
                <p className="text-sm font-medium text-[#F9FAFB]">Location required</p>
                <p className="text-xs text-[#6B7280]">Enable GPS to see safety data for your area</p>
              </div>
            </div>
          )}
        </div>

        {/* ── SECTION 2: Nearby Alerts ── */}
        <div
          className="rounded-2xl overflow-hidden animate-fade-in-up"
          style={{ background: '#1A1A24', border: '1px solid #1F2937', animationDelay: '120ms', animationFillMode: 'both' }}
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-[#1F2937]">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-[#EF4444]" />
              <span className="text-sm font-semibold text-[#F9FAFB]">Nearby Alerts</span>
            </div>
            <button
              onClick={() => navigate('/map')}
              className="flex items-center gap-1 text-xs text-[#A855F7] hover:text-[#C084FC] transition-colors font-medium"
            >
              View Map <ChevronRight className="h-3 w-3" />
            </button>
          </div>

          {incidentsLoading ? (
            <div className="p-4 space-y-3">
              {[0,1,2].map(i => (
                <div key={i} className="flex gap-3 items-center">
                  <div className="w-2 h-2 rounded-full bg-[#1F2937] shrink-0" />
                  <div className="flex-1 h-4 rounded bg-[#111827] animate-shimmer" />
                </div>
              ))}
            </div>
          ) : incidents.length === 0 ? (
            <div className="px-4 py-6 text-center">
              <p className="text-sm text-[#22C55E] font-medium">No incidents nearby</p>
              <p className="text-xs text-[#6B7280] mt-1">Your area appears clear within 5km</p>
            </div>
          ) : (
            <div className="divide-y divide-[#1F2937]">
              {incidents.map((inc) => {
                const sev = SEVERITY_CONFIG[inc.severity as keyof typeof SEVERITY_CONFIG] || SEVERITY_CONFIG.medium
                return (
                  <button
                    key={inc.id}
                    onClick={() => navigate(`/incident/${inc.id}`)}
                    className="w-full flex items-center gap-3 px-4 py-3.5 hover:bg-[#1F2937] transition-colors text-left group"
                  >
                    <div
                      className="w-2 h-2 rounded-full shrink-0"
                      style={{ background: sev.dot, boxShadow: `0 0 6px ${sev.dot}80` }}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-[#F9FAFB] truncate">
                        {TYPE_LABELS[inc.type] || inc.type}
                      </p>
                      <p className="text-xs text-[#6B7280]">{formatRelativeTime(inc.reportedAt)}</p>
                    </div>
                    <span
                      className="text-[10px] font-bold px-2 py-0.5 rounded-full shrink-0 uppercase tracking-wide"
                      style={{ background: sev.bg, color: sev.color }}
                    >
                      {inc.severity}
                    </span>
                    <ChevronRight className="h-3.5 w-3.5 text-[#374151] group-hover:text-[#6B7280] transition-colors shrink-0" />
                  </button>
                )
              })}
            </div>
          )}
        </div>

        {/* ── SECTION 3: Quick Actions ── */}
        <div
          className="animate-fade-in-up"
          style={{ animationDelay: '180ms', animationFillMode: 'both' }}
        >
          <p className="text-xs font-semibold text-[#6B7280] uppercase tracking-widest mb-3">Quick Actions</p>
          <div className="grid grid-cols-2 gap-3">
            <QuickAction
              icon={<Navigation className="h-6 w-6" />}
              label="Safe Route"
              description="Find the safest path"
              onClick={() => navigate('/map')}
              color="#A855F7"
              bg="rgba(168,85,247,0.12)"
              border="rgba(168,85,247,0.25)"
            />
            <QuickAction
              icon={<Flag className="h-6 w-6" />}
              label="Report Incident"
              description="Alert the community"
              onClick={() => navigate('/report')}
              color="#EC4899"
              bg="rgba(236,72,153,0.10)"
              border="rgba(236,72,153,0.20)"
            />
            <QuickAction
              icon={<AlertTriangle className="h-6 w-6" />}
              label="SOS"
              description="Emergency alert"
              onClick={() => navigate('/sos')}
              color="#EF4444"
              bg="rgba(239,68,68,0.10)"
              border="rgba(239,68,68,0.20)"
              pulse
            />
            <QuickAction
              icon={<MapIcon className="h-6 w-6" />}
              label="View Heatmap"
              description="See risk zones"
              onClick={() => navigate('/map')}
              color="#F59E0B"
              bg="rgba(245,158,11,0.10)"
              border="rgba(245,158,11,0.20)"
            />
          </div>
        </div>

        {/* ── SECTION 4: Heatmap Preview ── */}
        <button
          onClick={() => navigate('/map')}
          className="w-full rounded-2xl overflow-hidden text-left transition-all hover:scale-[1.01] active:scale-[0.99] animate-fade-in-up"
          style={{
            background: '#1A1A24',
            border: '1px solid #1F2937',
            animationDelay: '240ms',
            animationFillMode: 'both',
          }}
        >
          {/* Simulated heatmap preview */}
          <div
            className="h-28 relative overflow-hidden"
            style={{
              background: 'linear-gradient(135deg, #09090B 0%, #111827 50%, #1A1A24 100%)',
            }}
          >
            {/* Heatmap blobs */}
            <div className="absolute inset-0 pointer-events-none">
              <div className="absolute top-2 left-8 w-16 h-16 rounded-full opacity-40"
                style={{ background: 'radial-gradient(circle, #EF4444 0%, transparent 70%)' }} />
              <div className="absolute top-6 left-24 w-12 h-12 rounded-full opacity-30"
                style={{ background: 'radial-gradient(circle, #F97316 0%, transparent 70%)' }} />
              <div className="absolute bottom-2 right-8 w-20 h-20 rounded-full opacity-35"
                style={{ background: 'radial-gradient(circle, #EAB308 0%, transparent 70%)' }} />
              <div className="absolute bottom-4 right-28 w-10 h-10 rounded-full opacity-50"
                style={{ background: 'radial-gradient(circle, #22C55E 0%, transparent 70%)' }} />
              <div className="absolute top-4 right-12 w-8 h-8 rounded-full opacity-40"
                style={{ background: 'radial-gradient(circle, #22C55E 0%, transparent 70%)' }} />
            </div>
            {/* Overlay label */}
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-xs font-semibold text-[#F9FAFB] bg-black/40 backdrop-blur-sm px-3 py-1.5 rounded-full flex items-center gap-1.5">
                <Activity className="h-3.5 w-3.5 text-[#A855F7]" />
                Open Live Heatmap
              </span>
            </div>
          </div>
          <div className="px-4 py-3 flex items-center justify-between border-t border-[#1F2937]">
            <div>
              <p className="text-sm font-semibold text-[#F9FAFB]">Safety Heatmap</p>
              <p className="text-xs text-[#6B7280]">Real-time risk zone visualization</p>
            </div>
            <ChevronRight className="h-4 w-4 text-[#6B7280]" />
          </div>
        </button>

        {/* ── SECTION 5: Weekly Intelligence Summary ── */}
        {!trendsLoading && trends.length > 0 && (
          <div
            className="rounded-2xl p-4 animate-fade-in-up"
            style={{
              background: '#1A1A24',
              border: '1px solid #1F2937',
              animationDelay: '300ms',
              animationFillMode: 'both',
            }}
          >
            <div className="flex items-center gap-2 mb-4">
              <Activity className="h-4 w-4 text-[#A855F7]" />
              <p className="text-sm font-semibold text-[#F9FAFB]">Weekly Intelligence Summary</p>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <SummaryCard
                value={thisWeekTotal}
                label="Incidents"
                sub="this week"
                color="#EF4444"
              />
              <SummaryCard
                value={incidents.filter(i => i.severity === 'high' || i.severity === 'critical').length}
                label="High Risk"
                sub="nearby"
                color="#F59E0B"
              />
              <SummaryCard
                value={prevWeekTotal !== null && prevWeekTotal > 0 ? 1 : 0}
                label="Trend"
                sub={prevWeekTotal !== null && prevWeekTotal > 0 ? 'Improving' : prevWeekTotal !== null && prevWeekTotal < 0 ? 'Worsening' : 'Stable'}
                color={prevWeekTotal !== null && prevWeekTotal > 0 ? '#22C55E' : prevWeekTotal !== null && prevWeekTotal < 0 ? '#EF4444' : '#F59E0B'}
                isText
              />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function QuickAction({
  icon, label, description, onClick, color, bg, border, pulse,
}: {
  icon: React.ReactNode
  label: string
  description: string
  onClick: () => void
  color: string
  bg: string
  border: string
  pulse?: boolean
}) {
  return (
    <button
      onClick={onClick}
      className="relative flex flex-col items-start gap-3 p-4 rounded-2xl text-left transition-all hover:scale-[1.02] active:scale-[0.98]"
      style={{ background: bg, border: `1px solid ${border}` }}
    >
      {pulse && (
        <span
          className="absolute top-3 right-3 w-2 h-2 rounded-full"
          style={{ background: color, boxShadow: `0 0 8px ${color}` }}
        >
          <span
            className="absolute inset-0 rounded-full animate-ping opacity-75"
            style={{ background: color }}
          />
        </span>
      )}
      <div
        className="w-10 h-10 rounded-xl flex items-center justify-center"
        style={{ background: `${color}18`, color }}
      >
        {icon}
      </div>
      <div>
        <p className="text-sm font-bold text-[#F9FAFB]">{label}</p>
        <p className="text-xs text-[#6B7280] mt-0.5">{description}</p>
      </div>
    </button>
  )
}

function SummaryCard({
  value, label, sub, color, isText,
}: {
  value: number
  label: string
  sub: string
  color: string
  isText?: boolean
}) {
  return (
    <div className="rounded-xl p-3 text-center" style={{ background: '#111827' }}>
      {isText ? (
        <p className="text-base font-black" style={{ color }}>{sub}</p>
      ) : (
        <p className="text-2xl font-black" style={{ color }}>{value}</p>
      )}
      <p className="text-xs font-semibold text-[#F9FAFB] mt-0.5">{label}</p>
      {!isText && <p className="text-[10px] text-[#6B7280]">{sub}</p>}
    </div>
  )
}

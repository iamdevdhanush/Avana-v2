import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Navigation, Flag, AlertTriangle, Map as MapIcon,
  TrendingUp, TrendingDown, Minus, ChevronRight,
  Shield, Activity, Clock, Bot, Zap,
} from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { useGeolocation } from '@/hooks/useGeolocation'
import { riskApi, incidentApi, analyticsApi } from '@/services/api'
import type { LastIntelligenceRun } from '@/types'
import { formatRelativeTime } from '@/lib/utils'
import { DataFreshness } from '@/components/DataFreshness'
import { SystemHealthBar } from '@/components/SystemHealthBar'

const SEVERITY_CONFIG = {
  low:      { color: '#22C55E', bg: 'rgba(34,197,94,0.12)',    dot: '#22C55E' },
  medium:   { color: '#F59E0B', bg: 'rgba(245,158,11,0.12)',   dot: '#F59E0B' },
  high:     { color: '#EF4444', bg: 'rgba(239,68,68,0.12)',    dot: '#EF4444' },
  critical: { color: '#7C3AED', bg: 'rgba(124,58,237,0.12)',   dot: '#7C3AED' },
}

const CATEGORY_CONFIG: Record<string, { label: string; color: string; bg: string; ring: string }> = {
  safe:     { label: 'SAFE',      color: '#22C55E', bg: 'rgba(34,197,94,0.12)',    ring: '#22C55E' },
  low:      { label: 'LOW RISK',  color: '#22C55E', bg: 'rgba(34,197,94,0.12)',    ring: '#22C55E' },
  moderate: { label: 'MODERATE',  color: '#F59E0B', bg: 'rgba(245,158,11,0.12)',   ring: '#F59E0B' },
  high:     { label: 'HIGH RISK', color: '#EF4444', bg: 'rgba(239,68,68,0.12)',    ring: '#EF4444' },
  critical: { label: 'CRITICAL',  color: '#7C3AED', bg: 'rgba(124,58,237,0.12)',   ring: '#7C3AED' },
  unknown:  { label: 'UNKNOWN',   color: '#6B7280', bg: 'rgba(107,114,128,0.12)',  ring: '#6B7280' },
}

const TYPE_LABELS: Record<string, string> = {
  theft: 'Theft', assault: 'Assault', harassment: 'Harassment',
  robbery: 'Robbery', vandalism: 'Vandalism', suspicious: 'Suspicious Activity',
  traffic: 'Traffic Incident', medical: 'Medical Emergency', other: 'Incident',
}

export function HomeScreen() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const { position, isLoading: geoLoading, isFallback } = useGeolocation()

  const firstName = user?.name?.split(' ')[0] || 'there'
  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'

  // Read last intelligence run from localStorage (stored when admin triggers pipeline)
  const [lastIntelRun, setLastIntelRun] = React.useState<LastIntelligenceRun | null>(null)
  React.useEffect(() => {
    const stored = localStorage.getItem('avana_last_intel_run')
    if (stored) {
      try { setLastIntelRun(JSON.parse(stored) as LastIntelligenceRun) }
      catch { /* ignore */ }
    }
  }, [])

  // Risk score — React Query
  const { data: riskScore, isLoading: riskLoading } = useQuery({
    queryKey: ['risk-score', position.latitude, position.longitude],
    queryFn: () => riskApi.getRiskScore(position.latitude!, position.longitude!),
    enabled: !!(position.latitude && position.longitude),
    staleTime: 2 * 60_000,
    retry: 1,
  })

  // Nearby incidents — React Query
  const { data: incidentsRes, isLoading: incidentsLoading } = useQuery({
    queryKey: ['incidents-nearby', position.latitude, position.longitude],
    queryFn: () => incidentApi.getIncidents({
      lat: position.latitude!,
      lng: position.longitude!,
      radius: 5,
      limit: 5,
    }),
    enabled: !!(position.latitude && position.longitude),
    staleTime: 2 * 60_000,
    retry: 1,
  })
  const incidents = incidentsRes?.data ?? []

  // 14-day trends — React Query
  const { data: trends = [], isLoading: trendsLoading } = useQuery({
    queryKey: ['crime-trends-14'],
    queryFn: () => analyticsApi.getCrimeTrends({ days: 14 }),
    staleTime: 5 * 60_000,
    retry: 1,
  })

  // Compute weekly comparison from real trend data
  const thisWeekTotal = trends.slice(-7).reduce((s, d) => s + d.count, 0)
  const prevWeekDiff = trends.length >= 14
    ? trends.slice(-14, -7).reduce((s, d) => s + d.count, 0) - thisWeekTotal
    : null

  // Risk ring values
  const catConfig = riskScore
    ? CATEGORY_CONFIG[riskScore.category] || CATEGORY_CONFIG.moderate
    : null
  const scoreVal = riskScore ? Math.round(riskScore.score * 100) : null
  const circumference = 2 * Math.PI * 44
  const offset = riskScore ? circumference - (riskScore.score * circumference) : circumference

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
                : isFallback
                  ? 'Using Shivamogga default location'
                  : position.latitude
                    ? 'Location detected'
                    : 'Enable location for safety data'}
            </p>
          </div>
          {/* System health compact chip */}
          <SystemHealthBar compact />
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
              <div className="w-24 h-24 rounded-full bg-[#111827] animate-pulse shrink-0" />
              <div className="space-y-2 flex-1">
                <div className="h-4 w-24 rounded bg-[#111827] animate-pulse" />
                <div className="h-8 w-16 rounded bg-[#111827] animate-pulse" />
                <div className="h-3 w-32 rounded bg-[#111827] animate-pulse" />
              </div>
            </div>
          ) : riskScore ? (
            <div className="flex items-center gap-5">
              {/* Score ring */}
              <div className="relative shrink-0">
                <svg className="w-24 h-24 -rotate-90" viewBox="0 0 100 100">
                  <circle cx="50" cy="50" r="44" fill="none" stroke="#1F2937" strokeWidth="8" />
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
                {prevWeekDiff !== null && (
                  <div className="flex items-center gap-1.5 mt-1">
                    {prevWeekDiff > 0 ? (
                      <>
                        <TrendingUp className="h-3.5 w-3.5 text-[#22C55E]" />
                        <span className="text-xs text-[#22C55E] font-medium">Safer than last week</span>
                      </>
                    ) : prevWeekDiff < 0 ? (
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

        {/* ── SECTION 2: Intelligence Status ── */}
        <div
          className="rounded-2xl p-4 animate-fade-in-up"
          style={{
            background: '#1A1A24',
            border: '1px solid rgba(168,85,247,0.15)',
            animationDelay: '90ms',
            animationFillMode: 'both',
          }}
        >
          <div className="flex items-center gap-2 mb-3">
            <Bot className="h-4 w-4 text-[#A855F7]" />
            <p className="text-xs font-semibold text-[#F9FAFB] uppercase tracking-widest">Intelligence Status</p>
          </div>

          {lastIntelRun ? (
            <div className="space-y-2">
              <div className="grid grid-cols-3 gap-2">
                <div className="rounded-lg px-3 py-2.5 text-center" style={{ background: '#111827' }}>
                  <p className="text-lg font-black text-[#A855F7]">{lastIntelRun.incidentsSaved}</p>
                  <p className="text-[10px] text-[#6B7280]">Incidents Saved</p>
                </div>
                <div className="rounded-lg px-3 py-2.5 text-center" style={{ background: '#111827' }}>
                  <p className="text-lg font-black text-[#22C55E]">
                    {lastIntelRun.durationSeconds != null
                      ? `${Math.round(lastIntelRun.durationSeconds)}s`
                      : '—'}
                  </p>
                  <p className="text-[10px] text-[#6B7280]">Duration</p>
                </div>
                <div className="rounded-lg px-3 py-2.5 text-center" style={{ background: '#111827' }}>
                  <p className="text-lg font-black"
                    style={{ color: lastIntelRun.errors?.length ? '#EF4444' : '#22C55E' }}>
                    {lastIntelRun.errors?.length || 0}
                  </p>
                  <p className="text-[10px] text-[#6B7280]">Errors</p>
                </div>
              </div>
              <DataFreshness
                timestamp={lastIntelRun.ranAt}
                label="Intelligence Updated"
                warnAfterHours={24}
              />
            </div>
          ) : (
            <div className="flex items-center gap-3 py-1">
              <Clock className="h-4 w-4 text-[#374151] shrink-0" />
              <div>
                <p className="text-sm font-medium text-[#4B5563]">Intelligence Pipeline Has Not Run Yet</p>
                <p className="text-xs text-[#374151] mt-0.5">
                  Ask an admin to run the Intelligence pipeline.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* ── SECTION 3: Nearby Alerts ── */}
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
                  <div className="flex-1 h-4 rounded bg-[#111827] animate-pulse" />
                </div>
              ))}
            </div>
          ) : !position.latitude ? (
            <div className="px-4 py-6 text-center">
              <p className="text-sm text-[#6B7280]">Enable location to see nearby alerts</p>
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

        {/* ── SECTION 4: Quick Actions ── */}
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

        {/* ── SECTION 5: Heatmap → Real district summaries ── */}
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
          <div className="px-4 py-4 flex items-center gap-3 border-b border-[#1F2937]">
            <MapIcon className="h-4 w-4 text-[#A855F7]" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-[#F9FAFB]">Safety Heatmap</p>
              <p className="text-xs text-[#6B7280]">Open map for live risk zone visualization</p>
            </div>
            <ChevronRight className="h-4 w-4 text-[#6B7280]" />
          </div>
          {/* Real district risk summary instead of fake blobs */}
          <RealHeatmapPreview position={position} />
        </button>

        {/* ── SECTION 6: Weekly Intelligence Summary (real data only) ── */}
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
                value={0}
                label="Trend"
                sub={prevWeekDiff !== null && prevWeekDiff > 0 ? 'Improving' : prevWeekDiff !== null && prevWeekDiff < 0 ? 'Worsening' : 'Stable'}
                color={prevWeekDiff !== null && prevWeekDiff > 0 ? '#22C55E' : prevWeekDiff !== null && prevWeekDiff < 0 ? '#EF4444' : '#F59E0B'}
                isText
              />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// Real heatmap preview: links to map, prompts location if not available
function RealHeatmapPreview({ position }: { position: { latitude: number | null; longitude: number | null } }) {
  return (
    <div
      className="px-4 py-3 flex items-center justify-between"
      style={{ background: 'rgba(168,85,247,0.04)' }}
    >
      <div className="flex items-center gap-1.5">
        <Zap className="h-3.5 w-3.5 text-[#A855F7]" />
        <span className="text-xs text-[#6B7280]">
          {position.latitude ? 'Tap to see live risk zones near you' : 'Enable location to see risk zones'}
        </span>
      </div>
      <span className="text-[10px] font-semibold text-[#A855F7]">Open Map →</span>
    </div>
  )
}

// ── Sub-components ────────────────────────────────────────────────────────────

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

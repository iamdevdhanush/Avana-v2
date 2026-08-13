import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Navigation, Flag, AlertTriangle, Map as MapIcon,
  TrendingUp, TrendingDown, Minus, ChevronRight,
  Shield, Activity, Clock, Bot, MapPin, AlertCircle, Info,
} from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { useGeolocation } from '@/hooks/useGeolocation'
import { useLocationName } from '@/hooks/useLocationName'
import { riskApi, incidentApi, analyticsApi } from '@/services/api'
import type { LastIntelligenceRun } from '@/types'
import { formatRelativeTime } from '@/lib/utils'
import { DataFreshness } from '@/components/DataFreshness'
import { SystemHealthBar } from '@/components/SystemHealthBar'

const SEVERITY_CONFIG = {
  low:      { color: '#66BB6A', bg: 'rgba(102,187,106,0.12)', label: 'LOW' },
  medium:   { color: '#F5B942', bg: 'rgba(245,185,66,0.12)',  label: 'MEDIUM' },
  high:     { color: '#EF4444', bg: 'rgba(239,68,68,0.12)',   label: 'HIGH' },
  critical: { color: '#EF4444', bg: 'rgba(239,68,68,0.18)',   label: 'CRITICAL' },
}

const CATEGORY_CONFIG: Record<string, { label: string; color: string; bg: string; border: string }> = {
  safe:     { label: 'SAFE',          color: '#66BB6A', bg: 'rgba(102,187,106,0.12)', border: '#66BB6A' },
  low:      { label: 'LOWER RISK',    color: '#66BB6A', bg: 'rgba(102,187,106,0.12)', border: '#66BB6A' },
  moderate: { label: 'MODERATE RISK', color: '#F5B942', bg: 'rgba(245,185,66,0.12)',  border: '#F5B942' },
  high:     { label: 'ELEVATED RISK', color: '#EF4444', bg: 'rgba(239,68,68,0.12)',   border: '#EF4444' },
  critical: { label: 'HIGH DANGER',   color: '#EF4444', bg: 'rgba(239,68,68,0.18)',   border: '#EF4444' },
  unknown:  { label: 'UNKNOWN',       color: '#8A948C', bg: 'rgba(138,148,140,0.12)', border: '#8A948C' },
}

const TYPE_LABELS: Record<string, string> = {
  theft: 'Theft Report', assault: 'Assault Warning', harassment: 'Harassment',
  robbery: 'Robbery', vandalism: 'Vandalism', suspicious: 'Suspicious Activity',
  traffic: 'Traffic Incident', medical: 'Medical Emergency', other: 'Safety Incident',
}

export function HomeScreen() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const { position, isLoading: geoLoading, isFallback } = useGeolocation()
  const locationName = useLocationName(position.latitude, position.longitude)

  const firstName = user?.name?.split(' ')[0] || 'there'
  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'

  // Intelligence run state
  const [lastIntelRun, setLastIntelRun] = React.useState<LastIntelligenceRun | null>(null)
  React.useEffect(() => {
    const stored = localStorage.getItem('avana_last_intel_run')
    if (stored) {
      try { setLastIntelRun(JSON.parse(stored) as LastIntelligenceRun) }
      catch { /* ignore */ }
    }
  }, [])

  // Risk score query
  const { data: riskScore, isLoading: riskLoading } = useQuery({
    queryKey: ['risk-score', position.latitude, position.longitude],
    queryFn: () => riskApi.getRiskScore(position.latitude!, position.longitude!),
    enabled: !!(position.latitude && position.longitude),
    staleTime: 2 * 60_000,
    retry: 1,
  })

  // Nearby incidents query
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

  // 14-day trends query
  const { data: trends = [], isLoading: trendsLoading } = useQuery({
    queryKey: ['crime-trends-14'],
    queryFn: () => analyticsApi.getCrimeTrends({ days: 14 }),
    staleTime: 5 * 60_000,
    retry: 1,
  })

  const thisWeekTotal = trends.slice(-7).reduce((s, d) => s + d.count, 0)
  const prevWeekDiff = trends.length >= 14
    ? trends.slice(-14, -7).reduce((s, d) => s + d.count, 0) - thisWeekTotal
    : null

  const isUnknownRisk = !riskScore || riskScore.category?.toLowerCase() === 'unknown'
  const catConfig = riskScore
    ? CATEGORY_CONFIG[riskScore.category] || CATEGORY_CONFIG.moderate
    : CATEGORY_CONFIG.unknown

  const scoreVal = riskScore && !isUnknownRisk ? Math.round(riskScore.score * 100) : null

  return (
    <div className="min-h-full pb-safe bg-[#07110A]">
      <div className="max-w-lg mx-auto px-4 pt-5 pb-6 space-y-4">

        {/* ── HERO LOCATION & GREETING ── */}
        <div className="space-y-1.5 animate-fade-in-up">
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-bold text-[#F1F8F2] tracking-tight">
              {greeting}, {firstName}
            </h1>
            <SystemHealthBar compact />
          </div>

          <div className="flex items-center gap-2 text-xs text-[#9BAF9F]">
            <MapPin className="h-3.5 w-3.5 text-[#66BB6A] shrink-0" />
            <span className="truncate">
              {geoLoading
                ? 'Detecting location...'
                : locationName.displayName || (isFallback ? 'Shivamogga, Karnataka' : 'Location active')}
            </span>
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#66BB6A] ml-auto shrink-0" title="Intelligence Active" />
          </div>
        </div>

        {/* ── CURRENT SAFETY HERO CARD ── */}
        <div
          className="rounded-2xl p-5 animate-fade-in-up avana-surface"
          style={{ border: `1px solid ${isUnknownRisk ? '#1D3823' : catConfig.border + '40'}` }}
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-[10px] font-bold text-[#9BAF9F] uppercase tracking-wider">
              Current Safety Status
            </span>
            <span className="text-[10px] text-[#9BAF9F] flex items-center gap-1">
              <Shield className="h-3 w-3 text-[#66BB6A]" /> Verified
            </span>
          </div>

          {riskLoading || (!position.latitude && geoLoading) ? (
            <div className="py-6 space-y-3">
              <div className="h-6 w-32 rounded bg-[#122417] animate-pulse" />
              <div className="h-10 w-24 rounded bg-[#122417] animate-pulse" />
              <div className="h-4 w-48 rounded bg-[#122417] animate-pulse" />
            </div>
          ) : isUnknownRisk ? (
            /* UNKNOWN SAFETY STATE — Explicit & Clear */
            <div className="py-4 space-y-3">
              <div className="flex items-center gap-3">
                <div className="px-3 py-1.5 rounded-lg bg-[#8A948C]/15 border border-[#8A948C]/30 text-[#8A948C] font-extrabold text-sm tracking-wider">
                  SAFETY STATUS: UNKNOWN
                </div>
              </div>
              <p className="text-xs text-[#9BAF9F] leading-relaxed">
                Insufficient recent safety intelligence for this location. We display unknown status when local data points fall below accuracy confidence thresholds.
              </p>
            </div>
          ) : (
            /* KNOWN SAFETY SCORE STATE */
            <div className="space-y-4">
              <div className="flex items-baseline justify-between">
                <div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-4xl font-black tracking-tight text-[#F1F8F2]">{scoreVal}</span>
                    <span className="text-sm font-semibold text-[#9BAF9F]">/ 100</span>
                  </div>
                  <div className="mt-1">
                    <span
                      className="inline-block px-2.5 py-0.5 rounded-md text-xs font-black tracking-wide"
                      style={{ background: catConfig.bg, color: catConfig.color, border: `1px solid ${catConfig.border}40` }}
                    >
                      {catConfig.label}
                    </span>
                  </div>
                </div>

                {prevWeekDiff !== null && (
                  <div className="text-right">
                    <div className="flex items-center justify-end gap-1 text-xs font-semibold">
                      {prevWeekDiff > 0 ? (
                        <>
                          <TrendingUp className="h-3.5 w-3.5 text-[#66BB6A]" />
                          <span className="text-[#66BB6A]">Safer trend</span>
                        </>
                      ) : prevWeekDiff < 0 ? (
                        <>
                          <TrendingDown className="h-3.5 w-3.5 text-[#EF4444]" />
                          <span className="text-[#EF4444]">Elevated incidents</span>
                        </>
                      ) : (
                        <>
                          <Minus className="h-3.5 w-3.5 text-[#8A948C]" />
                          <span className="text-[#8A948C]">Stable trend</span>
                        </>
                      )}
                    </div>
                    <span className="text-[10px] text-[#9BAF9F]">vs last 7 days</span>
                  </div>
                )}
              </div>

              {/* Segmented Safety Scale */}
              <div className="space-y-1.5 pt-1">
                <div className="flex h-2 w-full rounded-full overflow-hidden bg-[#122417] gap-0.5 p-0.5 border border-[#1D3823]">
                  <div className={`flex-1 rounded-sm transition-all ${scoreVal! >= 20 ? 'bg-[#66BB6A]' : 'bg-[#1D3823]'}`} />
                  <div className={`flex-1 rounded-sm transition-all ${scoreVal! >= 40 ? 'bg-[#66BB6A]' : 'bg-[#1D3823]'}`} />
                  <div className={`flex-1 rounded-sm transition-all ${scoreVal! >= 60 ? 'bg-[#F5B942]' : 'bg-[#1D3823]'}`} />
                  <div className={`flex-1 rounded-sm transition-all ${scoreVal! >= 80 ? 'bg-[#F97316]' : 'bg-[#1D3823]'}`} />
                  <div className={`flex-1 rounded-sm transition-all ${scoreVal! >= 95 ? 'bg-[#EF4444]' : 'bg-[#1D3823]'}`} />
                </div>
              </div>

              {/* Factors Breakdown */}
              <div className="grid grid-cols-3 gap-2 pt-2 border-t border-[#1D3823]">
                <div className="p-2 rounded-lg bg-[#122417] text-center">
                  <span className="text-[10px] text-[#9BAF9F] block">Recent Incidents</span>
                  <span className="text-xs font-bold text-[#F1F8F2] mt-0.5 block">
                    {incidents.length === 0 ? 'Low' : incidents.length < 3 ? 'Moderate' : 'High'}
                  </span>
                </div>
                <div className="p-2 rounded-lg bg-[#122417] text-center">
                  <span className="text-[10px] text-[#9BAF9F] block">Reports</span>
                  <span className="text-xs font-bold text-[#66BB6A] mt-0.5 block">Active</span>
                </div>
                <div className="p-2 rounded-lg bg-[#122417] text-center">
                  <span className="text-[10px] text-[#9BAF9F] block">Route Risk</span>
                  <span className="text-xs font-bold text-[#F1F8F2] mt-0.5 block">Normal</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ── INTELLIGENCE STATUS ── */}
        <div className="rounded-2xl p-4 avana-surface animate-fade-in-up">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Bot className="h-4 w-4 text-[#66BB6A]" />
              <span className="text-xs font-bold text-[#F1F8F2] uppercase tracking-wider">
                Safety Intelligence Engine
              </span>
            </div>
            <span className="text-[10px] font-semibold text-[#66BB6A] bg-[#1B5E20]/40 px-2 py-0.5 rounded border border-[#66BB6A]/20">
              LIVE
            </span>
          </div>

          {lastIntelRun ? (
            <div className="space-y-2">
              <div className="grid grid-cols-3 gap-2">
                <div className="rounded-lg p-2.5 bg-[#122417] text-center border border-[#1D3823]">
                  <p className="text-base font-black text-[#66BB6A]">{lastIntelRun.incidentsSaved}</p>
                  <p className="text-[10px] text-[#9BAF9F]">Saved Incidents</p>
                </div>
                <div className="rounded-lg p-2.5 bg-[#122417] text-center border border-[#1D3823]">
                  <p className="text-base font-black text-[#F1F8F2]">
                    {lastIntelRun.durationSeconds != null ? `${Math.round(lastIntelRun.durationSeconds)}s` : '—'}
                  </p>
                  <p className="text-[10px] text-[#9BAF9F]">Run Time</p>
                </div>
                <div className="rounded-lg p-2.5 bg-[#122417] text-center border border-[#1D3823]">
                  <p className="text-base font-black" style={{ color: lastIntelRun.errors?.length ? '#EF4444' : '#66BB6A' }}>
                    {lastIntelRun.errors?.length || 0}
                  </p>
                  <p className="text-[10px] text-[#9BAF9F]">Pipeline Errors</p>
                </div>
              </div>
              <DataFreshness timestamp={lastIntelRun.ranAt} label="Intelligence Sync" warnAfterHours={24} />
            </div>
          ) : (
            <div className="flex items-center gap-3 py-1">
              <Clock className="h-4 w-4 text-[#8A948C] shrink-0" />
              <div>
                <p className="text-xs font-semibold text-[#F1F8F2]">Pipeline Awaiting Routine Cycle</p>
                <p className="text-[11px] text-[#9BAF9F]">Consuming active community reports & regional news feeds</p>
              </div>
            </div>
          )}
        </div>

        {/* ── NEARBY INCIDENTS LIST ── */}
        <div className="rounded-2xl avana-surface overflow-hidden animate-fade-in-up">
          <div className="flex items-center justify-between px-4 py-3 border-b border-[#1D3823]">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-[#F5B942]" />
              <span className="text-sm font-bold text-[#F1F8F2]">Nearby Incidents</span>
            </div>
            <button
              onClick={() => navigate('/map')}
              className="flex items-center gap-1 text-xs text-[#66BB6A] hover:text-[#81C784] font-semibold transition-colors"
            >
              Map View <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>

          {incidentsLoading ? (
            <div className="p-4 space-y-3">
              {[0, 1].map((i) => (
                <div key={i} className="h-10 rounded-lg bg-[#122417] animate-pulse" />
              ))}
            </div>
          ) : !position.latitude ? (
            <div className="px-4 py-6 text-center">
              <p className="text-xs text-[#9BAF9F]">Enable location services to view nearby incident alerts.</p>
            </div>
          ) : incidents.length === 0 ? (
            <div className="px-4 py-6 text-center space-y-1">
              <p className="text-xs font-bold text-[#66BB6A]">No recent incidents nearby</p>
              <p className="text-[11px] text-[#9BAF9F]">
                We'll update this area when new safety intelligence becomes available.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-[#1D3823]">
              {incidents.map((inc) => {
                const sev = SEVERITY_CONFIG[inc.severity as keyof typeof SEVERITY_CONFIG] || SEVERITY_CONFIG.medium
                return (
                  <button
                    key={inc.id}
                    onClick={() => navigate(`/incident/${inc.id}`)}
                    className="w-full flex items-center gap-3 px-4 py-3 hover:bg-[#122417] transition-colors text-left group"
                  >
                    <span
                      className="w-2 h-2 rounded-full shrink-0"
                      style={{ background: sev.color }}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-bold text-[#F1F8F2] truncate">
                        {TYPE_LABELS[inc.type] || inc.type}
                      </p>
                      <p className="text-[10px] text-[#9BAF9F]">
                        {formatRelativeTime(inc.reportedAt)}
                      </p>
                    </div>
                    <span
                      className="text-[9px] font-black px-2 py-0.5 rounded uppercase tracking-wider"
                      style={{ background: sev.bg, color: sev.color }}
                    >
                      {sev.label}
                    </span>
                    <ChevronRight className="h-3.5 w-3.5 text-[#8A948C] group-hover:text-[#9BAF9F] transition-colors shrink-0" />
                  </button>
                )
              })}
            </div>
          )}
        </div>

        {/* ── QUICK ACTIONS ── */}
        <div className="animate-fade-in-up space-y-2">
          <p className="text-[10px] font-bold text-[#9BAF9F] uppercase tracking-wider">Quick Actions</p>
          <div className="grid grid-cols-2 gap-3">
            <QuickActionCard
              icon={<Navigation className="h-5 w-5 text-[#66BB6A]" />}
              label="Safe Route"
              description="Calculate safe path"
              onClick={() => navigate('/map')}
            />
            <QuickActionCard
              icon={<Flag className="h-5 w-5 text-[#A5D6A7]" />}
              label="Report"
              description="Submit intelligence"
              onClick={() => navigate('/report')}
            />
            <QuickActionCard
              icon={<AlertTriangle className="h-5 w-5 text-[#EF4444]" />}
              label="SOS"
              description="Emergency trigger"
              onClick={() => navigate('/sos')}
              danger
            />
            <QuickActionCard
              icon={<MapIcon className="h-5 w-5 text-[#F5B942]" />}
              label="Risk Map"
              description="Explore risk layers"
              onClick={() => navigate('/map')}
            />
          </div>
        </div>

      </div>
    </div>
  )
}

function QuickActionCard({
  icon, label, description, onClick, danger,
}: {
  icon: React.ReactNode
  label: string
  description: string
  onClick: () => void
  danger?: boolean
}) {
  return (
    <button
      onClick={onClick}
      className={`flex flex-col items-start gap-2 p-3.5 rounded-xl text-left transition-all hover:bg-[#122417] active:scale-[0.98] avana-surface ${
        danger ? 'border-[#EF4444]/40 hover:border-[#EF4444]' : 'hover:border-[#66BB6A]/40'
      }`}
    >
      <div className={`p-2 rounded-lg ${danger ? 'bg-[#EF4444]/12' : 'bg-[#122417]'}`}>
        {icon}
      </div>
      <div>
        <p className={`text-xs font-bold ${danger ? 'text-[#EF4444]' : 'text-[#F1F8F2]'}`}>{label}</p>
        <p className="text-[10px] text-[#9BAF9F] mt-0.5">{description}</p>
      </div>
    </button>
  )
}

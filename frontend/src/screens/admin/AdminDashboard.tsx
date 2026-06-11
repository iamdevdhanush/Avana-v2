import * as React from 'react'
import {
  AlertTriangle, Users, Activity, Shield, TrendingUp,
  BarChart3, ChevronRight, Bot, Clock, CheckCircle,
} from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  AreaChart, Area,
  PieChart as RePieChart, Pie, Cell,
} from 'recharts'
import { useNavigate } from 'react-router-dom'
import { adminApi, analyticsApi } from '@/services/api'
import { formatRelativeTime } from '@/lib/utils'
import type { DashboardStats, DistrictAnalytics, CrimeTrend, LastIntelligenceRun } from '@/types'
import { SystemHealthBar } from '@/components/SystemHealthBar'
import { DataFreshness } from '@/components/DataFreshness'

const CHART_COLORS = ['#A855F7', '#EC4899', '#22C55E', '#F59E0B', '#EF4444', '#3B82F6']

const TOOLTIP_STYLE = {
  contentStyle: {
    background: '#1A1A24',
    border: '1px solid #1F2937',
    borderRadius: '10px',
    fontSize: '12px',
    color: '#F9FAFB',
  },
}

export function AdminDashboard() {
  const navigate = useNavigate()
  const [stats, setStats] = React.useState<DashboardStats | null>(null)
  const [districtData, setDistrictData] = React.useState<DistrictAnalytics[]>([])
  const [trends, setTrends] = React.useState<CrimeTrend[]>([])
  const [isLoading, setIsLoading] = React.useState(true)
  const [lastIntelRun, setLastIntelRun] = React.useState<LastIntelligenceRun | null>(null)

  React.useEffect(() => {
    // Read last pipeline run from localStorage (set by IntelligencePipeline after a run)
    const stored = localStorage.getItem('avana_last_intel_run')
    if (stored) {
      try { setLastIntelRun(JSON.parse(stored) as LastIntelligenceRun) } catch { /* ignore */ }
    }
    Promise.all([
      adminApi.getDashboardStats(),
      analyticsApi.getDistrictAnalytics(),
      analyticsApi.getCrimeTrends({ days: 30 }),
    ]).then(([s, d, t]) => {
      setStats(s)
      setDistrictData(d)
      setTrends(t)
    }).catch(() => {}).finally(() => setIsLoading(false))
  }, [])

  const statCards = [
    {
      label: 'Total Incidents',
      value: stats?.totalIncidents ?? 0,
      icon: AlertTriangle,
      color: '#EF4444',
      bg: 'rgba(239,68,68,0.1)',
      border: 'rgba(239,68,68,0.2)',
    },
    {
      label: 'High Risk Zones',
      value: districtData.filter(d => d.highRisk + d.critical > d.total * 0.3).length,
      icon: Shield,
      color: '#F59E0B',
      bg: 'rgba(245,158,11,0.1)',
      border: 'rgba(245,158,11,0.2)',
    },
    {
      label: 'Reports Pending',
      value: stats?.activeIncidents ?? 0,
      icon: Activity,
      color: '#A855F7',
      bg: 'rgba(168,85,247,0.1)',
      border: 'rgba(168,85,247,0.2)',
    },
    {
      label: 'Active Users',
      value: stats?.activeUsers ?? 0,
      icon: Users,
      color: '#22C55E',
      bg: 'rgba(34,197,94,0.1)',
      border: 'rgba(34,197,94,0.2)',
    },
  ]

  const incidentsByType = stats?.incidentsByType
    ? Object.entries(stats.incidentsByType).map(([name, value]) => ({ name, value }))
    : []

  const barData = districtData.slice(0, 8).map((d) => ({
    name: d.district.length > 8 ? d.district.slice(0, 8) + '…' : d.district,
    High: d.highRisk + d.critical,
    Medium: d.mediumRisk,
    Low: d.lowRisk,
  }))

  // Compute last AI run info from dashboard (derived)
  const lastRunInfo = stats
    ? {
        verifiedCount: stats.activeIncidents,
        totalProcessed: stats.totalIncidents,
        confidenceRate: stats.totalIncidents > 0
          ? Math.round((stats.activeIncidents / stats.totalIncidents) * 100)
          : 0,
      }
    : null

  return (
    <div
      className="min-h-full pb-safe"
      style={{ background: '#09090B' }}
    >
      <div className="max-w-6xl mx-auto px-4 md:px-6 py-6 space-y-6">

        {/* System Health Bar */}
        <SystemHealthBar />

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-black text-[#F9FAFB]">Admin Dashboard</h1>
            <p className="text-sm text-[#6B7280] mt-0.5">Safety platform intelligence overview</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => navigate('/admin/incidents')}
              className="px-3 py-2 rounded-xl text-xs font-semibold transition-all"
              style={{ background: '#1A1A24', border: '1px solid #1F2937', color: '#D1D5DB' }}
            >
              Moderate
            </button>
            <button
              onClick={() => navigate('/admin/pipeline')}
              className="px-3 py-2 rounded-xl text-xs font-semibold transition-all"
              style={{
                background: 'linear-gradient(135deg, #A855F7 0%, #9333EA 100%)',
                color: '#fff',
              }}
            >
              Run Pipeline
            </button>
          </div>
        </div>

        {/* Stat Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {isLoading
            ? Array.from({ length: 4 }).map((_, i) => (
                <div
                  key={i}
                  className="rounded-2xl p-5 h-28 animate-shimmer"
                  style={{ background: '#1A1A24', border: '1px solid #1F2937' }}
                />
              ))
            : statCards.map((stat) => (
                <div
                  key={stat.label}
                  className="rounded-2xl p-5 transition-all hover:scale-[1.02]"
                  style={{ background: stat.bg, border: `1px solid ${stat.border}` }}
                >
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-xs text-[#6B7280] font-medium">{stat.label}</p>
                    <div
                      className="w-8 h-8 rounded-xl flex items-center justify-center"
                      style={{ background: `${stat.color}18` }}
                    >
                      <stat.icon className="h-4 w-4" style={{ color: stat.color }} />
                    </div>
                  </div>
                  <p className="text-3xl font-black" style={{ color: stat.color }}>
                    {isLoading ? '—' : stat.value.toLocaleString()}
                  </p>
                </div>
              ))}
        </div>

        {/* Charts row */}
        <div className="grid gap-4 md:grid-cols-3">
          {/* Bar: Incidents by District */}
          <div
            className="md:col-span-2 rounded-2xl p-5"
            style={{ background: '#1A1A24', border: '1px solid #1F2937' }}
          >
            <div className="flex items-center gap-2 mb-4">
              <BarChart3 className="h-4 w-4 text-[#A855F7]" />
              <h2 className="text-sm font-bold text-[#F9FAFB]">Incidents by District</h2>
            </div>
            <div className="h-[260px]">
              {barData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={barData} barGap={2} barSize={8}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" vertical={false} />
                    <XAxis dataKey="name" tick={{ fill: '#6B7280', fontSize: 10 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: '#6B7280', fontSize: 10 }} axisLine={false} tickLine={false} />
                    <Tooltip {...TOOLTIP_STYLE} />
                    <Bar dataKey="High" fill="#EF4444" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="Medium" fill="#F59E0B" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="Low" fill="#22C55E" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center text-sm text-[#6B7280]">
                  No district data available
                </div>
              )}
            </div>
          </div>

          {/* Pie: By Type */}
          <div
            className="rounded-2xl p-5"
            style={{ background: '#1A1A24', border: '1px solid #1F2937' }}
          >
            <div className="flex items-center gap-2 mb-4">
              <Activity className="h-4 w-4 text-[#EC4899]" />
              <h2 className="text-sm font-bold text-[#F9FAFB]">By Type</h2>
            </div>
            <div className="h-[200px]">
              {incidentsByType.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <RePieChart>
                    <Pie
                      data={incidentsByType}
                      cx="50%" cy="50%"
                      innerRadius={55} outerRadius={80}
                      paddingAngle={3}
                      dataKey="value"
                    >
                      {incidentsByType.map((_, i) => (
                        <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip {...TOOLTIP_STYLE} />
                  </RePieChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center text-sm text-[#6B7280]">No data</div>
              )}
            </div>
            <div className="flex flex-wrap gap-x-3 gap-y-1.5 mt-2">
              {incidentsByType.slice(0, 5).map((entry, i) => (
                <div key={entry.name} className="flex items-center gap-1.5 text-[10px]">
                  <div className="w-2 h-2 rounded-full" style={{ background: CHART_COLORS[i % CHART_COLORS.length] }} />
                  <span className="text-[#9CA3AF] capitalize">{entry.name.replace(/_/g, ' ')}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 30-Day Trend */}
        <div
          className="rounded-2xl p-5"
          style={{ background: '#1A1A24', border: '1px solid #1F2937' }}
        >
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="h-4 w-4 text-[#A855F7]" />
            <h2 className="text-sm font-bold text-[#F9FAFB]">30-Day Incident Trend</h2>
          </div>
          <div className="h-[200px]">
            {trends.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trends}>
                  <defs>
                    <linearGradient id="purpleGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#A855F7" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#A855F7" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: '#6B7280', fontSize: 10 }}
                    axisLine={false} tickLine={false}
                    tickFormatter={(val) => {
                      const d = new Date(val)
                      return `${d.getDate()}/${d.getMonth() + 1}`
                    }}
                  />
                  <YAxis tick={{ fill: '#6B7280', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <Tooltip {...TOOLTIP_STYLE} />
                  <Area
                    type="monotone"
                    dataKey="count"
                    stroke="#A855F7"
                    strokeWidth={2}
                    fill="url(#purpleGrad)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-[#6B7280]">No trend data</div>
            )}
          </div>
        </div>

        {/* Bottom row */}
        <div className="grid gap-4 md:grid-cols-2">
          {/* Recent Reports */}
          <div
            className="rounded-2xl overflow-hidden"
            style={{ background: '#1A1A24', border: '1px solid #1F2937' }}
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-[#1F2937]">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-[#EF4444]" />
                <h2 className="text-sm font-bold text-[#F9FAFB]">Recent Alerts</h2>
              </div>
              <button
                onClick={() => navigate('/admin/incidents')}
                className="flex items-center gap-1 text-xs text-[#A855F7] font-medium"
              >
                View All <ChevronRight className="h-3 w-3" />
              </button>
            </div>
            <div className="divide-y divide-[#1F2937]">
              {isLoading ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="px-5 py-3 flex gap-3">
                    <div className="flex-1 h-4 rounded bg-[#111827] animate-shimmer" />
                  </div>
                ))
              ) : (stats?.recentIncidents?.length ?? 0) > 0 ? (
                stats!.recentIncidents.slice(0, 8).map((inc) => {
                  const sevColor =
                    inc.severity === 'critical' ? '#7C3AED' :
                    inc.severity === 'high' ? '#EF4444' :
                    inc.severity === 'medium' ? '#F59E0B' : '#22C55E'
                  return (
                    <div key={inc.id} className="flex items-center gap-3 px-5 py-3">
                      <div
                        className="w-2 h-2 rounded-full shrink-0"
                        style={{ background: sevColor }}
                      />
                      <span className="flex-1 text-sm text-[#F9FAFB] capitalize truncate">
                        {inc.type.replace(/_/g, ' ')}
                      </span>
                      <span
                        className="text-[10px] font-semibold px-2 py-0.5 rounded-full shrink-0 capitalize"
                        style={{ background: `${sevColor}18`, color: sevColor }}
                      >
                        {inc.severity}
                      </span>
                      <span className="text-[10px] text-[#6B7280] shrink-0">
                        {formatRelativeTime(inc.reportedAt)}
                      </span>
                    </div>
                  )
                })
              ) : (
                <div className="px-5 py-6 text-center text-sm text-[#6B7280]">No recent alerts</div>
              )}
            </div>
          </div>

          {/* Intelligence Pipeline — real last run data */}
          <div
            className="rounded-2xl p-5"
            style={{ background: '#1A1A24', border: '1px solid rgba(168,85,247,0.2)' }}
          >
            <div className="flex items-center gap-2 mb-4">
              <Bot className="h-4 w-4 text-[#A855F7]" />
              <h2 className="text-sm font-bold text-[#F9FAFB]">Intelligence Pipeline</h2>
            </div>

            {lastIntelRun ? (
              <div className="space-y-3">
                <div className="grid grid-cols-3 gap-2">
                  <div className="rounded-xl px-3 py-2.5 text-center" style={{ background: '#111827' }}>
                    <p className="text-xl font-black text-[#A855F7]">{lastIntelRun.incidentsSaved}</p>
                    <p className="text-[10px] text-[#6B7280]">Saved</p>
                  </div>
                  <div className="rounded-xl px-3 py-2.5 text-center" style={{ background: '#111827' }}>
                    <p className="text-xl font-black text-[#22C55E]">
                      {lastIntelRun.durationSeconds != null ? `${Math.round(lastIntelRun.durationSeconds)}s` : '—'}
                    </p>
                    <p className="text-[10px] text-[#6B7280]">Duration</p>
                  </div>
                  <div className="rounded-xl px-3 py-2.5 text-center" style={{ background: '#111827' }}>
                    <p className="text-xl font-black" style={{ color: lastIntelRun.errors?.length ? '#EF4444' : '#22C55E' }}>
                      {lastIntelRun.errors?.length || 0}
                    </p>
                    <p className="text-[10px] text-[#6B7280]">Errors</p>
                  </div>
                </div>
                <DataFreshness timestamp={lastIntelRun.ranAt} label="Last Run" warnAfterHours={24} />
                <button
                  onClick={() => navigate('/admin/pipeline')}
                  className="w-full py-2.5 rounded-xl text-xs font-bold text-[#A855F7] border border-[#A855F7]/30 hover:bg-[#A855F7]/10 transition-colors"
                >
                  Manage Pipeline →
                </button>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-40 text-center">
                <Clock className="h-10 w-10 text-[#374151] mb-3" />
                <p className="text-sm font-semibold text-[#6B7280]">Intelligence Pipeline Has Not Run Yet</p>
                <p className="text-xs text-[#374151] mt-1">No pipeline runs recorded.</p>
                <button
                  onClick={() => navigate('/admin/pipeline')}
                  className="mt-3 px-4 py-2 rounded-xl text-xs font-semibold text-[#A855F7] border border-[#A855F7]/30"
                >
                  Run Pipeline Now
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

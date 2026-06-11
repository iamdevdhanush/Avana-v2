/**
 * AdminAgents — Intelligence Pipeline Dashboard
 *
 * Loads real agent statuses from GET /admin/agents/status
 * Triggers real runs via POST /admin/agents/run/{agent_name}
 * Displays real results. Zero mock data.
 *
 * Valid runnable agents: news, community, heatmap
 */
import * as React from 'react'
import {
  Activity, Play, RefreshCw, Loader2, CheckCircle, XCircle,
  Clock, BarChart3, AlertTriangle, Newspaper, Users, MapPin, Bot,
} from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { adminApi } from '@/services/api'
import type { PipelineName } from '@/services/api'
import type { AgentStatus, PipelineRunResult } from '@/types'
import { SystemHealthBar } from '@/components/SystemHealthBar'

// Map backend agent names to display info
const AGENT_META: Record<string, {
  label: string
  description: string
  icon: React.ComponentType<{ className?: string }>
  runnableName: PipelineName | null
  color: string
}> = {
  news_intelligence: {
    label: 'News Intelligence',
    description: 'Fetches RSS feeds, extracts incidents via Gemini AI, geocodes locations',
    icon: Newspaper,
    runnableName: 'news',
    color: '#A855F7',
  },
  community_intelligence: {
    label: 'Community Intelligence',
    description: 'Processes community reports and cross-references with known incidents',
    icon: Users,
    runnableName: 'community',
    color: '#EC4899',
  },
  heatmap: {
    label: 'Heatmap Engine',
    description: 'Recalculates risk scores and regenerates heatmap grid cells',
    icon: MapPin,
    runnableName: 'heatmap',
    color: '#F59E0B',
  },
  risk_scoring: {
    label: 'Risk Scoring',
    description: 'Calculates safety risk scores for locations (on-demand)',
    icon: BarChart3,
    runnableName: null,
    color: '#22C55E',
  },
  route_intelligence: {
    label: 'Route Intelligence',
    description: 'Safe routing via OSRM + risk layer (on-demand)',
    icon: Activity,
    runnableName: null,
    color: '#3B82F6',
  },
  safety_recommendation: {
    label: 'Safety Recommendations',
    description: 'Generates safety tips based on current area conditions (on-demand)',
    icon: CheckCircle,
    runnableName: null,
    color: '#6B7280',
  },
}

const STATUS_CONFIG = {
  idle:      { label: 'Idle',      color: '#6B7280', bg: 'rgba(107,114,128,0.12)' },
  running:   { label: 'Running',   color: '#F59E0B', bg: 'rgba(245,158,11,0.12)' },
  available: { label: 'Available', color: '#22C55E', bg: 'rgba(34,197,94,0.12)' },
}

function formatDuration(secs: number): string {
  if (secs < 60) return `${secs.toFixed(1)}s`
  const m = Math.floor(secs / 60)
  const s = Math.round(secs % 60)
  return `${m}m ${s}s`
}

function RunResultCard({ result, onDismiss }: { result: PipelineRunResult; onDismiss: () => void }) {
  const hasErrors = result.errors && result.errors.length > 0
  const isSuccess = result.status === 'completed' && !hasErrors

  return (
    <div
      className="rounded-xl p-4 border"
      style={{
        background: isSuccess ? 'rgba(34,197,94,0.05)' : 'rgba(239,68,68,0.05)',
        borderColor: isSuccess ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)',
      }}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          {isSuccess ? (
            <CheckCircle className="h-4 w-4 text-[#22C55E]" />
          ) : (
            <XCircle className="h-4 w-4 text-[#EF4444]" />
          )}
          <span className="text-sm font-bold text-[#F9FAFB]">
            {result.agent} — {result.status}
          </span>
        </div>
        <button
          onClick={onDismiss}
          className="text-[10px] text-[#6B7280] hover:text-[#9CA3AF] transition-colors"
        >
          Dismiss
        </button>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-3">
        <div className="text-center">
          <p className="text-lg font-black" style={{ color: '#22C55E' }}>
            {result.incidentsSaved ?? '—'}
          </p>
          <p className="text-[10px] text-[#6B7280]">Incidents Saved</p>
        </div>
        <div className="text-center">
          <p className="text-lg font-black text-[#A855F7]">
            {result.articlesProcessed ?? '—'}
          </p>
          <p className="text-[10px] text-[#6B7280]">Articles Processed</p>
        </div>
        <div className="text-center">
          <p className="text-lg font-black text-[#F9FAFB]">
            {result.durationSeconds != null ? formatDuration(result.durationSeconds) : '—'}
          </p>
          <p className="text-[10px] text-[#6B7280]">Duration</p>
        </div>
      </div>

      {hasErrors && (
        <div className="mt-2 space-y-1">
          {result.errors!.slice(0, 3).map((err, i) => (
            <div key={i} className="flex items-start gap-1.5 text-[11px] text-[#EF4444]">
              <AlertTriangle className="h-3 w-3 shrink-0 mt-0.5" />
              <span className="break-all">{err as string}</span>
            </div>
          ))}
          {result.errors!.length > 3 && (
            <p className="text-[11px] text-[#6B7280]">+{result.errors!.length - 3} more errors</p>
          )}
        </div>
      )}

      <p className="text-[10px] text-[#4B5563] mt-2">
        Ran at: {new Date(result.ranAt).toLocaleString()}
      </p>
    </div>
  )
}

export function AdminAgents() {
  const queryClient = useQueryClient()
  const [runResults, setRunResults] = React.useState<Map<string, PipelineRunResult>>(new Map())

  // Load existing last run from localStorage on mount
  React.useEffect(() => {
    const stored = localStorage.getItem('avana_last_intel_run')
    if (stored) {
      try {
        const parsed = JSON.parse(stored) as PipelineRunResult
        setRunResults((prev) => new Map(prev).set(parsed.agent, parsed))
      } catch { /* ignore */ }
    }
  }, [])

  const { data: agents, isLoading, isError, refetch } = useQuery({
    queryKey: ['agent-status'],
    queryFn: () => adminApi.getAgentStatus(),
    refetchInterval: 30_000,
    staleTime: 25_000,
    retry: 2,
  })

  const runMutation = useMutation({
    mutationFn: (name: PipelineName) => adminApi.runAgent(name),
    onSuccess: (result) => {
      setRunResults((prev) => new Map(prev).set(result.agent, result))
      // Refresh agent status after run
      queryClient.invalidateQueries({ queryKey: ['agent-status'] })
    },
  })

  const dismissResult = (agentName: string) => {
    setRunResults((prev) => {
      const next = new Map(prev)
      next.delete(agentName)
      return next
    })
  }

  return (
    <div className="min-h-full" style={{ background: '#09090B' }}>
      <div className="max-w-4xl mx-auto px-4 md:px-6 py-6 space-y-5">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-black text-[#F9FAFB]">Intelligence Pipeline</h1>
            <p className="text-sm text-[#6B7280] mt-0.5">
              Monitor and trigger AI agent pipeline runs
            </p>
          </div>
          <button
            onClick={() => refetch()}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold transition-all"
            style={{ background: '#1A1A24', border: '1px solid #1F2937', color: '#D1D5DB' }}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* System Health */}
        <SystemHealthBar />

        {/* Error state */}
        {isError && (
          <div
            className="flex items-center gap-3 px-4 py-3 rounded-xl"
            style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)' }}
          >
            <AlertTriangle className="h-4 w-4 text-[#EF4444] shrink-0" />
            <div>
              <p className="text-sm font-semibold text-[#EF4444]">Could not load agent status</p>
              <p className="text-xs text-[#6B7280] mt-0.5">
                Verify the backend is running and you have admin access.
              </p>
            </div>
            <button
              onClick={() => refetch()}
              className="ml-auto text-xs text-[#EF4444] font-medium shrink-0"
            >
              Retry
            </button>
          </div>
        )}

        {/* Loading shimmer */}
        {isLoading && (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="rounded-2xl p-5 h-28 animate-pulse"
                style={{ background: '#1A1A24', border: '1px solid #1F2937' }}
              />
            ))}
          </div>
        )}

        {/* Agent cards — real data only */}
        {!isLoading && agents && agents.length === 0 && (
          <div
            className="flex flex-col items-center justify-center py-16 text-center rounded-2xl"
            style={{ background: '#1A1A24', border: '1px solid #1F2937' }}
          >
            <Bot className="h-12 w-12 text-[#374151] mb-3" />
            <p className="text-sm font-semibold text-[#6B7280]">No Agents Returned</p>
            <p className="text-xs text-[#374151] mt-1">
              The backend returned an empty agent list.
            </p>
          </div>
        )}

        {!isLoading && agents && agents.map((agent: AgentStatus) => {
          const meta = AGENT_META[agent.name] || {
            label: agent.name,
            description: 'Agent',
            icon: Bot,
            runnableName: null,
            color: '#6B7280',
          }
          const statusCfg = STATUS_CONFIG[agent.status as keyof typeof STATUS_CONFIG] || STATUS_CONFIG.idle
          const isRunning = runMutation.isPending && runMutation.variables === meta.runnableName
          const runResult = runResults.get(agent.name) ?? runResults.get(meta.runnableName ?? '')

          const Icon = meta.icon

          return (
            <div
              key={agent.name}
              className="rounded-2xl p-5 space-y-4"
              style={{ background: '#1A1A24', border: '1px solid #1F2937' }}
            >
              {/* Agent header */}
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-3">
                  <div
                  className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
                  style={{ background: `${meta.color}18` }}
                >
                  <span style={{ color: meta.color }}><Icon className="h-4 w-4" /></span>
                  </div>
                  <div>
                    <p className="text-sm font-bold text-[#F9FAFB]">{meta.label}</p>
                    <p className="text-xs text-[#6B7280] mt-0.5">{meta.description}</p>
                  </div>
                </div>

                {/* Status badge */}
                <div
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold shrink-0"
                  style={{ background: statusCfg.bg, color: statusCfg.color }}
                >
                  {agent.status === 'running' && <Activity className="h-3 w-3 animate-pulse" />}
                  {agent.status === 'idle' && <Clock className="h-3 w-3" />}
                  {agent.status === 'available' && <CheckCircle className="h-3 w-3" />}
                  {statusCfg.label}
                </div>
              </div>

              {/* Schedule info */}
              <div className="flex items-center gap-4 text-xs text-[#6B7280]">
                {agent.scheduledMinutes != null ? (
                  <span>
                    Schedule: every{' '}
                    <span className="text-[#9CA3AF] font-medium">
                      {agent.scheduledMinutes >= 60
                        ? `${agent.scheduledMinutes / 60}h`
                        : `${agent.scheduledMinutes}min`}
                    </span>
                  </span>
                ) : (
                  <span className="text-[#4B5563]">On-demand only</span>
                )}
              </div>

              {/* Last run result (if available) */}
              {runResult && (
                <RunResultCard result={runResult} onDismiss={() => dismissResult(agent.name)} />
              )}

              {/* Run button — only for triggerable agents */}
              {meta.runnableName && (
                <button
                  onClick={() => {
                    if (meta.runnableName) runMutation.mutate(meta.runnableName)
                  }}
                  disabled={isRunning || runMutation.isPending}
                  className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-xs font-bold transition-all"
                  style={
                    isRunning || runMutation.isPending
                      ? { background: '#1F2937', color: '#6B7280', cursor: 'not-allowed' }
                      : {
                          background: `linear-gradient(135deg, ${meta.color} 0%, ${meta.color}cc 100%)`,
                          color: '#fff',
                          boxShadow: `0 4px 16px ${meta.color}30`,
                        }
                  }
                >
                  {isRunning ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Running Pipeline…
                    </>
                  ) : (
                    <>
                      <Play className="h-3.5 w-3.5" />
                      Run {meta.label}
                    </>
                  )}
                </button>
              )}

              {!meta.runnableName && (
                <p className="text-xs text-[#4B5563] text-center py-1">
                  This agent runs automatically on-demand — no manual trigger available.
                </p>
              )}
            </div>
          )
        })}

        {/* No data yet message */}
        {!isLoading && !isError && agents && agents.length > 0 && (
          <p className="text-[11px] text-center text-[#374151]">
            Agent data refreshes every 30 seconds. Last pipeline runs are stored locally.
          </p>
        )}
      </div>
    </div>
  )
}

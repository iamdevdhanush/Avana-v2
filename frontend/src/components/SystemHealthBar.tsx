/**
 * SystemHealthBar — polls backend health endpoints every 60s.
 * Shows: Backend, Route Engine, Gemini AI status with color indicators.
 * Renders as a compact strip in the admin layout.
 */
import * as React from 'react'
import { useQuery } from '@tanstack/react-query'
import { healthApi } from '@/services/api'
import type { ServiceHealth, HealthStatus } from '@/types'
import { Activity, Wifi, WifiOff, AlertTriangle } from 'lucide-react'

const STATUS_COLOR: Record<HealthStatus, { dot: string; text: string; bg: string }> = {
  healthy:  { dot: '#22C55E', text: '#22C55E', bg: 'rgba(34,197,94,0.10)' },
  degraded: { dot: '#F59E0B', text: '#F59E0B', bg: 'rgba(245,158,11,0.10)' },
  offline:  { dot: '#EF4444', text: '#EF4444', bg: 'rgba(239,68,68,0.10)' },
}

function ServiceChip({ service }: { service: ServiceHealth }) {
  const cfg = STATUS_COLOR[service.status]
  return (
    <div
      className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium"
      style={{ background: cfg.bg, border: `1px solid ${cfg.dot}25` }}
    >
      <div
        className="w-1.5 h-1.5 rounded-full shrink-0"
        style={{
          background: cfg.dot,
          boxShadow: service.status === 'healthy' ? `0 0 4px ${cfg.dot}80` : 'none',
        }}
      />
      <span style={{ color: '#D1D5DB' }}>{service.name}</span>
      <span style={{ color: cfg.text }} className="font-semibold capitalize">
        {service.status === 'healthy' ? 'OK' : service.status}
      </span>
      {service.responseMs != null && service.status !== 'offline' && (
        <span style={{ color: '#6B7280' }} className="text-[10px]">
          {service.responseMs}ms
        </span>
      )}
    </div>
  )
}

interface SystemHealthBarProps {
  /** If true, renders in a compact inline format */
  compact?: boolean
}

export function SystemHealthBar({ compact = false }: SystemHealthBarProps) {
  const { data: health, isLoading, dataUpdatedAt } = useQuery({
    queryKey: ['system-health'],
    queryFn: () => healthApi.getSystemHealth(),
    refetchInterval: 60_000,        // poll every 60 seconds
    staleTime: 55_000,
    retry: 1,
  })

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 rounded-xl"
        style={{ background: '#1A1A24', border: '1px solid #1F2937' }}>
        <Activity className="h-3.5 w-3.5 text-[#6B7280] animate-pulse" />
        <span className="text-xs text-[#6B7280]">Checking system health…</span>
      </div>
    )
  }

  if (!health) return null

  const allHealthy = [health.backend, health.routeEngine, health.aiService].every(
    (s) => s.status === 'healthy'
  )
  const anyOffline = [health.backend, health.routeEngine, health.aiService].some(
    (s) => s.status === 'offline'
  )

  const lastChecked = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : '—'

  if (compact) {
    return (
      <div className="flex items-center gap-1.5">
        <div
          className="w-2 h-2 rounded-full"
          style={{
            background: allHealthy ? '#22C55E' : anyOffline ? '#EF4444' : '#F59E0B',
            boxShadow: allHealthy ? '0 0 6px #22C55E80' : 'none',
          }}
        />
        <span className="text-[11px] font-medium" style={{ color: allHealthy ? '#22C55E' : anyOffline ? '#EF4444' : '#F59E0B' }}>
          {allHealthy ? 'All Systems Operational' : anyOffline ? 'Service Offline' : 'Degraded'}
        </span>
      </div>
    )
  }

  return (
    <div
      className="rounded-xl p-3"
      style={{ background: '#0F0F17', border: '1px solid #1F2937' }}
    >
      <div className="flex items-center justify-between mb-2.5">
        <div className="flex items-center gap-1.5">
          {anyOffline ? (
            <WifiOff className="h-3.5 w-3.5 text-[#EF4444]" />
          ) : allHealthy ? (
            <Wifi className="h-3.5 w-3.5 text-[#22C55E]" />
          ) : (
            <AlertTriangle className="h-3.5 w-3.5 text-[#F59E0B]" />
          )}
          <span className="text-xs font-semibold text-[#F9FAFB]">System Health</span>
        </div>
        <span className="text-[10px] text-[#4B5563]">
          Last check: {lastChecked}
        </span>
      </div>
      <div className="flex flex-wrap gap-2">
        <ServiceChip service={health.backend} />
        <ServiceChip service={health.routeEngine} />
        <ServiceChip service={health.aiService} />
      </div>
    </div>
  )
}

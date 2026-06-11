/**
 * DataFreshness — shows when data was last updated and warns if stale.
 *
 * Props:
 *   timestamp     — ISO string from the backend, or null if never updated
 *   label         — e.g. "Heatmap", "Intelligence"
 *   warnAfterHours — warn if older than N hours (default 48)
 *   compact       — render inline chip instead of full row
 */
import * as React from 'react'
import { Clock, AlertTriangle } from 'lucide-react'

interface DataFreshnessProps {
  timestamp: string | null | undefined
  label?: string
  warnAfterHours?: number
  compact?: boolean
  className?: string
}

function formatAge(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
}

function isStale(iso: string, warnAfterHours: number): boolean {
  const diff = Date.now() - new Date(iso).getTime()
  return diff > warnAfterHours * 3600_000
}

export function DataFreshness({
  timestamp,
  label = 'Data',
  warnAfterHours = 48,
  compact = false,
  className = '',
}: DataFreshnessProps) {
  if (!timestamp) {
    if (compact) {
      return (
        <span
          className={`inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full ${className}`}
          style={{ background: 'rgba(107,114,128,0.15)', color: '#6B7280' }}
        >
          <Clock className="h-3 w-3" />
          Never Updated
        </span>
      )
    }
    return (
      <div className={`flex items-center gap-1.5 text-xs text-[#6B7280] ${className}`}>
        <Clock className="h-3.5 w-3.5 shrink-0" />
        <span>{label}: <span className="font-medium text-[#4B5563]">Never Updated</span></span>
      </div>
    )
  }

  const stale = isStale(timestamp, warnAfterHours)
  const age = formatAge(timestamp)

  if (compact) {
    return (
      <span
        className={`inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full ${className}`}
        style={{
          background: stale ? 'rgba(245,158,11,0.12)' : 'rgba(34,197,94,0.10)',
          color: stale ? '#F59E0B' : '#6B7280',
        }}
      >
        {stale ? <AlertTriangle className="h-3 w-3" /> : <Clock className="h-3 w-3" />}
        {stale ? 'May Be Outdated' : age}
      </span>
    )
  }

  return (
    <div className={`flex items-center gap-1.5 text-xs ${className}`} style={{ color: stale ? '#F59E0B' : '#6B7280' }}>
      {stale ? (
        <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-[#F59E0B]" />
      ) : (
        <Clock className="h-3.5 w-3.5 shrink-0" />
      )}
      <span>
        {label}: <span className="font-medium" style={{ color: stale ? '#F59E0B' : '#9CA3AF' }}>{age}</span>
        {stale && (
          <span className="ml-1.5 text-[10px] px-1.5 py-0.5 rounded-full font-semibold"
            style={{ background: 'rgba(245,158,11,0.15)', color: '#F59E0B' }}>
            May Be Outdated
          </span>
        )}
      </span>
    </div>
  )
}

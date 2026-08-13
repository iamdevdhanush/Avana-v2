import * as React from 'react'
import { X, Navigation, MapPin, ExternalLink, Shield, Clock, Building2, Newspaper } from 'lucide-react'
import { useMapStore } from '@/store/mapStore'
import { useLocationName } from '@/hooks/useLocationName'
import { riskApi } from '@/services/api'
import type { ExplainResponse, ExplainSourceItem } from '@/types'

function isUnknown(category?: string): boolean {
  return category?.toLowerCase() === 'unknown'
}

function getRiskColor(s: number, category?: string): string {
  if (isUnknown(category)) return '#8A948C'
  if (s >= 75) return '#EF4444'
  if (s >= 50) return '#F97316'
  if (s >= 25) return '#F5B942'
  return '#66BB6A'
}

function getRiskLabel(s: number, category?: string): string {
  if (isUnknown(category)) return 'UNKNOWN'
  if (s >= 75) return 'HIGH RISK'
  if (s >= 50) return 'ELEVATED RISK'
  if (s >= 25) return 'MODERATE RISK'
  return 'LOWER RISK'
}

const severityBadge: Record<string, string> = {
  CRITICAL: '#EF4444',
  HIGH: '#EF4444',
  MEDIUM: '#F5B942',
  LOW: '#66BB6A',
}

const sourceLabel: Record<string, string> = {
  NEWS: 'News Article',
  POLICE: 'Police Record',
  USER_REPORT: 'User Report',
  COMMUNITY_REPORT: 'Community Report',
  SOS: 'SOS Alert',
  SYSTEM: 'System',
}

function formatDate(dateStr: string): string {
  if (!dateStr) return 'Unknown'
  if (/^\d{4}$/.test(dateStr)) return dateStr
  try {
    const d = new Date(dateStr)
    if (isNaN(d.getTime())) return dateStr
    return d.toLocaleDateString('en-IN', { year: 'numeric', month: 'short', day: 'numeric' })
  } catch {
    return dateStr
  }
}

function isValidUrl(s: string): boolean {
  try {
    const u = new URL(s)
    return u.protocol === 'http:' || u.protocol === 'https:'
  } catch {
    return false
  }
}

function SourceCard({ item }: { item: ExplainSourceItem }) {
  const sevColor = severityBadge[item.severity] || '#8A948C'
  const distText = item.distance_meters < 1000
    ? `${Math.round(item.distance_meters)}m`
    : `${(item.distance_meters / 1000).toFixed(1)}km`

  return (
    <div
      className="rounded-xl px-3 py-2.5 bg-[#122417] border border-[#1D3823]"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-1">
            <span
              className="text-[9px] font-extrabold px-1.5 py-0.5 rounded"
              style={{ background: `${sevColor}20`, color: sevColor }}
            >
              {item.severity}
            </span>
            <span className="text-[10px] text-[#9BAF9F] font-semibold capitalize">
              {item.incident_type.replace(/_/g, ' ').toLowerCase()}
            </span>
          </div>
          {item.title && (
            <p className="text-[11px] text-[#F1F8F2] font-medium leading-relaxed mb-1">{item.title}</p>
          )}
          <div className="flex items-center gap-2 text-[9px] text-[#8A948C] flex-wrap">
            <span className="flex items-center gap-1">
              <MapPin className="h-2.5 w-2.5" />
              {distText}
            </span>
            <span>·</span>
            <span>{formatDate(item.date)}</span>
            <span>·</span>
            <span className="capitalize">{sourceLabel[item.source] || item.source.toLowerCase()}</span>
          </div>

          {item.source === 'NEWS' && item.publisher && (
            <div className="flex items-center gap-1 mt-1 text-[9px] text-[#8A948C]">
              <Newspaper className="h-2.5 w-2.5" />
              <span>{item.publisher}</span>
            </div>
          )}

          {item.source === 'POLICE' && item.dataset_name && (
            <div className="flex items-center gap-1 mt-1 text-[9px] text-[#8A948C]">
              <Building2 className="h-2.5 w-2.5" />
              <span className="truncate">{item.dataset_name}</span>
              {item.dataset_district && <span>· {item.dataset_district}</span>}
            </div>
          )}
        </div>
      </div>

      {item.source_url && isValidUrl(item.source_url) && (
        <a
          href={item.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 flex items-center gap-1 text-[10px] font-semibold text-[#66BB6A] hover:underline"
          onClick={(e) => e.stopPropagation()}
        >
          <ExternalLink className="h-3 w-3" />
          View Source
        </a>
      )}
    </div>
  )
}

interface RiskIntelligencePanelProps {
  onGetSafeRoute?: () => void
  onClose?: () => void
}

export function RiskIntelligencePanel({ onGetSafeRoute, onClose }: RiskIntelligencePanelProps) {
  const { selectedLocation, setSelectedLocation } = useMapStore()
  const [explain, setExplain] = React.useState<ExplainResponse | null>(null)
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const locationName = useLocationName(selectedLocation?.lat, selectedLocation?.lng)

  React.useEffect(() => {
    if (!selectedLocation) return
    setIsLoading(true)
    setError(null)
    riskApi.explainScore(selectedLocation.lat, selectedLocation.lng)
      .then(setExplain)
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false))
  }, [selectedLocation])

  if (!selectedLocation) return null

  const score = explain?.risk_score ?? 0
  const rawCategory = explain?.risk_category ?? ''
  const category = getRiskLabel(score, rawCategory)
  const riskColor = getRiskColor(score, rawCategory)
  const incidentCount = explain?.incident_count ?? 0
  const sources = explain?.sources ?? []

  const handleClose = () => {
    setSelectedLocation(null)
    onClose?.()
  }

  return (
    <div className="absolute bottom-0 left-0 right-0 z-[1000]" style={{ maxHeight: '80vh' }}>
      <div
        className="rounded-t-2xl overflow-y-auto avana-surface border-t border-[#1D3823]"
        style={{
          background: '#0D1A10',
          backdropFilter: 'blur(20px)',
          maxHeight: '80vh',
        }}
      >
        <div className="flex justify-center pt-2 pb-1 sticky top-0 z-10 bg-[#0D1A10]">
          <div className="w-10 h-1 rounded-full bg-[#1D3823]" />
        </div>

        <div className="flex items-center justify-between px-4 pb-2">
          <div className="flex items-center gap-1.5 min-w-0 flex-1">
            <MapPin className="h-3.5 w-3.5 shrink-0 text-[#66BB6A]" />
            <span className="text-xs font-semibold text-[#F1F8F2] truncate">
              {locationName.isLoading ? 'Detecting location...' : (locationName.displayName || `${selectedLocation.lat.toFixed(4)}, ${selectedLocation.lng.toFixed(4)}`)}
            </span>
          </div>
          <button onClick={handleClose} className="rounded-lg p-1 hover:bg-[#122417] transition-colors shrink-0 ml-2">
            <X className="h-4 w-4 text-[#8A948C]" />
          </button>
        </div>

        <div className="px-4 pb-4 space-y-3">
          {isLoading ? (
            <div className="flex items-center gap-3 py-4">
              <div className="h-14 w-14 rounded-full bg-[#122417] animate-pulse" />
              <div className="space-y-2 flex-1">
                <div className="h-3 w-20 bg-[#122417] rounded animate-pulse" />
                <div className="h-5 w-28 bg-[#122417] rounded-full animate-pulse" />
              </div>
            </div>
          ) : error ? (
            <div className="px-3 py-2 rounded-xl text-xs bg-[#EF4444]/10 border border-[#EF4444]/20 text-[#EF4444]">
              {error}
            </div>
          ) : (
            <>
              <div className="flex items-center gap-4">
                <div className="relative shrink-0">
                  <svg className="h-16 w-16 -rotate-90" viewBox="0 0 68 68">
                    <circle cx="34" cy="34" r="28" fill="none" stroke="#1D3823" strokeWidth="5" />
                    <circle
                      cx="34" cy="34" r="28" fill="none" stroke={riskColor} strokeWidth="5"
                      strokeDasharray={`${Math.min(360, (score / 100) * 360)} 360`}
                      strokeLinecap="round"
                    />
                  </svg>
                  <span className="absolute inset-0 flex items-center justify-center text-base font-extrabold text-[#F1F8F2]">
                    {Math.round(score)}
                  </span>
                </div>
                <div className="space-y-1">
                  <p className="text-[10px] font-bold text-[#8A948C] uppercase tracking-wider">Intelligence Score</p>
                  <div
                    className="px-2.5 py-0.5 rounded-full text-xs font-black inline-block"
                    style={{
                      background: `${riskColor}20`,
                      color: riskColor,
                      border: `1px solid ${riskColor}40`,
                    }}
                  >
                    {category}
                  </div>
                  <p className="text-[10px] text-[#9BAF9F] font-semibold">
                    {incidentCount} {incidentCount === 1 ? 'incident' : 'incidents'} nearby
                  </p>
                </div>
              </div>

              <div className="rounded-xl px-3.5 py-2.5 bg-[#122417] border border-[#1D3823]">
                <p className="text-[10px] font-bold text-[#8A948C] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <Shield className="h-3.5 w-3.5 text-[#66BB6A]" />
                  Safety Factors & Summary
                </p>
                {incidentCount > 0 ? (
                  <ul className="space-y-1">
                    {(() => {
                      const typeCounts: Record<string, { count: number; sources: string[] }> = {}
                      for (const s of sources) {
                        const t = s.incident_type
                        if (!typeCounts[t]) typeCounts[t] = { count: 0, sources: [] }
                        typeCounts[t].count++
                        const label = sourceLabel[s.source] || s.source
                        if (!typeCounts[t].sources.includes(label)) typeCounts[t].sources.push(label)
                      }
                      return Object.entries(typeCounts).sort((a, b) => b[1].count - a[1].count).slice(0, 5).map(([type, info]) => (
                        <li key={type} className="flex items-center gap-2 text-xs text-[#9BAF9F]">
                          <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: riskColor }} />
                          <span className="font-semibold capitalize text-[#F1F8F2]">{type.replace(/_/g, ' ').toLowerCase()}</span>
                          <span className="text-[10px] text-[#8A948C]">×{info.count}</span>
                          <span className="text-[10px] text-[#8A948C] ml-auto">{info.sources.join(', ')}</span>
                        </li>
                      ))
                    })()}
                  </ul>
                ) : (
                  <p className="text-xs text-[#9BAF9F]">No recent incidents recorded for this location.</p>
                )}
              </div>

              {sources.length > 0 && (
                <div>
                  <p className="text-[10px] font-bold text-[#8A948C] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                    <Clock className="h-3.5 w-3.5 text-[#66BB6A]" />
                    Intelligence Evidence ({sources.length})
                  </p>
                  <div className="space-y-2">
                    {sources.slice(0, 10).map((item, i) => (
                      <SourceCard key={`${item.source}-${item.date}-${i}`} item={item} />
                    ))}
                  </div>
                </div>
              )}

              <button
                onClick={onGetSafeRoute}
                className="w-full flex items-center justify-center gap-2 py-3 rounded-xl text-xs font-bold text-[#07110A] bg-[#66BB6A] hover:bg-[#81C784] transition-all"
              >
                <Navigation className="h-4 w-4" />
                Find Safe Route To This Location
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

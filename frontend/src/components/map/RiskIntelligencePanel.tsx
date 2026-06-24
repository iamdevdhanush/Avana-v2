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
  if (isUnknown(category)) return '#6B7280'
  if (s >= 75) return '#D50000'
  if (s >= 50) return '#FF8C00'
  if (s >= 25) return '#FFD600'
  return '#00E676'
}

function getRiskLabel(s: number, category?: string): string {
  if (isUnknown(category)) return 'Unknown'
  if (s >= 75) return 'High'
  if (s >= 50) return 'Elevated'
  if (s >= 25) return 'Moderate'
  return 'Low'
}

const severityBadge: Record<string, string> = {
  CRITICAL: '#D50000',
  HIGH: '#FF1744',
  MEDIUM: '#FF8C00',
  LOW: '#00E676',
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
  const sevColor = severityBadge[item.severity] || '#6B7280'
  const distText = item.distance_meters < 1000
    ? `${Math.round(item.distance_meters)}m`
    : `${(item.distance_meters / 1000).toFixed(1)}km`

  return (
    <div
      className="rounded-xl px-3 py-2.5"
      style={{ background: '#1A1A24', border: '1px solid #1F2937' }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-1">
            <span
              className="text-[10px] font-bold px-1.5 py-0.5 rounded"
              style={{ background: `${sevColor}18`, color: sevColor }}
            >
              {item.severity}
            </span>
            <span className="text-[10px] text-[#6B7280] font-medium capitalize">
              {item.incident_type.replace(/_/g, ' ').toLowerCase()}
            </span>
          </div>
          {item.title && (
            <p className="text-[11px] text-[#D1D5DB] font-medium leading-relaxed mb-1">{item.title}</p>
          )}
          <div className="flex items-center gap-2 text-[9px] text-[#6B7280] flex-wrap">
            <span className="flex items-center gap-1">
              <MapPin className="h-2.5 w-2.5" />
              {distText}
            </span>
            <span>·</span>
            <span>{formatDate(item.date)}</span>
            <span>·</span>
            <span className="capitalize">{sourceLabel[item.source] || item.source.toLowerCase()}</span>
          </div>

          {/* Publisher (NEWS) */}
          {item.source === 'NEWS' && item.publisher && (
            <div className="flex items-center gap-1 mt-1 text-[9px] text-[#4B5563]">
              <Newspaper className="h-2.5 w-2.5" />
              <span>{item.publisher}</span>
            </div>
          )}

          {/* Dataset info (POLICE) */}
          {item.source === 'POLICE' && item.dataset_name && (
            <div className="flex items-center gap-1 mt-1 text-[9px] text-[#4B5563]">
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
          className="mt-2 flex items-center gap-1.5 text-[10px] font-medium transition-colors"
          style={{ color: '#FF1744' }}
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
        className="rounded-t-2xl overflow-y-auto"
        style={{
          background: '#0F0F16',
          borderTop: `1px solid ${riskColor}30`,
          backdropFilter: 'blur(20px)',
          maxHeight: '80vh',
        }}
      >
        <div className="flex justify-center pt-2 pb-1 sticky top-0 z-10" style={{ background: '#0F0F16' }}>
          <div className="w-10 h-1 rounded-full bg-[#1F2937]" />
        </div>

        <div className="flex items-center justify-between px-4 pb-2">
          <div className="flex items-center gap-1.5 min-w-0 flex-1">
            <MapPin className="h-3 w-3 shrink-0" style={{ color: riskColor }} />
            <span className="text-[11px] text-[#9CA3AF] truncate">
              {locationName.isLoading ? 'Detecting…' : (locationName.displayName || `${selectedLocation.lat.toFixed(4)}, ${selectedLocation.lng.toFixed(4)}`)}
            </span>
          </div>
          <button onClick={handleClose} className="rounded-lg p-1 hover:bg-[#1F2937] transition-colors shrink-0 ml-2">
            <X className="h-3.5 w-3.5 text-[#6B7280]" />
          </button>
        </div>

        <div className="px-4 pb-4 space-y-3">
          {isLoading ? (
            <div className="flex items-center gap-3">
              <div className="h-14 w-14 rounded-full bg-[#1F2937] animate-pulse" />
              <div className="space-y-1.5">
                <div className="h-2.5 w-16 bg-[#1F2937] rounded animate-pulse" />
                <div className="h-4 w-20 bg-[#1F2937] rounded-full animate-pulse" />
              </div>
            </div>
          ) : error ? (
            <div className="px-3 py-2 rounded-xl text-[11px]" style={{ background: 'rgba(255,23,68,0.1)', border: '1px solid rgba(255,23,68,0.2)', color: '#FF1744' }}>
              {error}
            </div>
          ) : (
            <>
              <div className="flex items-center gap-4">
                <div className="relative shrink-0">
                  <svg className="h-16 w-16 -rotate-90" viewBox="0 0 68 68">
                    <circle cx="34" cy="34" r="28" fill="none" stroke="#1F2937" strokeWidth="5" />
                    <circle
                      cx="34" cy="34" r="28" fill="none" stroke={riskColor} strokeWidth="5"
                      strokeDasharray={`${Math.min(360, (score / 100) * 360)} 360`}
                      strokeLinecap="round"
                      style={{ filter: `drop-shadow(0 0 6px ${riskColor}60)` }}
                    />
                  </svg>
                  <span className="absolute inset-0 flex items-center justify-center text-lg font-bold text-[#F9FAFB]">
                    {Math.round(score)}
                  </span>
                </div>
                <div className="space-y-1">
                  <p className="text-[10px] font-semibold text-[#6B7280] uppercase tracking-wider">Risk Score</p>
                  <div
                    className="px-2.5 py-0.5 rounded-full text-[11px] font-bold inline-block"
                    style={{
                      background: `${riskColor}18`,
                      color: riskColor,
                      boxShadow: score >= 75 ? `0 0 10px ${riskColor}60` : `0 0 4px ${riskColor}30`,
                    }}
                  >
                    {category}
                  </div>
                  <p className="text-[10px] text-[#4B5563] font-medium">
                    {incidentCount} {incidentCount === 1 ? 'incident' : 'incidents'} nearby
                  </p>
                </div>
              </div>

              <div
                className="rounded-xl px-3.5 py-2.5"
                style={{ background: '#1A1A24', border: '1px solid #1F2937' }}
              >
                <p className="text-[10px] font-bold text-[#6B7280] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <Shield className="h-3 w-3" />
                  Why this area is risky
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
                        <li key={type} className="flex items-center gap-2 text-[11px] text-[#9CA3AF]">
                          <span className="w-1 h-1 rounded-full shrink-0" style={{ background: riskColor }} />
                          <span className="font-medium capitalize">{type.replace(/_/g, ' ').toLowerCase()}</span>
                          <span className="text-[9px] text-[#6B7280]">×{info.count}</span>
                          <span className="text-[9px] text-[#4B5563] ml-auto">{info.sources.join(', ')}</span>
                        </li>
                      ))
                    })()}
                  </ul>
                ) : (
                  <p className="text-[11px] text-[#6B7280]">No recent incidents reported in this area.</p>
                )}
              </div>

              {sources.length > 0 && (
                <div>
                  <p className="text-[10px] font-bold text-[#6B7280] uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                    <Clock className="h-3 w-3" />
                    Nearby Incidents &amp; Records
                    <span className="text-[9px] font-normal normal-case text-[#4B5563]">({sources.length})</span>
                  </p>
                  <div className="space-y-1.5">
                    {sources.slice(0, 15).map((item, i) => (
                      <SourceCard key={`${item.source}-${item.date}-${i}`} item={item} />
                    ))}
                    {sources.length > 15 && (
                      <p className="text-[9px] text-center text-[#4B5563] pt-1">
                        +{sources.length - 15} more records
                      </p>
                    )}
                  </div>
                </div>
              )}

              <button
                onClick={onGetSafeRoute}
                className="w-full flex items-center justify-center gap-2 py-3 rounded-xl text-[12px] font-bold text-white transition-all hover:opacity-90"
                style={{
                  background: 'linear-gradient(135deg, #FF1744 0%, #D50000 100%)',
                  boxShadow: '0 4px 20px rgba(255,23,68,0.35)',
                }}
              >
                <Navigation className="h-4 w-4" />
                Find Safe Route
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

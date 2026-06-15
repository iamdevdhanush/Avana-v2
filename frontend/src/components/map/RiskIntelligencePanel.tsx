import * as React from 'react'
import {
  X, AlertTriangle, Navigation, Flag, MapPin, ExternalLink,
  ChevronDown, ChevronRight, Shield, Newspaper, Users, Building2,
  FileText, Clock,
} from 'lucide-react'
import { useMapStore } from '@/store/mapStore'
import { useLocationName } from '@/hooks/useLocationName'
import type { ExplainResponse, ContributingIncident, SourceAttribution } from '@/types'

function getRiskColor(s: number): string {
  if (s >= 75) return '#D50000'
  if (s >= 50) return '#FF8C00'
  if (s >= 25) return '#FFD600'
  return '#00E676'
}

function getRiskLevelLabel(level: string): string {
  const m: Record<string, string> = { Low: 'Low', Moderate: 'Moderate', Elevated: 'Elevated', High: 'High', Critical: 'Critical' }
  return m[level] || level
}

function getTrendIcon(trend: string): string {
  if (trend === 'worsening') return '↑'
  if (trend === 'improving') return '↓'
  return '→'
}

function getTrendColor(trend: string): string {
  if (trend === 'worsening') return '#FF1744'
  if (trend === 'improving') return '#00E676'
  return '#FFD600'
}

const sourceIcons: Record<string, React.ReactNode> = {
  police_dataset: <Building2 className="h-3 w-3" />,
  news_article: <Newspaper className="h-3 w-3" />,
  community_report: <Users className="h-3 w-3" />,
  verified_incident: <Shield className="h-3 w-3" />,
}

interface RiskIntelligencePanelProps {
  onGetSafeRoute?: () => void
  onClose?: () => void
}

function IncidentCard({ inc }: { inc: ContributingIncident }) {
  const severityColor = inc.severity === 'CRITICAL' || inc.severity === 'HIGH' ? '#FF1744'
    : inc.severity === 'MEDIUM' ? '#FF8C00' : '#00E676'

  const distText = inc.distance_km < 1
    ? `${Math.round(inc.distance_km * 1000)}m`
    : `${inc.distance_km.toFixed(1)}km`

  return (
    <div
      className="rounded-xl px-3 py-2"
      style={{ background: '#1A1A24', border: '1px solid #1F2937' }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-1">
            <span
              className="text-[10px] font-bold px-1.5 py-0.5 rounded"
              style={{ background: `${severityColor}18`, color: severityColor }}
            >
              {inc.severity}
            </span>
            <span className="text-[10px] text-[#6B7280] font-medium">{inc.incident_type.replace(/_/g, ' ')}</span>
          </div>
          {inc.title && <p className="text-[11px] text-[#D1D5DB] font-medium truncate mb-0.5">{inc.title}</p>}
          <div className="flex items-center gap-2 text-[9px] text-[#6B7280]">
            <span>{distText}</span>
            <span>·</span>
            <span>{new Date(inc.date).toLocaleDateString()}</span>
            <span>·</span>
            <span className="capitalize">{inc.source.toLowerCase().replace(/_/g, ' ')}</span>
          </div>
        </div>
        {inc.source_url && (
          <a
            href={inc.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="shrink-0 p-1 rounded-lg hover:bg-[#1F2937] transition-colors"
            onClick={(e) => e.stopPropagation()}
          >
            <ExternalLink className="h-3 w-3 text-[#6B7280]" />
          </a>
        )}
      </div>
      {inc.news_metadata && (
        <div className="mt-1.5 pt-1.5 border-t border-[#1F2937] flex items-center gap-2 text-[9px] text-[#4B5563]">
          <Newspaper className="h-2.5 w-2.5" />
          <span className="truncate">{inc.news_metadata.publisher}</span>
          {inc.news_metadata.url && (
            <a href={inc.news_metadata.url} target="_blank" rel="noopener noreferrer" className="ml-auto flex items-center gap-1 text-[#FF1744] hover:underline">
              Open Original
              <ExternalLink className="h-2.5 w-2.5" />
            </a>
          )}
        </div>
      )}
      {inc.police_metadata && (
        <div className="mt-1.5 pt-1.5 border-t border-[#1F2937] flex items-center gap-2 text-[9px] text-[#4B5563]">
          <Building2 className="h-2.5 w-2.5" />
          <span className="truncate">{inc.police_metadata.dataset_name} · {inc.police_metadata.reporting_year}</span>
        </div>
      )}
    </div>
  )
}

function SourceSection({ sources }: { sources: SourceAttribution[] }) {
  if (sources.length === 0) return null
  return (
    <div className="space-y-1.5">
      <p className="text-[10px] font-bold text-[#6B7280] uppercase tracking-wider flex items-center gap-1.5">
        <FileText className="h-3 w-3" />
        Sources
      </p>
      <div className="space-y-1">
        {sources.map((s) => (
          <div
            key={s.type}
            className="rounded-xl px-3 py-2"
            style={{ background: '#1A1A24', border: '1px solid #1F2937' }}
          >
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-1.5">
                {sourceIcons[s.type] || <FileText className="h-3 w-3 text-[#9CA3AF]" />}
                <span className="text-[11px] text-[#D1D5DB] font-medium">{s.label}</span>
              </div>
              <span className="text-[9px] text-[#6B7280] font-medium">{s.count} records</span>
            </div>
            {s.items.length > 0 && (
              <div className="space-y-0.5">
                {s.items.slice(0, 3).map((item, i) => (
                  <div key={i} className="flex items-start gap-1.5 text-[9px] text-[#4B5563]">
                    <span className="w-1 h-1 rounded-full bg-[#4B5563] mt-1 shrink-0" />
                    <span className="truncate">{item.name}</span>
                    <span className="ml-auto shrink-0">{item.count > 1 && `×${item.count}`}</span>
                  </div>
                ))}
                {s.items.length > 3 && (
                  <p className="text-[9px] text-[#4B5563] pl-3">+{s.items.length - 3} more</p>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function ConfidenceBadge({ confidence }: { confidence: ExplainResponse['confidence'] }) {
  const color = confidence.score >= 75 ? '#00E676' : confidence.score >= 50 ? '#FFD600' : '#FF8C00'
  return (
    <div
      className="rounded-xl px-3 py-2 flex items-center justify-between"
      style={{ background: '#1A1A24', border: '1px solid #1F2937' }}
    >
      <div className="flex items-center gap-2">
        <Shield className="h-3 w-3" style={{ color }} />
        <div>
          <p className="text-[10px] text-[#D1D5DB] font-medium">Confidence</p>
          {confidence.based_on.length > 0 && (
            <p className="text-[9px] text-[#4B5563]">{confidence.based_on.join(', ')}</p>
          )}
        </div>
      </div>
      <span className="text-sm font-bold" style={{ color }}>{Math.round(confidence.score)}%</span>
    </div>
  )
}

export function RiskIntelligencePanel({ onGetSafeRoute, onClose }: RiskIntelligencePanelProps) {
  const { selectedLocation, setSelectedLocation } = useMapStore()
  const [explain, setExplain] = React.useState<ExplainResponse | null>(null)
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [showIncidents, setShowIncidents] = React.useState(true)
  const [showSources, setShowSources] = React.useState(true)

  const locationName = useLocationName(selectedLocation?.lat, selectedLocation?.lng)

  React.useEffect(() => {
    if (!selectedLocation) return
    setIsLoading(true)
    setError(null)
    import('@/services/api').then(({ riskApi }) =>
      riskApi.explainScore(selectedLocation.lat, selectedLocation.lng)
        .then(setExplain)
        .catch((err: Error) => setError(err.message))
        .finally(() => setIsLoading(false))
    )
  }, [selectedLocation])

  if (!selectedLocation) return null

  const score = explain?.score ?? 0
  const riskColor = getRiskColor(score)

  const handleClose = () => {
    setSelectedLocation(null)
    onClose?.()
  }

  return (
    <div className="absolute bottom-0 left-0 right-0 z-[1000]" style={{ maxHeight: '85vh' }}>
      <div
        className="rounded-t-2xl overflow-y-auto"
        style={{
          background: '#0F0F16',
          borderTop: `1px solid ${riskColor}30`,
          backdropFilter: 'blur(20px)',
          maxHeight: '85vh',
        }}
      >
        {/* Handle */}
        <div className="flex justify-center pt-2 pb-1 sticky top-0 z-10" style={{ background: '#0F0F16' }}>
          <div className="w-10 h-1 rounded-full bg-[#1F2937]" />
        </div>

        {/* Header */}
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
          {/* Loading / Error */}
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
          ) : explain ? (
            <>
              {/* Risk Score */}
              <div className="flex items-center gap-3">
                <div className="relative shrink-0">
                  <svg className="h-14 w-14 -rotate-90" viewBox="0 0 60 60">
                    <circle cx="30" cy="30" r="24" fill="none" stroke="#1F2937" strokeWidth="4" />
                    <circle
                      cx="30" cy="30" r="24" fill="none" stroke={riskColor} strokeWidth="4"
                      strokeDasharray={`${Math.min(360, (score / 100) * 360)} 360`} strokeLinecap="round"
                      style={{ filter: `drop-shadow(0 0 4px ${riskColor}60)` }}
                    />
                  </svg>
                  <span className="absolute inset-0 flex items-center justify-center text-sm font-bold text-[#F9FAFB]">
                    {Math.round(score)}
                  </span>
                </div>
                <div className="space-y-0.5">
                  <p className="text-[10px] font-semibold text-[#6B7280] uppercase tracking-wider">Risk Score</p>
                  <div className="flex items-center gap-2">
                    <div
                      className="px-2 py-0.5 rounded-full text-[10px] font-bold inline-block"
                      style={{ background: `${riskColor}18`, color: riskColor, boxShadow: score >= 75 ? `0 0 8px ${riskColor}60` : `0 0 3px ${riskColor}30` }}
                    >
                      {getRiskLevelLabel(explain.level)}
                    </div>
                    <span className="text-[10px] font-medium" style={{ color: getTrendColor(explain.trend) }}>
                      {getTrendIcon(explain.trend)} {explain.trend}
                    </span>
                  </div>
                  <div className="flex items-center gap-1 text-[9px] text-[#4B5563]">
                    <Clock className="h-2.5 w-2.5" />
                    Updated {new Date(explain.last_updated).toLocaleDateString()}
                  </div>
                </div>
              </div>

              {/* Confidence */}
              <ConfidenceBadge confidence={explain.confidence} />

              {/* Why this score? */}
              <div
                className="rounded-xl px-3 py-2.5"
                style={{ background: '#1A1A24', border: '1px solid #1F2937' }}
              >
                <p className="text-[10px] font-bold text-[#6B7280] uppercase tracking-wider mb-2">Why this score?</p>
                <div className="grid grid-cols-2 gap-1.5">
                  {[
                    { label: 'Police Data', key: 'police_crime_data' as const, icon: <Building2 className="h-3 w-3" /> },
                    { label: 'Verified Reports', key: 'verified_incidents' as const, icon: <Shield className="h-3 w-3" /> },
                    { label: 'Community', key: 'community_reports' as const, icon: <Users className="h-3 w-3" /> },
                    { label: 'News Intel', key: 'news_intelligence' as const, icon: <Newspaper className="h-3 w-3" /> },
                  ].map((src) => {
                    const val = explain.why_score[src.key]
                    return (
                      <div
                        key={src.key}
                        className="rounded-lg px-2.5 py-1.5 flex items-center gap-2"
                        style={{ background: val > 0 ? `${riskColor}10` : '#0F0F16', border: `1px solid ${val > 0 ? `${riskColor}20` : '#1F2937'}` }}
                      >
                        <span className="shrink-0" style={{ color: val > 0 ? riskColor : '#4B5563' }}>{src.icon}</span>
                        <div className="min-w-0">
                          <p className="text-[9px] text-[#6B7280] font-medium truncate">{src.label}</p>
                          <p className="text-[11px] font-bold" style={{ color: val > 0 ? '#D1D5DB' : '#4B5563' }}>{val}</p>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Contributing Incidents */}
              {explain.contributing_incidents.length > 0 && (
                <div>
                  <button
                    onClick={() => setShowIncidents((v) => !v)}
                    className="flex items-center gap-1 text-[10px] font-bold text-[#6B7280] uppercase tracking-wider mb-1.5 hover:text-[#9CA3AF] transition-colors"
                  >
                    {showIncidents ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                    Contributing Incidents ({explain.contributing_incidents.length})
                  </button>
                  {showIncidents && (
                    <div className="space-y-1">
                      {explain.contributing_incidents.slice(0, 10).map((inc) => (
                        <IncidentCard key={inc.id} inc={inc} />
                      ))}
                      {explain.contributing_incidents.length > 10 && (
                        <p className="text-[9px] text-center text-[#4B5563] pt-1">
                          +{explain.contributing_incidents.length - 10} more incidents
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Sources */}
              {explain.sources.length > 0 && (
                <div>
                  <button
                    onClick={() => setShowSources((v) => !v)}
                    className="flex items-center gap-1 text-[10px] font-bold text-[#6B7280] uppercase tracking-wider mb-1.5 hover:text-[#9CA3AF] transition-colors"
                  >
                    {showSources ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                    Sources ({explain.sources.length})
                  </button>
                  {showSources && <SourceSection sources={explain.sources} />}
                </div>
              )}

              {/* Action buttons */}
              <div className="flex gap-2 pt-1">
                <button
                  onClick={onGetSafeRoute}
                  className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-[11px] font-bold text-white transition-all hover:opacity-90"
                  style={{
                    background: 'linear-gradient(135deg, #FF1744 0%, #D50000 100%)',
                    boxShadow: '0 4px 16px rgba(255,23,68,0.3)',
                  }}
                >
                  <Navigation className="h-3 w-3" />
                  Safe Route
                </button>
              </div>
            </>
          ) : null}
        </div>
      </div>
    </div>
  )
}

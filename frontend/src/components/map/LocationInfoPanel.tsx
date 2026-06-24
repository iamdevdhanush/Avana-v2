import * as React from 'react'
import { X, AlertTriangle, Navigation, Flag, MapPin } from 'lucide-react'
import { useMapStore } from '@/store/mapStore'
import { useLocationName } from '@/hooks/useLocationName'
import { riskApi } from '@/services/api'

function isUnknown(category?: string): boolean {
  return category?.toLowerCase() === 'unknown'
}

function getRiskColor(s: number, category?: string): string {
  if (isUnknown(category)) return '#6B7280'
  if (s >= 0.9) return '#D50000'
  if (s >= 0.75) return '#FF1744'
  if (s >= 0.5) return '#FF8C00'
  if (s >= 0.25) return '#FFD600'
  return '#00E676'
}

function getRiskLabel(s: number, category?: string): string {
  if (isUnknown(category)) return 'Unknown'
  if (s >= 0.9) return 'Critical'
  if (s >= 0.75) return 'High'
  if (s >= 0.5) return 'Elevated'
  if (s >= 0.25) return 'Moderate'
  return 'Low'
}

function getRiskAdvice(s: number, category?: string): string {
  if (isUnknown(category)) return 'Insufficient intelligence available'
  if (s >= 0.9) return 'Avoid — active danger zone'
  if (s >= 0.75) return 'Avoid non-essential travel'
  if (s >= 0.5) return 'Exercise heightened caution'
  if (s >= 0.25) return 'Stay aware of surroundings'
  return 'Area is generally safe'
}

function RiskScoreBadge({ score, category }: { score: number; category?: string }) {
  const color = getRiskColor(score, category)
  const label = getRiskLabel(score, category)
  const angle = Math.min(360, score * 360)
  return (
    <div className="flex items-center gap-3">
      <div className="relative shrink-0">
        <svg className="h-14 w-14 -rotate-90" viewBox="0 0 60 60">
          <circle cx="30" cy="30" r="24" fill="none" stroke="#1F2937" strokeWidth="4" />
          <circle
            cx="30" cy="30" r="24" fill="none" stroke={color} strokeWidth="4"
            strokeDasharray={`${angle} 360`} strokeLinecap="round"
            style={{ filter: `drop-shadow(0 0 4px ${color}60)` }}
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-sm font-bold text-[#F9FAFB]">
          {Math.round(score * 100)}
        </span>
      </div>
      <div className="space-y-0.5">
        <p className="text-[10px] font-semibold text-[#6B7280] uppercase tracking-wider">Risk Score</p>
        <div
          className="px-2 py-0.5 rounded-full text-[10px] font-bold inline-block"
          style={{ background: `${color}18`, color, boxShadow: score >= 0.9 ? `0 0 8px ${color}60` : score >= 0.75 ? `0 0 6px ${color}50` : `0 0 3px ${color}30` }}
        >
          {label}
        </div>
        <p className="text-[9px] text-[#4B5563] font-medium">{getRiskAdvice(score)}</p>
      </div>
    </div>
  )
}

interface LocationInfoPanelProps {
  onReportArea?: () => void
  onGetSafeRoute?: () => void
  onClose?: () => void
}

interface RiskScoreState {
  score: number
  category: string
  factors: Record<string, number>
  recommendations: string[]
}

export function LocationInfoPanel({ onReportArea, onGetSafeRoute, onClose }: LocationInfoPanelProps) {
  const { selectedLocation, setSelectedLocation } = useMapStore()
  const [riskScore, setRiskScore] = React.useState<RiskScoreState | null>(null)
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const locationName = useLocationName(selectedLocation?.lat, selectedLocation?.lng)

  React.useEffect(() => {
    if (!selectedLocation) return
    setIsLoading(true)
    setError(null)
    riskApi.getRiskScore(selectedLocation.lat, selectedLocation.lng)
      .then((r) => {
        const fMap: Record<string, number> = {}
        for (const f of r.factors) fMap[f.name] = f.value
        setRiskScore({ score: r.score, category: r.category, factors: fMap, recommendations: r.recommendations })
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false))
  }, [selectedLocation])

  if (!selectedLocation) return null

  const score = riskScore?.score ?? 0
  const rawCategory = riskScore?.category ?? ''
  const riskColor = getRiskColor(score, rawCategory)

  const handleClose = () => {
    setSelectedLocation(null)
    onClose?.()
  }

  return (
    <div className="absolute bottom-0 left-0 right-0 z-[1000]">
      <div
        className="rounded-t-2xl overflow-hidden"
        style={{
          background: '#0F0F16',
          borderTop: `1px solid ${riskColor}30`,
          backdropFilter: 'blur(20px)',
        }}
      >
        <div className="flex justify-center pt-2 pb-1">
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
          ) : riskScore ? (
            <RiskScoreBadge score={riskScore.score} category={riskScore.category} />
          ) : null}

          {riskScore?.factors && (
            <div className="flex gap-2">
              {[
                { label: 'Historical', key: 'historical_risk', max: 100 },
                { label: 'Recent', key: 'recent_reports_impact', max: 30 },
                { label: 'Police', key: 'police_presence_bonus', max: 10 },
                { label: 'Hospitals', key: 'hospital_access_bonus', max: 5 },
              ].map((f) => {
                const val = riskScore.factors[f.key] ?? 0
                const pct = Math.min(100, (val / f.max) * 100)
                const barColor = pct >= 60 ? '#FF1744' : pct >= 30 ? '#FF8C00' : '#00E676'
                return (
                  <div key={f.key} className="flex-1 min-w-0">
                    <div className="flex justify-between items-center mb-0.5">
                      <span className="text-[8px] text-[#6B7280] font-semibold">{f.label}</span>
                      <span className="text-[8px] text-[#4B5563]">{Math.round(val)}</span>
                    </div>
                    <div className="h-1 rounded-full bg-[#1F2937] overflow-hidden">
                      <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: barColor, boxShadow: `0 0 3px ${barColor}50` }} />
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          <div className="flex gap-2">
            <button
              onClick={onReportArea}
              className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl text-[11px] font-bold transition-all hover:opacity-80"
              style={{ background: '#1F2937', color: '#D1D5DB', border: '1px solid #374151' }}
            >
              <Flag className="h-3 w-3" />
              Report
            </button>
            <button
              onClick={onGetSafeRoute}
              className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl text-[11px] font-bold text-white transition-all hover:opacity-90"
              style={{
                background: 'linear-gradient(135deg, #FF1744 0%, #D50000 100%)',
                boxShadow: '0 4px 16px rgba(255,23,68,0.3)',
              }}
            >
              <Navigation className="h-3 w-3" />
              Safe Route
            </button>
          </div>

          {riskScore?.recommendations?.[0] && (
            <div className="rounded-xl px-3 py-2" style={{ background: '#1A1A24', border: '1px solid #1F2937' }}>
              <div className="flex items-center gap-1.5 mb-1">
                <AlertTriangle className="h-3 w-3 text-[#FF8C00]" />
                <span className="text-[9px] font-bold text-[#6B7280] uppercase tracking-wider">Safety Note</span>
              </div>
              <p className="text-[11px] text-[#9CA3AF] leading-relaxed">{riskScore.recommendations[0]}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

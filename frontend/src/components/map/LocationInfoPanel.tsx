import * as React from 'react'
import { X, AlertTriangle, Navigation, Flag, MapPin, TrendingUp } from 'lucide-react'
import { useMapStore } from '@/store/mapStore'
import { riskApi } from '@/services/api'
import { useLocationName } from '@/hooks/useLocationName'
import type { RiskScore, RiskFactor } from '@/types'

interface LocationInfoPanelProps {
  onReportArea?: () => void
  onGetSafeRoute?: () => void
  onClose?: () => void
}

function getRiskColor(score: number): string {
  if (score >= 0.9) return '#D50000'
  if (score >= 0.75) return '#FF1744'
  if (score >= 0.5) return '#FF8C00'
  if (score >= 0.25) return '#FFD600'
  return '#00E676'
}

function getRiskLabel(score: number): string {
  if (score >= 0.9) return 'Critical'
  if (score >= 0.75) return 'High'
  if (score >= 0.5) return 'Elevated'
  if (score >= 0.25) return 'Moderate'
  return 'Low'
}

function getRiskGlow(score: number): string {
  if (score >= 0.9) return `0 0 8px #D5000060, 0 0 16px #D5000030`
  if (score >= 0.75) return `0 0 6px #FF174460`
  return `0 0 4px ${getRiskColor(score)}40`
}

function RiskGauge({ score }: { score: number }) {
  const color = getRiskColor(score)
  const label = getRiskLabel(score)
  const angle = Math.min(360, score * 360)
  return (
    <div className="flex items-center gap-4">
      <div className="relative flex items-center justify-center shrink-0">
        <svg className="h-16 w-16 -rotate-90" viewBox="0 0 72 72">
          <circle cx="36" cy="36" r="30" fill="none" stroke="#1F2937" strokeWidth="4" />
          <circle
            cx="36" cy="36" r="30" fill="none" stroke={color} strokeWidth="4"
            strokeDasharray={`${angle} 360`} strokeLinecap="round"
            className="transition-all duration-1000"
            style={{ filter: `drop-shadow(0 0 4px ${color}60)` }}
          />
        </svg>
        <span className="absolute text-base font-bold text-[#F9FAFB]">{Math.round(score * 100)}</span>
      </div>
      <div className="space-y-0.5">
        <p className="text-[11px] font-semibold text-[#6B7280] uppercase tracking-wider">Risk Score</p>
        <div
          className="px-2 py-0.5 rounded-full text-[11px] font-bold inline-block"
          style={{ background: `${color}20`, color, boxShadow: getRiskGlow(score) }}
        >
          {label}
        </div>
        <p className="text-[9px] text-[#4B5563] font-medium">{score >= 0.75 ? 'Avoid non-essential travel' : score >= 0.5 ? 'Exercise caution' : score >= 0.25 ? 'Stay aware' : 'Area is safe'}</p>
      </div>
    </div>
  )
}

export function LocationInfoPanel({ onReportArea, onGetSafeRoute, onClose }: LocationInfoPanelProps) {
  const { selectedLocation, setSelectedLocation } = useMapStore()
  const [riskScore, setRiskScore] = React.useState<RiskScore | null>(null)
  const [isLoading, setIsLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  const locationName = useLocationName(selectedLocation?.lat, selectedLocation?.lng)

  React.useEffect(() => {
    if (!selectedLocation) return
    setIsLoading(true)
    setError(null)
    riskApi.getRiskScore(selectedLocation.lat, selectedLocation.lng)
      .then(setRiskScore)
      .catch((err) => setError(err.message))
      .finally(() => setIsLoading(false))
  }, [selectedLocation])

  if (!selectedLocation) return null

  const handleClose = () => {
    setSelectedLocation(null)
    onClose?.()
  }

  const score = riskScore?.score ?? 0
  const riskColor = getRiskColor(score)

  return (
    <div className="absolute bottom-0 left-0 right-0 z-[1000]">
      <div
        className="rounded-t-2xl shadow-2xl overflow-hidden"
        style={{
          background: '#0F0F16',
          borderTop: `1px solid ${riskScore ? getRiskColor(riskScore.score) + '30' : '#1F2937'}`,
          backdropFilter: 'blur(20px)',
        }}
      >
        <div className="flex justify-center pt-2 pb-1">
          <div className="w-10 h-1 rounded-full bg-[#1F2937]" />
        </div>

        <div className="flex items-center justify-between px-5 pb-3">
          <div className="flex items-center gap-2 min-w-0 flex-1">
            <MapPin className="h-3.5 w-3.5 shrink-0" style={{ color: riskColor }} />
            <span className="text-xs text-[#9CA3AF] truncate">
              {locationName.isLoading ? 'Detecting location...' : (locationName.displayName || `${selectedLocation.lat.toFixed(4)}, ${selectedLocation.lng.toFixed(4)}`)}
            </span>
          </div>
          <button
            onClick={handleClose}
            className="rounded-lg p-1.5 hover:bg-[#1F2937] transition-colors shrink-0 ml-2"
          >
            <X className="h-4 w-4 text-[#6B7280]" />
          </button>
        </div>

        <div className="px-5 pb-5 space-y-4">
          {isLoading ? (
            <div className="flex items-center gap-4">
              <div className="h-16 w-16 rounded-full bg-[#1F2937] animate-pulse" />
              <div className="space-y-2">
                <div className="h-3 w-20 bg-[#1F2937] rounded animate-pulse" />
                <div className="h-5 w-24 bg-[#1F2937] rounded-full animate-pulse" />
              </div>
            </div>
          ) : error ? (
            <div
              className="px-3 py-2 rounded-xl text-xs"
              style={{ background: 'rgba(255,23,68,0.1)', border: '1px solid rgba(255,23,68,0.2)', color: '#FF1744' }}
            >
              {error}
            </div>
          ) : riskScore ? (
            <RiskGauge score={riskScore.score} />
          ) : null}

          {riskScore?.factors && riskScore.factors.length > 0 && (
            <div className="flex gap-3">
              {(function getFactors() {
                const fMap: Record<string, RiskFactor> = {}
                for (const f of riskScore.factors) {
                  fMap[f.name] = f
                }
                return [
                  { label: 'Historical', key: 'historical_risk', max: 100 },
                  { label: 'Recent', key: 'recent_reports_impact', max: 30 },
                  { label: 'Police', key: 'police_presence_bonus', max: 10 },
                  { label: 'Hospitals', key: 'hospital_access_bonus', max: 5 },
                ].map((f) => {
                  const factor = fMap[f.key]
                  const val = factor?.value ?? 0
                  const pct = Math.min(100, (val / f.max) * 100)
                  const barColor = pct > 60 ? '#FF1744' : pct > 30 ? '#FF8C00' : '#00E676'
                  return (
                    <div key={f.key} className="flex-1 min-w-0">
                      <div className="flex justify-between items-center mb-1">
                        <span className="text-[9px] text-[#6B7280] font-medium">{f.label}</span>
                        <span className="text-[9px] text-[#4B5563]">{Math.round(val)}</span>
                      </div>
                      <div className="h-1 rounded-full bg-[#1F2937] overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{ width: `${pct}%`, background: barColor, boxShadow: `0 0 4px ${barColor}60` }}
                        />
                      </div>
                    </div>
                  )
                })
              })()}
            </div>
          )}

          <div className="flex gap-2">
            <button
              onClick={onReportArea}
              className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-xs font-bold transition-all hover:opacity-80"
              style={{ background: '#1F2937', color: '#D1D5DB', border: '1px solid #374151' }}
            >
              <Flag className="h-3.5 w-3.5" />
              Report Area
            </button>
            <button
              onClick={onGetSafeRoute}
              className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-xs font-bold text-white transition-all hover:opacity-90"
              style={{
                background: 'linear-gradient(135deg, #FF1744 0%, #D50000 100%)',
                boxShadow: '0 4px 20px rgba(255,23,68,0.3)',
              }}
            >
              <Navigation className="h-3.5 w-3.5" />
              Safe Route
            </button>
          </div>

          {riskScore?.recommendations && riskScore.recommendations.length > 0 && (
            <div
              className="rounded-xl p-3"
              style={{ background: '#1A1A24', border: '1px solid #1F2937' }}
            >
              <div className="flex items-center gap-1.5 mb-2">
                <AlertTriangle className="h-3 w-3 text-[#FF8C00]" />
                <span className="text-[10px] font-bold text-[#6B7280] uppercase tracking-wider">Safety Note</span>
              </div>
              <p className="text-xs text-[#9CA3AF] leading-relaxed">{riskScore.recommendations[0]}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

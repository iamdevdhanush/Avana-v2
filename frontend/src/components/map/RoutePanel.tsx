import * as React from 'react'
import {
  Navigation, ArrowDown, Loader2, Shield, Zap, Scale, X, Info,
} from 'lucide-react'
import { cn, formatDistance, formatDuration } from '@/lib/utils'
import { useRouteSafety } from '@/hooks/useRouteSafety'
import { useGeolocation } from '@/hooks/useGeolocation'
import type { RouteOption } from '@/types'

interface RoutePanelProps {
  onClose?: () => void
}

const ROUTE_TYPES = [
  {
    value: 'safest' as const,
    icon: Shield,
    label: 'Safest',
    riskLabel: 'Low Risk',
    color: '#22C55E',
    bg: 'rgba(34,197,94,0.12)',
    desc: 'Most protected path',
  },
  {
    value: 'fastest' as const,
    icon: Zap,
    label: 'Fastest',
    riskLabel: 'Medium Risk',
    color: '#F59E0B',
    bg: 'rgba(245,158,11,0.12)',
    desc: 'Quickest route',
  },
  {
    value: 'balanced' as const,
    icon: Scale,
    label: 'Balanced',
    riskLabel: 'Low-Medium Risk',
    color: '#A855F7',
    bg: 'rgba(168,85,247,0.12)',
    desc: 'Time and safety',
  },
]

function getRiskLabel(score: number): { label: string; color: string } {
  if (score >= 0.8) return { label: 'Low Risk', color: '#22C55E' }
  if (score >= 0.6) return { label: 'Medium-Low Risk', color: '#84CC16' }
  if (score >= 0.4) return { label: 'Medium Risk', color: '#F59E0B' }
  if (score >= 0.2) return { label: 'Elevated Risk', color: '#F97316' }
  return { label: 'High Risk', color: '#EF4444' }
}

// Generate trust explanation from REAL backend data
function getRouteTrustInfo(opt: RouteOption, type: 'safest' | 'fastest' | 'balanced'): string[] {
  const reasons: string[] = []
  const safetyPct = Math.round(opt.safetyScore)

  if (safetyPct > 0) {
    reasons.push(`Safety score: ${safetyPct}/100 for this route`)
  }

  if (opt.segments && opt.segments.length > 0) {
    const highRiskSegs = opt.segments.filter(s => s.riskLevel === 'high').length
    const medRiskSegs = opt.segments.filter(s => s.riskLevel === 'medium').length
    const lowRiskSegs = opt.segments.filter(s => s.riskLevel === 'low').length
    if (highRiskSegs > 0) reasons.push(`Passes through ${highRiskSegs} elevated-risk segment${highRiskSegs > 1 ? 's' : ''}`)
    if (medRiskSegs > 0) reasons.push(`Includes ${medRiskSegs} moderate-risk segment${medRiskSegs > 1 ? 's' : ''}`)
    if (lowRiskSegs > 0) reasons.push(`${lowRiskSegs} low-risk segment${lowRiskSegs > 1 ? 's' : ''} on this path`)
  }

  if (reasons.length === 0) {
    // Fallback when no segment data returned by backend
    if (type === 'safest') reasons.push('Backend selected this as the safest calculated path')
    else if (type === 'fastest') reasons.push('Backend selected this as the fastest calculated path')
    else reasons.push('Backend balanced safety and time for this route')
  }

  return reasons
}

export function RoutePanel({ onClose }: RoutePanelProps) {
  const [from, setFrom] = React.useState('')
  const [to, setTo] = React.useState('')
  const [activeType, setActiveType] = React.useState<'safest' | 'fastest' | 'balanced'>('safest')
  const { position } = useGeolocation()
  const { routeResult, selectedRoute, isLoading, error, calculateRoute, selectRoute, clearRoute } = useRouteSafety()

  React.useEffect(() => {
    if (position.latitude && position.longitude) {
      setFrom(`${position.latitude.toFixed(4)}, ${position.longitude.toFixed(4)}`)
    }
  }, [position.latitude, position.longitude])

  const handleFindRoute = async () => {
    if (!position.latitude || !position.longitude) return
    const destMatch = to.match(/(-?\d+\.?\d*),\s*(-?\d+\.?\d*)/)
    if (!destMatch) return
    await calculateRoute(
      { lat: position.latitude, lng: position.longitude },
      { lat: parseFloat(destMatch[1]), lng: parseFloat(destMatch[2]) },
    )
  }

  const handleSelectRoute = (type: typeof activeType) => {
    setActiveType(type)
    if (routeResult) selectRoute(type)
  }

  return (
    <div
      className="absolute top-16 left-3 z-[1000] w-80 rounded-2xl shadow-2xl overflow-hidden"
      style={{ background: '#1A1A24', border: '1px solid #1F2937' }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#1F2937]">
        <div className="flex items-center gap-2">
          <Navigation className="h-4 w-4 text-[#A855F7]" />
          <span className="text-sm font-bold text-[#F9FAFB]">Safe Route</span>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-[#1F2937] transition-colors text-[#6B7280]"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      <div className="p-4 space-y-3">
        {/* From / To inputs */}
        <div className="space-y-2">
          <div className="relative">
            <div className="absolute left-3 top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full bg-[#22C55E] border-2 border-[#09090B]" />
            <input
              placeholder="From (your location)"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
              className="w-full pl-8 pr-3 py-2.5 rounded-xl text-xs bg-[#111827] text-[#F9FAFB] placeholder:text-[#6B7280] outline-none border border-[#1F2937] focus:border-[#A855F7]/40 transition-colors"
            />
          </div>

          <div className="flex items-center justify-center">
            <ArrowDown className="h-3.5 w-3.5 text-[#374151]" />
          </div>

          <div className="relative">
            <div className="absolute left-3 top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full bg-[#EF4444] border-2 border-[#09090B]" />
            <input
              placeholder="Destination (lat, lng)"
              value={to}
              onChange={(e) => setTo(e.target.value)}
              className="w-full pl-8 pr-3 py-2.5 rounded-xl text-xs bg-[#111827] text-[#F9FAFB] placeholder:text-[#6B7280] outline-none border border-[#1F2937] focus:border-[#A855F7]/40 transition-colors"
            />
          </div>
        </div>

        {/* Find route button */}
        {!routeResult && (
          <button
            onClick={handleFindRoute}
            disabled={isLoading || !to}
            className="w-full py-2.5 rounded-xl text-sm font-bold text-white transition-all disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            style={{
              background: !to ? '#1F2937' : 'linear-gradient(135deg, #A855F7 0%, #9333EA 100%)',
              boxShadow: to ? '0 4px 20px rgba(168,85,247,0.3)' : 'none',
            }}
          >
            {isLoading ? (
              <><Loader2 className="h-4 w-4 animate-spin" />Calculating...</>
            ) : (
              <><Navigation className="h-4 w-4" />Find Route</>
            )}
          </button>
        )}

        {/* Error */}
        {error && (
          <div
            className="px-3 py-2.5 rounded-xl text-xs"
            style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', color: '#EF4444' }}
          >
            {error}
          </div>
        )}

        {/* Route results */}
        {routeResult && (
          <div className="space-y-3">
            <div className="border-t border-[#1F2937] pt-3">
              <p className="text-xs text-[#6B7280] font-semibold uppercase tracking-wide mb-2">Choose Route</p>

              {/* Route option cards */}
              {ROUTE_TYPES.map(({ value, icon: Icon, label, color, bg }) => {
                const opt = routeResult[value]
                const risk = getRiskLabel(opt.safetyScore)
                const isSelected = activeType === value
                return (
                  <button
                    key={value}
                    onClick={() => handleSelectRoute(value)}
                    className="w-full flex items-center gap-3 p-3 rounded-xl mb-2 text-left transition-all"
                    style={{
                      background: isSelected ? bg : '#111827',
                      border: `1px solid ${isSelected ? color + '50' : '#1F2937'}`,
                      transform: isSelected ? 'scale(1.01)' : 'scale(1)',
                    }}
                  >
                    <div
                      className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                      style={{ background: isSelected ? bg : 'rgba(31,41,55,0.8)', color }}
                    >
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-[#F9FAFB]">{label}</span>
                        <span className="text-xs font-bold" style={{ color: '#F9FAFB' }}>
                          {formatDuration(opt.duration)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between mt-0.5">
                        <span className="text-[10px] font-medium" style={{ color: risk.color }}>
                          {risk.label}
                        </span>
                        <span className="text-[10px] text-[#6B7280]">{formatDistance(opt.distance)}</span>
                      </div>
                    </div>
                    {value === 'safest' && (
                      <span
                        className="text-[9px] font-black px-1.5 py-0.5 rounded-full shrink-0 uppercase"
                        style={{ background: '#22C55E20', color: '#22C55E' }}
                      >
                        Best
                      </span>
                    )}
                  </button>
                )
              })}
            </div>

            {/* Why this route — real data */}
            {selectedRoute && (
              <div
                className="rounded-xl p-3"
                style={{ background: '#111827', border: '1px solid #1F2937' }}
              >
                <div className="flex items-center gap-1.5 mb-2">
                  <Info className="h-3.5 w-3.5 text-[#A855F7]" />
                  <p className="text-xs font-bold text-[#F9FAFB]">Why this route?</p>
                  <span className="ml-auto text-[10px] text-[#4B5563]">Route Engine: OSRM</span>
                </div>
                <ul className="space-y-1.5">
                  {getRouteTrustInfo(routeResult[activeType], activeType).map((reason, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-[#A855F7] mt-1.5 shrink-0" />
                      <span className="text-[11px] text-[#9CA3AF] leading-relaxed">{reason}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Clear */}
            <button
              onClick={clearRoute}
              className="w-full py-2 rounded-xl text-xs font-semibold text-[#6B7280] hover:text-[#F9FAFB] hover:bg-[#1F2937] transition-all border border-[#1F2937]"
            >
              Clear Route
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

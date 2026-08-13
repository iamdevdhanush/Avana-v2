import * as React from 'react'
import {
  Navigation, ArrowDown, Loader2, Shield, Zap, Scale, X, Info, MapPin, CheckCircle2,
} from 'lucide-react'
import { formatDistance, formatDuration } from '@/lib/utils'
import { useRouteSafety } from '@/hooks/useRouteSafety'
import { useGeolocation } from '@/hooks/useGeolocation'
import { useLocationName } from '@/hooks/useLocationName'
import { SearchDestination } from '@/components/map/SearchDestination'
import type { RouteOption } from '@/types'

interface RoutePanelProps {
  onClose?: () => void
}

const ROUTE_TYPES = [
  {
    value: 'safest' as const,
    icon: Shield,
    label: 'Safest Route',
    riskLabel: 'LOWER RISK',
    color: '#66BB6A',
    bg: 'rgba(102,187,106,0.12)',
    desc: 'Lowest incident density path',
  },
  {
    value: 'fastest' as const,
    icon: Zap,
    label: 'Fastest Route',
    riskLabel: 'MODERATE RISK',
    color: '#F5B942',
    bg: 'rgba(245,185,66,0.12)',
    desc: 'Quickest estimated time',
  },
  {
    value: 'balanced' as const,
    icon: Scale,
    label: 'Balanced Path',
    riskLabel: 'BALANCED RISK',
    color: '#A5D6A7',
    bg: 'rgba(165,214,167,0.12)',
    desc: 'Optimum safety & duration',
  },
]

function getRiskBadge(score: number, category?: string): { label: string; color: string } {
  if (category?.toLowerCase() === 'unknown') return { label: 'UNKNOWN RISK', color: '#8A948C' }
  if (score >= 0.8) return { label: 'LOWER RISK', color: '#66BB6A' }
  if (score >= 0.6) return { label: 'MODERATE RISK', color: '#F5B942' }
  if (score >= 0.4) return { label: 'ELEVATED RISK', color: '#F97316' }
  return { label: 'HIGH RISK', color: '#EF4444' }
}

function getRouteTrustInfo(opt: RouteOption, type: 'safest' | 'fastest' | 'balanced'): string[] {
  const reasons: string[] = []
  const safetyPct = Math.round(opt.safetyScore)

  if (safetyPct > 0) {
    reasons.push(`Calculated route safety score: ${safetyPct}/100`)
  }

  if (opt.segments && opt.segments.length > 0) {
    const highRiskSegs = opt.segments.filter(s => s.riskLevel === 'high').length
    const medRiskSegs = opt.segments.filter(s => s.riskLevel === 'medium').length
    const lowRiskSegs = opt.segments.filter(s => s.riskLevel === 'low').length
    if (highRiskSegs > 0) reasons.push(`Passes ${highRiskSegs} elevated-risk area${highRiskSegs > 1 ? 's' : ''}`)
    if (medRiskSegs > 0) reasons.push(`Includes ${medRiskSegs} moderate risk segment${medRiskSegs > 1 ? 's' : ''}`)
    if (lowRiskSegs > 0) reasons.push(`Covers ${lowRiskSegs} low risk segment${lowRiskSegs > 1 ? 's' : ''}`)
  } else {
    if (type === 'safest') reasons.push('Lower recent incident density along calculated path')
    else if (type === 'fastest') reasons.push('Direct travel path prioritized for minimum travel time')
    else reasons.push('Balanced travel duration with community safety coverage')
  }

  return reasons
}

export function RoutePanel({ onClose }: RoutePanelProps) {
  const [destination, setDestination] = React.useState<{ label: string; lat: number; lng: number } | null>(null)
  const [activeType, setActiveType] = React.useState<'safest' | 'fastest' | 'balanced'>('safest')
  const { position } = useGeolocation()
  const locationName = useLocationName(position.latitude, position.longitude)
  const { routeResult, selectedRoute, isLoading, error, calculateRoute, selectRoute, clearRoute } = useRouteSafety()

  const handleSelectDestination = (dest: { label: string; lat: number; lng: number }) => {
    setDestination(dest)
    if (position.latitude && position.longitude) {
      calculateRoute(
        { lat: position.latitude, lng: position.longitude },
        { lat: dest.lat, lng: dest.lng }
      )
    }
  }

  const handleSelectRoute = (type: typeof activeType) => {
    setActiveType(type)
    if (routeResult) selectRoute(type)
  }

  return (
    <div className="absolute top-4 left-4 z-[1000] w-84 rounded-2xl avana-surface shadow-2xl overflow-hidden border border-[#1D3823]">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#1D3823] bg-[#07110A]">
        <div className="flex items-center gap-2">
          <Navigation className="h-4 w-4 text-[#66BB6A]" />
          <span className="text-xs font-bold text-[#F1F8F2] tracking-tight">SAFE ROUTE INTELLIGENCE</span>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-[#122417] transition-colors text-[#8A948C]"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      <div className="p-3.5 space-y-3">
        {/* Origin (Current location) */}
        <div className="space-y-2">
          <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-[#122417] border border-[#1D3823]">
            <span className="w-2 h-2 rounded-full bg-[#66BB6A] shrink-0" />
            <div className="min-w-0 flex-1">
              <span className="text-[10px] font-bold text-[#8A948C] uppercase block">Start Location</span>
              <span className="text-xs text-[#F1F8F2] truncate block">
                {locationName.displayName || 'Current Location (GPS Active)'}
              </span>
            </div>
          </div>

          <div className="flex justify-center my-0.5">
            <ArrowDown className="h-3.5 w-3.5 text-[#1D3823]" />
          </div>

          {/* Destination Search Component */}
          <div>
            <span className="text-[10px] font-bold text-[#8A948C] uppercase mb-1 block">Destination</span>
            <SearchDestination
              value={destination?.label || ''}
              onSelectDestination={handleSelectDestination}
              onClear={() => {
                setDestination(null)
                clearRoute()
              }}
            />
          </div>
        </div>

        {/* Loading state */}
        {isLoading && (
          <div className="flex items-center justify-center gap-2 py-4 text-xs text-[#9BAF9F]">
            <Loader2 className="h-4 w-4 animate-spin text-[#66BB6A]" />
            Analyzing safe routes...
          </div>
        )}

        {/* Error message */}
        {error && (
          <div className="p-3 rounded-xl bg-[#EF4444]/10 border border-[#EF4444]/20 text-xs text-[#EF4444]">
            {error}
          </div>
        )}

        {/* Route options selection */}
        {routeResult && !isLoading && (
          <div className="space-y-3 pt-2 border-t border-[#1D3823]">
            <p className="text-[10px] font-bold text-[#8A948C] uppercase tracking-wider">Calculated Options</p>

            {ROUTE_TYPES.map(({ value, icon: Icon, label, color, bg }) => {
              const opt = routeResult[value]
              const risk = getRiskBadge(opt.safetyScore)
              const isSelected = activeType === value
              return (
                <button
                  key={value}
                  onClick={() => handleSelectRoute(value)}
                  className="w-full flex items-center gap-3 p-3 rounded-xl text-left transition-all"
                  style={{
                    background: isSelected ? bg : '#122417',
                    border: `1px solid ${isSelected ? color : '#1D3823'}`,
                  }}
                >
                  <div
                    className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0"
                    style={{ background: isSelected ? color : '#0D1A10', color: isSelected ? '#07110A' : color }}
                  >
                    <Icon className="h-3.5 w-3.5" />
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-[#F1F8F2]">{label}</span>
                      <span className="text-xs font-bold text-[#F1F8F2]">{formatDuration(opt.duration)}</span>
                    </div>
                    <div className="flex items-center justify-between mt-0.5">
                      <span className="text-[10px] font-extrabold" style={{ color: risk.color }}>
                        {risk.label}
                      </span>
                      <span className="text-[10px] text-[#8A948C]">{formatDistance(opt.distance)}</span>
                    </div>
                  </div>
                </button>
              )
            })}

            {/* Why This Route Explanation Card */}
            {selectedRoute && (
              <div className="p-3 rounded-xl bg-[#122417] border border-[#1D3823] space-y-2">
                <div className="flex items-center gap-1.5">
                  <Info className="h-3.5 w-3.5 text-[#66BB6A]" />
                  <span className="text-xs font-bold text-[#F1F8F2]">WHY THIS ROUTE?</span>
                </div>
                <ul className="space-y-1">
                  {getRouteTrustInfo(routeResult[activeType], activeType).map((reason, i) => (
                    <li key={i} className="flex items-start gap-1.5 text-[11px] text-[#9BAF9F] leading-snug">
                      <CheckCircle2 className="h-3 w-3 text-[#66BB6A] shrink-0 mt-0.5" />
                      <span>{reason}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Action buttons */}
            <div className="flex gap-2">
              <button
                onClick={clearRoute}
                className="flex-1 py-2 rounded-xl text-xs font-semibold text-[#8A948C] bg-[#07110A] border border-[#1D3823] hover:text-[#F1F8F2]"
              >
                Clear Route
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

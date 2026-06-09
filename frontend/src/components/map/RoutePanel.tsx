import * as React from 'react'
import {
  Navigation,
  ArrowRight,
  MapPin,
  Loader2,
  Target,
  Shield,
  Zap,
  Scale,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { cn, formatDistance, formatDuration } from '@/lib/utils'
import { useRouteSafety } from '@/hooks/useRouteSafety'
import { useGeolocation } from '@/hooks/useGeolocation'

interface RoutePanelProps {
  onClose?: () => void
}

export function RoutePanel({ onClose }: RoutePanelProps) {
  const [from, setFrom] = React.useState('')
  const [to, setTo] = React.useState('')
  const [routeType, setRouteType] = React.useState<'safest' | 'fastest' | 'balanced'>('balanced')
  const { position } = useGeolocation()
  const { routeResult, selectedRoute, isLoading, error, calculateRoute, selectRoute, clearRoute } = useRouteSafety()

  React.useEffect(() => {
    if (position.latitude && position.longitude) {
      setFrom(`${position.latitude.toFixed(4)}, ${position.longitude.toFixed(4)}`)
    }
  }, [position])

  const handleFindRoute = async () => {
    if (!position.latitude || !position.longitude) return
    const destMatch = to.match(/(-?\d+\.?\d*),\s*(-?\d+\.?\d*)/)
    if (!destMatch) return

    await calculateRoute(
      { lat: position.latitude, lng: position.longitude },
      { lat: parseFloat(destMatch[1]), lng: parseFloat(destMatch[2]) }
    )
  }

  const routeTypes = [
    { value: 'safest' as const, icon: Shield, label: 'Safest', color: 'text-safety-500' },
    { value: 'fastest' as const, icon: Zap, label: 'Fastest', color: 'text-warning-500' },
    { value: 'balanced' as const, icon: Scale, label: 'Balanced', color: 'text-primary' },
  ]

  return (
    <div className="absolute top-4 left-4 z-[1000] w-80 rounded-xl border border-border bg-card shadow-2xl backdrop-blur-xl">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <Navigation className="h-4 w-4 text-primary" />
          <span className="text-sm font-medium">Find Safe Route</span>
        </div>
        {onClose && (
          <button onClick={onClose} className="rounded-md p-1 hover:bg-accent transition-colors text-muted-foreground">
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      <div className="p-4 space-y-3">
        <div className="relative">
          <div className="absolute left-3 top-1/2 -translate-y-1/2">
            <div className="h-3 w-3 rounded-full bg-safety-500 border-2 border-card" />
          </div>
          <Input
            placeholder="From (auto: your location)"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
            className="pl-8 h-9 text-sm"
          />
        </div>

        <div className="flex items-center justify-center">
          <ArrowRight className="h-4 w-4 text-muted-foreground" />
        </div>

        <div className="relative">
          <div className="absolute left-3 top-1/2 -translate-y-1/2">
            <div className="h-3 w-3 rounded-full bg-danger-500 border-2 border-card" />
          </div>
          <Input
            placeholder="Destination (lat, lng)"
            value={to}
            onChange={(e) => setTo(e.target.value)}
            className="pl-8 h-9 text-sm"
          />
        </div>

        {!routeResult && (
          <div className="flex gap-2">
            {routeTypes.map(({ value, icon: Icon, label, color }) => (
              <button
                key={value}
                onClick={() => setRouteType(value)}
                className={cn(
                  'flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors border',
                  routeType === value
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border text-muted-foreground hover:bg-accent'
                )}
              >
                <Icon className="h-3 w-3" />
                {label}
              </button>
            ))}
          </div>
        )}

        <Button
          className="w-full h-9"
          onClick={handleFindRoute}
          disabled={isLoading || !to}
        >
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
          ) : (
            <Navigation className="h-4 w-4 mr-2" />
          )}
          {isLoading ? 'Finding Route...' : 'Find Route'}
        </Button>

        {error && (
          <div className="rounded-md bg-danger-500/10 border border-danger-500/20 p-2 text-xs text-danger-500">
            {error}
          </div>
        )}

        {isLoading && (
          <div className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        )}

        {routeResult && selectedRoute && (
          <div className="space-y-3">
            <Separator />
            <div className="flex gap-2">
              {routeTypes.map(({ value, icon: Icon, label, color }) => (
                <button
                  key={value}
                  onClick={() => selectRoute(value)}
                  className={cn(
                    'flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors border',
                    selectedRoute === routeResult[value]
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border text-muted-foreground hover:bg-accent'
                  )}
                >
                  <Icon className={cn('h-3 w-3', routeResult[value] === selectedRoute && color)} />
                  {label}
                </button>
              ))}
            </div>

            <div className="grid grid-cols-3 gap-2">
              <div className="rounded-md bg-muted/50 p-2 text-center">
                <p className="text-lg font-bold text-safety-500">
                  {selectedRoute.safetyScore >= 0.8 ? 'A' :
                   selectedRoute.safetyScore >= 0.6 ? 'B' :
                   selectedRoute.safetyScore >= 0.4 ? 'C' : 'D'}
                </p>
                <p className="text-xs text-muted-foreground">Safety</p>
              </div>
              <div className="rounded-md bg-muted/50 p-2 text-center">
                <p className="text-lg font-bold">{formatDistance(selectedRoute.distance)}</p>
                <p className="text-xs text-muted-foreground">Distance</p>
              </div>
              <div className="rounded-md bg-muted/50 p-2 text-center">
                <p className="text-lg font-bold">{formatDuration(selectedRoute.duration)}</p>
                <p className="text-xs text-muted-foreground">Duration</p>
              </div>
            </div>

            <Button variant="outline" size="sm" className="w-full" onClick={clearRoute}>
              Clear Route
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}

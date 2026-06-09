import * as React from 'react'
import { X, Shield, Hospital, AlertTriangle, Navigation, Flag, Lightbulb } from 'lucide-react'
import { useMapStore } from '@/store/mapStore'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { getRiskColor, formatDistance, formatRelativeTime } from '@/lib/utils'
import type { RiskScore, Incident, PoliceStation, Hospital as HospitalType } from '@/types'
import { riskApi } from '@/services/api'

interface LocationInfoPanelProps {
  onReportArea?: () => void
  onGetSafeRoute?: () => void
  onClose?: () => void
}

export function LocationInfoPanel({ onReportArea, onGetSafeRoute, onClose }: LocationInfoPanelProps) {
  const { selectedLocation, setSelectedLocation } = useMapStore()
  const [riskScore, setRiskScore] = React.useState<RiskScore | null>(null)
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const [recentIncidents] = React.useState<Incident[]>([])
  const [nearbyPolice] = React.useState<PoliceStation[]>([])
  const [nearbyHospitals] = React.useState<HospitalType[]>([])

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

  const riskAngle = riskScore ? riskScore.score * 360 : 0
  const riskColor = riskScore ? getRiskColor(riskScore.score) : '#94a3b8'

  const handleClose = () => {
    setSelectedLocation(null)
    onClose?.()
  }

  return (
    <div className="absolute bottom-0 left-0 right-0 z-[1000] mx-auto max-w-lg">
      <div className="rounded-t-xl border border-border bg-card shadow-2xl backdrop-blur-xl">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2">
            <MapPin className="h-4 w-4 text-primary" />
            <span className="text-sm font-medium">Location Info</span>
          </div>
          <button
            onClick={handleClose}
            className="rounded-md p-1 hover:bg-accent transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <ScrollArea className="max-h-[60vh]">
          <div className="p-4 space-y-4">
            <div className="flex items-center gap-4">
              <div className="relative flex items-center justify-center">
                <svg className="h-20 w-20 -rotate-90" viewBox="0 0 72 72">
                  <circle cx="36" cy="36" r="30" fill="none" stroke="currentColor" strokeWidth="4"
                    className="text-muted" />
                  <circle cx="36" cy="36" r="30" fill="none" stroke={riskColor} strokeWidth="4"
                    strokeDasharray={`${riskAngle} 360`} strokeLinecap="round"
                    className="transition-all duration-1000" />
                </svg>
                <span className="absolute text-lg font-bold">{riskScore ? Math.round(riskScore.score * 100) : '--'}</span>
              </div>
              <div className="space-y-1">
                <p className="text-sm font-medium">Risk Score</p>
                {isLoading ? (
                  <Skeleton className="h-6 w-20" />
                ) : riskScore ? (
                  <Badge variant={
                    riskScore.category === 'critical' ? 'critical' :
                    riskScore.category === 'high' ? 'danger' :
                    riskScore.category === 'moderate' ? 'warning' :
                    riskScore.category === 'low' ? 'success' : 'secondary'
                  } className="capitalize">
                    {riskScore.category}
                  </Badge>
                ) : null}
                <p className="text-xs text-muted-foreground">
                  {selectedLocation.lat.toFixed(4)}, {selectedLocation.lng.toFixed(4)}
                </p>
              </div>
            </div>

            {error && (
              <div className="rounded-md bg-danger-500/10 border border-danger-500/20 p-2 text-xs text-danger-500">
                {error}
              </div>
            )}

            {riskScore && riskScore.recommendations.length > 0 && (
              <div className="rounded-lg bg-primary/5 border border-primary/10 p-3">
                <div className="flex items-center gap-2 mb-2">
                  <Lightbulb className="h-4 w-4 text-warning-500" />
                  <span className="text-xs font-medium">AI Safety Tip</span>
                </div>
                <p className="text-xs text-muted-foreground">{riskScore.recommendations[0]}</p>
              </div>
            )}

            {recentIncidents.length > 0 && (
              <>
                <Separator />
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground mb-2">
                    Recent Incidents ({recentIncidents.length})
                  </h4>
                  <div className="space-y-2">
                    {recentIncidents.slice(0, 5).map((inc) => (
                      <div key={inc.id} className="flex items-start gap-2 text-xs">
                        <AlertTriangle className="h-3 w-3 mt-0.5 text-danger-500 shrink-0" />
                        <div>
                          <p className="font-medium">{inc.title}</p>
                          <p className="text-muted-foreground">{formatRelativeTime(inc.reportedAt)}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}

            {nearbyPolice.length > 0 && (
              <>
                <Separator />
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground mb-2">
                    Nearby Police Stations
                  </h4>
                  <div className="space-y-2">
                    {nearbyPolice.map((station) => (
                      <div key={station.id} className="flex items-center gap-2 text-xs">
                        <Shield className="h-3 w-3 text-blue-500 shrink-0" />
                        <span className="flex-1">{station.name}</span>
                        <span className="text-muted-foreground">
                          {formatDistance(Math.random() * 2000)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}

            {nearbyHospitals.length > 0 && (
              <>
                <Separator />
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground mb-2">
                    Nearby Hospitals
                  </h4>
                  <div className="space-y-2">
                    {nearbyHospitals.map((hospital) => (
                      <div key={hospital.id} className="flex items-center gap-2 text-xs">
                        <Hospital className="h-3 w-3 text-red-500 shrink-0" />
                        <span className="flex-1">{hospital.name}</span>
                        <span className="text-muted-foreground">
                          {formatDistance(Math.random() * 3000)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>
        </ScrollArea>

        <div className="flex gap-2 p-4 pt-0">
          <Button variant="outline" size="sm" className="flex-1" onClick={onReportArea}>
            <Flag className="h-3 w-3 mr-1" />
            Report Area
          </Button>
          <Button variant="primary" size="sm" className="flex-1" onClick={onGetSafeRoute}>
            <Navigation className="h-3 w-3 mr-1" />
            Safe Route
          </Button>
        </div>
      </div>
    </div>
  )
}

function MapPin({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  )
}

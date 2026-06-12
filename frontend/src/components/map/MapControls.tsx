import * as React from 'react'
import {
  Crosshair,
  Layers,
  MapPin,
  Shield,
  Hospital,
  Flame,
  Plus,
} from 'lucide-react'
import { useMap } from 'react-leaflet'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { useMapStore } from '@/store/mapStore'
import { Separator } from '@/components/ui/separator'
import { useUIStore } from '@/store/uiStore'

interface MapControlsProps {
  onReportIncident?: () => void
}

export function MapControls({ onReportIncident }: MapControlsProps) {
  const map = useMap()
  const { addToast } = useUIStore()
  const {
    mapType,
    setMapType,
    setSelectedLocation,
    selectedLocation,
  } = useMapStore()
  const [layersOpen, setLayersOpen] = React.useState(false)
  const [showLayers, setShowLayers] = React.useState({
    heatmap: true,
    incidents: true,
    police: true,
    hospitals: true,
  })
  const [legendOpen, setLegendOpen] = React.useState(false)

  const handleRecenter = () => {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        map.flyTo([pos.coords.latitude, pos.coords.longitude], 15)
      },
      (err) => {
        const msg = err.code === err.PERMISSION_DENIED
          ? 'Location permission denied. Please enable in browser settings.'
          : err.code === err.TIMEOUT
          ? 'Location request timed out. Try again.'
          : 'Could not get your location.'
        addToast({ title: 'Location Error', description: msg, variant: 'destructive' })
        map.flyTo([12.9716, 77.5946], 12)
      }
    )
  }

  const toggleLayer = (layer: keyof typeof showLayers) => {
    setShowLayers((prev) => ({ ...prev, [layer]: !prev[layer] }))
  }

  return (
    <div className="absolute top-4 right-4 z-[1000] flex flex-col gap-2">
      <Button
        variant="secondary"
        size="icon"
        className="h-9 w-9 bg-card/90 backdrop-blur border border-border shadow-lg"
        onClick={handleRecenter}
        title="Recenter to location"
      >
        <Crosshair className="h-4 w-4" />
      </Button>

      <div className="relative">
        <Button
          variant="secondary"
          size="icon"
          className="h-9 w-9 bg-card/90 backdrop-blur border border-border shadow-lg"
          onClick={() => setLayersOpen(!layersOpen)}
          title="Toggle layers"
        >
          <Layers className="h-4 w-4" />
        </Button>

        {layersOpen && (
          <div className="absolute right-0 top-10 w-48 rounded-lg border border-border bg-card p-2 shadow-xl backdrop-blur">
            <p className="px-2 py-1 text-xs font-medium text-muted-foreground">Map Layers</p>
            {Object.entries(showLayers).map(([key, value]) => (
              <button
                key={key}
                className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent transition-colors"
                onClick={() => toggleLayer(key as keyof typeof showLayers)}
              >
                <div className={cn(
                  'h-4 w-4 rounded border border-border flex items-center justify-center transition-colors',
                  value && 'bg-primary border-primary'
                )}>
                  {value && <div className="h-2 w-2 rounded-sm bg-white" />}
                </div>
                <span className="capitalize">{key}</span>
              </button>
            ))}
            <Separator className="my-2" />
            <button
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent transition-colors"
              onClick={() => setLegendOpen(!legendOpen)}
            >
              <MapPin className="h-4 w-4" />
              Legend
            </button>
          </div>
        )}
      </div>

      {legendOpen && (
        <div className="absolute right-0 top-20 w-48 rounded-lg border border-border bg-card p-3 shadow-xl backdrop-blur">
          <p className="text-xs font-medium mb-2">Legend</p>
          <div className="space-y-1.5">
            <div className="flex items-center gap-2 text-xs">
              <div className="h-3 w-3 rounded-full border-2 border-white shadow-sm" style={{ background: '#7c3aed' }} />
              Critical
            </div>
            <div className="flex items-center gap-2 text-xs">
              <div className="h-3 w-3 rounded-full border-2 border-white shadow-sm" style={{ background: '#ef4444' }} />
              High
            </div>
            <div className="flex items-center gap-2 text-xs">
              <div className="h-3 w-3 rounded-full border-2 border-white shadow-sm" style={{ background: '#f59e0b' }} />
              Medium
            </div>
            <div className="flex items-center gap-2 text-xs">
              <div className="h-3 w-3 rounded-full border-2 border-white shadow-sm" style={{ background: '#22c55e' }} />
              Low
            </div>
            <Separator className="my-1" />
            <div className="flex items-center gap-2 text-xs">
              <Shield className="h-3 w-3 text-blue-500" />
              Police Station
            </div>
            <div className="flex items-center gap-2 text-xs">
              <Hospital className="h-3 w-3 text-red-500" />
              Hospital
            </div>
            <div className="flex items-center gap-2 text-xs">
              <div className="h-3 w-3 rounded-full bg-blue-500 border-2 border-white" />
              Your Location
            </div>
          </div>
        </div>
      )}

      <Button
        variant="secondary"
        size="icon"
        className="h-9 w-9 bg-card/90 backdrop-blur border border-border shadow-lg"
        onClick={onReportIncident}
        title="Report incident"
      >
        <Plus className="h-4 w-4" />
      </Button>
    </div>
  )
}

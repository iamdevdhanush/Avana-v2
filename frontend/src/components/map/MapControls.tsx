import * as React from 'react'
import { Crosshair, Layers } from 'lucide-react'
import { useMap } from 'react-leaflet'
import { useMapStore } from '@/store/mapStore'
import { HeatmapLegend } from './HeatmapLegend'
import { useUIStore } from '@/store/uiStore'

export function MapControls() {
  const map = useMap()
  const { addToast } = useUIStore()
  const [showLegend, setShowLegend] = React.useState(false)

  const handleRecenter = () => {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        map.flyTo([pos.coords.latitude, pos.coords.longitude], 15)
      },
      (err) => {
        const msg = err.code === err.PERMISSION_DENIED
          ? 'Location permission denied.'
          : err.code === err.TIMEOUT
          ? 'Location request timed out.'
          : 'Could not get your location.'
        addToast({ title: 'Location Error', description: msg, variant: 'destructive' })
        map.flyTo([12.9716, 77.5946], 12)
      },
    )
  }

  return (
    <>
      {/* Top-right controls */}
      <div className="absolute top-4 right-4 z-[1000] flex flex-col gap-2">
        <button
          onClick={handleRecenter}
          className="h-9 w-9 flex items-center justify-center rounded-xl transition-all"
          style={{
            background: 'rgba(15,15,22,0.9)',
            border: '1px solid rgba(255,255,255,0.08)',
            backdropFilter: 'blur(12px)',
            color: '#9CA3AF',
          }}
          title="Recenter"
        >
          <Crosshair className="h-4 w-4" />
        </button>

        <button
          onClick={() => setShowLegend(!showLegend)}
          className="h-9 w-9 flex items-center justify-center rounded-xl transition-all"
          style={{
            background: showLegend ? 'rgba(255,23,68,0.2)' : 'rgba(15,15,22,0.9)',
            border: `1px solid ${showLegend ? 'rgba(255,23,68,0.3)' : 'rgba(255,255,255,0.08)'}`,
            backdropFilter: 'blur(12px)',
            color: showLegend ? '#FF1744' : '#9CA3AF',
          }}
          title="Legend"
        >
          <Layers className="h-4 w-4" />
        </button>
      </div>

      {/* Legend panel - bottom left */}
      {showLegend && (
        <div className="absolute bottom-6 left-3 z-[1000]">
          <HeatmapLegend visible />
        </div>
      )}
    </>
  )
}

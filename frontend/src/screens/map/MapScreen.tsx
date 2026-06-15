import * as React from 'react'
import { Loader2 } from 'lucide-react'
import { SafetyMap } from '@/components/map/SafetyMap'
import { MapControls } from '@/components/map/MapControls'
import { LocationInfoPanel } from '@/components/map/LocationInfoPanel'
import { RoutePanel } from '@/components/map/RoutePanel'
import { useMapStore } from '@/store/mapStore'
import { useGeolocation } from '@/hooks/useGeolocation'
import { useHeatmap } from '@/hooks/useHeatmap'
import { DataFreshness } from '@/components/DataFreshness'

export function MapScreen() {
  const { bounds, zoom, selectedLocation, setSelectedLocation } = useMapStore()
  const { position } = useGeolocation()
  const {
    points: heatmapPoints,
    generatedAt,
    districtSummaries,
    isLoading: heatmapLoading,
  } = useHeatmap(bounds, zoom)

  const [showRoutePanel, setShowRoutePanel] = React.useState(false)

  const handleHotspotClick = (lat: number, lng: number) => {
    setSelectedLocation({ lat, lng })
    setShowRoutePanel(false)
  }

  return (
    <div className="relative w-full" style={{ height: 'calc(100vh - 48px - 64px)' }}>
      <SafetyMap
        heatmapPoints={heatmapPoints}
        showHeatmap
        userLocation={
          position.latitude && position.longitude
            ? { lat: position.latitude, lng: position.longitude }
            : null
        }
        onHotspotClick={handleHotspotClick}
      >
        <MapControls />
      </SafetyMap>

      {/* Heatmap freshness + district summaries (bottom left) */}
      <div className="absolute bottom-24 left-3 z-[1000] space-y-2">
        <div
          className="px-2.5 py-1.5 rounded-xl"
          style={{
            background: 'rgba(9,9,11,0.88)',
            border: '1px solid rgba(255,255,255,0.06)',
            backdropFilter: 'blur(12px)',
          }}
        >
          <DataFreshness
            timestamp={generatedAt}
            label="Heatmap"
            warnAfterHours={24}
            compact
          />
        </div>

        {districtSummaries.length > 0 && (
          <div
            className="px-2.5 py-2 rounded-xl space-y-1.5"
            style={{
              background: 'rgba(9,9,11,0.88)',
              border: '1px solid rgba(255,255,255,0.06)',
              backdropFilter: 'blur(12px)',
              maxWidth: '180px',
            }}
          >
            <p className="text-[10px] font-semibold text-[#6B7280] uppercase tracking-wide">District Risk</p>
            {districtSummaries.slice(0, 3).map((s) => (
              <div key={s.district} className="flex items-center justify-between gap-2">
                <span className="text-[10px] text-[#9CA3AF] truncate">{s.district.split(' ')[0]}</span>
                <span
                  className="text-[10px] font-semibold shrink-0"
                  style={{
                    color: s.trend === 'worsening' ? '#FF1744' : s.trend === 'improving' ? '#00E676' : '#FFD600',
                  }}
                >
                  {s.trend === 'worsening' ? '↑' : s.trend === 'improving' ? '↓' : '→'}
                  {' '}{s.trend}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Loading indicator */}
      {heatmapLoading && (
        <div className="absolute top-14 left-1/2 -translate-x-1/2 z-[1000]">
          <div
            className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs"
            style={{
              background: 'rgba(9,9,11,0.85)',
              border: '1px solid rgba(255,255,255,0.06)',
              backdropFilter: 'blur(12px)',
              color: '#9CA3AF',
            }}
          >
            <Loader2 className="h-3 w-3 animate-spin" style={{ color: '#FF1744' }} />
            Loading heatmap...
          </div>
        </div>
      )}

      {/* Route Panel */}
      {showRoutePanel && (
        <RoutePanel onClose={() => setShowRoutePanel(false)} />
      )}

      {/* Location Info Panel (bottom sheet) */}
      {selectedLocation && !showRoutePanel && (
        <LocationInfoPanel
          onGetSafeRoute={() => {
            setShowRoutePanel(true)
            setSelectedLocation(null)
          }}
          onClose={() => setSelectedLocation(null)}
        />
      )}

      {/* Find Safe Route FAB */}
      {!showRoutePanel && !selectedLocation && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-[1000]">
          <button
            onClick={() => setShowRoutePanel(true)}
            className="flex items-center gap-2 px-5 py-3 rounded-2xl text-sm font-bold text-white shadow-xl transition-all hover:scale-105 active:scale-95"
            style={{
              background: 'linear-gradient(135deg, #FF1744 0%, #D50000 100%)',
              boxShadow: '0 8px 32px rgba(255,23,68,0.4)',
            }}
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z" />
            </svg>
            Find Safe Route
          </button>
        </div>
      )}
    </div>
  )
}

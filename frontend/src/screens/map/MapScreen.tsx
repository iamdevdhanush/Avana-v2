import * as React from 'react'
import { Loader2, Navigation, MapPin } from 'lucide-react'
import { SafetyMap } from '@/components/map/SafetyMap'
import { MapControls } from '@/components/map/MapControls'
import { RiskIntelligencePanel } from '@/components/map/RiskIntelligencePanel'
import { RoutePanel } from '@/components/map/RoutePanel'
import { useMapStore } from '@/store/mapStore'
import { useGeolocation } from '@/hooks/useGeolocation'
import { useHeatmap } from '@/hooks/useHeatmap'
import { DataFreshness } from '@/components/DataFreshness'

export function MapScreen() {
  const bounds = useMapStore((s) => s.bounds)
  const zoom = useMapStore((s) => s.zoom)
  const selectedLocation = useMapStore((s) => s.selectedLocation)
  const setSelectedLocation = useMapStore((s) => s.setSelectedLocation)
  const { position } = useGeolocation()
  const {
    points: heatmapPoints,
    generatedAt,
    districtSummaries,
    isLoading: heatmapLoading,
  } = useHeatmap(bounds, zoom)

  const [showRoutePanel, setShowRoutePanel] = React.useState(false)
  const autoSelectedRef = React.useRef(false)

  React.useEffect(() => {
    if (position.latitude && position.longitude && !autoSelectedRef.current) {
      autoSelectedRef.current = true
      setSelectedLocation({ lat: position.latitude, lng: position.longitude })
    }
  }, [position.latitude, position.longitude, setSelectedLocation])

  const handleHotspotClick = React.useCallback((lat: number, lng: number) => {
    setSelectedLocation({ lat, lng })
    setShowRoutePanel(false)
  }, [setSelectedLocation])

  const handleGetSafeRoute = React.useCallback(() => {
    setShowRoutePanel(true)
    setSelectedLocation(null)
  }, [setSelectedLocation])

  const handleClosePanel = React.useCallback(() => {
    setSelectedLocation(null)
  }, [setSelectedLocation])

  const handleCloseRoute = React.useCallback(() => {
    setShowRoutePanel(false)
  }, [])

  const handleOpenRoute = React.useCallback(() => {
    setShowRoutePanel(true)
  }, [])

  return (
    <div
      className="relative w-full bg-[#07110A]"
      style={{
        height: 'calc(100vh - 52px - 64px - env(safe-area-inset-bottom, 0px))',
      }}
    >
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

      {/* Heatmap freshness & District risk pill (bottom left) */}
      <div className="absolute bottom-20 left-3 z-[1000] space-y-2 pointer-events-none">
        <div
          className="px-2.5 py-1.5 rounded-xl pointer-events-auto avana-surface"
          style={{
            background: 'rgba(7,17,10,0.92)',
            backdropFilter: 'blur(12px)',
          }}
        >
          <DataFreshness
            timestamp={generatedAt}
            label="Risk Intelligence Layer"
            warnAfterHours={24}
            compact
          />
        </div>

        {districtSummaries.length > 0 && (
          <div
            className="px-3 py-2 rounded-xl space-y-1 pointer-events-auto avana-surface"
            style={{
              background: 'rgba(7,17,10,0.92)',
              backdropFilter: 'blur(12px)',
              maxWidth: '190px',
            }}
          >
            <p className="text-[10px] font-bold text-[#8A948C] uppercase tracking-wider">Regional Activity</p>
            {districtSummaries.slice(0, 3).map((s) => (
              <div key={s.district} className="flex items-center justify-between gap-2">
                <span className="text-[10px] text-[#9BAF9F] truncate">{s.district.split(' ')[0]}</span>
                <span
                  className="text-[10px] font-bold shrink-0"
                  style={{
                    color: s.trend === 'worsening' ? '#EF4444' : s.trend === 'improving' ? '#66BB6A' : '#F5B942',
                  }}
                >
                  {s.trend === 'worsening' ? '↑ High' : s.trend === 'improving' ? '↓ Low' : '→ Stable'}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Loading bar */}
      {heatmapLoading && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-[1000] pointer-events-none">
          <div
            className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs pointer-events-auto avana-surface shadow-xl"
            style={{
              background: 'rgba(7,17,10,0.92)',
              backdropFilter: 'blur(12px)',
              color: '#9BAF9F',
            }}
          >
            <Loader2 className="h-3 w-3 animate-spin text-[#66BB6A]" />
            Syncing area intelligence...
          </div>
        </div>
      )}

      {/* Route Panel Overlay */}
      {showRoutePanel && (
        <RoutePanel onClose={handleCloseRoute} />
      )}

      {/* Risk Intelligence Panel (Bottom Sheet) */}
      {selectedLocation && !showRoutePanel && (
        <RiskIntelligencePanel
          onGetSafeRoute={handleGetSafeRoute}
          onClose={handleClosePanel}
        />
      )}

      {/* Safe Route Trigger FAB */}
      {!showRoutePanel && !selectedLocation && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-[1000] pointer-events-none">
          <button
            onClick={handleOpenRoute}
            className="flex items-center gap-2 px-5 py-3 rounded-2xl text-xs font-bold text-[#07110A] bg-[#66BB6A] hover:bg-[#81C784] shadow-xl transition-all hover:scale-105 active:scale-95 pointer-events-auto border border-[#66BB6A]"
          >
            <Navigation className="h-4 w-4" />
            Find Safe Route
          </button>
        </div>
      )}
    </div>
  )
}

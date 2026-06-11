import * as React from 'react'
import {
  Layers, Locate, SlidersHorizontal, X, Loader2, ChevronDown,
} from 'lucide-react'
import { SafetyMap } from '@/components/map/SafetyMap'
import { MapControls } from '@/components/map/MapControls'
import { LocationInfoPanel } from '@/components/map/LocationInfoPanel'
import { RoutePanel } from '@/components/map/RoutePanel'
import { HeatmapLegend } from '@/components/map/HeatmapLegend'
import { useMapStore } from '@/store/mapStore'
import { useGeolocation } from '@/hooks/useGeolocation'
import { useHeatmap } from '@/hooks/useHeatmap'
import { incidentApi } from '@/services/api'
import { cn } from '@/lib/utils'
import type { Incident } from '@/types'

const INCIDENT_TYPE_FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'theft', label: 'Theft' },
  { value: 'assault', label: 'Assault' },
  { value: 'harassment', label: 'Harassment' },
  { value: 'suspicious', label: 'Suspicious' },
  { value: 'traffic', label: 'Traffic' },
  { value: 'medical', label: 'Medical' },
]

const LAYER_TOGGLES = [
  { key: 'heatmap',   label: 'Heatmap',   color: '#A855F7' },
  { key: 'incidents', label: 'Incidents',  color: '#EF4444' },
  { key: 'police',    label: 'Police',     color: '#3B82F6' },
  { key: 'hospitals', label: 'Hospitals',  color: '#22C55E' },
]

export function MapScreen() {
  const { bounds, zoom, selectedLocation, setSelectedLocation } = useMapStore()
  const { position } = useGeolocation()
  const { points: heatmapPoints, isLoading: heatmapLoading } = useHeatmap(bounds, zoom)

  const [incidents, setIncidents] = React.useState<Incident[]>([])
  const [incidentsLoading, setIncidentsLoading] = React.useState(false)

  const [showRoutePanel, setShowRoutePanel] = React.useState(false)
  const [showFilters, setShowFilters] = React.useState(false)
  const [showLayers, setShowLayers] = React.useState(false)
  const [selectedType, setSelectedType] = React.useState('all')

  const [layers, setLayers] = React.useState({
    heatmap: true,
    incidents: true,
    police: false,
    hospitals: false,
  })

  // Fetch incidents when bounds change (debounced)
  const fetchTimer = React.useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  React.useEffect(() => {
    if (!bounds) return
    clearTimeout(fetchTimer.current)
    fetchTimer.current = setTimeout(() => {
      const centerLat = (bounds.north + bounds.south) / 2
      const centerLng = (bounds.east + bounds.west) / 2
      setIncidentsLoading(true)
      incidentApi.getIncidents({
        lat: centerLat,
        lng: centerLng,
        radius: 10,
        limit: 50,
        type: selectedType !== 'all' ? selectedType : undefined,
      })
        .then((res) => setIncidents(res.data))
        .catch(() => {})
        .finally(() => setIncidentsLoading(false))
    }, 500)
    return () => clearTimeout(fetchTimer.current)
  }, [bounds, selectedType])

  const toggleLayer = (key: string) => {
    setLayers(prev => ({ ...prev, [key]: !prev[key as keyof typeof prev] }))
  }

  return (
    <div className="relative w-full" style={{ height: 'calc(100vh - 48px - 64px)' }}>
      {/* The map — full size, behind everything */}
      <SafetyMap
        heatmapPoints={heatmapPoints}
        incidents={layers.incidents ? incidents : []}
        showHeatmap={layers.heatmap}
        showIncidents={layers.incidents}
        showPolice={layers.police}
        showHospitals={layers.hospitals}
        userLocation={
          position.latitude && position.longitude
            ? { lat: position.latitude, lng: position.longitude }
            : null
        }
        onLocationClick={(pos) => {
          setSelectedLocation(pos)
          setShowRoutePanel(false)
        }}
      >
        <MapControls onReportIncident={() => {}} />
      </SafetyMap>

      {/* ── Floating Filter Bar (top center) ── */}
      <div className="absolute top-3 left-1/2 -translate-x-1/2 z-[1000] flex flex-col items-center gap-2 w-full max-w-sm px-3">
        {/* Type filter chips */}
        <div className="flex gap-1.5 overflow-x-auto pb-0.5 w-full scrollbar-hide">
          {INCIDENT_TYPE_FILTERS.map((t) => (
            <button
              key={t.value}
              onClick={() => setSelectedType(t.value)}
              className="whitespace-nowrap px-3 py-1.5 rounded-full text-[11px] font-semibold transition-all shrink-0"
              style={{
                background: selectedType === t.value ? '#A855F7' : 'rgba(9,9,11,0.85)',
                color: selectedType === t.value ? '#fff' : '#9CA3AF',
                border: `1px solid ${selectedType === t.value ? '#A855F7' : 'rgba(255,255,255,0.08)'}`,
                backdropFilter: 'blur(12px)',
              }}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Layer Toggle (top right) ── */}
      <div className="absolute top-3 right-3 z-[1000]">
        <button
          onClick={() => setShowLayers(!showLayers)}
          className="flex items-center gap-1.5 px-2.5 py-2 rounded-xl text-xs font-semibold transition-all"
          style={{
            background: showLayers ? '#A855F7' : 'rgba(9,9,11,0.85)',
            color: showLayers ? '#fff' : '#D1D5DB',
            border: `1px solid ${showLayers ? '#A855F7' : 'rgba(255,255,255,0.08)'}`,
            backdropFilter: 'blur(12px)',
          }}
        >
          <Layers className="h-4 w-4" />
        </button>
        {showLayers && (
          <div
            className="absolute top-full right-0 mt-1.5 rounded-xl overflow-hidden shadow-2xl w-36"
            style={{ background: 'rgba(26,26,36,0.95)', border: '1px solid #1F2937', backdropFilter: 'blur(16px)' }}
          >
            {LAYER_TOGGLES.map(({ key, label, color }) => (
              <button
                key={key}
                onClick={() => toggleLayer(key)}
                className="w-full flex items-center justify-between px-3 py-2.5 text-xs hover:bg-[#1F2937] transition-colors"
              >
                <div className="flex items-center gap-2">
                  <div
                    className="w-2 h-2 rounded-full"
                    style={{ background: layers[key as keyof typeof layers] ? color : '#374151' }}
                  />
                  <span className="text-[#D1D5DB]">{label}</span>
                </div>
                <div
                  className="w-7 h-4 rounded-full transition-all"
                  style={{ background: layers[key as keyof typeof layers] ? color : '#374151' }}
                >
                  <div
                    className="w-3 h-3 rounded-full bg-white mt-0.5 transition-all"
                    style={{ marginLeft: layers[key as keyof typeof layers] ? '14px' : '2px' }}
                  />
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── Heatmap Legend (bottom left, above scale) ── */}
      {layers.heatmap && (
        <div className="absolute bottom-24 left-3 z-[1000]">
          <HeatmapLegend visible={layers.heatmap} />
        </div>
      )}

      {/* ── Loading indicator ── */}
      {(heatmapLoading || incidentsLoading) && (
        <div className="absolute top-14 left-1/2 -translate-x-1/2 z-[1000]">
          <div
            className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs"
            style={{
              background: 'rgba(9,9,11,0.85)',
              border: '1px solid rgba(255,255,255,0.08)',
              backdropFilter: 'blur(12px)',
              color: '#9CA3AF',
            }}
          >
            <Loader2 className="h-3 w-3 animate-spin text-[#A855F7]" />
            {heatmapLoading ? 'Loading heatmap...' : 'Updating incidents...'}
          </div>
        </div>
      )}

      {/* ── Route Panel ── */}
      {showRoutePanel && (
        <RoutePanel onClose={() => setShowRoutePanel(false)} />
      )}

      {/* ── Location Info Panel (bottom sheet) ── */}
      {selectedLocation && !showRoutePanel && (
        <LocationInfoPanel
          onGetSafeRoute={() => {
            setShowRoutePanel(true)
            setSelectedLocation(null)
          }}
          onClose={() => setSelectedLocation(null)}
        />
      )}

      {/* ── Find Safe Route FAB (bottom center, when no panel open) ── */}
      {!showRoutePanel && !selectedLocation && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-[1000]">
          <button
            onClick={() => setShowRoutePanel(true)}
            className="flex items-center gap-2 px-5 py-3 rounded-2xl text-sm font-bold text-white shadow-xl transition-all hover:scale-105 active:scale-95"
            style={{
              background: 'linear-gradient(135deg, #A855F7 0%, #9333EA 100%)',
              boxShadow: '0 8px 32px rgba(168,85,247,0.4)',
            }}
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z" />
              <circle cx="12" cy="9" r="2.5" />
            </svg>
            Find Safe Route
          </button>
        </div>
      )}
    </div>
  )
}

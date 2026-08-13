import { memo, useCallback, useEffect, useRef } from 'react'
import {
  MapContainer,
  TileLayer,
  Polyline,
  useMap,
  ScaleControl,
  ZoomControl,
} from 'react-leaflet'
import L from 'leaflet'
import { useMapStore } from '@/store/mapStore'
import { HeatmapLayer } from './HeatmapLayer'
import type { RouteOption, HeatmapPoint } from '@/types'

const userIcon = L.divIcon({
  className: '',
  html: `<div style="
    width: 12px; height: 12px;
    background: #66BB6A;
    border-radius: 50%;
    border: 2px solid #07110A;
    box-shadow: 0 0 0 4px rgba(102, 187, 106, 0.3);
  "></div>`,
  iconSize: [12, 12],
  iconAnchor: [6, 6],
})

function MapBoundsUpdater() {
  const map = useMap()
  const setBounds = useMapStore((s) => s.setBounds)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    const update = () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
      debounceRef.current = setTimeout(() => {
        const b = map.getBounds()
        setBounds({
          north: b.getNorth(),
          south: b.getSouth(),
          east: b.getEast(),
          west: b.getWest(),
        })
      }, 300)
    }
    map.on('moveend', update)
    update()
    return () => {
      map.off('moveend', update)
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [map, setBounds])
  return null
}

const StaticMarker = memo(function StaticMarker({ position, icon }: { position: [number, number]; icon: L.DivIcon }) {
  const map = useMap()
  const markerRef = useRef<L.Marker | null>(null)

  useEffect(() => {
    if (markerRef.current) {
      markerRef.current.setLatLng(position)
      return
    }
    const marker = L.marker(position, { icon, interactive: false }).addTo(map)
    markerRef.current = marker
    return () => {
      if (markerRef.current) {
        map.removeLayer(markerRef.current)
        markerRef.current = null
      }
    }
  }, [map, position, icon])

  return null
})

function getRouteColor(score: number, category?: string): string {
  if (category?.toLowerCase() === 'unknown') return '#8A948C'
  if (score >= 0.8) return '#66BB6A'
  if (score >= 0.6) return '#F5B942'
  if (score >= 0.4) return '#F97316'
  return '#EF4444'
}

interface SafetyMapProps {
  heatmapPoints?: HeatmapPoint[]
  selectedRoute?: RouteOption | null
  userLocation?: { lat: number; lng: number } | null
  showHeatmap?: boolean
  onHotspotClick?: (lat: number, lng: number, weight: number) => void
  children?: React.ReactNode
}

function AutoCenter({ position }: { position: { lat: number; lng: number } | null }) {
  const map = useMap()
  const doneRef = useRef(false)

  useEffect(() => {
    if (position && !doneRef.current) {
      doneRef.current = true
      map.flyTo([position.lat, position.lng], 13, { duration: 1.2 })
    }
  }, [position, map])

  return null
}

export const SafetyMap = memo(function SafetyMap({
  heatmapPoints = [],
  selectedRoute = null,
  userLocation = null,
  showHeatmap = true,
  onHotspotClick,
  children,
}: SafetyMapProps) {
  const { center, zoom, setSelectedLocation } = useMapStore()

  const handleHotspotClick = useCallback((lat: number, lng: number, w: number) => {
    setSelectedLocation({ lat, lng })
    onHotspotClick?.(lat, lng, w)
  }, [setSelectedLocation, onHotspotClick])

  return (
    <MapContainer
      center={center}
      zoom={zoom}
      className="h-full w-full"
      zoomControl={false}
      style={{ background: '#07110A' }}
    >
      <TileLayer
        attribution='&copy; <a href="https://carto.com/">CARTO</a>'
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      />
      <ScaleControl position="bottomleft" />
      <ZoomControl position="bottomright" />
      {children}
      <MapBoundsUpdater />
      {userLocation && <AutoCenter position={userLocation} />}

      {showHeatmap && heatmapPoints.length > 0 && (
        <HeatmapLayer
          points={heatmapPoints}
          onHotspotClick={handleHotspotClick}
        />
      )}

      {userLocation && (
        <StaticMarker
          position={[userLocation.lat, userLocation.lng]}
          icon={userIcon}
        />
      )}

      {selectedRoute && selectedRoute.geometry && selectedRoute.geometry.length >= 2 && (
        <Polyline
          positions={selectedRoute.geometry}
          pathOptions={{
            color: getRouteColor(selectedRoute.safetyScore),
            weight: 4,
            opacity: 0.85,
          }}
        />
      )}
    </MapContainer>
  )
})

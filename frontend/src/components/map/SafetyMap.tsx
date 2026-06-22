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
    width: 8px; height: 8px;
    background: #3b82f6;
    border-radius: 50%;
    box-shadow: 0 0 0 2px #3b82f640, 0 0 8px #3b82f680;
  "></div>`,
  iconSize: [8, 8],
  iconAnchor: [4, 4],
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

function getRouteColor(score: number): string {
  if (score >= 0.8) return '#00E676'
  if (score >= 0.6) return '#FFD600'
  if (score >= 0.4) return '#FF8C00'
  return '#FF1744'
}

interface SafetyMapProps {
  heatmapPoints?: HeatmapPoint[]
  selectedRoute?: RouteOption | null
  userLocation?: { lat: number; lng: number } | null
  showHeatmap?: boolean
  onHotspotClick?: (lat: number, lng: number, weight: number) => void
  children?: React.ReactNode
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
      style={{ background: '#0a0a10' }}
    >
      <TileLayer
        attribution='&copy; <a href="https://carto.com/">CARTO</a>'
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      />
      <ScaleControl position="bottomleft" />
      <ZoomControl position="bottomright" />
      {children}
      <MapBoundsUpdater />

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
            weight: 3,
            opacity: 0.7,
          }}
        />
      )}
    </MapContainer>
  )
})

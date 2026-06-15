import { useEffect, useRef } from 'react'
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

  useEffect(() => {
    const update = () => {
      const b = map.getBounds()
      setBounds({
        north: b.getNorth(),
        south: b.getSouth(),
        east: b.getEast(),
        west: b.getWest(),
      })
    }
    map.on('moveend', update)
    update()
    return () => { map.off('moveend', update) }
  }, [map, setBounds])

  return null
}

interface SafetyMapProps {
  heatmapPoints?: HeatmapPoint[]
  selectedRoute?: RouteOption | null
  userLocation?: { lat: number; lng: number } | null
  showHeatmap?: boolean
  onHotspotClick?: (lat: number, lng: number, weight: number) => void
  children?: React.ReactNode
}

export function SafetyMap({
  heatmapPoints = [],
  selectedRoute = null,
  userLocation = null,
  showHeatmap = true,
  onHotspotClick,
  children,
}: SafetyMapProps) {
  const { center, zoom, setSelectedLocation } = useMapStore()
  const mapRef = useRef<L.Map | null>(null)

  const getRouteColor = (score: number) => {
    if (score >= 0.8) return '#00E676'
    if (score >= 0.6) return '#FFD600'
    if (score >= 0.4) return '#FF8C00'
    return '#FF1744'
  }

  return (
    <MapContainer
      center={center}
      zoom={zoom}
      className="h-full w-full"
      zoomControl={false}
      style={{ background: '#0a0a10' }}
      ref={mapRef}
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
          onHotspotClick={(lat, lng, weight) => {
            setSelectedLocation({ lat, lng })
            onHotspotClick?.(lat, lng, weight)
          }}
        />
      )}

      {userLocation && (
        <Marker
          position={[userLocation.lat, userLocation.lng]}
          icon={userIcon}
        />
      )}

      {selectedRoute && (
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
}

function Marker({ position, icon }: { position: [number, number]; icon: L.DivIcon }) {
  const map = useMap()
  const markerRef = useRef<L.Marker | null>(null)

  useEffect(() => {
    const marker = L.marker(position, { icon, interactive: false }).addTo(map)
    markerRef.current = marker
    return () => {
      map.removeLayer(marker)
    }
  }, [map, position, icon])

  return null
}

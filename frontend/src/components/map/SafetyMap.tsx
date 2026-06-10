import { useEffect, useRef, useMemo, useCallback } from 'react'
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  Polyline,
  GeoJSON,
  useMapEvents,
  useMap,
  ScaleControl,
  ZoomControl,
} from 'react-leaflet'
import L from 'leaflet'
import { useMapStore } from '@/store/mapStore'
import { HeatmapLayer } from './HeatmapLayer'
import type {
  Incident,
  PoliceStation,
  Hospital,
  RouteOption,
  DistrictAnalytics,
  HeatmapPoint,
} from '@/types'
import { getSeverityColor, formatRelativeTime } from '@/lib/utils'

function createIncidentIcon(severity: string) {
  const colors: Record<string, string> = {
    critical: '#7c3aed',
    high: '#ef4444',
    medium: '#f59e0b',
    low: '#22c55e',
  }
  const color = colors[severity] || '#94a3b8'
  return L.divIcon({
    className: 'incident-marker',
    html: `<div style="
      width: 16px; height: 16px;
      background: ${color};
      border: 2px solid white;
      border-radius: 50%;
      box-shadow: 0 0 8px ${color}80;
    "></div>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
    popupAnchor: [0, -10],
  })
}

const policeIcon = L.divIcon({
  className: 'police-marker',
  html: `<div style="
    width: 24px; height: 24px;
    background: #3b82f6;
    border: 2px solid white;
    border-radius: 4px;
    display: flex; align-items: center; justify-content: center;
    font-size: 12px; color: white; font-weight: bold;
    box-shadow: 0 0 8px #3b82f680;
  ">P</div>`,
  iconSize: [24, 24],
  iconAnchor: [12, 12],
})

const hospitalIcon = L.divIcon({
  className: 'hospital-marker',
  html: `<div style="
    width: 24px; height: 24px;
    background: #ef4444;
    border: 2px solid white;
    border-radius: 4px;
    display: flex; align-items: center; justify-content: center;
    font-size: 12px; color: white; font-weight: bold;
    box-shadow: 0 0 8px #ef444480;
  ">H</div>`,
  iconSize: [24, 24],
  iconAnchor: [12, 12],
})

const userIcon = L.divIcon({
  className: 'user-location-marker',
  html: `<div style="
    width: 20px; height: 20px;
    background: #3b82f6;
    border: 3px solid white;
    border-radius: 50%;
    box-shadow: 0 0 0 4px #3b82f640, 0 0 12px #3b82f680;
    animation: pulse 2s infinite;
  "></div>`,
  iconSize: [20, 20],
  iconAnchor: [10, 10],
})

function MapEventsHandler({ onClick }: { onClick: (pos: { lat: number; lng: number }) => void }) {
  useMapEvents({
    click: (e) => {
      onClick({ lat: e.latlng.lat, lng: e.latlng.lng })
    },
  })
  return null
}

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
  incidents?: Incident[]
  policeStations?: PoliceStation[]
  hospitals?: Hospital[]
  heatmapPoints?: HeatmapPoint[]
  selectedRoute?: RouteOption | null
  userLocation?: { lat: number; lng: number } | null
  districts?: DistrictAnalytics[]
  showHeatmap?: boolean
  showIncidents?: boolean
  showPolice?: boolean
  showHospitals?: boolean
  onLocationClick?: (pos: { lat: number; lng: number }) => void
  children?: React.ReactNode
}

export function SafetyMap({
  incidents = [],
  policeStations = [],
  hospitals = [],
  heatmapPoints = [],
  selectedRoute = null,
  userLocation = null,
  districts = [],
  showHeatmap = true,
  showIncidents = true,
  showPolice = true,
  showHospitals = true,
  onLocationClick,
  children,
}: SafetyMapProps) {
  const { center, zoom, setCenter, setZoom, setSelectedLocation } = useMapStore()
  const mapRef = useRef<L.Map | null>(null)

  const handleClick = useCallback((pos: { lat: number; lng: number }) => {
    setSelectedLocation(pos)
    onLocationClick?.(pos)
  }, [setSelectedLocation, onLocationClick])

  const districtGeoJson = useMemo(() => {
    if (districts.length === 0) return null
    return {
      type: 'FeatureCollection' as const,
      features: districts.map((d) => ({
        type: 'Feature' as const,
        properties: {
          name: d.district,
          risk: d.critical + d.highRisk > d.total / 2 ? 'high' : d.mediumRisk > d.total / 2 ? 'medium' : 'low',
        },
        geometry: {
          type: 'Polygon' as const,
          coordinates: [[]],
        },
      })),
    }
  }, [districts])

  const getRouteColor = (score: number) => {
    if (score >= 0.8) return '#22c55e'
    if (score >= 0.6) return '#f59e0b'
    if (score >= 0.4) return '#ef4444'
    return '#7c3aed'
  }

  return (
    <MapContainer
      center={center}
      zoom={zoom}
      className="h-full w-full"
      zoomControl={false}
      style={{ background: '#1e293b' }}
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
      <MapEventsHandler onClick={handleClick} />

      {showHeatmap && heatmapPoints.length > 0 && (
        <HeatmapLayer points={heatmapPoints} />
      )}

      {showIncidents && incidents.map((incident) => (
        <Marker
          key={incident.id}
          position={[incident.location.lat, incident.location.lng]}
          icon={createIncidentIcon(incident.severity)}
        >
          <Popup>
            <div className="text-sm space-y-1 min-w-[200px]">
              <div className="flex items-center gap-2">
                <span className="font-semibold">{incident.title}</span>
                <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${getSeverityColor(incident.severity)}`}>
                  {incident.severity}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">{incident.description}</p>
              <p className="text-xs text-muted-foreground">{formatRelativeTime(incident.reportedAt)}</p>
              {incident.location.address && (
                <p className="text-xs text-muted-foreground">{incident.location.address}</p>
              )}
            </div>
          </Popup>
        </Marker>
      ))}

      {showPolice && policeStations.map((station) => (
        <Marker
          key={station.id}
          position={[station.location.lat, station.location.lng]}
          icon={policeIcon}
        >
          <Popup>
            <div className="text-sm space-y-1">
              <p className="font-semibold">{station.name}</p>
              <p className="text-xs text-muted-foreground">{station.address}</p>
              <p className="text-xs text-muted-foreground">{station.phone}</p>
            </div>
          </Popup>
        </Marker>
      ))}

      {showHospitals && hospitals.map((hospital) => (
        <Marker
          key={hospital.id}
          position={[hospital.location.lat, hospital.location.lng]}
          icon={hospitalIcon}
        >
          <Popup>
            <div className="text-sm space-y-1">
              <p className="font-semibold">{hospital.name}</p>
              <p className="text-xs text-muted-foreground">{hospital.address}</p>
              <p className="text-xs text-muted-foreground">{hospital.phone}</p>
            </div>
          </Popup>
        </Marker>
      ))}

      {userLocation && (
        <Marker position={[userLocation.lat, userLocation.lng]} icon={userIcon}>
          <Popup>
            <div className="text-sm">
              <p className="font-semibold">Your Location</p>
            </div>
          </Popup>
        </Marker>
      )}

      {selectedRoute && (
        <Polyline
          positions={selectedRoute.geometry}
          pathOptions={{
            color: getRouteColor(selectedRoute.safetyScore),
            weight: 4,
            opacity: 0.8,
          }}
        />
      )}

      {districtGeoJson && (
        <GeoJSON
          data={districtGeoJson}
          style={(feature) => ({
            fillColor: feature?.properties.risk === 'high' ? '#ef444420' :
                       feature?.properties.risk === 'medium' ? '#f59e0b20' : '#22c55e20',
            fillOpacity: 0.3,
            color: feature?.properties.risk === 'high' ? '#ef444480' :
                   feature?.properties.risk === 'medium' ? '#f59e0b80' : '#22c55e80',
            weight: 1,
          })}
        />
      )}
    </MapContainer>
  )
}

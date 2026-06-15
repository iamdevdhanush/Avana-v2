import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet.heat'
import type { HeatmapPoint } from '@/types'

const HEAT_GRADIENT: Record<number, string> = {
  0.0: 'rgba(0,0,0,0)',
  0.2: '#00E676',
  0.4: '#FFD600',
  0.6: '#FF8C00',
  0.8: '#FF1744',
  1.0: '#D50000',
}

function getRiskColor(weight: number): string {
  if (weight >= 0.9) return '#D50000'
  if (weight >= 0.75) return '#FF1744'
  if (weight >= 0.5) return '#FF8C00'
  if (weight >= 0.25) return '#FFD600'
  return '#00E676'
}

interface HeatmapLayerProps {
  points: HeatmapPoint[]
  onHotspotClick?: (lat: number, lng: number, weight: number) => void
}

export function HeatmapLayer({ points, onHotspotClick }: HeatmapLayerProps) {
  const map = useMap()
  const heatLayerRef = useRef<L.HeatLayer | null>(null)
  const clickHandlerRef = useRef<(() => void) | null>(null)

  useEffect(() => {
    if (heatLayerRef.current) {
      map.removeLayer(heatLayerRef.current)
      heatLayerRef.current = null
    }

    if (points.length === 0) return

    const heatData: Array<[number, number, number]> = points.map(
      (p) => [p.lat, p.lng, p.weight]
    )

    if (typeof L.heatLayer !== 'function') return

    const radius = map.getZoom() >= 13 ? 25 : map.getZoom() >= 11 ? 35 : 45

    heatLayerRef.current = L.heatLayer(heatData as unknown as L.LatLng[], {
      radius,
      blur: radius * 0.65,
      maxZoom: 18,
      max: 1,
      gradient: HEAT_GRADIENT,
    }).addTo(map)

    return () => {
      if (heatLayerRef.current) {
        map.removeLayer(heatLayerRef.current)
        heatLayerRef.current = null
      }
    }
  }, [points, map])

  useEffect(() => {
    if (clickHandlerRef.current) {
      clickHandlerRef.current()
      clickHandlerRef.current = null
    }

    if (!onHotspotClick || points.length === 0) return

    const handler = (e: L.LeafletMouseEvent) => {
      const clickPt = map.latLngToContainerPoint(e.latlng)
      const threshold = 60 + 40 * (1 / Math.max(1, map.getZoom() - 8))
      let nearest: { lat: number; lng: number; weight: number; dist: number } | null = null

      const step = Math.max(1, Math.floor(points.length / 200))
      for (let i = 0; i < points.length; i += step) {
        const p = points[i]
        const pt = map.latLngToContainerPoint([p.lat, p.lng])
        const dx = clickPt.x - pt.x
        const dy = clickPt.y - pt.y
        const dist = Math.sqrt(dx * dx + dy * dy)
        if (dist < threshold && (!nearest || dist < nearest.dist)) {
          nearest = { lat: p.lat, lng: p.lng, weight: p.weight, dist }
        }
      }

      if (nearest) {
        onHotspotClick(nearest.lat, nearest.lng, nearest.weight)
      }
    }

    map.on('click', handler)
    clickHandlerRef.current = () => map.off('click', handler)

    return () => {
      if (clickHandlerRef.current) {
        clickHandlerRef.current()
        clickHandlerRef.current = null
      }
    }
  }, [points, map, onHotspotClick])

  useEffect(() => {
    if (!document.getElementById('heatmap-glow-style')) {
      const style = document.createElement('style')
      style.id = 'heatmap-glow-style'
      style.textContent = `
        .leaflet-heatmap-layer { mix-blend-mode: screen; }
      `
      document.head.appendChild(style)
    }
  }, [])

  return null
}

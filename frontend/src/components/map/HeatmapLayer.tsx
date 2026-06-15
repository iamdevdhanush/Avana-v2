import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet.heat'
import type { HeatmapPoint } from '@/types'

const HEAT_GRADIENT: Record<number, string> = {
  0.0: 'rgba(0,0,0,0)',
  0.25: '#00E676',
  0.50: '#FFD600',
  0.75: '#FF8C00',
  0.90: '#FF1744',
  1.0: '#D50000',
}

function nonlinearWeight(score01: number): number {
  if (score01 <= 0) return 0
  if (score01 <= 0.25) return score01 * 0.16
  if (score01 <= 0.5) return 0.04 + (score01 - 0.25) * 0.64
  if (score01 <= 0.75) return 0.20 + (score01 - 0.5) * 2.4
  if (score01 <= 0.9) return 0.80 + (score01 - 0.75) * 0.67
  return 0.90 + (score01 - 0.9) * 1.0
}

function getRadius(zoom: number): number {
  if (zoom >= 15) return 20
  if (zoom >= 13) return 28
  if (zoom >= 11) return 38
  return 50
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

    const zoom = map.getZoom()
    const radius = getRadius(zoom)

    const heatData: Array<[number, number, number]> = points.map((p) => {
      const rawWeight = Math.min(1, Math.max(0, p.weight))
      const w = nonlinearWeight(rawWeight)
      return [p.lat, p.lng, w]
    })

    if (typeof L.heatLayer !== 'function') {
      return
    }

    heatLayerRef.current = L.heatLayer(heatData as unknown as L.LatLng[], {
      radius,
      blur: Math.round(radius * 0.7),
      maxZoom: 16,
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
      const threshold = 50 + 50 * (1 / Math.max(1, map.getZoom() - 8))
      let nearest: { lat: number; lng: number; weight: number; dist: number } | null = null

      const step = Math.max(1, Math.floor(points.length / 150))
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
        .leaflet-heatmap-layer {
          mix-blend-mode: screen;
          will-change: transform;
        }
        .leaflet-heatmap-layer canvas {
          image-rendering: auto;
        }
      `
      document.head.appendChild(style)
    }
  }, [])

  return null
}

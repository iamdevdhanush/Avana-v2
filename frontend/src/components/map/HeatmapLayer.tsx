import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet.heat'
import type { HeatmapPoint } from '@/types'

interface HeatmapLayerProps {
  points: HeatmapPoint[]
  radius?: number
  blur?: number
  maxZoom?: number
  max?: number
  gradient?: Record<number, string>
}

export function HeatmapLayer({
  points,
  radius = 25,
  blur = 15,
  maxZoom = 18,
  max = 1,
  gradient = {
    0.4: '#22c55e',
    0.6: '#f59e0b',
    0.8: '#ef4444',
    1.0: '#7c3aed',
  },
}: HeatmapLayerProps) {
  const map = useMap()
  const heatLayerRef = useRef<L.HeatLayer | null>(null)

  useEffect(() => {
    if (points.length === 0) return

    const heatData: Array<[number, number, number]> = points.map(
      (p) => [p.lat, p.lng, p.weight]
    )

    if (heatLayerRef.current) {
      heatLayerRef.current.setLatLngs(heatData as unknown as L.LatLng[])
    } else {
      heatLayerRef.current = L.heatLayer(heatData as unknown as L.LatLng[], {
        radius,
        blur,
        maxZoom,
        max,
        gradient,
      }).addTo(map)
    }

    return () => {
      if (heatLayerRef.current) {
        map.removeLayer(heatLayerRef.current)
        heatLayerRef.current = null
      }
    }
  }, [points, radius, blur, maxZoom, max, gradient, map])

  return null
}

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
  debug?: boolean
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
  debug = false,
}: HeatmapLayerProps) {
  const map = useMap()
  const heatLayerRef = useRef<L.HeatLayer | null>(null)
  const markerLayerRef = useRef<L.LayerGroup | null>(null)

  console.log("[HEATMAP_DEBUG]", points.length, points.slice(0, 5))
  console.log(`[HEATMAP] points=${points.length}, weights=[${points.slice(0, 3).map(p => p.weight.toFixed(4)).join(', ')}...], max=${max}, radius=${radius}, blur=${blur}`)
  if (points.length > 0) {
    const ws = points.map(p => p.weight)
    console.log(`[HEATMAP] weight range: ${Math.min(...ws).toFixed(4)} - ${Math.max(...ws).toFixed(4)}, avg=${(ws.reduce((a, b) => a + b, 0) / ws.length).toFixed(4)}`)
  }

  useEffect(() => {
    if (points.length === 0) return

    const heatData: Array<[number, number, number]> = points.map(
      (p) => [p.lat, p.lng, p.weight]
    )

    console.log("[HEATMAP_RENDER]", heatData.length)

    try {
      if (heatLayerRef.current) {
        console.log(`[HEATMAP] Updating existing layer with ${points.length} points`)
        heatLayerRef.current.setLatLngs(heatData as unknown as L.LatLng[])
      } else {
        if (typeof L.heatLayer !== 'function') {
          console.error("[HEATMAP] L.heatLayer is not a function — leaflet.heat may not be loaded")
          return
        }
        console.log(`[HEATMAP] Creating new L.heatLayer with ${points.length} points`)
        heatLayerRef.current = L.heatLayer(heatData as unknown as L.LatLng[], {
          radius,
          blur,
          maxZoom,
          max,
          gradient,
        }).addTo(map)
        console.log(`[HEATMAP] Layer added to map`)
      }
    } catch (err) {
      console.error("[HEATMAP] Failed to create/update heat layer:", err)
    }

    return () => {
      if (heatLayerRef.current) {
        console.log(`[HEATMAP] Removing layer from map (${points.length} points were shown)`)
        map.removeLayer(heatLayerRef.current)
        heatLayerRef.current = null
      }
    }
  }, [points, radius, blur, maxZoom, max, gradient, map])

  useEffect(() => {
    if (!debug) {
      if (markerLayerRef.current) {
        map.removeLayer(markerLayerRef.current)
        markerLayerRef.current = null
      }
      return
    }
    if (points.length === 0) return

    if (markerLayerRef.current) {
      map.removeLayer(markerLayerRef.current)
    }

    const group = L.layerGroup()
    const subset = points.length > 500 ? points.filter((_, i) => i % Math.ceil(points.length / 500) === 0) : points
    subset.forEach((p) => {
      const color = p.weight > 0.6 ? '#ef4444' : p.weight > 0.3 ? '#f59e0b' : '#22c55e'
      L.circleMarker([p.lat, p.lng], {
        radius: 4,
        color,
        fillColor: color,
        fillOpacity: 0.8,
        weight: 1,
      }).addTo(group)
    })
    group.addTo(map)
    markerLayerRef.current = group
    console.log(`[HEATMAP_MARKERS] Added ${subset.length} debug markers`)

    return () => {
      if (markerLayerRef.current) {
        map.removeLayer(markerLayerRef.current)
        markerLayerRef.current = null
      }
    }
  }, [debug, points, map])

  return null
}

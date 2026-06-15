import { useRef, useMemo, useEffect } from 'react'
import { useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet.heat'
import type { HeatmapPoint } from '@/types'

const MIN_SCORE = 0.25

const HEAT_GRADIENT: Record<number, string> = {
  0.0: 'rgba(0,0,0,0)',
  0.10: 'rgba(255,214,0,0.10)',
  0.33: 'rgba(255,214,0,0.45)',
  0.50: 'rgba(255,140,0,0.65)',
  0.67: 'rgba(255,23,68,0.85)',
  0.85: '#D50000',
  1.0: '#B71C1C',
}

function remapWeight(raw01: number): number {
  if (raw01 <= MIN_SCORE) return 0
  return Math.min(1, (raw01 - MIN_SCORE) / (1 - MIN_SCORE))
}

function thresholdPx(zoom: number): number {
  return 50 + 50 * (1 / Math.max(1, zoom - 8))
}

interface HeatmapLayerProps {
  points: HeatmapPoint[]
  onHotspotClick?: (lat: number, lng: number, weight: number) => void
}

export function HeatmapLayer({ points, onHotspotClick }: HeatmapLayerProps) {
  const map = useMap()
  const heatRef = useRef<L.HeatLayer | null>(null)
  const clickClean = useRef<(() => void) | null>(null)

  const filtered = useMemo(
    () => points.filter((p) => p.weight >= MIN_SCORE),
    [points]
  )

  const heatData = useMemo<Array<[number, number, number]>>(
    () => filtered.map((p) => [p.lat, p.lng, remapWeight(p.weight)]),
    [filtered]
  )

  useEffect(() => {
    if (heatRef.current) {
      map.removeLayer(heatRef.current)
      heatRef.current = null
    }
    if (heatData.length === 0 || typeof L.heatLayer !== 'function') return

    heatRef.current = L.heatLayer(heatData as unknown as L.LatLng[], {
      radius: 35,
      blur: 24,
      maxZoom: 16,
      max: 1,
      gradient: HEAT_GRADIENT,
    }).addTo(map)

    return () => {
      if (heatRef.current) {
        map.removeLayer(heatRef.current)
        heatRef.current = null
      }
    }
  }, [heatData, map])

  useEffect(() => {
    if (clickClean.current) {
      clickClean.current()
      clickClean.current = null
    }
    if (!onHotspotClick || filtered.length === 0) return

    const handler = (e: L.LeafletMouseEvent) => {
      const cp = map.latLngToContainerPoint(e.latlng)
      const th = thresholdPx(map.getZoom())
      let best: { lat: number; lng: number; weight: number; dist: number } | null = null

      const step = Math.max(1, Math.floor(filtered.length / 150))
      for (let i = 0; i < filtered.length; i += step) {
        const p = filtered[i]
        const pt = map.latLngToContainerPoint([p.lat, p.lng])
        const dx = cp.x - pt.x
        const dy = cp.y - pt.y
        const d = Math.sqrt(dx * dx + dy * dy)
        if (d < th && (!best || d < best.dist)) {
          best = { lat: p.lat, lng: p.lng, weight: p.weight, dist: d }
        }
      }

      if (best) onHotspotClick(best.lat, best.lng, best.weight)
    }

    map.on('click', handler)
    clickClean.current = () => map.off('click', handler)

    return () => {
      if (clickClean.current) {
        clickClean.current()
        clickClean.current = null
      }
    }
  }, [filtered, onHotspotClick, map])

  useEffect(() => {
    if (document.getElementById('hm-style')) return
    const s = document.createElement('style')
    s.id = 'hm-style'
    s.textContent = `
      .leaflet-heatmap-layer { mix-blend-mode: screen; will-change: transform; }
      .leaflet-heatmap-layer canvas { image-rendering: auto; }
    `
    document.head.appendChild(s)
  }, [])

  return null
}

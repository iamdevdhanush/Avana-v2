import { useState, useEffect, useRef, useCallback } from 'react'
import type { HeatmapPoint, HeatmapResponse, DistrictSummary, MapBounds } from '@/types'
import { riskApi } from '@/services/api'
import { useMapStore } from '@/store/mapStore'

interface UseHeatmapReturn {
  points: HeatmapPoint[]
  generatedAt: string | null
  districtSummaries: DistrictSummary[]
  isLoading: boolean
  error: string | null
  refresh: () => void
}

const cache = new Map<string, { data: HeatmapResponse; ts: number }>()
const CACHE_TTL = 120_000
const MIN_ZOOM_FOR_FETCH = 9

function boundsKey(bounds: MapBounds, zoom: number): string {
  return `${bounds.south.toFixed(4)},${bounds.west.toFixed(4)},${bounds.north.toFixed(4)},${bounds.east.toFixed(4)},${zoom}`
}

let inflightRequest: Promise<HeatmapResponse> | null = null

const FALLBACK_POINTS: HeatmapPoint[] = [
  { lat: 12.9716, lng: 77.5946, weight: 0.45, riskCategory: 'MODERATE' },
  { lat: 12.9340, lng: 77.6100, weight: 0.55, riskCategory: 'HIGH_RISK' },
  { lat: 12.9500, lng: 77.5700, weight: 0.35, riskCategory: 'MODERATE' },
  { lat: 12.9900, lng: 77.6000, weight: 0.30, riskCategory: 'MODERATE' },
  { lat: 12.9200, lng: 77.6200, weight: 0.50, riskCategory: 'HIGH_RISK' },
  { lat: 12.9800, lng: 77.5800, weight: 0.25, riskCategory: 'SAFE' },
  { lat: 13.0200, lng: 77.5600, weight: 0.20, riskCategory: 'SAFE' },
  { lat: 12.9600, lng: 77.6400, weight: 0.60, riskCategory: 'HIGH_RISK' },
  { lat: 12.9100, lng: 77.5900, weight: 0.40, riskCategory: 'MODERATE' },
  { lat: 13.0000, lng: 77.6300, weight: 0.35, riskCategory: 'MODERATE' },
  { lat: 12.9400, lng: 77.5800, weight: 0.00, riskCategory: 'UNKNOWN' },
  { lat: 12.9650, lng: 77.6050, weight: 0.00, riskCategory: 'UNKNOWN' },
]

export function useHeatmap(
  bounds: MapBounds | null,
  zoom: number,
  debounceMs: number = 500,
): UseHeatmapReturn {
  const [response, setResponse] = useState<HeatmapResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const setHeatmapPoints = useMapStore((state) => state.setHeatmapPoints)
  const lastKeyRef = useRef<string | null>(null)

  const fetchHeatmap = useCallback(async () => {
    if (!bounds || zoom < MIN_ZOOM_FOR_FETCH) return

    const key = boundsKey(bounds, zoom)
    const cached = cache.get(key)
    if (cached && Date.now() - cached.ts < CACHE_TTL) {
      setResponse(cached.data)
      setHeatmapPoints(cached.data.points)
      setIsLoading(false)
      setError(null)
      return
    }

    if (inflightRequest) {
      try {
        const data = await inflightRequest
        if (key !== lastKeyRef.current) return
        setResponse(data)
        setHeatmapPoints(data.points)
        setIsLoading(false)
        return
      } catch {
        inflightRequest = null
      }
    }

    setIsLoading(true)
    setError(null)

    try {
      const promise = riskApi.getHeatmapBounds(bounds, zoom)
      inflightRequest = promise
      const data = await promise

      if (key !== lastKeyRef.current) return

      if (data.points.length === 0) {
        const fallbackResponse: HeatmapResponse = {
          points: FALLBACK_POINTS,
          generatedAt: null,
          districtSummaries: [
            { district: 'Bengaluru Urban', avgScore: 42, totalIncidents: 0, trend: 'stable' },
            { district: 'Bengaluru Rural', avgScore: 28, totalIncidents: 0, trend: 'improving' },
            { district: 'Mysuru', avgScore: 35, totalIncidents: 0, trend: 'stable' },
          ],
        }
        cache.set(key, { data: fallbackResponse, ts: Date.now() })
        setResponse(fallbackResponse)
        setHeatmapPoints(fallbackResponse.points)
      } else {
        cache.set(key, { data, ts: Date.now() })
        if (cache.size > 50) {
          const firstKey = cache.keys().next().value
          if (firstKey) cache.delete(firstKey)
        }
        setResponse(data)
        setHeatmapPoints(data.points)
      }
    } catch (err) {
      if (key === lastKeyRef.current) {
        setError((err as Error).message)
        setResponse({
          points: FALLBACK_POINTS,
          generatedAt: null,
          districtSummaries: [
            { district: 'Bengaluru Urban', avgScore: 42, totalIncidents: 0, trend: 'stable' },
          ],
        })
        setHeatmapPoints(FALLBACK_POINTS)
      }
    } finally {
      inflightRequest = null
      if (key === lastKeyRef.current) {
        setIsLoading(false)
      }
    }
  }, [bounds, zoom, setHeatmapPoints])

  useEffect(() => {
    if (!bounds || zoom < MIN_ZOOM_FOR_FETCH) return

    const key = boundsKey(bounds, zoom)
    lastKeyRef.current = key

    if (timerRef.current) {
      clearTimeout(timerRef.current)
    }

    timerRef.current = setTimeout(() => {
      fetchHeatmap()
    }, debounceMs)

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current)
      }
    }
  }, [bounds, zoom, debounceMs, fetchHeatmap])

  const refresh = useCallback(() => {
    if (bounds && zoom >= MIN_ZOOM_FOR_FETCH) {
      const key = boundsKey(bounds, zoom)
      cache.delete(key)
    }
    if (timerRef.current) {
      clearTimeout(timerRef.current)
    }
    fetchHeatmap()
  }, [bounds, zoom, fetchHeatmap])

  return {
    points: response?.points ?? [],
    generatedAt: response?.generatedAt ?? null,
    districtSummaries: response?.districtSummaries ?? [],
    isLoading,
    error,
    refresh,
  }
}

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

      cache.set(key, { data, ts: Date.now() })
      if (cache.size > 50) {
        const firstKey = cache.keys().next().value
        if (firstKey) cache.delete(firstKey)
      }

      setResponse(data)
      setHeatmapPoints(data.points)
    } catch (err) {
      if (key === lastKeyRef.current) {
        setError((err as Error).message)
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

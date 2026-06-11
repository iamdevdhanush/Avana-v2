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

export function useHeatmap(
  bounds: MapBounds | null,
  zoom: number,
  debounceMs: number = 500
): UseHeatmapReturn {
  const [response, setResponse] = useState<HeatmapResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const setHeatmapPoints = useMapStore((state) => state.setHeatmapPoints)

  const fetchHeatmap = useCallback(async () => {
    if (!bounds) return

    setIsLoading(true)
    setError(null)

    try {
      const data = await riskApi.getHeatmapBounds(bounds, zoom)
      setResponse(data)
      setHeatmapPoints(data.points)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setIsLoading(false)
    }
  }, [bounds, zoom, setHeatmapPoints])

  useEffect(() => {
    if (!bounds) return

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
    if (timerRef.current) {
      clearTimeout(timerRef.current)
    }
    fetchHeatmap()
  }, [fetchHeatmap])

  return {
    points: response?.points ?? [],
    generatedAt: response?.generatedAt ?? null,
    districtSummaries: response?.districtSummaries ?? [],
    isLoading,
    error,
    refresh,
  }
}

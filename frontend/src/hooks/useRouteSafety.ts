import { useState, useCallback } from 'react'
import type { RouteResult, RouteOption } from '@/types'
import { routeApi } from '@/services/api'

interface UseRouteSafetyReturn {
  routeResult: RouteResult | null
  selectedRoute: RouteOption | null
  isLoading: boolean
  error: string | null
  calculateRoute: (
    source: { lat: number; lng: number },
    destination: { lat: number; lng: number }
  ) => Promise<void>
  selectRoute: (type: 'safest' | 'fastest' | 'balanced') => void
  clearRoute: () => void
}

export function useRouteSafety(): UseRouteSafetyReturn {
  const [routeResult, setRouteResult] = useState<RouteResult | null>(null)
  const [selectedRoute, setSelectedRoute] = useState<RouteOption | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const calculateRoute = useCallback(
    async (
      source: { lat: number; lng: number },
      destination: { lat: number; lng: number }
    ) => {
      setIsLoading(true)
      setError(null)

      try {
        const result = await routeApi.getSafeRoute(source, destination)
        setRouteResult(result)
        setSelectedRoute(result.balanced)
      } catch (err) {
        setError((err as Error).message)
        setRouteResult(null)
        setSelectedRoute(null)
      } finally {
        setIsLoading(false)
      }
    },
    []
  )

  const selectRoute = useCallback(
    (type: 'safest' | 'fastest' | 'balanced') => {
      if (!routeResult) return
      setSelectedRoute(routeResult[type])
    },
    [routeResult]
  )

  const clearRoute = useCallback(() => {
    setRouteResult(null)
    setSelectedRoute(null)
    setError(null)
  }, [])

  return {
    routeResult,
    selectedRoute,
    isLoading,
    error,
    calculateRoute,
    selectRoute,
    clearRoute,
  }
}

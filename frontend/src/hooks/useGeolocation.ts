import { useState, useEffect, useRef, useCallback, useMemo } from 'react'

interface GeolocationState {
  latitude: number | null
  longitude: number | null
  accuracy: number | null
  speed: number | null
  heading: number | null
  altitude: number | null
  timestamp: number | null
}

interface UseGeolocationReturn {
  position: GeolocationState
  error: string | null
  isLoading: boolean
  isWatching: boolean
  startWatching: () => void
  stopWatching: () => void
  refreshPosition: () => void
}

const defaultPosition: GeolocationState = {
  latitude: null,
  longitude: null,
  accuracy: null,
  speed: null,
  heading: null,
  altitude: null,
  timestamp: null,
}

export function useGeolocation(options: PositionOptions = {}): UseGeolocationReturn {
  const [position, setPosition] = useState<GeolocationState>(defaultPosition)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isWatching, setIsWatching] = useState(false)
  const watchIdRef = useRef<number | null>(null)
  const mountedRef = useRef(true)

  const defaultOptions = useMemo<PositionOptions>(() => ({
    enableHighAccuracy: true,
    timeout: 10000,
    maximumAge: 30000,
    ...options,
  }), [options])

  const handleSuccess = useCallback((pos: GeolocationPosition) => {
    if (!mountedRef.current) return
    console.log(`[GEOLOCATION] Position: ${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)} | accuracy: ±${pos.coords.accuracy}m`)
    setPosition({
      latitude: pos.coords.latitude,
      longitude: pos.coords.longitude,
      accuracy: pos.coords.accuracy,
      speed: pos.coords.speed,
      heading: pos.coords.heading,
      altitude: pos.coords.altitude,
      timestamp: pos.timestamp,
    })
    setError(null)
    setIsLoading(false)
  }, [])

  const handleError = useCallback((err: GeolocationPositionError) => {
    if (!mountedRef.current) return
    let message: string
    switch (err.code) {
      case err.PERMISSION_DENIED:
        message = 'Location permission denied. Please enable location access.'
        console.error(`[GEOLOCATION] Error: ${message}`)
        break
      case err.POSITION_UNAVAILABLE:
        message = 'Location information is unavailable.'
        console.error(`[GEOLOCATION] Error: ${message}`)
        break
      case err.TIMEOUT:
        message = 'Location request timed out.'
        console.error(`[GEOLOCATION] Error: ${message}`)
        break
      default:
        message = 'An unknown error occurred while fetching location.'
        console.error(`[GEOLOCATION] Error (code ${err.code}): ${message}`)
    }
    setError(message)
    setIsLoading(false)
  }, [])

  const startWatching = useCallback(() => {
    if (!navigator.geolocation) {
      setError('Geolocation is not supported by this browser.')
      return
    }

    setIsLoading(true)
    setIsWatching(true)

    watchIdRef.current = navigator.geolocation.watchPosition(
      handleSuccess,
      handleError,
      defaultOptions
    )
  }, [handleSuccess, handleError, defaultOptions])

  const stopWatching = useCallback(() => {
    if (watchIdRef.current !== null) {
      navigator.geolocation.clearWatch(watchIdRef.current)
      watchIdRef.current = null
    }
    setIsWatching(false)
    setIsLoading(false)
  }, [])

  const refreshPosition = useCallback(() => {
    if (!navigator.geolocation) {
      setError('Geolocation is not supported by this browser.')
      return
    }

    setIsLoading(true)
    navigator.geolocation.getCurrentPosition(handleSuccess, handleError, defaultOptions)
  }, [handleSuccess, handleError, defaultOptions])

  useEffect(() => {
    mountedRef.current = true
    startWatching()
    return () => {
      mountedRef.current = false
      if (watchIdRef.current !== null) {
        navigator.geolocation.clearWatch(watchIdRef.current)
      }
    }
  }, [startWatching])

  return {
    position,
    error,
    isLoading,
    isWatching,
    startWatching,
    stopWatching,
    refreshPosition,
  }
}

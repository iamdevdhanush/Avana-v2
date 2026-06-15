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
  isFallback: boolean
  startWatching: () => void
  stopWatching: () => void
  refreshPosition: () => void
}

const FALLBACK_POSITION: GeolocationState = {
  latitude: 13.9299,
  longitude: 75.5681,
  accuracy: null,
  speed: null,
  heading: null,
  altitude: null,
  timestamp: Date.now(),
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

const DRIFT_THRESHOLD_METERS = 25
const MIN_UPDATE_INTERVAL_MS = 2000

function haversineDistance(
  lat1: number, lng1: number,
  lat2: number, lng2: number
): number {
  const R = 6371000
  const dLat = (lat2 - lat1) * Math.PI / 180
  const dLng = (lng2 - lng1) * Math.PI / 180
  const a = Math.sin(dLat / 2) ** 2
    + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLng / 2) ** 2
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

export function useGeolocation(options: PositionOptions = {}): UseGeolocationReturn {
  const [position, setPosition] = useState<GeolocationState>(defaultPosition)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isWatching, setIsWatching] = useState(false)
  const [isFallback, setIsFallback] = useState(false)
  const watchIdRef = useRef<number | null>(null)
  const mountedRef = useRef(true)
  const lastUpdateRef = useRef<number>(0)
  const lastStablePosRef = useRef<GeolocationState | null>(null)

  const defaultOptions = useMemo<PositionOptions>(() => ({
    enableHighAccuracy: true,
    timeout: 8000,
    maximumAge: 15000,
    ...options,
  }), [options])

  const handleSuccess = useCallback((pos: GeolocationPosition) => {
    if (!mountedRef.current) return

    const now = Date.now()
    const coords = pos.coords
    const lastStable = lastStablePosRef.current

    if (lastStable?.latitude != null && lastStable?.longitude != null) {
      const dist = haversineDistance(
        lastStable.latitude, lastStable.longitude,
        coords.latitude, coords.longitude
      )

      if (dist < DRIFT_THRESHOLD_METERS && now - lastUpdateRef.current < MIN_UPDATE_INTERVAL_MS) {
        return
      }
    }

    lastUpdateRef.current = now
    const newPos: GeolocationState = {
      latitude: coords.latitude,
      longitude: coords.longitude,
      accuracy: coords.accuracy,
      speed: coords.speed,
      heading: coords.heading,
      altitude: coords.altitude,
      timestamp: pos.timestamp,
    }
    lastStablePosRef.current = newPos
    setPosition(newPos)
    setError(null)
    setIsLoading(false)
  }, [])

  const activateFallback = useCallback(() => {
    const stored = sessionStorage.getItem('avana_last_location')
    if (stored) {
      try {
        const parsed = JSON.parse(stored)
        if (parsed.latitude && parsed.longitude) {
          setPosition({ ...FALLBACK_POSITION, latitude: parsed.latitude, longitude: parsed.longitude })
          setIsFallback(true)
          setIsLoading(false)
          return
        }
      } catch {}
    }
    setPosition(FALLBACK_POSITION)
    setIsFallback(true)
    setIsLoading(false)
  }, [])

  const handleError = useCallback((err: GeolocationPositionError) => {
    if (!mountedRef.current) return
    let message: string
    switch (err.code) {
      case err.PERMISSION_DENIED:
        message = 'Location permission denied. Please enable location access.'
        break
      case err.POSITION_UNAVAILABLE:
        message = 'Location information is unavailable.'
        break
      case err.TIMEOUT:
        message = 'Location request timed out.'
        break
      default:
        message = 'An unknown error occurred while fetching location.'
    }
    setError(message)
    activateFallback()
  }, [activateFallback])

  const startWatching = useCallback(() => {
    if (!navigator.geolocation) {
      setError('Geolocation is not supported by this browser.')
      activateFallback()
      return
    }

    setIsLoading(true)
    setIsWatching(true)

    watchIdRef.current = navigator.geolocation.watchPosition(
      handleSuccess,
      handleError,
      defaultOptions,
    )
  }, [handleSuccess, handleError, defaultOptions, activateFallback])

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
      activateFallback()
      return
    }
    setIsLoading(true)
    navigator.geolocation.getCurrentPosition(handleSuccess, handleError, defaultOptions)
  }, [handleSuccess, handleError, defaultOptions, activateFallback])

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

  const result = useMemo(() => ({
    position,
    error,
    isLoading,
    isWatching,
    isFallback,
    startWatching,
    stopWatching,
    refreshPosition,
  }), [position, error, isLoading, isWatching, isFallback, startWatching, stopWatching, refreshPosition])

  return result
}

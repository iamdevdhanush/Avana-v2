import { useState, useEffect, useRef } from 'react'
import { locationApi } from '@/services/api'

interface LocationNameResult {
  displayName: string
  locality: string
  city: string
  state: string
  district: string
  isLoading: boolean
  error: string | null
}

const cache = new Map<string, LocationNameResult>()

function formatFallback(lat: number, lng: number): string {
  return `${lat.toFixed(4)}, ${lng.toFixed(4)}`
}

export function useLocationName(
  lat: number | null | undefined,
  lng: number | null | undefined,
  debounceMs: number = 300,
): LocationNameResult {
  const [result, setResult] = useState<LocationNameResult>({
    displayName: '',
    locality: '',
    city: '',
    state: '',
    district: '',
    isLoading: false,
    error: null,
  })
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  useEffect(() => {
    if (lat == null || lng == null) return

    const key = `${lat.toFixed(4)},${lng.toFixed(4)}`

    const cached = cache.get(key)
    if (cached) {
      setResult(cached)
      return
    }

    setResult(prev => ({ ...prev, isLoading: true, error: null, displayName: '' }))

    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(async () => {
      if (!mountedRef.current) return
      try {
        const res = await locationApi.reverseGeocode(lat!, lng!)
        const entry: LocationNameResult = {
          displayName: res.displayName || formatFallback(lat!, lng!),
          locality: res.locality || '',
          city: res.city || '',
          state: res.state || '',
          district: res.district || '',
          isLoading: false,
          error: null,
        }
        cache.set(key, entry)
        if (mountedRef.current) setResult(entry)
      } catch (err) {
        const entry: LocationNameResult = {
          displayName: formatFallback(lat!, lng!),
          locality: '',
          city: '',
          state: '',
          district: '',
          isLoading: false,
          error: (err as Error).message,
        }
        if (mountedRef.current) setResult(entry)
      }
    }, debounceMs)

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [lat, lng, debounceMs])

  return result
}

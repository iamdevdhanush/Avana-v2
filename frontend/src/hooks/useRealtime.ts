import { useEffect, useRef, useCallback } from 'react'
import { useIncidentStore } from '@/store/incidentStore'
import { useUIStore } from '@/store/uiStore'
import type { Incident, SOSEvent } from '@/types'

interface RealtimeEvent {
  type: 'incident_new' | 'incident_update' | 'sos_trigger' | 'sos_update'
  payload: Incident | SOSEvent
}

type EventHandler = (event: RealtimeEvent) => void

interface UseRealtimeReturn {
  subscribe: (handler: EventHandler) => () => void
  isConnected: boolean
}

const listeners = new Set<EventHandler>()
let isConnected = false

function broadcastEvent(event: RealtimeEvent) {
  listeners.forEach((handler) => handler(event))
}

function buildWsUrl(channel: string): string {
  const RAW = import.meta.env.VITE_API_URL || ''
  const baseUrl = RAW.replace(/\/api\/v1$/, '').replace(/\/+$/, '')
  if (baseUrl) {
    const wsProtocol = baseUrl.startsWith('https') ? 'wss' : 'ws'
    return `${wsProtocol}://${baseUrl.replace(/^https?:\/\//, '')}/ws/${channel}`
  }
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${protocol}://${window.location.host}/ws/${channel}`
}

export function useRealtime(channel: string = 'public'): UseRealtimeReturn {
  const fetchIncidents = useIncidentStore((state) => state.fetchIncidents)
  const addToast = useUIStore((state) => state.addToast)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mountedRef = useRef(true)

  const handleEvent = useCallback(
    (event: RealtimeEvent) => {
      switch (event.type) {
        case 'incident_new': {
          addToast({
            title: 'New Incident Reported',
            description: (event.payload as Incident).title,
            variant: 'warning',
          })
          fetchIncidents()
          break
        }
        case 'incident_update': {
          fetchIncidents()
          break
        }
        case 'sos_trigger': {
          addToast({
            title: 'SOS Alert',
            description: 'Someone nearby has triggered an SOS alert',
            variant: 'destructive',
          })
          break
        }
        case 'sos_update': {
          addToast({
            title: 'SOS Update',
            description: `SOS status: ${(event.payload as SOSEvent).status}`,
            variant: 'default',
          })
          break
        }
      }
    },
    [addToast, fetchIncidents]
  )

  useEffect(() => {
    mountedRef.current = true
    listeners.add(handleEvent)

    const wsUrl = buildWsUrl(channel)

    let retryCount = 0
    const maxRetries = 5

    function connect() {
      if (!mountedRef.current || retryCount >= maxRetries) return

      try {
        const ws = new WebSocket(wsUrl)
        wsRef.current = ws

        ws.onopen = () => {
          isConnected = true
          retryCount = 0
        }

        ws.onmessage = (event) => {
          try {
            const parsed: RealtimeEvent = JSON.parse(event.data)
            broadcastEvent(parsed)
          } catch {
            // ignore malformed messages
          }
        }

        ws.onclose = () => {
          isConnected = false
          if (mountedRef.current && retryCount < maxRetries) {
            retryCount++
            reconnectTimerRef.current = setTimeout(connect, 5000 * retryCount)
          }
        }

        ws.onerror = () => {
          ws.close()
        }
      } catch {
        if (mountedRef.current && retryCount < maxRetries) {
          retryCount++
          reconnectTimerRef.current = setTimeout(connect, 5000 * retryCount)
        }
      }
    }

    connect()

    return () => {
      mountedRef.current = false
      listeners.delete(handleEvent)
      if (wsRef.current) {
        wsRef.current.close()
      }
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
      }
    }
  }, [channel, handleEvent])

  const subscribe = useCallback((handler: EventHandler) => {
    listeners.add(handler)
    return () => {
      listeners.delete(handler)
    }
  }, [])

  return {
    subscribe,
    isConnected,
  }
}

import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertTriangle, MapPin, Phone, CheckCircle, Loader2,
  Clock, Shield, Info, ArrowLeft,
} from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { useUIStore } from '@/store/uiStore'
import { useGeolocation } from '@/hooks/useGeolocation'
import { useLocationName } from '@/hooks/useLocationName'
import { sosApi } from '@/services/api'
import type { SOSEvent } from '@/types'

type SOSStatus = 'idle' | 'armed' | 'sending' | 'sent'

export function SOSScreen() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const { addToast } = useUIStore()
  const { position } = useGeolocation()
  const locationName = useLocationName(position.latitude, position.longitude)

  const [status, setStatus] = React.useState<SOSStatus>('idle')
  const [countdown, setCountdown] = React.useState(3)
  const [sosEvent, setSosEvent] = React.useState<SOSEvent | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [sentTime, setSentTime] = React.useState<string>('')

  const timerRef = React.useRef<ReturnType<typeof setInterval> | null>(null)
  const contacts = user?.emergencyContacts || []

  // Countdown when armed
  React.useEffect(() => {
    if (status === 'armed') {
      timerRef.current = setInterval(() => {
        setCountdown((prev) => {
          if (prev <= 1) {
            handleSendSOS()
            return 0
          }
          return prev - 1
        })
      }, 1000)
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [status])

  const handleButtonPress = () => {
    if (status === 'idle') {
      setStatus('armed')
      setCountdown(3)
      setError(null)
      if (navigator.vibrate) navigator.vibrate(200)
    } else if (status === 'armed') {
      handleSendSOS()
    }
  }

  const handleSendSOS = async () => {
    if (timerRef.current) clearInterval(timerRef.current)
    setStatus('sending')
    setError(null)

    try {
      const location = position.latitude && position.longitude
        ? { lat: position.latitude, lng: position.longitude }
        : { lat: 13.9299, lng: 75.5681 }

      const event = await sosApi.triggerSOS(location)
      setSosEvent(event)
      setSentTime(new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }))
      setStatus('sent')
      if (navigator.vibrate) navigator.vibrate([300, 100, 300, 100, 300])
      addToast({ title: '🚨 SOS Alert Dispatched', description: 'Location captured & contacts notified.', variant: 'destructive' })
    } catch (err) {
      setError((err as Error).message || 'Failed to send SOS')
      setStatus('armed')
    }
  }

  const handleCancel = () => {
    if (timerRef.current) clearInterval(timerRef.current)
    setStatus('idle')
    setCountdown(3)
  }

  // ── POST ACTIVATION STATE ──
  if (status === 'sent') {
    return (
      <div className="flex flex-col items-center justify-center min-h-full px-6 py-8 animate-fade-in bg-[#07110A] pb-safe">
        <div className="w-full max-w-sm flex flex-col items-center gap-6 text-center">
          <div className="w-20 h-20 rounded-full flex items-center justify-center bg-[#EF4444]/15 border-2 border-[#EF4444]">
            <CheckCircle className="h-10 w-10 text-[#EF4444]" />
          </div>

          <div className="space-y-1">
            <h2 className="text-2xl font-black text-[#F1F8F2] tracking-wide">SOS ACTIVATED</h2>
            <p className="text-xs text-[#EF4444] font-bold">Alert dispatched at {sentTime}</p>
          </div>

          {/* Location Captured Card */}
          <div className="w-full p-4 rounded-xl avana-surface border border-[#1D3823] space-y-2 text-left">
            <div className="flex items-center gap-2 text-xs font-bold text-[#66BB6A]">
              <MapPin className="h-4 w-4 text-[#EF4444]" />
              <span>Location Captured</span>
            </div>
            <p className="text-xs text-[#F1F8F2]">
              {locationName.displayName || `${position.latitude?.toFixed(4)}, ${position.longitude?.toFixed(4)}`}
            </p>
          </div>

          {/* Contacts Notified */}
          <div className="w-full p-4 rounded-xl avana-surface border border-[#1D3823] space-y-2 text-left">
            <div className="flex items-center gap-2 text-xs font-bold text-[#F1F8F2]">
              <Shield className="h-4 w-4 text-[#66BB6A]" />
              <span>Emergency Contacts Notified</span>
            </div>
            <p className="text-xs text-[#9BAF9F]">
              {contacts.length > 0
                ? `${contacts.length} designated emergency contacts received your location dispatch.`
                : 'Primary emergency notification sent.'}
            </p>
          </div>

          {/* Demo Mode Notice */}
          <div className="flex items-center gap-2 p-3 rounded-xl bg-[#122417] border border-[#1D3823] text-[11px] text-[#9BAF9F]">
            <Info className="h-4 w-4 text-[#F5B942] shrink-0" />
            <span>Demonstration mode: Verify local emergency services before relying on automated dispatch.</span>
          </div>

          {/* Action buttons */}
          <div className="flex flex-col gap-3 w-full pt-2">
            <a
              href="tel:112"
              className="flex items-center justify-center gap-2 w-full py-3.5 rounded-xl font-bold text-xs text-white bg-[#EF4444] hover:bg-[#DC2626] transition-all shadow-lg"
            >
              <Phone className="h-4 w-4" />
              Call Emergency Services (112)
            </a>
            <button
              onClick={() => navigate('/map')}
              className="w-full py-3 rounded-xl font-bold text-xs text-[#66BB6A] bg-[#122417] border border-[#1D3823]"
            >
              Open Safety Map
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ── MAIN SOS FOCUS SCREEN ──
  return (
    <div className="flex flex-col min-h-full pb-safe bg-[#07110A] justify-between">
      {/* Header Context */}
      <div className="text-center pt-8 px-6">
        <h1 className="text-sm font-extrabold tracking-widest uppercase text-[#EF4444] mb-1">
          {status === 'idle' ? 'EMERGENCY SOS' : status === 'armed' ? `ACTIVATING IN ${countdown}s` : 'DISPATCHING...'}
        </h1>
        <p className="text-xs text-[#9BAF9F]">
          {status === 'idle'
            ? 'Press and hold for 3 seconds to trigger emergency alert'
            : 'Tap button to trigger immediately or press cancel'}
        </p>
      </div>

      {/* ── BIG SOS BUTTON HERO ── */}
      <div className="flex flex-col items-center justify-center py-6">
        <div className="relative flex items-center justify-center">
          {status === 'armed' && (
            <>
              <div
                className="absolute rounded-full"
                style={{
                  width: '260px', height: '260px',
                  background: 'rgba(239, 68, 68, 0.1)',
                  animation: 'sos-ring 1.2s ease-out infinite',
                }}
              />
              <div
                className="absolute rounded-full"
                style={{
                  width: '220px', height: '220px',
                  background: 'rgba(239, 68, 68, 0.15)',
                  animation: 'sos-ring 1.2s ease-out 0.4s infinite',
                }}
              />
            </>
          )}

          <button
            onClick={status === 'sending' ? undefined : handleButtonPress}
            disabled={status === 'sending'}
            className="relative flex flex-col items-center justify-center rounded-full transition-all select-none"
            style={{
              width: '200px',
              height: '200px',
              background: status === 'armed'
                ? '#DC2626'
                : status === 'sending'
                ? '#991B1B'
                : '#EF4444',
              boxShadow: status === 'armed'
                ? '0 0 50px rgba(239, 68, 68, 0.6)'
                : '0 0 30px rgba(239, 68, 68, 0.3)',
              transform: status === 'armed' ? 'scale(1.04)' : 'scale(1)',
            }}
          >
            {status === 'sending' ? (
              <Loader2 className="h-10 w-10 text-white animate-spin" />
            ) : status === 'armed' ? (
              <span className="text-6xl font-black text-white">{countdown}</span>
            ) : (
              <div className="flex flex-col items-center gap-1">
                <AlertTriangle className="h-12 w-12 text-white" strokeWidth={2.2} />
                <span className="text-2xl font-black text-white tracking-wider">SOS</span>
              </div>
            )}
          </button>
        </div>

        {status === 'armed' && (
          <button
            onClick={handleCancel}
            className="mt-6 px-6 py-2 rounded-xl text-xs font-bold text-[#8A948C] border border-[#1D3823] hover:text-[#F1F8F2]"
          >
            Cancel SOS
          </button>
        )}

        {error && (
          <p className="mt-4 text-xs text-[#EF4444] font-semibold">{error}</p>
        )}
      </div>

      {/* Hotline Action */}
      <div className="px-6 pb-6 space-y-3 max-w-sm mx-auto w-full">
        <a
          href="tel:112"
          className="flex items-center justify-center gap-2 w-full py-3 rounded-xl font-bold text-xs text-[#EF4444] bg-[#EF4444]/10 border border-[#EF4444]/20"
        >
          <Phone className="h-4 w-4" />
          Direct Emergency Line: 112
        </a>
      </div>
    </div>
  )
}

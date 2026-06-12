import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertTriangle, MapPin, Phone, CheckCircle, Loader2,
  Clock, Shield,
} from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { useUIStore } from '@/store/uiStore'
import { useGeolocation } from '@/hooks/useGeolocation'
import { useLocationName } from '@/hooks/useLocationName'
import { sosApi } from '@/services/api'
import { cn } from '@/lib/utils'
import type { SOSEvent } from '@/types'

type SOSStatus = 'idle' | 'armed' | 'sending' | 'sent'

export function SOSScreen() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const { addToast } = useUIStore()
  const { position } = useGeolocation()
  const locationName = useLocationName(position.latitude, position.longitude)

  const [status, setStatus] = React.useState<SOSStatus>('idle')
  const [countdown, setCountdown] = React.useState(5)
  const [sosEvent, setSosEvent] = React.useState<SOSEvent | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [history, setHistory] = React.useState<SOSEvent[]>([])

  const timerRef = React.useRef<ReturnType<typeof setInterval> | null>(null)

  const contacts = user?.emergencyContacts || []

  // Load SOS history
  React.useEffect(() => {
    sosApi.getSOSHistory().then(setHistory).catch(() => {})
  }, [])

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
      setCountdown(5)
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
        : { lat: 12.9716, lng: 77.5946 }

      const event = await sosApi.triggerSOS(location)
      setSosEvent(event)
      setStatus('sent')
      if (navigator.vibrate) navigator.vibrate([300, 100, 300, 100, 300])
      addToast({ title: '🚨 SOS Alert Sent', description: 'Emergency services notified', variant: 'destructive' })
    } catch (err) {
      setError((err as Error).message)
      setStatus('armed')
    }
  }

  const handleCancel = () => {
    if (timerRef.current) clearInterval(timerRef.current)
    setStatus('idle')
    setCountdown(5)
  }

  // ── SENT STATE ──
  if (status === 'sent') {
    return (
      <div
        className="flex flex-col items-center justify-center min-h-full px-6 py-8 animate-fade-in pb-safe"
        style={{ background: '#09090B' }}
      >
        <div className="w-full max-w-sm flex flex-col items-center gap-6 text-center">
          <div
            className="w-24 h-24 rounded-full flex items-center justify-center"
            style={{ background: 'rgba(34,197,94,0.12)', border: '2px solid rgba(34,197,94,0.3)' }}
          >
            <CheckCircle className="h-12 w-12 text-[#22C55E]" />
          </div>
          <div>
            <h2 className="text-2xl font-black text-[#F9FAFB] mb-2">SOS Sent</h2>
            <p className="text-sm text-[#6B7280] leading-relaxed">
              Your emergency contacts have been notified. Stay safe — help is on the way.
            </p>
          </div>

          {/* Location */}
          {position.latitude && (
            <div
              className="flex items-center gap-2 px-4 py-3 rounded-xl w-full"
              style={{ background: '#1A1A24', border: '1px solid #1F2937' }}
            >
              <MapPin className="h-4 w-4 text-[#EF4444] shrink-0" />
              <div className="text-left min-w-0">
                <p className="text-sm text-[#F9FAFB] truncate">
                  {locationName.isLoading ? (
                    <span className="inline-flex items-center gap-1"><Loader2 className="h-3 w-3 animate-spin" />Detecting...</span>
                  ) : (
                    locationName.displayName
                  )}
                </p>
                {position.accuracy && (
                  <p className="text-[10px] text-[#6B7280]">±{Math.round(position.accuracy)}m</p>
                )}
              </div>
            </div>
          )}

          {sosEvent?.id && (
            <p className="text-xs text-[#374151]">Event ID: {sosEvent.id.slice(0, 12)}...</p>
          )}

          <div className="flex flex-col gap-2.5 w-full">
            <a
              href="tel:112"
              className="flex items-center justify-center gap-2 w-full py-3.5 rounded-xl font-bold text-sm text-white"
              style={{ background: '#EF4444', boxShadow: '0 4px 20px rgba(239,68,68,0.4)' }}
            >
              <Phone className="h-4 w-4" />
              Call Emergency (112)
            </a>
            <button
              onClick={() => navigate('/map')}
              className="w-full py-3 rounded-xl font-semibold text-sm"
              style={{ background: 'rgba(168,85,247,0.1)', border: '1px solid rgba(168,85,247,0.25)', color: '#A855F7' }}
            >
              View on Map
            </button>
            <button
              onClick={() => navigate('/')}
              className="w-full py-3 rounded-xl text-sm text-[#6B7280] hover:text-[#F9FAFB] transition-colors"
            >
              Back to Home
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ── MAIN SOS SCREEN ──
  return (
    <div
      className="flex flex-col min-h-full pb-safe"
      style={{ background: '#09090B' }}
    >
      {/* Status text */}
      <div className="text-center pt-8 pb-4 px-6">
        <h1
          className="text-sm font-bold uppercase tracking-widest mb-1"
          style={{ color: status === 'armed' ? '#EF4444' : '#6B7280' }}
        >
          {status === 'idle' ? 'Emergency SOS' : status === 'armed' ? `Sending in ${countdown}s` : 'Sending...'}
        </h1>
        <p className="text-xs text-[#374151]">
          {status === 'idle'
            ? 'Hold to arm — tap again or wait to send'
            : status === 'armed'
            ? 'Tap button to send immediately'
            : 'Alerting emergency contacts...'}
        </p>
      </div>

      {/* ── BIG SOS BUTTON ── */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-4">
        <div className="relative flex items-center justify-center">
          {/* Pulsing rings when armed */}
          {status === 'armed' && (
            <>
              <div
                className="absolute rounded-full"
                style={{
                  width: '280px', height: '280px',
                  background: 'rgba(239,68,68,0.08)',
                  animation: 'sos-ring 1.5s ease-out infinite',
                }}
              />
              <div
                className="absolute rounded-full"
                style={{
                  width: '240px', height: '240px',
                  background: 'rgba(239,68,68,0.12)',
                  animation: 'sos-ring 1.5s ease-out 0.5s infinite',
                }}
              />
            </>
          )}

          {/* Main button */}
          <button
            onClick={status === 'sending' ? undefined : handleButtonPress}
            disabled={status === 'sending'}
            className="relative flex flex-col items-center justify-center rounded-full transition-all duration-200 select-none"
            style={{
              width: '220px',
              height: '220px',
              background: status === 'armed'
                ? 'radial-gradient(circle, #DC2626 0%, #B91C1C 100%)'
                : status === 'sending'
                ? '#7F1D1D'
                : 'radial-gradient(circle, #EF4444 0%, #DC2626 100%)',
              boxShadow: status === 'armed'
                ? '0 0 60px rgba(239,68,68,0.6), 0 0 120px rgba(239,68,68,0.2)'
                : status === 'sending'
                ? 'none'
                : '0 0 40px rgba(239,68,68,0.4), 0 20px 60px rgba(0,0,0,0.5)',
              transform: status === 'armed' ? 'scale(1.05)' : 'scale(1)',
              cursor: status === 'sending' ? 'not-allowed' : 'pointer',
            }}
          >
            {status === 'sending' ? (
              <>
                <Loader2 className="h-12 w-12 text-white animate-spin mb-2" />
                <span className="text-white text-sm font-bold">Sending</span>
              </>
            ) : status === 'armed' ? (
              <>
                <span className="text-white text-6xl font-black tracking-tighter leading-none">
                  {countdown}
                </span>
                <span className="text-white/80 text-sm font-bold mt-1">TAP TO SEND</span>
              </>
            ) : (
              <>
                <AlertTriangle className="h-14 w-14 text-white mb-2" strokeWidth={2} />
                <span className="text-white text-3xl font-black tracking-wider">SOS</span>
              </>
            )}

            {/* Inner glow ring */}
            <div
              className="absolute inset-3 rounded-full pointer-events-none"
              style={{
                border: '2px solid rgba(255,255,255,0.15)',
                boxShadow: 'inset 0 0 20px rgba(255,255,255,0.05)',
              }}
            />
          </button>
        </div>

        {/* Cancel */}
        {status === 'armed' && (
          <button
            onClick={handleCancel}
            className="mt-6 px-6 py-2.5 rounded-xl text-sm font-semibold text-[#6B7280] border border-[#1F2937] hover:border-[#374151] hover:text-[#F9FAFB] transition-all"
          >
            Cancel
          </button>
        )}

        {/* Error */}
        {error && (
          <div
            className="mt-4 px-4 py-2.5 rounded-xl text-xs text-[#EF4444] text-center"
            style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)' }}
          >
            {error}
          </div>
        )}
      </div>

      {/* ── Below Button: Contacts, Location, History ── */}
      <div className="px-4 pb-4 space-y-3">
        {/* Emergency Contacts */}
        {contacts.length > 0 && (
          <div
            className="rounded-2xl overflow-hidden"
            style={{ background: '#1A1A24', border: '1px solid #1F2937' }}
          >
            <div className="flex items-center gap-2 px-4 py-2.5 border-b border-[#1F2937]">
              <Shield className="h-3.5 w-3.5 text-[#A855F7]" />
              <span className="text-xs font-semibold text-[#F9FAFB]">Emergency Contacts</span>
            </div>
            <div className="flex gap-2 overflow-x-auto px-4 py-3">
              {contacts.slice(0, 4).map((c) => (
                <div
                  key={c.id}
                  className="flex flex-col items-center gap-1 shrink-0"
                >
                  <div
                    className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold"
                    style={{ background: 'rgba(168,85,247,0.15)', color: '#A855F7' }}
                  >
                    {c.name[0].toUpperCase()}
                  </div>
                  <span className="text-[10px] text-[#6B7280] max-w-[48px] text-center truncate">{c.name.split(' ')[0]}</span>
                  {c.notifyOnSOS && (
                    <div className="w-1.5 h-1.5 rounded-full bg-[#22C55E]" />
                  )}
                </div>
              ))}
              {contacts.length === 0 && (
                <p className="text-xs text-[#6B7280]">No contacts — add in Profile</p>
              )}
            </div>
          </div>
        )}

        {/* Current Location */}
        <div
          className="flex items-center gap-3 px-4 py-3 rounded-2xl"
          style={{ background: '#1A1A24', border: '1px solid #1F2937' }}
        >
          <MapPin className="h-4 w-4 text-[#EF4444] shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-xs text-[#6B7280] font-medium">Current Location</p>
            {position.latitude ? (
              <>
                <p className="text-sm text-[#F9FAFB] truncate">
                  {locationName.isLoading ? (
                    <span className="inline-flex items-center gap-1 text-[#6B7280]"><Loader2 className="h-3 w-3 animate-spin" />Detecting...</span>
                  ) : (
                    locationName.displayName
                  )}
                </p>
                {position.accuracy && (
                  <p className="text-[10px] text-[#6B7280] mt-0.5">±{Math.round(position.accuracy)}m</p>
                )}
              </>
            ) : (
              <p className="text-sm text-[#6B7280]">Detecting...</p>
            )}
          </div>
        </div>

        {/* Recent SOS history */}
        {history.length > 0 && (
          <div
            className="rounded-2xl overflow-hidden"
            style={{ background: '#1A1A24', border: '1px solid #1F2937' }}
          >
            <div className="flex items-center gap-2 px-4 py-2.5 border-b border-[#1F2937]">
              <Clock className="h-3.5 w-3.5 text-[#6B7280]" />
              <span className="text-xs font-semibold text-[#F9FAFB]">Recent Alerts</span>
            </div>
            {history.slice(0, 2).map((ev) => (
              <div key={ev.id} className="flex items-center gap-3 px-4 py-2.5 border-b border-[#1F2937] last:border-0">
                <div
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{
                    background: ev.status === 'resolved' ? '#22C55E' : ev.status === 'triggered' ? '#EF4444' : '#F59E0B',
                  }}
                />
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-[#F9FAFB] capitalize">{ev.status}</p>
                  <p className="text-[10px] text-[#6B7280]">
                    {new Date(ev.timestamp).toLocaleDateString('en-IN', {
                      day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
                    })}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Emergency hotline */}
        <a
          href="tel:112"
          className="flex items-center justify-center gap-2 w-full py-3 rounded-2xl font-semibold text-sm transition-all"
          style={{
            background: 'rgba(239,68,68,0.08)',
            border: '1px solid rgba(239,68,68,0.2)',
            color: '#EF4444',
          }}
        >
          <Phone className="h-4 w-4" />
          Call Emergency: 112
        </a>
      </div>
    </div>
  )
}

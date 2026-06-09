import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertTriangle, MapPin, Phone, CheckCircle, Loader2,
  Share2, MessageSquare, X, Users,
} from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { useUIStore } from '@/store/uiStore'
import { useGeolocation } from '@/hooks/useGeolocation'
import { sosApi } from '@/services/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'
import type { EmergencyContact } from '@/types'

type SOSStatus = 'idle' | 'armed' | 'sending' | 'sent' | 'acknowledged'

export function SOSScreen() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const { addToast } = useUIStore()
  const { position } = useGeolocation()
  const [status, setStatus] = React.useState<SOSStatus>('idle')
  const [countdown, setCountdown] = React.useState(5)
  const [selectedContacts, setSelectedContacts] = React.useState<string[]>([])
  const [customMessage, setCustomMessage] = React.useState('')
  const [shareLocation, setShareLocation] = React.useState(true)
  const [sosEvent, setSosEvent] = React.useState<{ id: string } | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const timerRef = React.useRef<ReturnType<typeof setInterval> | null>(null)

  const contacts = user?.emergencyContacts || []

  React.useEffect(() => {
    if (contacts.length > 0 && selectedContacts.length === 0) {
      const primary = contacts.filter((c) => c.notifyOnSOS).map((c) => c.id)
      setSelectedContacts(primary.length > 0 ? primary : [contacts[0].id])
    }
  }, [contacts])

  React.useEffect(() => {
    if (position.latitude && position.longitude && !customMessage) {
      setCustomMessage(
        `SOS Emergency! I need help. My location: ${position.latitude.toFixed(6)}, ${position.longitude.toFixed(6)}`
      )
    }
  }, [position])

  React.useEffect(() => {
    if (status === 'armed' && countdown > 0) {
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
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [status, countdown])

  const handleArmSOS = () => {
    if (status === 'idle') {
      setStatus('armed')
      setCountdown(5)
      setError(null)
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

      const event = await sosApi.triggerSOS(location, selectedContacts)
      setSosEvent(event)
      setStatus('sent')

      if (navigator.vibrate) navigator.vibrate([500, 200, 500, 200, 500])

      addToast({ title: 'SOS Alert Sent', description: 'Help is on the way', variant: 'destructive' })
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

  const toggleContact = (contactId: string) => {
    setSelectedContacts((prev) =>
      prev.includes(contactId)
        ? prev.filter((id) => id !== contactId)
        : [...prev, contactId]
    )
  }

  if (status === 'sent' || status === 'acknowledged') {
    return (
      <div className="mx-auto max-w-md space-y-6 p-4 md:p-6 text-center">
        <div className="pt-8">
          <div className="mx-auto mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-safety-500/20">
            <CheckCircle className="h-10 w-10 text-safety-500" />
          </div>
          <h1 className="text-2xl font-bold mb-2">SOS Sent Successfully</h1>
          <p className="text-sm text-muted-foreground">
            Your emergency contacts have been notified. Help is on the way.
          </p>
        </div>

        <Card>
          <CardContent className="p-4 space-y-3">
            <div className="flex items-center gap-2 text-sm">
              <MapPin className="h-4 w-4 text-danger-500" />
              <span className="text-muted-foreground">
                {position.latitude?.toFixed(4)}, {position.longitude?.toFixed(4)}
              </span>
            </div>
            {sosEvent?.id && (
              <p className="text-xs text-muted-foreground">Event ID: {sosEvent.id}</p>
            )}
            <Separator />
            <div className="flex flex-col gap-2">
              <Button variant="outline" className="w-full" onClick={() => window.location.href = 'tel:112'}>
                <Phone className="h-4 w-4 mr-2" /> Call Emergency (112)
              </Button>
              <Button variant="outline" className="w-full" onClick={() => navigate('/map')}>
                <MapPin className="h-4 w-4 mr-2" /> View on Map
              </Button>
              <Button variant="ghost" className="w-full" onClick={() => navigate('/')}>
                Back to Home
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-md space-y-6 p-4 md:p-6">
      <div className="text-center">
        <h1 className="text-2xl font-bold text-danger-500">Emergency SOS</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {status === 'idle' ? 'Tap the SOS button to arm, tap again to send' :
           status === 'armed' ? `Sending automatically in ${countdown}s` :
           'Sending SOS alert...'}
        </p>
      </div>

      <div className="flex justify-center">
        <button
          onClick={status === 'sending' ? undefined : status === 'armed' ? handleSendSOS : handleArmSOS}
          disabled={status === 'sending'}
          className={cn(
            'relative h-40 w-40 rounded-full font-bold text-2xl transition-all duration-300',
            status === 'armed'
              ? 'bg-danger-600 scale-110 animate-pulse ring-8 ring-danger-500/40'
              : status === 'sending'
              ? 'bg-danger-400 cursor-not-allowed'
              : 'bg-danger-500 hover:bg-danger-600 hover:scale-105',
            'text-white shadow-2xl shadow-danger-500/30'
          )}
        >
          {status === 'sending' ? (
            <Loader2 className="h-10 w-10 animate-spin mx-auto" />
          ) : (
            <div className="flex flex-col items-center gap-1">
              <AlertTriangle className="h-10 w-10" />
              <span>{status === 'armed' ? 'SEND!' : 'SOS'}</span>
            </div>
          )}
        </button>
      </div>

      {status === 'armed' && (
        <div className="text-center">
          <div className="inline-flex items-center gap-2 rounded-full bg-danger-500/10 px-4 py-2 text-sm text-danger-500">
            <AlertTriangle className="h-4 w-4 animate-pulse" />
            SOS will be sent in {countdown}s
          </div>
          <Button variant="ghost" size="sm" className="mt-2 text-muted-foreground" onClick={handleCancel}>
            Cancel
          </Button>
        </div>
      )}

      {error && (
        <div className="rounded-md bg-danger-500/10 border border-danger-500/20 p-3 text-sm text-danger-500">
          {error}
        </div>
      )}

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <MapPin className="h-4 w-4 text-danger-500" />
            Current Location
          </CardTitle>
        </CardHeader>
        <CardContent>
          {position.latitude ? (
            <div className="space-y-2">
              <p className="text-sm">
                {position.latitude.toFixed(6)}, {position.longitude?.toFixed(6) ?? '—'}
              </p>
              <p className="text-xs text-muted-foreground">
                Accuracy: ±{position.accuracy?.toFixed(0)}m
              </p>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Detecting location...</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Users className="h-4 w-4" />
            Emergency Contacts
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {contacts.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No emergency contacts added. Add them in your profile settings.
            </p>
          ) : (
            contacts.map((contact) => (
              <label
                key={contact.id}
                className={cn(
                  'flex items-center gap-3 rounded-lg border p-3 cursor-pointer transition-colors',
                  selectedContacts.includes(contact.id)
                    ? 'border-danger-500/50 bg-danger-500/5'
                    : 'border-border hover:bg-accent'
                )}
              >
                <div className={cn(
                  'h-4 w-4 rounded border flex items-center justify-center transition-colors',
                  selectedContacts.includes(contact.id)
                    ? 'bg-danger-500 border-danger-500'
                    : 'border-muted-foreground'
                )}>
                  {selectedContacts.includes(contact.id) && (
                    <CheckCircle className="h-3 w-3 text-white" />
                  )}
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium">{contact.name}</p>
                  <p className="text-xs text-muted-foreground">{contact.relationship}</p>
                </div>
                <span className="text-xs text-muted-foreground">{contact.phone}</span>
              </label>
            ))
          )}
        </CardContent>
      </Card>

      <div className="space-y-2">
        <label className="text-sm font-medium flex items-center gap-2">
          <MessageSquare className="h-4 w-4" />
          Custom Message
        </label>
        <Textarea
          value={customMessage}
          onChange={(e) => setCustomMessage(e.target.value)}
          placeholder="Add details about your emergency..."
          className="min-h-[80px]"
        />
      </div>

      <label className="flex items-center gap-3 cursor-pointer">
        <div
          onClick={() => setShareLocation(!shareLocation)}
          className={cn(
            'h-5 w-9 rounded-full transition-colors relative',
            shareLocation ? 'bg-primary' : 'bg-input'
          )}
        >
          <div className={cn(
            'absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white transition-transform',
            shareLocation && 'translate-x-4'
          )} />
        </div>
        <div className="flex items-center gap-2 text-sm">
          <Share2 className="h-4 w-4" />
          Share location with contacts
        </div>
      </label>

      <div className="flex gap-3">
        <Button variant="outline" className="flex-1" onClick={() => navigate('/')}>
          Back
        </Button>
        <Button
          variant="destructive"
          className="flex-1"
          disabled={status !== 'idle' || selectedContacts.length === 0}
          onClick={handleArmSOS}
        >
          {status === 'idle' ? 'Arm SOS' : status === 'armed' ? 'Sending...' : 'Sent'}
        </Button>
      </div>
    </div>
  )
}

import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Map as MapIcon, Share2, Phone, AlertTriangle, Shield, Bell,
  Users, Clock, Activity, Lightbulb, ChevronRight, Loader2,
} from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { useUIStore } from '@/store/uiStore'
import { useGeolocation } from '@/hooks/useGeolocation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { Skeleton } from '@/components/ui/skeleton'
import { Separator } from '@/components/ui/separator'
import { formatRelativeTime, getRiskColor, getRiskLabel } from '@/lib/utils'
import type { Incident, RiskScore, SafetyRecommendation } from '@/types'
import { riskApi, incidentApi } from '@/services/api'

export function HomeScreen() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const { addToast } = useUIStore()
  const { position, isLoading: geoLoading, error: geoError } = useGeolocation()
  const [riskScore, setRiskScore] = React.useState<RiskScore | null>(null)
  const [recentIncidents, setRecentIncidents] = React.useState<Incident[]>([])
  const [loading, setLoading] = React.useState(true)
  const [guardianMode, setGuardianMode] = React.useState(false)
  const [sosConfirming, setSosConfirming] = React.useState(false)

  React.useEffect(() => {
    if (position.latitude && position.longitude) {
      Promise.all([
        riskApi.getRiskScore(position.latitude, position.longitude),
        incidentApi.getIncidents({ lat: position.latitude, lng: position.longitude, radius: 5, limit: 5 }),
      ]).then(([risk, incidents]) => {
        setRiskScore(risk)
        setRecentIncidents(incidents.data)
      }).catch(() => {}).finally(() => setLoading(false))
    }
  }, [position])

  const handleSOS = () => {
    if (!sosConfirming) {
      setSosConfirming(true)
      setTimeout(() => setSosConfirming(false), 5000)
    } else {
      setSosConfirming(false)
      navigate('/sos')
    }
  }

  const safetyTip: SafetyRecommendation = {
    id: '1',
    title: 'Stay Aware',
    description: riskScore?.recommendations[0] || 'Keep your phone charged and share your location with trusted contacts when traveling at night.',
    category: 'awareness',
    priority: 'medium',
    createdAt: new Date().toISOString(),
  }

  const riskAngle = riskScore ? riskScore.score * 360 : 0
  const riskColor = riskScore ? getRiskColor(riskScore.score) : '#94a3b8'
  const safeDays = Math.floor(Math.random() * 30) + 1

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4 md:p-6 pb-20 lg:pb-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">
            Welcome back, {user?.name?.split(' ')[0] || 'User'}
          </h1>
          <p className="text-sm text-muted-foreground">
            {position.latitude
              ? 'Location detected'
              : geoLoading ? 'Detecting location...'
              : geoError || 'Location unavailable'}
          </p>
        </div>
        <Badge variant="outline" className="text-xs">
          <Clock className="h-3 w-3 mr-1" />
          {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card className="md:col-span-2">
          <CardContent className="p-6">
            <div className="flex items-center gap-6">
              <div className="relative flex items-center justify-center">
                <svg className="h-24 w-24 -rotate-90" viewBox="0 0 72 72">
                  <circle cx="36" cy="36" r="30" fill="none" stroke="currentColor" strokeWidth="4" className="text-muted" />
                  <circle cx="36" cy="36" r="30" fill="none" stroke={riskColor} strokeWidth="4"
                    strokeDasharray={`${riskAngle} 360`} strokeLinecap="round"
                    className="transition-all duration-1000" />
                </svg>
                <span className="absolute text-2xl font-bold">
                  {loading ? '--' : riskScore ? Math.round(riskScore.score * 100) : '?'}
                </span>
              </div>
              <div className="space-y-2">
                <p className="text-lg font-semibold">Safety Score</p>
                {loading ? (
                  <Skeleton className="h-6 w-20" />
                ) : riskScore ? (
                  <Badge variant={
                    riskScore.category === 'critical' ? 'critical' :
                    riskScore.category === 'high' ? 'danger' :
                    riskScore.category === 'moderate' ? 'warning' :
                    riskScore.category === 'low' ? 'success' : 'secondary'
                  } className="text-sm px-3 py-1 capitalize">
                    {riskScore.category} Risk
                  </Badge>
                ) : (
                  <p className="text-sm text-muted-foreground">Unable to calculate</p>
                )}
                <p className="text-xs text-muted-foreground">
                  {position.latitude && position.longitude
                    ? `${position.latitude.toFixed(4)}, ${position.longitude.toFixed(4)}`
                    : 'Location unknown'}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Shield className="h-4 w-4 text-primary" />
                <span className="text-sm font-medium">Guardian Mode</span>
              </div>
              <Switch checked={guardianMode} onCheckedChange={setGuardianMode} />
            </div>
            <Separator />
            <div className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Safe Days</span>
                <span className="font-semibold text-safety-500">{safeDays}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Nearby Events</span>
                <span className="font-semibold">{recentIncidents.length}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">High Alerts</span>
                <span className="font-semibold text-danger-500">
                  {recentIncidents.filter((i) => i.severity === 'high' || i.severity === 'critical').length}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Lightbulb className="h-4 w-4 text-warning-500" />
              AI Safety Tip
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{safetyTip.description}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center justify-between">
              <span className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-danger-500" />
                Recent Incidents
              </span>
              <button onClick={() => navigate('/map')} className="text-xs text-primary hover:underline">
                View All
              </button>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {loading ? (
              Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))
            ) : recentIncidents.length === 0 ? (
              <p className="text-sm text-muted-foreground">No recent incidents nearby</p>
            ) : (
              recentIncidents.slice(0, 5).map((inc) => (
                <div key={inc.id} className="flex items-start gap-2 text-sm">
                  <div className={`mt-0.5 h-2 w-2 rounded-full shrink-0 ${
                    inc.severity === 'critical' ? 'bg-critical' :
                    inc.severity === 'high' ? 'bg-danger-500' :
                    inc.severity === 'medium' ? 'bg-warning-500' : 'bg-safety-500'
                  }`} />
                  <div className="flex-1 min-w-0">
                    <p className="truncate font-medium">{inc.title}</p>
                    <p className="text-xs text-muted-foreground">{formatRelativeTime(inc.reportedAt)}</p>
                  </div>
                  <Badge variant={
                    inc.severity === 'critical' ? 'critical' :
                    inc.severity === 'high' ? 'danger' :
                    inc.severity === 'medium' ? 'warning' : 'success'
                  } className="text-[10px] px-1.5 capitalize">{inc.severity}</Badge>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium">Quick Actions</CardTitle>
          <CardDescription>Essential safety tools at your fingertips</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Button variant="outline" className="h-auto flex-col gap-2 py-4" onClick={() => navigate('/map')}>
              <MapIcon className="h-5 w-5" />
              <span className="text-xs">Open Map</span>
            </Button>
            <Button variant="outline" className="h-auto flex-col gap-2 py-4" onClick={() => {
              if (navigator.share) {
                navigator.share({ title: 'My Location', text: `I'm at ${position.latitude}, ${position.longitude}` })
              } else {
                navigator.clipboard.writeText(`${position.latitude}, ${position.longitude}`)
                addToast({ title: 'Location copied', variant: 'success' })
              }
            }}>
              <Share2 className="h-5 w-5" />
              <span className="text-xs">Share Location</span>
            </Button>
            <Button variant="outline" className="h-auto flex-col gap-2 py-4" onClick={() => window.location.href = 'tel:112'}>
              <Phone className="h-5 w-5" />
              <span className="text-xs">Call Helpline</span>
            </Button>
            <Button variant="outline" className="h-auto flex-col gap-2 py-4" onClick={() => addToast({ title: 'Feature coming soon', variant: 'default' })}>
              <Bell className="h-5 w-5" />
              <span className="text-xs">Report Incident</span>
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-col gap-3 sm:flex-row">
        {user?.emergencyContacts && user.emergencyContacts.length > 0 && (
          <Card className="flex-1">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Users className="h-4 w-4" />
                Emergency Contacts
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {user.emergencyContacts.slice(0, 3).map((contact) => (
                <div key={contact.id} className="flex items-center justify-between text-sm">
                  <span>{contact.name}</span>
                  <span className="text-xs text-muted-foreground">{contact.phone}</span>
                </div>
              ))}
              {user.emergencyContacts.length > 3 && (
                <button className="text-xs text-primary flex items-center gap-1">
                  View all <ChevronRight className="h-3 w-3" />
                </button>
              )}
            </CardContent>
          </Card>
        )}

        <Card className="flex-1">
          <CardContent className="p-6 flex flex-col items-center justify-center gap-3">
            <button
              onClick={handleSOS}
              className={`relative h-24 w-24 rounded-full font-bold text-lg transition-all duration-300 ${
                sosConfirming
                  ? 'bg-danger-600 scale-110 animate-pulse ring-4 ring-danger-500/50'
                  : 'bg-danger-500 hover:bg-danger-600 hover:scale-105'
              } text-white shadow-xl`}
            >
              {sosConfirming ? 'CONFIRM?' : 'SOS'}
            </button>
            <p className="text-xs text-muted-foreground text-center">
              {sosConfirming
                ? 'Tap again to send SOS alert'
                : 'Tap to arm SOS, then tap again to send'}
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

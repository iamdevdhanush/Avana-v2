import * as React from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  ArrowLeft, MapPin, Clock, AlertTriangle, Shield,
  ExternalLink, ChevronRight, Loader2, ShieldCheck,
} from 'lucide-react'
import { incidentApi } from '@/services/api'
import type { Incident } from '@/types'
import { formatRelativeTime } from '@/lib/utils'

const SEVERITY_CONFIG = {
  low:      { color: '#66BB6A', bg: 'rgba(102,187,106,0.12)', label: 'Low Risk' },
  medium:   { color: '#F5B942', bg: 'rgba(245,185,66,0.12)',  label: 'Moderate Risk' },
  high:     { color: '#EF4444', bg: 'rgba(239,68,68,0.12)',   label: 'High Risk' },
  critical: { color: '#EF4444', bg: 'rgba(239,68,68,0.18)',   label: 'Critical Danger' },
}

const SOURCE_LABELS: Record<string, string> = {
  user_reported: 'Community Report',
  official:      'Official Source',
  news:          'News Article',
  social_media:  'Social Feed',
  cctv:          'CCTV Surveillance',
}

const TYPE_LABELS: Record<string, string> = {
  theft:            'Theft',
  assault:          'Assault',
  harassment:       'Harassment',
  robbery:          'Robbery',
  vandalism:        'Vandalism',
  suspicious:       'Suspicious Activity',
  traffic:          'Traffic Incident',
  natural_disaster: 'Natural Disaster',
  fire:             'Fire Incident',
  medical:          'Medical Emergency',
  other:            'Other Safety Concern',
}

export function IncidentDetailScreen() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [incident, setIncident] = React.useState<Incident | null>(null)
  const [nearby, setNearby] = React.useState<Incident[]>([])
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (!id) return
    setLoading(true)
    incidentApi.getIncident(id)
      .then((inc) => {
        setIncident(inc)
        return incidentApi.getIncidents({
          lat: inc.location.lat,
          lng: inc.location.lng,
          radius: 1,
          limit: 6,
        })
      })
      .then((res) => {
        setNearby(res.data.filter(i => i.id !== id).slice(0, 5))
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-full gap-3 bg-[#07110A]">
        <Loader2 className="h-8 w-8 text-[#66BB6A] animate-spin" />
        <p className="text-xs text-[#9BAF9F]">Loading safety intelligence record...</p>
      </div>
    )
  }

  if (error || !incident) {
    return (
      <div className="flex flex-col items-center justify-center min-h-full gap-4 px-6 bg-[#07110A]">
        <AlertTriangle className="h-10 w-10 text-[#EF4444]" />
        <p className="text-base font-bold text-[#F1F8F2]">Incident record unavailable</p>
        <p className="text-xs text-[#9BAF9F] text-center">{error || 'This record may have been archived or removed.'}</p>
        <button
          onClick={() => navigate(-1)}
          className="px-6 py-2.5 rounded-xl text-xs font-bold text-[#07110A] bg-[#66BB6A]"
        >
          Return Back
        </button>
      </div>
    )
  }

  const sev = SEVERITY_CONFIG[incident.severity as keyof typeof SEVERITY_CONFIG] || SEVERITY_CONFIG.medium
  const reportedDate = new Date(incident.reportedAt)

  return (
    <div className="min-h-full max-w-lg mx-auto animate-fade-in-up pb-safe bg-[#07110A]">
      {/* Header */}
      <div className="sticky top-0 z-10 flex items-center gap-3 px-4 py-3 border-b border-[#1D3823] bg-[#07110A]">
        <button
          onClick={() => navigate(-1)}
          className="p-1.5 rounded-xl bg-[#0D1A10] border border-[#1D3823] text-[#8A948C] hover:text-[#F1F8F2]"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div>
          <h1 className="text-sm font-bold text-[#F1F8F2]">Incident Details</h1>
          <p className="text-[10px] text-[#8A948C]">ID: #{id?.slice(0, 8)}</p>
        </div>
      </div>

      <div className="px-4 py-5 space-y-4">
        {/* Severity Banner */}
        <div
          className="rounded-2xl p-5 avana-surface"
          style={{ border: `1px solid ${sev.color}40` }}
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <span
                  className="inline-flex items-center px-2.5 py-0.5 rounded text-[10px] font-extrabold uppercase tracking-wider"
                  style={{ background: sev.bg, color: sev.color }}
                >
                  {sev.label}
                </span>
                {incident.isVerified && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-[#122417] text-[#66BB6A] border border-[#1D3823]">
                    <ShieldCheck className="h-3 w-3" />
                    Verified Intelligence
                  </span>
                )}
              </div>
              <h2 className="text-lg font-extrabold text-[#F1F8F2] leading-snug">
                {TYPE_LABELS[incident.type] || incident.type}
              </h2>
            </div>
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
              style={{ background: sev.bg }}
            >
              <AlertTriangle className="h-5 w-5" style={{ color: sev.color }} />
            </div>
          </div>

          {incident.description && (
            <p className="mt-4 text-xs text-[#9BAF9F] leading-relaxed border-t border-[#1D3823] pt-3">
              {incident.description}
            </p>
          )}
        </div>

        {/* Intelligence Grid */}
        <div className="grid grid-cols-2 gap-3">
          <MetaCard
            icon={<Clock className="h-4 w-4 text-[#66BB6A]" />}
            label="Timestamp"
            value={formatRelativeTime(incident.reportedAt)}
            sub={reportedDate.toLocaleDateString('en-IN', {
              day: 'numeric', month: 'short', year: 'numeric',
            })}
          />
          <MetaCard
            icon={<MapPin className="h-4 w-4 text-[#66BB6A]" />}
            label="Location"
            value={incident.location.address || 'GPS Coordinates'}
            sub={`${incident.location.lat.toFixed(4)}, ${incident.location.lng.toFixed(4)}`}
          />
          <MetaCard
            icon={<ExternalLink className="h-4 w-4 text-[#F59E0B]" />}
            label="Source"
            value={SOURCE_LABELS[incident.source] || incident.source}
            sub={incident.status}
          />
          <MetaCard
            icon={<Shield className="h-4 w-4 text-[#66BB6A]" />}
            label="Confidence"
            value={incident.isVerified ? 'High' : 'Unverified'}
            sub={incident.isVerified ? 'Verified record' : 'Community report'}
          />
        </div>

        {/* View on Map CTA */}
        <button
          onClick={() => navigate('/map')}
          className="w-full flex items-center justify-between px-4 py-3.5 rounded-xl text-xs font-bold text-[#07110A] bg-[#66BB6A] hover:bg-[#81C784] transition-all"
        >
          <div className="flex items-center gap-2">
            <MapPin className="h-4 w-4" />
            View Incident Location on Safety Map
          </div>
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}

function MetaCard({
  icon, label, value, sub,
}: {
  icon: React.ReactNode
  label: string
  value: string
  sub?: string
}) {
  return (
    <div className="rounded-xl p-3 bg-[#0D1A10] border border-[#1D3823]">
      <div className="flex items-center gap-1.5 mb-1">
        {icon}
        <span className="text-[10px] text-[#8A948C] font-bold uppercase">{label}</span>
      </div>
      <p className="text-xs font-bold text-[#F1F8F2] truncate">{value}</p>
      {sub && <p className="text-[10px] text-[#9BAF9F] mt-0.5 truncate">{sub}</p>}
    </div>
  )
}

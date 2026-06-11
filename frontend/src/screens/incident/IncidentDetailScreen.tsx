import * as React from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  ArrowLeft, MapPin, Clock, AlertTriangle, Shield,
  ExternalLink, ChevronRight, Loader2,
} from 'lucide-react'
import { incidentApi } from '@/services/api'
import type { Incident } from '@/types'
import { formatRelativeTime } from '@/lib/utils'

const SEVERITY_CONFIG = {
  low:      { color: '#22C55E', bg: 'rgba(34,197,94,0.12)',    label: 'Low Risk' },
  medium:   { color: '#F59E0B', bg: 'rgba(245,158,11,0.12)',   label: 'Moderate Risk' },
  high:     { color: '#EF4444', bg: 'rgba(239,68,68,0.12)',    label: 'High Risk' },
  critical: { color: '#7C3AED', bg: 'rgba(124,58,237,0.12)',   label: 'Critical' },
}

const SOURCE_LABELS: Record<string, string> = {
  user_reported: 'Community Report',
  official:      'Official Source',
  news:          'News Report',
  social_media:  'Social Media',
  cctv:          'CCTV / Surveillance',
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
  fire:             'Fire',
  medical:          'Medical Emergency',
  other:            'Other',
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
        // Fetch nearby incidents
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
      <div className="flex flex-col items-center justify-center min-h-full gap-3">
        <Loader2 className="h-8 w-8 text-[#A855F7] animate-spin" />
        <p className="text-sm text-[#6B7280]">Loading incident details...</p>
      </div>
    )
  }

  if (error || !incident) {
    return (
      <div className="flex flex-col items-center justify-center min-h-full gap-4 px-6">
        <AlertTriangle className="h-10 w-10 text-[#EF4444]" />
        <p className="text-base font-semibold text-[#F9FAFB]">Incident not found</p>
        <p className="text-sm text-[#6B7280] text-center">{error || 'This incident may have been removed.'}</p>
        <button
          onClick={() => navigate(-1)}
          className="px-6 py-2.5 rounded-xl text-sm font-medium text-[#A855F7] border border-[#A855F7]/30 hover:bg-[#A855F7]/10 transition-colors"
        >
          Go Back
        </button>
      </div>
    )
  }

  const sev = SEVERITY_CONFIG[incident.severity as keyof typeof SEVERITY_CONFIG] || SEVERITY_CONFIG.medium
  const reportedDate = new Date(incident.reportedAt)

  return (
    <div className="min-h-full max-w-lg mx-auto animate-fade-in-up pb-safe">
      {/* Header */}
      <div className="sticky top-0 z-10 flex items-center gap-3 px-4 py-3 border-b border-[#1F2937]"
        style={{ background: 'rgba(9,9,11,0.95)', backdropFilter: 'blur(12px)' }}>
        <button
          onClick={() => navigate(-1)}
          className="p-2 rounded-lg hover:bg-[#1F2937] transition-colors text-[#6B7280]"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-base font-bold text-[#F9FAFB]">Incident Detail</h1>
          <p className="text-xs text-[#6B7280]">#{id?.slice(0, 8)}</p>
        </div>
      </div>

      <div className="px-4 py-5 space-y-4">
        {/* Hero severity card */}
        <div
          className="rounded-2xl p-5"
          style={{ background: '#1A1A24', border: `1px solid ${sev.color}30` }}
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <span
                  className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wide"
                  style={{ background: sev.bg, color: sev.color }}
                >
                  {sev.label}
                </span>
                {incident.isVerified && (
                  <span
                    className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-[10px] font-semibold"
                    style={{ background: 'rgba(34,197,94,0.12)', color: '#22C55E' }}
                  >
                    <Shield className="h-3 w-3" />
                    Verified
                  </span>
                )}
              </div>
              <h2 className="text-xl font-bold text-[#F9FAFB] leading-snug">
                {TYPE_LABELS[incident.type] || incident.type}
              </h2>
              {incident.title && incident.title !== TYPE_LABELS[incident.type] && (
                <p className="text-sm text-[#9CA3AF] mt-1">{incident.title}</p>
              )}
            </div>
            <div
              className="w-12 h-12 rounded-2xl flex items-center justify-center shrink-0"
              style={{ background: sev.bg }}
            >
              <AlertTriangle className="h-6 w-6" style={{ color: sev.color }} />
            </div>
          </div>

          {incident.description && (
            <p className="mt-4 text-sm text-[#9CA3AF] leading-relaxed border-t border-[#1F2937] pt-4">
              {incident.description}
            </p>
          )}
        </div>

        {/* Metadata grid */}
        <div className="grid grid-cols-2 gap-3">
          <MetaCard
            icon={<Clock className="h-4 w-4 text-[#A855F7]" />}
            label="Reported"
            value={formatRelativeTime(incident.reportedAt)}
            sub={reportedDate.toLocaleDateString('en-IN', {
              day: 'numeric', month: 'short', year: 'numeric',
              hour: '2-digit', minute: '2-digit',
            })}
          />
          <MetaCard
            icon={<MapPin className="h-4 w-4 text-[#EC4899]" />}
            label="Area"
            value={incident.location.address || 'Location data'}
            sub={`${incident.location.lat.toFixed(4)}, ${incident.location.lng.toFixed(4)}`}
          />
          <MetaCard
            icon={<ExternalLink className="h-4 w-4 text-[#F59E0B]" />}
            label="Source"
            value={SOURCE_LABELS[incident.source] || incident.source}
            sub={incident.status.replace(/_/g, ' ')}
          />
          <MetaCard
            icon={<Shield className="h-4 w-4 text-[#22C55E]" />}
            label="Confidence"
            value={incident.isVerified ? 'High' : 'Unverified'}
            sub={incident.isVerified ? 'Independently verified' : 'Community report'}
            valueColor={incident.isVerified ? '#22C55E' : '#F59E0B'}
          />
        </div>

        {/* View on map CTA */}
        <button
          onClick={() => navigate('/map')}
          className="w-full flex items-center justify-between px-4 py-4 rounded-2xl text-sm font-semibold transition-all"
          style={{
            background: 'rgba(168,85,247,0.1)',
            border: '1px solid rgba(168,85,247,0.25)',
            color: '#A855F7',
          }}
        >
          <div className="flex items-center gap-2">
            <MapPin className="h-4 w-4" />
            View on Safety Map
          </div>
          <ChevronRight className="h-4 w-4" />
        </button>

        {/* Nearby incidents */}
        {nearby.length > 0 && (
          <div
            className="rounded-2xl overflow-hidden"
            style={{ background: '#1A1A24', border: '1px solid #1F2937' }}
          >
            <div className="px-4 py-3 border-b border-[#1F2937]">
              <h3 className="text-sm font-semibold text-[#F9FAFB]">Nearby Incidents</h3>
              <p className="text-xs text-[#6B7280] mt-0.5">Within 1km of this location</p>
            </div>
            <div className="divide-y divide-[#1F2937]">
              {nearby.map((inc) => {
                const nearSev = SEVERITY_CONFIG[inc.severity as keyof typeof SEVERITY_CONFIG] || SEVERITY_CONFIG.medium
                return (
                  <button
                    key={inc.id}
                    onClick={() => navigate(`/incident/${inc.id}`)}
                    className="w-full flex items-center gap-3 px-4 py-3 hover:bg-[#1F2937] transition-colors text-left"
                  >
                    <div
                      className="w-2 h-2 rounded-full shrink-0"
                      style={{ background: nearSev.color, boxShadow: `0 0 6px ${nearSev.color}80` }}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-[#F9FAFB] truncate">
                        {TYPE_LABELS[inc.type] || inc.type}
                      </p>
                      <p className="text-xs text-[#6B7280]">{formatRelativeTime(inc.reportedAt)}</p>
                    </div>
                    <span
                      className="text-[10px] font-semibold px-2 py-0.5 rounded-full shrink-0"
                      style={{ background: nearSev.bg, color: nearSev.color }}
                    >
                      {nearSev.label}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function MetaCard({
  icon, label, value, sub, valueColor,
}: {
  icon: React.ReactNode
  label: string
  value: string
  sub?: string
  valueColor?: string
}) {
  return (
    <div className="rounded-xl p-3.5" style={{ background: '#111827', border: '1px solid #1F2937' }}>
      <div className="flex items-center gap-1.5 mb-2">
        {icon}
        <span className="text-xs text-[#6B7280] font-medium">{label}</span>
      </div>
      <p className="text-sm font-bold text-[#F9FAFB] truncate" style={{ color: valueColor }}>{value}</p>
      {sub && <p className="text-[10px] text-[#6B7280] mt-0.5 truncate">{sub}</p>}
    </div>
  )
}

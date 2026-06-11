import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Flag, MapPin, ChevronDown, CheckCircle, AlertCircle, Loader2, ArrowLeft,
} from 'lucide-react'
import { useGeolocation } from '@/hooks/useGeolocation'
import { incidentApi } from '@/services/api'
import { useUIStore } from '@/store/uiStore'

const INCIDENT_TYPES = [
  { value: 'theft', label: 'Theft' },
  { value: 'assault', label: 'Assault' },
  { value: 'harassment', label: 'Harassment' },
  { value: 'robbery', label: 'Robbery' },
  { value: 'vandalism', label: 'Vandalism' },
  { value: 'suspicious', label: 'Suspicious Activity' },
  { value: 'traffic', label: 'Traffic Incident' },
  { value: 'medical', label: 'Medical Emergency' },
  { value: 'other', label: 'Other' },
]

const SEVERITIES = [
  { value: 'low', label: 'Low', color: '#22C55E', desc: 'Minor concern' },
  { value: 'medium', label: 'Medium', color: '#F59E0B', desc: 'Moderate risk' },
  { value: 'high', label: 'High', color: '#EF4444', desc: 'Serious threat' },
]

type Status = 'idle' | 'submitting' | 'success' | 'error'

export function ReportIncidentScreen() {
  const navigate = useNavigate()
  const { position } = useGeolocation()
  const { addToast } = useUIStore()

  const [incidentType, setIncidentType] = React.useState('')
  const [severity, setSeverity] = React.useState('')
  const [description, setDescription] = React.useState('')
  const [locationText, setLocationText] = React.useState('')
  const [status, setStatus] = React.useState<Status>('idle')
  const [errorMsg, setErrorMsg] = React.useState('')
  const [typeOpen, setTypeOpen] = React.useState(false)

  // Auto-fill location from GPS
  React.useEffect(() => {
    if (position.latitude && position.longitude) {
      setLocationText(`${position.latitude.toFixed(5)}, ${position.longitude.toFixed(5)}`)
    }
  }, [position.latitude, position.longitude])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!incidentType || !severity) return

    setStatus('submitting')
    setErrorMsg('')

    try {
      // Parse location
      const coordMatch = locationText.match(/(-?\d+\.?\d*),\s*(-?\d+\.?\d*)/)
      const lat = coordMatch ? parseFloat(coordMatch[1]) : (position.latitude ?? 0)
      const lng = coordMatch ? parseFloat(coordMatch[2]) : (position.longitude ?? 0)

      await incidentApi.createReport({
        incident_type: incidentType,
        severity,
        latitude: lat,
        longitude: lng,
        description: description || undefined,
      })

      setStatus('success')
    } catch (err) {
      setStatus('error')
      setErrorMsg((err as Error).message || 'Failed to submit report')
    }
  }

  if (status === 'success') {
    return (
      <div className="flex flex-col items-center justify-center min-h-full px-6 py-12 animate-fade-in-up">
        <div className="w-full max-w-sm flex flex-col items-center gap-6 text-center">
          <div
            className="flex items-center justify-center w-20 h-20 rounded-full"
            style={{ background: 'rgba(34,197,94,0.12)' }}
          >
            <CheckCircle className="h-10 w-10 text-[#22C55E]" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[#F9FAFB] mb-2">Report Submitted</h2>
            <p className="text-sm text-[#6B7280]">
              Thank you. Your report helps keep the community safer.
            </p>
          </div>
          <div className="flex flex-col gap-3 w-full">
            <button
              onClick={() => navigate('/map')}
              className="w-full py-3 rounded-xl font-semibold text-sm transition-all"
              style={{ background: 'rgba(168,85,247,0.15)', color: '#A855F7', border: '1px solid rgba(168,85,247,0.3)' }}
            >
              View on Map
            </button>
            <button
              onClick={() => navigate('/')}
              className="w-full py-3 rounded-xl font-semibold text-sm text-[#6B7280] hover:text-[#F9FAFB] transition-colors"
            >
              Back to Home
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-full px-4 py-6 max-w-lg mx-auto animate-fade-in-up">
      {/* Header */}
      <div className="flex items-center gap-3 mb-8">
        <button
          onClick={() => navigate(-1)}
          className="p-2 rounded-lg hover:bg-[#1F2937] transition-colors text-[#6B7280]"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-xl font-bold text-[#F9FAFB]">Report Incident</h1>
          <p className="text-xs text-[#6B7280] mt-0.5">Help keep your community safe</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Incident Type */}
        <div className="space-y-2">
          <label className="text-sm font-semibold text-[#F9FAFB]">Incident Type</label>
          <div className="relative">
            <button
              type="button"
              onClick={() => setTypeOpen(!typeOpen)}
              className="w-full flex items-center justify-between px-4 py-3.5 rounded-xl text-sm text-left transition-all"
              style={{
                background: '#1A1A24',
                border: `1px solid ${incidentType ? 'rgba(168,85,247,0.4)' : '#1F2937'}`,
                color: incidentType ? '#F9FAFB' : '#6B7280',
              }}
            >
              <span>{incidentType ? INCIDENT_TYPES.find(t => t.value === incidentType)?.label : 'Select incident type'}</span>
              <ChevronDown className={`h-4 w-4 text-[#6B7280] transition-transform ${typeOpen ? 'rotate-180' : ''}`} />
            </button>
            {typeOpen && (
              <div
                className="absolute top-full mt-1 left-0 right-0 rounded-xl overflow-hidden z-50 shadow-2xl"
                style={{ background: '#1A1A24', border: '1px solid #1F2937' }}
              >
                {INCIDENT_TYPES.map((type) => (
                  <button
                    key={type.value}
                    type="button"
                    onClick={() => { setIncidentType(type.value); setTypeOpen(false) }}
                    className="w-full text-left px-4 py-3 text-sm transition-colors hover:bg-[#1F2937]"
                    style={{ color: incidentType === type.value ? '#A855F7' : '#F9FAFB' }}
                  >
                    {type.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Severity */}
        <div className="space-y-2">
          <label className="text-sm font-semibold text-[#F9FAFB]">Severity</label>
          <div className="grid grid-cols-3 gap-2">
            {SEVERITIES.map((sev) => (
              <button
                key={sev.value}
                type="button"
                onClick={() => setSeverity(sev.value)}
                className="flex flex-col items-center gap-1 py-3 px-2 rounded-xl text-xs font-semibold transition-all"
                style={{
                  background: severity === sev.value ? `${sev.color}20` : '#1A1A24',
                  border: `1px solid ${severity === sev.value ? `${sev.color}60` : '#1F2937'}`,
                  color: severity === sev.value ? sev.color : '#6B7280',
                  transform: severity === sev.value ? 'scale(1.02)' : 'scale(1)',
                }}
              >
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ background: sev.color, boxShadow: severity === sev.value ? `0 0 8px ${sev.color}80` : 'none' }}
                />
                <span>{sev.label}</span>
                <span className="text-[10px] opacity-70 font-normal">{sev.desc}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Location */}
        <div className="space-y-2">
          <label className="text-sm font-semibold text-[#F9FAFB]">Location</label>
          <div className="relative">
            <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#A855F7]" />
            <input
              type="text"
              value={locationText}
              onChange={(e) => setLocationText(e.target.value)}
              placeholder="Detecting your location..."
              className="w-full pl-10 pr-4 py-3.5 rounded-xl text-sm bg-[#1A1A24] text-[#F9FAFB] placeholder:text-[#6B7280] outline-none transition-all"
              style={{ border: '1px solid #1F2937' }}
              onFocus={(e) => (e.target.style.borderColor = 'rgba(168,85,247,0.4)')}
              onBlur={(e) => (e.target.style.borderColor = '#1F2937')}
            />
          </div>
          <p className="text-xs text-[#6B7280] pl-1">Auto-detected from GPS — tap to edit if needed</p>
        </div>

        {/* Description */}
        <div className="space-y-2">
          <label className="text-sm font-semibold text-[#F9FAFB]">
            Description <span className="text-[#6B7280] font-normal">(optional)</span>
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Briefly describe what happened..."
            rows={4}
            className="w-full px-4 py-3.5 rounded-xl text-sm bg-[#1A1A24] text-[#F9FAFB] placeholder:text-[#6B7280] outline-none resize-none transition-all"
            style={{ border: '1px solid #1F2937' }}
            onFocus={(e) => (e.target.style.borderColor = 'rgba(168,85,247,0.4)')}
            onBlur={(e) => (e.target.style.borderColor = '#1F2937')}
          />
        </div>

        {/* Error */}
        {status === 'error' && (
          <div
            className="flex items-start gap-2 px-4 py-3 rounded-xl text-sm"
            style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', color: '#EF4444' }}
          >
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={!incidentType || !severity || status === 'submitting'}
          className="w-full py-4 rounded-xl font-bold text-sm text-white transition-all mt-2 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          style={{
            background: incidentType && severity
              ? 'linear-gradient(135deg, #A855F7 0%, #9333EA 100%)'
              : '#1A1A24',
            boxShadow: incidentType && severity ? '0 8px 32px rgba(168,85,247,0.3)' : 'none',
          }}
        >
          {status === 'submitting' ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Submitting...
            </>
          ) : (
            <>
              <Flag className="h-4 w-4" />
              Submit Report
            </>
          )}
        </button>
      </form>
    </div>
  )
}

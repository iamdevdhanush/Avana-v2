import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Flag, MapPin, ChevronDown, CheckCircle, AlertCircle, Loader2, ArrowLeft, ShieldCheck,
} from 'lucide-react'
import { useGeolocation } from '@/hooks/useGeolocation'
import { useLocationName } from '@/hooks/useLocationName'
import { incidentApi } from '@/services/api'
import { useUIStore } from '@/store/uiStore'

const INCIDENT_TYPES = [
  { value: 'theft', label: 'Theft / Stealing' },
  { value: 'assault', label: 'Physical Assault' },
  { value: 'harassment', label: 'Harassment / Stalking' },
  { value: 'robbery', label: 'Robbery / Mugging' },
  { value: 'vandalism', label: 'Vandalism / Damage' },
  { value: 'suspicious', label: 'Suspicious Activity' },
  { value: 'traffic', label: 'Road / Traffic Incident' },
  { value: 'medical', label: 'Medical Emergency' },
  { value: 'other', label: 'Other Safety Concern' },
]

const SEVERITIES = [
  { value: 'low', label: 'Low', color: '#66BB6A', desc: 'Minor concern' },
  { value: 'medium', label: 'Medium', color: '#F5B942', desc: 'Elevated caution' },
  { value: 'high', label: 'High', color: '#EF4444', desc: 'Serious threat' },
]

type Status = 'idle' | 'submitting' | 'success' | 'error'

export function ReportIncidentScreen() {
  const navigate = useNavigate()
  const { position, isFallback } = useGeolocation()
  const locationName = useLocationName(position.latitude, position.longitude)
  const { addToast } = useUIStore()

  const [incidentType, setIncidentType] = React.useState('')
  const [severity, setSeverity] = React.useState('')
  const [description, setDescription] = React.useState('')
  const [locationText, setLocationText] = React.useState('')
  const [status, setStatus] = React.useState<Status>('idle')
  const [errorMsg, setErrorMsg] = React.useState('')
  const [typeOpen, setTypeOpen] = React.useState(false)

  // Auto-fill location label from GPS
  React.useEffect(() => {
    if (position.latitude && position.longitude) {
      const name = locationName.displayName
      const coordFallback = `${position.latitude.toFixed(5)}, ${position.longitude.toFixed(5)}`
      setLocationText(name && name !== coordFallback ? name : 'Current Location (GPS Active)')
    } else if (isFallback) {
      setLocationText('Shivamogga, Karnataka')
    }
  }, [position.latitude, position.longitude, locationName.displayName, isFallback])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!incidentType || !severity) return

    setStatus('submitting')
    setErrorMsg('')

    try {
      const coordMatch = locationText.match(/(-?\d+\.?\d*),\s*(-?\d+\.?\d*)/)
      const lat = coordMatch ? parseFloat(coordMatch[1]) : (position.latitude ?? 13.9299)
      const lng = coordMatch ? parseFloat(coordMatch[2]) : (position.longitude ?? 75.5681)

      await incidentApi.createReport({
        incident_type: incidentType,
        severity,
        latitude: lat,
        longitude: lng,
        description: description || undefined,
      })

      setStatus('success')
      addToast({ title: 'Report Submitted', description: 'Added to community safety intelligence.', variant: 'success' })
    } catch (err) {
      setStatus('error')
      setErrorMsg((err as Error).message || 'Unable to submit report. Please check your connection.')
    }
  }

  // ── REASSURING SUCCESS STATE ──
  if (status === 'success') {
    return (
      <div className="flex flex-col items-center justify-center min-h-full px-6 py-12 animate-fade-in-up bg-[#07110A]">
        <div className="w-full max-w-sm flex flex-col items-center gap-6 text-center">
          <div className="flex items-center justify-center w-20 h-20 rounded-full bg-[#66BB6A]/12 border border-[#66BB6A]/30">
            <CheckCircle className="h-10 w-10 text-[#66BB6A]" />
          </div>
          <div className="space-y-2">
            <h2 className="text-2xl font-bold text-[#F1F8F2]">Report Submitted</h2>
            <p className="text-xs text-[#9BAF9F] leading-relaxed">
              Thank you. Your report has been added to the safety intelligence system and helps protect your community.
            </p>
          </div>
          <div className="flex flex-col gap-3 w-full pt-2">
            <button
              onClick={() => navigate('/map')}
              className="w-full py-3 rounded-xl font-bold text-xs text-[#07110A] bg-[#66BB6A] hover:bg-[#81C784] transition-all"
            >
              View Activity on Map
            </button>
            <button
              onClick={() => navigate('/')}
              className="w-full py-3 rounded-xl font-semibold text-xs text-[#8A948C] hover:text-[#F1F8F2] transition-colors"
            >
              Return to Home
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-full px-4 py-6 max-w-lg mx-auto animate-fade-in-up bg-[#07110A] space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate(-1)}
          className="p-2 rounded-xl bg-[#0D1A10] border border-[#1D3823] text-[#8A948C] hover:text-[#F1F8F2] transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div>
          <h1 className="text-lg font-bold text-[#F1F8F2]">Report an Incident</h1>
          <p className="text-xs text-[#9BAF9F]">Help improve safety intelligence in your area.</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* STEP 01: What happened? */}
        <div className="space-y-2 avana-surface p-4">
          <label className="flex items-center justify-between text-xs font-bold text-[#F1F8F2]">
            <span className="flex items-center gap-2">
              <span className="px-1.5 py-0.5 rounded bg-[#122417] border border-[#1D3823] text-[#66BB6A] text-[10px]">01</span>
              What happened?
            </span>
            <span className="text-[10px] text-[#EF4444] font-semibold">* Required</span>
          </label>

          <div className="relative pt-1">
            <button
              type="button"
              onClick={() => setTypeOpen(!typeOpen)}
              className="w-full flex items-center justify-between px-3.5 py-3 rounded-xl text-xs text-left bg-[#122417] border border-[#1D3823] text-[#F1F8F2] transition-all"
            >
              <span className={incidentType ? 'text-[#F1F8F2] font-semibold' : 'text-[#8A948C]'}>
                {incidentType ? INCIDENT_TYPES.find(t => t.value === incidentType)?.label : 'Select incident category...'}
              </span>
              <ChevronDown className={`h-4 w-4 text-[#8A948C] transition-transform ${typeOpen ? 'rotate-180' : ''}`} />
            </button>
            {typeOpen && (
              <div className="absolute top-full mt-1 left-0 right-0 rounded-xl bg-[#0D1A10] border border-[#1D3823] overflow-hidden z-50 shadow-2xl max-h-56 overflow-y-auto">
                {INCIDENT_TYPES.map((type) => (
                  <button
                    key={type.value}
                    type="button"
                    onClick={() => { setIncidentType(type.value); setTypeOpen(false) }}
                    className="w-full text-left px-4 py-3 text-xs transition-colors hover:bg-[#122417] flex items-center justify-between"
                    style={{ color: incidentType === type.value ? '#66BB6A' : '#F1F8F2' }}
                  >
                    <span>{type.label}</span>
                    {incidentType === type.value && <ShieldCheck className="h-3.5 w-3.5 text-[#66BB6A]" />}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* STEP 02: How serious was it? */}
        <div className="space-y-2 avana-surface p-4">
          <label className="flex items-center justify-between text-xs font-bold text-[#F1F8F2]">
            <span className="flex items-center gap-2">
              <span className="px-1.5 py-0.5 rounded bg-[#122417] border border-[#1D3823] text-[#66BB6A] text-[10px]">02</span>
              How serious was it?
            </span>
            <span className="text-[10px] text-[#EF4444] font-semibold">* Required</span>
          </label>

          <div className="grid grid-cols-3 gap-2 pt-1">
            {SEVERITIES.map((sev) => (
              <button
                key={sev.value}
                type="button"
                onClick={() => setSeverity(sev.value)}
                className="flex flex-col items-center gap-1 py-3 px-2 rounded-xl text-xs font-bold transition-all"
                style={{
                  background: severity === sev.value ? `${sev.color}15` : '#122417',
                  border: `1px solid ${severity === sev.value ? sev.color : '#1D3823'}`,
                  color: severity === sev.value ? sev.color : '#8A948C',
                }}
              >
                <span
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ background: sev.color }}
                />
                <span>{sev.label}</span>
                <span className="text-[9px] opacity-80 font-normal">{sev.desc}</span>
              </button>
            ))}
          </div>
        </div>

        {/* STEP 03: Where? */}
        <div className="space-y-2 avana-surface p-4">
          <label className="flex items-center justify-between text-xs font-bold text-[#F1F8F2]">
            <span className="flex items-center gap-2">
              <span className="px-1.5 py-0.5 rounded bg-[#122417] border border-[#1D3823] text-[#66BB6A] text-[10px]">03</span>
              Where did this happen?
            </span>
          </label>

          <div className="relative pt-1">
            <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#66BB6A]" />
            <input
              type="text"
              value={locationText}
              onChange={(e) => setLocationText(e.target.value)}
              placeholder="Detecting location..."
              className="w-full pl-9 pr-4 py-2.5 rounded-xl text-xs bg-[#122417] text-[#F1F8F2] placeholder:text-[#8A948C] outline-none border border-[#1D3823] focus:border-[#66BB6A]"
            />
          </div>
          <p className="text-[10px] text-[#9BAF9F] pl-1">
            Defaults to your current GPS position — edit location text if needed.
          </p>
        </div>

        {/* STEP 04: Additional details */}
        <div className="space-y-2 avana-surface p-4">
          <label className="flex items-center justify-between text-xs font-bold text-[#F1F8F2]">
            <span className="flex items-center gap-2">
              <span className="px-1.5 py-0.5 rounded bg-[#122417] border border-[#1D3823] text-[#66BB6A] text-[10px]">04</span>
              Additional details
            </span>
            <span className="text-[10px] text-[#8A948C]">Optional</span>
          </label>

          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Briefly describe what happened..."
            rows={3}
            className="w-full px-3.5 py-2.5 rounded-xl text-xs bg-[#122417] text-[#F1F8F2] placeholder:text-[#8A948C] outline-none resize-none border border-[#1D3823] focus:border-[#66BB6A]"
          />
        </div>

        {/* Error notification */}
        {status === 'error' && (
          <div className="flex items-start gap-2 p-3 rounded-xl bg-[#EF4444]/10 border border-[#EF4444]/20 text-xs text-[#EF4444]">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Submit Button */}
        <button
          type="submit"
          disabled={!incidentType || !severity || status === 'submitting'}
          className="w-full py-3.5 rounded-xl font-bold text-xs text-[#07110A] bg-[#66BB6A] hover:bg-[#81C784] transition-all disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          {status === 'submitting' ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Submitting Report...
            </>
          ) : (
            <>
              <Flag className="h-4 w-4" />
              Submit Incident Report
            </>
          )}
        </button>
      </form>
    </div>
  )
}

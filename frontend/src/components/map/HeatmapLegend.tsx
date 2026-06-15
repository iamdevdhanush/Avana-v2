import * as React from 'react'

const LEVELS = [
  { range: '90–100', label: 'Critical', color: '#D50000', level: 5 },
  { range: '75–89', label: 'High', color: '#FF1744', level: 4 },
  { range: '50–74', label: 'Elevated', color: '#FF8C00', level: 3 },
  { range: '25–49', label: 'Moderate', color: '#FFD600', level: 2 },
  { range: '0–24', label: 'Low', color: '#00E676', level: 1 },
]

interface HeatmapLegendProps {
  visible?: boolean
}

export function HeatmapLegend({ visible: initialVisible = true }: HeatmapLegendProps) {
  const [visible, setVisible] = React.useState(initialVisible)

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{
        background: '#0F0F16',
        border: '1px solid #1F2937',
        backdropFilter: 'blur(12px)',
        width: '160px',
      }}
    >
      <button
        onClick={() => setVisible((v) => !v)}
        className="flex items-center justify-between w-full px-3 py-2 text-[10px] font-bold text-[#6B7280] uppercase tracking-wider hover:text-[#9CA3AF] transition-colors"
      >
        Risk Levels
        <svg
          className={`h-3 w-3 transition-transform ${visible ? 'rotate-180' : ''}`}
          viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      {visible && (
        <div className="px-3 pb-3 space-y-3">
          <div className="relative h-2 rounded-full overflow-hidden" style={{ background: '#1F2937' }}>
            <div
              className="absolute inset-0"
              style={{
                background: 'linear-gradient(90deg, #00E676 0%, #FFD600 25%, #FF8C00 50%, #FF1744 75%, #D50000 100%)',
              }}
            />
          </div>

          <div className="space-y-1.5">
            {LEVELS.map((l) => (
              <div key={l.label} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div
                    className="h-2 w-2 rounded-full shrink-0"
                    style={{
                      background: l.color,
                      boxShadow: l.level >= 4 ? `0 0 6px ${l.color}80` : 'none',
                    }}
                  />
                  <span className="text-[11px] text-[#D1D5DB] font-medium">{l.label}</span>
                </div>
                <span className="text-[9px] text-[#6B7280]">{l.range}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

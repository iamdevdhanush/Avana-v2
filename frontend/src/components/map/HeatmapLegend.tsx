import * as React from 'react'

const LEVELS = [
  { range: '90–100', label: 'Critical', color: '#D50000', glow: true },
  { range: '76–89', label: 'High', color: '#FF1744', glow: false },
  { range: '51–75', label: 'Elevated', color: '#FF8C00', glow: false },
  { range: '26–50', label: 'Moderate', color: '#FFD600', glow: false },
  { range: '0–25', label: 'Low', color: '#00E676', glow: false },
]

export function HeatmapLegend() {
  return (
    <div
      className="rounded-xl p-3.5 space-y-2.5"
      style={{
        background: '#0F0F16',
        border: '1px solid #1F2937',
        backdropFilter: 'blur(12px)',
      }}
    >
      <div className="text-[10px] font-bold text-[#6B7280] uppercase tracking-wider">
        Risk Levels
      </div>

      <div className="relative h-3 rounded-full overflow-hidden" style={{ background: '#1F2937' }}>
        <div
          className="absolute inset-0"
          style={{
            background: 'linear-gradient(90deg, #00E676 0%, #FFD600 30%, #FF8C00 55%, #FF1744 75%, #D50000 100%)',
          }}
        />
      </div>

      <div className="flex justify-between text-[9px] text-[#9CA3AF] font-medium">
        <span>Low</span>
        <span>Moderate</span>
        <span>Elevated</span>
        <span>High</span>
        <span>Critical</span>
      </div>

      <div className="pt-1 space-y-1.5">
        {LEVELS.map((l) => (
          <div key={l.label} className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div
                className="h-2.5 w-2.5 rounded-full"
                style={{
                  background: l.color,
                  boxShadow: l.glow ? `0 0 6px ${l.color}80` : undefined,
                }}
              />
              <span className="text-[11px] text-[#D1D5DB] font-medium">{l.label}</span>
            </div>
            <span className="text-[9px] text-[#6B7280]">{l.range}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

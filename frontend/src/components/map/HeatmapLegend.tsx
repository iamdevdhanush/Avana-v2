interface HeatmapLegendProps {
  visible?: boolean
}

export function HeatmapLegend({ visible = true }: HeatmapLegendProps) {
  if (!visible) return null

  const items = [
    { color: '#22C55E', label: 'Low Risk' },
    { color: '#EAB308', label: 'Moderate Risk' },
    { color: '#F97316', label: 'Elevated Risk' },
    { color: '#EF4444', label: 'High Risk' },
  ]

  return (
    <div
      className="glass-card-light px-3 py-2.5 flex flex-col gap-1.5"
      style={{
        background: 'rgba(9,9,11,0.82)',
        backdropFilter: 'blur(12px)',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: '10px',
        minWidth: '140px',
      }}
    >
      <p className="text-[9px] font-bold text-[#6B7280] uppercase tracking-widest mb-0.5">
        Risk Level
      </p>
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-2">
          <div
            className="w-2.5 h-2.5 rounded-full shrink-0"
            style={{
              background: item.color,
              boxShadow: `0 0 6px ${item.color}80`,
            }}
          />
          <span className="text-[11px] text-[#D1D5DB] font-medium">{item.label}</span>
        </div>
      ))}
    </div>
  )
}

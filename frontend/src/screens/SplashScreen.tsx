import * as React from 'react'
import { Shield } from 'lucide-react'

interface SplashScreenProps {
  onDone: () => void
}

export function SplashScreen({ onDone }: SplashScreenProps) {
  React.useEffect(() => {
    const timer = setTimeout(onDone, 1600)
    return () => clearTimeout(timer)
  }, [onDone])

  return (
    <div
      id="splash-screen"
      className="fixed inset-0 flex flex-col items-center justify-center bg-[#07110A] z-50 select-none"
      style={{ animation: 'fade-in 0.25s ease forwards' }}
    >
      <div className="flex flex-col items-center gap-5 animate-fade-in-up">
        {/* Shield Icon Badge */}
        <div className="w-20 h-20 rounded-2xl bg-[#122417] border border-[#66BB6A]/40 flex items-center justify-center shadow-2xl">
          <Shield className="h-10 w-10 text-[#66BB6A]" strokeWidth={2} />
        </div>

        {/* Wordmark */}
        <div className="flex flex-col items-center gap-1.5 text-center">
          <h1 className="text-3xl font-extrabold tracking-widest text-[#F1F8F2]">
            AVANA <span className="text-sm text-[#66BB6A] font-bold tracking-normal px-2 py-0.5 rounded bg-[#122417] border border-[#1D3823]">V2</span>
          </h1>
          <p className="text-xs font-semibold text-[#9BAF9F] uppercase tracking-wider">
            Karnataka Safety Intelligence
          </p>
        </div>
      </div>

      {/* Footer message */}
      <div className="absolute bottom-12 flex flex-col items-center gap-1">
        <p className="text-xs text-[#8A948C] font-medium tracking-wide">Trustworthy · Calm · Precise</p>
        <div className="flex gap-1.5 pt-2">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="h-1.5 w-1.5 rounded-full bg-[#66BB6A]"
              style={{ animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite` }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

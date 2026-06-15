import * as React from 'react'

interface SplashScreenProps {
  onDone: () => void
}

export function SplashScreen({ onDone }: SplashScreenProps) {
  React.useEffect(() => {
    const timer = setTimeout(onDone, 1800)
    return () => clearTimeout(timer)
  }, [onDone])

  return (
    <div
      id="splash-screen"
      className="fixed inset-0 flex flex-col items-center justify-center bg-[#09090B] z-50"
      style={{ animation: 'fade-in 0.4s ease forwards' }}
    >
      {/* Background radial glow */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: 'radial-gradient(ellipse 60% 50% at 50% 50%, rgba(168,85,247,0.08) 0%, transparent 70%)',
        }}
      />

      {/* Logo */}
      <div
        className="flex flex-col items-center gap-6 animate-fade-in-up"
        style={{ animationDelay: '100ms', animationFillMode: 'both' }}
      >
        {/* Logo with glow */}
        <div className="relative">
          <div className="animate-logo-glow flex items-center justify-center">
            <img
              src="/icons/icon-192x192.png"
              alt="Avana"
              className="h-24 w-24 object-contain"
              style={{ filter: 'drop-shadow(0 0 20px rgba(168,85,247,0.5))' }}
            />
          </div>
          {/* Outer glow rings */}
          <div
            className="absolute inset-0 rounded-full"
            style={{
              background: 'radial-gradient(circle, rgba(168,85,247,0.15) 0%, transparent 70%)',
              transform: 'scale(2)',
            }}
          />
        </div>

        {/* Wordmark */}
        <div className="flex flex-col items-center gap-2">
          <h1
            className="text-5xl font-black tracking-widest"
            style={{
              background: 'linear-gradient(135deg, #A855F7 0%, #EC4899 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
              letterSpacing: '0.3em',
            }}
          >
            AVANA
          </h1>
          <p
            className="text-sm font-medium tracking-[0.15em] text-[#6B7280] uppercase"
            style={{ animationDelay: '300ms', animationFillMode: 'both' }}
          >
            Safety Intelligence Platform
          </p>
        </div>
      </div>

      {/* Subtext */}
      <div
        className="absolute bottom-24 flex flex-col items-center gap-1 animate-fade-in"
        style={{ animationDelay: '600ms', animationFillMode: 'both' }}
      >
        <p className="text-[#374151] text-sm font-light tracking-wide">Safer Routes.</p>
        <p className="text-[#374151] text-sm font-light tracking-wide">Smarter Communities.</p>
      </div>

      {/* Loading dot */}
      <div
        className="absolute bottom-12 flex gap-1.5 animate-fade-in"
        style={{ animationDelay: '800ms', animationFillMode: 'both' }}
      >
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="h-1.5 w-1.5 rounded-full bg-[#A855F7]"
            style={{
              animation: `pulse 1.4s ease-in-out ${i * 0.2}s infinite`,
            }}
          />
        ))}
      </div>
    </div>
  )
}

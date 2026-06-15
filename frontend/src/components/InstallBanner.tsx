import { useState, useEffect, useCallback } from 'react'
import { Shield, X } from 'lucide-react'

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

const DISMISSED_KEY = 'avana_install_dismissed'
const DISMISS_EXPIRY_MS = 7 * 24 * 60 * 60 * 1000

function isDismissed(): boolean {
  try {
    const stored = localStorage.getItem(DISMISSED_KEY)
    if (!stored) return false
    const { timestamp } = JSON.parse(stored)
    return Date.now() - timestamp < DISMISS_EXPIRY_MS
  } catch {
    return false
  }
}

function markDismissed() {
  try {
    localStorage.setItem(DISMISSED_KEY, JSON.stringify({ timestamp: Date.now() }))
  } catch {}
}

export function InstallBanner() {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null)
  const [isVisible, setIsVisible] = useState(false)
  const [isAnimatingIn, setIsAnimatingIn] = useState(false)

  useEffect(() => {
    const handler = (e: Event) => {
      e.preventDefault()
      setDeferredPrompt(e as BeforeInstallPromptEvent)
      if (!isDismissed()) {
        setIsVisible(true)
        requestAnimationFrame(() => setIsAnimatingIn(true))
      }
    }
    window.addEventListener('beforeinstallprompt', handler)

    const checkStandalone = () => {
      if (window.matchMedia('(display-mode: standalone)').matches) {
        setIsVisible(false)
      }
    }
    checkStandalone()
    window.matchMedia('(display-mode: standalone)').addEventListener('change', checkStandalone)

    return () => {
      window.removeEventListener('beforeinstallprompt', handler)
      window.matchMedia('(display-mode: standalone)').removeEventListener('change', checkStandalone)
    }
  }, [])

  const handleInstall = useCallback(async () => {
    if (!deferredPrompt) return
    deferredPrompt.prompt()
    const { outcome } = await deferredPrompt.userChoice
    if (outcome === 'accepted') {
      setIsAnimatingIn(false)
      setTimeout(() => setIsVisible(false), 300)
    } else {
      markDismissed()
      setIsAnimatingIn(false)
      setTimeout(() => setIsVisible(false), 300)
    }
    setDeferredPrompt(null)
  }, [deferredPrompt])

  const handleDismiss = useCallback(() => {
    markDismissed()
    setIsAnimatingIn(false)
    setTimeout(() => setIsVisible(false), 300)
  }, [])

  if (!isVisible) return null

  return (
    <div
      className="fixed inset-x-0 bottom-20 z-[9999] flex justify-center pointer-events-none"
      style={{ padding: '0 env(safe-area-inset-left) 0 env(safe-area-inset-right)' }}
    >
      <div
        className={`pointer-events-auto mx-4 w-full max-w-sm rounded-2xl overflow-hidden transition-all duration-500 ease-out ${
          isAnimatingIn
            ? 'opacity-100 translate-y-0 scale-100'
            : 'opacity-0 translate-y-8 scale-95'
        }`}
        style={{
          background: 'linear-gradient(135deg, rgba(15,15,22,0.97) 0%, rgba(20,10,30,0.97) 100%)',
          border: '1px solid rgba(168,85,247,0.2)',
          boxShadow: '0 8px 48px rgba(168,85,247,0.15), 0 0 0 1px rgba(168,85,247,0.1) inset',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
        }}
      >
        <button
          onClick={handleDismiss}
          className="absolute top-3 right-3 p-1 rounded-full hover:bg-white/10 transition-colors z-10"
          aria-label="Dismiss"
        >
          <X className="h-4 w-4 text-[#6B7280]" />
        </button>

        <div className="p-5 pt-6">
          <div className="flex items-start gap-3.5">
            <div
              className="shrink-0 flex items-center justify-center w-12 h-12 rounded-2xl"
              style={{
                background: 'linear-gradient(135deg, rgba(168,85,247,0.2) 0%, rgba(236,72,153,0.2) 100%)',
                border: '1px solid rgba(168,85,247,0.25)',
              }}
            >
              <Shield className="h-6 w-6" style={{ color: '#A855F7' }} />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-base font-bold" style={{ color: '#F9FAFB' }}>
                Install Avana
              </h3>
              <p className="mt-1 text-xs leading-relaxed" style={{ color: '#9CA3AF' }}>
                Get instant access to women's safety intelligence, safe routes and emergency features.
              </p>
            </div>
          </div>

          <div className="mt-4 flex gap-2.5">
            <button
              onClick={handleDismiss}
              className="flex-1 py-2.5 px-4 rounded-xl text-sm font-medium transition-all duration-200 active:scale-95"
              style={{
                background: 'rgba(255,255,255,0.06)',
                color: '#9CA3AF',
                border: '1px solid rgba(255,255,255,0.08)',
              }}
            >
              Maybe Later
            </button>
            <button
              onClick={handleInstall}
              className="flex-1 py-2.5 px-4 rounded-xl text-sm font-bold text-white transition-all duration-200 active:scale-95"
              style={{
                background: 'linear-gradient(135deg, #A855F7 0%, #EC4899 100%)',
                boxShadow: '0 4px 16px rgba(168,85,247,0.35)',
              }}
            >
              Install
            </button>
          </div>
        </div>

        <div
          className="h-1 w-full"
          style={{
            background: 'linear-gradient(90deg, #A855F7, #EC4899, #A855F7)',
            backgroundSize: '200% 100%',
            animation: 'shimmer 2s linear infinite',
          }}
        />
      </div>
    </div>
  )
}

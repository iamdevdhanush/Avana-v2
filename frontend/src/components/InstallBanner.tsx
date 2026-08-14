import { useState, useEffect, useCallback } from 'react'
import { X, Shield } from 'lucide-react'

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
      if (typeof window.matchMedia === 'function' && window.matchMedia('(display-mode: standalone)').matches) {
        setIsVisible(false)
      }
    }
    checkStandalone()
    if (typeof window.matchMedia === 'function') {
      window.matchMedia('(display-mode: standalone)').addEventListener('change', checkStandalone)
    }

    return () => {
      window.removeEventListener('beforeinstallprompt', handler)
      if (typeof window.matchMedia === 'function') {
        window.matchMedia('(display-mode: standalone)').removeEventListener('change', checkStandalone)
      }
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
        className={`pointer-events-auto mx-4 w-full max-w-sm rounded-2xl overflow-hidden transition-all duration-300 ease-out ${
          isAnimatingIn
            ? 'opacity-100 translate-y-0 scale-100'
            : 'opacity-0 translate-y-8 scale-95'
        } avana-surface shadow-2xl border border-[#1D3823] bg-[#0D1A10]`}
      >
        <button
          onClick={handleDismiss}
          className="absolute top-3 right-3 p-1 rounded-full hover:bg-[#122417] transition-colors z-10"
          aria-label="Dismiss"
        >
          <X className="h-4 w-4 text-[#8A948C]" />
        </button>

        <div className="p-4 pt-5">
          <div className="flex items-start gap-3">
            <div className="shrink-0 flex items-center justify-center w-10 h-10 rounded-xl bg-[#122417] border border-[#1D3823] text-[#66BB6A]">
              <Shield className="w-5 h-5" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-bold text-[#F1F8F2]">
                Install Avana Web App
              </h3>
              <p className="mt-0.5 text-xs text-[#9BAF9F] leading-relaxed">
                Quick access to safety intelligence, safe routing, and emergency SOS features.
              </p>
            </div>
          </div>

          <div className="mt-4 flex gap-2">
            <button
              onClick={handleDismiss}
              className="flex-1 py-2 px-3 rounded-xl text-xs font-semibold text-[#8A948C] bg-[#07110A] border border-[#1D3823]"
            >
              Later
            </button>
            <button
              onClick={handleInstall}
              className="flex-1 py-2 px-3 rounded-xl text-xs font-bold text-[#07110A] bg-[#66BB6A] hover:bg-[#81C784] transition-all"
            >
              Install App
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

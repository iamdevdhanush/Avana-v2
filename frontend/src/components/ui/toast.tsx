import { useEffect } from 'react'
import { useUIStore } from '@/store/uiStore'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { cva } from 'class-variance-authority'

const toastVariants = cva(
  'group pointer-events-auto relative flex w-full items-center justify-between space-x-2 overflow-hidden rounded-md border p-4 pr-6 shadow-lg transition-all data-[swipe=cancel]:translate-x-0 data-[swipe=end]:translate-x-[var(--radix-toast-swipe-end-x)] data-[swipe=move]:translate-x-[var(--radix-toast-swipe-move-x)] data-[swipe=move]:transition-none data-[state=open]:animate-in data-[state=closed]:animate-out data-[swipe=end]:animate-out data-[state=closed]:fade-out-80 data-[state=closed]:slide-out-to-right-full data-[state=open]:slide-in-from-top-full',
  {
    variants: {
      variant: {
        default: 'border bg-card text-card-foreground',
        destructive: 'destructive group border-destructive bg-destructive text-destructive-foreground',
        success: 'border-safety-500/30 bg-safety-500/10 text-safety-500',
        warning: 'border-warning-500/30 bg-warning-500/10 text-warning-500',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
)

interface ToastProps {
  id: string
  title: string
  description?: string
  variant?: 'default' | 'destructive' | 'success' | 'warning'
  duration?: number
  onDismiss?: () => void
}

function Toast({ id, title, description, variant = 'default', duration = 5000, onDismiss }: ToastProps) {
  const removeToast = useUIStore((state) => state.removeToast)

  useEffect(() => {
    if (duration <= 0) return
    const timer = setTimeout(() => {
      removeToast(id)
      onDismiss?.()
    }, duration)
    return () => clearTimeout(timer)
  }, [id, duration, removeToast, onDismiss])

  const handleDismiss = () => {
    removeToast(id)
    onDismiss?.()
  }

  return (
    <div className={cn(toastVariants({ variant }))} role="alert">
      <div className="flex flex-col gap-1">
        <div className="text-sm font-semibold">{title}</div>
        {description && (
          <div className="text-xs opacity-90">{description}</div>
        )}
      </div>
      <button
        onClick={handleDismiss}
        className="absolute right-2 top-2 rounded-md p-1 opacity-0 transition-opacity group-hover:opacity-100"
      >
        <X className="h-3 w-3" />
      </button>
    </div>
  )
}

function ToastContainer() {
  const toasts = useUIStore((state) => state.toasts)
  const removeToast = useUIStore((state) => state.removeToast)

  if (toasts.length === 0) return null

  return (
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 max-w-sm">
      {toasts.map((toast) => (
        <Toast
          key={toast.id}
          id={toast.id}
          title={toast.title}
          description={toast.description}
          variant={toast.variant}
          duration={toast.duration}
          onDismiss={() => removeToast(toast.id)}
        />
      ))}
    </div>
  )
}

function Toaster() {
  return <ToastContainer />
}

import type { Toast as ToastType } from '@/store/uiStore'

export interface UseToastReturn {
  toast: (props: Omit<ToastType, 'id'>) => string
  dismiss: (id: string) => void
  dismissAll: () => void
}

export function useToast(): UseToastReturn {
  const addToast = useUIStore((state) => state.addToast)
  const removeToast = useUIStore((state) => state.removeToast)
  const toasts = useUIStore((state) => state.toasts)

  return {
    toast: (props: Omit<ToastType, 'id'>) => addToast(props),
    dismiss: (id) => removeToast(id),
    dismissAll: () => toasts.forEach((t) => removeToast(t.id)),
  }
}

export { Toast, ToastContainer, Toaster, toastVariants }

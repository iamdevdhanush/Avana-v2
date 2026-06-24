import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { format, formatDistanceToNow, parseISO } from 'date-fns'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(date: string | Date, pattern: string = 'PPp'): string {
  const d = typeof date === 'string' ? parseISO(date) : date
  return format(d, pattern)
}

export function formatRelativeTime(date: string | Date): string {
  const d = typeof date === 'string' ? parseISO(date) : date
  return formatDistanceToNow(d, { addSuffix: true })
}

export function formatDistance(meters: number): string {
  if (meters < 1000) {
    return `${Math.round(meters)}m`
  }
  return `${(meters / 1000).toFixed(1)}km`
}

export function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)

  if (hours > 0) {
    return `${hours}h ${minutes}m`
  }
  return `${minutes}min`
}

function isUnknown(category?: string): boolean {
  return category?.toLowerCase() === 'unknown'
}

export function getRiskColor(score: number, category?: string): string {
  if (isUnknown(category)) return 'var(--color-risk-unknown)'
  if (score >= 0.8) return 'var(--color-critical)'
  if (score >= 0.6) return 'var(--color-danger-500)'
  if (score >= 0.4) return 'var(--color-warning-500)'
  if (score >= 0.2) return 'var(--color-safety-400)'
  return 'var(--color-safety-600)'
}

export function getRiskLabel(score: number, category?: string): string {
  if (isUnknown(category)) return 'Unknown'
  if (score >= 0.8) return 'Critical'
  if (score >= 0.6) return 'High'
  if (score >= 0.4) return 'Moderate'
  if (score >= 0.2) return 'Low'
  return 'Safe'
}

export function getSeverityColor(severity: string): string {
  switch (severity) {
    case 'critical':
      return 'bg-critical text-white'
    case 'high':
      return 'bg-danger-500 text-white'
    case 'medium':
      return 'bg-warning-500 text-black'
    case 'low':
      return 'bg-safety-500 text-white'
    default:
      return 'bg-muted text-muted-foreground'
  }
}

export function getStatusColor(status: string): string {
  switch (status) {
    case 'active':
    case 'reported':
      return 'bg-danger-500/20 text-danger-500 border-danger-500/30'
    case 'verified':
    case 'investigating':
      return 'bg-warning-500/20 text-warning-500 border-warning-500/30'
    case 'resolved':
      return 'bg-safety-500/20 text-safety-500 border-safety-500/30'
    case 'dismissed':
    case 'cancelled':
      return 'bg-muted text-muted-foreground border-border'
    default:
      return 'bg-muted text-muted-foreground border-border'
  }
}

export function truncate(str: string, length: number = 100): string {
  if (str.length <= length) return str
  return str.slice(0, length).trimEnd() + '...'
}

export function generateId(): string {
  return crypto.randomUUID()
}

export function debounce<T extends (...args: unknown[]) => unknown>(
  fn: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timer: ReturnType<typeof setTimeout>
  return (...args: Parameters<T>) => {
    clearTimeout(timer)
    timer = setTimeout(() => fn(...args), delay)
  }
}

export function throttle<T extends (...args: unknown[]) => unknown>(
  fn: T,
  limit: number
): (...args: Parameters<T>) => void {
  let inThrottle = false
  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      fn(...args)
      inThrottle = true
      setTimeout(() => {
        inThrottle = false
      }, limit)
    }
  }
}

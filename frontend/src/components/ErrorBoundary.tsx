import { Component, ErrorInfo, ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('[ErrorBoundary] Uncaught error:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }
      return (
        <div
          className="flex flex-col items-center justify-center min-h-screen bg-background text-foreground p-6"
          style={{ background: '#09090B', color: '#F9FAFB' }}
        >
          <div className="flex items-center justify-center w-16 h-16 rounded-full bg-danger-muted mb-4">
            <svg className="w-8 h-8 text-danger" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
          <h2 className="text-lg font-bold mb-2">Something went wrong</h2>
          <p className="text-sm text-muted-foreground text-center mb-6 max-w-xs">
            Avana encountered an unexpected error. Please try refreshing the page.
          </p>
          <button
            onClick={() => {
              this.setState({ hasError: false, error: null })
              window.location.href = '/'
            }}
            className="px-6 py-2.5 rounded-xl text-sm font-semibold text-white transition-all hover:scale-105 active:scale-95"
            style={{ background: 'linear-gradient(135deg, #A855F7 0%, #EC4899 100%)' }}
          >
            Restart App
          </button>
          {this.state.error && (
            <details className="mt-4 w-full max-w-xs">
              <summary className="text-xs text-muted-foreground cursor-pointer">Error details</summary>
              <pre className="mt-2 p-3 rounded-lg text-xs text-muted-foreground overflow-auto max-h-32"
                style={{ background: 'rgba(255,255,255,0.05)' }}
              >
                {this.state.error.message}
              </pre>
            </details>
          )}
        </div>
      )
    }
    return this.props.children
  }
}

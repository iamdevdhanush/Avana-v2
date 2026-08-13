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
          className="flex flex-col items-center justify-center min-h-screen p-6"
          style={{ background: '#07110A', color: '#F1F8F2' }}
        >
          <div className="flex items-center justify-center w-16 h-16 rounded-full bg-[#EF4444]/12 mb-4">
            <svg className="w-8 h-8 text-[#EF4444]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
          <h2 className="text-lg font-bold mb-2 text-[#F1F8F2]">Something went wrong</h2>
          <p className="text-xs text-[#9BAF9F] text-center mb-6 max-w-xs leading-relaxed">
            Avana encountered an unexpected error. Please try restarting the application.
          </p>
          <button
            onClick={() => {
              this.setState({ hasError: false, error: null })
              window.location.href = '/'
            }}
            className="px-6 py-2.5 rounded-xl text-xs font-bold text-[#07110A] bg-[#66BB6A] hover:bg-[#81C784] transition-all"
          >
            Restart App
          </button>
          {this.state.error && (
            <details className="mt-4 w-full max-w-xs">
              <summary className="text-[10px] text-[#8A948C] cursor-pointer">Technical Details</summary>
              <pre
                className="mt-2 p-3 rounded-lg text-[10px] text-[#9BAF9F] overflow-auto max-h-32 bg-[#0D1A10] border border-[#1D3823]"
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

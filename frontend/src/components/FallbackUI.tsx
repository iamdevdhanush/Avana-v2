export function FallbackUI() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen p-6"
      style={{ background: '#09090B', color: '#F9FAFB' }}
    >
      <div className="flex items-center justify-center w-16 h-16 rounded-full mb-4"
        style={{ background: 'rgba(168, 85, 247, 0.12)' }}
      >
        <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none" stroke="#A855F7" strokeWidth="2">
          <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z" />
          <circle cx="12" cy="9" r="1.5" fill="#A855F7" />
        </svg>
      </div>
      <h2 className="text-lg font-bold mb-2">Unable to Connect</h2>
      <p className="text-sm text-center mb-6 max-w-xs" style={{ color: '#6B7280' }}>
        Avana is having trouble connecting to the server. Your safety features will work once the connection is restored.
      </p>
      <button
        onClick={() => window.location.reload()}
        className="px-6 py-2.5 rounded-xl text-sm font-semibold text-white transition-all hover:scale-105 active:scale-95"
        style={{ background: 'linear-gradient(135deg, #A855F7 0%, #EC4899 100%)' }}
      >
        Retry Connection
      </button>
      <p className="mt-6 text-xs text-center" style={{ color: '#374151' }}>
        Avana v2.0.0 &middot; Women Safety Intelligence
      </p>
    </div>
  )
}

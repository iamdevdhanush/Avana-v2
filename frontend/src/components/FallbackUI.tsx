export function FallbackUI() {
  return (
    <div
      className="flex flex-col items-center justify-center min-h-screen p-6 bg-[#07110A] text-[#F1F8F2]"
    >
      <div
        className="flex items-center justify-center w-16 h-16 rounded-full mb-4 bg-[#66BB6A]/12 border border-[#66BB6A]/30"
      >
        <svg className="w-8 h-8 text-[#66BB6A]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z" />
          <circle cx="12" cy="9" r="1.5" fill="#66BB6A" />
        </svg>
      </div>
      <h2 className="text-lg font-bold mb-2">Unable to Connect</h2>
      <p className="text-xs text-center mb-6 max-w-xs text-[#9BAF9F] leading-relaxed">
        Unable to connect to Avana safety intelligence servers. Please check network connection.
      </p>
      <button
        onClick={() => window.location.reload()}
        className="px-6 py-2.5 rounded-xl text-xs font-bold text-[#07110A] bg-[#66BB6A] hover:bg-[#81C784] transition-all"
      >
        Retry Connection
      </button>
      <p className="mt-6 text-[10px] text-center text-[#8A948C]">
        Avana v2.0 · Karnataka Safety Intelligence
      </p>
    </div>
  )
}

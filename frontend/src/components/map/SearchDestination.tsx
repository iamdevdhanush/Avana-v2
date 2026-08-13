import * as React from 'react'
import { Search, MapPin, Navigation, Clock, X, Loader2 } from 'lucide-react'
import { useGeolocation } from '@/hooks/useGeolocation'

interface DestinationOption {
  label: string
  address: string
  lat: number
  lng: number
}

const KNOWN_DESTINATIONS: DestinationOption[] = [
  { label: 'Shivamogga Bus Stand', address: 'NT Road, Shivamogga', lat: 13.9299, lng: 75.5681 },
  { label: 'Vinoba Nagar Market', address: '100 Feet Rd, Vinoba Nagar', lat: 13.9350, lng: 75.5780 },
  { label: 'Kuvempu University', address: 'Jnana Sahyadri, Shankaraghatta', lat: 13.7380, lng: 75.6320 },
  { label: 'McGann District Hospital', address: 'Jail Road, Shivamogga', lat: 13.9330, lng: 75.5650 },
  { label: 'Shivamogga Railway Station', address: 'KSRTC Colony, Shivamogga', lat: 13.9200, lng: 75.5700 },
]

interface SearchDestinationProps {
  value: string
  onSelectDestination: (dest: { label: string; lat: number; lng: number }) => void
  onClear?: () => void
}

export function SearchDestination({ value, onSelectDestination, onClear }: SearchDestinationProps) {
  const [query, setQuery] = React.useState(value)
  const [isOpen, setIsOpen] = React.useState(false)
  const [searching, setSearching] = React.useState(false)
  const [searchResults, setSearchResults] = React.useState<DestinationOption[]>([])
  const { position } = useGeolocation()

  const containerRef = React.useRef<HTMLDivElement>(null)

  // Filter recommendations or fetch geocoding suggestions
  React.useEffect(() => {
    if (!query.trim()) {
      setSearchResults([])
      return
    }

    const filtered = KNOWN_DESTINATIONS.filter(
      (d) => d.label.toLowerCase().includes(query.toLowerCase()) || d.address.toLowerCase().includes(query.toLowerCase())
    )

    // Check if user entered coordinates as fallback
    const coordMatch = query.match(/(-?\d+\.?\d*),\s*(-?\d+\.?\d*)/)
    if (coordMatch) {
      filtered.unshift({
        label: `Location (${coordMatch[1]}, ${coordMatch[2]})`,
        address: 'Specified geographic coordinate',
        lat: parseFloat(coordMatch[1]),
        lng: parseFloat(coordMatch[2]),
      })
    }

    setSearchResults(filtered)
  }, [query])

  // Close dropdown on outside click
  React.useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleSelect = (option: DestinationOption) => {
    setQuery(option.label)
    setIsOpen(false)
    onSelectDestination({ label: option.label, lat: option.lat, lng: option.lng })
  }

  return (
    <div ref={containerRef} className="relative w-full">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#8A948C]" />
        <input
          type="text"
          value={query}
          onFocus={() => setIsOpen(true)}
          onChange={(e) => {
            setQuery(e.target.value)
            setIsOpen(true)
          }}
          placeholder="Where are you going? Search destination..."
          className="w-full pl-9 pr-8 py-2.5 rounded-xl text-xs bg-[#0D1A10] text-[#F1F8F2] placeholder:text-[#8A948C] outline-none border border-[#1D3823] focus:border-[#66BB6A] transition-colors"
        />
        {query && (
          <button
            onClick={() => {
              setQuery('')
              onClear?.()
            }}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 text-[#8A948C] hover:text-[#F1F8F2]"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* Autocomplete Dropdown */}
      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-1 rounded-xl bg-[#0D1A10] border border-[#1D3823] shadow-2xl z-[1050] overflow-hidden max-h-60 overflow-y-auto">
          {query.trim() === '' ? (
            <div className="p-2 space-y-1">
              <p className="px-3 py-1.5 text-[10px] font-bold text-[#8A948C] uppercase tracking-wider">
                Popular Destinations
              </p>
              {KNOWN_DESTINATIONS.map((item) => (
                <button
                  key={item.label}
                  onClick={() => handleSelect(item)}
                  className="w-full flex items-center gap-2.5 px-3 py-2 text-left hover:bg-[#122417] transition-colors rounded-lg group"
                >
                  <MapPin className="h-3.5 w-3.5 text-[#66BB6A] shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-semibold text-[#F1F8F2] truncate group-hover:text-[#66BB6A] transition-colors">
                      {item.label}
                    </p>
                    <p className="text-[10px] text-[#8A948C] truncate">{item.address}</p>
                  </div>
                </button>
              ))}
            </div>
          ) : searchResults.length > 0 ? (
            <div className="p-2 space-y-1">
              {searchResults.map((item) => (
                <button
                  key={item.label}
                  onClick={() => handleSelect(item)}
                  className="w-full flex items-center gap-2.5 px-3 py-2 text-left hover:bg-[#122417] transition-colors rounded-lg group"
                >
                  <MapPin className="h-3.5 w-3.5 text-[#66BB6A] shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-semibold text-[#F1F8F2] truncate group-hover:text-[#66BB6A] transition-colors">
                      {item.label}
                    </p>
                    <p className="text-[10px] text-[#8A948C] truncate">{item.address}</p>
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <div className="px-4 py-3 text-center">
              <p className="text-xs text-[#8A948C]">No matching locations found.</p>
              <p className="text-[10px] text-[#8A948C] mt-0.5">Try searching landmark names or area names.</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

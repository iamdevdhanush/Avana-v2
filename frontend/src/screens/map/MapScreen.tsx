import * as React from 'react'
import { Search, SlidersHorizontal, X } from 'lucide-react'
import { SafetyMap } from '@/components/map/SafetyMap'
import { MapControls } from '@/components/map/MapControls'
import { LocationInfoPanel } from '@/components/map/LocationInfoPanel'
import { RoutePanel } from '@/components/map/RoutePanel'
import { useMapStore } from '@/store/mapStore'
import { useGeolocation } from '@/hooks/useGeolocation'
import { useHeatmap } from '@/hooks/useHeatmap'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { IncidentType } from '@/types'

const incidentTypes = [
  { value: 'all', label: 'All' },
  { value: 'theft', label: 'Theft' },
  { value: 'assault', label: 'Assault' },
  { value: 'harassment', label: 'Harassment' },
  { value: 'suspicious', label: 'Suspicious' },
  { value: 'traffic', label: 'Traffic' },
  { value: 'medical', label: 'Medical' },
]

const districts = [
  'All Districts',
  'Downtown',
  'Northside',
  'Southside',
  'Eastend',
  'Westend',
  'Central',
  'Suburbs',
]

const timeRanges = [
  { value: '24h', label: '24h' },
  { value: '7d', label: '7 Days' },
  { value: '30d', label: '30 Days' },
  { value: 'all', label: 'All Time' },
]

export function MapScreen() {
  const { bounds, zoom, selectedLocation, setSelectedLocation } = useMapStore()
  const { position } = useGeolocation()
  const { points, isLoading: heatmapLoading } = useHeatmap(bounds, zoom)
  const [showRoutePanel, setShowRoutePanel] = React.useState(false)
  const [searchQuery, setSearchQuery] = React.useState('')
  const [selectedDistrict, setSelectedDistrict] = React.useState('All Districts')
  const [selectedTime, setSelectedTime] = React.useState('24h')
  const [selectedType, setSelectedType] = React.useState<string>('all')
  const [showFilters, setShowFilters] = React.useState(false)
  const [districtOpen, setDistrictOpen] = React.useState(false)
  const [timeOpen, setTimeOpen] = React.useState(false)

  const handleLocationClick = (pos: { lat: number; lng: number }) => {
    setSelectedLocation(pos)
  }

  return (
    <div className="relative h-full w-full">
      <SafetyMap
        heatmapPoints={points}
        userLocation={position.latitude && position.longitude
          ? { lat: position.latitude, lng: position.longitude }
          : null}
        onLocationClick={handleLocationClick}
      >
        <MapControls onReportIncident={() => {}} />
      </SafetyMap>

      {showRoutePanel && (
        <RoutePanel onClose={() => setShowRoutePanel(false)} />
      )}

      {selectedLocation && (
        <LocationInfoPanel
          onGetSafeRoute={() => {
            setShowRoutePanel(true)
            setSelectedLocation(null)
          }}
          onClose={() => setSelectedLocation(null)}
        />
      )}

      <div className="absolute top-4 left-1/2 -translate-x-1/2 z-[1000] w-full max-w-md px-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search places..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 h-10 bg-card/90 backdrop-blur border-border shadow-lg"
          />
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={cn(
              'absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-md transition-colors',
              showFilters ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-accent'
            )}
          >
            <SlidersHorizontal className="h-4 w-4" />
          </button>
        </div>

        {showFilters && (
          <div className="mt-2 rounded-xl border border-border bg-card/95 backdrop-blur p-3 shadow-xl space-y-3">
            <div className="flex items-center gap-2 overflow-x-auto pb-1">
              {incidentTypes.map((t) => (
                <button
                  key={t.value}
                  onClick={() => setSelectedType(t.value)}
                  className={cn(
                    'whitespace-nowrap rounded-full px-3 py-1 text-xs font-medium transition-colors',
                    selectedType === t.value
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-muted-foreground hover:bg-accent'
                  )}
                >
                  {t.label}
                </button>
              ))}
            </div>

            <div className="flex gap-2">
              <div className="relative flex-1">
                <button
                  onClick={() => { setDistrictOpen(!districtOpen); setTimeOpen(false) }}
                  className="flex w-full items-center justify-between rounded-md border border-input bg-transparent px-3 py-1.5 text-xs"
                >
                  {selectedDistrict}
                  <svg className="h-3 w-3 ml-1 opacity-50" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="m6 9 6 6 6-6" />
                  </svg>
                </button>
                {districtOpen && (
                  <div className="absolute top-full mt-1 w-full rounded-md border border-border bg-popover p-1 shadow-lg z-10">
                    {districts.map((d) => (
                      <button
                        key={d}
                        onClick={() => { setSelectedDistrict(d); setDistrictOpen(false) }}
                        className="w-full rounded-sm px-2 py-1.5 text-xs text-left hover:bg-accent"
                      >
                        {d}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="relative flex-1">
                <button
                  onClick={() => { setTimeOpen(!timeOpen); setDistrictOpen(false) }}
                  className="flex w-full items-center justify-between rounded-md border border-input bg-transparent px-3 py-1.5 text-xs"
                >
                  {timeRanges.find((t) => t.value === selectedTime)?.label}
                  <svg className="h-3 w-3 ml-1 opacity-50" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="m6 9 6 6 6-6" />
                  </svg>
                </button>
                {timeOpen && (
                  <div className="absolute top-full mt-1 w-full rounded-md border border-border bg-popover p-1 shadow-lg z-10">
                    {timeRanges.map((t) => (
                      <button
                        key={t.value}
                        onClick={() => { setSelectedTime(t.value); setTimeOpen(false) }}
                        className="w-full rounded-sm px-2 py-1.5 text-xs text-left hover:bg-accent"
                      >
                        {t.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {!showRoutePanel && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-[1000]">
          <Button
            onClick={() => setShowRoutePanel(true)}
            variant="secondary"
            className="bg-card/90 backdrop-blur border border-border shadow-lg"
          >
            <svg className="h-4 w-4 mr-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2v20M2 12h20" />
            </svg>
            Find Safe Route
          </Button>
        </div>
      )}

      {heatmapLoading && (
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-[1000]">
          <div className="flex items-center gap-2 rounded-full bg-card/90 backdrop-blur px-4 py-2 border border-border shadow-lg">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            <span className="text-xs">Loading map data...</span>
          </div>
        </div>
      )}
    </div>
  )
}

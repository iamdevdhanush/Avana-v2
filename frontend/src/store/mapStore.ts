import { create } from 'zustand'
import type { HeatmapPoint, Incident, MapType, MapBounds } from '@/types'

interface MapState {
  center: [number, number]
  zoom: number
  bounds: MapBounds | null
  mapType: MapType
  heatmapPoints: HeatmapPoint[]
  incidents: Incident[]
  markers: {
    id: string
    position: [number, number]
    type: 'incident' | 'police' | 'hospital' | 'safe_zone' | 'user' | 'sos'
    data: unknown
  }[]
  selectedLocation: { lat: number; lng: number } | null
  isDrawing: boolean
  drawPath: [number, number][]

  setCenter: (center: [number, number]) => void
  setZoom: (zoom: number) => void
  setBounds: (bounds: MapBounds) => void
  setMapType: (type: MapType) => void
  setHeatmapPoints: (points: HeatmapPoint[]) => void
  setIncidents: (incidents: Incident[]) => void
  addMarker: (marker: MapState['markers'][0]) => void
  removeMarker: (id: string) => void
  clearMarkers: () => void
  setSelectedLocation: (location: { lat: number; lng: number } | null) => void
  setIsDrawing: (drawing: boolean) => void
  addDrawPoint: (point: [number, number]) => void
  clearDrawPath: () => void
  resetMap: () => void
}

const initialState = {
  center: [12.9716, 77.5946] as [number, number],
  zoom: 12,
  bounds: null,
  mapType: 'heatmap' as MapType,
  heatmapPoints: [] as HeatmapPoint[],
  incidents: [] as Incident[],
  markers: [] as MapState['markers'],
  selectedLocation: null,
  isDrawing: false,
  drawPath: [] as [number, number][],
}

export const useMapStore = create<MapState>()((set) => ({
  ...initialState,

  setCenter: (center) => set({ center }),
  setZoom: (zoom) => set({ zoom }),
  setBounds: (bounds) => set({ bounds }),
  setMapType: (type) => set({ mapType: type }),
  setHeatmapPoints: (points) => set({ heatmapPoints: points }),
  setIncidents: (incidents) => set({ incidents }),

  addMarker: (marker) =>
    set((state) => ({ markers: [...state.markers, marker] })),

  removeMarker: (id) =>
    set((state) => ({ markers: state.markers.filter((m) => m.id !== id) })),

  clearMarkers: () => set({ markers: [] }),

  setSelectedLocation: (location) => set({ selectedLocation: location }),

  setIsDrawing: (drawing) => set({ isDrawing: drawing }),
  addDrawPoint: (point) =>
    set((state) => ({ drawPath: [...state.drawPath, point] })),
  clearDrawPath: () => set({ drawPath: [] }),

  resetMap: () => set(initialState),
}))

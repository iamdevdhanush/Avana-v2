import { create } from 'zustand'
import type { Incident, IncidentType, IncidentSeverity, IncidentStatus, ApiResponse } from '@/types'
import { incidentApi } from '@/services/api'

interface IncidentFilters {
  type: IncidentType | 'all'
  severity: IncidentSeverity | 'all'
  status: IncidentStatus | 'all'
  search: string
  dateFrom: string
  dateTo: string
}

interface IncidentState {
  incidents: Incident[]
  selectedIncident: Incident | null
  filters: IncidentFilters
  pagination: {
    page: number
    limit: number
    total: number
    totalPages: number
  }
  isLoading: boolean
  error: string | null

  fetchIncidents: (page?: number) => Promise<void>
  selectIncident: (incident: Incident | null) => void
  setFilters: (filters: Partial<IncidentFilters>) => void
  resetFilters: () => void
  setPage: (page: number) => void
  clearError: () => void
}

const defaultFilters: IncidentFilters = {
  type: 'all',
  severity: 'all',
  status: 'all',
  search: '',
  dateFrom: '',
  dateTo: '',
}

export const useIncidentStore = create<IncidentState>()((set, get) => ({
  incidents: [],
  selectedIncident: null,
  filters: defaultFilters,
  pagination: {
    page: 1,
    limit: 20,
    total: 0,
    totalPages: 0,
  },
  isLoading: false,
  error: null,

  fetchIncidents: async (page?: number) => {
    const { filters, pagination } = get()
    set({ isLoading: true, error: null })
    try {
      const currentPage = page ?? pagination.page
      const params: Record<string, string | number | undefined> = {
        page: currentPage,
        limit: pagination.limit,
      }
      if (filters.type !== 'all') params.type = filters.type
      if (filters.severity !== 'all') params.severity = filters.severity
      if (filters.status !== 'all') params.status = filters.status
      if (filters.search) params.search = filters.search

      const response: ApiResponse<Incident[]> = await incidentApi.getIncidents(params)
      set({
        incidents: response.data,
        pagination: {
          ...get().pagination,
          page: currentPage,
          total: response.pagination?.total ?? 0,
          totalPages: response.pagination?.totalPages ?? 0,
        },
        isLoading: false,
      })
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false })
    }
  },

  selectIncident: (incident) => set({ selectedIncident: incident }),

  setFilters: (newFilters) =>
    set((state) => ({
      filters: { ...state.filters, ...newFilters },
      pagination: { ...state.pagination, page: 1 },
    })),

  resetFilters: () => set({ filters: defaultFilters, pagination: { ...get().pagination, page: 1 } }),

  setPage: (page) =>
    set((state) => ({
      pagination: { ...state.pagination, page },
    })),

  clearError: () => set({ error: null }),
}))

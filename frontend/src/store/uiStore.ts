import { create } from 'zustand'

export interface Toast {
  id: string
  title: string
  description?: string
  variant?: 'default' | 'destructive' | 'success' | 'warning'
  duration?: number
}

interface UIState {
  theme: 'dark' | 'light'
  sidebarOpen: boolean
  sidebarWidth: number
  activeModal: string | null
  modalData: unknown
  toasts: Toast[]
  isOnline: boolean

  toggleTheme: () => void
  setTheme: (theme: 'dark' | 'light') => void
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
  setSidebarWidth: (width: number) => void
  openModal: (modalId: string, data?: unknown) => void
  closeModal: () => void
  addToast: (toast: Omit<Toast, 'id'>) => string
  removeToast: (id: string) => void
  setIsOnline: (online: boolean) => void
}

export const useUIStore = create<UIState>()((set) => ({
  theme: 'dark',
  sidebarOpen: true,
  sidebarWidth: 280,
  activeModal: null,
  modalData: null,
  toasts: [],
  isOnline: navigator.onLine,

  toggleTheme: () =>
    set((state) => ({
      theme: state.theme === 'dark' ? 'light' : 'dark',
    })),

  setTheme: (theme) => set({ theme }),

  toggleSidebar: () =>
    set((state) => ({ sidebarOpen: !state.sidebarOpen })),

  setSidebarOpen: (open) => set({ sidebarOpen: open }),

  setSidebarWidth: (width) => set({ sidebarWidth: width }),

  openModal: (modalId, data = null) =>
    set({ activeModal: modalId, modalData: data }),

  closeModal: () => set({ activeModal: null, modalData: null }),

  addToast: (toast) => {
    const id = crypto.randomUUID()
    set((state) => ({
      toasts: [...state.toasts, { ...toast, id }],
    }))
    return id
  },

  removeToast: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    })),

  setIsOnline: (online) => set({ isOnline: online }),
}))

import { create } from 'zustand'
import type { User } from '@/types'
import { authApi } from '@/services/api'

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null

  login: (email: string, password: string) => Promise<void>
  signup: (data: { email: string; password: string; name: string; phone?: string }) => Promise<void>
  logout: () => Promise<void>
  loadUser: () => Promise<void>
  updateProfile: (updates: Partial<User>) => Promise<void>
  clearError: () => void
}

export const useAuthStore = create<AuthState>()((set, get) => ({
  user: null,
  token: localStorage.getItem('avana_token'),
  isAuthenticated: !!localStorage.getItem('avana_token'),
  isLoading: false,
  error: null,

  login: async (email: string, password: string) => {
    set({ isLoading: true, error: null })
    try {
      const { token, user } = await authApi.login(email, password)
      localStorage.setItem('avana_token', token)
      localStorage.setItem('avana_user', JSON.stringify(user))
      set({ user, token, isAuthenticated: true, isLoading: false })
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false })
      throw error
    }
  },

  signup: async (data) => {
    set({ isLoading: true, error: null })
    try {
      const { token, user } = await authApi.signup(data)
      localStorage.setItem('avana_token', token)
      localStorage.setItem('avana_user', JSON.stringify(user))
      set({ user, token, isAuthenticated: true, isLoading: false })
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false })
      throw error
    }
  },

  logout: async () => {
    set({ isLoading: true })
    try {
      await authApi.logout()
    } catch {
      // proceed with local logout even if API fails
    } finally {
      localStorage.removeItem('avana_token')
      localStorage.removeItem('avana_user')
      set({ user: null, token: null, isAuthenticated: false, isLoading: false, error: null })
    }
  },

  loadUser: async () => {
    const token = get().token
    if (!token) return

    set({ isLoading: true })
    try {
      const user = await authApi.getProfile()
      localStorage.setItem('avana_user', JSON.stringify(user))
      set({ user, isAuthenticated: true, isLoading: false })
    } catch {
      localStorage.removeItem('avana_token')
      localStorage.removeItem('avana_user')
      set({ user: null, token: null, isAuthenticated: false, isLoading: false })
    }
  },

  updateProfile: async (updates) => {
    set({ isLoading: true, error: null })
    try {
      const user = await authApi.updateProfile(updates)
      localStorage.setItem('avana_user', JSON.stringify(user))
      set({ user, isLoading: false })
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false })
      throw error
    }
  },

  clearError: () => set({ error: null }),
}))

import { Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from '@/components/ui/toast'
import { Layout } from '@/components/Layout'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { LoginScreen } from '@/screens/auth/LoginScreen'
import { SignupScreen } from '@/screens/auth/SignupScreen'
import { HomeScreen } from '@/screens/home/HomeScreen'
import { MapScreen } from '@/screens/map/MapScreen'
import { CommunityScreen } from '@/screens/community/CommunityScreen'
import { SOSScreen } from '@/screens/sos/SOSScreen'
import { ChatScreen } from '@/screens/chat/ChatScreen'
import { AdminDashboard } from '@/screens/admin/AdminDashboard'
import { AdminIncidents } from '@/screens/admin/AdminIncidents'
import { AdminUsers } from '@/screens/admin/AdminUsers'
import { AdminAgents } from '@/screens/admin/AdminAgents'
import { useAuthStore } from '@/store/authStore'
import { useEffect } from 'react'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      refetchOnWindowFocus: false,
      staleTime: 30000,
    },
  },
})

export default function App() {
  const { isAuthenticated, token, loadUser } = useAuthStore()

  useEffect(() => {
    if (token && !useAuthStore.getState().user) {
      loadUser()
    }
  }, [token, loadUser])

  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-background text-foreground">
        <Routes>
          <Route path="/login" element={<LoginScreen />} />
          <Route path="/signup" element={<SignupScreen />} />
          <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route path="/" element={<HomeScreen />} />
            <Route path="/map" element={<MapScreen />} />
            <Route path="/community" element={<CommunityScreen />} />
            <Route path="/sos" element={<SOSScreen />} />
            <Route path="/chat" element={<ChatScreen />} />
            <Route path="/analytics" element={<ProtectedRoute adminOnly><AdminDashboard /></ProtectedRoute>} />
            <Route path="/admin/incidents" element={<ProtectedRoute adminOnly><AdminIncidents /></ProtectedRoute>} />
            <Route path="/admin/users" element={<ProtectedRoute adminOnly><AdminUsers /></ProtectedRoute>} />
            <Route path="/admin/agents" element={<ProtectedRoute adminOnly><AdminAgents /></ProtectedRoute>} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <Toaster />
      </div>
    </QueryClientProvider>
  )
}

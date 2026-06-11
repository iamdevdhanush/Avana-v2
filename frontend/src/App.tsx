import { Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from '@/components/ui/toast'
import { Layout } from '@/components/Layout'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { LoginScreen } from '@/screens/auth/LoginScreen'
import { SignupScreen } from '@/screens/auth/SignupScreen'
import { SplashScreen } from '@/screens/SplashScreen'
import { HomeScreen } from '@/screens/home/HomeScreen'
import { MapScreen } from '@/screens/map/MapScreen'
import { SOSScreen } from '@/screens/sos/SOSScreen'
import { ReportIncidentScreen } from '@/screens/report/ReportIncidentScreen'
import { ProfileScreen } from '@/screens/profile/ProfileScreen'
import { IncidentDetailScreen } from '@/screens/incident/IncidentDetailScreen'
import { CommunityScreen } from '@/screens/community/CommunityScreen'
import { ChatScreen } from '@/screens/chat/ChatScreen'
import { AdminDashboard } from '@/screens/admin/AdminDashboard'
import { AdminIncidents } from '@/screens/admin/AdminIncidents'
import { AdminUsers } from '@/screens/admin/AdminUsers'
import { IntelligencePipeline } from '@/screens/admin/IntelligencePipeline'
import { useAuthStore } from '@/store/authStore'
import { useEffect, useState } from 'react'

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
  const { token, loadUser } = useAuthStore()
  const [showSplash, setShowSplash] = useState(() => {
    return !sessionStorage.getItem('avana_splashed')
  })

  useEffect(() => {
    if (token && !useAuthStore.getState().user) {
      loadUser()
    }
  }, [token, loadUser])

  const handleSplashDone = () => {
    sessionStorage.setItem('avana_splashed', '1')
    setShowSplash(false)
  }

  if (showSplash) {
    return <SplashScreen onDone={handleSplashDone} />
  }

  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-background text-foreground">
        <Routes>
          <Route path="/login" element={<LoginScreen />} />
          <Route path="/signup" element={<SignupScreen />} />
          <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route path="/" element={<HomeScreen />} />
            <Route path="/map" element={<MapScreen />} />
            <Route path="/report" element={<ReportIncidentScreen />} />
            <Route path="/sos" element={<SOSScreen />} />
            <Route path="/profile" element={<ProfileScreen />} />
            <Route path="/incident/:id" element={<IncidentDetailScreen />} />
            {/* Secondary routes — kept functional, not in primary nav */}
            <Route path="/community" element={<CommunityScreen />} />
            <Route path="/chat" element={<ChatScreen />} />
            {/* Admin routes */}
            <Route path="/analytics" element={<ProtectedRoute adminOnly><AdminDashboard /></ProtectedRoute>} />
            <Route path="/admin/incidents" element={<ProtectedRoute adminOnly><AdminIncidents /></ProtectedRoute>} />
            <Route path="/admin/users" element={<ProtectedRoute adminOnly><AdminUsers /></ProtectedRoute>} />
            <Route path="/admin/pipeline" element={<ProtectedRoute adminOnly><IntelligencePipeline /></ProtectedRoute>} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <Toaster />
      </div>
    </QueryClientProvider>
  )
}

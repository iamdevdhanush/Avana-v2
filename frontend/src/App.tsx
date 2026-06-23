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
import { useAuthStore } from '@/store/authStore'
import { useEffect, useState, lazy, Suspense } from 'react'

const AdminDashboard = lazy(() => import('@/screens/admin/AdminDashboard').then(m => ({ default: m.AdminDashboard })))
const AdminIncidents = lazy(() => import('@/screens/admin/AdminIncidents').then(m => ({ default: m.AdminIncidents })))
const AdminUsers = lazy(() => import('@/screens/admin/AdminUsers').then(m => ({ default: m.AdminUsers })))
const IntelligencePipeline = lazy(() => import('@/screens/admin/IntelligencePipeline').then(m => ({ default: m.IntelligencePipeline })))
const AdminAIConfig = lazy(() => import('@/screens/admin/AdminAIConfig').then(m => ({ default: m.AdminAIConfig })))

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
    try {
      return !sessionStorage.getItem('avana_splashed')
    } catch {
      return false
    }
  })
  const [initError, setInitError] = useState<string | null>(null)

  useEffect(() => {
    try {
      if (token && !useAuthStore.getState().user) {
        loadUser().catch(() => {})
      }
    } catch (e) {
      setInitError('Failed to initialize')
    }
  }, [token, loadUser])

  const handleSplashDone = () => {
    try {
      sessionStorage.setItem('avana_splashed', '1')
    } catch {}
    setShowSplash(false)
  }

  if (showSplash) {
    return <SplashScreen onDone={handleSplashDone} />
  }

  if (initError) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen p-6"
        style={{ background: '#09090B', color: '#F9FAFB' }}
      >
        <p className="text-sm text-center text-muted-foreground mb-4">Avana is loading...</p>
        <button
          onClick={() => { setInitError(null); window.location.reload() }}
          className="px-6 py-2.5 rounded-xl text-sm font-semibold text-white"
          style={{ background: 'linear-gradient(135deg, #A855F7 0%, #EC4899 100%)' }}
        >
          Retry
        </button>
      </div>
    )
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
            <Route path="/community" element={<CommunityScreen />} />
            <Route path="/chat" element={<ChatScreen />} />
            <Route path="/analytics" element={<ProtectedRoute adminOnly><Suspense fallback={<div className="flex h-32 items-center justify-center"><span className="text-sm text-muted-foreground">Loading...</span></div>}><AdminDashboard /></Suspense></ProtectedRoute>} />
            <Route path="/admin/incidents" element={<ProtectedRoute adminOnly><Suspense fallback={<div className="flex h-32 items-center justify-center"><span className="text-sm text-muted-foreground">Loading...</span></div>}><AdminIncidents /></Suspense></ProtectedRoute>} />
            <Route path="/admin/users" element={<ProtectedRoute adminOnly><Suspense fallback={<div className="flex h-32 items-center justify-center"><span className="text-sm text-muted-foreground">Loading...</span></div>}><AdminUsers /></Suspense></ProtectedRoute>} />
            <Route path="/admin/pipeline" element={<ProtectedRoute adminOnly><Suspense fallback={<div className="flex h-32 items-center justify-center"><span className="text-sm text-muted-foreground">Loading...</span></div>}><IntelligencePipeline /></Suspense></ProtectedRoute>} />
            <Route path="/admin/ai-config" element={<ProtectedRoute adminOnly><Suspense fallback={<div className="flex h-32 items-center justify-center"><span className="text-sm text-muted-foreground">Loading...</span></div>}><AdminAIConfig /></Suspense></ProtectedRoute>} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <Toaster />
      </div>
    </QueryClientProvider>
  )
}

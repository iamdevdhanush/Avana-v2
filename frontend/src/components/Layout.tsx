import * as React from 'react'
import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  Home, Map, Flag, AlertTriangle, User, Shield,
  Bell, LogOut, BarChart3, Users, Brain, Activity, ChevronRight,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/store/authStore'
import { useUIStore } from '@/store/uiStore'
import { InstallBanner } from '@/components/InstallBanner'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'

const PRIMARY_NAV = [
  { path: '/', label: 'Home', icon: Home },
  { path: '/map', label: 'Map', icon: Map },
  { path: '/report', label: 'Report', icon: Flag },
  { path: '/sos', label: 'SOS', icon: AlertTriangle, isSOS: true },
  { path: '/profile', label: 'Profile', icon: User },
]

const ROUTE_TITLES: Record<string, string> = {
  '/': 'Safety Intelligence',
  '/map': 'Live Safety Map',
  '/report': 'Report Incident',
  '/sos': 'Emergency SOS',
  '/profile': 'Your Safety Profile',
  '/community': 'Community Safety',
  '/chat': 'Safety Assistant',
  '/analytics': 'Admin Analytics',
  '/admin/incidents': 'Incident Moderation',
  '/admin/users': 'User Management',
  '/admin/pipeline': 'Intelligence Pipeline',
  '/admin/ai-config': 'AI Engine Settings',
}

export function Layout() {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()
  const { addToast } = useUIStore()

  const initials = user?.name?.split(' ').map(n => n[0]).join('').toUpperCase() || 'U'
  const isActive = (path: string) => location.pathname === path

  const isMapScreen = location.pathname === '/map'
  const pageTitle = ROUTE_TITLES[location.pathname] || 'Karnataka Safety Intelligence'

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <div className="flex flex-col h-screen bg-[#07110A] text-[#F1F8F2] overflow-hidden">
      {/* Install Banner */}
      <InstallBanner />

      {/* Header */}
      <header className="flex h-13 items-center justify-between px-4 border-b border-[#1D3823] bg-[#07110A] shrink-0 z-[1001]">
        {/* Brand & Page Context */}
        <div className="flex items-center gap-3">
          <div
            onClick={() => navigate('/')}
            className="flex items-center gap-2 cursor-pointer group"
          >
            <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-[#1B5E20]/60 border border-[#66BB6A]/30 text-[#66BB6A] group-hover:border-[#66BB6A]/60 transition-all">
              <Shield className="h-4 w-4" />
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-bold tracking-tight text-[#F1F8F2] flex items-center gap-1.5">
                AVANA
                <span className="text-[10px] font-semibold px-1.5 py-0.2 rounded bg-[#122417] border border-[#1D3823] text-[#A5D6A7]">
                  V2
                </span>
              </span>
            </div>
          </div>

          <div className="hidden sm:block h-4 w-px bg-[#1D3823]" />

          {/* Context Title */}
          <span className="hidden sm:inline-block text-xs text-[#9BAF9F] font-medium">
            {pageTitle}
          </span>
        </div>

        {/* Status + Actions */}
        <div className="flex items-center gap-3">
          {/* Operational Signal */}
          <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#0D1A10] border border-[#1D3823]">
            <span className="w-2 h-2 rounded-full bg-[#66BB6A]" />
            <span className="text-[11px] font-medium text-[#9BAF9F]">Operational</span>
          </div>

          {/* Notifications */}
          <button
            onClick={() => addToast({ title: 'Notifications', description: 'System monitoring active. No critical unread alerts.' })}
            className="relative p-2 rounded-lg hover:bg-[#0D1A10] transition-colors border border-transparent hover:border-[#1D3823]"
            title="Notifications"
          >
            <Bell className="h-4 w-4 text-[#9BAF9F]" />
            <span className="absolute top-1.5 right-1.5 h-1.5 w-1.5 rounded-full bg-[#EF4444]" />
          </button>

          {/* Profile Dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="flex items-center gap-2 p-1 rounded-lg hover:bg-[#0D1A10] transition-colors border border-transparent hover:border-[#1D3823]">
                <Avatar className="h-7 w-7 border border-[#1D3823]">
                  {user?.avatar ? (
                    <img src={user.avatar} alt={user.name} className="object-cover" />
                  ) : (
                    <AvatarFallback className="text-[11px] bg-[#122417] text-[#66BB6A] font-bold">
                      {initials}
                    </AvatarFallback>
                  )}
                </Avatar>
                <span className="hidden md:inline-block text-xs font-semibold text-[#F1F8F2] max-w-[100px] truncate">
                  {user?.name?.split(' ')[0]}
                </span>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52 bg-[#0D1A10] border-[#1D3823] text-[#F1F8F2]">
              <div className="px-3 py-2.5 border-b border-[#1D3823]">
                <p className="text-sm font-semibold text-[#F1F8F2] truncate">{user?.name}</p>
                <p className="text-xs text-[#9BAF9F] truncate">{user?.email}</p>
              </div>
              <DropdownMenuItem
                onClick={() => navigate('/profile')}
                className="text-[#F1F8F2] focus:bg-[#122417] focus:text-[#66BB6A] cursor-pointer"
              >
                <User className="mr-2 h-4 w-4" />
                Your Safety Profile
              </DropdownMenuItem>

              {user?.role === 'admin' && (
                <>
                  <DropdownMenuSeparator className="bg-[#1D3823]" />
                  <div className="px-2 py-1 text-[10px] font-semibold text-[#9BAF9F] uppercase tracking-wider">
                    Admin Tools
                  </div>
                  <DropdownMenuItem
                    onClick={() => navigate('/analytics')}
                    className="text-[#F1F8F2] focus:bg-[#122417] focus:text-[#66BB6A] cursor-pointer text-xs"
                  >
                    <BarChart3 className="mr-2 h-3.5 w-3.5" />
                    Admin Analytics
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={() => navigate('/admin/incidents')}
                    className="text-[#F1F8F2] focus:bg-[#122417] focus:text-[#66BB6A] cursor-pointer text-xs"
                  >
                    <Shield className="mr-2 h-3.5 w-3.5" />
                    Moderate Incidents
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={() => navigate('/admin/users')}
                    className="text-[#F1F8F2] focus:bg-[#122417] focus:text-[#66BB6A] cursor-pointer text-xs"
                  >
                    <Users className="mr-2 h-3.5 w-3.5" />
                    Manage Users
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={() => navigate('/admin/pipeline')}
                    className="text-[#F1F8F2] focus:bg-[#122417] focus:text-[#66BB6A] cursor-pointer text-xs"
                  >
                    <Activity className="mr-2 h-3.5 w-3.5" />
                    Intelligence Pipeline
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={() => navigate('/admin/ai-config')}
                    className="text-[#F1F8F2] focus:bg-[#122417] focus:text-[#66BB6A] cursor-pointer text-xs"
                  >
                    <Brain className="mr-2 h-3.5 w-3.5" />
                    AI Engine Config
                  </DropdownMenuItem>
                </>
              )}

              <DropdownMenuSeparator className="bg-[#1D3823]" />
              <DropdownMenuItem
                onClick={handleLogout}
                className="text-[#EF4444] focus:bg-[#EF4444]/10 focus:text-[#EF4444] cursor-pointer"
              >
                <LogOut className="mr-2 h-4 w-4" />
                Sign Out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      {/* Main Content Viewport */}
      <main className={cn(
        'flex-1 overflow-auto relative',
        !isMapScreen && 'pb-16'
      )}>
        <Outlet />
      </main>

      {/* Navigation Bar */}
      <nav className="fixed bottom-0 left-0 right-0 z-[1000] bottom-nav-height border-t border-[#1D3823] bg-[#07110A]/95 backdrop-blur-xl">
        <div className="max-w-md mx-auto flex items-center justify-around h-16 px-3">
          {PRIMARY_NAV.map((item) => {
            const active = isActive(item.path)
            return (
              <NavLink
                key={item.path}
                to={item.path}
                id={`nav-${item.label.toLowerCase()}`}
                className="flex flex-col items-center justify-center gap-1 flex-1 h-full relative group"
              >
                {/* SOS Tab */}
                {item.isSOS ? (
                  <div className={cn(
                    'relative flex flex-col items-center gap-0.5 transition-all duration-200',
                    active ? 'scale-105' : 'group-hover:scale-105'
                  )}>
                    <div className={cn(
                      'relative flex items-center justify-center w-9 h-9 rounded-full transition-all duration-200',
                      active
                        ? 'bg-[#EF4444] shadow-[0_0_16px_rgba(239,68,68,0.5)]'
                        : 'bg-[#EF4444]/20 group-hover:bg-[#EF4444]/30'
                    )}>
                      <item.icon className={cn(
                        'h-4.5 w-4.5 transition-colors',
                        active ? 'text-white' : 'text-[#EF4444]'
                      )} />
                      {!active && (
                        <span className="absolute inset-0 rounded-full animate-ping bg-[#EF4444]/20" />
                      )}
                    </div>
                    <span className={cn(
                      'text-[10px] font-bold tracking-wider uppercase',
                      active ? 'text-[#EF4444]' : 'text-[#EF4444]/80'
                    )}>
                      {item.label}
                    </span>
                  </div>
                ) : (
                  <div className={cn(
                    'flex flex-col items-center gap-0.5 transition-all duration-150',
                    active ? 'scale-100' : 'group-hover:scale-100'
                  )}>
                    {/* Active Top Bar */}
                    <div className={cn(
                      'absolute top-0 left-1/2 -translate-x-1/2 h-0.5 w-6 rounded-full transition-all duration-200',
                      active ? 'bg-[#66BB6A] opacity-100' : 'opacity-0'
                    )} />
                    <item.icon className={cn(
                      'h-5 w-5 transition-colors duration-150',
                      active ? 'text-[#66BB6A]' : 'text-[#8A948C] group-hover:text-[#9BAF9F]'
                    )} />
                    <span className={cn(
                      'text-[10px] font-semibold transition-colors duration-150',
                      active ? 'text-[#66BB6A]' : 'text-[#8A948C] group-hover:text-[#9BAF9F]'
                    )}>
                      {item.label}
                    </span>
                  </div>
                )}
              </NavLink>
            )
          })}
        </div>
      </nav>
    </div>
  )
}

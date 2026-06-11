import * as React from 'react'
import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  Home, Map, Flag, AlertTriangle, User, Shield,
  Bell, ChevronRight, LogOut, BarChart3, Users,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/store/authStore'
import { useUIStore } from '@/store/uiStore'
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

export function Layout() {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()
  const { addToast } = useUIStore()

  const initials = user?.name?.split(' ').map(n => n[0]).join('').toUpperCase() || 'U'
  const isActive = (path: string) => location.pathname === path

  // Map screen uses full viewport — no padding
  const isMapScreen = location.pathname === '/map'

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <div className="flex flex-col h-screen bg-[#09090B] text-[#F9FAFB] overflow-hidden">
      {/* Header */}
      <header className="flex h-12 items-center justify-between px-4 border-b border-[#1F2937] bg-[#09090B] shrink-0 z-30">
        <div className="flex items-center gap-2">
          <Shield className="h-5 w-5 text-[#A855F7]" />
          <span
            className="text-base font-bold tracking-tight"
            style={{
              background: 'linear-gradient(135deg, #A855F7 0%, #EC4899 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            AVANA
          </span>
        </div>

        <div className="flex items-center gap-1">
          {/* Notifications */}
          <button className="relative p-2 rounded-lg hover:bg-[#1F2937] transition-colors">
            <Bell className="h-4 w-4 text-[#6B7280]" />
            <span className="absolute top-1.5 right-1.5 h-1.5 w-1.5 rounded-full bg-[#EF4444]" />
          </button>

          {/* Profile/Admin dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="flex items-center gap-1.5 p-1.5 rounded-lg hover:bg-[#1F2937] transition-colors">
                <Avatar className="h-6 w-6">
                  {user?.avatar ? (
                    <img src={user.avatar} alt={user.name} className="object-cover" />
                  ) : (
                    <AvatarFallback className="text-[10px] bg-[#A855F7]/20 text-[#A855F7]">
                      {initials}
                    </AvatarFallback>
                  )}
                </Avatar>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48 bg-[#1A1A24] border-[#1F2937]">
              <div className="px-3 py-2 border-b border-[#1F2937]">
                <p className="text-sm font-medium text-[#F9FAFB] truncate">{user?.name}</p>
                <p className="text-xs text-[#6B7280] capitalize">{user?.role}</p>
              </div>
              <DropdownMenuItem
                onClick={() => navigate('/profile')}
                className="text-[#F9FAFB] hover:bg-[#1F2937] focus:bg-[#1F2937]"
              >
                <User className="mr-2 h-4 w-4" />
                Profile
              </DropdownMenuItem>
              {user?.role === 'admin' && (
                <>
                  <DropdownMenuSeparator className="bg-[#1F2937]" />
                  <DropdownMenuItem
                    onClick={() => navigate('/analytics')}
                    className="text-[#F9FAFB] hover:bg-[#1F2937] focus:bg-[#1F2937]"
                  >
                    <BarChart3 className="mr-2 h-4 w-4" />
                    Admin Dashboard
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={() => navigate('/admin/incidents')}
                    className="text-[#F9FAFB] hover:bg-[#1F2937] focus:bg-[#1F2937]"
                  >
                    <Shield className="mr-2 h-4 w-4" />
                    Moderate Incidents
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={() => navigate('/admin/users')}
                    className="text-[#F9FAFB] hover:bg-[#1F2937] focus:bg-[#1F2937]"
                  >
                    <Users className="mr-2 h-4 w-4" />
                    Manage Users
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={() => navigate('/admin/pipeline')}
                    className="text-[#F9FAFB] hover:bg-[#1F2937] focus:bg-[#1F2937]"
                  >
                    <BarChart3 className="mr-2 h-4 w-4" />
                    Intelligence Pipeline
                  </DropdownMenuItem>
                </>
              )}
              <DropdownMenuSeparator className="bg-[#1F2937]" />
              <DropdownMenuItem
                onClick={handleLogout}
                className="text-[#EF4444] hover:bg-[#EF4444]/10 focus:bg-[#EF4444]/10"
              >
                <LogOut className="mr-2 h-4 w-4" />
                Sign Out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      {/* Main Content */}
      <main className={cn(
        'flex-1 overflow-auto relative',
        !isMapScreen && 'pb-16'
      )}>
        <Outlet />
      </main>

      {/* Bottom Navigation */}
      <nav className="fixed bottom-0 left-0 right-0 z-40 bottom-nav-height border-t border-[#1F2937] bg-[#09090B]/95 backdrop-blur-xl">
        <div className="flex items-center justify-around h-16 px-2">
          {PRIMARY_NAV.map((item) => {
            const active = isActive(item.path)
            return (
              <NavLink
                key={item.path}
                to={item.path}
                id={`nav-${item.label.toLowerCase()}`}
                className="flex flex-col items-center justify-center gap-0.5 flex-1 h-full relative group"
              >
                {/* SOS tab — special styling */}
                {item.isSOS ? (
                  <div className={cn(
                    'relative flex flex-col items-center gap-0.5 transition-all duration-200',
                    active ? 'scale-110' : 'group-hover:scale-105'
                  )}>
                    <div className={cn(
                      'relative flex items-center justify-center w-10 h-10 rounded-full transition-all duration-200',
                      active
                        ? 'bg-[#EF4444] shadow-[0_0_20px_rgba(239,68,68,0.5)]'
                        : 'bg-[#EF4444]/20 group-hover:bg-[#EF4444]/30'
                    )}>
                      <item.icon className={cn(
                        'h-5 w-5 transition-colors',
                        active ? 'text-white' : 'text-[#EF4444]'
                      )} />
                      {/* Pulsing ring when inactive */}
                      {!active && (
                        <span className="absolute inset-0 rounded-full animate-ping bg-[#EF4444]/20" />
                      )}
                    </div>
                    <span className={cn(
                      'text-[10px] font-semibold tracking-wide',
                      active ? 'text-[#EF4444]' : 'text-[#EF4444]/70'
                    )}>
                      {item.label}
                    </span>
                  </div>
                ) : (
                  <div className={cn(
                    'flex flex-col items-center gap-0.5 transition-all duration-200',
                    active ? 'scale-105' : 'group-hover:scale-100'
                  )}>
                    {/* Active indicator bar */}
                    <div className={cn(
                      'absolute top-0 left-1/2 -translate-x-1/2 h-0.5 w-6 rounded-full transition-all duration-200',
                      active ? 'bg-[#A855F7] opacity-100' : 'opacity-0'
                    )} />
                    <item.icon className={cn(
                      'h-5 w-5 transition-colors duration-200',
                      active ? 'text-[#A855F7]' : 'text-[#6B7280] group-hover:text-[#9CA3AF]'
                    )} />
                    <span className={cn(
                      'text-[10px] font-medium transition-colors duration-200',
                      active ? 'text-[#A855F7]' : 'text-[#6B7280] group-hover:text-[#9CA3AF]'
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

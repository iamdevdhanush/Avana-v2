import * as React from 'react'
import { Outlet, NavLink, useLocation } from 'react-router-dom'
import {
  Home, Map, Users, AlertTriangle, MessageSquare, BarChart3,
  Menu, X, Bell, Search, ChevronDown, LogOut, User, Shield,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/store/authStore'
import { useUIStore } from '@/store/uiStore'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Input } from '@/components/ui/input'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

const navItems = [
  { path: '/', label: 'Home', icon: Home },
  { path: '/map', label: 'Safety Map', icon: Map },
  { path: '/community', label: 'Community', icon: Users },
  { path: '/sos', label: 'SOS', icon: AlertTriangle },
  { path: '/chat', label: 'AI Chat', icon: MessageSquare },
  { path: '/analytics', label: 'Analytics', icon: BarChart3, adminOnly: true },
]

export function Layout() {
  const location = useLocation()
  const { user, logout } = useAuthStore()
  const { sidebarOpen, toggleSidebar } = useUIStore()
  const [mobileOpen, setMobileOpen] = React.useState(false)
  const [searchOpen, setSearchOpen] = React.useState(false)

  const initials = user?.name?.split(' ').map(n => n[0]).join('').toUpperCase() || 'U'

  const isActive = (path: string) => location.pathname === path

  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden">
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-border bg-card transition-transform duration-300 lg:static lg:translate-x-0',
          mobileOpen ? 'translate-x-0' : '-translate-x-full',
          !sidebarOpen && 'lg:w-16'
        )}
      >
        <div className={cn('flex h-14 items-center border-b border-border px-4', !sidebarOpen && 'lg:justify-center')}>
          {sidebarOpen ? (
            <div className="flex items-center gap-2">
              <Shield className="h-6 w-6 text-primary" />
              <span className="text-lg font-bold">Avana</span>
            </div>
          ) : (
            <Shield className="h-6 w-6 text-primary" />
          )}
          <button onClick={() => setMobileOpen(false)} className="ml-auto lg:hidden">
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto p-2 space-y-1">
          {navItems.map((item) => {
            if (item.adminOnly && user?.role !== 'admin') return null
            return (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={() => setMobileOpen(false)}
                className={cn(
                  'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                  isActive(item.path)
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                  !sidebarOpen && 'lg:justify-center lg:px-2'
                )}
              >
                <item.icon className="h-5 w-5 shrink-0" />
                {sidebarOpen && <span>{item.label}</span>}
              </NavLink>
            )
          })}
        </nav>

        <Separator />

        <div className={cn('p-2', !sidebarOpen && 'lg:flex lg:justify-center')}>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                className={cn(
                  'flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors hover:bg-accent',
                  !sidebarOpen && 'lg:justify-center lg:px-2'
                )}
              >
                <Avatar className="h-8 w-8">
                  {user?.avatar ? (
                    <img src={user.avatar} alt={user.name} className="object-cover" />
                  ) : (
                    <AvatarFallback>{initials}</AvatarFallback>
                  )}
                </Avatar>
                {sidebarOpen && (
                  <>
                    <div className="flex-1 text-left">
                      <p className="text-sm font-medium">{user?.name}</p>
                      <p className="text-xs text-muted-foreground capitalize">{user?.role}</p>
                    </div>
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                  </>
                )}
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuItem onClick={() => {}}>
                <User className="mr-2 h-4 w-4" /> Profile
              </DropdownMenuItem>
              {user?.role === 'admin' && (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => window.location.href = '/admin/incidents'}>
                    <Shield className="mr-2 h-4 w-4" /> Moderate Incidents
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => window.location.href = '/admin/users'}>
                    <Users className="mr-2 h-4 w-4" /> Manage Users
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => window.location.href = '/admin/agents'}>
                    <BarChart3 className="mr-2 h-4 w-4" /> Agent Pipeline
                  </DropdownMenuItem>
                </>
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={logout}>
                <LogOut className="mr-2 h-4 w-4" /> Sign Out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </aside>

      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      <div className="flex flex-1 flex-col min-w-0">
        <header className="flex h-14 items-center border-b border-border bg-card px-4 gap-4">
          <button onClick={() => setMobileOpen(true)} className="lg:hidden">
            <Menu className="h-5 w-5" />
          </button>

          <button onClick={toggleSidebar} className="hidden lg:block">
            <Menu className="h-5 w-5" />
          </button>

          <div className={cn('flex-1', searchOpen ? 'block' : 'hidden md:block')}>
            <div className="relative max-w-md">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search locations, incidents..."
                className="pl-9 h-9 bg-muted/50 border-none"
              />
            </div>
          </div>

          <div className="flex items-center gap-2 ml-auto">
            <button
              onClick={() => setSearchOpen(!searchOpen)}
              className="md:hidden p-2 rounded-lg hover:bg-accent"
            >
              <Search className="h-5 w-5" />
            </button>

            <button className="relative p-2 rounded-lg hover:bg-accent">
              <Bell className="h-5 w-5" />
              <span className="absolute top-1 right-1 h-2 w-2 rounded-full bg-danger-500" />
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>

      <nav className="fixed bottom-0 left-0 right-0 z-30 border-t border-border bg-card lg:hidden">
        <div className="flex items-center justify-around px-2 py-1">
          {navItems.filter(i => !i.adminOnly || user?.role === 'admin').slice(0, 5).map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={cn(
                'flex flex-col items-center gap-0.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors',
                isActive(item.path)
                  ? 'text-primary'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              <item.icon className="h-5 w-5" />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  )
}

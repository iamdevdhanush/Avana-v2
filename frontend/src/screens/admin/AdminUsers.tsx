import * as React from 'react'
import {
  Search, ChevronLeft, ChevronRight, Shield, Loader2,
  UserCheck, UserX, ChevronDown,
} from 'lucide-react'
import { adminApi } from '@/services/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useUIStore } from '@/store/uiStore'
import { formatDate, cn } from '@/lib/utils'
import type { User } from '@/types'

interface UserWithPagination {
  users: User[]
  total: number
  page: number
  totalPages: number
}

export function AdminUsers() {
  const { addToast } = useUIStore()
  const [users, setUsers] = React.useState<User[]>([])
  const [loading, setLoading] = React.useState(true)
  const [search, setSearch] = React.useState('')
  const [page, setPage] = React.useState(1)
  const [totalPages, setTotalPages] = React.useState(1)
  const [total, setTotal] = React.useState(0)
  const [actionLoading, setActionLoading] = React.useState<string | null>(null)
  const [expandedId, setExpandedId] = React.useState<string | null>(null)
  const [roleOpen, setRoleOpen] = React.useState<string | null>(null)

  const fetchUsers = React.useCallback(async () => {
    setLoading(true)
    try {
      setUsers([])
      setTotal(0)
      setTotalPages(1)
    } catch {
      addToast({ title: 'Failed to load users', variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [addToast])

  React.useEffect(() => {
    fetchUsers()
  }, [fetchUsers, page, search])

  const handleAction = async (userId: string, action: 'suspend' | 'activate' | 'promote' | 'demote') => {
    setActionLoading(userId)
    try {
      await adminApi.manageUser(userId, action)
      addToast({ title: `User ${action}d successfully`, variant: 'success' })
      fetchUsers()
    } catch {
      addToast({ title: 'Action failed', variant: 'destructive' })
    } finally {
      setActionLoading(null)
    }
  }

  const getRoleBadge = (role: string) => {
    switch (role) {
      case 'admin': return <Badge variant="critical" className="text-[10px]">Admin</Badge>
      case 'moderator': return <Badge variant="warning" className="text-[10px]">Mod</Badge>
      default: return <Badge variant="secondary" className="text-[10px]">User</Badge>
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-4 md:p-6 pb-20 lg:pb-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">User Management</h1>
          <p className="text-sm text-muted-foreground">{total} registered users</p>
        </div>
      </div>

      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by name or email..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1) }}
            className="pl-9"
          />
        </div>
      </div>

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/50">
                <th className="text-left px-3 py-2.5 text-xs font-medium text-muted-foreground">Name</th>
                <th className="text-left px-3 py-2.5 text-xs font-medium text-muted-foreground hidden sm:table-cell">Email</th>
                <th className="text-left px-3 py-2.5 text-xs font-medium text-muted-foreground">Role</th>
                <th className="text-left px-3 py-2.5 text-xs font-medium text-muted-foreground hidden md:table-cell">Status</th>
                <th className="text-left px-3 py-2.5 text-xs font-medium text-muted-foreground hidden lg:table-cell">Joined</th>
                <th className="text-right px-3 py-2.5 text-xs font-medium text-muted-foreground">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i}>
                    <td colSpan={6} className="px-3 py-2"><Skeleton className="h-6 w-full" /></td>
                  </tr>
                ))
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-3 py-8 text-center text-sm text-muted-foreground">
                    {search ? 'No users matching search' : 'No users found'}
                  </td>
                </tr>
              ) : (
                users.map((u) => (
                  <React.Fragment key={u.id}>
                    <tr
                      className="border-b border-border hover:bg-accent/30 transition-colors cursor-pointer"
                      onClick={() => setExpandedId(expandedId === u.id ? null : u.id)}
                    >
                      <td className="px-3 py-2.5">
                        <div className="flex items-center gap-2">
                          <div className="h-7 w-7 rounded-full bg-muted flex items-center justify-center text-xs font-medium">
                            {u.name?.split(' ').map((n) => n[0]).join('').toUpperCase() || 'U'}
                          </div>
                          <span className="font-medium">{u.name}</span>
                        </div>
                      </td>
                      <td className="px-3 py-2.5 text-xs text-muted-foreground hidden sm:table-cell">{u.email}</td>
                      <td className="px-3 py-2.5">{getRoleBadge(u.role)}</td>
                      <td className="px-3 py-2.5 hidden md:table-cell">
                        <Badge variant={u.isVerified ? 'success' : 'secondary'} className="text-[10px]">
                          {u.isVerified ? 'Verified' : 'Unverified'}
                        </Badge>
                      </td>
                      <td className="px-3 py-2.5 text-xs text-muted-foreground hidden lg:table-cell">
                        {formatDate(u.createdAt, 'PP')}
                      </td>
                      <td className="px-3 py-2.5 text-right" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-end gap-1">
                          <div className="relative">
                            <button
                              onClick={() => setRoleOpen(roleOpen === u.id ? null : u.id)}
                              className="flex items-center gap-1 rounded-md border border-input px-2 py-1 text-xs"
                            >
                              <Shield className="h-3 w-3" />
                              Role
                              <ChevronDown className="h-3 w-3" />
                            </button>
                            {roleOpen === u.id && (
                              <div className="absolute right-0 top-full mt-1 w-28 rounded-md border border-border bg-popover p-1 shadow-lg z-10">
                                {(['user', 'moderator', 'admin'] as const).map((role) => (
                                  <button
                                    key={role}
                                    onClick={() => {
                                      handleAction(u.id, u.role === 'user' && role === 'moderator' ? 'promote' : 'demote')
                                      setRoleOpen(null)
                                    }}
                                    className="w-full rounded-sm px-2 py-1.5 text-xs text-left capitalize hover:bg-accent"
                                    disabled={u.role === role}
                                  >
                                    {role}
                                  </button>
                                ))}
                              </div>
                            )}
                          </div>
                          <Button
                            size="icon" variant="ghost" className="h-7 w-7"
                            onClick={() => handleAction(u.id, u.isVerified ? 'suspend' : 'activate')}
                            disabled={actionLoading === u.id}
                            title={u.isVerified ? 'Suspend' : 'Activate'}
                          >
                            {actionLoading === u.id ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : u.isVerified ? (
                              <UserX className="h-3 w-3 text-danger-500" />
                            ) : (
                              <UserCheck className="h-3 w-3 text-safety-500" />
                            )}
                          </Button>
                        </div>
                      </td>
                    </tr>
                    {expandedId === u.id && (
                      <tr className="bg-muted/20">
                        <td colSpan={6} className="px-6 py-3">
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                            <div>
                              <p className="text-xs text-muted-foreground">Phone</p>
                              <p>{u.phone || 'N/A'}</p>
                            </div>
                            <div>
                              <p className="text-xs text-muted-foreground">Emergency Contacts</p>
                              <p>{u.emergencyContacts?.length || 0}</p>
                            </div>
                            <div>
                              <p className="text-xs text-muted-foreground">Joined</p>
                              <p>{formatDate(u.createdAt, 'PPp')}</p>
                            </div>
                            <div>
                              <p className="text-xs text-muted-foreground">Last Updated</p>
                              <p>{formatDate(u.updatedAt, 'PPp')}</p>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))
              )}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-border px-4 py-3">
            <span className="text-xs text-muted-foreground">Page {page} of {totalPages}</span>
            <div className="flex gap-1">
              <Button size="icon" variant="outline" className="h-8 w-8" disabled={page <= 1}
                onClick={() => setPage(page - 1)}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button size="icon" variant="outline" className="h-8 w-8" disabled={page >= totalPages}
                onClick={() => setPage(page + 1)}>
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}

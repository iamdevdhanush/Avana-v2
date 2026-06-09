import * as React from 'react'
import {
  Search, ChevronDown, Check, X, Copy, Flag,
  Loader2, Download, ChevronLeft, ChevronRight,
} from 'lucide-react'
import { useIncidentStore } from '@/store/incidentStore'
import { adminApi } from '@/services/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { useUIStore } from '@/store/uiStore'
import { formatDate, formatRelativeTime, getSeverityColor, cn } from '@/lib/utils'
import type { Incident } from '@/types'

export function AdminIncidents() {
  const {
    incidents, filters, setFilters, resetFilters,
    pagination, setPage, fetchIncidents, isLoading, error,
  } = useIncidentStore()
  const { addToast } = useUIStore()
  const [searchInput, setSearchInput] = React.useState(filters.search)
  const [selectedIds, setSelectedIds] = React.useState<Set<string>>(new Set())
  const [expandedId, setExpandedId] = React.useState<string | null>(null)
  const [actionLoading, setActionLoading] = React.useState<string | null>(null)
  const [filterOpen, setFilterOpen] = React.useState<'type' | 'severity' | 'status' | null>(null)

  React.useEffect(() => {
    fetchIncidents()
  }, [fetchIncidents])

  const handleSearch = () => {
    setFilters({ search: searchInput })
    fetchIncidents(1)
  }

  const handleModerate = async (incidentId: string, action: 'verify' | 'dismiss' | 'resolve') => {
    setActionLoading(incidentId)
    try {
      await adminApi.moderateIncident(incidentId, action)
      addToast({ title: `Incident ${action}d successfully`, variant: 'success' })
      fetchIncidents(pagination.page)
    } catch {
      addToast({ title: 'Failed to moderate incident', variant: 'destructive' })
    } finally {
      setActionLoading(null)
    }
  }

  const handleBulkModerate = async (action: 'verify' | 'dismiss' | 'resolve') => {
    setActionLoading('bulk')
    try {
      await Promise.all(
        Array.from(selectedIds).map((id) => adminApi.moderateIncident(id, action))
      )
      addToast({ title: `${selectedIds.size} incidents updated`, variant: 'success' })
      setSelectedIds(new Set())
      fetchIncidents(pagination.page)
    } catch {
      addToast({ title: 'Bulk action failed', variant: 'destructive' })
    } finally {
      setActionLoading(null)
    }
  }

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (selectedIds.size === incidents.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(incidents.map((i) => i.id)))
    }
  }

  const exportCSV = () => {
    const headers = ['ID', 'Type', 'Severity', 'Status', 'Source', 'District', 'Time', 'Description']
    const rows = incidents.map((i) => [
      i.id, i.type, i.severity, i.status, i.source,
      i.location.address || '', i.reportedAt, i.description,
    ])
    const csv = [headers, ...rows].map((r) => r.map((c) => `"${c}"`).join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `incidents-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
    addToast({ title: 'Exported to CSV', variant: 'success' })
  }

  const filterOptions = {
    type: ['all', 'theft', 'assault', 'harassment', 'robbery', 'vandalism', 'suspicious', 'traffic', 'medical', 'fire', 'other'],
    severity: ['all', 'low', 'medium', 'high', 'critical'],
    status: ['all', 'reported', 'verified', 'investigating', 'resolved', 'dismissed'],
  }

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-4 md:p-6 pb-20 lg:pb-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Incident Moderation</h1>
          <p className="text-sm text-muted-foreground">{pagination.total} incidents found</p>
        </div>
        <Button variant="outline" size="sm" onClick={exportCSV}>
          <Download className="h-4 w-4 mr-2" /> Export CSV
        </Button>
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search incidents..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="pl-9"
          />
        </div>

        {(['type', 'severity', 'status'] as const).map((key) => (
          <div key={key} className="relative">
            <button
              onClick={() => setFilterOpen(filterOpen === key ? null : key)}
              className={cn(
                'flex items-center gap-2 rounded-md border border-input px-3 py-1.5 text-xs',
                filters[key] !== 'all' && 'border-primary text-primary'
              )}
            >
              <span className="capitalize">{key}: {filters[key]}</span>
              <ChevronDown className="h-3 w-3" />
            </button>
            {filterOpen === key && (
              <div className="absolute top-full mt-1 w-36 rounded-md border border-border bg-popover p-1 shadow-lg z-10">
                {filterOptions[key].map((opt) => (
                  <button
                    key={opt}
                    onClick={() => {
                      setFilters({ [key]: opt } as Partial<typeof filters>)
                      setFilterOpen(null)
                    }}
                    className={cn(
                      'w-full rounded-sm px-2 py-1.5 text-xs text-left capitalize hover:bg-accent',
                      filters[key] === opt && 'text-primary'
                    )}
                  >
                    {opt.replace(/_/g, ' ')}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}

        <Button variant="ghost" size="sm" onClick={resetFilters}>Reset</Button>
      </div>

      {selectedIds.size > 0 && (
        <div className="flex items-center gap-2 rounded-lg bg-primary/5 border border-primary/10 p-2">
          <span className="text-sm text-muted-foreground">{selectedIds.size} selected</span>
          <Separator orientation="vertical" className="h-4" />
          <Button size="sm" variant="outline" onClick={() => handleBulkModerate('verify')}
            disabled={actionLoading === 'bulk'}>
            <Check className="h-3 w-3 mr-1" /> Verify All
          </Button>
          <Button size="sm" variant="outline" onClick={() => handleBulkModerate('resolve')}
            disabled={actionLoading === 'bulk'}>
            <Flag className="h-3 w-3 mr-1" /> Resolve All
          </Button>
          <Button size="sm" variant="outline" onClick={() => handleBulkModerate('dismiss')}
            disabled={actionLoading === 'bulk'}>
            <X className="h-3 w-3 mr-1" /> Dismiss All
          </Button>
        </div>
      )}

      {error && (
        <div className="rounded-md bg-danger-500/10 border border-danger-500/20 p-3 text-sm text-danger-500">
          {error}
        </div>
      )}

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/50">
                <th className="w-8 px-3 py-2.5">
                  <input
                    type="checkbox"
                    checked={incidents.length > 0 && selectedIds.size === incidents.length}
                    onChange={toggleSelectAll}
                    className="rounded border-border"
                  />
                </th>
                <th className="text-left px-3 py-2.5 text-xs font-medium text-muted-foreground">Type</th>
                <th className="text-left px-3 py-2.5 text-xs font-medium text-muted-foreground">Severity</th>
                <th className="text-left px-3 py-2.5 text-xs font-medium text-muted-foreground hidden md:table-cell">District</th>
                <th className="text-left px-3 py-2.5 text-xs font-medium text-muted-foreground">Source</th>
                <th className="text-left px-3 py-2.5 text-xs font-medium text-muted-foreground">Status</th>
                <th className="text-left px-3 py-2.5 text-xs font-medium text-muted-foreground hidden lg:table-cell">Time</th>
                <th className="text-right px-3 py-2.5 text-xs font-medium text-muted-foreground">Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i}>
                    <td colSpan={8} className="px-3 py-2"><Skeleton className="h-6 w-full" /></td>
                  </tr>
                ))
              ) : incidents.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-3 py-8 text-center text-sm text-muted-foreground">
                    No incidents found
                  </td>
                </tr>
              ) : (
                incidents.map((incident) => (
                  <React.Fragment key={incident.id}>
                    <tr
                      className="border-b border-border hover:bg-accent/30 transition-colors cursor-pointer"
                      onClick={() => setExpandedId(expandedId === incident.id ? null : incident.id)}
                    >
                      <td className="px-3 py-2.5" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={selectedIds.has(incident.id)}
                          onChange={() => toggleSelect(incident.id)}
                          className="rounded border-border"
                        />
                      </td>
                      <td className="px-3 py-2.5 capitalize">{incident.type.replace(/_/g, ' ')}</td>
                      <td className="px-3 py-2.5">
                        <Badge variant={
                          incident.severity === 'critical' ? 'critical' :
                          incident.severity === 'high' ? 'danger' :
                          incident.severity === 'medium' ? 'warning' : 'success'
                        } className="text-[10px] capitalize">{incident.severity}</Badge>
                      </td>
                      <td className="px-3 py-2.5 text-xs text-muted-foreground hidden md:table-cell">
                        {incident.location.address || 'Unknown'}
                      </td>
                      <td className="px-3 py-2.5">
                        <Badge variant="secondary" className="text-[10px] capitalize">
                          {incident.source.replace(/_/g, ' ')}
                        </Badge>
                      </td>
                      <td className="px-3 py-2.5 capitalize">{incident.status.replace(/_/g, ' ')}</td>
                      <td className="px-3 py-2.5 text-xs text-muted-foreground hidden lg:table-cell">
                        {formatRelativeTime(incident.reportedAt)}
                      </td>
                      <td className="px-3 py-2.5 text-right" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            size="icon" variant="ghost" className="h-7 w-7"
                            onClick={() => handleModerate(incident.id, 'verify')}
                            disabled={actionLoading === incident.id}
                            title="Verify"
                          >
                            {actionLoading === incident.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3 text-safety-500" />}
                          </Button>
                          <Button
                            size="icon" variant="ghost" className="h-7 w-7"
                            onClick={() => handleModerate(incident.id, 'resolve')}
                            disabled={actionLoading === incident.id}
                            title="Resolve"
                          >
                            <Flag className="h-3 w-3 text-primary" />
                          </Button>
                          <Button
                            size="icon" variant="ghost" className="h-7 w-7"
                            onClick={() => handleModerate(incident.id, 'dismiss')}
                            disabled={actionLoading === incident.id}
                            title="Dismiss"
                          >
                            <X className="h-3 w-3 text-muted-foreground" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                    {expandedId === incident.id && (
                      <tr className="bg-muted/20">
                        <td colSpan={8} className="px-6 py-3">
                          <div className="space-y-2 text-sm">
                            <p className="font-medium">{incident.title}</p>
                            <p className="text-muted-foreground">{incident.description}</p>
                            <div className="flex gap-4 text-xs text-muted-foreground">
                              <span>Reported: {formatDate(incident.reportedAt)}</span>
                              <span>Location: {incident.location.lat?.toFixed(4)}, {incident.location.lng?.toFixed(4)}</span>
                              {incident.resolvedAt && <span>Resolved: {formatDate(incident.resolvedAt)}</span>}
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

        {pagination.totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-border px-4 py-3">
            <span className="text-xs text-muted-foreground">
              Page {pagination.page} of {pagination.totalPages}
            </span>
            <div className="flex gap-1">
              <Button
                size="icon" variant="outline" className="h-8 w-8"
                disabled={pagination.page <= 1}
                onClick={() => { setPage(pagination.page - 1); fetchIncidents(pagination.page - 1) }}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                size="icon" variant="outline" className="h-8 w-8"
                disabled={pagination.page >= pagination.totalPages}
                onClick={() => { setPage(pagination.page + 1); fetchIncidents(pagination.page + 1) }}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}

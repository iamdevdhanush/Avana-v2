import * as React from 'react'
import {
  BarChart3, PieChart, TrendingUp, AlertTriangle, Users,
  Shield, Activity, ChevronRight, Loader2,
} from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart as RePieChart, Pie, Cell,
  LineChart, Line, Area, AreaChart,
} from 'recharts'
import { useNavigate } from 'react-router-dom'
import { adminApi, analyticsApi } from '@/services/api'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Separator } from '@/components/ui/separator'
import { formatRelativeTime, getSeverityColor } from '@/lib/utils'
import type { DashboardStats, DistrictAnalytics, CrimeTrend } from '@/types'

const COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#7c3aed', '#ec4899']

export function AdminDashboard() {
  const navigate = useNavigate()
  const [stats, setStats] = React.useState<DashboardStats | null>(null)
  const [districtData, setDistrictData] = React.useState<DistrictAnalytics[]>([])
  const [trends, setTrends] = React.useState<CrimeTrend[]>([])
  const [isLoading, setIsLoading] = React.useState(true)

  React.useEffect(() => {
    Promise.all([
      adminApi.getDashboardStats(),
      analyticsApi.getDistrictAnalytics(),
      analyticsApi.getCrimeTrends({ days: 30 }),
    ]).then(([s, d, t]) => {
      setStats(s)
      setDistrictData(d)
      setTrends(t)
    }).catch(() => {}).finally(() => setIsLoading(false))
  }, [])

  const statCards = [
    { label: 'Total Incidents', value: stats?.totalIncidents ?? 0, icon: AlertTriangle, color: 'text-danger-500', bg: 'bg-danger-500/10' },
    { label: 'Active Users', value: stats?.activeUsers ?? 0, icon: Users, color: 'text-primary', bg: 'bg-primary/10' },
    { label: 'SOS Triggers', value: stats?.sosTriggers ?? 0, icon: Activity, color: 'text-warning-500', bg: 'bg-warning-500/10' },
    { label: 'Pending Reports', value: stats?.activeIncidents ?? 0, icon: Shield, color: 'text-critical', bg: 'bg-critical/10' },
  ]

  const incidentsByType = stats?.incidentsByType
    ? Object.entries(stats.incidentsByType).map(([name, value]) => ({ name, value }))
    : []

  const barData = districtData.map((d) => ({
    name: d.district,
    High: d.highRisk + d.critical,
    Medium: d.mediumRisk,
    Low: d.lowRisk,
  }))

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6 pb-20 lg:pb-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Admin Dashboard</h1>
          <p className="text-sm text-muted-foreground">Overview of platform safety metrics</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => navigate('/admin/incidents')}>
            Moderate
          </Button>
          <Button variant="outline" size="sm" onClick={() => navigate('/admin/agents')}>
            Run Agents
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <Skeleton className="h-4 w-20 mb-2" />
                <Skeleton className="h-8 w-16" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-4">
          {statCards.map((stat) => (
            <Card key={stat.label}>
              <CardContent className="p-6">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-muted-foreground">{stat.label}</span>
                  <div className={`rounded-lg p-2 ${stat.bg}`}>
                    <stat.icon className={`h-4 w-4 ${stat.color}`} />
                  </div>
                </div>
                <p className="text-2xl font-bold">{stat.value.toLocaleString()}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-primary" />
              Incidents by District
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              {barData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={barData} barGap={2}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                    <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} />
                    <Tooltip
                      contentStyle={{
                        background: '#1e293b',
                        border: '1px solid #334155',
                        borderRadius: '8px',
                        fontSize: '12px',
                      }}
                    />
                    <Bar dataKey="High" fill="#ef4444" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="Medium" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="Low" fill="#22c55e" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                  No district data available
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <PieChart className="h-4 w-4 text-primary" />
              By Type
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              {incidentsByType.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <RePieChart>
                    <Pie
                      data={incidentsByType}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={90}
                      paddingAngle={2}
                      dataKey="value"
                    >
                      {incidentsByType.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        background: '#1e293b',
                        border: '1px solid #334155',
                        borderRadius: '8px',
                        fontSize: '12px',
                      }}
                    />
                  </RePieChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                  No data
                </div>
              )}
              <div className="flex flex-wrap justify-center gap-2 mt-2">
                {incidentsByType.slice(0, 6).map((entry, index) => (
                  <div key={entry.name} className="flex items-center gap-1 text-xs">
                    <div className="h-2 w-2 rounded-full" style={{ background: COLORS[index % COLORS.length] }} />
                    <span className="capitalize">{entry.name.replace(/_/g, ' ')}</span>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-primary" />
            30-Day Crime Trend
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[250px]">
            {trends.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trends}>
                  <defs>
                    <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: '#94a3b8', fontSize: 11 }}
                    tickFormatter={(val) => {
                      const d = new Date(val)
                      return `${d.getDate()}/${d.getMonth() + 1}`
                    }}
                  />
                  <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{
                      background: '#1e293b',
                      border: '1px solid #334155',
                      borderRadius: '8px',
                      fontSize: '12px',
                    }}
                  />
                  <Area type="monotone" dataKey="count" stroke="#3b82f6" fill="url(#colorCount)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                No trend data available
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center justify-between">
            <span className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-danger-500" />
              Recent Alerts
            </span>
            <Button variant="ghost" size="sm" className="text-xs" onClick={() => navigate('/admin/incidents')}>
              View All <ChevronRight className="h-3 w-3 ml-1" />
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 px-3 text-xs font-medium text-muted-foreground">Type</th>
                  <th className="text-left py-2 px-3 text-xs font-medium text-muted-foreground">Severity</th>
                  <th className="text-left py-2 px-3 text-xs font-medium text-muted-foreground">Status</th>
                  <th className="text-left py-2 px-3 text-xs font-medium text-muted-foreground">Time</th>
                </tr>
              </thead>
              <tbody>
                {stats?.recentIncidents?.slice(0, 10).map((inc) => (
                  <tr key={inc.id} className="border-b border-border hover:bg-accent/50 transition-colors">
                    <td className="py-2 px-3 capitalize">{inc.type.replace(/_/g, ' ')}</td>
                    <td className="py-2 px-3">
                      <Badge variant={
                        inc.severity === 'critical' ? 'critical' :
                        inc.severity === 'high' ? 'danger' :
                        inc.severity === 'medium' ? 'warning' : 'success'
                      } className="text-[10px] capitalize">{inc.severity}</Badge>
                    </td>
                    <td className="py-2 px-3 capitalize">{inc.status.replace(/_/g, ' ')}</td>
                    <td className="py-2 px-3 text-xs text-muted-foreground">{formatRelativeTime(inc.reportedAt)}</td>
                  </tr>
                ))}
                {(!stats?.recentIncidents || stats.recentIncidents.length === 0) && (
                  <tr>
                    <td colSpan={4} className="py-4 text-center text-sm text-muted-foreground">No recent alerts</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

import * as React from 'react'
import {
  Activity, Play, StopCircle, RefreshCw, Loader2,
  CheckCircle, XCircle, Clock, BarChart3,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

interface Agent {
  id: string
  name: string
  description: string
  status: 'running' | 'idle' | 'failed'
  lastRun: string | null
  nextRun: string | null
  avgRuntime: number
  successRate: number
  logs: { time: string; message: string; level: 'info' | 'error' | 'warn' }[]
}

const mockAgents: Agent[] = [
  {
    id: '1', name: 'Incident Detector',
    description: 'Scans social media and news for new incidents',
    status: 'running', lastRun: new Date(Date.now() - 300000).toISOString(),
    nextRun: new Date(Date.now() + 900000).toISOString(),
    avgRuntime: 45, successRate: 96,
    logs: [
      { time: new Date(Date.now() - 300000).toISOString(), message: 'Scanned 245 sources', level: 'info' },
      { time: new Date(Date.now() - 310000).toISOString(), message: 'Found 3 new incident candidates', level: 'info' },
      { time: new Date(Date.now() - 320000).toISOString(), message: 'Processing complete', level: 'info' },
    ],
  },
  {
    id: '2', name: 'Risk Analyzer',
    description: 'Calculates risk scores for all map regions',
    status: 'idle', lastRun: new Date(Date.now() - 3600000).toISOString(),
    nextRun: new Date(Date.now() + 5400000).toISOString(),
    avgRuntime: 120, successRate: 99,
    logs: [
      { time: new Date(Date.now() - 3600000).toISOString(), message: 'Updated risk scores for 48 districts', level: 'info' },
    ],
  },
  {
    id: '3', name: 'Safety Recommender',
    description: 'Generates AI safety tips based on current conditions',
    status: 'failed', lastRun: new Date(Date.now() - 7200000).toISOString(),
    nextRun: new Date(Date.now() + 3600000).toISOString(),
    avgRuntime: 30, successRate: 88,
    logs: [
      { time: new Date(Date.now() - 7200000).toISOString(), message: 'API timeout exceeded', level: 'error' },
      { time: new Date(Date.now() - 7210000).toISOString(), message: 'Retry attempt 1 failed', level: 'warn' },
    ],
  },
  {
    id: '4', name: 'Data Cleanup Agent',
    description: 'Archives old incidents and optimizes database',
    status: 'idle', lastRun: new Date(Date.now() - 86400000).toISOString(),
    nextRun: new Date(Date.now() + 43200000).toISOString(),
    avgRuntime: 90, successRate: 100,
    logs: [
      { time: new Date(Date.now() - 86400000).toISOString(), message: 'Archived 156 resolved incidents', level: 'info' },
    ],
  },
]

export function AdminAgents() {
  const [agents, setAgents] = React.useState<Agent[]>(mockAgents)
  const [loading, setLoading] = React.useState(false)
  const [selectedAgent, setSelectedAgent] = React.useState<Agent | null>(null)
  const [runningAll, setRunningAll] = React.useState(false)
  const [actionLoading, setActionLoading] = React.useState<string | null>(null)

  const handleTrigger = (agentId: string) => {
    setActionLoading(agentId)
    setAgents((prev) =>
      prev.map((a) => a.id === agentId ? { ...a, status: 'running' as const } : a)
    )
    setTimeout(() => {
      setAgents((prev) =>
        prev.map((a) => a.id === agentId
          ? { ...a, status: 'idle', lastRun: new Date().toISOString(), logs: [{ time: new Date().toISOString(), message: 'Manual run completed', level: 'info' }, ...a.logs] }
          : a
        )
      )
      setActionLoading(null)
    }, 3000)
  }

  const handleRunAll = () => {
    setRunningAll(true)
    setAgents((prev) => prev.map((a) => ({ ...a, status: 'running' as const })))
    setTimeout(() => {
      setAgents((prev) =>
        prev.map((a) => ({
          ...a,
          status: 'idle',
          lastRun: new Date().toISOString(),
          logs: [{ time: new Date().toISOString(), message: 'Run all completed', level: 'info' }, ...a.logs],
        }))
      )
      setRunningAll(false)
    }, 5000)
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'running':
        return <Badge variant="warning" className="text-[10px] animate-pulse"><Activity className="h-3 w-3 mr-1" /> Running</Badge>
      case 'failed':
        return <Badge variant="destructive" className="text-[10px]"><XCircle className="h-3 w-3 mr-1" /> Failed</Badge>
      default:
        return <Badge variant="secondary" className="text-[10px]"><CheckCircle className="h-3 w-3 mr-1" /> Idle</Badge>
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6 pb-20 lg:pb-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Agent Pipeline</h1>
          <p className="text-sm text-muted-foreground">Monitor and manage background AI agents</p>
        </div>
        <Button onClick={handleRunAll} disabled={runningAll}>
          {runningAll ? (
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
          ) : (
            <RefreshCw className="h-4 w-4 mr-2" />
          )}
          {runningAll ? 'Running All...' : 'Run All'}
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {agents.map((agent) => (
          <Card
            key={agent.id}
            className={cn(
              'cursor-pointer transition-all hover:border-primary/50',
              selectedAgent?.id === agent.id && 'border-primary'
            )}
            onClick={() => setSelectedAgent(agent)}
          >
            <CardContent className="p-5 space-y-3">
              <div className="flex items-start justify-between">
                <div className="space-y-1">
                  <h3 className="font-semibold">{agent.name}</h3>
                  <p className="text-xs text-muted-foreground">{agent.description}</p>
                </div>
                {getStatusBadge(agent.status)}
              </div>

              <Separator />

              <div className="grid grid-cols-3 gap-2">
                <div>
                  <p className="text-xs text-muted-foreground">Avg Runtime</p>
                  <p className="text-sm font-medium">{agent.avgRuntime}s</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Success Rate</p>
                  <p className="text-sm font-medium">{agent.successRate}%</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Next Run</p>
                  <p className="text-sm font-medium">
                    {agent.nextRun
                      ? new Date(agent.nextRun).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                      : '--'}
                  </p>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <div className="text-xs text-muted-foreground">
                  Last: {agent.lastRun
                    ? new Date(agent.lastRun).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                    : 'Never'}
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8"
                  onClick={(e) => { e.stopPropagation(); handleTrigger(agent.id) }}
                  disabled={actionLoading === agent.id || agent.status === 'running'}
                >
                  {actionLoading === agent.id ? (
                    <Loader2 className="h-3 w-3 animate-spin mr-1" />
                  ) : (
                    <Play className="h-3 w-3 mr-1" />
                  )}
                  Run
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {selectedAgent && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-primary" />
                {selectedAgent.name} - Logs
              </CardTitle>
              <Button variant="ghost" size="sm" onClick={() => setSelectedAgent(null)}>
                Close
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[200px]">
              <div className="space-y-1">
                {selectedAgent.logs.map((log, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs py-1 border-b border-border last:border-0">
                    <span className="text-muted-foreground shrink-0 w-16">
                      {new Date(log.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                    <span className={cn(
                      'shrink-0 font-medium w-10',
                      log.level === 'error' ? 'text-danger-500' :
                      log.level === 'warn' ? 'text-warning-500' : 'text-safety-500'
                    )}>
                      [{log.level}]
                    </span>
                    <span className="text-muted-foreground">{log.message}</span>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

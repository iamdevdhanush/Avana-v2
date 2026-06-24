import * as React from 'react'
import {
  Brain, Plus, Loader2, Check, X, RefreshCw,
  Zap, ShieldAlert, ExternalLink, Eye, EyeOff,
} from 'lucide-react'
import { adminApi } from '@/services/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { useUIStore } from '@/store/uiStore'
import { cn } from '@/lib/utils'
import type { AIConfigResponse, AIConfigStatus } from '@/types'

const PROVIDER_OPTIONS = [
  { value: 'mock', label: 'Mock' },
  { value: 'openrouter', label: 'OpenRouter' },
  { value: 'auto', label: 'Auto (Fallback)' },
]

export function AdminAIConfig() {
  const { addToast } = useUIStore()
  const [configs, setConfigs] = React.useState<AIConfigResponse[]>([])
  const [status, setStatus] = React.useState<AIConfigStatus | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [showForm, setShowForm] = React.useState(false)
  const [provider, setProvider] = React.useState('openrouter')
  const [model, setModel] = React.useState('')
  const [apiKey, setApiKey] = React.useState('')
  const [showKey, setShowKey] = React.useState(false)
  const [saving, setSaving] = React.useState(false)
  const [testing, setTesting] = React.useState(false)
  const [testResult, setTestResult] = React.useState<{ success: boolean; latency?: number | null; error?: string | null } | null>(null)
  const [activatingId, setActivatingId] = React.useState<string | null>(null)

  const fetchData = React.useCallback(async () => {
    setLoading(true)
    try {
      const [configsData, statusData] = await Promise.all([
        adminApi.listAIConfigs(),
        adminApi.getAIConfigStatus(),
      ])
      setConfigs(configsData)
      setStatus(statusData)
    } catch {
      addToast({ title: 'Failed to load AI configurations', variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [addToast])

  React.useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleTest = async () => {
    if (!apiKey.trim() || !model.trim()) {
      addToast({ title: 'API key and model are required for testing', variant: 'destructive' })
      return
    }
    setTesting(true)
    setTestResult(null)
    try {
      const result = await adminApi.testAIConfig({ provider, model, api_key: apiKey })
      setTestResult(result)
      addToast({
        title: result.success ? 'Connection successful' : 'Connection failed',
        variant: result.success ? 'success' : 'destructive',
      })
    } catch {
      setTestResult({ success: false, latency: null, error: 'Test request failed' })
      addToast({ title: 'Test request failed', variant: 'destructive' })
    } finally {
      setTesting(false)
    }
  }

  const handleSave = async () => {
    if (!apiKey.trim() || !model.trim()) {
      addToast({ title: 'API key and model are required', variant: 'destructive' })
      return
    }
    setSaving(true)
    try {
      await adminApi.createAIConfig({ provider, model, api_key: apiKey })
      addToast({ title: 'Configuration saved', variant: 'success' })
      setShowForm(false)
      setProvider('openrouter')
      setModel('')
      setApiKey('')
      setTestResult(null)
      fetchData()
    } catch {
      addToast({ title: 'Failed to save configuration', variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }

  const handleActivate = async (configId: string) => {
    setActivatingId(configId)
    try {
      await adminApi.activateAIConfig(configId)
      addToast({ title: 'Configuration activated', variant: 'success' })
      fetchData()
    } catch {
      addToast({ title: 'Failed to activate configuration', variant: 'destructive' })
    } finally {
      setActivatingId(null)
    }
  }

  const getProviderBadge = (p: string) => {
    switch (p) {
      case 'mock': return <Badge variant="secondary" className="text-[10px]">Mock</Badge>
      case 'openrouter': return <Badge variant="secondary" className="text-[10px]">OpenRouter</Badge>
      case 'auto': return <Badge variant="secondary" className="text-[10px]">Auto</Badge>
      default: return <Badge variant="secondary" className="text-[10px]">{p}</Badge>
    }
  }

  const getTestStatusBadge = (s: string | null) => {
    if (!s) return <span className="text-xs text-muted-foreground">Never tested</span>
    if (s === 'success') return <Badge variant="success" className="text-[10px]">Pass</Badge>
    return <Badge variant="destructive" className="text-[10px]">Fail</Badge>
  }

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-4 md:p-6 pb-20 lg:pb-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">AI Configuration</h1>
          <p className="text-sm text-muted-foreground">Manage AI provider settings</p>
        </div>
        <Button onClick={() => setShowForm(!showForm)} className="gap-2">
          {showForm ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
          {showForm ? 'Cancel' : 'New Config'}
        </Button>
      </div>

      {/* Status Card */}
      {status && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Brain className="h-4 w-4 text-purple-500" />
              Active Provider Status
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <p className="text-xs text-muted-foreground">Active DB Config</p>
                <p className="font-medium">
                  {status.active_config
                    ? `${status.active_config.provider} / ${status.active_config.model}`
                    : 'None'}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Provider (Env)</p>
                <p className="font-medium">{status.env_provider || 'auto'}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Model (Env)</p>
                <p className="font-medium">{status.env_model || 'default'}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Env API Key</p>
                <p className="font-medium">
                  {status.env_has_key
                    ? <Badge variant="success" className="text-[10px]">Configured</Badge>
                    : <Badge variant="secondary" className="text-[10px]">Not Set</Badge>}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* New Config Form */}
      {showForm && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">New AI Provider Config</CardTitle>
            <CardDescription>API keys are encrypted before storage</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">Provider</label>
                <select
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                >
                  {PROVIDER_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">Model</label>
                <Input
                  placeholder='openai/gpt-4o-mini'
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">API Key</label>
                <div className="relative">
                  <Input
                    type={showKey ? 'text' : 'password'}
                    placeholder="Enter API key..."
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    className="pr-9"
                  />
                  <button
                    type="button"
                    onClick={() => setShowKey(!showKey)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>
            </div>

            {/* Test Result */}
            {testResult && (
              <div className={cn(
                'rounded-md border px-3 py-2 text-xs flex items-center gap-2',
                testResult.success ? 'border-green-500/30 bg-green-500/10 text-green-400' : 'border-red-500/30 bg-red-500/10 text-red-400',
              )}>
                {testResult.success ? (
                  <>
                    <Check className="h-3.5 w-3.5" />
                    Connected — {testResult.latency?.toFixed(0)}ms
                  </>
                ) : (
                  <>
                    <X className="h-3.5 w-3.5" />
                    {testResult.error || 'Connection failed'}
                  </>
                )}
              </div>
            )}

            <div className="flex gap-2">
              <Button variant="outline" onClick={handleTest} disabled={testing || !apiKey.trim() || !model.trim()} className="gap-2">
                {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
                {testing ? 'Testing...' : 'Test Connection'}
              </Button>
              <Button onClick={handleSave} disabled={saving || !apiKey.trim() || !model.trim()} className="gap-2">
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                {saving ? 'Saving...' : 'Save Config'}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Saved Configs List */}
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/50">
                <th className="text-left px-3 py-2.5 text-xs font-medium text-muted-foreground">Provider</th>
                <th className="text-left px-3 py-2.5 text-xs font-medium text-muted-foreground">Model</th>
                <th className="text-left px-3 py-2.5 text-xs font-medium text-muted-foreground hidden sm:table-cell">API Key</th>
                <th className="text-left px-3 py-2.5 text-xs font-medium text-muted-foreground">Status</th>
                <th className="text-left px-3 py-2.5 text-xs font-medium text-muted-foreground hidden md:table-cell">Last Test</th>
                <th className="text-right px-3 py-2.5 text-xs font-medium text-muted-foreground">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <tr key={i}>
                    <td colSpan={6} className="px-3 py-2"><Skeleton className="h-6 w-full" /></td>
                  </tr>
                ))
              ) : configs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-3 py-8 text-center text-sm text-muted-foreground">
                    No AI configurations saved yet
                  </td>
                </tr>
              ) : (
                configs.map((cfg) => (
                  <tr key={cfg.id} className={cn(
                    'border-b border-border hover:bg-accent/30 transition-colors',
                    cfg.is_active && 'bg-primary/5',
                  )}>
                    <td className="px-3 py-2.5">{getProviderBadge(cfg.provider)}</td>
                    <td className="px-3 py-2.5 font-medium">{cfg.model}</td>
                    <td className="px-3 py-2.5 text-xs text-muted-foreground hidden sm:table-cell font-mono">
                      {cfg.api_key_masked}
                    </td>
                    <td className="px-3 py-2.5">
                      {cfg.is_active
                        ? <Badge variant="success" className="text-[10px]">Active</Badge>
                        : <Badge variant="secondary" className="text-[10px]">Inactive</Badge>}
                    </td>
                    <td className="px-3 py-2.5 hidden md:table-cell">
                      {getTestStatusBadge(cfg.last_test_status)}
                      {cfg.last_error && (
                        <p className="text-[10px] text-muted-foreground mt-0.5 truncate max-w-[120px]" title={cfg.last_error}>
                          {cfg.last_error}
                        </p>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      {!cfg.is_active && (
                        <Button
                          size="sm" variant="ghost" className="gap-1.5 h-7 text-xs"
                          onClick={() => handleActivate(cfg.id)}
                          disabled={activatingId === cfg.id}
                        >
                          {activatingId === cfg.id
                            ? <Loader2 className="h-3 w-3 animate-spin" />
                            : <Check className="h-3 w-3" />}
                          Activate
                        </Button>
                      )}
                      {cfg.is_active && (
                        <Badge variant="success" className="text-[10px]">In Use</Badge>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

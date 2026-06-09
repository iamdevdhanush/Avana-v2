import * as React from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { Mail, Lock, User, Phone, Eye, EyeOff, Loader2, Shield } from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'

function PasswordStrength({ password }: { password: string }) {
  const strength = React.useMemo(() => {
    let score = 0
    if (password.length >= 8) score++
    if (password.length >= 12) score++
    if (/[A-Z]/.test(password)) score++
    if (/[a-z]/.test(password)) score++
    if (/[0-9]/.test(password)) score++
    if (/[^A-Za-z0-9]/.test(password)) score++
    return Math.min(score, 5)
  }, [password])

  const colors = ['', 'bg-danger-500', 'bg-danger-400', 'bg-warning-500', 'bg-warning-400', 'bg-safety-500']
  const labels = ['', 'Weak', 'Weak', 'Fair', 'Good', 'Strong']

  return (
    <div className="space-y-1">
      <div className="flex gap-1">
        {[1, 2, 3, 4, 5].map((i) => (
          <div
            key={i}
            className={`h-1 flex-1 rounded-full ${i <= strength ? colors[strength] : 'bg-muted'} transition-colors`}
          />
        ))}
      </div>
      {password.length > 0 && (
        <p className="text-xs text-muted-foreground">{labels[strength]}</p>
      )}
    </div>
  )
}

export function SignupScreen() {
  const navigate = useNavigate()
  const { signup, isAuthenticated, isLoading, error, clearError } = useAuthStore()
  const [name, setName] = React.useState('')
  const [email, setEmail] = React.useState('')
  const [phone, setPhone] = React.useState('')
  const [password, setPassword] = React.useState('')
  const [confirmPassword, setConfirmPassword] = React.useState('')
  const [showPassword, setShowPassword] = React.useState(false)
  const [formErrors, setFormErrors] = React.useState<Record<string, string>>({})

  React.useEffect(() => { clearError() }, [clearError])

  if (isAuthenticated) return <Navigate to="/" replace />

  const validate = () => {
    const errors: Record<string, string> = {}
    if (!name.trim()) errors.name = 'Name is required'
    if (!email) errors.email = 'Email is required'
    else if (!/\S+@\S+\.\S+/.test(email)) errors.email = 'Invalid email format'
    if (!password) errors.password = 'Password is required'
    else if (password.length < 6) errors.password = 'At least 6 characters'
    if (password !== confirmPassword) errors.confirmPassword = 'Passwords do not match'
    setFormErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!validate()) return
    try {
      await signup({ email, password, name, phone: phone || undefined })
      navigate('/')
    } catch { /* handled by store */ }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="flex flex-col items-center gap-2">
          <div className="flex items-center gap-2">
            <Shield className="h-8 w-8 text-primary" />
            <span className="text-2xl font-bold">Avana</span>
          </div>
          <p className="text-sm text-muted-foreground">Create your account to get started.</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <div className="relative">
              <User className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input placeholder="Full Name" value={name}
                onChange={(e) => { setName(e.target.value); setFormErrors((p) => ({ ...p, name: '' })) }} className="pl-9" />
            </div>
            {formErrors.name && <p className="text-xs text-danger-500">{formErrors.name}</p>}
          </div>

          <div className="space-y-2">
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input type="email" placeholder="Email" value={email}
                onChange={(e) => { setEmail(e.target.value); setFormErrors((p) => ({ ...p, email: '' })) }} className="pl-9" />
            </div>
            {formErrors.email && <p className="text-xs text-danger-500">{formErrors.email}</p>}
          </div>

          <div className="space-y-2">
            <div className="relative">
              <Phone className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input type="tel" placeholder="Phone (optional)" value={phone}
                onChange={(e) => setPhone(e.target.value)} className="pl-9" />
            </div>
          </div>

          <div className="space-y-2">
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input type={showPassword ? 'text' : 'password'} placeholder="Password" value={password}
                onChange={(e) => { setPassword(e.target.value); setFormErrors((p) => ({ ...p, password: '' })) }}
                className="pl-9 pr-9" />
              <button type="button" onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            <PasswordStrength password={password} />
            {formErrors.password && <p className="text-xs text-danger-500">{formErrors.password}</p>}
          </div>

          <div className="space-y-2">
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input type={showPassword ? 'text' : 'password'} placeholder="Confirm Password" value={confirmPassword}
                onChange={(e) => { setConfirmPassword(e.target.value); setFormErrors((p) => ({ ...p, confirmPassword: '' })) }} className="pl-9" />
            </div>
            {formErrors.confirmPassword && <p className="text-xs text-danger-500">{formErrors.confirmPassword}</p>}
          </div>

          {error && (
            <div className="rounded-md bg-danger-500/10 border border-danger-500/20 p-3 text-sm text-danger-500">{error}</div>
          )}

          <Button type="submit" className="w-full h-10" disabled={isLoading}>
            {isLoading && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
            {isLoading ? 'Creating account...' : 'Create Account'}
          </Button>
        </form>

        <div className="relative">
          <Separator />
          <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-background px-2 text-xs text-muted-foreground">OR</span>
        </div>

        <Button variant="outline" className="w-full h-10" onClick={() => window.location.href = '/api/auth/google'}>
          <svg className="h-4 w-4 mr-2" viewBox="0 0 24 24">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
          </svg>
          Continue with Google
        </Button>

        <p className="text-center text-sm text-muted-foreground">
          Already have an account?{' '}
          <Link to="/login" className="text-primary hover:underline font-medium">Sign In</Link>
        </p>
      </div>
    </div>
  )
}

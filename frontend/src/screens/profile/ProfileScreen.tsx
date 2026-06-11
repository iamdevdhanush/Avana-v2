import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  User, Phone, Shield, Bell, Lock, LogOut, ChevronRight,
  Mail, Users, Edit2, Check, X, Loader2, Plus, Trash2, Star,
} from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { authApi } from '@/services/api'
import { useUIStore } from '@/store/uiStore'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import type { EmergencyContact } from '@/types'

export function ProfileScreen() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user, logout, loadUser } = useAuthStore()
  const { addToast } = useUIStore()
  const [editingName, setEditingName] = React.useState(false)
  const [nameValue, setNameValue] = React.useState(user?.name || '')
  const [savingName, setSavingName] = React.useState(false)
  const [showAddContact, setShowAddContact] = React.useState(false)
  const [notificationsEnabled, setNotificationsEnabled] = React.useState(
    () => localStorage.getItem('avana_notifications') !== 'false'
  )
  const [locationSharing, setLocationSharing] = React.useState(
    () => localStorage.getItem('avana_location_sharing') !== 'false'
  )

  const initials = user?.name?.split(' ').map(n => n[0]).join('').toUpperCase() || 'U'

  // ── Emergency Contacts — real API ──────────────────────────────────────────
  const { data: contacts = [], isLoading: contactsLoading } = useQuery({
    queryKey: ['emergency-contacts'],
    queryFn: () => authApi.getEmergencyContacts(),
    staleTime: 5 * 60_000,
    retry: 1,
  })

  const addContactMutation = useMutation({
    mutationFn: (contact: { name: string; phone: string; relationship: string; is_primary: boolean }) =>
      authApi.addEmergencyContact(contact),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['emergency-contacts'] })
      addToast({ title: 'Contact added', variant: 'success' })
      setShowAddContact(false)
    },
    onError: (err: Error) => {
      addToast({ title: err.message || 'Failed to add contact', variant: 'destructive' })
    },
  })

  const deleteContactMutation = useMutation({
    mutationFn: (id: string) => authApi.deleteEmergencyContact(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['emergency-contacts'] })
      addToast({ title: 'Contact removed', variant: 'success' })
    },
    onError: (err: Error) => {
      addToast({ title: err.message || 'Failed to remove contact', variant: 'destructive' })
    },
  })

  // ── Name edit ──────────────────────────────────────────────────────────────
  const handleSaveName = async () => {
    if (!nameValue.trim() || nameValue === user?.name) {
      setEditingName(false)
      return
    }
    setSavingName(true)
    try {
      await authApi.updateProfile({ name: nameValue.trim() } as Parameters<typeof authApi.updateProfile>[0])
      await loadUser()
      addToast({ title: 'Name updated', variant: 'success' })
    } catch {
      addToast({ title: 'Failed to update name', variant: 'destructive' })
      setNameValue(user?.name || '')
    } finally {
      setSavingName(false)
      setEditingName(false)
    }
  }

  const handleLogout = async () => {
    try { await logout() } finally { navigate('/login') }
  }

  const toggleNotifications = (val: boolean) => {
    setNotificationsEnabled(val)
    localStorage.setItem('avana_notifications', val ? 'true' : 'false')
  }

  const toggleLocationSharing = (val: boolean) => {
    setLocationSharing(val)
    localStorage.setItem('avana_location_sharing', val ? 'true' : 'false')
  }

  return (
    <div className="min-h-full max-w-lg mx-auto px-4 py-6 space-y-5 animate-fade-in-up pb-safe">

      {/* User Info Card */}
      <div className="rounded-2xl p-6" style={{ background: '#1A1A24', border: '1px solid #1F2937' }}>
        <div className="flex items-center gap-4">
          <Avatar className="h-16 w-16">
            {user?.avatar ? (
              <img src={user.avatar} alt={user.name} className="object-cover" />
            ) : (
              <AvatarFallback
                className="text-xl font-bold"
                style={{ background: 'rgba(168,85,247,0.15)', color: '#A855F7' }}
              >
                {initials}
              </AvatarFallback>
            )}
          </Avatar>
          <div className="flex-1 min-w-0">
            {editingName ? (
              <div className="flex items-center gap-2">
                <input
                  value={nameValue}
                  onChange={(e) => setNameValue(e.target.value)}
                  autoFocus
                  className="flex-1 bg-[#111827] text-[#F9FAFB] text-base font-bold rounded-lg px-2 py-1 outline-none border border-[#A855F7]/40"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleSaveName()
                    if (e.key === 'Escape') { setEditingName(false); setNameValue(user?.name || '') }
                  }}
                />
                <button
                  onClick={handleSaveName}
                  disabled={savingName}
                  className="p-1.5 rounded-lg bg-[#22C55E]/20 text-[#22C55E] hover:bg-[#22C55E]/30 transition-colors"
                >
                  {savingName ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                </button>
                <button
                  onClick={() => { setEditingName(false); setNameValue(user?.name || '') }}
                  className="p-1.5 rounded-lg bg-[#EF4444]/20 text-[#EF4444] hover:bg-[#EF4444]/30 transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-[#F9FAFB] truncate">{user?.name}</h2>
                <button
                  onClick={() => setEditingName(true)}
                  className="p-1 rounded text-[#6B7280] hover:text-[#A855F7] transition-colors"
                >
                  <Edit2 className="h-3.5 w-3.5" />
                </button>
              </div>
            )}
            <p className="text-sm text-[#6B7280] truncate">{user?.email}</p>
            <span
              className="inline-block mt-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide"
              style={{
                background: user?.role === 'admin' ? 'rgba(168,85,247,0.15)' : 'rgba(34,197,94,0.12)',
                color: user?.role === 'admin' ? '#A855F7' : '#22C55E',
              }}
            >
              {user?.role === 'admin' ? '⚡ Admin' : '✓ Verified User'}
            </span>
          </div>
        </div>

        <div className="mt-5 space-y-3 pt-4 border-t border-[#1F2937]">
          <div className="flex items-center gap-3 text-sm">
            <Mail className="h-4 w-4 text-[#6B7280] shrink-0" />
            <span className="text-[#6B7280]">Email</span>
            <span className="ml-auto text-[#F9FAFB] truncate max-w-[180px]">{user?.email}</span>
          </div>
          {user?.phone && (
            <div className="flex items-center gap-3 text-sm">
              <Phone className="h-4 w-4 text-[#6B7280] shrink-0" />
              <span className="text-[#6B7280]">Phone</span>
              <span className="ml-auto text-[#F9FAFB]">{user.phone}</span>
            </div>
          )}
        </div>
      </div>

      {/* Emergency Contacts — real API */}
      <div className="rounded-2xl overflow-hidden" style={{ background: '#1A1A24', border: '1px solid #1F2937' }}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#1F2937]">
          <div className="flex items-center gap-2">
            <Users className="h-4 w-4 text-[#A855F7]" />
            <span className="text-sm font-semibold text-[#F9FAFB]">Emergency Contacts</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-[#6B7280]">{contacts.length} added</span>
            <button
              onClick={() => setShowAddContact(!showAddContact)}
              className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-semibold transition-all"
              style={{
                background: showAddContact ? 'rgba(168,85,247,0.15)' : 'rgba(168,85,247,0.08)',
                color: '#A855F7',
                border: '1px solid rgba(168,85,247,0.2)',
              }}
            >
              <Plus className="h-3 w-3" />
              Add
            </button>
          </div>
        </div>

        {/* Add Contact Form */}
        {showAddContact && (
          <AddContactForm
            onSubmit={(data) => addContactMutation.mutate(data)}
            isLoading={addContactMutation.isPending}
            onCancel={() => setShowAddContact(false)}
          />
        )}

        <div className="divide-y divide-[#1F2937]">
          {contactsLoading ? (
            <div className="px-4 py-6 space-y-3">
              {[1, 2].map(i => (
                <div key={i} className="flex gap-3 items-center">
                  <div className="w-8 h-8 rounded-full bg-[#111827] animate-pulse" />
                  <div className="flex-1 space-y-1">
                    <div className="h-3 w-24 bg-[#111827] rounded animate-pulse" />
                    <div className="h-2 w-16 bg-[#111827] rounded animate-pulse" />
                  </div>
                </div>
              ))}
            </div>
          ) : contacts.length > 0 ? (
            contacts.map((contact: EmergencyContact) => (
              <div key={contact.id} className="flex items-center gap-3 px-4 py-3">
                <div
                  className="flex items-center justify-center w-8 h-8 rounded-full text-xs font-bold shrink-0"
                  style={{ background: 'rgba(168,85,247,0.15)', color: '#A855F7' }}
                >
                  {contact.name[0].toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <p className="text-sm font-medium text-[#F9FAFB] truncate">{contact.name}</p>
                    {contact.isPrimary && (
                      <Star className="h-3 w-3 text-[#F59E0B] shrink-0" fill="#F59E0B" />
                    )}
                  </div>
                  <p className="text-xs text-[#6B7280]">{contact.relationship}</p>
                </div>
                <div className="text-right shrink-0 mr-2">
                  <p className="text-xs text-[#9CA3AF]">{contact.phone}</p>
                  {contact.isPrimary && (
                    <span className="text-[10px] text-[#22C55E]">Primary SOS</span>
                  )}
                </div>
                <button
                  onClick={() => deleteContactMutation.mutate(contact.id)}
                  disabled={deleteContactMutation.isPending}
                  className="p-1.5 rounded-lg text-[#6B7280] hover:text-[#EF4444] hover:bg-[#EF4444]/10 transition-colors"
                >
                  {deleteContactMutation.isPending && deleteContactMutation.variables === contact.id ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Trash2 className="h-3.5 w-3.5" />
                  )}
                </button>
              </div>
            ))
          ) : (
            <div className="px-4 py-6 text-center">
              <p className="text-sm text-[#6B7280]">No emergency contacts added</p>
              <p className="text-xs text-[#374151] mt-1">Contacts are notified when you trigger SOS</p>
              <button
                onClick={() => setShowAddContact(true)}
                className="mt-3 px-3 py-1.5 rounded-lg text-xs font-semibold text-[#A855F7] border border-[#A855F7]/30 hover:bg-[#A855F7]/10 transition-colors"
              >
                Add Your First Contact
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Settings */}
      <div className="rounded-2xl overflow-hidden" style={{ background: '#1A1A24', border: '1px solid #1F2937' }}>
        <div className="px-4 py-3 border-b border-[#1F2937]">
          <span className="text-xs font-semibold text-[#6B7280] uppercase tracking-wide">Preferences</span>
        </div>

        <SettingsToggle
          icon={<Bell className="h-4 w-4 text-[#A855F7]" />}
          label="Notifications"
          description="Alerts for nearby incidents"
          value={notificationsEnabled}
          onChange={toggleNotifications}
        />

        <SettingsToggle
          icon={<Shield className="h-4 w-4 text-[#22C55E]" />}
          label="Location Sharing"
          description="Share location during SOS"
          value={locationSharing}
          onChange={toggleLocationSharing}
          borderTop
        />

        <SettingsRow
          icon={<Lock className="h-4 w-4 text-[#6B7280]" />}
          label="Privacy Settings"
          borderTop
        />
      </div>

      {/* Logout */}
      <button
        onClick={handleLogout}
        className="w-full flex items-center justify-center gap-2 py-4 rounded-2xl font-semibold text-sm transition-all"
        style={{
          background: 'rgba(239,68,68,0.08)',
          border: '1px solid rgba(239,68,68,0.2)',
          color: '#EF4444',
        }}
      >
        <LogOut className="h-4 w-4" />
        Sign Out
      </button>

      <p className="text-center text-xs text-[#374151] pb-4">Avana v2.0 — Safety Intelligence Platform</p>
    </div>
  )
}

// ── Add Contact Form ──────────────────────────────────────────────────────────

function AddContactForm({
  onSubmit,
  isLoading,
  onCancel,
}: {
  onSubmit: (data: { name: string; phone: string; relationship: string; is_primary: boolean }) => void
  isLoading: boolean
  onCancel: () => void
}) {
  const [name, setName] = React.useState('')
  const [phone, setPhone] = React.useState('')
  const [relationship, setRelationship] = React.useState('')
  const [isPrimary, setIsPrimary] = React.useState(false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim() || !phone.trim() || !relationship.trim()) return
    onSubmit({ name: name.trim(), phone: phone.trim(), relationship: relationship.trim(), is_primary: isPrimary })
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="px-4 py-4 space-y-3 border-b border-[#1F2937]"
      style={{ background: 'rgba(168,85,247,0.04)' }}
    >
      <p className="text-xs font-semibold text-[#A855F7] uppercase tracking-wide">New Contact</p>

      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-[10px] text-[#6B7280] font-medium">Name *</label>
          <input
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="Rahul Kumar"
            required
            className="w-full mt-1 bg-[#111827] text-[#F9FAFB] text-sm rounded-lg px-3 py-2 outline-none border border-[#1F2937] focus:border-[#A855F7]/40 placeholder:text-[#374151]"
          />
        </div>
        <div>
          <label className="text-[10px] text-[#6B7280] font-medium">Phone *</label>
          <input
            value={phone}
            onChange={e => setPhone(e.target.value)}
            placeholder="+91-9876543210"
            required
            type="tel"
            className="w-full mt-1 bg-[#111827] text-[#F9FAFB] text-sm rounded-lg px-3 py-2 outline-none border border-[#1F2937] focus:border-[#A855F7]/40 placeholder:text-[#374151]"
          />
        </div>
      </div>

      <div>
        <label className="text-[10px] text-[#6B7280] font-medium">Relationship *</label>
        <input
          value={relationship}
          onChange={e => setRelationship(e.target.value)}
          placeholder="Brother, Mother, Friend..."
          required
          className="w-full mt-1 bg-[#111827] text-[#F9FAFB] text-sm rounded-lg px-3 py-2 outline-none border border-[#1F2937] focus:border-[#A855F7]/40 placeholder:text-[#374151]"
        />
      </div>

      <label className="flex items-center gap-2 cursor-pointer">
        <div
          onClick={() => setIsPrimary(!isPrimary)}
          className="w-4 h-4 rounded border flex items-center justify-center transition-all"
          style={{
            background: isPrimary ? '#A855F7' : 'transparent',
            borderColor: isPrimary ? '#A855F7' : '#374151',
          }}
        >
          {isPrimary && <Check className="h-2.5 w-2.5 text-white" />}
        </div>
        <span className="text-xs text-[#9CA3AF]">Mark as primary SOS contact</span>
      </label>

      <div className="flex gap-2 pt-1">
        <button
          type="submit"
          disabled={isLoading || !name || !phone || !relationship}
          className="flex-1 py-2 rounded-xl text-xs font-bold transition-all disabled:opacity-50"
          style={{ background: '#A855F7', color: '#fff' }}
        >
          {isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin mx-auto" /> : 'Add Contact'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 rounded-xl text-xs font-semibold transition-all"
          style={{ background: '#1F2937', color: '#6B7280' }}
        >
          Cancel
        </button>
      </div>
    </form>
  )
}

// ── Helper components ─────────────────────────────────────────────────────────

function SettingsToggle({
  icon, label, description, value, onChange, borderTop,
}: {
  icon: React.ReactNode
  label: string
  description: string
  value: boolean
  onChange: (val: boolean) => void
  borderTop?: boolean
}) {
  return (
    <div className={`flex items-center justify-between px-4 py-4 ${borderTop ? 'border-t border-[#1F2937]' : ''}`}>
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 flex items-center justify-center rounded-xl" style={{ background: '#111827' }}>
          {icon}
        </div>
        <div>
          <p className="text-sm font-medium text-[#F9FAFB]">{label}</p>
          <p className="text-xs text-[#6B7280]">{description}</p>
        </div>
      </div>
      <button
        onClick={() => onChange(!value)}
        className="relative w-10 h-6 rounded-full transition-all duration-200 shrink-0"
        style={{ background: value ? '#A855F7' : '#1F2937' }}
      >
        <div
          className="absolute top-1 h-4 w-4 rounded-full bg-white transition-all duration-200"
          style={{ left: value ? '22px' : '2px', boxShadow: '0 1px 4px rgba(0,0,0,0.3)' }}
        />
      </button>
    </div>
  )
}

function SettingsRow({ icon, label, borderTop }: { icon: React.ReactNode; label: string; borderTop?: boolean }) {
  return (
    <button
      className={`w-full flex items-center gap-3 px-4 py-4 hover:bg-[#1F2937] transition-colors text-left ${borderTop ? 'border-t border-[#1F2937]' : ''}`}
    >
      <div className="w-8 h-8 flex items-center justify-center rounded-xl" style={{ background: '#111827' }}>
        {icon}
      </div>
      <span className="flex-1 text-sm font-medium text-[#F9FAFB]">{label}</span>
      <ChevronRight className="h-4 w-4 text-[#6B7280]" />
    </button>
  )
}

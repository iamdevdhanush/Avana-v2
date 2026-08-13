import * as React from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  User, Phone, Shield, Bell, Lock, LogOut, ChevronRight,
  Mail, Users, Edit2, Check, X, Loader2, Plus, Trash2, Star, ShieldCheck,
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

  // Emergency contacts query
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

  const handleSaveName = async () => {
    if (!nameValue.trim() || nameValue === user?.name) {
      setEditingName(false)
      return
    }
    setSavingName(true)
    try {
      await authApi.updateProfile({ name: nameValue.trim() } as Parameters<typeof authApi.updateProfile>[0])
      await loadUser()
      addToast({ title: 'Profile name updated', variant: 'success' })
    } catch {
      addToast({ title: 'Failed to update profile name', variant: 'destructive' })
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
    <div className="min-h-full max-w-lg mx-auto px-4 py-6 space-y-5 animate-fade-in-up pb-safe bg-[#07110A]">

      {/* User Information */}
      <div className="rounded-2xl p-5 avana-surface">
        <div className="flex items-center gap-4">
          <Avatar className="h-14 w-14 border border-[#1D3823]">
            {user?.avatar ? (
              <img src={user.avatar} alt={user.name} className="object-cover" />
            ) : (
              <AvatarFallback className="text-base font-bold bg-[#122417] text-[#66BB6A]">
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
                  className="flex-1 bg-[#122417] text-[#F1F8F2] text-sm font-bold rounded-lg px-2.5 py-1 outline-none border border-[#66BB6A]"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleSaveName()
                    if (e.key === 'Escape') { setEditingName(false); setNameValue(user?.name || '') }
                  }}
                />
                <button
                  onClick={handleSaveName}
                  disabled={savingName}
                  className="p-1.5 rounded-lg bg-[#66BB6A]/20 text-[#66BB6A]"
                >
                  {savingName ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-[#F1F8F2] truncate">{user?.name}</h2>
                <button
                  onClick={() => setEditingName(true)}
                  className="p-1 text-[#8A948C] hover:text-[#66BB6A] transition-colors"
                >
                  <Edit2 className="h-3.5 w-3.5" />
                </button>
              </div>
            )}
            <p className="text-xs text-[#9BAF9F] truncate">{user?.email}</p>
            <span className="inline-flex items-center gap-1 mt-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-[#122417] border border-[#1D3823] text-[#66BB6A]">
              <ShieldCheck className="h-3 w-3" />
              {user?.role === 'admin' ? 'Administrator' : 'Verified Safety Member'}
            </span>
          </div>
        </div>
      </div>

      {/* Emergency Contacts Section */}
      <div className="rounded-2xl avana-surface overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#1D3823]">
          <div className="flex items-center gap-2">
            <Users className="h-4 w-4 text-[#66BB6A]" />
            <span className="text-xs font-bold text-[#F1F8F2]">EMERGENCY CONTACTS</span>
          </div>
          <button
            onClick={() => setShowAddContact(!showAddContact)}
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold text-[#07110A] bg-[#66BB6A] hover:bg-[#81C784] transition-all"
          >
            <Plus className="h-3.5 w-3.5" />
            Add Contact
          </button>
        </div>

        {/* Add Contact Form */}
        {showAddContact && (
          <AddContactForm
            onSubmit={(data) => addContactMutation.mutate(data)}
            isLoading={addContactMutation.isPending}
            onCancel={() => setShowAddContact(false)}
          />
        )}

        <div className="divide-y divide-[#1D3823]">
          {contactsLoading ? (
            <div className="px-4 py-4 space-y-2">
              {[1, 2].map(i => (
                <div key={i} className="h-10 bg-[#122417] rounded-lg animate-pulse" />
              ))}
            </div>
          ) : contacts.length > 0 ? (
            contacts.map((contact: EmergencyContact) => (
              <div key={contact.id} className="flex items-center gap-3 px-4 py-3">
                <div className="w-8 h-8 rounded-full bg-[#122417] border border-[#1D3823] flex items-center justify-center text-xs font-bold text-[#66BB6A]">
                  {contact.name[0].toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <p className="text-xs font-bold text-[#F1F8F2] truncate">{contact.name}</p>
                    {contact.isPrimary && (
                      <Star className="h-3 w-3 text-[#F59E0B]" fill="#F59E0B" />
                    )}
                  </div>
                  <p className="text-[10px] text-[#9BAF9F]">{contact.relationship} · {contact.phone}</p>
                </div>
                <button
                  onClick={() => deleteContactMutation.mutate(contact.id)}
                  disabled={deleteContactMutation.isPending}
                  className="p-1.5 text-[#8A948C] hover:text-[#EF4444] transition-colors"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))
          ) : (
            <div className="px-4 py-6 text-center space-y-1">
              <p className="text-xs font-semibold text-[#F1F8F2]">No emergency contacts configured</p>
              <p className="text-[10px] text-[#9BAF9F]">
                Add trusted family members or friends to be notified during SOS emergencies.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Safety & App Preferences */}
      <div className="rounded-2xl avana-surface overflow-hidden">
        <div className="px-4 py-3 border-b border-[#1D3823]">
          <span className="text-[10px] font-bold text-[#8A948C] uppercase tracking-wider">Preferences & Security</span>
        </div>

        <SettingsToggle
          icon={<Bell className="h-4 w-4 text-[#66BB6A]" />}
          label="Safety Notifications"
          description="Real-time incident alerts near location"
          value={notificationsEnabled}
          onChange={toggleNotifications}
        />

        <SettingsToggle
          icon={<Shield className="h-4 w-4 text-[#66BB6A]" />}
          label="Emergency Location Sharing"
          description="Transmit location coordinates during SOS"
          value={locationSharing}
          onChange={toggleLocationSharing}
          borderTop
        />

        <SettingsRow
          icon={<Lock className="h-4 w-4 text-[#8A948C]" />}
          label="Privacy & Security Audit"
          borderTop
        />
      </div>

      {/* Sign Out */}
      <button
        onClick={handleLogout}
        className="w-full flex items-center justify-center gap-2 py-3 rounded-xl font-bold text-xs text-[#EF4444] bg-[#EF4444]/10 border border-[#EF4444]/20 hover:bg-[#EF4444]/15 transition-all"
      >
        <LogOut className="h-4 w-4" />
        Sign Out of Avana
      </button>
    </div>
  )
}

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
    <form onSubmit={handleSubmit} className="p-4 space-y-3 border-b border-[#1D3823] bg-[#122417]">
      <p className="text-[10px] font-bold text-[#66BB6A] uppercase tracking-wider">New Emergency Contact</p>
      <div className="grid grid-cols-2 gap-2">
        <input
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder="Contact Name *"
          required
          className="bg-[#0D1A10] text-[#F1F8F2] text-xs rounded-lg px-3 py-2 border border-[#1D3823] outline-none"
        />
        <input
          value={phone}
          onChange={e => setPhone(e.target.value)}
          placeholder="Phone Number *"
          type="tel"
          required
          className="bg-[#0D1A10] text-[#F1F8F2] text-xs rounded-lg px-3 py-2 border border-[#1D3823] outline-none"
        />
      </div>
      <input
        value={relationship}
        onChange={e => setRelationship(e.target.value)}
        placeholder="Relationship (Mother, Brother, Friend) *"
        required
        className="w-full bg-[#0D1A10] text-[#F1F8F2] text-xs rounded-lg px-3 py-2 border border-[#1D3823] outline-none"
      />
      <div className="flex items-center gap-2 pt-1">
        <button
          type="submit"
          disabled={isLoading || !name || !phone || !relationship}
          className="px-4 py-2 rounded-lg text-xs font-bold text-[#07110A] bg-[#66BB6A]"
        >
          Save Contact
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-2 rounded-lg text-xs text-[#8A948C]"
        >
          Cancel
        </button>
      </div>
    </form>
  )
}

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
    <div className={`flex items-center justify-between px-4 py-3.5 ${borderTop ? 'border-t border-[#1D3823]' : ''}`}>
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-[#122417]">
          {icon}
        </div>
        <div>
          <p className="text-xs font-bold text-[#F1F8F2]">{label}</p>
          <p className="text-[10px] text-[#9BAF9F]">{description}</p>
        </div>
      </div>
      <button
        onClick={() => onChange(!value)}
        className="relative w-9 h-5 rounded-full transition-all shrink-0"
        style={{ background: value ? '#66BB6A' : '#1D3823' }}
      >
        <div
          className="absolute top-0.5 h-4 w-4 rounded-full bg-[#07110A] transition-all"
          style={{ left: value ? '18px' : '2px' }}
        />
      </button>
    </div>
  )
}

function SettingsRow({ icon, label, borderTop }: { icon: React.ReactNode; label: string; borderTop?: boolean }) {
  return (
    <button
      className={`w-full flex items-center gap-3 px-4 py-3.5 hover:bg-[#122417] transition-colors text-left ${borderTop ? 'border-t border-[#1D3823]' : ''}`}
    >
      <div className="p-2 rounded-lg bg-[#122417]">
        {icon}
      </div>
      <span className="flex-1 text-xs font-bold text-[#F1F8F2]">{label}</span>
      <ChevronRight className="h-4 w-4 text-[#8A948C]" />
    </button>
  )
}

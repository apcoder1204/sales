import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { User, Mail, Lock } from 'lucide-react'
import PageWrapper from '@components/layout/PageWrapper'
import Input from '@components/ui/Input'
import Button from '@components/ui/Button'
import { useAuth } from '@hooks/useAuth'
import { useToast } from '@hooks/useToast'
import { authService } from '@services/authService'
import { tokenStorage } from '@services/api'
import SW from '@constants/sw'

export default function ProfilePage() {
  const { user, reload } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()

  const [username, setUsername] = useState(user?.username || '')
  const [fullName, setFullName] = useState(user?.full_name || '')
  const [email, setEmail] = useState(user?.email || '')
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const wantsPasswordChange = currentPassword || newPassword || confirmPassword

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (wantsPasswordChange && (!currentPassword || !newPassword || !confirmPassword)) {
      setError(SW.wasifu.jazaVyoteVyaNenosiri)
      return
    }
    if (wantsPasswordChange && newPassword !== confirmPassword) {
      setError(SW.wasifu.nenosiriHazifanani)
      return
    }

    const payload = {}
    if (username !== user?.username) payload.username = username
    if (fullName !== user?.full_name) payload.full_name = fullName
    if (email !== (user?.email || '')) payload.email = email
    if (wantsPasswordChange) {
      payload.current_password = currentPassword
      payload.new_password = newPassword
      payload.confirm_password = confirmPassword
    }

    if (Object.keys(payload).length === 0) return

    setSaving(true)
    try {
      await authService.updateMe(payload)
      if (wantsPasswordChange) {
        // The server invalidated every existing session/token the moment
        // the password changed — the access token this very request just
        // used is already stale for anything after it, so log out cleanly
        // instead of letting the next API call fail and bounce unexpectedly.
        toast.success(SW.wasifu.mafanikioNenosiri)
        tokenStorage.clear()
        navigate('/login')
        return
      }
      toast.success(SW.wasifu.mafanikio)
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      await reload()
    } catch (err) {
      setError(err.response?.data?.detail || SW.makosa.jumla)
    } finally {
      setSaving(false)
    }
  }

  return (
    <PageWrapper title={SW.wasifu.kichwa}>
      <form onSubmit={handleSubmit} className="max-w-lg space-y-6">
        <div className="glass-card p-6 space-y-4">
          <h2 className="text-sm font-semibold text-text-primary">
            {SW.wasifu.maelezoYaKimsingi}
          </h2>
          <Input
            label={SW.auth.jinalaMtumiaji}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            leftIcon={<User size={16} />}
            autoComplete="username"
            required
          />
          <Input
            label={SW.wasifu.jinaKamili}
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            leftIcon={<User size={16} />}
            required
          />
          <Input
            label={SW.auth.barua_pepe}
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            leftIcon={<Mail size={16} />}
            autoComplete="email"
          />
        </div>

        <div className="glass-card p-6 space-y-4">
          <h2 className="text-sm font-semibold text-text-primary">
            {SW.wasifu.badilishaNenosiri}
          </h2>
          <Input
            label={SW.wasifu.nenosiriLaSasa}
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            leftIcon={<Lock size={16} />}
            autoComplete="current-password"
          />
          <Input
            label={SW.wasifu.nenosiriJipya}
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            leftIcon={<Lock size={16} />}
            autoComplete="new-password"
          />
          <Input
            label={SW.wasifu.thibitishaNenosiri}
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            leftIcon={<Lock size={16} />}
            autoComplete="new-password"
          />
        </div>

        {error && (
          <div className="text-sm text-accent-red bg-accent-red-muted border border-accent-red/20 rounded-lg px-3 py-2">
            {error}
          </div>
        )}

        <Button type="submit" loading={saving}>
          {saving ? SW.wasifu.inahifadhi : SW.wasifu.hifadhiMabadiliko}
        </Button>
      </form>
    </PageWrapper>
  )
}

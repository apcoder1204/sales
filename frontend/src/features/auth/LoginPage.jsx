import React, { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Eye, EyeOff, Zap, Lock, User } from 'lucide-react'
import { useAuth } from '@hooks/useAuth'
import Button from '@components/ui/Button'
import Input from '@components/ui/Input'
import SW from '@constants/sw'

export default function LoginPage() {
  const { login, isAuthenticated } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ username: '', password: '' })
  const [showPwd, setShowPwd] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (isAuthenticated) navigate('/dashibodi', { replace: true })
  }, [isAuthenticated, navigate])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.username || !form.password) return
    setLoading(true)
    setError('')
    try {
      await login(form.username, form.password)
      navigate('/dashibodi', { replace: true })
    } catch (err) {
      const detail = err.response?.data?.detail || SW.makosa.jumla
      setError(detail)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background glow */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -left-40 w-96 h-96 bg-primary/10 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-accent-purple/10 rounded-full blur-3xl" />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-sm relative z-10"
      >
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-gradient-primary flex items-center justify-center mb-4 shadow-glow">
            <Zap size={28} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold text-text-primary">{SW.appName}</h1>
          <p className="text-text-muted text-sm mt-1">{SW.auth.tafadhaliIngia}</p>
        </div>

        {/* Card */}
        <div className="glass-card p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label={SW.auth.jinalaMtumiaji}
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              leftIcon={<User size={16} />}
              placeholder="superadmin"
              autoComplete="username"
              autoFocus
              required
            />
            <Input
              label={SW.auth.nenosiri}
              type={showPwd ? 'text' : 'password'}
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              leftIcon={<Lock size={16} />}
              rightIcon={
                <button type="button" onClick={() => setShowPwd((v) => !v)} className="hover:text-text-primary transition-colors">
                  {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              }
              placeholder="••••••"
              autoComplete="current-password"
              required
            />

            {error && (
              <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-sm text-accent-red bg-accent-red-muted border border-accent-red/20 rounded-lg px-3 py-2"
              >
                {error}
              </motion.div>
            )}

            <Button type="submit" loading={loading} className="w-full" size="lg">
              {SW.auth.kuingia}
            </Button>

            <Link
              to="/forgot-password"
              className="block text-center text-sm text-text-muted hover:text-text-primary transition-colors"
            >
              {SW.auth.umesahauNenosiri}
            </Link>
          </form>

          {/* Demo hint */}
          <div className="mt-5 pt-4 border-t border-border">
            <p className="text-xs text-text-muted text-center mb-2">Akaunti za mazoezi (nenosiri: 1234)</p>
            <div className="grid grid-cols-2 gap-1 text-xs text-text-muted">
              {['superadmin', 'admin', 'storekeeper', 'manager', 'cctvpoint', 'kabwepoint', 'ahpoint'].map((u) => (
                <button
                  key={u}
                  type="button"
                  onClick={() => setForm({ username: u, password: '1234' })}
                  className="text-left px-2 py-1 rounded hover:bg-bg-hover hover:text-text-secondary transition-colors"
                >
                  {u}
                </button>
              ))}
            </div>
          </div>
        </div>

        <p className="text-center text-xs text-text-muted mt-6">
          DUKANI POS &copy; {new Date().getFullYear()} — Haki zote zimehifadhiwa
        </p>
      </motion.div>
    </div>
  )
}

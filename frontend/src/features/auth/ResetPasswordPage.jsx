import React, { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Eye, EyeOff, Zap, Lock, ArrowLeft } from 'lucide-react'
import Button from '@components/ui/Button'
import Input from '@components/ui/Input'
import SW from '@constants/sw'
import { authService } from '@services/authService'

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''
  const navigate = useNavigate()

  const [form, setForm] = useState({ password: '', confirm: '' })
  const [showPwd, setShowPwd] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.password || !form.confirm) return
    setLoading(true)
    setError('')
    try {
      await authService.resetPassword(token, form.password, form.confirm)
      setDone(true)
      setTimeout(() => navigate('/login', { replace: true }), 2500)
    } catch (err) {
      const detail = err.response?.data?.detail
      if (typeof detail === 'string') {
        setError(detail)
      } else if (Array.isArray(detail) && detail[0]?.msg) {
        setError(detail[0].msg)
      } else {
        setError(SW.makosa.jumla)
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4 relative overflow-hidden">
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
        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-gradient-primary flex items-center justify-center mb-4 shadow-glow">
            <Zap size={28} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold text-text-primary">{SW.appName}</h1>
          <p className="text-text-muted text-sm mt-1">{SW.auth.resetKichwa}</p>
        </div>

        <div className="glass-card p-6">
          {!token ? (
            <div className="text-sm text-accent-red bg-accent-red-muted border border-accent-red/20 rounded-lg px-3 py-2 text-center">
              {SW.auth.kiunganiSahihi}
            </div>
          ) : done ? (
            <div className="text-sm text-text-secondary text-center py-2">
              {SW.auth.resetMafanikio}
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <Input
                label={SW.auth.nenosiriJipya}
                type={showPwd ? 'text' : 'password'}
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                leftIcon={<Lock size={16} />}
                rightIcon={
                  <button type="button" onClick={() => setShowPwd((v) => !v)} className="hover:text-text-primary transition-colors">
                    {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                }
                autoComplete="new-password"
                autoFocus
                required
              />
              <Input
                label={SW.auth.thibitishaNenosiri}
                type={showPwd ? 'text' : 'password'}
                value={form.confirm}
                onChange={(e) => setForm({ ...form, confirm: e.target.value })}
                leftIcon={<Lock size={16} />}
                autoComplete="new-password"
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
                {loading ? SW.auth.inaweka : SW.auth.wekaNenosiri}
              </Button>
            </form>
          )}

          <div className="mt-5 pt-4 border-t border-border">
            <Link
              to="/login"
              className="flex items-center justify-center gap-1.5 text-sm text-text-muted hover:text-text-primary transition-colors"
            >
              <ArrowLeft size={14} />
              {SW.auth.rudiKuingia}
            </Link>
          </div>
        </div>
      </motion.div>
    </div>
  )
}

import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Mail, Zap, ArrowLeft } from 'lucide-react'
import Button from '@components/ui/Button'
import Input from '@components/ui/Input'
import SW from '@constants/sw'
import { authService } from '@services/authService'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [sent, setSent] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!email) return
    setLoading(true)
    setError('')
    try {
      await authService.forgotPassword(email)
      setSent(true)
    } catch (err) {
      const detail = err.response?.data?.detail || SW.makosa.jumla
      setError(detail)
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
          <p className="text-text-muted text-sm mt-1">{SW.auth.ombaKichwa}</p>
        </div>

        <div className="glass-card p-6">
          {sent ? (
            <div className="text-sm text-text-secondary text-center py-2">
              {SW.auth.ombaImetumwa}
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <p className="text-sm text-text-muted">{SW.auth.ombaMaelezo}</p>
              <Input
                label={SW.auth.barua_pepe}
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                leftIcon={<Mail size={16} />}
                placeholder="jina@mfano.com"
                autoComplete="email"
                autoFocus
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
                {loading ? SW.auth.inatuma : SW.auth.tumaKiungo}
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

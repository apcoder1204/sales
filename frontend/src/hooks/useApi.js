import { useState, useCallback } from 'react'
import { useToast } from './useToast'
import SW from '@constants/sw'

export function useApi() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const toast = useToast()

  const call = useCallback(async (fn, { onSuccess, onError, successMsg, silent = false } = {}) => {
    setLoading(true)
    setError(null)
    try {
      const result = await fn()
      if (successMsg && !silent) toast.success(successMsg)
      onSuccess?.(result)
      return result
    } catch (err) {
      const raw = err.response?.data?.detail
      let msg
      if (Array.isArray(raw) && raw.length > 0) {
        // Pydantic v2 validation errors — extract readable messages, strip "Value error, " prefix
        msg = raw
          .map((e) => (e.msg || '').replace(/^Value error,\s*/, ''))
          .filter(Boolean)
          .join('; ') || SW.makosa.jumla
      } else {
        msg = (typeof raw === 'string' ? raw : null) || SW.makosa.jumla
      }
      setError(msg)
      if (!silent) toast.error(msg)
      onError?.(err)
      throw err
    } finally {
      setLoading(false)
    }
  }, [toast])

  return { loading, error, call }
}

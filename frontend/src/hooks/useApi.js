import { useState, useCallback } from 'react'
import { useToast } from './useToast'
import { resolveApiErrorMessage } from '@utils/apiError'

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
      const msg = resolveApiErrorMessage(err)
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

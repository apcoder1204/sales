import { useCallback, useEffect, useState } from 'react'
import { whatsappService } from '@services/whatsappService'

const TTL_MS = 60_000
const DISABLED = { enabled: false, configured: false, connected: false }

// Module-level cache so a page with many rows (each with a send button)
// makes one status request, not one per row.
let cache = { at: 0, value: null, inflight: null }

function fetchStatus(force) {
  const fresh = cache.value && Date.now() - cache.at < TTL_MS
  if (fresh && !force) return Promise.resolve(cache.value)
  if (cache.inflight && !force) return cache.inflight
  cache.inflight = whatsappService
    .getStatus()
    .catch(() => DISABLED)
    .then((value) => {
      cache = { at: Date.now(), value, inflight: null }
      return value
    })
  return cache.inflight
}

export function useWhatsAppStatus() {
  const [status, setStatus] = useState(cache.value || DISABLED)
  const [loading, setLoading] = useState(!cache.value)

  const refresh = useCallback(async (force = true) => {
    const value = await fetchStatus(force)
    setStatus(value)
    setLoading(false)
  }, [])

  useEffect(() => {
    refresh(false)
  }, [refresh])

  return { ...status, loading, refresh }
}

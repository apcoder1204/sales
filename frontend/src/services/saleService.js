import api from './api'

export const saleService = {
  list: async (params = {}) => {
    const { data } = await api.get('/sales', { params })
    return data
  },

  get: async (id) => {
    const { data } = await api.get(`/sales/${id}`)
    return data
  },

  // idempotencyKey: pass the same value across retries of one checkout
  // attempt (network timeout, a re-click before the button disables) so the
  // backend replays the first response instead of creating a second sale.
  create: async (payload, idempotencyKey) => {
    const { data } = await api.post('/sales', payload, {
      headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined,
    })
    return data
  },

  void: async (id, reason) => {
    const { data } = await api.post(`/sales/${id}/void`, { reason })
    return data
  },

  receipt: async (id) => {
    const { data } = await api.get(`/sales/${id}/receipt`)
    return data
  },
}

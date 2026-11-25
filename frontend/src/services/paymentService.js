import api from './api'

export const paymentService = {
  get: async (id) => {
    const { data } = await api.get(`/payments/${id}`)
    return data
  },

  // Reprint: read-only, no side effects on the server.
  receipt: async (id) => {
    const { data } = await api.get(`/payments/${id}/receipt`)
    return data
  },

  reverse: async (id, reason, idempotencyKey) => {
    const { data } = await api.post(`/payments/${id}/reverse`, { reason }, {
      headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined,
    })
    return data
  },
}

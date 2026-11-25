import api from './api'

const withKey = (idempotencyKey) =>
  idempotencyKey ? { headers: { 'Idempotency-Key': idempotencyKey } } : undefined

export const customerService = {
  search: async (q, params = {}) => {
    const { data } = await api.get('/customers', { params: { q: q || undefined, ...params } })
    return data
  },

  // params.branch_id: optional branch scope for global roles (ignored for cashiers)
  get: async (id, params = {}) => {
    const { data } = await api.get(`/customers/${id}`, { params })
    return data
  },

  create: async (payload) => {
    const { data } = await api.post('/customers', payload)
    return data
  },

  update: async (id, payload) => {
    const { data } = await api.put(`/customers/${id}`, payload)
    return data
  },

  updateCredit: async (id, payload) => {
    const { data } = await api.put(`/customers/${id}/credit`, payload)
    return data
  },

  receivables: async (id, params = {}) => {
    const { data } = await api.get(`/customers/${id}/receivables`, { params })
    return data
  },

  payments: async (id, params = {}) => {
    const { data } = await api.get(`/customers/${id}/payments`, { params })
    return data
  },

  // One idempotency key per "receive payment" attempt so a retried click or
  // a slow network can never record the same money twice.
  recordPayment: async (id, payload, idempotencyKey) => {
    const { data } = await api.post(`/customers/${id}/payments`, payload, withKey(idempotencyKey))
    return data
  },

  openingBalances: {
    list: async (params = {}) => {
      const { data } = await api.get('/opening-balances', { params })
      return data
    },
    create: async (customerId, payload) => {
      const { data } = await api.post(`/customers/${customerId}/opening-balances`, payload)
      return data
    },
    approve: async (id, note, idempotencyKey) => {
      const { data } = await api.post(`/opening-balances/${id}/approve`, { note: note || null }, withKey(idempotencyKey))
      return data
    },
    reject: async (id, note) => {
      const { data } = await api.post(`/opening-balances/${id}/reject`, { note })
      return data
    },
  },
}

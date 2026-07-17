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

  create: async (payload) => {
    const { data } = await api.post('/sales', payload)
    return data
  },

  void: async (id, reason) => {
    const { data } = await api.post(`/sales/${id}/void`, { void_reason: reason })
    return data
  },

  receipt: async (id) => {
    const { data } = await api.get(`/sales/${id}/receipt`)
    return data
  },
}

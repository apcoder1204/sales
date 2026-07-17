import api from './api'

export const transferService = {
  listRequests: async (params = {}) => {
    const { data } = await api.get('/transfers/requests', { params })
    return data
  },

  listTransfers: async (params = {}) => {
    const { data } = await api.get('/transfers', { params })
    return data
  },

  getRequest: async (id) => {
    const { data } = await api.get(`/transfers/requests/${id}`)
    return data
  },

  createRequest: async (payload) => {
    const { data } = await api.post('/transfers/requests', payload)
    return data
  },

  approveRequest: async (id, payload) => {
    const { data } = await api.put(`/transfers/requests/${id}/approve`, payload)
    return data
  },

  rejectRequest: async (id, reason) => {
    const { data } = await api.put(`/transfers/requests/${id}/reject`, { notes: reason })
    return data
  },

  executeTransfer: async (id) => {
    const { data } = await api.post(`/transfers/requests/${id}/execute`)
    return data
  },

  createDirect: async (payload) => {
    const { data } = await api.post('/transfers', payload)
    return data
  },
}

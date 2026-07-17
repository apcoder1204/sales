import api from './api'

export const closingService = {
  preview: async (branchId, businessDate) => {
    const { data } = await api.get('/closings/preview', {
      params: { branch_id: branchId, business_date: businessDate },
    })
    return data
  },

  close: async (payload) => {
    const { data } = await api.post('/closings/close', payload)
    return data
  },

  reopen: async (id, reason) => {
    const { data } = await api.put(`/closings/${id}/reopen`, { reason })
    return data
  },

  list: async (params = {}) => {
    const { data } = await api.get('/closings', { params })
    return data
  },
}

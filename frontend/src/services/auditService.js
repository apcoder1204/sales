import api from './api'

export const auditService = {
  list: async (params = {}) => {
    const { data } = await api.get('/audit-logs', { params })
    return data
  },

  get: async (id) => {
    const { data } = await api.get(`/audit-logs/${id}`)
    return data
  },
}

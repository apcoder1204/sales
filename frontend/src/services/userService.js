import api from './api'

export const userService = {
  list: async (params = {}) => {
    const { data } = await api.get('/users', { params })
    return data
  },

  get: async (id) => {
    const { data } = await api.get(`/users/${id}`)
    return data
  },

  create: async (payload) => {
    const { data } = await api.post('/users', payload)
    return data
  },

  update: async (id, payload) => {
    const { data } = await api.put(`/users/${id}`, payload)
    return data
  },

  unlock: async (id) => {
    const { data } = await api.post(`/users/${id}/unlock`)
    return data
  },

  deactivate: async (id) => {
    const { data } = await api.delete(`/users/${id}`)
    return data
  },

  activate: async (id) => {
    const { data } = await api.put(`/users/${id}`, { is_active: true })
    return data
  },

  permanentlyDelete: async (id) => {
    const { data } = await api.delete(`/users/${id}/permanent`)
    return data
  },

  branches: async () => {
    const { data } = await api.get('/users/branches')
    return data
  },

  roles: async () => {
    const { data } = await api.get('/users/roles')
    return data
  },
}

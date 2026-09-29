import api from './api'

// Global branch REGISTRY management (create/edit/deactivate/delete) — admin-
// only, backed by /branches. Deliberately separate from userService.branches(),
// which calls /users/branches (the role-scoped branch-context SELECTOR list
// every role uses, not a management surface) and must stay untouched.
export const branchService = {
  list: async () => {
    const { data } = await api.get('/branches')
    return data
  },

  get: async (id) => {
    const { data } = await api.get(`/branches/${id}`)
    return data
  },

  create: async (payload) => {
    const { data } = await api.post('/branches', payload)
    return data
  },

  update: async (id, payload) => {
    const { data } = await api.patch(`/branches/${id}`, payload)
    return data
  },

  remove: async (id) => {
    const { data } = await api.delete(`/branches/${id}`)
    return data
  },
}

import api from './api'

// Reconciliation (Upatanisho wa Hesabu): runs are started on demand and
// only ever read financial records; exceptions are reviewed by admins.
export const reconciliationService = {
  runs: {
    list: async () => (await api.get('/reconciliation/runs')).data,
    get: async (id) => (await api.get(`/reconciliation/runs/${id}`)).data,
    create: async (payload) => (await api.post('/reconciliation/runs', payload)).data,
  },
  exceptions: {
    list: async (params = {}) => (await api.get('/reconciliation/exceptions', { params })).data,
    changeStatus: async (id, payload) => (await api.post(`/reconciliation/exceptions/${id}/status`, payload)).data,
  },
}

import api from './api'

export const reportService = {
  sales: async (params = {}) => {
    const { data } = await api.get('/reports/sales', { params })
    return data
  },

  inventory: async (params = {}) => {
    const { data } = await api.get('/reports/inventory', { params })
    return data
  },

  stockMovements: async (params = {}) => {
    const { data } = await api.get('/inventory/movements', { params })
    return data
  },

  branchPerformance: async (params = {}) => {
    const { data } = await api.get('/reports/branch-performance', { params })
    return data
  },

  cashierPerformance: async (params = {}) => {
    const { data } = await api.get('/reports/cashier-performance', { params })
    return data
  },

  lowStock: async (params = {}) => {
    const { data } = await api.get('/reports/low-stock', { params })
    return data
  },

  closing: async (params = {}) => {
    const { data } = await api.get('/reports/closing', { params })
    return data
  },

  dashboard: async () => {
    const { data } = await api.get('/reports/dashboard')
    return data
  },
}

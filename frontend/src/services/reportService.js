import api from './api'

function mapReportParams(params = {}) {
  const { date_from, date_to, ...rest } = params
  return {
    ...rest,
    ...(date_from ? { from_date: date_from } : {}),
    ...(date_to ? { to_date: date_to } : {}),
  }
}

export const reportService = {
  sales: async (params = {}) => {
    const { data } = await api.get('/reports/sales', { params: mapReportParams(params) })
    return data
  },

  inventory: async (params = {}) => {
    const { data } = await api.get('/reports/inventory', { params: mapReportParams(params) })
    return data
  },

  stockMovements: async (params = {}) => {
    const { data } = await api.get('/inventory/movements', { params: mapReportParams(params) })
    return data
  },

  branchPerformance: async (params = {}) => {
    const { data } = await api.get('/reports/branch-performance', { params: mapReportParams(params) })
    return data
  },

  cashierPerformance: async (params = {}) => {
    const { data } = await api.get('/reports/cashier-performance', { params: mapReportParams(params) })
    return data
  },

  lowStock: async (params = {}) => {
    const { data } = await api.get('/reports/low-stock', { params: mapReportParams(params) })
    return data
  },

  closing: async (params = {}) => {
    const { data } = await api.get('/reports/closing', { params: mapReportParams(params) })
    return data
  },

  dashboard: async (params = {}) => {
    const { data } = await api.get('/reports/dashboard', { params: mapReportParams(params) })
    return data
  },
}

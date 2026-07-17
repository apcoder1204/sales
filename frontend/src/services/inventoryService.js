import api from './api'

export const inventoryService = {
  list: async (params = {}) => {
    const { data } = await api.get('/inventory', { params })
    return data
  },

  movements: async (params = {}) => {
    const { data } = await api.get('/inventory/movements', { params })
    return data
  },

  adjust: async (payload) => {
    const { data } = await api.post('/inventory/adjust', payload)
    return data
  },

  availableSources: async (productId, requiredQty, destinationBranchId) => {
    const { data } = await api.get('/inventory/available-sources', {
      params: { product_id: productId, quantity: requiredQty, destination_branch_id: destinationBranchId },
    })
    return data
  },

  summary: async (branchId) => {
    const { data } = await api.get('/inventory/summary', {
      params: branchId ? { branch_id: branchId } : {},
    })
    return data
  },
}

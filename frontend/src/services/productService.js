import api from './api'

export const productService = {
  // ─── Products ────────────────────────────────────────────────────────────
  list: async (params = {}) => {
    const { data } = await api.get('/products', { params })
    return data
  },

  get: async (id) => {
    const { data } = await api.get(`/products/${id}`)
    return data
  },

  create: async (payload) => {
    const { data } = await api.post('/products', payload)
    return data
  },

  update: async (id, payload) => {
    const { data } = await api.put(`/products/${id}`, payload)
    return data
  },

  delete: async (id) => {
    const { data } = await api.delete(`/products/${id}`)
    return data
  },

  // ─── Categories ──────────────────────────────────────────────────────────
  categories: async () => {
    const { data } = await api.get('/products/categories')
    return data
  },

  createCategory: async (payload) => {
    const { data } = await api.post('/products/categories', payload)
    return data
  },

  updateCategory: async (id, payload) => {
    const { data } = await api.put(`/products/categories/${id}`, payload)
    return data
  },

  deleteCategory: async (id) => {
    const { data } = await api.delete(`/products/categories/${id}`)
    return data
  },
}

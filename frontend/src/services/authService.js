import api from './api'

export const authService = {
  login: async (username, password) => {
    const { data } = await api.post('/auth/login', { username, password })
    return data
  },

  refresh: async (refreshToken) => {
    const { data } = await api.post('/auth/refresh', { refresh_token: refreshToken })
    return data
  },

  logout: async () => {
    try {
      await api.post('/auth/logout')
    } finally {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
    }
  },

  getMe: async () => {
    const { data } = await api.get('/auth/me')
    return data
  },
}

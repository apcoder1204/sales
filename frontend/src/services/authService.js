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

  forgotPassword: async (email) => {
    const { data } = await api.post('/auth/forgot-password', { email })
    return data
  },

  resetPassword: async (token, newPassword, confirmPassword) => {
    const { data } = await api.post('/auth/reset-password', {
      token,
      new_password: newPassword,
      confirm_password: confirmPassword,
    })
    return data
  },
}

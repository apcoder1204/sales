import axios from 'axios'

// ?? (not ||) so VITE_API_BASE_URL="" (empty string) works — empty = use Vite proxy (demo/tunnel mode)
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

// ── Token storage abstraction ─────────────────────────────────────────────────
// Centralised so swapping to cookies or sessionStorage is a one-line change.
export const tokenStorage = {
  getAccess: () => localStorage.getItem('access_token'),
  getRefresh: () => localStorage.getItem('refresh_token'),
  setTokens: (access, refresh) => {
    localStorage.setItem('access_token', access)
    if (refresh) localStorage.setItem('refresh_token', refresh)
  },
  clear: () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  },
}

// ── Axios instance ────────────────────────────────────────────────────────────
const api = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000,
})

api.interceptors.request.use((config) => {
  const token = tokenStorage.getAccess()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// ── 401 → auto-refresh with bounded queue ────────────────────────────────────
const REFRESH_TIMEOUT_MS = 8_000  // give up if the server doesn't respond in 8 s

let isRefreshing = false
let waitQueue = []

const processQueue = (error, token = null) => {
  waitQueue.forEach((p) => (error ? p.reject(error) : p.resolve(token)))
  waitQueue = []
}

const redirectToLogin = () => {
  tokenStorage.clear()
  window.location.href = '/login'
}

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    if (error.response?.status !== 401 || original._retry) {
      return Promise.reject(error)
    }

    // Queue subsequent 401s while a refresh is in flight
    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        waitQueue.push({ resolve, reject })
      }).then((token) => {
        original.headers.Authorization = `Bearer ${token}`
        return api(original)
      })
    }

    original._retry = true
    isRefreshing = true

    const refresh = tokenStorage.getRefresh()
    if (!refresh) {
      isRefreshing = false
      redirectToLogin()
      return Promise.reject(error)
    }

    try {
      const { data } = await axios.post(
        `${BASE_URL}/api/v1/auth/refresh`,
        { refresh_token: refresh },
        { timeout: REFRESH_TIMEOUT_MS },
      )

      tokenStorage.setTokens(data.access_token, data.refresh_token)
      api.defaults.headers.common.Authorization = `Bearer ${data.access_token}`
      processQueue(null, data.access_token)

      original.headers.Authorization = `Bearer ${data.access_token}`
      return api(original)
    } catch (refreshError) {
      processQueue(refreshError, null)
      redirectToLogin()
      return Promise.reject(refreshError)
    } finally {
      isRefreshing = false
    }
  },
)

export default api

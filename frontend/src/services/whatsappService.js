import api from './api'

export const whatsappService = {
  getStatus: async () => {
    const { data } = await api.get('/whatsapp/status')
    return data
  },

  getSettings: async () => {
    const { data } = await api.get('/whatsapp/settings')
    return data
  },

  updateSettings: async (number) => {
    const { data } = await api.put('/whatsapp/settings', { number })
    return data
  },

  // Sends a report PDF to the server-configured receiver. The receiver number
  // is never chosen here — the backend reads it from its own settings.
  sendReport: async ({ blob, filename, reportType, title, periodLabel, branchId }) => {
    const form = new FormData()
    form.append('file', blob, filename)
    form.append('report_type', reportType)
    form.append('title', (title || '').slice(0, 120))
    form.append('period_label', (periodLabel || '').slice(0, 60))
    if (branchId) form.append('branch_id', branchId)
    const { data } = await api.post('/whatsapp/send-report', form, {
      // The shared axios instance defaults to JSON, which makes axios
      // serialize FormData to JSON. Override it; the browser then sets
      // multipart/form-data with the correct boundary itself.
      headers: { 'Content-Type': 'multipart/form-data' },
      // Long enough to cover OpenWA's send pacing plus the backend's own
      // 30 s gateway timeout.
      timeout: 60000,
    })
    return data
  },
}

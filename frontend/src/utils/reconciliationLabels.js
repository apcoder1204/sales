import SW from '@constants/sw'
import { formatCurrency, formatDate, formatNumber } from '@utils/formatters'

// Shared by the Upatanisho page and the exceptions report export, so the
// screen and the PDF/Excel/WhatsApp copy describe a discrepancy the same way.

export const codeText = (code) => SW.upatanisho.kodi[code] || code

export function recordLabel(e) {
  const parts = [e.customer?.name, e.sale_no, e.payment_no, e.opening_balance_ref]
  if (e.closing) parts.push(`${SW.nav.ufungaji} ${formatDate(e.closing.business_date)} #${e.closing.register_number}`)
  return parts.filter(Boolean).join(' · ') || '—'
}

export const detailText = (e) => (e.detail ? SW.upatanisho.sehemu[e.detail] || e.detail : '')

export function figure(e, value) {
  if (value == null) return '—'
  return e.detail === 'total_sales_count' ? formatNumber(Number(value)) : formatCurrency(Number(value))
}

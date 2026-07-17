import { format, parseISO } from 'date-fns'

export const formatCurrency = (amount) => {
  if (amount === null || amount === undefined) return 'TSh 0'
  return `TSh ${parseInt(amount).toLocaleString('en-US')}`
}

export const formatDate = (dateStr, fmt = 'dd/MM/yyyy') => {
  if (!dateStr) return '-'
  try {
    return format(parseISO(dateStr), fmt)
  } catch {
    return dateStr
  }
}

export const formatDateTime = (dateStr) => {
  return formatDate(dateStr, 'dd/MM/yyyy HH:mm')
}

export const formatDateLong = (dateStr) => {
  return formatDate(dateStr, 'dd MMMM yyyy')
}

export const formatPercent = (value, decimals = 1) => {
  if (value === null || value === undefined) return '0%'
  return `${parseFloat(value).toFixed(decimals)}%`
}

export const formatNumber = (value) => {
  if (value === null || value === undefined) return '0'
  return parseInt(value).toLocaleString('en-US')
}

export const truncate = (str, len = 40) => {
  if (!str) return ''
  return str.length > len ? str.slice(0, len) + '…' : str
}

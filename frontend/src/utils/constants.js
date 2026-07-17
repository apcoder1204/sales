export const PAYMENT_METHODS = [
  { value: 'cash', label: 'Taslimu' },
  { value: 'mobile_money', label: 'Malipo ya Simu' },
  { value: 'bank_transfer', label: 'Benki' },
]

export const TRANSFER_STATUSES = {
  pending: { label: 'Inasubiri', color: 'yellow' },
  approved: { label: 'Imekubaliwa', color: 'blue' },
  rejected: { label: 'Imekataliwa', color: 'red' },
  fulfilled: { label: 'Imetekelezwa', color: 'green' },
  completed: { label: 'Imekamilika', color: 'green' },
}

export const PRODUCT_STATUSES = {
  active: { label: 'Hai', color: 'green' },
  inactive: { label: 'Imesimama', color: 'red' },
}

export const SALE_STATUSES = {
  completed: { label: 'Imekamilika', color: 'green' },
  voided: { label: 'Imefutwa', color: 'red' },
}

export const TX_TYPES = {
  sale: { label: 'Mauzo', color: 'red' },
  transfer_in: { label: 'Uhamisho ndani', color: 'green' },
  transfer_out: { label: 'Uhamisho nje', color: 'yellow' },
  adjustment_in: { label: 'Marekebisho +', color: 'green' },
  adjustment_out: { label: 'Marekebisho -', color: 'red' },
  initial_stock: { label: 'Bidhaa ya Awali', color: 'blue' },
  return: { label: 'Kurudisha', color: 'purple' },
}

export const REPORT_PERIODS = [
  { value: 'today', label: 'Leo' },
  { value: 'week', label: 'Wiki Hii' },
  { value: 'month', label: 'Mwezi Huu' },
  { value: 'custom', label: 'Muda Maalum' },
]

export const LOW_STOCK_THRESHOLD = 5

export const PAGE_SIZES = [10, 25, 50, 100]

export const BRANCH_TYPES = {
  main_store: 'Hifadhi Kuu',
  pos_point: 'Kioski cha POS',
}

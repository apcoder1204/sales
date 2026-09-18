import SW from '@constants/sw'

// These are exported as functions (not pre-built objects/arrays) because SW is a
// live object that LanguageContext repopulates in place on language switch — a
// module-scope constant built from SW.* once at import time would freeze at
// whichever language was active on first load and never update.

export const getPaymentMethods = () => [
  { value: 'cash', label: SW.hali.malipo.cash },
  { value: 'mobile_money', label: SW.hali.malipo.mobile_money },
  { value: 'bank_transfer', label: SW.hali.malipo.bank_transfer },
]

export const getTransferStatuses = () => ({
  pending: { label: SW.hali.uhamisho.pending, color: 'yellow' },
  approved: { label: SW.hali.uhamisho.approved, color: 'blue' },
  rejected: { label: SW.hali.uhamisho.rejected, color: 'red' },
  fulfilled: { label: SW.hali.uhamisho.fulfilled, color: 'green' },
  completed: { label: SW.hali.uhamisho.completed, color: 'green' },
})

export const getProductStatuses = () => ({
  active: { label: SW.hali.bidhaa.active, color: 'green' },
  inactive: { label: SW.hali.bidhaa.inactive, color: 'red' },
})

export const getSaleStatuses = () => ({
  completed: { label: SW.hali.mauzo.completed, color: 'green' },
  voided: { label: SW.hali.mauzo.voided, color: 'red' },
})

export const getTxTypes = () => ({
  sale: { label: SW.hali.harakati.sale, color: 'red' },
  transfer_in: { label: SW.hali.harakati.transfer_in, color: 'green' },
  transfer_out: { label: SW.hali.harakati.transfer_out, color: 'yellow' },
  adjustment_in: { label: SW.hali.harakati.adjustment_in, color: 'green' },
  adjustment_out: { label: SW.hali.harakati.adjustment_out, color: 'red' },
  initial_stock: { label: SW.hali.harakati.initial_stock, color: 'blue' },
  return: { label: SW.hali.harakati.return, color: 'purple' },
})

export const getReportPeriods = () => [
  { value: 'today', label: SW.hali.kipindi.today },
  { value: 'week', label: SW.hali.kipindi.week },
  { value: 'month', label: SW.hali.kipindi.month },
  { value: 'custom', label: SW.hali.kipindi.custom },
]

export const getBranchTypes = () => ({
  main_store: SW.hali.tawi.main_store,
  pos_point: SW.hali.tawi.pos_point,
})

export const LOW_STOCK_THRESHOLD = 5

export const PAGE_SIZES = [10, 25, 50, 100]

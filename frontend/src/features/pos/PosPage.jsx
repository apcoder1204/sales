import React, { useState } from 'react'
import { ShoppingCart, X, TrendingUp, Receipt, ShoppingBag, Clock } from 'lucide-react'
import ProductCatalog from './ProductCatalog'
import Cart from './Cart'
import CheckoutModal from './CheckoutModal'
import ReceiptModal from './ReceiptModal'
import KpiCard from '@components/ui/KpiCard'
import { PaymentBreakdownModal } from '@features/dashboard/DrillDowns'
import { useCart } from '@hooks/useCart'
import { useDashboard } from '@features/dashboard/useDashboard'
import { formatCurrency, formatNumber, formatDateTime } from '@utils/formatters'
import SW from '@constants/sw'

export default function PosPage() {
  const [checkoutOpen, setCheckoutOpen] = useState(false)
  const [receipt, setReceipt] = useState(null)
  const [cartOpen, setCartOpen] = useState(false)
  const [salesTick, setSalesTick] = useState(0)
  const [drillDown, setDrillDown] = useState(null)
  const { itemCount, total } = useCart()
  // Reuses the exact same dashboard_summary data CashierDash shows — this
  // screen isn't a separate reporting surface, it's "today's numbers,
  // right where the cashier is already working" instead of a page away.
  const { data, loading } = useDashboard()

  const handleSaleComplete = (receiptData) => {
    setCheckoutOpen(false)
    setCartOpen(false)
    setReceipt(receiptData)
    setSalesTick((t) => t + 1)
  }

  return (
    <div className="flex flex-col gap-4 h-[calc(100vh-8rem)]">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 flex-shrink-0">
        <KpiCard title={SW.dashibodi.mauzoLeo} value={formatCurrency(data?.today_revenue)} icon={TrendingUp} color="green" loading={loading} onClick={() => setDrillDown('today')} />
        <KpiCard title={SW.dashibodi.muamalaLeo} value={formatNumber(data?.today_transactions)} icon={Receipt} color="blue" loading={loading} />
        <KpiCard title={SW.ripoti.wastaniWaUuzaji} value={formatCurrency(data?.avg_sale_value)} icon={ShoppingBag} color="purple" loading={loading} />
        <KpiCard title={SW.dashibodi.muamalaWaMwisho} value={data?.last_sale_time ? formatDateTime(data.last_sale_time) : '-'} icon={Clock} color="yellow" loading={loading} />
      </div>

      <PaymentBreakdownModal
        open={drillDown === 'today'} onClose={() => setDrillDown(null)}
        title={SW.dashibodi.mauzoLeo} breakdown={data?.today_payment_breakdown} count={data?.today_transactions}
      />

      <div className="flex gap-4 flex-1 min-h-0">
      {/* Catalog — full width on mobile, flex-1 on desktop */}
      <div className="flex-1 min-w-0">
        <ProductCatalog />
      </div>

      {/* Desktop cart sidebar */}
      <div className="hidden md:block w-80 flex-shrink-0">
        <Cart onCheckout={() => setCheckoutOpen(true)} salesTick={salesTick} />
      </div>
      </div>

      {/* Mobile floating cart button */}
      {itemCount > 0 && (
        <button
          onClick={() => setCartOpen(true)}
          className="md:hidden fixed bottom-5 right-4 z-40 flex items-center gap-2 bg-primary text-white px-4 py-3 rounded-2xl shadow-lg active:scale-95 transition-transform"
        >
          <ShoppingCart size={18} />
          <span className="font-semibold text-sm">{SW.bidhaa.idadiBidhaa(itemCount)}</span>
          <span className="font-bold text-sm">· {formatCurrency(total)}</span>
        </button>
      )}

      {/* Mobile cart drawer */}
      {cartOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex flex-col justify-end">
          <div className="absolute inset-0 bg-black/50" onClick={() => setCartOpen(false)} />
          <div className="relative rounded-t-2xl shadow-2xl max-h-[88vh] flex flex-col overflow-hidden">
            <Cart
              onCheckout={() => { setCartOpen(false); setCheckoutOpen(true) }}
              onClose={() => setCartOpen(false)}
              salesTick={salesTick}
            />
          </div>
        </div>
      )}

      <CheckoutModal
        open={checkoutOpen}
        onClose={() => setCheckoutOpen(false)}
        onComplete={handleSaleComplete}
      />

      {receipt && (
        <ReceiptModal
          open={!!receipt}
          receipt={receipt}
          onClose={() => setReceipt(null)}
        />
      )}
    </div>
  )
}

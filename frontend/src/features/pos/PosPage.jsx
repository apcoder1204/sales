import React, { useState } from 'react'
import { ShoppingCart, X } from 'lucide-react'
import ProductCatalog from './ProductCatalog'
import Cart from './Cart'
import CheckoutModal from './CheckoutModal'
import ReceiptModal from './ReceiptModal'
import { useCart } from '@hooks/useCart'
import { formatCurrency } from '@utils/formatters'

export default function PosPage() {
  const [checkoutOpen, setCheckoutOpen] = useState(false)
  const [receipt, setReceipt] = useState(null)
  const [cartOpen, setCartOpen] = useState(false)
  const [salesTick, setSalesTick] = useState(0)
  const { itemCount, total } = useCart()

  const handleSaleComplete = (receiptData) => {
    setCheckoutOpen(false)
    setCartOpen(false)
    setReceipt(receiptData)
    setSalesTick((t) => t + 1)
  }

  return (
    <div className="flex gap-4 h-[calc(100vh-8rem)]">
      {/* Catalog — full width on mobile, flex-1 on desktop */}
      <div className="flex-1 min-w-0">
        <ProductCatalog />
      </div>

      {/* Desktop cart sidebar */}
      <div className="hidden md:block w-80 flex-shrink-0">
        <Cart onCheckout={() => setCheckoutOpen(true)} salesTick={salesTick} />
      </div>

      {/* Mobile floating cart button */}
      {itemCount > 0 && (
        <button
          onClick={() => setCartOpen(true)}
          className="md:hidden fixed bottom-5 right-4 z-40 flex items-center gap-2 bg-primary text-white px-4 py-3 rounded-2xl shadow-lg active:scale-95 transition-transform"
        >
          <ShoppingCart size={18} />
          <span className="font-semibold text-sm">{itemCount} bidhaa</span>
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

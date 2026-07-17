import React from 'react'
import { Minus, Plus, X } from 'lucide-react'
import { useCart } from '@hooks/useCart'
import { formatCurrency } from '@utils/formatters'

export default function CartItem({ item }) {
  const { removeItem, setQty } = useCart()

  return (
    <div className="flex items-center gap-1.5 py-1.5 border-b border-border/50 last:border-0">
      {/* Name + code + unit price */}
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium text-text-primary truncate leading-tight">{item.product_name}</p>
        <p className="text-[10px] text-text-muted leading-tight truncate">{item.product_code}</p>
        <p className="text-[10px] text-text-muted leading-tight">{formatCurrency(item.selling_price)}</p>
      </div>

      {/* Qty stepper */}
      <div className="flex items-center gap-0.5 flex-shrink-0">
        <button
          onClick={() => setQty(item.product_id, item.quantity - 1)}
          className="w-5 h-5 rounded bg-bg-hover hover:bg-bg-panel flex items-center justify-center text-text-secondary hover:text-text-primary transition-colors active:scale-90"
        >
          <Minus size={10} />
        </button>
        <span className="w-6 text-center text-xs font-semibold text-text-primary">{item.quantity}</span>
        <button
          onClick={() => setQty(item.product_id, item.quantity + 1)}
          className="w-5 h-5 rounded bg-bg-hover hover:bg-bg-panel flex items-center justify-center text-text-secondary hover:text-text-primary transition-colors active:scale-90"
        >
          <Plus size={10} />
        </button>
      </div>

      {/* Line total */}
      <div className="text-right flex-shrink-0 w-16">
        <p className="text-xs font-bold text-text-primary">{formatCurrency(item.selling_price * item.quantity)}</p>
      </div>

      {/* Remove */}
      <button
        onClick={() => removeItem(item.product_id)}
        className="text-text-muted hover:text-accent-red transition-colors p-0.5 flex-shrink-0 active:scale-90"
      >
        <X size={12} />
      </button>
    </div>
  )
}

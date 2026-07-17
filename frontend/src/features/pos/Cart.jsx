import React from 'react'
import { ShoppingCart, Trash2, X, Check } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useCart } from '@hooks/useCart'
import Button from '@components/ui/Button'
import Divider from '@components/ui/Divider'
import CartItem from './CartItem'
import TodaySales from './TodaySales'
import { formatCurrency } from '@utils/formatters'
import SW from '@constants/sw'

export default function Cart({ onCheckout, onClose, salesTick }) {
  const { items, clear, subtotal, total, itemCount } = useCart()

  return (
    <div className="glass-card flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-border flex-shrink-0">
        <div className="flex items-center gap-2">
          <ShoppingCart size={16} className="text-primary-light" />
          <span className="font-semibold text-sm text-text-primary">{SW.mauzo.kadiYaUuzaji}</span>
          {itemCount > 0 && (
            <span className="px-1.5 py-0.5 bg-primary text-white text-[10px] rounded-full font-bold">{itemCount}</span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {items.length > 0 && (
            <button onClick={clear} className="text-text-muted hover:text-accent-red transition-colors p-1">
              <Trash2 size={14} />
            </button>
          )}
          {onClose && (
            <button onClick={onClose} className="text-text-muted hover:text-text-primary transition-colors p-1">
              <X size={16} />
            </button>
          )}
        </div>
      </div>

      {/* Items */}
      <div className="flex-1 overflow-y-auto px-3 py-1">
        <AnimatePresence>
          {items.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <ShoppingCart size={40} className="text-text-muted mb-3" />
              <p className="text-sm text-text-muted">{SW.mauzo.tupu}</p>
            </div>
          ) : (
            items.map((item) => (
              <motion.div
                key={item.product_id}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
              >
                <CartItem item={item} />
              </motion.div>
            ))
          )}
        </AnimatePresence>
      </div>

      {/* Summary */}
      {items.length > 0 && (
        <div className="border-t border-border px-3 py-2.5 space-y-1.5 flex-shrink-0">
          <div className="flex justify-between text-xs text-text-secondary">
            <span>{SW.mauzo.jumla}</span>
            <span>{formatCurrency(subtotal)}</span>
          </div>
          <div className="flex justify-between text-xs text-text-secondary">
            <span>{SW.mauzo.punguzo}</span>
            <span>{formatCurrency(0)}</span>
          </div>
          <Divider />
          <div className="flex justify-between font-bold text-sm text-text-primary">
            <span>{SW.mauzo.jumlaKuu}</span>
            <span className="text-accent-green">{formatCurrency(total)}</span>
          </div>
          <div className="flex gap-2 mt-1">
            <Button
              variant="secondary" onClick={clear} leftIcon={<Trash2 size={14} />}
              className="flex-1 !text-accent-red !border-accent-red/30 hover:!bg-accent-red-muted"
            >
              {SW.mauzo.futaKikapu}
            </Button>
            <Button onClick={onCheckout} leftIcon={<Check size={14} />} className="flex-1">
              {SW.mauzo.thibitisha}
            </Button>
          </div>
        </div>
      )}

      <TodaySales refreshKey={salesTick} />
    </div>
  )
}

import React, { useRef } from 'react'
import Modal from '@components/ui/Modal'
import Button from '@components/ui/Button'
import Divider from '@components/ui/Divider'
import { Printer, X } from 'lucide-react'
import { formatCurrency, formatDateTime } from '@utils/formatters'

export default function ReceiptModal({ open, onClose, receipt }) {
  const printRef = useRef(null)

  const handlePrint = () => {
    const content = printRef.current?.innerHTML
    const win = window.open('', '_blank', 'width=400,height=600')
    win.document.write(`
      <html><head><title>Receipt - ${receipt.transaction_no}</title>
      <style>
        body { font-family: monospace; font-size: 12px; margin: 20px; }
        .center { text-align: center; }
        .line { border-top: 1px dashed #000; margin: 8px 0; }
        .row { display: flex; justify-content: space-between; }
        .bold { font-weight: bold; }
      </style></head>
      <body>${content}</body></html>
    `)
    win.document.close()
    win.print()
    win.close()
  }

  if (!receipt) return null

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Receipt"
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} leftIcon={<X size={16} />}>Close</Button>
          <Button onClick={handlePrint} leftIcon={<Printer size={16} />}>Print Receipt</Button>
        </>
      }
    >
      <div ref={printRef} className="font-mono text-xs text-text-primary space-y-2">
        <div className="text-center space-y-1">
          <p className="font-bold text-sm">DUKANI POS</p>
          <p>{receipt.branch_name}</p>
          <p>{formatDateTime(receipt.created_at)}</p>
          <p>Receipt No: {receipt.transaction_no}</p>
        </div>

        <Divider />

        <div className="space-y-1">
          {receipt.items?.map((item, i) => (
            <div key={i}>
              <p>{item.product_name}</p>
              <div className="flex justify-between pl-2">
                <span>{item.quantity} × {formatCurrency(item.unit_price)}</span>
                <span>{formatCurrency(item.line_total)}</span>
              </div>
            </div>
          ))}
        </div>

        <Divider />

        <div className="space-y-1">
          <div className="flex justify-between">
            <span>Subtotal</span><span>{formatCurrency(receipt.subtotal)}</span>
          </div>
          <div className="flex justify-between font-bold text-sm">
            <span>TOTAL</span><span>{formatCurrency(receipt.total_amount)}</span>
          </div>
        </div>

        <Divider />

        <div className="space-y-1">
          <div className="flex justify-between">
            <span>Payment</span><span>{receipt.payment_method?.replace('_', ' ').toUpperCase()}</span>
          </div>
          {receipt.payment_reference && (
            <div className="flex justify-between">
              <span>Ref</span><span>{receipt.payment_reference}</span>
            </div>
          )}
          <div className="flex justify-between">
            <span>Cashier</span><span>{receipt.cashier_name}</span>
          </div>
        </div>

        <Divider />
        <p className="text-center">Thank you for your business!</p>
        <p className="text-center text-xs">Powered by DUKANI POS</p>
      </div>
    </Modal>
  )
}

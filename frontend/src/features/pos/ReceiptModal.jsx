import React, { useRef } from 'react'
import Modal from '@components/ui/Modal'
import Button from '@components/ui/Button'
import Divider from '@components/ui/Divider'
import { Printer, X } from 'lucide-react'
import { formatCurrency } from '@utils/formatters'
import { printHtml } from '@utils/printReceipt'
import SW from '@constants/sw'

// `receipt` is the POST /sales response ({sale, receipt}) or a bare
// ReceiptData (GET /sales/{id}/receipt). The server pre-formats money and
// dates on ReceiptData, so this prints them as given.
export default function ReceiptModal({ open, onClose, receipt: data }) {
  const printRef = useRef(null)
  const receipt = data?.receipt ?? data

  if (!receipt) return null

  const handlePrint = () => printHtml(`${SW.risiti.risiti} - ${receipt.transaction_no}`, printRef.current?.innerHTML)

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={SW.risiti.risiti}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} leftIcon={<X size={16} />}>{SW.risiti.funga}</Button>
          <Button onClick={handlePrint} leftIcon={<Printer size={16} />}>{SW.risiti.chapishaRisiti}</Button>
        </>
      }
    >
      <div ref={printRef} className="font-mono text-xs text-text-primary space-y-2">
        <div className="text-center space-y-1">
          <p className="font-bold text-sm">{SW.appName}</p>
          <p>{receipt.branch_name}</p>
          <p>{receipt.date}</p>
          <p>{SW.risiti.namba}: {receipt.transaction_no}</p>
          {receipt.customer_name && <p>{SW.risiti.mteja}: {receipt.customer_name}</p>}
        </div>

        <Divider className="divider" />

        <div className="space-y-1">
          {receipt.items?.map((item, i) => (
            <div key={item.id || i}>
              <p>{item.product}</p>
              <div className="row flex justify-between pl-2">
                <span>{item.quantity} × {formatCurrency(item.unit_price)}</span>
                <span>{formatCurrency(item.line_total)}</span>
              </div>
            </div>
          ))}
        </div>

        <Divider className="divider" />

        <div className="space-y-1">
          <div className="row flex justify-between">
            <span>{SW.risiti.jumlaNdogo}</span><span>{receipt.subtotal}</span>
          </div>
          <div className="row flex justify-between font-bold text-sm">
            <span>{SW.risiti.jumlaKuu}</span><span>{receipt.total_amount}</span>
          </div>
        </div>

        <Divider className="divider" />

        <div className="space-y-1">
          {(receipt.payments || []).map((p, i) => (
            <div key={i}>
              <div className="row flex justify-between">
                <span>{p.method}</span><span>{p.amount}</span>
              </div>
              {p.reference && (
                <div className="row flex justify-between pl-2">
                  <span>{SW.risiti.kumbukumbu}</span><span>{p.reference}</span>
                </div>
              )}
            </div>
          ))}
          {receipt.paid && (
            <div className="row flex justify-between">
              <span>{SW.risiti.kilicholipwa}</span><span>{receipt.paid}</span>
            </div>
          )}
          {receipt.balance && (
            <div className="row flex justify-between font-bold">
              <span>{SW.risiti.deni}</span><span>{receipt.balance}</span>
            </div>
          )}
          {receipt.due_date && (
            <div className="row flex justify-between">
              <span>{SW.risiti.tareheYaKulipa}</span><span>{receipt.due_date}</span>
            </div>
          )}
          <div className="row flex justify-between">
            <span>{SW.risiti.mhusika}</span><span>{receipt.cashier_name}</span>
          </div>
        </div>

        <Divider className="divider" />
        <p className="text-center">{SW.risiti.asante}</p>
        <p className="text-center text-xs">{SW.risiti.naushindwaNa}</p>
      </div>
    </Modal>
  )
}

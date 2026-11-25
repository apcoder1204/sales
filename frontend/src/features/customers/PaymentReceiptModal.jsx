import React, { useEffect, useRef, useState } from 'react'
import Modal from '@components/ui/Modal'
import Button from '@components/ui/Button'
import Divider from '@components/ui/Divider'
import Spinner from '@components/feedback/Spinner'
import { Printer, X } from 'lucide-react'
import { paymentService } from '@services/paymentService'
import { resolveApiErrorMessage } from '@utils/apiError'
import { printHtml } from '@utils/printReceipt'
import SW from '@constants/sw'

// Debt-payment receipt (brief §12). Always loaded from GET
// /payments/{id}/receipt, so a reprint shows exactly what the server holds
// and has no side effects.
export default function PaymentReceiptModal({ paymentId, open, onClose }) {
  const printRef = useRef(null)
  const [receipt, setReceipt] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!open || !paymentId) return
    setReceipt(null)
    setError(null)
    paymentService.receipt(paymentId).then(setReceipt).catch((e) => setError(resolveApiErrorMessage(e)))
  }, [open, paymentId])

  const row = (label, value) => (
    <div className="row flex justify-between"><span>{label}</span><span>{value}</span></div>
  )

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={SW.risiti.risitiYaMalipo}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} leftIcon={<X size={16} />}>{SW.risiti.funga}</Button>
          <Button
            disabled={!receipt}
            onClick={() => printHtml(`${SW.risiti.risitiYaMalipo} - ${receipt.payment_no}`, printRef.current?.innerHTML)}
            leftIcon={<Printer size={16} />}
          >
            {SW.risiti.chapishaRisiti}
          </Button>
        </>
      }
    >
      {error && <p className="text-sm text-accent-red">{error}</p>}
      {!receipt && !error && <div className="flex justify-center py-6"><Spinner /></div>}
      {receipt && (
        <div ref={printRef} className="font-mono text-xs text-text-primary space-y-2">
          <div className="text-center space-y-1">
            <p className="font-bold text-sm">{receipt.business_name}</p>
            <p>{SW.risiti.risitiYaMalipo}</p>
            <p>{receipt.branch_name}</p>
            <p>{receipt.date}</p>
            <p>{SW.risiti.namba}: {receipt.payment_no}</p>
          </div>
          {receipt.reversed && (
            <p className="banner text-center font-bold border-2 border-accent-red text-accent-red py-1">
              {SW.risiti.imebatilishwa}
            </p>
          )}
          <Divider className="divider" />
          {row(SW.risiti.mteja, receipt.customer_name)}
          {row(SW.risiti.nambaYaMteja, receipt.customer_no)}
          <Divider className="divider" />
          <div className="row flex justify-between font-bold text-sm">
            <span>{SW.risiti.kiasi}</span><span>{receipt.amount}</span>
          </div>
          {row(SW.risiti.njia, receipt.method)}
          {receipt.reference && row(SW.risiti.kumbukumbu, receipt.reference)}
          <Divider className="divider" />
          <p className="font-bold">{SW.risiti.madeniYaliyolipwa}</p>
          {receipt.allocations.map((a, i) => (
            <div key={i} className="row flex justify-between pl-2">
              <span>{a.reference}</span><span>{a.amount}</span>
            </div>
          ))}
          <Divider className="divider" />
          {receipt.balance_before && row(SW.risiti.deniKabla, receipt.balance_before)}
          {receipt.balance_after && (
            <div className="row flex justify-between font-bold">
              <span>{SW.risiti.deniBaada}</span><span>{receipt.balance_after}</span>
            </div>
          )}
          {row(SW.risiti.amepokea, receipt.received_by)}
          <Divider className="divider" />
          <p className="text-center">{SW.risiti.asante}</p>
          <p className="text-center text-xs">{SW.risiti.naushindwaNa}</p>
        </div>
      )}
    </Modal>
  )
}

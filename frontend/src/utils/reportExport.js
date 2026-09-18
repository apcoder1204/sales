import SW from '@constants/sw'

// Brand name is intentionally not localized — same across both languages.
const BRAND = 'DUKANI POS'

function fmt(v) {
  if (v == null) return ''
  if (typeof v === 'number') return v.toLocaleString('en-TZ', { minimumFractionDigits: 0 })
  return String(v)
}

function fmtCurrency(v) {
  if (v == null) return ''
  return `TSh ${Number(v).toLocaleString('en-TZ', { minimumFractionDigits: 0 })}`
}

function timestamp() {
  return new Date().toLocaleString('en-TZ', { dateStyle: 'medium', timeStyle: 'short' })
}

function filename(type, ext, label) {
  const slug = label || new Date().toISOString().slice(0, 10)
  return `${BRAND}_${type}_${slug}.${ext}`
}

function periodLabel(period) {
  if (!period) return ''
  if (/^\d{4}-\d{2}-\d{2}$/.test(period)) return ` — ${period}`
  return ` — ${period.toUpperCase()}`
}

/** Map closing list/history rows into the shape expected by closing export. */
export function toClosingExportData(closings) {
  const rows = (closings || []).map((c) => ({
    business_date: c.business_date,
    branch: c.branch_name || c.branch || '',
    status: c.status,
    total_cash: Number(c.total_cash),
    total_mobile_money: Number(c.total_mobile_money),
    total_bank_transfer: Number(c.total_bank_transfer),
    total_revenue: Number(c.total_revenue),
    cash_variance: c.cash_variance != null ? Number(c.cash_variance) : null,
    total_expenses: Number(c.total_expenses || 0),
    expenses: (c.expenses || []).map((e) => ({
      description: e.description,
      amount: Number(e.amount),
    })),
    closed_by: c.closed_by || null,
  }))

  return {
    summary: {
      total_cash: rows.reduce((sum, c) => sum + c.total_cash, 0),
      total_mobile_money: rows.reduce((sum, c) => sum + c.total_mobile_money, 0),
      total_bank_transfer: rows.reduce((sum, c) => sum + c.total_bank_transfer, 0),
      total_revenue: rows.reduce((sum, c) => sum + c.total_revenue, 0),
      closings_count: rows.length,
    },
    closings: rows,
  }
}

function normalise(type, data, period) {
  const label = periodLabel(period)

  switch (type) {
    case 'sales': {
      const s = data.summary || {}
      return {
        title: `${SW.ripoti.mauzo}${label}`,
        sheets: [
          {
            name: SW.ripoti.muhtasariSheet,
            head: [[SW.ripoti.kipimoSheet, SW.ripoti.thamani]],
            rows: [
              [SW.ripoti.mauzoYote, fmtCurrency(s.total_revenue)],
              [SW.ripoti.idadiYaMuamala, fmt(s.total_transactions)],
              [SW.ripoti.wastaniWaUuzaji, fmtCurrency(s.avg_transaction)],
              [SW.ripoti.bidhaaZilizouzwa, fmt(s.total_items_sold)],
            ],
          },
          {
            name: SW.ripoti.bidhaaBoraSheet,
            head: [[SW.bidhaa.bidhaa, SW.common.idadi, SW.ripoti.mapato]],
            rows: (data.top_products || []).map((p) => [p.product, fmt(p.qty_sold), fmtCurrency(p.revenue)]),
          },
          {
            name: SW.ripoti.njiaZaMalipo,
            head: [[SW.ripoti.njia, SW.common.idadi, SW.common.jumla]],
            rows: (data.payment_breakdown || []).map((p) => [p.method, fmt(p.count), fmtCurrency(p.total)]),
          },
        ],
      }
    }

    case 'inventory': {
      const s = data.summary || {}
      return {
        title: SW.ripoti.hifadhi,
        sheets: [
          {
            name: SW.ripoti.muhtasariSheet,
            head: [[SW.ripoti.kipimoSheet, SW.ripoti.thamani]],
            rows: [
              [SW.ripoti.bidhaaZote, fmt(s.total_products)],
              [SW.ripoti.kiasiChote, fmt(s.total_quantity)],
              [SW.ripoti.thamaniYaInventory, fmtCurrency(s.total_value)],
              [SW.ripoti.bidhaaZaHisaaChini, fmt(s.low_stock_count)],
            ],
          },
          {
            name: SW.ripoti.kwaTawiSheet,
            head: [[SW.ufungaji.tawi, SW.ripoti.kiasi, SW.ripoti.thamani]],
            rows: (data.by_branch || []).map((b) => [b.branch, fmt(b.total_quantity), fmtCurrency(b.total_value)]),
          },
          {
            name: SW.ripoti.hisaaChiniSheet,
            head: [[SW.bidhaa.bidhaa, SW.ripoti.msimbo, SW.ufungaji.tawi, SW.ripoti.kilichobaki, SW.ripoti.kiwangoChiniShort, SW.ripoti.upungufu]],
            rows: (data.low_stock_items || []).map((i) => [
              i.product, i.product_code, i.branch,
              fmt(i.current_stock), fmt(i.minimum_stock), fmt(i.deficit),
            ]),
          },
        ],
      }
    }

    case 'stock_movements': {
      return {
        title: `${SW.hifadhi.harakati}${label}`,
        sheets: [{
          name: SW.hifadhi.harakati,
          head: [[SW.bidhaa.bidhaa, SW.ufungaji.tawi, SW.hifadhi.aina, SW.hifadhi.mabadiliko, SW.ripoti.kiasiKipya, SW.ripoti.aliyefanya, SW.common.tarehe]],
          rows: (data.items || []).map((m) => [
            m.product, m.branch, SW.hali.harakati[m.transaction_type] || m.transaction_type,
            (m.quantity_change > 0 ? '+' : '') + fmt(m.quantity_change),
            fmt(m.quantity_after), m.performed_by || '',
            m.created_at ? new Date(m.created_at).toLocaleString('en-TZ') : '',
          ]),
        }],
      }
    }

    case 'branch_performance':
      return {
        title: `${SW.ripoti.tawi}${label}`,
        sheets: [{
          name: SW.ripoti.matawiSheet,
          head: [[SW.ufungaji.tawi, SW.mauzo.mauzo, SW.ripoti.muamala, SW.ripoti.wastani, SW.ripoti.bidhaaZilizouzwa]],
          rows: (data.branches || []).map((b) => [
            b.branch, fmtCurrency(b.total_revenue), fmt(b.transaction_count),
            fmtCurrency(b.avg_transaction), fmt(b.items_sold),
          ]),
        }],
      }

    case 'cashier_performance':
      return {
        title: `${SW.ripoti.mhusika}${label}`,
        sheets: [{
          name: SW.ripoti.wahusikaSheet,
          head: [[SW.ripoti.mhusikaHeader, SW.ufungaji.tawi, SW.mauzo.mauzo, SW.ripoti.muamala, SW.ripoti.wastani, SW.ripoti.bidhaaZilizouzwa]],
          rows: (data.cashiers || []).map((c) => [
            c.cashier, c.branch, fmtCurrency(c.total_revenue),
            fmt(c.transaction_count), fmtCurrency(c.avg_transaction), fmt(c.items_sold),
          ]),
        }],
      }

    case 'low_stock':
      return {
        title: SW.ripoti.bidhaaZaHisaaChini,
        sheets: [{
          name: SW.ripoti.hisaaChiniSheet,
          head: [[SW.bidhaa.bidhaa, SW.ripoti.msimbo, SW.ufungaji.tawi, SW.ripoti.kilichobaki, SW.ripoti.kiwangoChiniShort, SW.ripoti.upungufu]],
          rows: (data.items || []).map((i) => [
            i.product, i.product_code, i.branch,
            fmt(i.current_stock), fmt(i.minimum_stock), fmt(i.deficit),
          ]),
        }],
      }

    case 'closing': {
      const s = data.summary || {}
      return {
        title: `${SW.ripoti.ufungaji}${label}`,
        sheets: [
          {
            name: SW.ripoti.muhtasariSheet,
            head: [[SW.ripoti.kipimoSheet, SW.ripoti.thamani]],
            rows: [
              [SW.ufungaji.taslimu, fmtCurrency(s.total_cash)],
              [SW.ufungaji.simuLipa, fmtCurrency(s.total_mobile_money)],
              [SW.ufungaji.benki, fmtCurrency(s.total_bank_transfer)],
              [SW.ufungaji.jumlaKuu, fmtCurrency(s.total_revenue)],
              [SW.ripoti.idadiYaUfungaji, fmt(s.closings_count)],
            ],
          },
          {
            name: SW.ufungaji.ufungaji,
            head: [[SW.common.tarehe, SW.ufungaji.tawi, SW.common.hali, SW.ufungaji.taslimu, SW.ripoti.simuShort, SW.ufungaji.benki, SW.common.jumla, SW.ufungaji.tofauti, SW.ufungaji.matumizi, SW.ufungaji.aliyefunga]],
            rows: (data.closings || []).map((c) => [
              c.business_date, c.branch, c.status === 'closed' ? SW.ufungaji.imefungwa : SW.ufungaji.wazi,
              fmtCurrency(c.total_cash), fmtCurrency(c.total_mobile_money), fmtCurrency(c.total_bank_transfer),
              fmtCurrency(c.total_revenue), c.cash_variance != null ? fmtCurrency(c.cash_variance) : '',
              c.total_expenses > 0 ? fmtCurrency(c.total_expenses) : '', c.closed_by || '',
            ]),
          },
          {
            name: SW.ufungaji.matumizi,
            head: [[SW.common.tarehe, SW.ufungaji.tawi, SW.bidhaa.maelezo, SW.ripoti.kiasi]],
            rows: (data.closings || []).flatMap((c) =>
              (c.expenses || []).map((e) => [c.business_date, c.branch, e.description, fmtCurrency(e.amount)])
            ),
          },
        ],
      }
    }

    default:
      return { title: SW.ripoti.ripoti, sheets: [] }
  }
}

// ── PDF — loaded lazily on first call ─────────────────────────────────────────

export async function downloadPDF(type, data, period) {
  const [{ default: jsPDF }, { default: autoTable }] = await Promise.all([
    import('jspdf'),
    import('jspdf-autotable'),
  ])

  const { title, sheets } = normalise(type, data, period)
  const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' })

  const BLUE = [37, 99, 235]
  const LIGHT = [241, 245, 249]

  function drawHeader() {
    doc.setFillColor(...BLUE)
    doc.rect(0, 0, 297, 18, 'F')
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(11)
    doc.setTextColor(255, 255, 255)
    doc.text(BRAND, 10, 11)
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(9)
    doc.text(title, 297 / 2, 11, { align: 'center' })
    doc.text(SW.ripoti.imetolewa(timestamp()), 287, 11, { align: 'right' })
  }

  drawHeader()
  let y = 24

  sheets.forEach((sheet, si) => {
    if (si > 0) {
      doc.addPage()
      drawHeader()
      y = 24
    }

    doc.setFont('helvetica', 'bold')
    doc.setFontSize(9)
    doc.setTextColor(30, 45, 74)
    doc.text(sheet.name.toUpperCase(), 10, y)
    y += 4

    autoTable(doc, {
      startY: y,
      head: sheet.head,
      body: sheet.rows.length ? sheet.rows : [[SW.common.hakuna]],
      theme: 'grid',
      styles: { fontSize: 8, cellPadding: 2.5, textColor: [30, 30, 50] },
      headStyles: { fillColor: BLUE, textColor: [255, 255, 255], fontStyle: 'bold', fontSize: 8 },
      alternateRowStyles: { fillColor: LIGHT },
      margin: { left: 10, right: 10 },
    })
    y = doc.lastAutoTable.finalY + 8
  })

  const pageCount = doc.getNumberOfPages()
  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i)
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(7)
    doc.setTextColor(150, 150, 150)
    doc.text(SW.ripoti.ukurasa(i, pageCount), 297 / 2, 205, { align: 'center' })
  }

  doc.save(filename(type, 'pdf', period))
}

// ── Excel — loaded lazily on first call ──────────────────────────────────────

export async function downloadExcel(type, data, period) {
  const XLSX = await import('xlsx')

  const { title, sheets } = normalise(type, data, period)
  const wb = XLSX.utils.book_new()
  wb.Props = { Title: title, Company: BRAND, CreatedDate: new Date() }

  sheets.forEach((sheet) => {
    const wsData = [
      [title],
      [SW.ripoti.imetolewa(timestamp())],
      [],
      ...sheet.head,
      ...sheet.rows,
    ]
    const ws = XLSX.utils.aoa_to_sheet(wsData)

    const colCount = Math.max(...wsData.map((r) => r.length))
    ws['!cols'] = Array.from({ length: colCount }, (_, ci) => ({
      wch: Math.min(40, Math.max(12, ...wsData.map((r) => String(r[ci] ?? '').length + 2))),
    }))

    XLSX.utils.book_append_sheet(wb, ws, sheet.name.slice(0, 31))
  })

  XLSX.writeFile(wb, filename(type, 'xlsx', period))
}

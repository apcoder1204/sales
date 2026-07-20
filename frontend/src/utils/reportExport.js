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

function filename(type, ext) {
  const d = new Date().toISOString().slice(0, 10)
  return `${BRAND}_${type}_${d}.${ext}`
}

function normalise(type, data, period) {
  const periodLabel = period ? ` — ${period.toUpperCase()}` : ''

  switch (type) {
    case 'sales': {
      const s = data.summary || {}
      return {
        title: `Ripoti ya Mauzo${periodLabel}`,
        sheets: [
          {
            name: 'Muhtasari',
            head: [['Kipimo', 'Thamani']],
            rows: [
              ['Mauzo Yote', fmtCurrency(s.total_revenue)],
              ['Idadi ya Muamala', fmt(s.total_transactions)],
              ['Wastani wa Uuzaji', fmtCurrency(s.avg_transaction)],
              ['Bidhaa Zilizouzwa', fmt(s.total_items_sold)],
            ],
          },
          {
            name: 'Bidhaa Bora',
            head: [['Bidhaa', 'Idadi', 'Mapato']],
            rows: (data.top_products || []).map((p) => [p.product, fmt(p.qty_sold), fmtCurrency(p.revenue)]),
          },
          {
            name: 'Njia za Malipo',
            head: [['Njia', 'Idadi', 'Jumla']],
            rows: (data.payment_breakdown || []).map((p) => [p.method, fmt(p.count), fmtCurrency(p.total)]),
          },
        ],
      }
    }

    case 'inventory': {
      const s = data.summary || {}
      return {
        title: 'Ripoti ya Inventory',
        sheets: [
          {
            name: 'Muhtasari',
            head: [['Kipimo', 'Thamani']],
            rows: [
              ['Bidhaa Zote', fmt(s.total_products)],
              ['Kiasi Chote', fmt(s.total_quantity)],
              ['Thamani ya Inventory', fmtCurrency(s.total_value)],
              ['Bidhaa za Hisaa Chini', fmt(s.low_stock_count)],
            ],
          },
          {
            name: 'Kwa Tawi',
            head: [['Tawi', 'Kiasi', 'Thamani']],
            rows: (data.by_branch || []).map((b) => [b.branch, fmt(b.total_quantity), fmtCurrency(b.total_value)]),
          },
          {
            name: 'Hisaa Chini',
            head: [['Bidhaa', 'Msimbo', 'Tawi', 'Kilichobaki', 'Kiwango Chini', 'Upungufu']],
            rows: (data.low_stock_items || []).map((i) => [
              i.product, i.product_code, i.branch,
              fmt(i.current_stock), fmt(i.minimum_stock), fmt(i.deficit),
            ]),
          },
        ],
      }
    }

    case 'stock_movements': {
      const TX = {
        sale: 'Uuzaji', adjustment: 'Marekebisho',
        transfer_in: 'Uhamisho (Ndani)', transfer_out: 'Uhamisho (Nje)',
        purchase: 'Ununuzi', return: 'Urejesho',
      }
      return {
        title: `Harakati za Bidhaa${periodLabel}`,
        sheets: [{
          name: 'Harakati',
          head: [['Bidhaa', 'Tawi', 'Aina', 'Mabadiliko', 'Kiasi Kipya', 'Aliyefanya', 'Tarehe']],
          rows: (data.items || []).map((m) => [
            m.product, m.branch, TX[m.transaction_type] || m.transaction_type,
            (m.quantity_change > 0 ? '+' : '') + fmt(m.quantity_change),
            fmt(m.quantity_after), m.performed_by || '',
            m.created_at ? new Date(m.created_at).toLocaleString('en-TZ') : '',
          ]),
        }],
      }
    }

    case 'branch_performance':
      return {
        title: `Utendaji wa Matawi${periodLabel}`,
        sheets: [{
          name: 'Matawi',
          head: [['Tawi', 'Mauzo', 'Muamala', 'Wastani', 'Bidhaa Zilizouzwa']],
          rows: (data.branches || []).map((b) => [
            b.branch, fmtCurrency(b.total_revenue), fmt(b.transaction_count),
            fmtCurrency(b.avg_transaction), fmt(b.items_sold),
          ]),
        }],
      }

    case 'cashier_performance':
      return {
        title: `Utendaji wa Wahusika${periodLabel}`,
        sheets: [{
          name: 'Wahusika',
          head: [['Mhusika', 'Tawi', 'Mauzo', 'Muamala', 'Wastani', 'Bidhaa Zilizouzwa']],
          rows: (data.cashiers || []).map((c) => [
            c.cashier, c.branch, fmtCurrency(c.total_revenue),
            fmt(c.transaction_count), fmtCurrency(c.avg_transaction), fmt(c.items_sold),
          ]),
        }],
      }

    case 'low_stock':
      return {
        title: 'Bidhaa za Hisaa Chini',
        sheets: [{
          name: 'Hisaa Chini',
          head: [['Bidhaa', 'Msimbo', 'Tawi', 'Kilichobaki', 'Kiwango Chini', 'Upungufu']],
          rows: (data.items || []).map((i) => [
            i.product, i.product_code, i.branch,
            fmt(i.current_stock), fmt(i.minimum_stock), fmt(i.deficit),
          ]),
        }],
      }

    case 'closing': {
      const s = data.summary || {}
      return {
        title: `Ripoti ya Ufungaji wa Siku${periodLabel}`,
        sheets: [
          {
            name: 'Muhtasari',
            head: [['Kipimo', 'Thamani']],
            rows: [
              ['Taslimu', fmtCurrency(s.total_cash)],
              ['Malipo ya Simu', fmtCurrency(s.total_mobile_money)],
              ['Benki', fmtCurrency(s.total_bank_transfer)],
              ['Jumla Kuu', fmtCurrency(s.total_revenue)],
              ['Idadi ya Ufungaji', fmt(s.closings_count)],
            ],
          },
          {
            name: 'Ufungaji',
            head: [['Tarehe', 'Tawi', 'Hali', 'Taslimu', 'Simu', 'Benki', 'Jumla', 'Tofauti', 'Matumizi', 'Aliyefunga']],
            rows: (data.closings || []).map((c) => [
              c.business_date, c.branch, c.status === 'closed' ? 'Imefungwa' : 'Wazi',
              fmtCurrency(c.total_cash), fmtCurrency(c.total_mobile_money), fmtCurrency(c.total_bank_transfer),
              fmtCurrency(c.total_revenue), c.cash_variance != null ? fmtCurrency(c.cash_variance) : '',
              c.total_expenses > 0 ? fmtCurrency(c.total_expenses) : '', c.closed_by || '',
            ]),
          },
          {
            name: 'Matumizi',
            head: [['Tarehe', 'Tawi', 'Maelezo', 'Kiasi']],
            rows: (data.closings || []).flatMap((c) =>
              (c.expenses || []).map((e) => [c.business_date, c.branch, e.description, fmtCurrency(e.amount)])
            ),
          },
        ],
      }
    }

    default:
      return { title: 'Ripoti', sheets: [] }
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
    doc.text(`Imetolewa: ${timestamp()}`, 287, 11, { align: 'right' })
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
      body: sheet.rows.length ? sheet.rows : [['Hakuna data']],
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
    doc.text(`Ukurasa ${i} / ${pageCount}`, 297 / 2, 205, { align: 'center' })
  }

  doc.save(filename(type, 'pdf'))
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
      [`Imetolewa: ${timestamp()}`],
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

  XLSX.writeFile(wb, filename(type, 'xlsx'))
}

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
    total_credit_given: Number(c.total_credit_given || 0),
    total_debt_collected: Number(c.total_debt_collected || 0),
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
      total_credit_given: rows.reduce((sum, c) => sum + c.total_credit_given, 0),
      total_debt_collected: rows.reduce((sum, c) => sum + c.total_debt_collected, 0),
      closings_count: rows.length,
    },
    closings: rows,
  }
}

/** The title and sheets a report exports as — exported so screens can show
 *  exactly the figures the PDF/Excel will carry (DebtReportView). */
export function normaliseReport(type, data, period) {
  return normalise(type, data, period)
}

function normalise(type, data, period) {
  const label = periodLabel(period)

  switch (type) {
    // ── Debt reports (brief §29) — one summary sheet plus the rows ──
    case 'debt_outstanding': {
      const R = SW.ripotiMadeni
      const s = data.summary || {}
      return {
        title: R.outstanding,
        sheets: [
          { name: SW.ripoti.muhtasariSheet, head: [[SW.ripoti.kipimoSheet, SW.ripoti.thamani]], rows: [
            [R.jumlaYaMadeni, fmtCurrency(s.total_balance)],
            [R.yaliyochelewa, fmtCurrency(s.total_overdue)],
            [R.idadiWateja, fmt(s.customers)],
          ] },
          { name: R.wateja, head: [[SW.wateja.mteja, SW.wateja.simu, R.salio, R.yaliyochelewa, R.kikomo, R.malipoYaMwisho, R.viashiria]],
            rows: (data.rows || []).map((r) => [
              `${r.customer.name} (${r.customer.customer_no})`, r.customer.phone, fmtCurrency(r.balance),
              fmtCurrency(r.overdue), fmtCurrency(r.credit_limit), r.last_payment_at ? r.last_payment_at.slice(0, 10) : '-',
              (r.flags || []).map((f) => SW.hatari[f] || f).join(', '),
            ]) },
        ],
      }
    }

    case 'debt_overdue': {
      const R = SW.ripotiMadeni
      const s = data.summary || {}
      return {
        title: R.overdue,
        sheets: [
          { name: SW.ripoti.muhtasariSheet, head: [[SW.ripoti.kipimoSheet, SW.ripoti.thamani]], rows: [
            [R.jumlaYaMadeni, fmtCurrency(s.total)], [R.idadi, fmt(s.count)],
          ] },
          { name: R.madeni, head: [[SW.wateja.mteja, SW.wateja.tawi, SW.wateja.kumbukumbu, SW.wateja.tareheYaKulipa, R.sikuZilizochelewa, R.salio]],
            rows: (data.rows || []).map((r) => [
              r.customer.name, r.branch_name, r.reference, r.due_date, fmt(r.days_overdue), fmtCurrency(r.outstanding),
            ]) },
        ],
      }
    }

    case 'debt_ageing': {
      const R = SW.ripotiMadeni
      const B = ['not_due', '1_30', '31_60', '61_90', '90_plus']
      const head = [B.map((b) => SW.madeni.umri[b]).concat(SW.madeni.jumlaFupi)]
      return {
        title: R.ageing,
        sheets: [
          { name: SW.ripoti.muhtasariSheet, head: [[SW.ripoti.kipimoSheet, SW.ripoti.thamani]],
            rows: B.map((b) => [SW.madeni.umri[b], fmtCurrency(data.totals?.[b])]).concat([[SW.madeni.jumlaFupi, fmtCurrency(data.total)]]) },
          { name: R.wateja, head: [[SW.wateja.mteja, ...head[0]]],
            rows: (data.rows || []).map((r) => [r.customer.name, ...B.map((b) => fmtCurrency(r.buckets[b])), fmtCurrency(r.total)]) },
          { name: R.matawi, head: [[SW.wateja.tawi, ...head[0]]],
            rows: (data.by_branch || []).map((r) => [r.branch_name, ...B.map((b) => fmtCurrency(r.buckets[b])), fmtCurrency(r.total)]) },
        ],
      }
    }

    case 'debt_collections': {
      const R = SW.ripotiMadeni
      const s = data.summary || {}
      return {
        title: `${R.collections}${label}`,
        sheets: [
          { name: SW.ripoti.muhtasariSheet, head: [[SW.ripoti.kipimoSheet, SW.ripoti.thamani]], rows: [
            [R.jumlaIliyokusanywa, fmtCurrency(s.total)], [R.idadi, fmt(s.count)],
            ...Object.entries(s.by_method || {}).map(([m, v]) => [SW.hali.malipo[m] || m, fmtCurrency(v)]),
          ] },
          { name: R.malipo, head: [[SW.wateja.namba, SW.wateja.tarehe, SW.wateja.mteja, SW.wateja.tawi, SW.wateja.njia, SW.wateja.kiasi, SW.wateja.aliyepokea]],
            rows: (data.rows || []).map((r) => [
              r.payment_no, r.business_date, r.customer.name, r.branch_name, SW.hali.malipo[r.method] || r.method,
              fmtCurrency(r.amount), r.received_by,
            ]) },
        ],
      }
    }

    case 'debt_branches': {
      const R = SW.ripotiMadeni
      const s = data.summary || {}
      return {
        title: `${R.branches}${label}`,
        sheets: [
          { name: SW.ripoti.muhtasariSheet, head: [[SW.ripoti.kipimoSheet, SW.ripoti.thamani]], rows: [
            [R.jumlaYaMadeni, fmtCurrency(s.outstanding)], [R.yaliyochelewa, fmtCurrency(s.overdue)],
            [R.idadiWateja, fmt(s.customers_owing)], [R.jumlaIliyokusanywa, fmtCurrency(s.collected_in_period)],
          ] },
          { name: R.matawi, head: [[SW.wateja.tawi, R.salio, R.yaliyochelewa, R.idadiWateja, R.jumlaIliyokusanywa]],
            rows: (data.rows || []).map((r) => [
              r.branch_name, fmtCurrency(r.outstanding), fmtCurrency(r.overdue), fmt(r.customers_owing), fmtCurrency(r.collected_in_period),
            ]) },
        ],
      }
    }

    case 'debt_credit_utilization': {
      const R = SW.ripotiMadeni
      const s = data.summary || {}
      return {
        title: R.creditUtilization,
        sheets: [
          { name: SW.ripoti.muhtasariSheet, head: [[SW.ripoti.kipimoSheet, SW.ripoti.thamani]], rows: [
            [SW.hatari.OVER_LIMIT, fmt(s.customers_over_limit)], [SW.hatari.NEAR_LIMIT, fmt(s.customers_near_limit)],
          ] },
          { name: R.wateja, head: [[SW.wateja.mteja, R.kikomo, R.salio, R.asilimiaIliyotumika, R.inayopatikana, R.viashiria]],
            rows: (data.rows || []).map((r) => [
              r.customer.name, fmtCurrency(r.credit_limit), fmtCurrency(r.balance),
              r.used_pct == null ? '-' : `${Number(r.used_pct).toLocaleString('en-TZ', { maximumFractionDigits: 1 })}%`,
              fmtCurrency(r.available), (r.flags || []).map((f) => SW.hatari[f] || f).join(', '),
            ]) },
        ],
      }
    }

    case 'debt_opening_balances': {
      const R = SW.ripotiMadeni
      const s = data.summary || {}
      return {
        title: R.openingBalances,
        sheets: [
          { name: SW.ripoti.muhtasariSheet, head: [[SW.wateja.hali, R.idadi, SW.wateja.kiasi]],
            rows: Object.entries(s).map(([k, v]) => [SW.hali.aliyeingizaHali[k] || k, fmt(v.count), fmtCurrency(v.amount)]) },
          { name: R.madeni, head: [[SW.wateja.mteja, SW.wateja.tawi, SW.wateja.kiasi, SW.madeniYaZamani.tareheYaDeni, SW.wateja.kumbukumbu, SW.wateja.hali, SW.madeniYaZamani.aliyeingiza, SW.madeniYaZamani.aliyeamua]],
            rows: (data.rows || []).map((r) => [
              r.customer.name, r.branch_name, fmtCurrency(r.amount), r.effective_date, r.reference,
              SW.hali.aliyeingizaHali[r.status] || r.status, r.entered_by_name, r.decided_by_name || '-',
            ]) },
        ],
      }
    }

    case 'customer_statement': {
      const c = data.customer || {}
      const T = SW.taarifa
      return {
        title: `${T.kichwa} — ${c.name}${label}`,
        sheets: [
          {
            name: SW.ripoti.muhtasariSheet,
            head: [[SW.ripoti.kipimoSheet, SW.ripoti.thamani]],
            rows: [
              [SW.wateja.mteja, `${c.name} (${c.customer_no})`],
              [SW.wateja.simu, c.phone],
              [T.kipindi, `${data.date_from} – ${data.date_to}`],
              [T.salioLaKuanzia, fmtCurrency(data.opening_balance)],
              [T.debiti, fmtCurrency(data.total_debit)],
              [T.krediti, fmtCurrency(data.total_credit)],
              [T.salioLaMwisho, fmtCurrency(data.closing_balance)],
            ],
          },
          {
            name: T.miamala,
            head: [[SW.wateja.tarehe, SW.wateja.kumbukumbu, T.maelezo, SW.wateja.tawi, T.debiti, T.krediti, T.salio]],
            rows: [
              [data.date_from, '', T.salioLaKuanzia, '', '', '', fmtCurrency(data.opening_balance)],
              ...(data.lines || []).map((l) => [
                l.date, l.reference, l.description, l.branch_name,
                Number(l.debit) ? fmtCurrency(l.debit) : '', Number(l.credit) ? fmtCurrency(l.credit) : '',
                fmtCurrency(l.balance),
              ]),
              [data.date_to, '', T.salioLaMwisho, '', fmtCurrency(data.total_debit), fmtCurrency(data.total_credit), fmtCurrency(data.closing_balance)],
            ],
          },
        ],
      }
    }

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

    case 'inventory_valuation':
      return {
        title: SW.ripoti.thamaniYaInventory,
        sheets: [{
          name: SW.ripoti.thamaniYaInventory,
          head: [[SW.ufungaji.tawi, SW.bidhaa.bidhaa, SW.hifadhi.bichiBidhaa, SW.hifadhi.thamani]],
          rows: (data || []).map((r) => [
            r.branch_name, fmt(r.product_count), fmt(r.total_quantity), r.total_value,
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
              [SW.wateja.mkopoUliotolewa, fmtCurrency(s.total_credit_given || 0)],
              [SW.wateja.madeniYaliyolipwa, fmtCurrency(s.total_debt_collected || 0)],
              [SW.ripoti.idadiYaUfungaji, fmt(s.closings_count)],
            ],
          },
          {
            name: SW.ufungaji.ufungaji,
            head: [[SW.common.tarehe, SW.ufungaji.tawi, SW.common.hali, SW.ufungaji.taslimu, SW.ripoti.simuShort, SW.ufungaji.benki, SW.common.jumla, SW.wateja.mkopoUliotolewa, SW.wateja.madeniYaliyolipwa, SW.ufungaji.tofauti, SW.ufungaji.matumizi, SW.ufungaji.aliyefunga]],
            rows: (data.closings || []).map((c) => [
              c.business_date, c.branch, c.status === 'closed' ? SW.ufungaji.imefungwa : SW.ufungaji.wazi,
              fmtCurrency(c.total_cash), fmtCurrency(c.total_mobile_money), fmtCurrency(c.total_bank_transfer),
              fmtCurrency(c.total_revenue), fmtCurrency(c.total_credit_given || 0), fmtCurrency(c.total_debt_collected || 0),
              c.cash_variance != null ? fmtCurrency(c.cash_variance) : '',
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

    case 'profit_loss': {
      const s = data.summary || {}
      const pct = (v) => (v == null ? '—' : `${Number(v).toFixed(1)}%`)
      const statusLabel = (v) => (v === 'profit' ? SW.ripoti.faida.faida : v === 'loss' ? SW.ripoti.faida.hasara : SW.ripoti.faida.kutokaKuathiriana)
      return {
        title: `${SW.ripoti.faida.jina}${label}`,
        sheets: [
          {
            name: SW.ripoti.muhtasariSheet,
            head: [[SW.ripoti.kipimoSheet, SW.ripoti.thamani]],
            rows: [
              [SW.ripoti.mapato, fmtCurrency(s.revenue)],
              [SW.ripoti.faida.gharamaMauzo, fmtCurrency(s.cost_of_goods_sold)],
              [SW.ripoti.faida.faidaGhalisi, fmtCurrency(s.gross_profit)],
              [SW.ripoti.faida.faidaGhalisiAsilimia, pct(s.gross_margin)],
              [SW.ripoti.faida.gharamaZaUendeshaji, fmtCurrency(s.operating_expenses)],
              [SW.ripoti.faida.faidaHalisi, fmtCurrency(s.net_profit)],
              [SW.ripoti.faida.faidaHalisiAsilimia, pct(s.net_margin)],
              [SW.common.hali, statusLabel(s.status)],
            ],
          },
          {
            name: SW.ripoti.faida.faidaKwaTawi,
            head: [[SW.ufungaji.tawi, SW.ripoti.mapato, SW.ripoti.faida.gharamaMauzo, SW.ripoti.faida.faidaGhalisi, SW.ripoti.faida.gharamaZaUendeshaji, SW.ripoti.faida.faidaHalisi, SW.ripoti.faida.faidaHalisiAsilimia, SW.common.hali]],
            rows: (data.branches || []).map((b) => [
              b.branch, fmtCurrency(b.revenue), fmtCurrency(b.cost_of_goods_sold), fmtCurrency(b.gross_profit),
              fmtCurrency(b.operating_expenses), fmtCurrency(b.net_profit), pct(b.net_margin), statusLabel(b.status),
            ]),
          },
          {
            name: SW.ripoti.faida.bidhaaZenyeFaidaKubwa,
            head: [[SW.bidhaa.bidhaa, SW.ripoti.faida.idadiIliyouzwaHeader, SW.ripoti.mapato, SW.ripoti.faida.gharamaMauzo, SW.ripoti.faida.faidaGhalisi, SW.ripoti.faida.faidaGhalisiAsilimia]],
            rows: (data.products || []).map((p) => [
              p.product, fmt(p.quantity_sold), fmtCurrency(p.revenue), fmtCurrency(p.cost_of_goods_sold),
              fmtCurrency(p.gross_profit), pct(p.gross_margin),
            ]),
          },
          {
            name: SW.ripoti.faida.faidaKwaJamii,
            head: [[SW.bidhaa.jamii, SW.ripoti.mapato, SW.ripoti.faida.gharamaMauzo, SW.ripoti.faida.faidaGhalisi, SW.ripoti.faida.faidaGhalisiAsilimia]],
            rows: (data.categories || []).map((c) => [
              c.category, fmtCurrency(c.revenue), fmtCurrency(c.cost_of_goods_sold), fmtCurrency(c.gross_profit), pct(c.gross_margin),
            ]),
          },
        ],
      }
    }

    default:
      return { title: SW.ripoti.ripoti, sheets: [] }
  }
}

// ── PDF — loaded lazily on first call ─────────────────────────────────────────

/**
 * Build the report PDF in memory. Returns the Blob plus metadata used both
 * for downloading and for sending to WhatsApp (same document either way).
 */
export async function buildPDF(type, data, period) {
  const [{ default: jsPDF }, { default: autoTable }] = await Promise.all([
    import('jspdf'),
    import('jspdf-autotable'),
  ])

  const { title, sheets } = normalise(type, data, period)
  // compress: report tables are text-heavy; uncompressed output easily
  // passes nginx's default 1 MB request limit when sent to WhatsApp.
  const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4', compress: true })

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

  return {
    blob: doc.output('blob'),
    filename: filename(type, 'pdf', period),
    title,
    // The report period when it is a concrete date (closings); callers with a
    // named period (today/week/custom range) pass their own label.
    periodLabel: /^\d{4}-\d{2}-\d{2}$/.test(period || '') ? period : '',
  }
}

export async function downloadPDF(type, data, period) {
  const { blob, filename: name } = await buildPDF(type, data, period)
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
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

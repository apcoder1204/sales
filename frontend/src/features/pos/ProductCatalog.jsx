import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { clsx } from 'clsx'
import { Plus, Camera, Router, Cable, ShieldCheck, Fence, Package } from 'lucide-react'
import SearchInput from '@components/ui/SearchInput'
import { useCart } from '@hooks/useCart'
import { useToast } from '@hooks/useToast'
import { useAuth } from '@hooks/useAuth'
import { useBranch } from '@hooks/useBranch'
import { productService } from '@services/productService'
import { useDebounce } from '@hooks/useDebounce'
import { formatCurrency } from '@utils/formatters'
import { isGlobalRole } from '@utils/permissions'
import SW from '@constants/sw'

const GRID_CLASSES = 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4'
const EMPTY_COL_SPAN = 'col-span-1 sm:col-span-2 lg:col-span-3 xl:col-span-4'

// There's no product-photo feature in this app (no image upload/storage
// anywhere in the schema) — rather than fabricate fake product photos to
// match a mockup, each card gets a category-appropriate icon instead, kept
// honestly generic. Matched by substring against the real category name,
// which is free text set by whoever created the category (confirmed real
// values include things like "cctv camera", "Network Video Recorder",
// "CABLE", "Poles", "Energizer" — not a clean fixed vocabulary).
const CATEGORY_ICONS = [
  [/camera|cctv/i, Camera],
  [/nvr|network|router|switch/i, Router],
  [/cable|wire/i, Cable],
  [/alarm|energiz|security|access/i, ShieldCheck],
  [/pole|fence/i, Fence],
]
function iconForCategory(name) {
  return CATEGORY_ICONS.find(([re]) => re.test(name || ''))?.[1] || Package
}

export default function ProductCatalog() {
  const [products, setProducts] = useState([])
  const [categories, setCategories] = useState([])
  const [categoryId, setCategoryId] = useState('')
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebounce(search)
  const { addItem, items } = useCart()
  const toast = useToast()
  const { user } = useAuth()
  const { activeBranchId } = useBranch()

  // Branch-scoped roles always see their own branch's stock. Global roles
  // follow the shared branch-context selector — a specific branch selected
  // there filters stock badges to it; "All Branches" (null) shows the
  // catalog unfiltered, same as before this was wired up.
  const branchId = !isGlobalRole(user) ? user?.branch_id : activeBranchId

  const cartQty = (id) => items.find((i) => i.product_id === id)?.quantity || 0

  useEffect(() => {
    productService.categories().then(setCategories).catch(() => {})
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await productService.list({
        search: debouncedSearch || undefined,
        category_id: categoryId || undefined,
        status: 'active',
        per_page: 50,
        branch_id: branchId || undefined,
      })
      setProducts(res.items || res)
    } finally {
      setLoading(false)
    }
  }, [debouncedSearch, categoryId, branchId])

  useEffect(() => { load() }, [load])

  const CATEGORY_TABS = useMemo(() => [
    { id: '', name: SW.hifadhi.bidhaaZote },
    ...categories.map((c) => ({ id: c.id, name: c.name })),
  ], [categories])

  const handleAdd = (product) => {
    addItem({
      product_id: product.id,
      product_name: product.name,
      product_code: product.product_code,
      selling_price: product.selling_price,
      cost_price: product.cost_price,
    })
    toast.success(SW.mauzo.imeongezwaKwenyeKikapu(product.name))
  }

  return (
    <div className="flex flex-col h-full">
      <div className="mb-3">
        <SearchInput value={search} onChange={setSearch} placeholder={SW.bidhaa.tafutaPlaceholder} />
      </div>

      {categories.length > 0 && (
        <div className="flex gap-2 mb-4 overflow-x-auto pb-1 -mx-1 px-1">
          {CATEGORY_TABS.map((c) => (
            <button
              key={c.id}
              onClick={() => setCategoryId(c.id)}
              className={clsx(
                'flex-shrink-0 px-3.5 py-1.5 rounded-lg text-sm font-medium transition-colors whitespace-nowrap',
                categoryId === c.id
                  ? 'bg-primary text-white'
                  : 'bg-bg-panel border border-border text-text-secondary hover:text-text-primary hover:border-border-light'
              )}
            >
              {c.name}
            </button>
          ))}
        </div>
      )}

      {loading ? (
        <div className={GRID_CLASSES}>
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="glass-card p-4 h-36 animate-pulse bg-bg-hover rounded-xl" />
          ))}
        </div>
      ) : (
        <div className={clsx(GRID_CLASSES, 'overflow-y-auto flex-1 pb-24 md:pb-0 content-start')}>
          {products.map((p) => {
            const qty = cartQty(p.id)
            const outOfStock = p.available_qty != null && p.available_qty <= 0
            const lowStock = !outOfStock && p.is_low_stock
            const CategoryIcon = iconForCategory(p.category)

            return (
              <button
                key={p.id}
                onClick={() => handleAdd(p)}
                className={clsx(
                  'glass-card p-4 text-left hover:border-primary/40 hover:bg-bg-hover transition-all duration-150 relative active:scale-[0.98] rounded-xl flex flex-col',
                  qty > 0 && 'border-primary/40 bg-primary/5'
                )}
              >
                {qty > 0 && (
                  <div className="absolute -top-2 -left-2 flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full bg-primary text-white text-[11px] font-bold leading-none shadow">
                    {qty}
                  </div>
                )}
                {p.available_qty != null && (
                  <span
                    className={clsx(
                      'absolute top-3 right-3 px-2 py-0.5 rounded-full text-[11px] font-semibold leading-none',
                      outOfStock ? 'bg-accent-red-muted text-accent-red'
                        : lowStock ? 'bg-accent-yellow-muted text-accent-yellow'
                        : 'bg-accent-green-muted text-accent-green'
                    )}
                  >
                    {outOfStock ? SW.mauzo.hisaImeisha : SW.mauzo.vipandeCount(p.available_qty)}
                  </span>
                )}

                <div className="w-11 h-11 rounded-lg bg-primary-muted flex items-center justify-center mb-2.5 flex-shrink-0">
                  <CategoryIcon size={20} className="text-primary-light" />
                </div>

                <p className="text-base font-semibold text-text-primary pr-16 leading-tight">{p.name}</p>
                <p className="text-xs text-text-muted mt-0.5">{p.product_code}</p>
                <p className="text-xl font-bold text-text-primary mt-2">{formatCurrency(p.selling_price)}</p>

                <div className="mt-auto pt-3 flex items-end justify-between gap-2">
                  <div className="text-xs text-text-muted leading-tight min-w-0">
                    <p className="truncate">{p.category}</p>
                    {p.brand && <p className="uppercase truncate">{p.brand}</p>}
                  </div>
                  <span className="flex-shrink-0 inline-flex items-center gap-1 bg-primary text-white text-xs font-semibold px-3 py-1.5 rounded-lg">
                    <Plus size={13} /> {SW.common.ongeza}
                  </span>
                </div>
              </button>
            )
          })}
          {products.length === 0 && (
            <div className={clsx(EMPTY_COL_SPAN, 'text-center py-16 text-text-muted')}>
              {SW.mauzo.tupu}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

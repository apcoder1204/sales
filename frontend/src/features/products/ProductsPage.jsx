import React, { useState, useEffect, useCallback } from 'react'
import { Plus, Activity } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import PageWrapper from '@components/layout/PageWrapper'
import Button from '@components/ui/Button'
import SearchInput from '@components/ui/SearchInput'
import Select from '@components/ui/Select'
import ProductTable from './ProductTable'
import ProductFormModal from './ProductFormModal'
import InventoryGrid from '../inventory/InventoryGrid'
import StockAdjustModal from '../inventory/StockAdjustModal'
import SendToPosModal from '../inventory/SendToPosModal'
import { productService } from '@services/productService'
import { inventoryService } from '@services/inventoryService'
import { userService } from '@services/userService'
import { usePermission } from '@hooks/usePermission'
import { useAuth } from '@hooks/useAuth'
import { useDebounce } from '@hooks/useDebounce'
import { usePagination } from '@hooks/usePagination'
import SW from '@constants/sw'

const TABS = [
  { key: 'bidhaa', label: 'Bidhaa' },
  { key: 'hifadhi', label: 'Inventory' },
]

export default function ProductsPage() {
  const { can } = usePermission()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('bidhaa')

  // Products state
  const [products, setProducts] = useState([])
  const [loadingProducts, setLoadingProducts] = useState(true)
  const [productSearch, setProductSearch] = useState('')
  const debouncedProductSearch = useDebounce(productSearch)
  const productPagination = usePagination()
  const [modalOpen, setModalOpen] = useState(false)
  const [editingProduct, setEditingProduct] = useState(null)

  // Inventory state
  const [inventoryItems, setInventoryItems] = useState([])
  const [loadingInventory, setLoadingInventory] = useState(true)
  const [inventorySearch, setInventorySearch] = useState('')
  const debouncedInventorySearch = useDebounce(inventorySearch)
  const inventoryPagination = usePagination()
  const [adjustItem, setAdjustItem] = useState(null)
  const [sendItem, setSendItem] = useState(null)
  const [branches, setBranches] = useState([])
  const [branchFilter, setBranchFilter] = useState('')

  const canFilterBranch = ['super_admin', 'admin', 'general_manager'].includes(user?.role)

  useEffect(() => {
    if (canFilterBranch) {
      userService.branches().then(setBranches).catch(() => {})
    }
  }, [canFilterBranch])

  const loadProducts = useCallback(async () => {
    setLoadingProducts(true)
    try {
      const res = await productService.list({
        search: debouncedProductSearch || undefined,
        ...productPagination.params,
      })
      setProducts(res.items || res)
      if (res.total !== undefined) productPagination.setTotal(res.total)
    } finally {
      setLoadingProducts(false)
    }
  }, [debouncedProductSearch, productPagination.page, productPagination.pageSize])

  const loadInventory = useCallback(async () => {
    setLoadingInventory(true)
    try {
      const res = await inventoryService.list({
        search: debouncedInventorySearch || undefined,
        branch_id: branchFilter || undefined,
        ...inventoryPagination.params,
      })
      // Backend returns ProductWithInventory objects with nested inventory[].
      // InventoryGrid expects flat records: one row per product+branch.
      const products = res.items || res
      const flat = products.flatMap((p) =>
        (p.inventory && p.inventory.length > 0)
          ? p.inventory.map((stock) => ({
              product_id: p.id,
              product_name: p.name,
              product_code: p.product_code,
              cost_price: p.cost_price,
              selling_price: p.selling_price,
              branch_type: stock.branch_type || null,
              ...stock,
            }))
          : [{
              product_id: p.id,
              product_name: p.name,
              product_code: p.product_code,
              cost_price: p.cost_price,
              selling_price: p.selling_price,
              branch_id: null,
              branch_name: '—',
              branch_type: null,
              quantity: 0,
              reserved_qty: 0,
              available_qty: 0,
              is_low_stock: true,
            }]
      )
      setInventoryItems(flat)
      if (res.total !== undefined) inventoryPagination.setTotal(res.total)
    } finally {
      setLoadingInventory(false)
    }
  }, [debouncedInventorySearch, branchFilter, inventoryPagination.page])

  useEffect(() => { loadProducts() }, [loadProducts])
  useEffect(() => { loadInventory() }, [loadInventory])

  const openAdd = () => { setEditingProduct(null); setModalOpen(true) }
  const openEdit = (p) => { setEditingProduct(p); setModalOpen(true) }

  const search = activeTab === 'bidhaa' ? productSearch : inventorySearch
  const setSearch = activeTab === 'bidhaa' ? setProductSearch : setInventorySearch

  return (
    <PageWrapper
      title={SW.nav.orodhaYaBidhaa}
      subtitle="Dhibiti bidhaa na hifadhi ya duka"
      action={
        <div className="flex gap-2">
          <Button
            variant="secondary"
            onClick={() => navigate('/hifadhi/harakati')}
            leftIcon={<Activity size={16} />}
          >
            Harakati
          </Button>
          {can('products.write') && (
            <Button onClick={openAdd} leftIcon={<Plus size={16} />}>
              {SW.bidhaa.kuongezaBidhaa}
            </Button>
          )}
        </div>
      }
    >
      {/* Tabs */}
      <div className="flex border-b border-border gap-1 -mt-2 mb-1">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              activeTab === t.key
                ? 'border-primary text-primary-light'
                : 'border-transparent text-text-muted hover:text-text-secondary'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex gap-3 flex-wrap">
        <SearchInput
          value={search}
          onChange={setSearch}
          className="max-w-xs"
          placeholder="Tafuta bidhaa..."
        />
        {activeTab === 'hifadhi' && canFilterBranch && (
          <Select
            value={branchFilter}
            onChange={(e) => { setBranchFilter(e.target.value); inventoryPagination.reset() }}
            options={[
              { value: '', label: 'Matawi Yote' },
              ...branches.map((b) => ({ value: b.id, label: b.name })),
            ]}
            containerClassName="w-48"
          />
        )}
      </div>

      {activeTab === 'bidhaa' ? (
        <ProductTable
          products={products}
          loading={loadingProducts}
          onEdit={can('products.write') ? openEdit : null}
          onRefresh={loadProducts}
          pagination={{ ...productPagination }}
        />
      ) : (
        <InventoryGrid
          items={inventoryItems}
          loading={loadingInventory}
          onAdjust={can('inventory.adjust') ? setAdjustItem : null}
          onSend={can('transfers.execute') ? setSendItem : null}
          pagination={inventoryPagination}
        />
      )}

      <ProductFormModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSaved={loadProducts}
        product={editingProduct}
      />

      {adjustItem && (
        <StockAdjustModal
          open={!!adjustItem}
          item={adjustItem}
          onClose={() => setAdjustItem(null)}
          onSaved={() => { setAdjustItem(null); loadInventory() }}
        />
      )}

      {sendItem && (
        <SendToPosModal
          open={!!sendItem}
          item={sendItem}
          onClose={() => setSendItem(null)}
          onSaved={() => { setSendItem(null); loadInventory() }}
        />
      )}
    </PageWrapper>
  )
}

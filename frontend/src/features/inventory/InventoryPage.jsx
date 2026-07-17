import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Activity, PlusCircle } from 'lucide-react'
import PageWrapper from '@components/layout/PageWrapper'
import Button from '@components/ui/Button'
import SearchInput from '@components/ui/SearchInput'
import InventoryGrid from './InventoryGrid'
import StockAdjustModal from './StockAdjustModal'
import { inventoryService } from '@services/inventoryService'
import { usePermission } from '@hooks/usePermission'
import { useDebounce } from '@hooks/useDebounce'
import { usePagination } from '@hooks/usePagination'
import SW from '@constants/sw'

export default function InventoryPage() {
  const { can } = usePermission()
  const navigate = useNavigate()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [adjustItem, setAdjustItem] = useState(null)
  const debouncedSearch = useDebounce(search)
  const pagination = usePagination()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await inventoryService.list({
        search: debouncedSearch || undefined,
        ...pagination.params,
      })
      setItems(res.items || res)
      if (res.total !== undefined) pagination.setTotal(res.total)
    } finally {
      setLoading(false)
    }
  }, [debouncedSearch, pagination.page])

  useEffect(() => { load() }, [load])

  return (
    <PageWrapper
      title={SW.nav.hifadhi}
      subtitle="Hali ya bidhaa katika matawi yote"
      action={
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => navigate('/hifadhi/harakati')} leftIcon={<Activity size={16} />}>
            Harakati
          </Button>
        </div>
      }
    >
      <SearchInput value={search} onChange={setSearch} className="max-w-xs" placeholder="Tafuta bidhaa..." />

      <InventoryGrid
        items={items}
        loading={loading}
        onAdjust={can('inventory.adjust') ? setAdjustItem : null}
        pagination={pagination}
      />

      {adjustItem && (
        <StockAdjustModal
          open={!!adjustItem}
          item={adjustItem}
          onClose={() => setAdjustItem(null)}
          onSaved={() => { setAdjustItem(null); load() }}
        />
      )}
    </PageWrapper>
  )
}

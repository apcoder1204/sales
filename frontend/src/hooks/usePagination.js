import { useState, useCallback } from 'react'

export function usePagination(defaultSize = 25) {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(defaultSize)
  const [total, setTotal] = useState(0)

  const totalPages = Math.ceil(total / pageSize)

  const reset = useCallback(() => setPage(1), [])

  return {
    page,
    pageSize,
    total,
    totalPages,
    setPage,
    setPageSize,
    setTotal,
    reset,
    offset: (page - 1) * pageSize,
    params: { page, page_size: pageSize },
  }
}

/**
 * 图书检索页（UC-003）—— 所有角色可见。
 *
 * 读者在「无可借副本」时可发起预约（BR-020）；
 * 馆员/管理员可额外看到馆藏管理提示。
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Alert,
  Badge,
  Button,
  Card,
  Empty,
  Input,
  Modal,
  ReadonlyField,
  Select,
  Skeleton,
} from '@/components/ui'
import { IconBook, IconChevronLeft, IconChevronRight, IconSearch } from '@/components/icons'
import { useToast } from '@/components/Toast'
import { queryApi, reservationApi } from '@/api/endpoints'
import { toMessage } from '@/api/client'
import { ITEM_TYPES, labelOf } from '@/api/types'
import type { BookListItem } from '@/api/types'
import { useAuth } from '@/auth/AuthContext'

const PAGE_SIZE = 12

export function CatalogPage() {
  const toast = useToast()
  const { account } = useAuth()

  const [keyword, setKeyword] = useState('')
  const [itemType, setItemType] = useState('')
  const [availableOnly, setAvailableOnly] = useState(false)
  const [page, setPage] = useState(1)

  /** 关键词 300ms 防抖，避免每敲一个字符就请求一次 */
  const [debouncedKeyword, setDebouncedKeyword] = useState('')
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedKeyword(keyword), 300)
    return () => clearTimeout(timer)
  }, [keyword])

  const [items, setItems] = useState<BookListItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [target, setTarget] = useState<BookListItem | null>(null)
  const [reserving, setReserving] = useState(false)

  /** 请求序号守卫：慢的旧响应不允许覆盖新结果 */
  const seqRef = useRef(0)

  const load = useCallback(async () => {
    const seq = ++seqRef.current
    setLoading(true)
    setError(null)
    try {
      const data = await queryApi.searchBooks({
        keyword: debouncedKeyword.trim() || undefined,
        item_type: itemType || undefined,
        available_only: availableOnly || undefined,
        page,
        page_size: PAGE_SIZE,
      })
      if (seq !== seqRef.current) return
      setItems(data.items)
      setTotal(data.total)
    } catch (err) {
      if (seq !== seqRef.current) return
      setError(toMessage(err))
      setItems([])
      setTotal(0)
    } finally {
      if (seq === seqRef.current) setLoading(false)
    }
  }, [debouncedKeyword, itemType, availableOnly, page])

  useEffect(() => {
    void load()
  }, [load])

  // 条件变化时回到第一页
  useEffect(() => {
    setPage(1)
  }, [debouncedKeyword, itemType, availableOnly])

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const handleReserve = async () => {
    if (!target) return
    setReserving(true)
    try {
      const result = await reservationApi.create(target.title_id)
      toast.success('预约成功', `排队位置：第 ${result.queue_position} 位`)
      setTarget(null)
    } catch (err) {
      toast.fromError(err, '预约失败')
    } finally {
      setReserving(false)
    }
  }

  return (
    <div className="page">
      {error && (
        <Alert tone="danger" title="加载失败">
          {error}
        </Alert>
      )}

      <Card title="馆藏检索" subtitle={`共 ${total} 条题录`}>
        <div className="toolbar">
          <div className="toolbar__search">
            <span className="toolbar__search-icon">
              <IconSearch size={16} />
            </span>
            <Input
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="搜索书名、作者或 ISBN…"
            />
          </div>

          <div style={{ width: 160 }}>
            <Select
              value={itemType}
              onChange={(e) => setItemType(e.target.value)}
              options={ITEM_TYPES}
              placeholder="全部类型"
            />
          </div>

          <label className="row" style={{ gap: 'var(--space-2)', cursor: 'pointer', fontSize: 13 }}>
            <input
              type="checkbox"
              checked={availableOnly}
              onChange={(e) => setAvailableOnly(e.target.checked)}
              style={{ width: 16, height: 16, accentColor: 'var(--brand-600)' }}
            />
            仅看可借
          </label>

          <Button onClick={() => void load()} loading={loading}>
            刷新
          </Button>
        </div>
      </Card>

      {loading ? (
        <div className="book-grid">
          {Array.from({ length: 8 }).map((_, i) => (
            <div className="book-card" key={i}>
              <Skeleton height={18} width="70%" />
              <Skeleton height={13} width="45%" />
              <Skeleton height={13} width="60%" />
              <Skeleton height={30} width="100%" />
            </div>
          ))}
        </div>
      ) : items.length === 0 ? (
        <Card flush>
          <Empty
            title="没有找到匹配的图书"
            desc="试试更换关键词，或取消「仅看可借」筛选条件。"
          />
        </Card>
      ) : (
        <div className="book-grid">
          {items.map((book) => {
            const available = book.available_items > 0
            return (
              <article className="book-card" key={book.title_id}>
                <div className="row" style={{ gap: 'var(--space-2)', alignItems: 'flex-start' }}>
                  <span
                    style={{
                      color: 'var(--brand-500)',
                      flexShrink: 0,
                      marginTop: 2,
                    }}
                  >
                    <IconBook size={18} />
                  </span>
                  <h3 className="book-card__title">{book.title}</h3>
                </div>

                <div className="book-card__meta">
                  {book.author && <span>{book.author}</span>}
                  {book.publisher && (
                    <span>
                      {book.publisher}
                      {book.publish_year ? ` · ${book.publish_year}` : ''}
                    </span>
                  )}
                  {book.isbn && <span className="mono">ISBN {book.isbn}</span>}
                </div>

                <div className="row" style={{ gap: 'var(--space-2)', flexWrap: 'wrap' }}>
                  {book.item_type && <Badge tone="neutral">{labelOf(ITEM_TYPES, book.item_type)}</Badge>}
                  <Badge tone="brand">馆藏 {book.total_items}</Badge>
                </div>

                <div className="book-card__footer">
                  <span className="availability">
                    <span
                      className="availability__dot"
                      style={{
                        background: available ? 'var(--success-500)' : 'var(--danger-500)',
                      }}
                    />
                    {available ? `可借 ${book.available_items} 册` : '暂无可借副本'}
                  </span>

                  {!available && account?.role === 'READER' && (
                    <Button size="sm" variant="primary" onClick={() => setTarget(book)}>
                      预约
                    </Button>
                  )}
                  {available && <Badge tone="success">可借</Badge>}
                </div>
              </article>
            )
          })}
        </div>
      )}

      {!loading && total > PAGE_SIZE && (
        <div className="pagination" style={{ borderTop: 'none', padding: 0 }}>
          <span>
            第 {page} / {totalPages} 页
          </span>
          <div className="pagination__controls">
            <Button
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              icon={<IconChevronLeft size={16} />}
            >
              上一页
            </Button>
            <Button
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              下一页
              <IconChevronRight size={16} />
            </Button>
          </div>
        </div>
      )}

      <Modal
        open={target !== null}
        title="预约图书"
        desc="仅当该题录下所有副本均不可借时才可预约"
        onClose={() => setTarget(null)}
        footer={
          <>
            <Button onClick={() => setTarget(null)}>取消</Button>
            <Button variant="primary" loading={reserving} onClick={() => void handleReserve()}>
              确认预约
            </Button>
          </>
        }
      >
        {target && (
          <div className="stack">
            <ReadonlyField label="书名" value={target.title} />
            {target.author && <ReadonlyField label="作者" value={target.author} />}
            <div className="grid-2" style={{ gap: 'var(--space-4)' }}>
              <ReadonlyField label="馆藏总量" value={`${target.total_items} 册`} />
              <ReadonlyField label="可借数量" value={`${target.available_items} 册`} />
            </div>
            <Alert tone="info">
              预约有效期为 7 天；队列上限 5 人。副本归还后将自动为你预留，请在有效期内到馆借取。
            </Alert>
          </div>
        )}
      </Modal>
    </div>
  )
}

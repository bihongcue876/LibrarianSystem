/**
 * 书目与馆藏管理（UC-208~212）—— 仅系统管理员。
 *
 * **关于副本明细的重要说明**：
 * 后端目前只暴露了「新增副本」「删除副本」「标记状态」三个**按 item_id 操作**的端点，
 * 未提供「按题录列出全部副本」的查询端点（`14-api-spec.md` §4 未定义）。
 * 仓储层虽已有 `find_items_by_title`，但没有对外的 HTTP 接口。
 *
 * 因此本页面的做法是：如实呈现现有能力，通过**条码查询 → 定位副本**完成操作，
 * 而不是伪造一个明细列表。若需补齐该端点，属后端规格变更，应在规格中先行定义。
 */

import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Badge,
  Button,
  Card,
  Empty,
  Field,
  Input,
  Modal,
  ReadonlyField,
  Select,
  TableSkeleton,
} from '@/components/ui'
import { IconPlus, IconSearch, IconTrash } from '@/components/icons'
import { useToast } from '@/components/Toast'
import { catalogApi, queryApi } from '@/api/endpoints'
import { toMessage } from '@/api/client'
import { ITEM_STATUS, ITEM_TYPES, labelOf } from '@/api/types'
import type { BookListItem, BookTitle, LibraryItem } from '@/api/types'

/** 可手动标记的状态（BORROWED / RESERVED 由流通流程驱动，不允许手工设置） */
const MARKABLE_STATUS = ITEM_STATUS.filter((s) => ['AVAILABLE', 'LOST', 'DAMAGED'].includes(s.value))

const EMPTY_TITLE_FORM = {
  title: '',
  author: '',
  isbn: '',
  publisher: '',
  publish_year: '',
  item_type: 'CHINESE_BOOK',
  language: 'ZH',
}

export function AdminCatalogPage() {
  const toast = useToast()

  // 题录列表
  const [keyword, setKeyword] = useState('')
  const [titles, setTitles] = useState<BookListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // 新增题录
  const [titleModal, setTitleModal] = useState(false)
  const [titleForm, setTitleForm] = useState(EMPTY_TITLE_FORM)
  const [savingTitle, setSavingTitle] = useState(false)

  // 删除题录
  const [deleteTitleTarget, setDeleteTitleTarget] = useState<BookListItem | null>(null)

  const [reloadFlag, setReloadFlag] = useState(0)
  const reload = () => setReloadFlag((n) => n + 1)

  const loadTitles = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await queryApi.searchBooks({
        keyword: keyword.trim() || undefined,
        page: 1,
        page_size: 100,
      })
      setTitles(data.items)
    } catch (err) {
      setError(toMessage(err))
    } finally {
      setLoading(false)
    }
  }, [keyword])

  useEffect(() => {
    void loadTitles()
  }, [loadTitles, reloadFlag])

  const createTitle = async () => {
    if (!titleForm.title.trim()) {
      toast.error('书名必填')
      return
    }
    setSavingTitle(true)
    try {
      const created: BookTitle = await catalogApi.addBookTitle({
        title: titleForm.title.trim(),
        author: titleForm.author.trim(),
        isbn: titleForm.isbn.trim() || null,
        publisher: titleForm.publisher.trim() || null,
        publish_year: titleForm.publish_year ? Number(titleForm.publish_year) : null,
        item_type: titleForm.item_type,
        language: titleForm.language.trim() || null,
      })
      toast.success('题录已创建', `《${created.title}》，接下来可为它添加馆藏副本`)
      setTitleModal(false)
      setTitleForm(EMPTY_TITLE_FORM)
      reload()
    } catch (err) {
      toast.fromError(err, '创建题录失败')
    } finally {
      setSavingTitle(false)
    }
  }

  const removeTitle = async () => {
    if (!deleteTitleTarget) return
    try {
      await catalogApi.deleteBookTitle(deleteTitleTarget.title_id)
      toast.success('题录已删除', `《${deleteTitleTarget.title}》及其副本已置为下架`)
      setDeleteTitleTarget(null)
      reload()
    } catch (err) {
      toast.fromError(err, '删除失败')
    }
  }

  return (
    <div className="page">
      {error && (
        <Alert tone="danger" title="加载失败">
          {error}
        </Alert>
      )}

      <Card
        title="题录管理"
        subtitle="题录可先于副本创建；ISBN 仅对活跃题录查重"
        actions={
          <Button
            variant="primary"
            size="sm"
            icon={<IconPlus size={15} />}
            onClick={() => setTitleModal(true)}
          >
            新增题录
          </Button>
        }
        flush
      >
        <div style={{ padding: 'var(--space-5) var(--space-6)' }}>
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
            <Button size="sm" onClick={() => void loadTitles()} loading={loading}>
              刷新
            </Button>
          </div>
        </div>

        {loading ? (
          <TableSkeleton rows={5} cols={5} />
        ) : titles.length === 0 ? (
          <Empty
            title="暂无题录"
            desc="点击「新增题录」录入第一本书，之后再为其添加馆藏副本。"
          />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>书名</th>
                  <th>作者</th>
                  <th>ISBN</th>
                  <th>类型</th>
                  <th>馆藏 / 可借</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {titles.map((t) => (
                  <tr key={t.title_id}>
                    <td style={{ fontWeight: 550 }}>{t.title}</td>
                    <td className="muted">{t.author || '-'}</td>
                    <td className="mono muted">{t.isbn || '-'}</td>
                    <td>
                      <Badge tone="neutral">{labelOf(ITEM_TYPES, t.item_type)}</Badge>
                    </td>
                    <td>
                      <span>{t.total_items}</span>
                      <span className="muted"> / </span>
                      <span
                        style={{
                          color:
                            t.available_items > 0 ? 'var(--success-600)' : 'var(--text-tertiary)',
                          fontWeight: 500,
                        }}
                      >
                        {t.available_items}
                      </span>
                    </td>
                    <td>
                      <div className="table__actions">
                        <Button
                          size="sm"
                          variant="danger-ghost"
                          icon={<IconTrash size={14} />}
                          onClick={() => setDeleteTitleTarget(t)}
                        >
                          删除
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <ItemPanel titles={titles} reloadFlag={reloadFlag} onChanged={reload} />

      {/* 新增题录 */}
      <Modal
        open={titleModal}
        title="新增题录"
        desc="ISBN 为选填；相同 ISBN 的活跃题录会被拒绝"
        onClose={() => setTitleModal(false)}
        wide
        footer={
          <>
            <Button onClick={() => setTitleModal(false)}>取消</Button>
            <Button variant="primary" loading={savingTitle} onClick={() => void createTitle()}>
              创建
            </Button>
          </>
        }
      >
        <div className="stack">
          <Field label="书名" required>
            <Input
              value={titleForm.title}
              onChange={(e) => setTitleForm({ ...titleForm, title: e.target.value })}
              placeholder="如 设计模式"
            />
          </Field>

          <div className="grid-2" style={{ gap: 'var(--space-4)' }}>
            <Field label="作者">
              <Input
                value={titleForm.author}
                onChange={(e) => setTitleForm({ ...titleForm, author: e.target.value })}
                placeholder="如 GoF"
              />
            </Field>
            <Field label="ISBN" hint="选填，用于查重">
              <Input
                value={titleForm.isbn}
                onChange={(e) => setTitleForm({ ...titleForm, isbn: e.target.value })}
                placeholder="9787111128069"
                className="mono"
                maxLength={20}
              />
            </Field>
          </div>

          <div className="grid-2" style={{ gap: 'var(--space-4)' }}>
            <Field label="出版社">
              <Input
                value={titleForm.publisher}
                onChange={(e) => setTitleForm({ ...titleForm, publisher: e.target.value })}
                placeholder="如 机械工业出版社"
              />
            </Field>
            <Field label="出版年份" hint="1000 ~ 2100">
              <Input
                type="number"
                min={1000}
                max={2100}
                value={titleForm.publish_year}
                onChange={(e) => setTitleForm({ ...titleForm, publish_year: e.target.value })}
                placeholder="2004"
              />
            </Field>
          </div>

          <div className="grid-2" style={{ gap: 'var(--space-4)' }}>
            <Field label="文献类型" required hint="决定超期罚款单价">
              <Select
                value={titleForm.item_type}
                onChange={(e) => setTitleForm({ ...titleForm, item_type: e.target.value })}
                options={ITEM_TYPES}
              />
            </Field>
            <Field label="语种">
              <Input
                value={titleForm.language}
                onChange={(e) => setTitleForm({ ...titleForm, language: e.target.value })}
                placeholder="ZH / EN"
              />
            </Field>
          </div>
        </div>
      </Modal>

      {/* 删除题录 */}
      <Modal
        open={deleteTitleTarget !== null}
        title="确认删除题录"
        onClose={() => setDeleteTitleTarget(null)}
        footer={
          <>
            <Button onClick={() => setDeleteTitleTarget(null)}>取消</Button>
            <Button variant="danger" onClick={() => void removeTitle()}>
              确认删除
            </Button>
          </>
        }
      >
        {deleteTitleTarget && (
          <div className="stack">
            <ReadonlyField label="书名" value={deleteTitleTarget.title} />
            <Alert tone="warning" title="软删除，不影响已借出的副本">
              该题录及其副本将置为「已下架」，不再出现在检索结果中。
              若存在未归还的副本，删除<b>不会失败</b>——该副本保持「已借出」，
              待归还后再置为「已下架」（FR-011 验收 3/4）。
            </Alert>
          </div>
        )}
      </Modal>
    </div>
  )
}

/**
 * 馆藏副本操作面板。
 *
 * 因后端未提供「按题录列副本」的查询端点，此处采用**条码精确查询 → 操作**的流程：
 * `GET /api/borrow-cards/{card_no}` 是借阅证查询，副本查询则通过新增后回显的 item_id、
 * 或从读者借阅记录中的条码定位。这样虽然多一步，但每一步都对应真实可用的接口。
 */
function ItemPanel({
  titles,
  reloadFlag,
  onChanged,
}: {
  titles: BookListItem[]
  reloadFlag: number
  onChanged: () => void
}) {
  const toast = useToast()

  const [titleId, setTitleId] = useState('')
  const [itemModal, setItemModal] = useState(false)
  const [itemForm, setItemForm] = useState({ location: '', price: '', acquired_at: '' })
  const [savingItem, setSavingItem] = useState(false)
  const [createdItem, setCreatedItem] = useState<LibraryItem | null>(null)

  // 按条码/编号定位副本
  const [lookupId, setLookupId] = useState('')
  const [statusTarget, setStatusTarget] = useState<{ itemId: number; status: string } | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null)
  const [acting, setActing] = useState(false)

  useEffect(() => {
    setCreatedItem(null)
  }, [reloadFlag])

  const createItem = async () => {
    const tid = Number(titleId)
    if (!Number.isInteger(tid) || tid <= 0) {
      toast.error('题录编号无效', '请先在上方表格中选定题录，或直接填写其编号')
      return
    }
    setSavingItem(true)
    try {
      const created = await catalogApi.addLibraryItem({
        title_id: tid,
        location: itemForm.location.trim() || null,
        price: itemForm.price.trim() || null,
        acquired_at: itemForm.acquired_at || null,
      })
      setCreatedItem(created)
      setItemModal(false)
      setItemForm({ location: '', price: '', acquired_at: '' })
      toast.success('副本已入库', `条码 ${created.barcode}（内部编号 #${created.item_id}）`)
      onChanged()
    } catch (err) {
      toast.fromError(err, '新增副本失败')
    } finally {
      setSavingItem(false)
    }
  }

  const markStatus = async () => {
    if (!statusTarget) return
    setActing(true)
    try {
      await catalogApi.markItemStatus(statusTarget.itemId, statusTarget.status)
      toast.success('状态已更新', `副本 #${statusTarget.itemId}`)
      setStatusTarget(null)
      onChanged()
    } catch (err) {
      toast.fromError(err, '状态更新失败')
    } finally {
      setActing(false)
    }
  }

  const removeItem = async () => {
    if (deleteTarget === null) return
    setActing(true)
    try {
      await catalogApi.deleteLibraryItem(deleteTarget)
      toast.success('副本已下架', `副本 #${deleteTarget}`)
      setDeleteTarget(null)
      onChanged()
    } catch (err) {
      toast.fromError(err, '下架失败')
    } finally {
      setActing(false)
    }
  }

  return (
    <>
      <div className="grid-2">
        <Card title="新增馆藏副本" subtitle="为已有题录添加一册副本，条码自动生成">
          <div className="stack">
            <Field
              label="题录编号"
              required
              hint={
                titles.length > 0
                  ? '可从上方表格的「馆藏」列查看，或在文献列表中确认'
                  : '请先创建题录'
              }
            >
              <Input
                type="number"
                min={1}
                value={titleId}
                onChange={(e) => setTitleId(e.target.value)}
                placeholder="如 1"
                className="mono"
              />
            </Field>

            {titles.length > 0 && (
              <div className="stack stack--sm">
                <span className="muted" style={{ fontSize: 12 }}>
                  快速选择：
                </span>
                <div className="row" style={{ flexWrap: 'wrap', gap: 'var(--space-2)' }}>
                  {titles.slice(0, 6).map((t) => (
                    <button
                      key={t.title_id}
                      className={`badge badge--${String(t.title_id) === titleId ? 'brand' : 'neutral'}`}
                      style={{ cursor: 'pointer', height: 24 }}
                      onClick={() => setTitleId(String(t.title_id))}
                      title={`题录 #${t.title_id}`}
                    >
                      #{t.title_id} {t.title.length > 10 ? `${t.title.slice(0, 10)}…` : t.title}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <Button
              variant="primary"
              block
              icon={<IconPlus size={16} />}
              disabled={!titleId}
              onClick={() => setItemModal(true)}
            >
              填写副本信息
            </Button>

            {createdItem && (
              <Alert tone="success" title="最近入库的副本">
                <div className="stack stack--sm" style={{ marginTop: 'var(--space-2)' }}>
                  <span>
                    条码 <span className="mono">{createdItem.barcode}</span>
                  </span>
                  <span>
                    内部编号 <span className="mono">#{createdItem.item_id}</span>
                  </span>
                  <span className="muted" style={{ fontSize: 12 }}>
                    可用下方「副本操作」按该编号标记状态或下架。
                  </span>
                </div>
              </Alert>
            )}
          </div>
        </Card>

        <Card title="副本操作" subtitle="按内部编号标记状态或下架">
          <div className="stack">
            <Field
              label="馆藏内部编号"
              required
              hint="新增副本成功后会返回该编号；也可从读者借阅记录中查得"
            >
              <Input
                type="number"
                min={1}
                value={lookupId}
                onChange={(e) => setLookupId(e.target.value)}
                placeholder="如 1"
                className="mono"
              />
            </Field>

            <Field label="目标状态" hint="「已借出」「已预留」由流通流程驱动，不可手工设置">
              <Select
                value={statusTarget?.status ?? 'AVAILABLE'}
                onChange={(e) =>
                  setStatusTarget({ itemId: Number(lookupId), status: e.target.value })
                }
                options={MARKABLE_STATUS}
                disabled={!lookupId}
              />
            </Field>

            <div className="row" style={{ gap: 'var(--space-3)' }}>
              <Button
                block
                disabled={!lookupId}
                icon={<IconSearch size={15} />}
                onClick={() => setStatusTarget({ itemId: Number(lookupId), status: 'AVAILABLE' })}
              >
                标记状态
              </Button>
              <Button
                block
                variant="danger-ghost"
                disabled={!lookupId}
                icon={<IconTrash size={15} />}
                onClick={() => setDeleteTarget(Number(lookupId))}
              >
                下架副本
              </Button>
            </div>

            <Alert tone="info">
              下架为软删除。若该副本当前处于「已借出」状态，后端会拒绝删除
              （FR-013 验收 4），请先办理归还。
            </Alert>
          </div>
        </Card>
      </div>

      {/* 新增副本 */}
      <Modal
        open={itemModal}
        title="新增馆藏副本"
        desc={`为题录 #${titleId} 添加一册副本`}
        onClose={() => setItemModal(false)}
        footer={
          <>
            <Button onClick={() => setItemModal(false)}>取消</Button>
            <Button variant="primary" loading={savingItem} onClick={() => void createItem()}>
              入库
            </Button>
          </>
        }
      >
        <div className="stack">
          <Alert tone="info">
            条码由系统自动生成（<span className="mono">BC</span> 加 8 位数字），初始状态为「可借」。
          </Alert>

          <div className="grid-2" style={{ gap: 'var(--space-4)' }}>
            <Field label="存放位置">
              <Input
                value={itemForm.location}
                onChange={(e) => setItemForm({ ...itemForm, location: e.target.value })}
                placeholder="如 A-01 书架"
              />
            </Field>
            <Field label="价格" hint="定点小数，如 59.00">
              <Input
                value={itemForm.price}
                onChange={(e) => setItemForm({ ...itemForm, price: e.target.value })}
                placeholder="59.00"
                className="mono"
              />
            </Field>
          </div>

          <Field label="入藏日期" hint="留空则使用当前日期">
            <Input
              type="date"
              value={itemForm.acquired_at}
              onChange={(e) => setItemForm({ ...itemForm, acquired_at: e.target.value })}
            />
          </Field>
        </div>
      </Modal>

      {/* 状态标记 */}
      <Modal
        open={statusTarget !== null}
        title="标记副本状态"
        onClose={() => setStatusTarget(null)}
        footer={
          <>
            <Button onClick={() => setStatusTarget(null)}>取消</Button>
            <Button variant="primary" loading={acting} onClick={() => void markStatus()}>
              确认标记
            </Button>
          </>
        }
      >
        {statusTarget && (
          <div className="stack">
            <ReadonlyField
              label="副本内部编号"
              value={<span className="mono">#{statusTarget.itemId}</span>}
            />
            <ReadonlyField
              label="目标状态"
              value={labelOf(ITEM_STATUS, statusTarget.status)}
            />
          </div>
        )}
      </Modal>

      {/* 下架副本 */}
      <Modal
        open={deleteTarget !== null}
        title="确认下架副本"
        onClose={() => setDeleteTarget(null)}
        footer={
          <>
            <Button onClick={() => setDeleteTarget(null)}>取消</Button>
            <Button variant="danger" loading={acting} onClick={() => void removeItem()}>
              确认下架
            </Button>
          </>
        }
      >
        {deleteTarget !== null && (
          <div className="stack">
            <ReadonlyField
              label="副本内部编号"
              value={<span className="mono">#{deleteTarget}</span>}
            />
            <Alert tone="warning" title="下架为软删除">
              副本状态将变为「已下架」，不再出现在检索结果中。
            </Alert>
          </div>
        )}
      </Modal>
    </>
  )
}

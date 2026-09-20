/**
 * 罚款收缴页（UC-104）—— 馆员与系统管理员。
 *
 * 系统不接入在线支付（BR-031），此处只做「线下收款后在系统中标记已缴」。
 * 罚款记录需先按读者编号查询，故复用 `/api/readers/{id}/loans` 的 fines 段。
 */

import { useState } from 'react'
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
  StatTile,
} from '@/components/ui'
import { IconMoney, IconSearch } from '@/components/icons'
import { useToast } from '@/components/Toast'
import { circulationApi, loanApi } from '@/api/endpoints'
import { toMessage } from '@/api/client'
import type { FineEntry } from '@/api/types'
import { formatDateTime, formatMoney } from '@/utils/format'

export function FinesPage() {
  const toast = useToast()
  const [readerId, setReaderId] = useState('')
  const [readerName, setReaderName] = useState<string | null>(null)
  const [fines, setFines] = useState<FineEntry[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [target, setTarget] = useState<FineEntry | null>(null)
  const [collecting, setCollecting] = useState(false)

  const search = async () => {
    const id = Number(readerId.trim())
    if (!Number.isInteger(id) || id <= 0) {
      setError('请输入有效的读者编号（正整数）')
      return
    }
    setLoading(true)
    setError(null)
    setFines(null)
    setReaderName(null)
    try {
      const data = await loanApi.readerLoans(id)
      setFines(data.fines)
      setReaderName(data.reader.name)
    } catch (err) {
      setError(toMessage(err))
    } finally {
      setLoading(false)
    }
  }

  const collect = async () => {
    if (!target) return
    setCollecting(true)
    try {
      await circulationApi.collectFine(target.fine_id)
      toast.success('罚款已标记为已缴', `罚款编号 #${target.fine_id}`)
      setTarget(null)
      await search()
    } catch (err) {
      toast.fromError(err, '收缴失败')
    } finally {
      setCollecting(false)
    }
  }

  const unpaid = fines?.filter((f) => f.status === 'UNPAID') ?? []
  const paid = fines?.filter((f) => f.status === 'PAID') ?? []
  const unpaidTotal = unpaid.reduce((sum, f) => sum + Number(f.amount), 0)

  return (
    <div className="page">
      <Card title="查询读者罚款" subtitle="输入读者编号后查看罚款记录并办理收缴">
        <div className="toolbar">
          <div style={{ width: 220 }}>
            <Field label="读者编号">
              <Input
                type="number"
                min={1}
                value={readerId}
                onChange={(e) => setReaderId(e.target.value)}
                placeholder="如 1"
                className="mono"
                onKeyDown={(e) => {
                  if (e.key === 'Enter') void search()
                }}
              />
            </Field>
          </div>
          <Button
            variant="primary"
            style={{ marginTop: 22 }}
            loading={loading}
            onClick={() => void search()}
            icon={<IconSearch size={16} />}
          >
            查询
          </Button>
        </div>
      </Card>

      {error && (
        <Alert tone="danger" title="查询未完成">
          {error}
        </Alert>
      )}

      {fines && (
        <>
          <div className="grid-stats">
            <StatTile label="读者" value={readerName ?? '-'} />
            <StatTile
              label="未缴笔数"
              value={unpaid.length}
              tone={unpaid.length > 0 ? 'danger' : 'success'}
            />
            <StatTile
              label="未缴总额"
              value={formatMoney(unpaidTotal)}
              tone={unpaidTotal > 0 ? 'danger' : 'success'}
              icon={<IconMoney size={15} />}
            />
            <StatTile label="已缴笔数" value={paid.length} tone="neutral" />
          </div>

          <Card title="未缴罚款" flush>
            {unpaid.length === 0 ? (
              <Empty title="没有未缴罚款" desc="该读者当前没有待缴款项。" />
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>罚款编号</th>
                      <th>关联借阅</th>
                      <th>金额</th>
                      <th>超期天数</th>
                      <th>计费天数</th>
                      <th>生成时间</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {unpaid.map((fine) => (
                      <tr key={fine.fine_id}>
                        <td className="mono">#{fine.fine_id}</td>
                        <td className="mono muted">#{fine.loan_id}</td>
                        <td style={{ fontWeight: 650, color: 'var(--danger-600)' }}>
                          {formatMoney(fine.amount)}
                        </td>
                        <td>{fine.overdue_days} 天</td>
                        <td className="muted">
                          {fine.billed_days} 天
                          {fine.unit_price && (
                            <span style={{ fontSize: 11 }}> @ {formatMoney(fine.unit_price)}/天</span>
                          )}
                        </td>
                        <td className="muted">{formatDateTime(fine.created_at)}</td>
                        <td>
                          <div className="table__actions">
                            <Button
                              size="sm"
                              variant="primary"
                              onClick={() => setTarget(fine)}
                            >
                              标记已缴
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

          {paid.length > 0 && (
            <Card title="已缴罚款" subtitle="历史缴纳记录" flush>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>罚款编号</th>
                      <th>金额</th>
                      <th>状态</th>
                      <th>缴纳时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paid.map((fine) => (
                      <tr key={fine.fine_id}>
                        <td className="mono">#{fine.fine_id}</td>
                        <td>{formatMoney(fine.amount)}</td>
                        <td>
                          <Badge tone="success">已缴纳</Badge>
                        </td>
                        <td className="muted">{formatDateTime(fine.paid_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </>
      )}

      <Modal
        open={target !== null}
        title="确认收缴罚款"
        desc="请确认已在线下完成收款"
        onClose={() => setTarget(null)}
        footer={
          <>
            <Button onClick={() => setTarget(null)}>取消</Button>
            <Button variant="primary" loading={collecting} onClick={() => void collect()}>
              确认已收款
            </Button>
          </>
        }
      >
        {target && (
          <div className="stack">
            <ReadonlyField label="罚款编号" value={<span className="mono">#{target.fine_id}</span>} />
            <ReadonlyField
              label="应缴金额"
              value={
                <span style={{ fontSize: 20, fontWeight: 700, color: 'var(--danger-600)' }}>
                  {formatMoney(target.amount)}
                </span>
              }
            />
            <ReadonlyField label="读者" value={readerName ?? '-'} />
            <Alert tone="warning" title="本操作不可撤销">
              标记后该笔罚款将变为「已缴纳」，读者的未缴罚款总额相应减少。
            </Alert>
          </div>
        )}
      </Modal>
    </div>
  )
}

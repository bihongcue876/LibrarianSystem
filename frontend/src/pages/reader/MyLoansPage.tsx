/**
 * 我的借阅（UC-004 / FR-019）—— 读者端。
 *
 * 后端 `/api/me/loans` 返回五段结构：current / history / overdue / reservations / fines。
 * 注意 overdue 是 current 的子集（超期仍属在借），展示时需去重避免重复计数。
 */

import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Badge,
  Button,
  Card,
  Empty,
  StatTile,
  StatusBadge,
  TableSkeleton,
} from '@/components/ui'
import { IconCard, IconClock, IconMoney } from '@/components/icons'
import { useToast } from '@/components/Toast'
import { circulationApi, loanApi, reservationApi } from '@/api/endpoints'
import { toMessage } from '@/api/client'
import { RESERVATION_STATUS, labelOf, READER_TYPES } from '@/api/types'
import type { ReaderLoansResponse } from '@/api/types'
import { daysFromNow, formatDate, formatDateTime, formatMoney } from '@/utils/format'

type Tab = 'current' | 'history' | 'reservations' | 'fines'

export function MyLoansPage() {
  const toast = useToast()
  const [data, setData] = useState<ReaderLoansResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>('current')
  const [busyId, setBusyId] = useState<number | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await loanApi.myLoans())
    } catch (err) {
      setError(toMessage(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const handleRenew = async (loanId: number) => {
    setBusyId(loanId)
    try {
      const result = await circulationApi.renew(loanId)
      toast.success('续借成功', `应还日期已更新为 ${formatDate(result.due_at)}（第 ${result.renew_count} 次续借）`)
      await load()
    } catch (err) {
      toast.fromError(err, '续借失败')
    } finally {
      setBusyId(null)
    }
  }

  const handleCancelReservation = async (reservationId: number) => {
    setBusyId(reservationId)
    try {
      await reservationApi.cancel(reservationId)
      toast.success('预约已取消')
      await load()
    } catch (err) {
      toast.fromError(err, '取消失败')
    } finally {
      setBusyId(null)
    }
  }

  // 刷新（手动点击/操作后 reload）不重置为 skeleton——已有数据时保持展示
  if (loading && !data) {
    return (
      <div className="page">
        <Card flush>
          <TableSkeleton rows={6} cols={5} />
        </Card>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="page">
        <Alert tone="danger" title="加载失败">
          {error}
        </Alert>
        <Button onClick={() => void load()}>重试</Button>
      </div>
    )
  }

  const overdueCount = data.overdue.length
  const unpaidCount = data.fines.filter((f) => f.status === 'UNPAID').length

  return (
    <div className="page">
      <div className="grid-stats">
        <StatTile
          label="当前在借"
          value={data.current.length}
          tone="brand"
          icon={<IconClock size={15} />}
        />
        <StatTile
          label="超期未还"
          value={overdueCount}
          tone={overdueCount > 0 ? 'danger' : 'neutral'}
          icon={<IconClock size={15} />}
        />
        <StatTile
          label="有效预约"
          value={data.reservations.length}
          tone="neutral"
          icon={<IconCard size={15} />}
        />
        <StatTile
          label="未缴罚款"
          value={formatMoney(data.unpaid_total)}
          tone={unpaidCount > 0 ? 'danger' : 'success'}
          icon={<IconMoney size={15} />}
        />
      </div>

      <Card
        title={`${data.reader.name} 的借阅记录`}
        subtitle={
          data.reader.reader_type
            ? `${labelOf(READER_TYPES, data.reader.reader_type)}${data.reader.department ? ` · ${data.reader.department}` : ''}`
            : undefined
        }
        actions={<Button size="sm" onClick={() => void load()}>刷新</Button>}
        flush
      >
        <div style={{ padding: '0 var(--space-6)' }}>
          <div className="tabs">
            <button
              className={`tab${tab === 'current' ? ' tab--active' : ''}`}
              onClick={() => setTab('current')}
            >
              当前借阅 <span className="tab__count">{data.current.length}</span>
            </button>
            <button
              className={`tab${tab === 'history' ? ' tab--active' : ''}`}
              onClick={() => setTab('history')}
            >
              历史记录 <span className="tab__count">{data.history.length}</span>
            </button>
            <button
              className={`tab${tab === 'reservations' ? ' tab--active' : ''}`}
              onClick={() => setTab('reservations')}
            >
              我的预约 <span className="tab__count">{data.reservations.length}</span>
            </button>
            <button
              className={`tab${tab === 'fines' ? ' tab--active' : ''}`}
              onClick={() => setTab('fines')}
            >
              罚款记录 <span className="tab__count">{data.fines.length}</span>
            </button>
          </div>
        </div>

        <div style={{ paddingTop: 'var(--space-5)' }}>
          {tab === 'current' &&
            (data.current.length === 0 ? (
              <Empty title="当前没有在借图书" desc="到图书馆借书后，这里会显示应还日期与剩余天数。" />
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>书名</th>
                      <th>条码</th>
                      <th>借出时间</th>
                      <th>应还日期</th>
                      <th>状态</th>
                      <th>续借</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {data.current.map((loan) => {
                      const days = daysFromNow(loan.due_at)
                      return (
                        <tr key={loan.loan_id}>
                          <td style={{ fontWeight: 500 }}>{loan.title ?? '-'}</td>
                          <td className="mono">{loan.barcode ?? '-'}</td>
                          <td className="muted">{formatDateTime(loan.borrowed_at)}</td>
                          <td>
                            <div>{formatDate(loan.due_at)}</div>
                            {loan.is_overdue ? (
                              <span className="text-danger" style={{ fontSize: 12 }}>
                                已超期 {loan.overdue_days} 天
                              </span>
                            ) : days !== null && days <= 7 ? (
                              <span className="text-warning" style={{ fontSize: 12 }}>
                                剩余 {days} 天
                              </span>
                            ) : days !== null ? (
                              <span className="muted" style={{ fontSize: 12 }}>
                                剩余 {days} 天
                              </span>
                            ) : null}
                          </td>
                          <td>
                            <StatusBadge value={loan.status} dictionary={[
                              { value: 'BORROWED', label: '在借' },
                              { value: 'OVERDUE', label: '超期' },
                              { value: 'RETURNED', label: '已归还' },
                            ]} />
                          </td>
                          <td>
                            <span className="muted">{loan.renew_count} / 2 次</span>
                          </td>
                          <td>
                            <div className="table__actions">
                              <Button
                                size="sm"
                                disabled={!loan.can_renew}
                                loading={busyId === loan.loan_id}
                                onClick={() => void handleRenew(loan.loan_id)}
                                title={loan.can_renew ? '续借 7 天' : '已超期或已达续借上限'}
                              >
                                续借
                              </Button>
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            ))}

          {tab === 'history' &&
            (data.history.length === 0 ? (
              <Empty title="暂无历史借阅记录" />
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>书名</th>
                      <th>条码</th>
                      <th>借出时间</th>
                      <th>归还时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.history.map((loan) => (
                      <tr key={loan.loan_id}>
                        <td style={{ fontWeight: 500 }}>{loan.title ?? '-'}</td>
                        <td className="mono">{loan.barcode ?? '-'}</td>
                        <td className="muted">{formatDateTime(loan.borrowed_at)}</td>
                        <td className="muted">{formatDateTime(loan.returned_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}

          {tab === 'reservations' &&
            (data.reservations.length === 0 ? (
              <Empty
                title="没有有效预约"
                desc="在图书检索页对「暂无可借副本」的图书可发起预约。"
              />
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>题录编号</th>
                      <th>状态</th>
                      <th>排队位置</th>
                      <th>到书时间</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {data.reservations.map((res) => (
                      <tr key={res.reservation_id}>
                        <td className="mono">#{res.title_id}</td>
                        <td>
                          <StatusBadge value={res.status} dictionary={RESERVATION_STATUS} />
                        </td>
                        <td>
                          {res.status === 'READY' ? (
                            <Badge tone="success">已到书，请尽快借取</Badge>
                          ) : (
                            <span>第 {res.queue_position} 位</span>
                          )}
                        </td>
                        <td className="muted">{formatDateTime(res.ready_at)}</td>
                        <td>
                          <div className="table__actions">
                            <Button
                              size="sm"
                              variant="danger-ghost"
                              loading={busyId === res.reservation_id}
                              onClick={() => void handleCancelReservation(res.reservation_id)}
                            >
                              取消预约
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}

          {tab === 'fines' &&
            (data.fines.length === 0 ? (
              <Empty title="没有罚款记录" desc="按时归还图书就不会产生罚款。" />
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>罚款编号</th>
                      <th>金额</th>
                      <th>超期天数</th>
                      <th>计费天数</th>
                      <th>状态</th>
                      <th>生成时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.fines.map((fine) => (
                      <tr key={fine.fine_id}>
                        <td className="mono">#{fine.fine_id}</td>
                        <td style={{ fontWeight: 600 }}>{formatMoney(fine.amount)}</td>
                        <td>{fine.overdue_days} 天</td>
                        <td className="muted">{fine.billed_days} 天</td>
                        <td>
                          <StatusBadge
                            value={fine.status}
                            dictionary={[
                              { value: 'UNPAID', label: '未缴纳' },
                              { value: 'PAID', label: '已缴纳' },
                            ]}
                          />
                        </td>
                        <td className="muted">{formatDateTime(fine.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
        </div>
      </Card>

      {unpaidCount > 0 && (
        <Alert tone="warning" title="存在未缴罚款">
          未缴罚款会阻止新的借阅。请到图书馆前台缴纳（系统不接入在线支付）。
        </Alert>
      )}
    </div>
  )
}

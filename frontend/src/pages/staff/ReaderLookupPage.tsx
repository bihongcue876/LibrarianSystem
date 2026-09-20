/**
 * 读者查询页（UC-103）—— 馆员与系统管理员按读者编号查询借阅与罚款。
 *
 * 与读者端「我的借阅」共用后端 `/api/readers/{id}/loans`，
 * 差异：馆员视角会额外返回 `librarian_id`（经办人，FR-019 验收 6）。
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
  StatusBadge,
} from '@/components/ui'
import { IconSearch } from '@/components/icons'
import { loanApi } from '@/api/endpoints'
import { toMessage } from '@/api/client'
import { READER_TYPES, RESERVATION_STATUS, labelOf } from '@/api/types'
import type { ReaderLoansResponse } from '@/api/types'
import { daysFromNow, formatDate, formatDateTime, formatMoney } from '@/utils/format'

export function ReaderLookupPage() {
  const [readerId, setReaderId] = useState('')
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<ReaderLoansResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const search = async () => {
    const id = Number(readerId.trim())
    if (!Number.isInteger(id) || id <= 0) {
      setError('请输入有效的读者编号（正整数）')
      return
    }
    setLoading(true)
    setError(null)
    setData(null)
    try {
      setData(await loanApi.readerLoans(id))
    } catch (err) {
      setError(toMessage(err))
    } finally {
      setLoading(false)
    }
  }

  const unpaidTotal = data
    ? data.fines.filter((f) => f.status === 'UNPAID').reduce((sum, f) => sum + Number(f.amount), 0)
    : 0

  return (
    <div className="page">
      <Card title="按读者编号查询" subtitle="可查看该读者的在借、历史、预约与罚款明细">
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

      {!data && !error && !loading && (
        <Card flush>
          <Empty
            title="请输入读者编号"
            desc="读者编号可在「借阅证管理」中查得，或由读者本人从「我的借阅」页获知。"
          />
        </Card>
      )}

      {data && (
        <>
          <Card
            title={data.reader.name}
            subtitle={`${labelOf(READER_TYPES, data.reader.reader_type)}${data.reader.department ? ` · ${data.reader.department}` : ''} · 编号 ${data.reader.reader_id}`}
            actions={
              <Badge tone={unpaidTotal > 0 ? 'danger' : 'success'}>
                未缴罚款 {formatMoney(unpaidTotal)}
              </Badge>
            }
          >
            <div className="grid-stats">
              <div>
                <div className="muted">当前在借</div>
                <div style={{ fontSize: 22, fontWeight: 650 }}>{data.current.length}</div>
              </div>
              <div>
                <div className="muted">其中超期</div>
                <div
                  style={{
                    fontSize: 22,
                    fontWeight: 650,
                    color: data.overdue.length > 0 ? 'var(--danger-600)' : undefined,
                  }}
                >
                  {data.overdue.length}
                </div>
              </div>
              <div>
                <div className="muted">历史借阅</div>
                <div style={{ fontSize: 22, fontWeight: 650 }}>{data.history.length}</div>
              </div>
              <div>
                <div className="muted">有效预约</div>
                <div style={{ fontSize: 22, fontWeight: 650 }}>{data.reservations.length}</div>
              </div>
            </div>
          </Card>

          <Card title="当前借阅" flush>
            {data.current.length === 0 ? (
              <Empty title="当前没有在借图书" />
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
                      <th>续借次数</th>
                      <th>经办人</th>
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
                            {formatDate(loan.due_at)}
                            {loan.is_overdue && (
                              <div className="text-danger" style={{ fontSize: 12 }}>
                                超期 {loan.overdue_days} 天
                              </div>
                            )}
                            {!loan.is_overdue && days !== null && (
                              <div className="muted" style={{ fontSize: 12 }}>
                                剩余 {days} 天
                              </div>
                            )}
                          </td>
                          <td>
                            <StatusBadge
                              value={loan.status}
                              dictionary={[
                                { value: 'BORROWED', label: '在借' },
                                { value: 'OVERDUE', label: '超期' },
                                { value: 'RETURNED', label: '已归还' },
                              ]}
                            />
                          </td>
                          <td className="muted">{loan.renew_count} / 2</td>
                          <td className="muted">
                            {loan.librarian_id ? (
                              <span className="mono">#{loan.librarian_id}</span>
                            ) : (
                              <span title="管理员代行时为空">管理员代行</span>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <div className="grid-2">
            <Card title="预约记录" flush>
              {data.reservations.length === 0 ? (
                <Empty title="无有效预约" />
              ) : (
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>编号</th>
                        <th>状态</th>
                        <th>排队位置</th>
                        <th>到书时间</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.reservations.map((res) => (
                        <tr key={res.reservation_id}>
                          <td className="mono">#{res.reservation_id}</td>
                          <td>
                            <StatusBadge value={res.status} dictionary={RESERVATION_STATUS} />
                          </td>
                          <td>{res.status === 'READY' ? '-' : `第 ${res.queue_position} 位`}</td>
                          <td className="muted">{formatDateTime(res.ready_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>

            <Card title="罚款记录" flush>
              {data.fines.length === 0 ? (
                <Empty title="无罚款记录" />
              ) : (
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>编号</th>
                        <th>金额</th>
                        <th>状态</th>
                        <th>生成时间</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.fines.map((fine) => (
                        <tr key={fine.fine_id}>
                          <td className="mono">#{fine.fine_id}</td>
                          <td style={{ fontWeight: 600 }}>{formatMoney(fine.amount)}</td>
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
              )}
            </Card>
          </div>

          <Card title="历史借阅" flush>
            {data.history.length === 0 ? (
              <Empty title="无历史记录" />
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
            )}
          </Card>
        </>
      )}
    </div>
  )
}

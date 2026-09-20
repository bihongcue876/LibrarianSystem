/**
 * 规则维护（UC-213 / UC-214）—— 仅系统管理员。
 *
 * 重要业务语义：修改**只影响之后创建的业务记录**，不追溯已有数据（BR-050）。
 * 界面上必须把这个语义说清楚，避免管理员误以为会重算历史罚款。
 */

import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Field,
  Input,
  Modal,
  ReadonlyField,
  TableSkeleton,
} from '@/components/ui'
import { IconSettings } from '@/components/icons'
import { useToast } from '@/components/Toast'
import { policyApi } from '@/api/endpoints'
import { toMessage } from '@/api/client'
import { ITEM_TYPES, READER_TYPES, labelOf } from '@/api/types'
import type { BorrowPolicyItem, FineRuleItem, PoliciesResponse } from '@/api/types'
import { formatDateTime, formatMoney, toFixedString } from '@/utils/format'

export function PoliciesPage() {
  const toast = useToast()
  const [data, setData] = useState<PoliciesResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // 编辑借阅规则
  const [editBorrow, setEditBorrow] = useState<BorrowPolicyItem | null>(null)
  const [borrowForm, setBorrowForm] = useState({ max_borrow_count: '', borrow_days: '' })
  const [savingBorrow, setSavingBorrow] = useState(false)

  // 编辑罚款规则
  const [editFine, setEditFine] = useState<FineRuleItem | null>(null)
  const [fineForm, setFineForm] = useState({ daily_price: '', grace_days: '', max_amount: '' })
  const [savingFine, setSavingFine] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await policyApi.getAll())
    } catch (err) {
      setError(toMessage(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const submitBorrow = async () => {
    if (!editBorrow) return
    const count = Number(borrowForm.max_borrow_count)
    const days = Number(borrowForm.borrow_days)
    if (!Number.isInteger(count) || count < 1) {
      toast.error('可借册数无效', '必须为不小于 1 的整数')
      return
    }
    if (!Number.isInteger(days) || days < 1) {
      toast.error('借期无效', '必须为不小于 1 的整数')
      return
    }
    setSavingBorrow(true)
    try {
      await policyApi.updateBorrow({
        reader_type: editBorrow.reader_type,
        max_borrow_count: count,
        borrow_days: days,
      })
      toast.success('借阅规则已更新', '仅对之后创建的借阅生效')
      setEditBorrow(null)
      await load()
    } catch (err) {
      toast.fromError(err, '更新失败')
    } finally {
      setSavingBorrow(false)
    }
  }

  const submitFine = async () => {
    if (!editFine) return
    const grace = Number(fineForm.grace_days)
    if (!Number.isInteger(grace) || grace < 0) {
      toast.error('宽限天数无效', '必须为不小于 0 的整数')
      return
    }
    setSavingFine(true)
    try {
      await policyApi.updateFine({
        item_type: editFine.item_type,
        daily_price: toFixedString(fineForm.daily_price || '0'),
        grace_days: grace,
        max_amount: toFixedString(fineForm.max_amount || '0'),
      })
      toast.success('罚款规则已更新', '仅对之后生成的罚款生效')
      setEditFine(null)
      await load()
    } catch (err) {
      toast.fromError(err, '更新失败')
    } finally {
      setSavingFine(false)
    }
  }

  if (loading) {
    return (
      <div className="page">
        <Card flush>
          <TableSkeleton rows={6} cols={4} />
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

  return (
    <div className="page">
      <Alert tone="warning" title="规则修改不追溯历史数据">
        修改后的规则<b>只影响之后创建的业务记录</b>。已存在的借阅保持其原应还日期，
        已生成的罚款保持其原单价与金额（<span className="mono">BR-050</span>）。
      </Alert>

      <Card
        title="借阅规则"
        subtitle="按读者类型设定可借册数与借期"
        actions={
          <Button size="sm" onClick={() => void load()} icon={<IconSettings size={15} />}>
            刷新
          </Button>
        }
        flush
      >
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>读者类型</th>
                <th>可借册数</th>
                <th>借期（天）</th>
                <th>最后修改</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.borrow_policies.map((policy) => (
                <tr key={policy.reader_type}>
                  <td style={{ fontWeight: 550 }}>
                    {labelOf(READER_TYPES, policy.reader_type)}
                  </td>
                  <td>
                    <span style={{ fontWeight: 600 }}>{policy.max_borrow_count}</span> 册
                  </td>
                  <td>
                    <span style={{ fontWeight: 600 }}>{policy.borrow_days}</span> 天
                  </td>
                  <td className="muted">{formatDateTime(policy.updated_at)}</td>
                  <td>
                    <div className="table__actions">
                      <Button
                        size="sm"
                        onClick={() => {
                          setEditBorrow(policy)
                          setBorrowForm({
                            max_borrow_count: String(policy.max_borrow_count),
                            borrow_days: String(policy.borrow_days),
                          })
                        }}
                      >
                        修改
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="罚款规则" subtitle="按文献类型设定超期单价、宽限期与单笔封顶" flush>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>文献类型</th>
                <th>单价（元/天）</th>
                <th>宽限期（天）</th>
                <th>单笔封顶</th>
                <th>最后修改</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.fine_rules.map((rule) => (
                <tr key={rule.item_type}>
                  <td style={{ fontWeight: 550 }}>{labelOf(ITEM_TYPES, rule.item_type)}</td>
                  <td style={{ fontWeight: 600 }}>{formatMoney(rule.daily_price)}</td>
                  <td>{rule.grace_days} 天</td>
                  <td>{formatMoney(rule.max_amount)}</td>
                  <td className="muted">{formatDateTime(rule.updated_at)}</td>
                  <td>
                    <div className="table__actions">
                      <Button
                        size="sm"
                        onClick={() => {
                          setEditFine(rule)
                          setFineForm({
                            daily_price: rule.daily_price,
                            grace_days: String(rule.grace_days),
                            max_amount: rule.max_amount,
                          })
                        }}
                      >
                        修改
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Alert tone="info" title="罚款计算方式">
        超出宽限期后，按「超出天数 × 单价」计费，单笔金额不超过封顶值。
        例如中文图书（单价 0.20 元/天，宽限 2 天）超期 5 天，计费天数为 3 天，应收 0.60 元。
      </Alert>

      {/* 编辑借阅规则 */}
      <Modal
        open={editBorrow !== null}
        title="修改借阅规则"
        desc={editBorrow ? labelOf(READER_TYPES, editBorrow.reader_type) : ''}
        onClose={() => setEditBorrow(null)}
        footer={
          <>
            <Button onClick={() => setEditBorrow(null)}>取消</Button>
            <Button variant="primary" loading={savingBorrow} onClick={() => void submitBorrow()}>
              保存
            </Button>
          </>
        }
      >
        {editBorrow && (
          <div className="stack">
            <div className="grid-2" style={{ gap: 'var(--space-4)' }}>
              <Field label="可借册数" required hint="不小于 1">
                <Input
                  type="number"
                  min={1}
                  value={borrowForm.max_borrow_count}
                  onChange={(e) =>
                    setBorrowForm({ ...borrowForm, max_borrow_count: e.target.value })
                  }
                />
              </Field>
              <Field label="借期（天）" required hint="不小于 1">
                <Input
                  type="number"
                  min={1}
                  value={borrowForm.borrow_days}
                  onChange={(e) => setBorrowForm({ ...borrowForm, borrow_days: e.target.value })}
                />
              </Field>
            </div>
            <ReadonlyField
              label="修改前"
              value={`${editBorrow.max_borrow_count} 册 / ${editBorrow.borrow_days} 天`}
            />
          </div>
        )}
      </Modal>

      {/* 编辑罚款规则 */}
      <Modal
        open={editFine !== null}
        title="修改罚款规则"
        desc={editFine ? labelOf(ITEM_TYPES, editFine.item_type) : ''}
        onClose={() => setEditFine(null)}
        footer={
          <>
            <Button onClick={() => setEditFine(null)}>取消</Button>
            <Button variant="primary" loading={savingFine} onClick={() => void submitFine()}>
              保存
            </Button>
          </>
        }
      >
        {editFine && (
          <div className="stack">
            <div className="grid-2" style={{ gap: 'var(--space-4)' }}>
              <Field label="单价（元/天）" required hint="定点小数，如 0.20">
                <Input
                  value={fineForm.daily_price}
                  onChange={(e) => setFineForm({ ...fineForm, daily_price: e.target.value })}
                  className="mono"
                  placeholder="0.20"
                />
              </Field>
              <Field label="宽限期（天）" required hint="可为 0">
                <Input
                  type="number"
                  min={0}
                  value={fineForm.grace_days}
                  onChange={(e) => setFineForm({ ...fineForm, grace_days: e.target.value })}
                />
              </Field>
            </div>
            <Field label="单笔封顶（元）" required hint="定点小数，如 100.00">
              <Input
                value={fineForm.max_amount}
                onChange={(e) => setFineForm({ ...fineForm, max_amount: e.target.value })}
                className="mono"
                placeholder="100.00"
              />
            </Field>
            <ReadonlyField
              label="修改前"
              value={`${formatMoney(editFine.daily_price)}/天 · 宽限 ${editFine.grace_days} 天 · 封顶 ${formatMoney(editFine.max_amount)}`}
            />
          </div>
        )}
      </Modal>
    </div>
  )
}

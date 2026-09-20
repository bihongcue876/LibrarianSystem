/**
 * 借阅证管理（UC-201~205）—— 仅系统管理员。
 *
 * 一人一证：`ACTIVE` / `SUSPENDED` 计入唯一性，`CANCELLED` 不计入（BR-003）。
 * 卡号由后端自动生成（`CARD` + 10 位），前端不提供输入。
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
  StatusBadge,
} from '@/components/ui'
import { IconCard, IconPlus, IconSearch } from '@/components/icons'
import { useToast } from '@/components/Toast'
import { cardApi } from '@/api/endpoints'
import { toMessage } from '@/api/client'
import { CARD_STATUS } from '@/api/types'
import type { BorrowCard } from '@/api/types'
import { formatDateTime } from '@/utils/format'

type Action = 'cancel' | 'restore' | 'suspend' | 'resume'

const ACTION_LABEL: Record<Action, string> = {
  cancel: '注销',
  restore: '恢复',
  suspend: '挂失',
  resume: '解挂',
}

export function CardsPage() {
  const toast = useToast()

  // 办证
  const [issueReaderId, setIssueReaderId] = useState('')
  const [issuing, setIssuing] = useState(false)

  // 按读者查询
  const [lookupReaderId, setLookupReaderId] = useState('')
  const [cards, setCards] = useState<BorrowCard[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // 单卡操作
  const [pending, setPending] = useState<{ card: BorrowCard; action: Action } | null>(null)
  const [acting, setActing] = useState(false)

  const issueCard = async () => {
    const id = Number(issueReaderId.trim())
    if (!Number.isInteger(id) || id <= 0) {
      toast.error('读者编号无效', '请输入正整数读者编号')
      return
    }
    setIssuing(true)
    try {
      const card = await cardApi.issueCard(id)
      toast.success('办证成功', `卡号 ${card.card_no}`)
      setIssueReaderId('')
      if (cards !== null) setLookupReaderId(String(id))
    } catch (err) {
      toast.fromError(err, '办证失败')
    } finally {
      setIssuing(false)
    }
  }

  const lookup = async () => {
    const id = Number(lookupReaderId.trim())
    if (!Number.isInteger(id) || id <= 0) {
      setError('请输入有效的读者编号（正整数）')
      return
    }
    setLoading(true)
    setError(null)
    setCards(null)
    try {
      setCards(await cardApi.listByReader(id))
    } catch (err) {
      setError(toMessage(err))
    } finally {
      setLoading(false)
    }
  }

  const runAction = async () => {
    if (!pending) return
    setActing(true)
    try {
      const { card, action } = pending
      const fn = {
        cancel: () => cardApi.cancelCard(card.card_id),
        restore: () => cardApi.restoreCard(card.card_id),
        suspend: () => cardApi.suspendCard(card.card_id),
        resume: () => cardApi.resumeCard(card.card_id),
      }[action]
      const updated = await fn()
      toast.success(`已${ACTION_LABEL[action]}`, `卡号 ${updated.card_no}`)
      setPending(null)
      await lookup()
    } catch (err) {
      toast.fromError(err, `${ACTION_LABEL[pending.action]}失败`)
    } finally {
      setActing(false)
    }
  }

  return (
    <div className="page">
      <div className="grid-2">
        <Card title="办理借阅证" subtitle="一人一证；已注销的证不计入唯一性">
          <div className="stack">
            <Field label="读者编号" required hint="读者须先完成注册">
              <Input
                type="number"
                min={1}
                value={issueReaderId}
                onChange={(e) => setIssueReaderId(e.target.value)}
                placeholder="如 1"
                className="mono"
                onKeyDown={(e) => {
                  if (e.key === 'Enter') void issueCard()
                }}
              />
            </Field>
            <Button
              variant="primary"
              block
              loading={issuing}
              onClick={() => void issueCard()}
              icon={<IconPlus size={16} />}
            >
              办理借阅证
            </Button>
            <Alert tone="info">
              卡号由系统自动生成，格式为 <span className="mono">CARD</span> 加 10 位数字。
            </Alert>
          </div>
        </Card>

        <Card title="查询读者借阅证" subtitle="含历史注销记录">
          <div className="toolbar">
            <div style={{ width: 200 }}>
              <Field label="读者编号">
                <Input
                  type="number"
                  min={1}
                  value={lookupReaderId}
                  onChange={(e) => setLookupReaderId(e.target.value)}
                  placeholder="如 1"
                  className="mono"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') void lookup()
                  }}
                />
              </Field>
            </div>
            <Button
              style={{ marginTop: 22 }}
              loading={loading}
              onClick={() => void lookup()}
              icon={<IconSearch size={16} />}
            >
              查询
            </Button>
          </div>
        </Card>
      </div>

      {error && (
        <Alert tone="danger" title="查询未完成">
          {error}
        </Alert>
      )}

      {cards !== null && (
        <Card
          title="借阅证列表"
          subtitle={`读者编号 ${lookupReaderId} · 共 ${cards.length} 张`}
          flush
        >
          {cards.length === 0 ? (
            <Empty
              title="该读者尚未办理借阅证"
              desc="使用上方「办理借阅证」为其办证后，读者即可借阅图书。"
              action={
                <Button
                  variant="primary"
                  icon={<IconCard size={16} />}
                  onClick={() => {
                    setIssueReaderId(lookupReaderId)
                    void issueCard()
                  }}
                >
                  立即办证
                </Button>
              }
            />
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>卡号</th>
                    <th>状态</th>
                    <th>办证时间</th>
                    <th>注销时间</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {cards.map((card) => (
                    <tr key={card.card_id}>
                      <td className="mono" style={{ fontWeight: 600 }}>
                        {card.card_no}
                      </td>
                      <td>
                        <StatusBadge value={card.status} dictionary={CARD_STATUS} />
                      </td>
                      <td className="muted">{formatDateTime(card.issued_at)}</td>
                      <td className="muted">{formatDateTime(card.cancelled_at)}</td>
                      <td>
                        <div className="table__actions">
                          {card.status === 'ACTIVE' && (
                            <>
                              <Button
                                size="sm"
                                onClick={() => setPending({ card, action: 'suspend' })}
                              >
                                挂失
                              </Button>
                              <Button
                                size="sm"
                                variant="danger-ghost"
                                onClick={() => setPending({ card, action: 'cancel' })}
                              >
                                注销
                              </Button>
                            </>
                          )}
                          {card.status === 'SUSPENDED' && (
                            <>
                              <Button
                                size="sm"
                                variant="primary"
                                onClick={() => setPending({ card, action: 'resume' })}
                              >
                                解挂
                              </Button>
                              <Button
                                size="sm"
                                variant="danger-ghost"
                                onClick={() => setPending({ card, action: 'cancel' })}
                              >
                                注销
                              </Button>
                            </>
                          )}
                          {card.status === 'CANCELLED' && (
                            <Button
                              size="sm"
                              variant="primary"
                              onClick={() => setPending({ card, action: 'restore' })}
                            >
                              恢复
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      <Modal
        open={pending !== null}
        title={pending ? `确认${ACTION_LABEL[pending.action]}借阅证` : ''}
        onClose={() => setPending(null)}
        footer={
          <>
            <Button onClick={() => setPending(null)}>取消</Button>
            <Button
              variant={pending?.action === 'cancel' ? 'danger' : 'primary'}
              loading={acting}
              onClick={() => void runAction()}
            >
              确认{ACTION_LABEL[pending?.action ?? 'cancel']}
            </Button>
          </>
        }
      >
        {pending && (
          <div className="stack">
            <ReadonlyField
              label="卡号"
              value={<span className="mono">{pending.card.card_no}</span>}
            />
            <ReadonlyField
              label="当前状态"
              value={<StatusBadge value={pending.card.status} dictionary={CARD_STATUS} />}
            />
            <Alert
              tone={pending.action === 'cancel' ? 'warning' : 'info'}
              title={
                pending.action === 'cancel'
                  ? '注销后该读者将无法借书'
                  : pending.action === 'suspend'
                    ? '挂失期间不可借书'
                    : '操作立即生效'
              }
            >
              {pending.action === 'cancel' &&
                '该证注销后不再计入「一人一证」限制，读者可重新办证（FR-006 验收 4）。已借出的图书不受影响，仍需归还。'}
              {pending.action === 'suspend' && '挂失后该证不能用于借书，解挂后恢复。'}
              {pending.action === 'resume' && '解挂后该证恢复为有效状态。'}
              {pending.action === 'restore' && '恢复后该证重新变为有效，并再次计入「一人一证」限制。'}
            </Alert>
            {pending.card.status === 'ACTIVE' && <Badge tone="success">当前有效</Badge>}
          </div>
        )}
      </Modal>
    </div>
  )
}

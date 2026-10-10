/**
 * 借还流通页（UC-101 / UC-102 / UC-104）—— 馆员与系统管理员。
 *
 * 借书流程严格按规格实现「前置确认 → 正式提交」两步：
 * 1. `POST /api/circulation/precheck`（只读，展示六项校验明细）
 * 2. `POST /api/circulation/borrow`（事务内执行，失败全部回滚）
 *
 * 还书仅凭馆藏条码，不需要借阅证。
 */

import { useState } from 'react'
import {
  Alert,
  Badge,
  Button,
  Card,
  Field,
  Input,
  Modal,
  ReadonlyField,
} from '@/components/ui'
import { IconAlert, IconCheck, IconScan, IconSwap } from '@/components/icons'
import { useToast } from '@/components/Toast'
import { circulationApi } from '@/api/endpoints'
import { READER_TYPES, ITEM_STATUS, labelOf } from '@/api/types'
import type { BorrowBookResponse, PreCheckResponse, ReturnBookResponse } from '@/api/types'
import { formatDate, formatMoney } from '@/utils/format'

/** 校验步骤中文名（后端返回英文 step 标识） */
const STEP_LABELS: Record<string, string> = {
  card: '借阅证有效性',
  card_status: '借阅证状态',
  quota: '借阅额度',
  count: '借阅数量',
  overdue: '超期未还',
  fine: '未缴罚款',
  item: '馆藏副本',
  item_status: '副本状态',
}

const stepLabel = (step: string) => STEP_LABELS[step] ?? step

/** 条码/卡号格式校验是后端强约束，提前在客户端拦一下，避免无意义的 422 */
const CARD_PATTERN = /^CARD\d{10}$/
const BARCODE_PATTERN = /^BC\d{8}$/

export function CirculationPage() {
  const toast = useToast()

  // ---- 借书 ----
  const [cardNo, setCardNo] = useState('')
  const [borrowBarcode, setBorrowBarcode] = useState('')
  const [prechecking, setPrechecking] = useState(false)
  const [precheckResult, setPrecheckResult] = useState<PreCheckResponse | null>(null)
  const [borrowOpen, setBorrowOpen] = useState(false)
  const [borrowing, setBorrowing] = useState(false)
  const [borrowResult, setBorrowResult] = useState<BorrowBookResponse | null>(null)
  /** 打开确认弹窗那一刻的卡号/条码快照——弹窗展示与提交都用它，避免输入框后续改动造成展示与实际借阅对象不一致 */
  const [borrowSnapshot, setBorrowSnapshot] = useState<{ cardNo: string; barcode: string } | null>(
    null,
  )

  // ---- 还书 ----
  const [returnBarcode, setReturnBarcode] = useState('')
  const [returning, setReturning] = useState(false)
  const [returnResult, setReturnResult] = useState<ReturnBookResponse | null>(null)

  const cardValid = CARD_PATTERN.test(cardNo.trim())
  const borrowBarcodeValid = BARCODE_PATTERN.test(borrowBarcode.trim())
  const returnBarcodeValid = BARCODE_PATTERN.test(returnBarcode.trim())

  const runPrecheck = async () => {
    setPrechecking(true)
    setPrecheckResult(null)
    try {
      const result = await circulationApi.precheck(cardNo.trim(), borrowBarcode.trim())
      setPrecheckResult(result)
      if (!result.can_borrow) {
        toast.error('校验未通过', '请查看下方校验明细')
      }
    } catch (err) {
      toast.fromError(err, '前置校验失败')
    } finally {
      setPrechecking(false)
    }
  }

  const confirmBorrow = async () => {
    if (!borrowSnapshot) return
    setBorrowing(true)
    try {
      const result = await circulationApi.borrow(
        borrowSnapshot.cardNo,
        borrowSnapshot.barcode,
      )
      setBorrowResult(result)
      setBorrowOpen(false)
      setPrecheckResult(null)
      setCardNo('')
      setBorrowBarcode('')
      toast.success('借书成功', `应还日期 ${formatDate(result.due_at)}`)
    } catch (err) {
      toast.fromError(err, '借书失败')
    } finally {
      setBorrowing(false)
    }
  }

  const doReturn = async () => {
    setReturning(true)
    setReturnResult(null)
    try {
      const result = await circulationApi.returnBook(returnBarcode.trim())
      setReturnResult(result)
      setReturnBarcode('')
      if (result.fine) {
        toast.info(
          '还书成功（产生罚款）',
          `超期 ${result.overdue_days} 天，应缴 ${formatMoney(result.fine.amount)}`,
        )
      } else {
        toast.success('还书成功', result.overdue_days > 0 ? '在宽限期内，不产生罚款' : undefined)
      }
    } catch (err) {
      toast.fromError(err, '还书失败')
    } finally {
      setReturning(false)
    }
  }

  const resetBorrowPanel = () => {
    setCardNo('')
    setBorrowBarcode('')
    setPrecheckResult(null)
    setBorrowResult(null)
    setBorrowSnapshot(null)
  }

  /** 打开确认弹窗并记录当时的输入快照，展示与提交都用快照值 */
  const openBorrowModal = () => {
    setBorrowSnapshot({ cardNo: cardNo.trim(), barcode: borrowBarcode.trim() })
    setBorrowOpen(true)
  }

  return (
    <div className="page">
      <div className="grid-2">
        {/* -------- 借书 -------- */}
        <Card
          title="办理借书"
          subtitle="代理读者借书，须先执行前置校验"
          actions={
            <Button size="sm" variant="ghost" onClick={resetBorrowPanel}>
              清空
            </Button>
          }
        >
          <div className="stack">
            <Field
              label="借阅证号"
              required
              hint="格式：CARD + 10 位数字"
              error={cardNo && !cardValid ? '格式不正确，应为 CARD 加 10 位数字' : undefined}
            >
              <Input
                value={cardNo}
                onChange={(e) => setCardNo(e.target.value.toUpperCase())}
                placeholder="CARD2026000001"
                invalid={Boolean(cardNo) && !cardValid}
                className="mono"
              />
            </Field>

            <Field
              label="馆藏条码"
              required
              hint="格式：BC + 8 位数字"
              error={
                borrowBarcode && !borrowBarcodeValid ? '格式不正确，应为 BC 加 8 位数字' : undefined
              }
            >
              <Input
                value={borrowBarcode}
                onChange={(e) => setBorrowBarcode(e.target.value.toUpperCase())}
                placeholder="BC00000001"
                invalid={Boolean(borrowBarcode) && !borrowBarcodeValid}
                className="mono"
              />
            </Field>

            <div className="row" style={{ gap: 'var(--space-3)' }}>
              <Button
                variant="primary"
                block
                loading={prechecking}
                disabled={!cardValid || !borrowBarcodeValid}
                onClick={() => void runPrecheck()}
                icon={<IconScan size={16} />}
              >
                前置校验
              </Button>
              <Button
                variant="secondary"
                block
                disabled={!cardValid || !borrowBarcodeValid}
                onClick={() => setBorrowOpen(true)}
              >
                直接借书
              </Button>
            </div>
          </div>

          {precheckResult && (
            <div style={{ marginTop: 'var(--space-5)' }} className="stack">
              <div className="row row--between">
                <strong style={{ fontSize: 14 }}>校验结果</strong>
                <Badge tone={precheckResult.can_borrow ? 'success' : 'danger'}>
                  {precheckResult.can_borrow ? '可以借出' : '不可借出'}
                </Badge>
              </div>

              {precheckResult.reader && (
                <div className="grid-2" style={{ gap: 'var(--space-4)' }}>
                  <ReadonlyField label="读者" value={precheckResult.reader.name} />
                  <ReadonlyField
                    label="读者类型"
                    value={labelOf(READER_TYPES, precheckResult.reader.reader_type)}
                  />
                </div>
              )}

              {precheckResult.quota && (
                <div className="grid-2" style={{ gap: 'var(--space-4)' }}>
                  <ReadonlyField
                    label="额度使用"
                    value={`${precheckResult.quota.occupied} / ${precheckResult.quota.limit}`}
                  />
                  <ReadonlyField
                    label="剩余可借"
                    value={`${precheckResult.quota.remaining} 册`}
                  />
                </div>
              )}

              <div className="check-list">
                {precheckResult.checks.map((check, idx) => (
                  <div
                    className={`check-item check-item--${check.ok ? 'ok' : 'fail'}`}
                    key={`${check.step}-${idx}`}
                  >
                    <span className="check-item__icon">
                      {check.ok ? <IconCheck size={15} /> : <IconAlert size={15} />}
                    </span>
                    <div>
                      <span className="check-item__step">{stepLabel(check.step)}</span>
                      {check.message || (check.ok ? '通过' : '未通过')}
                    </div>
                  </div>
                ))}
              </div>

              {precheckResult.can_borrow && (
                <Button variant="primary" block onClick={openBorrowModal}>
                  确认借出
                </Button>
              )}
            </div>
          )}

          {borrowResult && (
            <div style={{ marginTop: 'var(--space-5)' }}>
              <Alert tone="success" title="借书成功">
                <div className="stack stack--sm" style={{ marginTop: 'var(--space-2)' }}>
                  <span>
                    借阅编号 <span className="mono">#{borrowResult.loan_id}</span>
                  </span>
                  <span>应还日期：{formatDate(borrowResult.due_at)}</span>
                  <span>剩余可借额度：{borrowResult.remaining_quota} 册</span>
                </div>
              </Alert>
            </div>
          )}
        </Card>

        {/* -------- 还书 -------- */}
        <Card title="办理还书" subtitle="仅凭馆藏条码归还，无需借阅证">
          <div className="stack">
            <Field
              label="馆藏条码"
              required
              hint="格式：BC + 8 位数字"
              error={
                returnBarcode && !returnBarcodeValid ? '格式不正确，应为 BC 加 8 位数字' : undefined
              }
            >
              <Input
                value={returnBarcode}
                onChange={(e) => setReturnBarcode(e.target.value.toUpperCase())}
                placeholder="BC00000001"
                invalid={Boolean(returnBarcode) && !returnBarcodeValid}
                className="mono"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && returnBarcodeValid) void doReturn()
                }}
              />
            </Field>

            <Button
              variant="primary"
              size="lg"
              block
              loading={returning}
              disabled={!returnBarcodeValid}
              onClick={() => void doReturn()}
              icon={<IconSwap size={16} />}
            >
              确认归还
            </Button>

            <Alert tone="info">
              超期将自动生成罚款（宽限 2 天，按超出天数计费，单笔封顶 100 元）。
              若该副本存在有效预约，归还后会自动为下一位预约者预留。
            </Alert>
          </div>

          {returnResult && (
            <div style={{ marginTop: 'var(--space-5)' }} className="stack">
              <Alert
                tone={returnResult.fine ? 'warning' : 'success'}
                title={returnResult.fine ? '还书成功，产生罚款' : '还书成功'}
              >
                <div className="stack stack--sm" style={{ marginTop: 'var(--space-2)' }}>
                  <span>
                    超期天数：{returnResult.overdue_days} 天
                    {returnResult.billed_days > 0 && `（计费 ${returnResult.billed_days} 天）`}
                  </span>
                  {returnResult.fine && (
                    <span>
                      罚款金额：<strong>{formatMoney(returnResult.fine.amount)}</strong>，状态
                      {' '}未缴纳
                    </span>
                  )}
                  <span>
                    副本状态：{labelOf(ITEM_STATUS, returnResult.item_status)}
                  </span>
                  {returnResult.reservation_advanced && (
                    <span className="text-success">
                      已自动为预约者 #{returnResult.reservation_advanced.reader_id} 预留该副本
                    </span>
                  )}
                </div>
              </Alert>
            </div>
          )}
        </Card>
      </div>

      {/* 借书确认弹窗 */}
      <Modal
        open={borrowOpen}
        title="确认办理借书"
        desc="提交后不可撤销，请核对信息无误"
        onClose={() => setBorrowOpen(false)}
        footer={
          <>
            <Button onClick={() => setBorrowOpen(false)}>取消</Button>
            <Button variant="primary" loading={borrowing} onClick={() => void confirmBorrow()}>
              确认借出
            </Button>
          </>
        }
      >
        <div className="stack">
          <ReadonlyField
            label="借阅证号"
            value={<span className="mono">{borrowSnapshot?.cardNo}</span>}
          />
          <ReadonlyField
            label="馆藏条码"
            value={<span className="mono">{borrowSnapshot?.barcode}</span>}
          />

          {precheckResult?.reader && (
            <ReadonlyField label="读者" value={precheckResult.reader.name} />
          )}
          {precheckResult?.quota && (
            <ReadonlyField
              label="借出后剩余额度"
              value={`${Math.max(0, precheckResult.quota.remaining - 1)} 册`}
            />
          )}

          {!precheckResult && (
            <Alert tone="warning" title="尚未执行前置校验">
              直接借书仍会在服务端执行全部六项校验，若有不通过项，操作会被拒绝且不产生任何数据变更。
            </Alert>
          )}
        </div>
      </Modal>
    </div>
  )
}

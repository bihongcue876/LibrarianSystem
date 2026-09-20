/**
 * 馆藏统计（UC-215 / FR-029）—— 仅系统管理员。
 *
 * 展示题录总数、副本总数，以及按状态、按文献类型的分布。
 * 分布用纯 CSS 条形图呈现，不引入图表库。
 */

import { useCallback, useEffect, useState } from 'react'
import { Alert, Button, Card, StatTile } from '@/components/ui'
import { IconBook, IconChart } from '@/components/icons'
import { queryApi } from '@/api/endpoints'
import { toMessage } from '@/api/client'
import { ITEM_STATUS, ITEM_TYPES } from '@/api/types'
import type { CollectionStats } from '@/api/types'

/** 状态分布配色（与全站语义色一致） */
const STATUS_COLOR: Record<string, string> = {
  AVAILABLE: 'var(--success-500)',
  BORROWED: 'var(--warning-500)',
  RESERVED: 'var(--info-500)',
  LOST: 'var(--danger-500)',
  DAMAGED: 'var(--danger-400, #f87171)',
  REMOVED: 'var(--gray-400)',
}

export function StatsPage() {
  const [data, setData] = useState<CollectionStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await queryApi.collectionStats())
    } catch (err) {
      setError(toMessage(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  if (error) {
    return (
      <div className="page">
        <Alert tone="danger" title="加载失败">
          {error}
        </Alert>
        <Button onClick={() => void load()}>重试</Button>
      </div>
    )
  }

  if (loading || !data) {
    return (
      <div className="page">
        <div className="grid-stats">
          {Array.from({ length: 4 }).map((_, i) => (
            <div className="skeleton" key={i} style={{ height: 96, borderRadius: 'var(--radius-lg)' }} />
          ))}
        </div>
      </div>
    )
  }

  const statusTotal = Object.values(data.by_status).reduce((a, b) => a + b, 0)
  const typeTotal = Object.values(data.by_item_type).reduce((a, b) => a + b, 0)
  const borrowed = data.by_status.BORROWED ?? 0
  const available = data.by_status.AVAILABLE ?? 0
  const utilization = data.items > 0 ? Math.round(((data.items - available) / data.items) * 100) : 0

  return (
    <div className="page">
      <div className="grid-stats">
        <StatTile label="题录总数" value={data.titles} tone="brand" icon={<IconBook size={15} />} />
        <StatTile label="副本总数" value={data.items} icon={<IconChart size={15} />} />
        <StatTile label="当前可借" value={available} tone="success" />
        <StatTile
          label="在借 / 流转率"
          value={
            <>
              {borrowed}
              <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-tertiary)' }}>
                {' '}
                / {utilization}%
              </span>
            </>
          }
          tone={borrowed > 0 ? 'warning' : 'neutral'}
        />
      </div>

      <div className="grid-2">
        <Card title="按副本状态分布" subtitle={`共 ${statusTotal} 册`}>
          <div className="stack">
            {ITEM_STATUS.map((status) => {
              const count = data.by_status[status.value] ?? 0
              const pct = statusTotal > 0 ? (count / statusTotal) * 100 : 0
              return (
                <div key={status.value}>
                  <div
                    className="row row--between"
                    style={{ marginBottom: 'var(--space-2)', fontSize: 13 }}
                  >
                    <span style={{ fontWeight: 500 }}>{status.label}</span>
                    <span className="muted">
                      {count} 册 · {pct.toFixed(1)}%
                    </span>
                  </div>
                  <div
                    style={{
                      height: 8,
                      borderRadius: 'var(--radius-full)',
                      background: 'var(--gray-100)',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        width: `${pct}%`,
                        height: '100%',
                        background: STATUS_COLOR[status.value] ?? 'var(--gray-400)',
                        borderRadius: 'var(--radius-full)',
                        transition: 'width 600ms var(--ease-out)',
                      }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </Card>

        <Card title="按文献类型分布" subtitle={`共 ${typeTotal} 册`}>
          <div className="stack">
            {ITEM_TYPES.map((type) => {
              const count = data.by_item_type[type.value] ?? 0
              const pct = typeTotal > 0 ? (count / typeTotal) * 100 : 0
              return (
                <div key={type.value}>
                  <div
                    className="row row--between"
                    style={{ marginBottom: 'var(--space-2)', fontSize: 13 }}
                  >
                    <span style={{ fontWeight: 500 }}>{type.label}</span>
                    <span className="muted">
                      {count} 册 · {pct.toFixed(1)}%
                    </span>
                  </div>
                  <div
                    style={{
                      height: 8,
                      borderRadius: 'var(--radius-full)',
                      background: 'var(--gray-100)',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        width: `${pct}%`,
                        height: '100%',
                        background: 'var(--brand-500)',
                        borderRadius: 'var(--radius-full)',
                        transition: 'width 600ms var(--ease-out)',
                      }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </Card>
      </div>

      <Card title="副本状态说明" subtitle="状态由业务流程驱动，仅「可借 / 丢失 / 破损」可由管理员手工标记">
        <div className="stack stack--sm" style={{ fontSize: 13 }}>
          {ITEM_STATUS.map((status) => (
            <div className="row" key={status.value} style={{ gap: 'var(--space-3)' }}>
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: STATUS_COLOR[status.value] ?? 'var(--gray-400)',
                  flexShrink: 0,
                }}
              />
              <span style={{ fontWeight: 550, minWidth: 64 }}>{status.label}</span>
              <span className="muted">
                {status.value === 'AVAILABLE' && '可被借出'}
                {status.value === 'BORROWED' && '已借出，归还后自动转为可借或预留'}
                {status.value === 'RESERVED' && '已为预约者预留，取消预约则转交下一位'}
                {status.value === 'LOST' && '读者报失或管理员标记'}
                {status.value === 'DAMAGED' && '管理员标记，不可借出'}
                {status.value === 'REMOVED' && '软删除，不出现在检索结果中'}
              </span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}

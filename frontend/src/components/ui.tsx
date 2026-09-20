/** 基础 UI 组件 —— 无第三方依赖，纯 React + CSS */

import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from 'react'
import { useEffect, type CSSProperties } from 'react'
import { IconAlert, IconCheck, IconInfo, IconInbox, IconX } from './icons'
import { labelOf } from '@/api/types'

// ---- Button ------------------------------------------------------------

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'danger-ghost'
type ButtonSize = 'sm' | 'md' | 'lg'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
  block?: boolean
  icon?: ReactNode
}

export function Button({
  variant = 'secondary',
  size = 'md',
  loading = false,
  block = false,
  icon,
  children,
  className = '',
  disabled,
  ...rest
}: ButtonProps) {
  const classes = [
    'btn',
    `btn--${variant}`,
    size !== 'md' ? `btn--${size}` : '',
    block ? 'btn--block' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <button className={classes} disabled={disabled || loading} {...rest}>
      {loading ? <span className="spinner" /> : icon}
      {children}
    </button>
  )
}

// ---- Field / Input -----------------------------------------------------

interface FieldProps {
  label?: string
  required?: boolean
  hint?: string
  error?: string
  children: ReactNode
  style?: CSSProperties
}

export function Field({ label, required, hint, error, children, style }: FieldProps) {
  return (
    <div className="field" style={style}>
      {label && (
        <label className={`field__label${required ? ' field__label--required' : ''}`}>{label}</label>
      )}
      {children}
      {error ? (
        <span className="field__error">{error}</span>
      ) : hint ? (
        <span className="field__hint">{hint}</span>
      ) : null}
    </div>
  )
}

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean
}

export function Input({ invalid, className = '', ...rest }: InputProps) {
  return <input className={`input${invalid ? ' input--error' : ''} ${className}`} {...rest} />
}

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  invalid?: boolean
  options: readonly { value: string; label: string }[]
  placeholder?: string
}

export function Select({ invalid, options, placeholder, className = '', ...rest }: SelectProps) {
  return (
    <select className={`select${invalid ? ' select--error' : ''} ${className}`} {...rest}>
      {placeholder && <option value="">{placeholder}</option>}
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  )
}

/** 只读展示项 —— 用于「确认框」里回显信息 */
export function ReadonlyField({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="field">
      <span className="field__label">{label}</span>
      <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)' }}>{value}</div>
    </div>
  )
}

// ---- Card --------------------------------------------------------------

interface CardProps {
  title?: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
  children: ReactNode
  flush?: boolean
  className?: string
}

export function Card({ title, subtitle, actions, children, flush, className = '' }: CardProps) {
  const hasHeader = title || subtitle || actions
  return (
    <section className={`card ${className}`}>
      {hasHeader && (
        <header className="card__header">
          <div>
            {title && <h2 className="card__title">{title}</h2>}
            {subtitle && <p className="card__subtitle">{subtitle}</p>}
          </div>
          {actions && <div style={{ display: 'flex', gap: 'var(--space-2)' }}>{actions}</div>}
        </header>
      )}
      <div className={`card__body${flush ? ' card__body--flush' : ''}`}>{children}</div>
    </section>
  )
}

// ---- Badge -------------------------------------------------------------

type BadgeTone = 'neutral' | 'brand' | 'success' | 'warning' | 'danger' | 'info'

export function Badge({ tone = 'neutral', children }: { tone?: BadgeTone; children: ReactNode }) {
  return <span className={`badge badge--${tone}`}>{children}</span>
}

/** 状态 → 色调映射（各模块共用，避免色调散落） */
const STATUS_TONES: Record<string, BadgeTone> = {
  AVAILABLE: 'success',
  BORROWED: 'warning',
  RESERVED: 'info',
  LOST: 'danger',
  DAMAGED: 'danger',
  REMOVED: 'neutral',
  ACTIVE: 'success',
  SUSPENDED: 'warning',
  CANCELLED: 'neutral',
  EXPIRED: 'neutral',
  READY: 'info',
  RETURNED: 'neutral',
  OVERDUE: 'danger',
  UNPAID: 'danger',
  PAID: 'success',
}

export function StatusBadge({
  value,
  dictionary,
}: {
  value: string | null | undefined
  dictionary: readonly { value: string; label: string }[]
}) {
  if (!value) return <span style={{ color: 'var(--text-tertiary)' }}>-</span>
  return <Badge tone={STATUS_TONES[value] ?? 'neutral'}>{labelOf(dictionary, value)}</Badge>
}

// ---- Alert -------------------------------------------------------------

export function Alert({
  tone = 'info',
  title,
  children,
}: {
  tone?: 'info' | 'success' | 'warning' | 'danger'
  title?: string
  children?: ReactNode
}) {
  const Icon = tone === 'success' ? IconCheck : tone === 'danger' ? IconAlert : IconInfo
  return (
    <div className={`alert alert--${tone}`}>
      <span className="alert__icon">
        <Icon size={16} />
      </span>
      <div className="alert__body">
        {title && <div className="alert__title">{title}</div>}
        {children}
      </div>
    </div>
  )
}

// ---- Empty -------------------------------------------------------------

export function Empty({
  title = '暂无数据',
  desc,
  action,
}: {
  title?: string
  desc?: string
  action?: ReactNode
}) {
  return (
    <div className="empty">
      <span className="empty__icon">
        <IconInbox size={36} />
      </span>
      <p className="empty__title">{title}</p>
      {desc && <p className="empty__desc">{desc}</p>}
      {action}
    </div>
  )
}

// ---- Skeleton ----------------------------------------------------------

export function Skeleton({ width = '100%', height = 16 }: { width?: string | number; height?: number }) {
  return <div className="skeleton" style={{ width, height }} />
}

export function TableSkeleton({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div style={{ padding: 'var(--space-6)' }}>
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} style={{ display: 'flex', gap: 'var(--space-4)', marginBottom: 'var(--space-4)' }}>
          {Array.from({ length: cols }).map((__, c) => (
            <Skeleton key={c} height={16} width={c === 0 ? '24%' : `${Math.floor(60 / cols)}%`} />
          ))}
        </div>
      ))}
    </div>
  )
}

// ---- Modal -------------------------------------------------------------

export function Modal({
  open,
  title,
  desc,
  onClose,
  footer,
  wide,
  children,
}: {
  open: boolean
  title: string
  desc?: string
  onClose: () => void
  footer?: ReactNode
  wide?: boolean
  children: ReactNode
}) {
  // Esc 关闭 + 锁定背景滚动
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prev
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="modal-overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal${wide ? ' modal--wide' : ''}`} role="dialog" aria-modal="true">
        <header className="modal__header">
          <div>
            <h3 className="modal__title">{title}</h3>
            {desc && <p className="modal__desc">{desc}</p>}
          </div>
          <button className="modal__close" onClick={onClose} aria-label="关闭">
            <IconX size={18} />
          </button>
        </header>
        <div className="modal__body">{children}</div>
        {footer && <footer className="modal__footer">{footer}</footer>}
      </div>
    </div>
  )
}

// ---- Toast -------------------------------------------------------------

export function ToastStack({
  items,
  onDismiss,
}: {
  items: { id: number; tone: 'success' | 'error' | 'info'; title: string; message?: string }[]
  onDismiss: (id: number) => void
}) {
  return (
    <div className="toast-stack">
      {items.map((t) => (
        <div key={t.id} className={`toast toast--${t.tone}`}>
          <span style={{ color: `var(--${t.tone === 'info' ? 'info' : t.tone}-500)`, marginTop: 2 }}>
            {t.tone === 'success' ? <IconCheck size={16} /> : t.tone === 'error' ? <IconAlert size={16} /> : <IconInfo size={16} />}
          </span>
          <div className="toast__content">
            <div className="toast__title">{t.title}</div>
            {t.message && <div className="toast__message">{t.message}</div>}
          </div>
          <button className="modal__close" style={{ width: 24, height: 24 }} onClick={() => onDismiss(t.id)}>
            <IconX size={14} />
          </button>
        </div>
      ))}
    </div>
  )
}

// ---- Stat tile ---------------------------------------------------------

export function StatTile({
  label,
  value,
  tone = 'neutral',
  icon,
}: {
  label: string
  value: ReactNode
  tone?: 'neutral' | 'brand' | 'success' | 'warning' | 'danger'
  icon?: ReactNode
}) {
  const colorMap: Record<string, string> = {
    neutral: 'var(--text-primary)',
    brand: 'var(--brand-600)',
    success: 'var(--success-600)',
    warning: 'var(--warning-600)',
    danger: 'var(--danger-600)',
  }
  return (
    <div
      style={{
        padding: 'var(--space-5)',
        borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--border-default)',
        background: 'var(--bg-surface)',
        boxShadow: 'var(--shadow-xs)',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-2)',
          fontSize: 13,
          color: 'var(--text-tertiary)',
          marginBottom: 'var(--space-2)',
        }}
      >
        {icon}
        {label}
      </div>
      <div style={{ fontSize: 26, fontWeight: 650, color: colorMap[tone], letterSpacing: '-0.02em' }}>
        {value}
      </div>
    </div>
  )
}

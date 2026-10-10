/** 通用工具：日期格式化、金额显示 */

/**
 * 后端统一以 UTC 存储、ISO 字符串返回（`serializers.iso`）。
 * 此处按浏览器本地时区渲染（中国用户即北京时间）。
 */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

/** 距今天数（正数=还有几天，负数=已过期几天） */
export function daysFromNow(value: string | null | undefined): number | null {
  if (!value) return null
  const target = new Date(value)
  if (Number.isNaN(target.getTime())) return null
  const diff = target.getTime() - Date.now()
  return Math.ceil(diff / (1000 * 60 * 60 * 24))
}

/** 金额显示（后端以定点小数字符串返回，如 "12.60"） */
export function formatMoney(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '¥0.00'
  const num = typeof value === 'number' ? value : Number(value)
  if (Number.isNaN(num)) return '¥0.00'
  return `¥${num.toFixed(2)}`
}

/** 把输入转成后端要求的两位定点小数字符串 */
export function toFixedString(value: string | number): string {
  const num = typeof value === 'number' ? value : Number(value)
  if (Number.isNaN(num)) return '0.00'
  return num.toFixed(2)
}

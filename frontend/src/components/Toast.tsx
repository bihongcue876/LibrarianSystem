/** 全局提示 —— 轻量 Toast，无需第三方库 */

import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react'
import { ToastStack } from '@/components/ui'
import { toMessage } from '@/api/client'

type Tone = 'success' | 'error' | 'info'

interface ToastItem {
  id: number
  tone: Tone
  title: string
  message?: string
}

interface ToastApi {
  success: (title: string, message?: string) => void
  error: (title: string, message?: string) => void
  info: (title: string, message?: string) => void
  /** 直接消费一个异常对象，自动转成可读文案 */
  fromError: (error: unknown, title?: string) => void
}

const ToastContext = createContext<ToastApi | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const seq = useRef(0)
  const timers = useRef(new Map<number, number>())

  const dismiss = useCallback((id: number) => {
    // 手动关闭时同时清掉定时器，避免之后触发一次无效 setState
    const timer = timers.current.get(id)
    if (timer !== undefined) {
      window.clearTimeout(timer)
      timers.current.delete(id)
    }
    setItems((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const push = useCallback(
    (tone: Tone, title: string, message?: string) => {
      const id = ++seq.current
      setItems((prev) => [...prev, { id, tone, title, message }])
      const timer = window.setTimeout(() => dismiss(id), tone === 'error' ? 6000 : 3500)
      timers.current.set(id, timer)
    },
    [dismiss],
  )

  const api = useMemo<ToastApi>(
    () => ({
      success: (t, m) => push('success', t, m),
      error: (t, m) => push('error', t, m),
      info: (t, m) => push('info', t, m),
      fromError: (error, title = '操作失败') => push('error', title, toMessage(error)),
    }),
    [push],
  )

  return (
    <ToastContext.Provider value={api}>
      {children}
      <ToastStack items={items} onDismiss={dismiss} />
    </ToastContext.Provider>
  )
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast 必须在 ToastProvider 内使用')
  return ctx
}

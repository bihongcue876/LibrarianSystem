/** 路由守卫：未登录跳登录页；角色不符跳该角色的首页（权限最终由后端裁决，BR-042） */

import { Navigate, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useAuth } from '@/auth/AuthContext'
import type { Role } from '@/api/types'

const HOME: Record<Role, string> = {
  READER: '/catalog',
  LIBRARIAN: '/circulation',
  SYSTEM_ADMIN: '/admin/stats',
}

export function RequireAuth({ children, roles }: { children: ReactNode; roles?: Role[] }) {
  const { account, initializing } = useAuth()
  const location = useLocation()

  if (initializing) {
    return (
      <div className="center-screen">
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
          <span className="spinner spinner--lg" style={{ color: 'var(--brand-500)' }} />
          <span className="muted">正在恢复登录状态…</span>
        </div>
      </div>
    )
  }

  if (!account) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
  }

  if (roles && !roles.includes(account.role)) {
    return <Navigate to={HOME[account.role]} replace />
  }

  return <>{children}</>
}

/** 已登录用户访问 /login 时，直接送回其首页 */
export function RedirectIfAuthed({ children }: { children: ReactNode }) {
  const { account, initializing } = useAuth()

  if (initializing) return null
  if (account) return <Navigate to={HOME[account.role]} replace />
  return <>{children}</>
}

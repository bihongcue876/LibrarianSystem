/** 应用路由 —— 按角色分流，权限最终由后端守卫裁决 */

import { Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { AppLayout } from '@/layouts/AppLayout'
import { RedirectIfAuthed, RequireAuth } from '@/auth/guards'
import { LoginPage } from '@/pages/LoginPage'
import { CatalogPage } from '@/pages/reader/CatalogPage'
import { MyLoansPage } from '@/pages/reader/MyLoansPage'
import { CirculationPage } from '@/pages/staff/CirculationPage'
import { ReaderLookupPage } from '@/pages/staff/ReaderLookupPage'
import { FinesPage } from '@/pages/staff/FinesPage'
import { CardsPage } from '@/pages/admin/CardsPage'
import { AdminCatalogPage } from '@/pages/admin/AdminCatalogPage'
import { PoliciesPage } from '@/pages/admin/PoliciesPage'
import { AccountsPage } from '@/pages/admin/AccountsPage'
import { StatsPage } from '@/pages/admin/StatsPage'
import { Button, Card } from '@/components/ui'
import { roleHome } from '@/auth/guards'
import { useAuth } from '@/auth/AuthContext'

const ALL = ['READER', 'LIBRARIAN', 'SYSTEM_ADMIN'] as const
const STAFF = ['LIBRARIAN', 'SYSTEM_ADMIN'] as const
const ADMIN = ['SYSTEM_ADMIN'] as const

function NotFoundPage() {
  const { account } = useAuth()
  const navigate = useNavigate()
  return (
    <div className="center-screen">
      <Card title="页面不存在">
        <div className="stack">
          <p className="muted">你访问的页面不存在，或已被移动。</p>
          <Button variant="primary" onClick={() => navigate(account ? '/' : '/login')}>
            返回首页
          </Button>
        </div>
      </Card>
    </div>
  )
}

export function AppRoutes() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <RedirectIfAuthed>
            <LoginPage />
          </RedirectIfAuthed>
        }
      />

      <Route
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        {/* 全角色可访问 */}
        <Route
          path="/catalog"
          element={
            <RequireAuth roles={[...ALL]}>
              <CatalogPage />
            </RequireAuth>
          }
        />

        {/* 读者专属 */}
        <Route
          path="/my"
          element={
            <RequireAuth roles={['READER']}>
              <MyLoansPage />
            </RequireAuth>
          }
        />

        {/* 员工（馆员 + 管理员） */}
        <Route
          path="/circulation"
          element={
            <RequireAuth roles={[...STAFF]}>
              <CirculationPage />
            </RequireAuth>
          }
        />
        <Route
          path="/reader-lookup"
          element={
            <RequireAuth roles={[...STAFF]}>
              <ReaderLookupPage />
            </RequireAuth>
          }
        />
        <Route
          path="/fines"
          element={
            <RequireAuth roles={[...STAFF]}>
              <FinesPage />
            </RequireAuth>
          }
        />

        {/* 仅系统管理员 */}
        <Route
          path="/admin/cards"
          element={
            <RequireAuth roles={[...ADMIN]}>
              <CardsPage />
            </RequireAuth>
          }
        />
        <Route
          path="/admin/catalog"
          element={
            <RequireAuth roles={[...ADMIN]}>
              <AdminCatalogPage />
            </RequireAuth>
          }
        />
        <Route
          path="/admin/policies"
          element={
            <RequireAuth roles={[...ADMIN]}>
              <PoliciesPage />
            </RequireAuth>
          }
        />
        <Route
          path="/admin/accounts"
          element={
            <RequireAuth roles={[...ADMIN]}>
              <AccountsPage />
            </RequireAuth>
          }
        />
        <Route
          path="/admin/stats"
          element={
            <RequireAuth roles={[...ADMIN]}>
              <StatsPage />
            </RequireAuth>
          }
        />
      </Route>

      {/* 根路径按其角色跳转 */}
      <Route path="/" element={<RootRedirect />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}

function RootRedirect() {
  const { account, initializing } = useAuth()

  if (initializing) return null
  if (!account) return <Navigate to="/login" replace />

  return <Navigate to={roleHome(account.role)} replace />
}

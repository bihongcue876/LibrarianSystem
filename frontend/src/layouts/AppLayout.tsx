/** 侧边栏 + 顶栏外壳。导航项按角色过滤 —— 界面只呈现，权限由后端守卫（BR-042）。 */

import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '@/auth/AuthContext'
import {
  IconBook,
  IconCard,
  IconChart,
  IconClock,
  IconLogout,
  IconMenu,
  IconSearch,
  IconSettings,
  IconSwap,
  IconUser,
  IconUsers,
} from '@/components/icons'
import type { Role } from '@/api/types'

interface NavEntry {
  to: string
  label: string
  icon: React.ReactNode
  roles: Role[]
  group: string
  /** 路由匹配时用于高亮的额外前缀 */
  match?: string[]
}

const NAV: NavEntry[] = [
  { to: '/catalog', label: '图书检索', icon: <IconSearch />, roles: ['READER', 'LIBRARIAN', 'SYSTEM_ADMIN'], group: '读者服务' },
  { to: '/my', label: '我的借阅', icon: <IconClock />, roles: ['READER'], group: '读者服务' },

  { to: '/circulation', label: '借还流通', icon: <IconSwap />, roles: ['LIBRARIAN', 'SYSTEM_ADMIN'], group: '流通业务' },
  { to: '/reader-lookup', label: '读者查询', icon: <IconUsers />, roles: ['LIBRARIAN', 'SYSTEM_ADMIN'], group: '流通业务' },
  { to: '/fines', label: '罚款收缴', icon: <IconCard />, roles: ['LIBRARIAN', 'SYSTEM_ADMIN'], group: '流通业务' },

  { to: '/admin/cards', label: '借阅证管理', icon: <IconCard />, roles: ['SYSTEM_ADMIN'], group: '系统管理' },
  { to: '/admin/catalog', label: '书目与馆藏', icon: <IconBook />, roles: ['SYSTEM_ADMIN'], group: '系统管理' },
  { to: '/admin/policies', label: '规则维护', icon: <IconSettings />, roles: ['SYSTEM_ADMIN'], group: '系统管理' },
  { to: '/admin/accounts', label: '账号管理', icon: <IconUser />, roles: ['SYSTEM_ADMIN'], group: '系统管理' },
  { to: '/admin/stats', label: '馆藏统计', icon: <IconChart />, roles: ['SYSTEM_ADMIN'], group: '系统管理' },
]

const ROLE_LABEL: Record<Role, string> = {
  READER: '读者',
  LIBRARIAN: '图书管理员',
  SYSTEM_ADMIN: '系统管理员',
}

/** 路由 → 顶栏标题 */
const TITLES: { match: string; title: string; subtitle: string }[] = [
  { match: '/catalog', title: '图书检索', subtitle: '按关键词、类型筛选馆藏，查看可借状态' },
  { match: '/my', title: '我的借阅', subtitle: '当前借阅、历史记录、预约与罚款' },
  { match: '/circulation', title: '借还流通', subtitle: '代理借书与凭条码还书，含前置校验' },
  { match: '/reader-lookup', title: '读者查询', subtitle: '按读者编号查询其借阅与罚款明细' },
  { match: '/fines', title: '罚款收缴', subtitle: '线下收费后在系统中标记已缴' },
  { match: '/admin/cards', title: '借阅证管理', subtitle: '办证、挂失、解挂、注销与恢复' },
  { match: '/admin/catalog', title: '书目与馆藏', subtitle: '题录与副本的增删、状态标记' },
  { match: '/admin/policies', title: '规则维护', subtitle: '借阅额度与罚款标准（仅影响之后的新业务）' },
  { match: '/admin/accounts', title: '账号管理', subtitle: '图书管理员账号与密码重置' },
  { match: '/admin/stats', title: '馆藏统计', subtitle: '题录、副本总量与分布' },
]

export function AppLayout() {
  const { account, logout } = useAuth()
  const location = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)

  // 路由切换时收起移动端侧边栏
  useEffect(() => {
    setMobileOpen(false)
  }, [location.pathname])

  if (!account) return null

  const visible = NAV.filter((item) => item.roles.includes(account.role))
  const groups = Array.from(new Set(visible.map((item) => item.group)))
  const heading =
    TITLES.find((t) => location.pathname.startsWith(t.match)) ?? {
      title: '图书管理系统',
      subtitle: '',
    }

  const initials = account.name?.slice(0, 1) || account.username.slice(0, 1).toUpperCase()

  return (
    <div className="app-shell">
      <aside className={`sidebar${mobileOpen ? ' sidebar--open' : ''}`}>
        <div className="sidebar__brand">
          <span className="sidebar__logo">
            <IconBook size={20} />
          </span>
          <div>
            <div className="sidebar__name">图书管理系统</div>
            <div className="sidebar__tagline">Library Management</div>
          </div>
        </div>

        <nav className="sidebar__nav">
          {groups.map((group) => (
            <div key={group}>
              <div className="sidebar__group">{group}</div>
              {visible
                .filter((item) => item.group === group)
                .map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) => `nav-item${isActive ? ' nav-item--active' : ''}`}
                  >
                    <span className="nav-item__icon">{item.icon}</span>
                    {item.label}
                  </NavLink>
                ))}
            </div>
          ))}
        </nav>

        <div className="sidebar__footer">
          <div className="account-chip">
            <span className="account-chip__avatar">{initials}</span>
            <div className="account-chip__info">
              <div className="account-chip__name">{account.name || account.username}</div>
              <div className="account-chip__role">{ROLE_LABEL[account.role]}</div>
            </div>
            <button className="modal__close" style={{ width: 28, height: 28 }} onClick={logout} title="退出登录">
              <IconLogout size={16} />
            </button>
          </div>
        </div>
      </aside>

      <div className="app-main">
        <header className="topbar">
          <div className="row">
            <button
              className="modal__close mobile-only"
              onClick={() => setMobileOpen((v) => !v)}
              aria-label="展开导航"
            >
              <IconMenu size={20} />
            </button>
            <div>
              <h1 className="topbar__title">{heading.title}</h1>
              {heading.subtitle && <p className="topbar__subtitle">{heading.subtitle}</p>}
            </div>
          </div>
          <div className="topbar__actions">
            <span className={`badge badge--${account.role === 'SYSTEM_ADMIN' ? 'brand' : account.role === 'LIBRARIAN' ? 'info' : 'neutral'}`}>
              {ROLE_LABEL[account.role]}
            </span>
          </div>
        </header>

        <main className="app-content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

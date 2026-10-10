/**
 * 登录 / 注册页。
 *
 * 关键点：**登录必须指定角色入口**（`LoginRequest.role` 后端默认 READER）。
 * 三类账号可同名（BR-044），故入口必须显式选择——这也是后端规格的要求。
 */

import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Alert, Button, Field, Input, Select } from '@/components/ui'
import { useToast } from '@/components/Toast'
import { IconBook, IconClock, IconSearch, IconSwap } from '@/components/icons'
import { useAuth } from '@/auth/AuthContext'
import { roleHome } from '@/auth/guards'
import { authApi } from '@/api/endpoints'
import { toMessage } from '@/api/client'
import { READER_TYPES } from '@/api/types'
import type { Role } from '@/api/types'

type Mode = 'login' | 'register'

const ROLE_OPTIONS = [
  { value: 'READER', label: '读者' },
  { value: 'LIBRARIAN', label: '图书管理员' },
  { value: 'SYSTEM_ADMIN', label: '系统管理员' },
] as const

export function LoginPage() {
  const { login } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()

  const [mode, setMode] = useState<Mode>('login')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // 登录表单
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<Role>('READER')

  // 注册表单
  const [regName, setRegName] = useState('')
  const [regDepartment, setRegDepartment] = useState('')
  const [regType, setRegType] = useState('UNDERGRADUATE')

  const handleLogin = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const account = await login({ username: username.trim(), password, role })
      toast.success('登录成功', `欢迎回来，${account.name || account.username}`)
      navigate(roleHome(account.role), { replace: true })
    } catch (err) {
      setError(toMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  const handleRegister = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const account = await authApi.register({
        username: username.trim(),
        password,
        name: regName.trim(),
        department: regDepartment.trim(),
        reader_type: regType,
      })
      toast.success('注册成功', `${account.name}，请登录后到馆办理借阅证`)
      setMode('login')
      setRole('READER')
      setRegName('')
      setRegDepartment('')
    } catch (err) {
      setError(toMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="auth-page">
      <section className="auth-hero">
        <div className="auth-hero__content">
          <div className="auth-hero__brand">
            <span className="auth-hero__logo">
              <IconBook size={22} />
            </span>
            AI时代图书管理系统
          </div>
          <h1 className="auth-hero__title">
            让每一次
            <br />
            借阅都有据可循
          </h1>
          <p className="auth-hero__desc">
            覆盖读者管理、借阅证、书目馆藏、借还流通、预约排队、超期罚款与规则维护的完整流通管理系统。
          </p>
        </div>

        <div className="auth-hero__features">
          <div className="auth-feature">
            <span className="auth-feature__icon">
              <IconSearch size={16} />
            </span>
            <div>
              <div className="auth-feature__label">检索与预约</div>
              <div className="auth-feature__desc">按关键词与类型筛选，无可借副本时可排队预约</div>
            </div>
          </div>
          <div className="auth-feature">
            <span className="auth-feature__icon">
              <IconSwap size={16} />
            </span>
            <div>
              <div className="auth-feature__label">借还与续借</div>
              <div className="auth-feature__desc">馆员代理借书，六项前置校验；读者可自助续借</div>
            </div>
          </div>
          <div className="auth-feature">
            <span className="auth-feature__icon">
              <IconClock size={16} />
            </span>
            <div>
              <div className="auth-feature__label">超期与罚款</div>
              <div className="auth-feature__desc">宽限期与封顶自动计算，金额精确到分</div>
            </div>
          </div>
        </div>
      </section>

      <section className="auth-panel">
        <div className="auth-form">
          <h2 className="auth-form__title">{mode === 'login' ? '登录' : '读者注册'}</h2>
          <p className="auth-form__desc">
            {mode === 'login'
              ? '请选择身份入口后登录，三类账号可同名'
              : '注册后需到馆办理借阅证才能借书'}
          </p>

          <div className="auth-tabs" role="tablist">
            <button
              role="tab"
              className={`auth-tab${mode === 'login' ? ' auth-tab--active' : ''}`}
              onClick={() => {
                setMode('login')
                setError(null)
              }}
            >
              登录
            </button>
            <button
              role="tab"
              className={`auth-tab${mode === 'register' ? ' auth-tab--active' : ''}`}
              onClick={() => {
                setMode('register')
                setError(null)
              }}
            >
              读者注册
            </button>
            <button
              role="tab"
              className="auth-tab"
              onClick={() => window.open('/docs', '_blank', 'noopener,noreferrer')}
              title="打开后端接口文档"
            >
              API 文档
            </button>
          </div>

          {error && (
            <div style={{ marginBottom: 'var(--space-5)' }}>
              <Alert tone="danger" title="操作未完成">
                {error}
              </Alert>
            </div>
          )}

          {mode === 'login' ? (
            <form className="auth-form__fields" onSubmit={handleLogin}>
              <Field label="身份入口" required>
                <Select
                  value={role}
                  onChange={(e) => setRole(e.target.value as Role)}
                  options={ROLE_OPTIONS}
                />
              </Field>

              <Field label="用户名" required>
                <Input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="请输入用户名"
                  autoComplete="username"
                  required
                  minLength={3}
                />
              </Field>

              <Field label="密码" required>
                <Input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="请输入密码"
                  autoComplete="current-password"
                  required
                  minLength={6}
                />
              </Field>

              <Button type="submit" variant="primary" size="lg" block loading={submitting}>
                登录
              </Button>
            </form>
          ) : (
            <form className="auth-form__fields" onSubmit={handleRegister}>
              <Field label="用户名" required hint="3~32 位，仅限字母、数字与下划线">
                <Input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="如 zhangsan"
                  required
                  minLength={3}
                  pattern="[A-Za-z0-9_]+"
                />
              </Field>

              <Field label="密码" required hint="6~24 位">
                <Input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="请设置密码"
                  required
                  minLength={6}
                  maxLength={24}
                />
              </Field>

              <Field label="姓名" required>
                <Input
                  value={regName}
                  onChange={(e) => setRegName(e.target.value)}
                  placeholder="真实姓名"
                  required
                />
              </Field>

              <Field label="院系 / 单位" required>
                <Input
                  value={regDepartment}
                  onChange={(e) => setRegDepartment(e.target.value)}
                  placeholder="如 计算机学院"
                  required
                />
              </Field>

              <Field label="读者类型" required hint="决定可借册数与借期">
                <Select
                  value={regType}
                  onChange={(e) => setRegType(e.target.value)}
                  options={READER_TYPES}
                />
              </Field>

              <Button type="submit" variant="primary" size="lg" block loading={submitting}>
                注册
              </Button>
            </form>
          )}

          <div className="auth-hint">
            <strong>首次使用提示：</strong>
            <br />
            系统管理员账号由后端初始化脚本创建（
            <code>init_db.py --admin-username admin</code>）。读者注册后需由系统管理员办理借阅证，
            方可借书（<code>BR-012</code>）。馆员账号由系统管理员在「账号管理」中添加。
          </div>
        </div>
      </section>
    </div>
  )
}

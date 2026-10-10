/**
 * 账号管理（UC-206 / UC-207 + 密码重置）—— 仅系统管理员。
 *
 * 系统不提供自助找回密码（Q-05 裁定），因此重置密码入口只在管理员侧。
 */

import { useCallback, useEffect, useState } from 'react'
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
  TableSkeleton,
} from '@/components/ui'
import { IconPlus, IconTrash, IconUser } from '@/components/icons'
import { useToast } from '@/components/Toast'
import { authApi } from '@/api/endpoints'
import { toMessage } from '@/api/client'
import type { Account } from '@/api/types'

const EMPTY_FORM = { username: '', password: '', name: '' }

/** 与后端 `AddLibrarianRequest` 一致的客户端校验 */
const USERNAME_PATTERN = /^[A-Za-z0-9_]+$/

export function AccountsPage() {
  const toast = useToast()

  const [librarians, setLibrarians] = useState<Account[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [includeDeleted, setIncludeDeleted] = useState(false)

  const [addModal, setAddModal] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)

  const [deleteTarget, setDeleteTarget] = useState<Account | null>(null)
  const [resetTarget, setResetTarget] = useState<Account | null>(null)
  const [resetForm, setResetForm] = useState<{ new_password: string }>({ new_password: '' })
  const [acting, setActing] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setLibrarians(await authApi.listLibrarians(includeDeleted))
    } catch (err) {
      setError(toMessage(err))
    } finally {
      setLoading(false)
    }
  }, [includeDeleted])

  useEffect(() => {
    void load()
  }, [load])

  const addLibrarian = async () => {
    if (!form.username.trim() || !form.password || !form.name.trim()) {
      toast.error('请填写完整信息', '用户名、密码与姓名为必填项')
      return
    }
    if (!USERNAME_PATTERN.test(form.username.trim()) || form.username.trim().length < 3) {
      toast.error('用户名格式不正确', '3~32 位，仅限字母、数字与下划线')
      return
    }
    if (form.password.length < 6 || form.password.length > 24) {
      toast.error('密码长度不正确', '长度须为 6~24 位')
      return
    }
    setSaving(true)
    try {
      await authApi.addLibrarian({
        username: form.username.trim(),
        password: form.password,
        name: form.name.trim(),
      })
      toast.success('馆员账号已创建', `用户名 ${form.username.trim()}`)
      setAddModal(false)
      setForm(EMPTY_FORM)
      await load()
    } catch (err) {
      toast.fromError(err, '创建失败')
    } finally {
      setSaving(false)
    }
  }

  const removeLibrarian = async () => {
    if (!deleteTarget) return
    setActing(true)
    try {
      await authApi.deleteLibrarian(deleteTarget.account_id)
      toast.success('馆员已删除', `用户名 ${deleteTarget.username}`)
      setDeleteTarget(null)
      await load()
    } catch (err) {
      toast.fromError(err, '删除失败')
    } finally {
      setActing(false)
    }
  }

  const resetPassword = async () => {
    if (!resetTarget) return
    if (resetForm.new_password.length < 6) {
      toast.error('密码过短', '长度须为 6~24 位')
      return
    }
    setActing(true)
    try {
      // 本页列表只包含馆员账号，重置目标固定为 LIBRARIAN 入口
      await authApi.resetPassword(resetTarget.account_id, resetForm.new_password, 'LIBRARIAN')
      toast.success('密码已重置', `账号 ${resetTarget.username}，请告知本人新密码`)
      setResetTarget(null)
      setResetForm({ new_password: '' })
    } catch (err) {
      toast.fromError(err, '重置失败')
    } finally {
      setActing(false)
    }
  }

  return (
    <div className="page">
      {error && (
        <Alert tone="danger" title="加载失败">
          {error}
        </Alert>
      )}

      <Card
        title="图书管理员账号"
        subtitle="馆员可办理借还与罚款收缴，但不能管理书目、规则与账号"
        actions={
          <>
            <label className="row" style={{ gap: 'var(--space-2)', cursor: 'pointer', fontSize: 13 }}>
              <input
                type="checkbox"
                checked={includeDeleted}
                onChange={(e) => setIncludeDeleted(e.target.checked)}
                style={{ width: 16, height: 16, accentColor: 'var(--brand-600)' }}
              />
              含已删除
            </label>
            <Button
              size="sm"
              variant="primary"
              icon={<IconPlus size={15} />}
              onClick={() => setAddModal(true)}
            >
              添加馆员
            </Button>
          </>
        }
        flush
      >
        {loading ? (
          <TableSkeleton rows={4} cols={4} />
        ) : librarians.length === 0 ? (
          <Empty
            title="暂无图书管理员账号"
            desc="添加馆员后，对方即可登录并办理借还流通业务。"
            action={
              <Button variant="primary" icon={<IconPlus size={16} />} onClick={() => setAddModal(true)}>
                添加馆员
              </Button>
            }
          />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>姓名</th>
                  <th>用户名</th>
                  <th>编号</th>
                  <th>角色</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {librarians.map((lib) => (
                  <tr key={lib.account_id}>
                    <td style={{ fontWeight: 550 }}>
                      <span className="row" style={{ gap: 'var(--space-2)' }}>
                        <span
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            width: 26,
                            height: 26,
                            borderRadius: '50%',
                            background: 'var(--brand-100)',
                            color: 'var(--brand-700)',
                            fontSize: 12,
                            fontWeight: 600,
                          }}
                        >
                          {lib.name?.slice(0, 1) || <IconUser size={13} />}
                        </span>
                        {lib.name}
                      </span>
                    </td>
                    <td className="mono">{lib.username}</td>
                    <td className="mono muted">#{lib.account_id}</td>
                    <td>
                      <Badge tone="info">图书管理员</Badge>
                    </td>
                    <td>
                      <div className="table__actions">
                        <Button
                          size="sm"
                          onClick={() => {
                            setResetTarget(lib)
                            setResetForm({ new_password: '' })
                          }}
                        >
                          重置密码
                        </Button>
                        <Button
                          size="sm"
                          variant="danger-ghost"
                          icon={<IconTrash size={14} />}
                          onClick={() => setDeleteTarget(lib)}
                        >
                          删除
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Alert tone="info" title="关于读者账号与系统管理员">
        读者可自行注册（登录页「读者注册」），无需管理员创建；读者的密码同样可由本页重置——
        只需在重置时把「目标角色」选为「读者」并填写其编号。
        系统管理员账号由后端初始化脚本创建，不能在界面中增删（
        <span className="mono">BR-043</span>）。
      </Alert>

      {/* 添加馆员 */}
      <Modal
        open={addModal}
        title="添加图书管理员"
        desc="新账号可立即登录，仅具备流通业务权限"
        onClose={() => setAddModal(false)}
        footer={
          <>
            <Button onClick={() => setAddModal(false)}>取消</Button>
            <Button variant="primary" loading={saving} onClick={() => void addLibrarian()}>
              创建账号
            </Button>
          </>
        }
      >
        <div className="stack">
          <Field label="用户名" required hint="3~32 位，仅限字母、数字与下划线">
            <Input
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              placeholder="如 lib001"
              className="mono"
              pattern="[A-Za-z0-9_]+"
            />
          </Field>

          <Field label="初始密码" required hint="6~24 位，请线下告知本人">
            <Input
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              placeholder="设置初始密码"
              minLength={6}
              maxLength={24}
            />
          </Field>

          <Field label="姓名" required>
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="真实姓名"
            />
          </Field>
        </div>
      </Modal>

      {/* 删除馆员 */}
      <Modal
        open={deleteTarget !== null}
        title="确认删除馆员"
        onClose={() => setDeleteTarget(null)}
        footer={
          <>
            <Button onClick={() => setDeleteTarget(null)}>取消</Button>
            <Button variant="danger" loading={acting} onClick={() => void removeLibrarian()}>
              确认删除
            </Button>
          </>
        }
      >
        {deleteTarget && (
          <div className="stack">
            <ReadonlyField label="姓名" value={deleteTarget.name} />
            <ReadonlyField
              label="用户名"
              value={<span className="mono">{deleteTarget.username}</span>}
            />
            <Alert tone="warning" title="软删除">
              该账号将无法登录，但历史操作记录保留。
              系统管理员之间不可互相删除（<span className="mono">BR-043</span>）。
            </Alert>
          </div>
        )}
      </Modal>

      {/* 重置密码 */}
      <Modal
        open={resetTarget !== null}
        title="重置账号密码"
        desc="系统不提供自助找回密码，需由管理员协助"
        onClose={() => setResetTarget(null)}
        footer={
          <>
            <Button onClick={() => setResetTarget(null)}>取消</Button>
            <Button variant="primary" loading={acting} onClick={() => void resetPassword()}>
              确认重置
            </Button>
          </>
        }
      >
        {resetTarget && (
          <div className="stack">
            <ReadonlyField
              label="目标账号"
              value={`${resetTarget.name}（${resetTarget.username}）`}
            />
            <ReadonlyField
              label="账号编号"
              value={<span className="mono">#{resetTarget.account_id}</span>}
            />

            <ReadonlyField label="目标角色" value="图书管理员（LIBRARIAN）" />

            <Field label="新密码" required hint="6~24 位，重置后请线下告知本人">
              <Input
                type="password"
                value={resetForm.new_password}
                onChange={(e) => setResetForm({ ...resetForm, new_password: e.target.value })}
                placeholder="设置新密码"
                minLength={6}
                maxLength={24}
              />
            </Field>
          </div>
        )}
      </Modal>
    </div>
  )
}

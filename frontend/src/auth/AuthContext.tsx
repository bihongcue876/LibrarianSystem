/**
 * 认证上下文 —— 登录态、当前账号、登录/登出操作。
 *
 * 登录后立即调用 `/api/auth/me` 拉取权威账号信息（而不是只信 token 载荷），
 * 这样刷新页面后角色与姓名依然准确。
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { ApiError, accountStore, setUnauthorizedHandler, tokenStore } from '@/api/client'
import { authApi } from '@/api/endpoints'
import type { Account, LoginRequest } from '@/api/types'

interface AuthState {
  account: Account | null
  /** 首次挂载时校验本地 token 是否仍有效，期间为 true */
  initializing: boolean
  login: (credentials: LoginRequest) => Promise<Account>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [account, setAccount] = useState<Account | null>(() => accountStore.get<Account>())
  const [initializing, setInitializing] = useState(true)

  const logout = useCallback(() => {
    tokenStore.clear()
    setAccount(null)
  }, [])

  // 任意请求返回 401 时统一登出
  useEffect(() => {
    setUnauthorizedHandler(logout)
    return () => setUnauthorizedHandler(() => {})
  }, [logout])

  // 启动时用本地 token 换取权威账号信息
  useEffect(() => {
    let cancelled = false
    const bootstrap = async () => {
      if (!tokenStore.get()) {
        setInitializing(false)
        return
      }
      try {
        const me = await authApi.me()
        if (cancelled) return
        accountStore.set(me)
        setAccount(me)
      } catch (err) {
        if (cancelled) return
        // 仅在凭据确实失效（401）时登出；网络故障等不该清掉本地有效 token
        if (err instanceof ApiError && err.status === 401) logout()
      } finally {
        if (!cancelled) setInitializing(false)
      }
    }
    void bootstrap()
    return () => {
      cancelled = true
    }
  }, [logout])

  const login = useCallback(async (credentials: LoginRequest) => {
    const token = await authApi.login(credentials)
    tokenStore.set(token.access_token)
    accountStore.set({
      account_id: token.account_id,
      username: token.username,
      name: token.username,
      role: token.role,
    })
    // 用 me 覆盖为权威资料（姓名、读者类型、院系）
    const me = await authApi.me()
    accountStore.set(me)
    setAccount(me)
    return me
  }, [])

  const value = useMemo<AuthState>(
    () => ({ account, initializing, login, logout }),
    [account, initializing, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth 必须在 AuthProvider 内使用')
  return ctx
}

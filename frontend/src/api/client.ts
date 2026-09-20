/**
 * HTTP 客户端 —— 统一处理 JWT 注入、错误码解包、401 自动登出。
 *
 * 后端错误体格式固定为 `{"error": {"code", "message", "detail"}}`
 * （见 `backend/app/main.py` 的异常处理器），此处统一转换成 `ApiError`。
 */

const TOKEN_KEY = 'library.token'
const ACCOUNT_KEY = 'library.account'

/** 后端业务异常 —— 携带 HTTP 状态与业务错误码，供界面精确提示 */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly detail: Record<string, unknown>

  constructor(status: number, code: string, message: string, detail: Record<string, unknown> = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.detail = detail
  }
}

/** 网络层失败（服务未启动、断网等） */
export class NetworkError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'NetworkError'
  }
}

export const tokenStore = {
  get(): string | null {
    return localStorage.getItem(TOKEN_KEY)
  },
  set(token: string): void {
    localStorage.setItem(TOKEN_KEY, token)
  },
  clear(): void {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(ACCOUNT_KEY)
  },
}

export const accountStore = {
  get<T>(): T | null {
    const raw = localStorage.getItem(ACCOUNT_KEY)
    if (!raw) return null
    try {
      return JSON.parse(raw) as T
    } catch {
      return null
    }
  },
  set(account: unknown): void {
    localStorage.setItem(ACCOUNT_KEY, JSON.stringify(account))
  },
}

/** 401 时的全局回调（由 AuthProvider 注册），用于清理登录态并跳回登录页 */
let onUnauthorized: (() => void) | null = null
export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  query?: Record<string, string | number | boolean | undefined | null>
  /** 跳过 Authorization 头（登录、注册等公开接口） */
  anonymous?: boolean
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  if (!query) return path
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue
    params.append(key, String(value))
  }
  const qs = params.toString()
  return qs ? `${path}?${qs}` : path
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, query, anonymous = false } = options

  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (!anonymous) {
    const token = tokenStore.get()
    if (token) headers['Authorization'] = `Bearer ${token}`
  }

  let response: Response
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new NetworkError('无法连接后端服务，请确认它已在 127.0.0.1:8000 启动')
  }

  // 204 / 空响应
  if (response.status === 204) return undefined as T
  const text = await response.text()
  const payload = text ? safeParse(text) : null

  if (!response.ok) {
    // 统一错误体；若后端返回了非预期结构（如 FastAPI 默认 detail），做兜底
    const err = payload && typeof payload === 'object' && 'error' in payload ? (payload as any).error : null
    const code = err?.code ?? `HTTP_${response.status}`
    const message = err?.message ?? defaultMessage(response.status)
    const detail = err?.detail ?? {}

    if (response.status === 401) {
      tokenStore.clear()
      onUnauthorized?.()
    }
    throw new ApiError(response.status, code, message, detail)
  }

  return payload as T
}

function safeParse(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

function defaultMessage(status: number): string {
  switch (status) {
    case 400:
      return '请求不被接受'
    case 401:
      return '未登录或登录已过期'
    case 403:
      return '无权执行该操作'
    case 404:
      return '资源不存在'
    case 409:
      return '与现有数据冲突'
    case 422:
      return '请求参数校验失败'
    default:
      return `请求失败（HTTP ${status}）`
  }
}

/**
 * 提取 422 校验错误的可读信息。
 * FastAPI 的 detail.errors 形如 `[{loc: ["body","card_no"], msg: "..."}]`
 */
export function describeValidationError(error: ApiError): string {
  const errors = (error.detail as { errors?: { loc?: unknown[]; msg?: string }[] }).errors
  if (!Array.isArray(errors) || errors.length === 0) return error.message
  return errors
    .map((e) => {
      const field = Array.isArray(e.loc) ? e.loc.filter((x) => x !== 'body').join('.') : ''
      return field ? `${field}: ${e.msg ?? '格式不正确'}` : (e.msg ?? '格式不正确')
    })
    .join('；')
}

/** 把任意异常转成用户可读文案 */
export function toMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.status === 422 ? describeValidationError(error) : error.message
  }
  if (error instanceof NetworkError) return error.message
  if (error instanceof Error) return error.message
  return '发生未知错误'
}

/**
 * 领域类型定义 —— 严格对齐后端 `app/domain/enums/` 与各 schemas。
 * 后端枚举取值单一来源，此处仅做镜像，不自行发明取值。
 */

// ---- 枚举（对应 backend/app/domain/enums/） --------------------------

export const READER_TYPES = [
  { value: 'COLLEGE', label: '专科生' },
  { value: 'UNDERGRADUATE', label: '本科生' },
  { value: 'GRADUATE', label: '研究生' },
  { value: 'DOCTOR', label: '博士生' },
  { value: 'TEACHER', label: '教师' },
] as const

export const ITEM_TYPES = [
  { value: 'CHINESE_BOOK', label: '中文图书' },
  { value: 'FOREIGN_BOOK', label: '外文图书' },
  { value: 'CHINESE_MAGAZINE', label: '中文杂志' },
  { value: 'FOREIGN_MAGAZINE', label: '外文杂志' },
  { value: 'THESIS', label: '论文' },
] as const

export const ITEM_STATUS = [
  { value: 'AVAILABLE', label: '可借' },
  { value: 'BORROWED', label: '已借出' },
  { value: 'RESERVED', label: '已预留' },
  { value: 'LOST', label: '丢失' },
  { value: 'DAMAGED', label: '破损' },
  { value: 'REMOVED', label: '已下架' },
] as const

export const CARD_STATUS = [
  { value: 'ACTIVE', label: '有效' },
  { value: 'SUSPENDED', label: '挂失' },
  { value: 'CANCELLED', label: '已注销' },
] as const

export const RESERVATION_STATUS = [
  { value: 'ACTIVE', label: '排队中' },
  { value: 'READY', label: '待借取' },
  { value: 'EXPIRED', label: '已失效' },
  { value: 'CANCELLED', label: '已取消' },
] as const

export type Role = 'READER' | 'LIBRARIAN' | 'SYSTEM_ADMIN'
export type ItemStatus = (typeof ITEM_STATUS)[number]['value']
export type ItemType = (typeof ITEM_TYPES)[number]['value']
export type CardStatusValue = (typeof CARD_STATUS)[number]['value']
export type ReservationStatusValue = (typeof RESERVATION_STATUS)[number]['value']

/** 枚举值 → 中文标签（未命中时原样返回，避免界面出现空白） */
export function labelOf(
  list: readonly { value: string; label: string }[],
  value: string | null | undefined,
): string {
  if (!value) return '-'
  return list.find((x) => x.value === value)?.label ?? value
}

// ---- 账号与鉴权 ------------------------------------------------------

export interface LoginRequest {
  username: string
  password: string
  role: Role
}

export interface TokenResponse {
  access_token: string
  token_type: string
  role: Role
  account_id: number
  username: string
  expires_at?: string | null
}

export interface Account {
  account_id: number
  username: string
  name: string
  role: Role
  reader_type?: string | null
  department?: string | null
}

export interface RegisterReaderRequest {
  username: string
  password: string
  name: string
  department: string
  reader_type: string
}

// ---- 图书检索 --------------------------------------------------------

export interface BookListItem {
  title_id: number
  title: string
  author?: string | null
  isbn?: string | null
  publisher?: string | null
  publish_year?: number | null
  item_type?: string | null
  language?: string | null
  is_deleted: boolean
  total_items: number
  available_items: number
}

export interface BookListResponse {
  page: number
  page_size: number
  total: number
  items: BookListItem[]
}

export interface BookQuery {
  keyword?: string
  item_type?: string
  available_only?: boolean
  page?: number
  page_size?: number
}

// ---- 书目与馆藏 ------------------------------------------------------

export interface AddBookTitleRequest {
  title: string
  author?: string
  isbn?: string | null
  publisher?: string | null
  publish_year?: number | null
  item_type: string
  language?: string | null
}

export interface BookTitle {
  title_id: number
  title: string
  author?: string | null
  isbn?: string | null
  publisher?: string | null
  publish_year?: number | null
  item_type: string
  language?: string | null
  is_deleted: boolean
  total_items: number
  available_items: number
}

export interface AddLibraryItemRequest {
  title_id: number
  location?: string | null
  price?: string | null
  acquired_at?: string | null
}

export interface LibraryItem {
  item_id: number
  barcode: string
  title_id: number
  item_type?: string | null
  status: string
  location?: string | null
  price?: string | null
}

// ---- 借阅证 ----------------------------------------------------------

export interface BorrowCard {
  card_id: number
  card_no: string
  reader_id: number
  status: CardStatusValue
  issued_at?: string | null
  issued_by?: number | null
  cancelled_at?: string | null
}

// ---- 流通 ------------------------------------------------------------

export interface CheckResult {
  step: string
  ok: boolean
  code: string
  message: string
  detail: Record<string, unknown>
}

export interface PreCheckResponse {
  reader?: { reader_id: number; name: string; reader_type?: string | null } | null
  quota?: { limit: number; occupied: number; remaining: number } | null
  alerts: Record<string, unknown>
  can_borrow: boolean
  checks: CheckResult[]
}

export interface BorrowBookResponse {
  loan_id: number
  reader_id: number
  item_id: number
  barcode: string
  borrowed_at?: string | null
  due_at?: string | null
  status: string
  remaining_quota: number
}

export interface ReturnBookResponse {
  loan_id: number
  returned_at?: string | null
  overdue_days: number
  billed_days: number
  fine?: { fine_id: number; amount: string; status: string } | null
  item_status: string
  reservation_advanced?: { reservation_id: number; status: string; reader_id?: number | null } | null
}

export interface RenewResponse {
  loan_id: number
  due_at?: string | null
  renew_count: number
  status: string
}

export interface CollectFineResponse {
  fine_id: number
  status: string
  paid_at?: string | null
  operator_id?: number | null
  operator_role?: string | null
}

// ---- 查询借阅信息 ----------------------------------------------------

export interface LoanEntry {
  loan_id: number
  item_id: number
  barcode?: string | null
  title?: string | null
  borrowed_at?: string | null
  due_at?: string | null
  returned_at?: string | null
  status: string
  is_overdue: boolean
  overdue_days: number
  renew_count: number
  can_renew: boolean
  librarian_id?: number | null
}

export interface FineEntry {
  fine_id: number
  loan_id?: number
  amount: string
  status: string
  overdue_days: number
  billed_days: number
  unit_price?: string
  created_at?: string | null
  paid_at?: string | null
}

export interface ReaderLoansResponse {
  reader: {
    reader_id: number
    name: string
    reader_type?: string | null
    department?: string | null
  }
  current: LoanEntry[]
  history: LoanEntry[]
  overdue: LoanEntry[]
  reservations: {
    reservation_id: number
    title_id: number
    status: string
    queue_position: number
    ready_at?: string | null
  }[]
  fines: FineEntry[]
  unpaid_total: string
}

export interface ReaderFinesResponse {
  unpaid: FineEntry[]
  paid: FineEntry[]
  unpaid_total: string
}

// ---- 预约 ------------------------------------------------------------

export interface Reservation {
  reservation_id: number
  title_id: number
  reader_id?: number | null
  status: ReservationStatusValue
  created_at?: string | null
  ready_at?: string | null
  queue_position: number
  expires_at?: string | null
  is_expired: boolean
}

export interface CancelReservationResponse {
  reservation_id: number
  status: string
  advanced_to?: { reservation_id?: number; status?: string; reader_id?: number | null } | null
}

// ---- 规则 ------------------------------------------------------------

export interface BorrowPolicyItem {
  reader_type: string
  max_borrow_count: number
  borrow_days: number
  updated_at?: string | null
  updated_by?: number | null
}

export interface FineRuleItem {
  item_type: string
  daily_price: string
  grace_days: number
  max_amount: string
  updated_at?: string | null
  updated_by?: number | null
}

export interface PoliciesResponse {
  borrow_policies: BorrowPolicyItem[]
  fine_rules: FineRuleItem[]
}

// ---- 统计 ------------------------------------------------------------

export interface CollectionStats {
  titles: number
  items: number
  by_status: Record<string, number>
  by_item_type: Record<string, number>
}

// ---- 错误 ------------------------------------------------------------

export interface ApiErrorBody {
  error: {
    code: string
    message: string
    detail: Record<string, unknown>
  }
}

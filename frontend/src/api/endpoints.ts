/**
 * 后端接口封装 —— 与 `backend/app/presentation/routers/` 逐一对齐。
 *
 * 注意两个易错点（已在真实联调中踩过）：
 * 1. **登录必须带 `role`**：`LoginRequest.role` 默认 `READER`，
 *    管理员/馆员不传对应角色会拿到过不了守卫的 token（401）。
 * 2. **路径无 `/api/v1` 前缀**，直接 `/api/...`。
 */

import { request } from './client'
import type {
  Account,
  AddBookTitleRequest,
  AddLibraryItemRequest,
  BookListResponse,
  BookQuery,
  BookTitle,
  BorrowBookResponse,
  BorrowCard,
  CancelReservationResponse,
  CollectFineResponse,
  CollectionStats,
  LibraryItem,
  LoginRequest,
  PoliciesResponse,
  PreCheckResponse,
  ReaderLoansResponse,
  RegisterReaderRequest,
  RenewResponse,
  Reservation,
  ReturnBookResponse,
  Role,
  TokenResponse,
} from './types'

// ---- 认证与账号（auth_router） ---------------------------------------

export const authApi = {
  login: (payload: LoginRequest) =>
    request<TokenResponse>('/api/auth/login', { method: 'POST', body: payload, anonymous: true }),

  register: (payload: RegisterReaderRequest) =>
    request<Account>('/api/auth/register', { method: 'POST', body: payload, anonymous: true }),

  me: () => request<Account>('/api/auth/me'),

  addLibrarian: (payload: { username: string; password: string; name: string }) =>
    request<Account>('/api/admin/librarians', { method: 'POST', body: payload }),

  listLibrarians: (includeDeleted = false) =>
    request<Account[]>('/api/admin/librarians', { query: { include_deleted: includeDeleted } }),

  deleteLibrarian: (id: number) =>
    request<{ deleted: boolean; librarian_id: number }>(`/api/admin/librarians/${id}`, {
      method: 'DELETE',
    }),

  resetPassword: (accountId: number, newPassword: string, role: Role) =>
    request<{ reset: boolean }>(`/api/admin/accounts/${accountId}/reset-password`, {
      method: 'POST',
      body: { new_password: newPassword, role },
    }),
}

// ---- 图书检索（query_router） ----------------------------------------

export const queryApi = {
  searchBooks: (query: BookQuery) =>
    request<BookListResponse>('/api/books', {
      anonymous: true,
      query: {
        keyword: query.keyword,
        item_type: query.item_type,
        available_only: query.available_only,
        page: query.page,
        page_size: query.page_size,
      },
    }),

  collectionStats: () => request<CollectionStats>('/api/admin/collection-stats'),
}

// ---- 书目与馆藏（catalog_router） ------------------------------------

export const catalogApi = {
  addBookTitle: (payload: AddBookTitleRequest) =>
    request<BookTitle>('/api/admin/book-titles', { method: 'POST', body: payload }),

  deleteBookTitle: (titleId: number) =>
    request<{ deleted: boolean; title_id: number }>(`/api/admin/book-titles/${titleId}`, {
      method: 'DELETE',
    }),

  addLibraryItem: (payload: AddLibraryItemRequest) =>
    request<LibraryItem>('/api/admin/library-items', { method: 'POST', body: payload }),

  deleteLibraryItem: (itemId: number) =>
    request<{ deleted: boolean; item_id: number; status: string }>(
      `/api/admin/library-items/${itemId}`,
      { method: 'DELETE' },
    ),

  markItemStatus: (itemId: number, status: string) =>
    request<LibraryItem>(`/api/admin/library-items/${itemId}/status`, {
      method: 'POST',
      body: { status },
    }),
}

// ---- 借阅证（card_router） -------------------------------------------

export const cardApi = {
  issueCard: (readerId: number) =>
    request<BorrowCard>('/api/admin/borrow-cards', { method: 'POST', body: { reader_id: readerId } }),

  cancelCard: (cardId: number) =>
    request<BorrowCard>(`/api/admin/borrow-cards/${cardId}/cancel`, { method: 'POST' }),

  restoreCard: (cardId: number) =>
    request<BorrowCard>(`/api/admin/borrow-cards/${cardId}/restore`, { method: 'POST' }),

  suspendCard: (cardId: number) =>
    request<BorrowCard>(`/api/admin/borrow-cards/${cardId}/suspend`, { method: 'POST' }),

  resumeCard: (cardId: number) =>
    request<BorrowCard>(`/api/admin/borrow-cards/${cardId}/resume`, { method: 'POST' }),

  listByReader: (readerId: number) =>
    request<BorrowCard[]>(`/api/admin/readers/${readerId}/borrow-cards`),
}

// ---- 流通（circulation_router） --------------------------------------

export const circulationApi = {
  /** 借书前置校验（只读，不产生数据变更） */
  precheck: (cardNo: string, barcode: string) =>
    request<PreCheckResponse>('/api/circulation/precheck', {
      method: 'POST',
      body: { card_no: cardNo, barcode },
    }),

  borrow: (cardNo: string, barcode: string) =>
    request<BorrowBookResponse>('/api/circulation/borrow', {
      method: 'POST',
      body: { card_no: cardNo, barcode },
    }),

  returnBook: (barcode: string) =>
    request<ReturnBookResponse>('/api/circulation/return', {
      method: 'POST',
      body: { barcode },
    }),

  renew: (loanId: number) =>
    request<RenewResponse>(`/api/circulation/loans/${loanId}/renew`, { method: 'POST' }),

  collectFine: (fineId: number) =>
    request<CollectFineResponse>(`/api/fines/${fineId}/collect`, { method: 'POST' }),
}

// ---- 借阅信息查询 ----------------------------------------------------

export const loanApi = {
  myLoans: (status?: string) =>
    request<ReaderLoansResponse>('/api/me/loans', { query: { status } }),

  readerLoans: (readerId: number, status?: string) =>
    request<ReaderLoansResponse>(`/api/readers/${readerId}/loans`, { query: { status } }),
}

// ---- 预约（reservation_router） --------------------------------------

export const reservationApi = {
  create: (titleId: number) =>
    request<Reservation>('/api/reservations', { method: 'POST', body: { title_id: titleId } }),

  cancel: (reservationId: number) =>
    request<CancelReservationResponse>(`/api/reservations/${reservationId}`, { method: 'DELETE' }),

  mine: (onlyActive = false) =>
    request<Reservation[]>('/api/me/reservations', { query: { only_active: onlyActive } }),
}

// ---- 规则（policy_router） -------------------------------------------

export const policyApi = {
  getAll: () => request<PoliciesResponse>('/api/policies'),

  updateBorrow: (payload: { reader_type: string; max_borrow_count: number; borrow_days: number }) =>
    request('/api/admin/policies/borrow', { method: 'PUT', body: payload }),

  updateFine: (payload: {
    item_type: string
    daily_price: string
    grace_days: number
    max_amount: string
  }) => request('/api/admin/policies/fine', { method: 'PUT', body: payload }),
}

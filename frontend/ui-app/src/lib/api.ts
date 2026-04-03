import useAuthStore from '@/store/authStore'

const BASE_URL = ''  // proxied via Vite

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = useAuthStore.getState().token
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  })

  if (!res.ok) {
    let msg = ''
    try {
      const body = await res.json()
      if (body?.detail?.error) {
        msg = String(body.detail.error)
      } else if (typeof body?.detail === 'string') {
        msg = body.detail
      } else if (body?.error) {
        msg = String(body.error)
      }
    } catch { /* ignore parse failure */ }
    const err = { status: res.status, error: msg || `请求失败 (${res.status})` }
    if (res.status === 401) {
      ;(err as any).isAuthError = true
    }
    throw err
  }

  return res.json()
}

export interface LoginResponse {
  user_id: string
  username: string
  token: string
  onboarding_done: boolean
}

export interface RegisterResponse {
  user_id: string
  username: string
  token: string
  onboarding_done: boolean
}

export const api = {
  login: (email: string, password: string) =>
    request<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  register: (email: string, password: string, username: string) =>
    request<RegisterResponse>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, username }),
    }),

  updateProfile: (
    userId: string,
    data: {
      username?: string
      occupation: string
      apps: string[]
      sensitive_fields: string[]
      onboarding_done: boolean
      avatar_index?: number
      grad_from?: string
      grad_to?: string
    }
  ) =>
    request(`/user/profile/${userId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  /** 完成 onboarding：写入 profile + 播种默认 Skill */
  completeOnboarding: (
    userId: string,
    data: {
      username?: string
      occupation: string
      apps: string[]
      sensitive_fields: string[]
      onboarding_done: boolean
      avatar_index?: number
      grad_from?: string
      grad_to?: string
    }
  ) =>
    request<{ ok: boolean; seeded_skills: number }>(
      `/user/complete-onboarding/${userId}`,
      { method: 'POST', body: JSON.stringify(data) }
    ),
}

export const ERROR_MESSAGES: Record<string, string> = {
  email_exists:          '该邮箱已被注册，请直接登录',
  invalid_credentials:   '邮箱或密码错误',
  missing_fields:        '请填写所有必填项',
  network_error:         '连接失败，请检查网络后重试',
  password_mismatch:     '两次输入的密码不一致',
  password_too_short:    '密码至少需要 6 位',
}

export function getErrorMessage(err: unknown): string {
  if (err instanceof TypeError) return ERROR_MESSAGES.network_error
  if (typeof err === 'object' && err !== null) {
    const e = err as Record<string, unknown>
    if (typeof e.error === 'string' && e.error in ERROR_MESSAGES) {
      return ERROR_MESSAGES[e.error]
    }
    // 透传具体错误文本（后端返回了具体描述）
    if (typeof e.error === 'string' && e.error.trim()) {
      return e.error
    }
    if (typeof e.detail === 'object' && e.detail !== null) {
      const detail = e.detail as Record<string, unknown>
      if (typeof detail.error === 'string' && detail.error in ERROR_MESSAGES) {
        return ERROR_MESSAGES[detail.error]
      }
      if (typeof detail.message === 'string') {
        return detail.message
      }
    }
    if (typeof e.detail === 'string') return e.detail
  }
  return '发生未知错误，请重试'
}

// === Evolution 接口 ===

export interface EvolutionEvent {
  event_id: string
  ts: number
  date_key: string
  event_type: 'added' | 'conflict' | 'disabled' | 'generating' | 'reinforced'
  type_label: string
  skill_name: string | null
  title: string
  summary: string
  source: string
  action_label: string
  conflict_note: string | null
  processed: boolean
}

export interface EvolutionGroup {
  date: string
  date_key: string
  items: EvolutionEvent[]
}

export interface EvolutionEventsResponse {
  groups: EvolutionGroup[]
  pagination: { page: number; page_size: number; total: number; has_next: boolean }
}

export interface EvolutionStats {
  rules_total: number
  added_this_week: number
  evolved_this_week: number
  summary_text: string
}

export const evolution = {
  getEvents: (userId: string, range = 'all', eventTypes?: string, page = 1) =>
    request<EvolutionEventsResponse>(
      `/evolution/events/${userId}?range=${range}${eventTypes ? `&event_types=${eventTypes}` : ''}&page=${page}`
    ),
  getStats: (userId: string) =>
    request<EvolutionStats>(`/evolution/stats/${userId}`),
}

// === Skill CRUD 接口（JWT 版，供前端控制台使用）===

export interface SkillRecord {
  id: number
  user_id: string
  skill_name: string
  version: string
  path: string
  confidence: number | null
  content_hash: string | null
  strategy: string | null
  sensitive_field: string | null
  app_context?: string
  scene: string | null
  rule_text: string | null
  skill_md_content: string | null
  rules_json_content: string | null
  created_ts: number
  archived_ts: number | null
  archived_reason: string | null
  superseded_by: string | null
}

export interface SkillMetaUpdate {
  confidence?: number
  scene?: string
  rule_text?: string
  strategy?: string
  sensitive_field?: string
}

export const skillApi = {
  /** 获取当前用户所有 active Skills */
  getActive: (userId: string) =>
    request<{ user_id: string; skills: SkillRecord[]; count: number }>(
      `/console/skills/active/${userId}`
    ),

  /** 获取当前用户所有 Skills（含 active + archived）*/
  getAll: (userId: string) =>
    request<{ user_id: string; active: SkillRecord[]; archived: SkillRecord[]; total: number }>(
      `/console/skills/all/${userId}`
    ),

  /** 停用（归档）指定 Skill */
  archive: (userId: string, skillName: string, version: string, reason = 'user_archived') =>
    request<{ success: boolean }>(
      `/console/skills/archive/${userId}/${encodeURIComponent(skillName)}/${encodeURIComponent(version)}`,
      { method: 'POST', body: JSON.stringify({ reason }) }
    ),

  /** 恢复已归档的 Skill */
  restore: (userId: string, skillName: string, version: string) =>
    request<{ success: boolean }>(
      `/console/skills/restore/${userId}/${encodeURIComponent(skillName)}/${encodeURIComponent(version)}`,
      { method: 'POST' }
    ),

  /** 删除 Skill（归档 + 删除文件系统文件）*/
  delete: (userId: string, skillName: string, version: string) =>
    request<{ success: boolean }>(
      `/console/skills/${userId}/${encodeURIComponent(skillName)}/${encodeURIComponent(version)}`,
      { method: 'DELETE', body: JSON.stringify({ confirm: true }) }
    ),

  /** 更新 Skill 元数据 */
  updateMeta: (userId: string, skillName: string, meta: SkillMetaUpdate) =>
    request<{ success: boolean }>(
      `/console/skills/${userId}/${encodeURIComponent(skillName)}`,
      { method: 'PUT', body: JSON.stringify(meta) }
    ),
}

// ===== Notifications API =====

export interface NotificationRecord {
  id: number
  user_id: string
  notif_type: string
  title: string
  body: string | null
  skill_name: string | null
  skill_version: string | null
  event_id: string | null
  status: 'pending' | 'confirmed' | 'dismissed'
  created_ts: number
  read_ts: number | null
}

export interface NotificationsResponse {
  user_id: string
  items: NotificationRecord[]
  total: number
  unread: number
  page: number
  page_size: number
}

export const notifications = {
  list: (userId: string, params?: { status?: string; page?: number; page_size?: number }) => {
    const qs = new URLSearchParams()
    if (params?.status) qs.set('status', params.status)
    if (params?.page) qs.set('page', String(params.page))
    if (params?.page_size) qs.set('page_size', String(params.page_size))
    const query = qs.toString()
    return request<NotificationsResponse>(
      `/notifications/${userId}${query ? `?${query}` : ''}`
    )
  },
  read: (userId: string, notifId: number) =>
    request<{ ok: boolean; notif_id: number }>(
      `/notifications/${userId}/${notifId}/read`,
      { method: 'PUT' }
    ),
  readAll: (userId: string) =>
    request<{ ok: boolean; count: number }>(
      `/notifications/${userId}/read-all`,
      { method: 'PUT' }
    ),
  confirm: (userId: string, notifId: number) =>
    request<{ ok: boolean; notif_id: number }>(
      `/notifications/${userId}/${notifId}/confirm`,
      { method: 'PUT' }
    ),
  dismiss: (userId: string, notifId: number) =>
    request<{ ok: boolean; notif_id: number; status: string }>(
      `/notifications/${userId}/${notifId}/dismiss`,
      { method: 'PUT' }
    ),
}

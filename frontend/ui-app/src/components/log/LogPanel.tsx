/**
 * LogPanel — 右侧可折叠规则动态面板
 * 展开时占 360px，单页纵向滚动：
 *   区块1（上）：待决策 — pending 通知，含确认/拒绝按钮
 *   区块2（下）：进化日志 — 进化事件 + 已确认通知混排，含搜索+类型筛选
 */
import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { GradientDot } from '@/components/ui/GradientDot'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { getTagBg } from '@/lib/tagColorMap'
import { Bell, ChevronDown, ChevronUp } from 'lucide-react'
import { notifications, type NotificationRecord } from '@/lib/api'
import type { EvolutionEvent } from '@/lib/api'

// ─── 类型 ───────────────────────────────────────────────

type NotificationDecision = {
  notif: NotificationRecord
  decision: 'confirm' | 'dismiss' | null
}

// MergedItem: 进化事件与通知的统一类型，两个变体都包含渲染所需全部字段
type MergedItem =
  | ({ _source: 'evo' } & EvolutionEvent)
  | ({
      _source: 'notif'
      notif: NotificationRecord
      // 统一渲染字段（与 EvolutionEvent 对齐）
      event_id: string
      ts: number
      date_key: string
      event_type: EvolutionEvent['event_type']
      type_label: string
      skill_name: string
      title: string
      summary: string
      source: string
      action_label: string
      conflict_note: string | null
      processed: boolean
    })

// ─── 辅助函数 ────────────────────────────────────────────

function formatTime(ts: number): string {
  const d = new Date(ts * 1000)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function formatDateKey(ts: number): string {
  const d = new Date(ts * 1000)
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
}

function hexToRgbStr(hex: string): string {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `${r},${g},${b}`
}

// skill_name 中文转换（如 wechat-medical -> 微信病历传输规范）
const SLUG_ZH_MAP: Record<string, string> = {
  'wechat-medical': '微信病历传输',
  'alipay-receipt': '支付宝收款行为',
  'dingtalk-contact': '钉钉联系外传',
  'home-address': '家庭住址保护',
  'phone-share': '手机号分享管控',
}

function _slugToZhFull(slug: string): string {
  if (SLUG_ZH_MAP[slug]) return SLUG_ZH_MAP[slug]
  // 尝试用中划线分割并拼接
  return slug.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join('')
}

// ─── 常量 ───────────────────────────────────────────────

const EVENT_GRAD: Record<string, { from: string; to: string }> = {
  added:      { from: '#0BA360', to: '#3CBA92' },
  conflict:   { from: '#FF416C', to: '#FF4B2B' },
  disabled:   { from: '#BDBDBD', to: '#D4D4D4' },
  generating: { from: '#F7971E', to: '#FFD200' },
  reinforced: { from: '#1677FF', to: '#69A8FF' },
}

const EVENT_TYPE_OPTIONS = [
  { key: 'added',      label: '新增',   color: '#0BA360' },
  { key: 'conflict',   label: '冲突',   color: '#FF416C' },
  { key: 'disabled',   label: '停用',   color: '#BDBDBD' },
  { key: 'reinforced', label: '强化',   color: '#1677FF' },
]

const NOTIF_TYPE_COLORS: Record<string, string> = {
  skill_added:       '#0BA360',
  conflict_resolved: '#FF416C',
  pending_confirm:   '#F7971E',
  rule_merged:      '#1677FF',
}

/** 本地演示用：负数 id，不写入后端；用于观察「新一条待决策」弹入动画 */
const DEMO_PENDING_NOTIF_ID = -999_999

function buildDemoPendingNotif(userId: string): NotificationRecord {
  return {
    id: DEMO_PENDING_NOTIF_ID,
    user_id: userId,
    notif_type: 'pending_confirm',
    title: '请确认新增规则：自动进入专注模式',
    body: '系统检测到你常在办公 Wi-Fi 下处理文档，建议新增一条「连接公司网络时自动进入专注模式、聚合非紧急通知」的隐私规则。',
    skill_name: 'office-focus-mode',
    skill_version: 'v1.0.0',
    event_id: null,
    status: 'pending',
    created_ts: Math.floor(Date.now() / 1000),
    read_ts: null,
  }
}

function notifDotColor(n: NotificationRecord): string {
  if (n.status === 'pending') return '#F7971E'
  if (n.status === 'dismissed') return '#BDBDBD'
  return NOTIF_TYPE_COLORS[n.notif_type] ?? '#888888'
}

// ─── Props ──────────────────────────────────────────────

interface LogPanelProps {
  isOpen: boolean
  onClose: () => void
  gradFrom: string
  gradTo: string
  userId?: string | null
  token?: string | null
  onSkillClick?: (skillName: string) => void
  onUnreadChange?: (count: number) => void
}

// ─── 主组件 ─────────────────────────────────────────────

export function LogPanel({ isOpen, onClose, gradFrom, gradTo, userId, token, onSkillClick, onUnreadChange }: LogPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  // ── 状态 ────────────────────────────────────────────
  // 规则动态（统一从notification表读取）
  const [confirmedNotifs, setConfirmedNotifs] = useState<NotificationRecord[]>([])
  const [logSearch, setLogSearch] = useState('')
  const [logActiveTypes, setLogActiveTypes] = useState<Set<string>>(new Set())
  const [logCutoffDate, setLogCutoffDate] = useState<string | null>(null)
  const [logLoading, setLogLoading] = useState(false)

  // 通知
  const [pendingDecisions, setPendingDecisions] = useState<NotificationDecision[]>([])
  const [notifUnread, setNotifUnread] = useState(0)
  const [notifLoading, setNotifLoading] = useState(false)
  /** 延迟插入顶部的演示待决策（观察弹入动画） */
  const [demoPendingRow, setDemoPendingRow] = useState<NotificationDecision | null>(null)

  // ── 加载通知（统一数据源）─────────────────────────────
  useEffect(() => {
    if (!userId || !token || !isOpen) return
    setNotifLoading(true)
    setLogLoading(true)
    // 并行拉 pending（供决策）和 confirmed（历史记录）
    Promise.all([
      notifications.list(userId, { status: 'pending', page_size: 50 }),
      notifications.list(userId, { status: 'confirmed', page_size: 100 }),
    ])
      .then(([pendRes, confRes]) => {
        setPendingDecisions(pendRes.items.map(n => ({ notif: n, decision: null })))
        setConfirmedNotifs(confRes.items)
        const unread = pendRes.unread ?? 0
        setNotifUnread(unread)
        onUnreadChange?.(unread)
      })
      .catch(() => {})
      .finally(() => {
        setNotifLoading(false)
        setLogLoading(false)
      })
  }, [userId, token, isOpen])

  // 面板关闭时清掉演示条，下次打开可再次播放弹入
  useEffect(() => {
    if (!isOpen) setDemoPendingRow(null)
  }, [isOpen])

  // 加载完成后延迟 ~1.4s 在待决策列表顶部插入演示通知（仅本地）
  useEffect(() => {
    if (!isOpen || !userId || notifLoading) return
    const t = window.setTimeout(() => {
      setDemoPendingRow({ notif: buildDemoPendingNotif(userId), decision: null })
    }, 1400)
    return () => window.clearTimeout(t)
  }, [isOpen, userId, notifLoading])

  // ── 决策操作 ────────────────────────────────────────
  async function handleConfirm(notif: NotificationRecord) {
    if (notif.id === DEMO_PENDING_NOTIF_ID) {
      setDemoPendingRow(d => (d ? { ...d, decision: 'confirm' } : null))
      return
    }
    if (!userId) return
    setPendingDecisions(prev =>
      prev.map(d => d.notif.id === notif.id ? { ...d, decision: 'confirm' } : d)
    )
    try {
      await notifications.confirm(userId, notif.id)
      const newUnread = Math.max(0, notifUnread - 1)
      setNotifUnread(newUnread)
      onUnreadChange?.(newUnread)
      // 追加到 confirmed 列表
      setConfirmedNotifs(prev => [{ ...notif, status: 'confirmed' as const }, ...prev])
    } catch {
      setPendingDecisions(prev =>
        prev.map(d => d.notif.id === notif.id ? { ...d, decision: null } : d)
      )
    }
  }

  async function handleDismiss(notif: NotificationRecord) {
    if (notif.id === DEMO_PENDING_NOTIF_ID) {
      setDemoPendingRow(d => (d ? { ...d, decision: 'dismiss' } : null))
      return
    }
    if (!userId) return
    setPendingDecisions(prev =>
      prev.map(d => d.notif.id === notif.id ? { ...d, decision: 'dismiss' } : d)
    )
    try {
      await notifications.dismiss(userId, notif.id)
      const newUnread = Math.max(0, notifUnread - 1)
      setNotifUnread(newUnread)
      onUnreadChange?.(newUnread)
    } catch {
      setPendingDecisions(prev =>
        prev.map(d => d.notif.id === notif.id ? { ...d, decision: null } : d)
      )
    }
  }

  // ── 通知点击 → Skill 详情 ───────────────────────────
  function handleNotifClick(n: NotificationRecord) {
    if (n.skill_name) onSkillClick?.(n.skill_name)
  }

  // ── 类型筛选 ─────────────────────────────────────────
  function toggleType(key: string) {
    setLogActiveTypes(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  // ── notif_type 到 event_type 的映射 ─────────────────
  function notifTypeToEventType(notifType: string): EvolutionEvent['event_type'] {
    switch (notifType) {
      case 'skill_added': return 'added'
      case 'evolution_created': return 'added'
      case 'skill_disabled': return 'disabled'
      case 'evolution_conflict_resolved': return 'conflict'
      case 'skill_updated': return 'reinforced'
      default: return 'added'
    }
  }

  // ── notif_type 到类型标签的映射 ──────────────────────
  function notifTypeToLabel(notifType: string): string {
    switch (notifType) {
      case 'skill_added': return '规则新增'
      case 'evolution_created': return '进化新增'
      case 'skill_disabled': return '规则停用'
      case 'evolution_conflict_resolved': return '冲突已解决'
      case 'skill_updated': return '规则更新'
      default: return '通知'
    }
  }

  // ── 构建历史记录列表（只用confirmed notifications）──────
  const allItems = useRef<MergedItem[]>([]).current

  useEffect(() => {
    const notifItems: MergedItem[] = confirmedNotifs.map(n => ({
      _source: 'notif' as const,
      notif: n,
      event_id: `notif-${n.id}`,
      ts: n.created_ts,
      date_key: formatDateKey(n.created_ts),
      event_type: notifTypeToEventType(n.notif_type),
      type_label: notifTypeToLabel(n.notif_type),
      skill_name: n.skill_name ?? '',
      title: n.title || (n.skill_name ? _slugToZhFull(n.skill_name) : ''),
      summary: n.body ?? '',
      source: '规则动态',
      action_label: '',
      conflict_note: null,
      processed: true,
    }))
    allItems.length = 0
    allItems.push(...notifItems)
    allItems.sort((a, b) => b.ts - a.ts)
  }, [confirmedNotifs])

  const filteredItems = allItems.filter((item) => {
    if (logActiveTypes.size > 0 && !logActiveTypes.has(item.event_type)) return false
    // 日历筛选：只显示截至当日（含）的记录
    if (logCutoffDate) {
      const cutoffEnd = new Date(logCutoffDate)
      cutoffEnd.setHours(23, 59, 59, 999)
      if (item.ts > cutoffEnd.getTime() / 1000) return false
    }
    if (logSearch.trim()) {
      const q = logSearch.trim().toLowerCase()
      return (
        (item.skill_name ?? '').toLowerCase().includes(q) ||
        item.summary.toLowerCase().includes(q) ||
        item.title.toLowerCase().includes(q)
      )
    }
    return true
  })

  // 按日期分组
  const groupedByDate = filteredItems.reduce<Record<string, MergedItem[]>>((acc, item) => {
    const key = item.date_key
    if (!acc[key]) acc[key] = []
    acc[key].push(item)
    return acc
  }, {})
  const sortedDates = Object.keys(groupedByDate).sort((a, b) => {
    // 解析日期字符串并比较
    const parseDate = (s: string) => new Date(s.replace(/年|月/g, '-').replace(/日/, '')).getTime()
    return parseDate(b) - parseDate(a)
  })

  // ── 日期分组 ─────────────────────────────────────────

  const displayPending: NotificationDecision[] = demoPendingRow
    ? [demoPendingRow, ...pendingDecisions]
    : pendingDecisions
  const unresolvedCount = displayPending.filter(d => d.decision === null).length

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ width: 0, opacity: 0 }}
          animate={{ width: 360, opacity: 1 }}
          exit={{ width: 0, opacity: 0 }}
          transition={{ type: 'spring', stiffness: 300, damping: 32 }}
          style={{
            height: '100%',
            background: '#FFFFFF',
            borderLeft: '1px solid #E0DFDB',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            flexShrink: 0,
          }}
        >
          {/* ── 顶部工具栏 ── */}
          <div style={{ padding: '14px 16px 10px', borderBottom: '1px solid #E0DFDB', flexShrink: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
              <button
                onClick={onClose}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: '#888888', fontSize: 14, fontFamily: "'IBM Plex Mono', monospace",
                  padding: '2px 4px', borderRadius: 4,
                }}
                title="收起"
              >
                &gt;&gt;
              </button>

              <span style={{
                fontFamily: "'Sora', sans-serif",
                fontSize: 12,
                fontWeight: 600,
                color: gradFrom,
              }}>
                规则动态
              </span>

              <div style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 4 }}>
                <input
                  type="date"
                  value={logCutoffDate ?? ''}
                  onChange={e => setLogCutoffDate(e.target.value || null)}
                  title="筛选此日及之前的记录"
                  style={{
                    opacity: 0,
                    position: 'absolute',
                    right: 0,
                    top: 0,
                    width: 24,
                    height: 24,
                    cursor: 'pointer',
                  }}
                />
                <span style={{ fontSize: 16, cursor: 'pointer', color: logCutoffDate ? gradFrom : '#888888' }} title="筛选此日及之前的记录">📅</span>
                {logCutoffDate && (
                  <button
                    onClick={() => setLogCutoffDate(null)}
                    style={{
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      fontFamily: "'IBM Plex Mono', monospace",
                      fontSize: 10,
                      color: '#888888',
                      padding: '0 1px',
                      textDecoration: 'underline',
                    }}
                    title="清除筛选"
                  >
                    ✕
                  </button>
                )}
              </div>
            </div>

            {/* 筛选提示 */}
            {logCutoffDate && (
              <div style={{
                fontFamily: "'IBM Plex Mono', monospace",
                fontSize: 10,
                color: gradFrom,
                marginTop: -2,
                marginBottom: 8,
              }}>
                已筛选：截至 {logCutoffDate} 前的记录
              </div>
            )}

            {/* 搜索框 */}
            <input
              type="text"
              placeholder="搜索..."
              value={logSearch}
              onChange={e => setLogSearch(e.target.value)}
              style={{
                width: '100%',
                boxSizing: 'border-box',
                padding: '6px 10px',
                borderRadius: 5,
                border: '1px solid #E0DFDB',
                fontFamily: "'IBM Plex Mono', monospace",
                fontSize: 12,
                color: '#0A0A0A',
                background: '#F8F6F2',
                outline: 'none',
                marginBottom: 8,
              }}
            />

            {/* 类型筛选 */}
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              {EVENT_TYPE_OPTIONS.map(opt => {
                const active = logActiveTypes.has(opt.key)
                return (
                  <button
                    key={opt.key}
                    onClick={() => toggleType(opt.key)}
                    style={{
                      fontFamily: "'IBM Plex Mono', monospace",
                      fontSize: 10,
                      padding: '2px 8px',
                      borderRadius: 4,
                      border: 'none',
                      background: active ? getTagBg(opt.key, 0.18) : '#F0EEE9',
                      color: active ? opt.color : '#888888',
                      fontWeight: active ? 600 : 400,
                      cursor: 'pointer',
                      transition: 'all 0.12s',
                    }}
                  >
                    {opt.label}
                  </button>
                )
              })}
            </div>
          </div>

          {/* ── 主滚动区 ── */}
          <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', padding: '0 0 20px' }}>

            {/* ── 区块1：待决策通知 ── */}
            {notifLoading ? (
              <LoadingSpinner label="加载中..." />
            ) : displayPending.length === 0 ? (
              <div style={{ padding: '20px 16px', textAlign: 'center' }}>
                <p style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, color: '#AAAAAA' }}>
                  暂无待确认变更
                </p>
                <p style={{ fontFamily: "'Sora', sans-serif", fontSize: 11, color: '#CCCCCC', marginTop: 6 }}>
                  系统会持续学习你的隐私偏好
                </p>
              </div>
            ) : (
              <div style={{
                padding: '10px 0',
                borderBottom: '1px solid #E0DFDB',
                background: 'rgba(247,151,30,0.03)',
                marginBottom: 4,
              }}>
                {/* 区块标题 */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0 16px 8px',
                }}>
                  <span style={{
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: 10,
                    color: '#F7971E',
                    fontWeight: 600,
                    letterSpacing: '0.05em',
                  }}>
                    ● 待决策
                    {unresolvedCount > 0 && ` (${unresolvedCount})`}
                  </span>
                  <span style={{
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: 9,
                    color: '#CCCCCC',
                  }}>
                    共 {displayPending.length} 条
                  </span>
                </div>

                <AnimatePresence initial={false}>
                  {displayPending.map(({ notif, decision }) => (
                    <motion.div
                      key={notif.id}
                      layout
                      initial={
                        notif.id === DEMO_PENDING_NOTIF_ID
                          ? { opacity: 0, y: -18, scale: 0.97 }
                          : false
                      }
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ type: 'spring', stiffness: 420, damping: 30 }}
                      style={{ overflow: 'hidden' }}
                    >
                      <PendingNotifRow
                        notif={notif}
                        decision={decision}
                        onClick={() => handleNotifClick(notif)}
                        onConfirm={() => handleConfirm(notif)}
                        onDismiss={() => handleDismiss(notif)}
                        gradFrom={gradFrom}
                      />
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>
            )}

            {/* ── 区块2：进化日志（含 confirmed 通知）─── */}
            {sortedDates.length === 0 ? (
              <div style={{ textAlign: 'center', paddingTop: 40, fontFamily: "'Sora', sans-serif", fontSize: 13, color: '#AAAAAA' }}>
                暂无记录
              </div>
            ) : (
              sortedDates.map(date => (
                <div key={date}>
                  {/* 日期分隔线 */}
                  <div
                    data-date={date}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '12px 16px 6px',
                      position: 'sticky',
                      top: 0,
                      background: '#FFFFFF',
                      zIndex: 1,
                    }}
                  >
                    <div style={{ flex: 1, height: 1, background: '#E0DFDB' }} />
                    <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 10, color: '#AAAAAA', whiteSpace: 'nowrap' }}>
                      {date}
                    </span>
                    <div style={{ flex: 1, height: 1, background: '#E0DFDB' }} />
                  </div>

                  {groupedByDate[date].map(item => (
                    <MergedItemRow
                      key={item.event_id}
                      item={item}
                      gradFrom={gradFrom}
                      onSkillClick={onSkillClick}
                    />
                  ))}
                </div>
              ))
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

// ─── 子组件：待决策通知行 ────────────────────────────────

interface PendingNotifRowProps {
  notif: NotificationRecord
  decision: 'confirm' | 'dismiss' | null
  onClick: () => void
  onConfirm: () => void
  onDismiss: () => void
  gradFrom: string
}

function PendingNotifRow({ notif, decision, onClick, onConfirm, onDismiss, gradFrom }: PendingNotifRowProps) {
  const color = notifDotColor(notif)
  const decided = decision !== null

  return (
    <div style={{
      display: 'flex',
      alignItems: 'flex-start',
      gap: 8,
      padding: '8px 16px',
      borderBottom: '1px solid #F0EEE9',
      opacity: decided ? 0.45 : 1,
      transition: 'opacity 0.2s',
      cursor: notif.skill_name ? 'pointer' : 'default',
    }}
      onClick={onClick}
    >
      {/* 时间 */}
      <span style={{
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: 10,
        color: '#AAAAAA',
        width: 36,
        flexShrink: 0,
        paddingTop: 3,
      }}>
        {formatTime(notif.created_ts)}
      </span>

      {/* 图标 */}
      <div style={{ paddingTop: 2, flexShrink: 0 }}>
        <Bell size={13} style={{ color, display: 'block' }} />
      </div>

      {/* 内容 */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* 标题行 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          <span style={{
            fontFamily: "'Sora', sans-serif",
            fontSize: 12,
            fontWeight: 600,
            color: '#0A0A0A',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            flex: 1,
            maxWidth: 160,
          }}>
            {notif.title || notif.skill_name}
          </span>
          <span style={{
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: 9,
            color: '#F7971E',
            background: '#F7971E18',
            borderRadius: 3,
            padding: '1px 5px',
            flexShrink: 0,
          }}>
            待确认
          </span>
        </div>

        {/* 正文 */}
        <p style={{
          fontFamily: "'Sora', sans-serif",
          fontSize: 11,
          color: '#666666',
          lineHeight: 1.5,
          margin: '4px 0 0',
        }}>
          {notif.body || '暂无详情'}
        </p>

        {/* 操作按钮 */}
        {decided ? (
          <span style={{
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: 10,
            color: decision === 'confirm' ? '#07C160' : '#FF416C',
          }}>
            {decision === 'confirm' ? '✓ 已确认' : '✗ 已忽略'}
          </span>
        ) : (
          <div style={{ display: 'flex', gap: 4, marginTop: 6 }}>
            <button
              onClick={e => { e.stopPropagation(); onConfirm() }}
              style={{
                fontFamily: "'Sora', sans-serif",
                fontSize: 11,
                color: '#07C160',
                background: '#07C16010',
                border: '1px solid #07C16040',
                borderRadius: 4,
                padding: '2px 8px',
                cursor: 'pointer',
              }}
            >
              确认
            </button>
            <button
              onClick={e => { e.stopPropagation(); onDismiss() }}
              style={{
                fontFamily: "'Sora', sans-serif",
                fontSize: 11,
                color: '#888888',
                background: 'transparent',
                border: '1px solid #E0DFDB',
                borderRadius: 4,
                padding: '2px 8px',
                cursor: 'pointer',
              }}
            >
              忽略
            </button>
          </div>
        )}
      </div>
    </div>
  )
}


// ─── 子组件：合并后的日志行 ──────────────────────────────

interface MergedItemRowProps {
  item: MergedItem
  gradFrom: string
  onSkillClick?: (skillName: string) => void
}

function MergedItemRow({ item, gradFrom, onSkillClick }: MergedItemRowProps) {
  const [expanded, setExpanded] = useState(false)
  const isEvo = item._source === 'evo'
  const grad = isEvo
    ? EVENT_GRAD[item.event_type] ?? { from: '#888888', to: '#AAAAAA' }
    : { from: notifDotColor(item.notif), to: notifDotColor(item.notif) }
  const isGenerating = isEvo && item.event_type === 'generating'

  // 主标题：事件描述（如"首次触发新规则"）
  const primaryTitle = item.title || ''
  // 次级：Skill 名称（如"微信病历传输规范"）
  const secondaryTitle = item.skill_name || ''
  // 详情文本：summary 或通知 body
  const detailText = expanded ? (item.summary || '') : ''

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 8,
        padding: '8px 16px',
        cursor: item.skill_name ? 'pointer' : 'default',
        transition: 'background 0.12s',
      }}
      onMouseEnter={e => { if (item.skill_name) (e.currentTarget as HTMLElement).style.background = 'rgba(0,0,0,0.02)' }}
      onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}
      onClick={e => {
        // 点击展开按钮时不要触发整行跳转
        if ((e.target as HTMLElement).closest('.log-expand-btn')) return
        if (item.skill_name) onSkillClick?.(item.skill_name)
      }}
    >
      {/* 时间 */}
      <span style={{
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: 10,
        color: '#AAAAAA',
        width: 36,
        flexShrink: 0,
        paddingTop: 3,
      }}>
        {formatTime(item.ts)}
      </span>

      {/* 图标 */}
      <div style={{ paddingTop: 3, flexShrink: 0 }}>
        {isGenerating ? (
          <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', border: `1.5px solid ${grad.from}`, animation: 'spin 1s linear infinite' }} />
        ) : (
          <GradientDot
            gradFrom={grad.from}
            gradTo={grad.to}
            size={7}
            pulse={item.event_type === 'conflict'}
            hollow={item.event_type === 'disabled'}
          />
        )}
      </div>

      {/* 内容 */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* 第一行：主标题 + 展开按钮（若有详情） */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          <span style={{
            fontFamily: "'Sora', sans-serif",
            fontSize: 12,
            fontWeight: 600,
            color: '#0A0A0A',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            flex: 1,
            maxWidth: item.summary ? 175 : 210,
          }}>
            {primaryTitle}
          </span>
          {item.summary && (
            <button
              className="log-expand-btn"
              onClick={e => { e.stopPropagation(); setExpanded(v => !v) }}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: '1px 2px',
                color: '#AAAAAA',
                display: 'flex',
                alignItems: 'center',
                flexShrink: 0,
              }}
              title={expanded ? '收起详情' : '展开详情'}
            >
              {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>
          )}
          <span style={{
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: 10,
            background: `rgba(${hexToRgbStr(grad.from)},0.12)`,
            color: grad.from,
            borderRadius: 4,
            padding: '1px 6px',
            flexShrink: 0,
          }}>
            {item.type_label}
          </span>
          {item._source === 'notif' && (
            <Bell size={10} style={{ color: '#888888', flexShrink: 0 }} />
          )}
        </div>

        {/* 展开详情 */}
        {expanded && detailText && (
          <div style={{
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: 10,
            color: '#666666',
            marginTop: 4,
            lineHeight: 1.5,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-all',
          }}>
            {detailText}
          </div>
        )}

        {/* 次行：Skill 名称（小字灰色） */}
        {!expanded && secondaryTitle && primaryTitle !== secondaryTitle && (
          <div style={{
            fontFamily: "'Sora', sans-serif",
            fontSize: 10,
            color: '#888888',
            marginTop: 2,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}>
            {secondaryTitle}
          </div>
        )}
      </div>

      {item.action_label && !expanded && (
        <span style={{
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: 10,
          color: item.event_type === 'conflict' ? '#FF416C' : gradFrom,
          cursor: 'pointer',
          flexShrink: 0,
          paddingTop: 2,
        }}>
          {item.action_label} →
        </span>
      )}
    </div>
  )
}

export default LogPanel

// 类型别名（供外部引用）
export type { LogPanelProps }

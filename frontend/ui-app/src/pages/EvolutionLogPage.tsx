/**
 * EvolutionLogPage — 进化日志页 (/app/log)
 * 展示用户 Skill 的进化历史，支持日期范围和事件类型筛选。
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import useAuthStore from '@/store/authStore'
import { Navbar } from '@/components/layout/Navbar'
import { HaloBackground } from '@/components/ui/OrbBackground'
import { GradientDot } from '@/components/ui/GradientDot'
import { evolution } from '@/lib/api'
import type { EvolutionGroup, EvolutionEvent, EvolutionStats } from '@/lib/api'
import { hexToRgba } from '@/lib/colorMap'

// 事件类型对应的渐变色
const EVENT_TYPE_GRADIENTS = {
  added:      { from: '#0BA360', to: '#3CBA92', label: '新增' },
  conflict:   { from: '#FF416C', to: '#FF4B2B', label: '冲突' },
  disabled:   { from: '#BDBDBD', to: '#D4D4D4', label: '停用' },
  generating: { from: '#F7971E', to: '#FFD200', label: '生成中' },
  reinforced: { from: '#1677FF', to: '#69A8FF', label: '强化' },
}

type EventTypeKey = keyof typeof EVENT_TYPE_GRADIENTS
type DateRange = 'week' | 'month' | 'all'

const DATE_RANGE_OPTIONS: { key: DateRange; label: string }[] = [
  { key: 'week',  label: '本周' },
  { key: 'month', label: '本月' },
  { key: 'all',   label: '全部' },
]

const ALL_EVENT_TYPES: EventTypeKey[] = ['added', 'conflict', 'disabled', 'reinforced']

// Mock fallback 数据
const MOCK_GROUPS: EvolutionGroup[] = [
  {
    date: '2026-03-23',
    date_key: '2026-03-23',
    items: [
      {
        event_id: 'mock-1',
        ts: 1742731200,
        date_key: '2026-03-23',
        event_type: 'added',
        type_label: '新增',
        skill_name: '微信病历传输规范',
        title: '首次触发新规则',
        summary: '向非医疗系统内人员发送含诊断结论的消息时，自动拦截',
        source: '用户纠错',
        action_label: '查看详情',
        conflict_note: null,
        processed: true,
      },
      {
        event_id: 'mock-2',
        ts: 1742724000,
        date_key: '2026-03-23',
        event_type: 'conflict',
        type_label: '规则待确认',
        skill_name: '支付宝收款码行为',
        title: '规则边界冲突',
        summary: '规则与新场景产生冲突，需重新审核边界条件',
        source: '自动推导',
        action_label: '确认规则',
        conflict_note: '规则与新触发场景产生冲突，需重新审核边界条件',
        processed: false,
      },
    ],
  },
  {
    date: '2026-03-22',
    date_key: '2026-03-22',
    items: [
      {
        event_id: 'mock-3',
        ts: 1742640000,
        date_key: '2026-03-22',
        event_type: 'conflict',
        type_label: '冲突',
        skill_name: '家庭住址保护',
        title: '规则发生冲突',
        summary: '两条规则对同一场景判断不一致，需要手动解决',
        source: '自动检测',
        action_label: '解决冲突',
        conflict_note: '规则 A 要求拦截，规则 B 允许通过',
        processed: false,
      },
      {
        event_id: 'mock-4',
        ts: 1742630000,
        date_key: '2026-03-22',
        event_type: 'disabled',
        type_label: '停用',
        skill_name: '手机号分享管控',
        title: '规则被停用',
        summary: '用户手动停用了此规则',
        source: '用户操作',
        action_label: '查看详情',
        conflict_note: null,
        processed: true,
      },
    ],
  },
]

const MOCK_STATS: EvolutionStats = {
  rules_total: 24,
  added_this_week: 3,
  evolved_this_week: 7,
  summary_text: '规则库共 24 条 · 本周新增 3 · 本周进化 7 次',
}

function formatTime(ts: number): string {
  const d = new Date(ts * 1000)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

export default function EvolutionLogPage() {
  const navigate = useNavigate()
  const { user_id, gradFrom, gradTo } = useAuthStore()

  const [dateRange, setDateRange] = useState<DateRange>('all')
  const [activeTypes, setActiveTypes] = useState<Set<EventTypeKey>>(new Set())
  const [groups, setGroups] = useState<EvolutionGroup[]>([])
  const [stats, setStats] = useState<EvolutionStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!user_id) return
    setLoading(true)
    const typesParam = activeTypes.size > 0 ? [...activeTypes].join(',') : undefined
    evolution.getEvents(user_id, dateRange, typesParam)
      .then(res => setGroups(res.groups))
      .catch(() => setGroups(MOCK_GROUPS))
      .finally(() => setLoading(false))
  }, [user_id, dateRange, activeTypes])

  useEffect(() => {
    if (!user_id) return
    evolution.getStats(user_id)
      .then(setStats)
      .catch(() => setStats(MOCK_STATS))
  }, [user_id])

  function toggleType(t: EventTypeKey) {
    setActiveTypes(prev => {
      const next = new Set(prev)
      if (next.has(t)) next.delete(t)
      else next.add(t)
      return next
    })
  }

  const displayStats = stats ?? MOCK_STATS

  return (
    <div className="min-h-screen relative" style={{ background: '#F8F6F2', paddingTop: 56, paddingBottom: 64 }}>
      <HaloBackground gradFrom={gradFrom} gradTo={gradTo} intensity="subtle" />

      <Navbar
        onLogClick={() => navigate('/app/log')}
        onSettingsClick={() => navigate('/app/settings')}
        onProfileClick={() => navigate('/app/profile')}
      />

      <main className="relative z-10" style={{ maxWidth: 800, margin: '0 auto', padding: '0 24px' }}>
        {/* 返回按钮 */}
        <div style={{ paddingTop: 24, paddingBottom: 8 }}>
          <button
            onClick={() => navigate('/app')}
            style={{
              fontFamily: "'Sora', sans-serif",
              fontSize: 13,
              color: '#888888',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: 0,
              display: 'flex',
              alignItems: 'center',
              gap: 4,
            }}
          >
            ← 返回主页
          </button>
        </div>

        {/* 标题 */}
        <h1
          style={{
            fontFamily: "'Sora', sans-serif",
            fontSize: 20,
            fontWeight: 600,
            color: '#0A0A0A',
            marginBottom: 20,
          }}
        >
          进化日志
        </h1>

        {/* 筛选区 */}
        <div style={{ marginBottom: 24 }}>
          {/* 日期范围 pills */}
          <div className="flex items-center gap-2 flex-wrap" style={{ marginBottom: 12 }}>
            {DATE_RANGE_OPTIONS.map(opt => {
              const isActive = dateRange === opt.key
              return (
                <button
                  key={opt.key}
                  onClick={() => setDateRange(opt.key)}
                  style={{
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: 12,
                    padding: '5px 14px',
                    borderRadius: 4,
                    border: 'none',
                    background: isActive
                      ? `linear-gradient(135deg, ${gradFrom}, ${gradTo})`
                      : '#F0EEE9',
                    color: isActive ? 'white' : '#888888',
                    cursor: 'pointer',
                    transition: 'all 0.15s',
                  }}
                >
                  {opt.label}
                </button>
              )
            })}
          </div>

          {/* 事件类型多选 tags */}
          <div className="flex items-center gap-2 flex-wrap">
            {ALL_EVENT_TYPES.map(t => {
              const g = EVENT_TYPE_GRADIENTS[t]
              const isActive = activeTypes.has(t)
              return (
                <button
                  key={t}
                  onClick={() => toggleType(t)}
                  style={{
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: 11,
                    padding: '4px 12px',
                    borderRadius: 4,
                    border: 'none',
                    background: isActive
                      ? `linear-gradient(135deg, ${hexToRgba(g.from, 0.1)}, ${hexToRgba(g.to, 0.1)})`
                      : '#F0EEE9',
                    cursor: 'pointer',
                    transition: 'all 0.15s',
                    ...(isActive
                      ? {
                          WebkitBackgroundClip: undefined,
                          color: 'transparent',
                          backgroundClip: undefined,
                        }
                      : { color: '#888888' }
                    ),
                  }}
                >
                  {isActive ? (
                    <span
                      style={{
                        background: `linear-gradient(135deg, ${g.from}, ${g.to})`,
                        WebkitBackgroundClip: 'text',
                        WebkitTextFillColor: 'transparent',
                        backgroundClip: 'text',
                      }}
                    >
                      {g.label}
                    </span>
                  ) : (
                    g.label
                  )}
                </button>
              )
            })}
          </div>
        </div>

        {/* 日志条目区 */}
        {loading ? (
          // 骨架屏
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {[1, 2, 3].map(i => (
              <div
                key={i}
                className="animate-pulse"
                style={{
                  height: 52,
                  background: '#F0EEE9',
                  borderRadius: 4,
                }}
              />
            ))}
          </div>
        ) : groups.length === 0 ? (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              paddingTop: 80,
              paddingBottom: 80,
              fontFamily: "'Sora', sans-serif",
              fontSize: 15,
              color: '#AAAAAA',
            }}
          >
            暂无进化记录
          </div>
        ) : (
          <div>
            {groups.map(group => (
              <div key={group.date} style={{ marginBottom: 24 }}>
                {/* 日期分组标题 */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    marginBottom: 12,
                  }}
                >
                  <div style={{ flex: 1, height: 1, background: '#E0DFDB' }} />
                  <span
                    style={{
                      fontFamily: "'IBM Plex Mono', monospace",
                      fontSize: 12,
                      color: '#888888',
                      letterSpacing: '1px',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {group.date}
                  </span>
                  <div style={{ flex: 1, height: 1, background: '#E0DFDB' }} />
                </div>

                {/* 条目列表 */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  {group.items.map(item => (
                    <LogItem
                      key={item.event_id}
                      item={item}
                      gradFrom={gradFrom}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* 底部统计栏 */}
      <div
        style={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          background: 'white',
          borderTop: '1px solid #E0DFDB',
          height: 48,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 20,
        }}
      >
        <p
          style={{
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: 12,
            color: '#888888',
            margin: 0,
          }}
        >
          规则库共{' '}
          <GradientNumber value={displayStats.rules_total} gradFrom={gradFrom} gradTo={gradTo} />{' '}
          条 · 本周新增{' '}
          <GradientNumber value={displayStats.added_this_week} gradFrom={gradFrom} gradTo={gradTo} />{' '}
          · 本周进化{' '}
          <GradientNumber value={displayStats.evolved_this_week} gradFrom={gradFrom} gradTo={gradTo} />{' '}
          次
        </p>
      </div>
    </div>
  )
}

// 单条日志条目组件
function LogItem({ item, gradFrom }: { item: EvolutionEvent; gradFrom: string }) {
  const g = EVENT_TYPE_GRADIENTS[item.event_type] ?? EVENT_TYPE_GRADIENTS.added
  const isConflict = item.event_type === 'conflict'

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '10px 12px',
        borderRadius: 6,
        transition: 'background 0.15s',
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLElement).style.background = hexToRgba(gradFrom, 0.03)
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLElement).style.background = 'transparent'
      }}
    >
      {/* 时间 */}
      <span
        style={{
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: 11,
          color: '#888888',
          width: 50,
          flexShrink: 0,
        }}
      >
        {formatTime(item.ts)}
      </span>

      {/* 渐变点 */}
      <GradientDot
        gradFrom={g.from}
        gradTo={g.to}
        size={8}
        pulse={isConflict}
      />

      {/* Skill 名称 */}
      <span
        style={{
          fontFamily: "'Sora', sans-serif",
          fontSize: 14,
          fontWeight: 500,
          color: '#0A0A0A',
          maxWidth: 180,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          flexShrink: 0,
        }}
      >
        {item.title || item.skill_name}
      </span>

      {/* 变更类型标签 */}
      <span
        style={{
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: 11,
          padding: '2px 8px',
          borderRadius: 4,
          background: `linear-gradient(135deg, ${hexToRgba(g.from, 0.1)}, ${hexToRgba(g.to, 0.1)})`,
          flexShrink: 0,
        }}
      >
        <span
          style={{
            background: `linear-gradient(135deg, ${g.from}, ${g.to})`,
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
          }}
        >
          {item.type_label}
        </span>
      </span>

      {/* 来源说明 */}
      <span
        style={{
          fontFamily: "'Sora', sans-serif",
          fontSize: 12,
          color: '#888888',
          flex: 1,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {item.source}
      </span>

      {/* 操作链接 */}
      {isConflict ? (
        <button
          style={{
            fontFamily: "'Sora', sans-serif",
            fontSize: 12,
            color: '#FF416C',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: 0,
            flexShrink: 0,
          }}
        >
          解决冲突→
        </button>
      ) : (
        <button
          style={{
            fontFamily: "'Sora', sans-serif",
            fontSize: 12,
            background: `linear-gradient(135deg, ${g.from}, ${g.to})`,
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
            border: 'none',
            cursor: 'pointer',
            padding: 0,
            flexShrink: 0,
          }}
        >
          查看详情→
        </button>
      )}
    </div>
  )
}

// 渐变数字组件
function GradientNumber({ value, gradFrom, gradTo }: { value: number; gradFrom: string; gradTo: string }) {
  return (
    <span
      style={{
        background: `linear-gradient(135deg, ${gradFrom}, ${gradTo})`,
        WebkitBackgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
        backgroundClip: 'text',
        fontWeight: 600,
      }}
    >
      {value}
    </span>
  )
}

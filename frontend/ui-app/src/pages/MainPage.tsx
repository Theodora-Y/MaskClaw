/**
 * MainPage — 主页 (/app)
 * 三列布局：skill 卡片网格（2或3列）+ 右侧可折叠进化日志面板。
 * 登录后如有待确认变更，先弹出 ChangeConfirmModal。
 */
import { useState, useMemo, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import useAuthStore from '@/store/authStore'
import { Navbar } from '@/components/layout/Navbar'
import { HaloBackground } from '@/components/ui/OrbBackground'
import { SkillCard } from '@/components/skills/SkillCard'
import { SkillDetailDrawer } from '@/components/skills/SkillDetailDrawer'
import { ChangeConfirmModal } from '@/components/modals/ChangeConfirmModal'
import { LogPanel } from '@/components/log/LogPanel'
import { getTagColor, getTagBg } from '@/lib/tagColorMap'
import { skillApi, notifications, SkillRecord } from '@/lib/api'
import { Bell } from 'lucide-react'
import {
  MOCK_SKILLS,
  MOCK_PENDING_CHANGES,
  ALL_SKILL_TAGS,
  getGreeting,
} from '@/lib/mockData'
import type { SkillCard as SkillCardType } from '@/lib/mockData'

const SESSION_KEY = 'maskclaw-confirmed-session'

// 技能状态优先级排序：冲突 > 警告 > 激活 > 停用
const STATUS_PRIORITY: Record<SkillCardType['status'], number> = {
  conflict: 0,
  warning:  1,
  active:   2,
  disabled: 3,
}

// 从 task_description 中提取与已知 tag 匹配的关键词
const _KNOWN_TAGS = new Set(ALL_SKILL_TAGS)
function _extractSceneTags(desc: string): string[] {
  if (!desc) return []
  const words = desc.split(/[，、,.\s]+/)
  return words
    .filter(w => _KNOWN_TAGS.has(w))
    .slice(0, 3)
}

// app_context_hint → 中文应用名（覆盖 UserC 全部 15 个唯一 app_context_hint）
const _APP_ZH_MAP: Record<string, string> = {
  // 社交通讯
  dingtalk: '钉钉', wechat: '微信', feishu: '飞书', lark: 'Lark',
  email: '邮件', sms: '短信', slack: 'Slack', telegram: 'Telegram',
  // 支付
  alipay: '支付宝',
  // UserC 22 个 rules.json 涉及的全部 app_context_hint
  didienterprise: '企业滴滴',
  procurement: '物资采购',
  attendance: '考勤打卡',
  meeting: '在线会议',
  expense: '报销审批',
  food_delivery: '外卖点餐',
  his: 'HIS系统',
  intranet: '内网办公',
  office: '办公设备',
  calendar: '工作日历',
  xiaohongshu: '小红书',
}
function _slugToZh(slug: string): string {
  // 从 slug 首段推断应用
  const first = slug.split('-')[0] || ''
  return _APP_ZH_MAP[first] || first
}
function _slugToZhFull(slug: string): string {
  return _APP_ZH_MAP[slug] || _slugToZh(slug)
}

// 解析 rules_json_content，返回结构化字段
interface _RjFields {
  scene: string
  app_context_zh: string
  rule_text: string
  sensitive_fields: string[]
  steps_md: string
}
function _parseRulesJson(content: string | null | undefined): _RjFields {
  if (!content) return { scene: '', app_context_zh: '', rule_text: '', sensitive_fields: [], steps_md: '' }
  try {
    const rj: any = typeof content === 'string' ? JSON.parse(content) : content
    const hint: string = rj.app_context_hint || ''
    const sf: string[] = []
    if (rj.sensitive_field) {
      const raw = Array.isArray(rj.sensitive_field) ? rj.sensitive_field.join('、') : String(rj.sensitive_field)
      raw.split(/[、,，]/).forEach((t: string) => { const t2 = t.trim(); if (t2) sf.push(t2) })
    }
    if (rj.field) {
      const raw = Array.isArray(rj.field) ? rj.field.join('、') : String(rj.field)
      raw.split(/[、,，]/).forEach((t: string) => { const t2 = t.trim(); if (t2 && !sf.includes(t2)) sf.push(t2) })
    }
    return {
      scene: rj.scene || '',
      app_context_zh: _APP_ZH_MAP[hint] || _slugToZh(hint) || _slugToZh(''),
      rule_text: rj.rule_text || '',
      sensitive_fields: sf,
      steps_md: '',
    }
  } catch {
    return { scene: '', app_context_zh: '', rule_text: '', sensitive_fields: [], steps_md: '' }
  }
}

// 合并：中文应用 tag + 敏感字段 tag（去重，cap 6）
function _mergeTags(rj: _RjFields): string[] {
  const all = [rj.app_context_zh, ...rj.sensitive_fields].filter(Boolean)
  const seen = new Set<string>()
  const out: string[] = []
  for (const t of all) {
    if (!seen.has(t)) { seen.add(t); out.push(t) }
    if (out.length >= 6) break
  }
  return out
}

export default function MainPage() {
  const { user_id, token, username, gradFrom, gradTo } = useAuthStore()

  const [searchText, setSearchText] = useState('')
  const [activeTags, setActiveTags] = useState<Set<string>>(new Set())
  const [selectedSkill, setSelectedSkill] = useState<SkillCardType | null>(null)
  const [logOpen, setLogOpen] = useState(false)
  const [realSkills, setRealSkills] = useState<SkillCardType[] | null>(null)
  const [realSkillRecords, setRealSkillRecords] = useState<Record<string, SkillRecord>>({})
  const [greetingExpanded, setGreetingExpanded] = useState(() => {
    return sessionStorage.getItem('maskclaw-greeting-shrunk') !== 'true'
  })
  const scrollRef = useRef<HTMLDivElement>(null)

  const [pendingCount, setPendingCount] = useState(0)
  const hasPending = pendingCount > 0
  const [showConfirm, setShowConfirm] = useState(() => {
    if (!hasPending) return false
    return sessionStorage.getItem(SESSION_KEY) !== 'done'
  })

  // 加载后端真实 Skill 列表（含 active + archived，失败时回落 MOCK）
  useEffect(() => {
    if (!user_id || !token) return
    skillApi.getAll(user_id)
      .then(data => {
        const recMap: Record<string, SkillRecord> = {}
        // 合并 active + archived，统一映射
        const all = [...(data.active || []), ...(data.archived || [])]
        const mapped: SkillCardType[] = all.map((s) => {
          recMap[`${s.skill_name}-${s.version}`] = s
          const rj = _parseRulesJson(s.rules_json_content)
          const isActive = Boolean(s.path)
          return {
            skill_id: `${s.skill_name}-${s.version}`,
            slug: s.skill_name,
            name: rj.scene || s.skill_name || '未知规则',
            app_context: rj.app_context_zh || s.app_context || _slugToZh(s.skill_name),
            scene_tags: _mergeTags(rj),
            status: isActive ? 'active' as const : 'disabled' as const,
            last_updated_ts: isActive ? (s.created_ts || 0) : (s.archived_ts || s.created_ts || 0),
            version: s.version || 'v1',
            task_description: rj.rule_text || '',
          }
        })
        setRealSkills(mapped)
        setRealSkillRecords(recMap)
      })
      .catch(() => { /* 保持 null，回落 MOCK */ })
  }, [user_id, token])

  // 加载真实通知数量（铃铛数字来源）
  useEffect(() => {
    if (!user_id || !token) return
    notifications.list(user_id, { status: 'pending', page_size: 1 })
      .then(data => setPendingCount(data.unread ?? 0))
      .catch(() => { /* 失败保持 0 */ })
  }, [user_id, token])

  // 问候语滚动收缩
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const node = el
    function onScroll() {
      if (greetingExpanded && node.scrollTop > 60) {
        setGreetingExpanded(false)
        sessionStorage.setItem('maskclaw-greeting-shrunk', 'true')
      }
    }
    node.addEventListener('scroll', onScroll, { passive: true })
    return () => node.removeEventListener('scroll', onScroll)
  }, [greetingExpanded])

  function handleConfirmClose() {
    sessionStorage.setItem(SESSION_KEY, 'done')
    setShowConfirm(false)
  }

  function handleSkillRefresh(skillId: string) {
    // 保存/删除成功后统一刷新后端真实列表（含 archived），并更新当前选中项
    if (!user_id || !token) return
    skillApi.getAll(user_id)
      .then(data => {
        const recMap: Record<string, SkillRecord> = {}
        const all = [...(data.active || []), ...(data.archived || [])]
        const mapped: SkillCardType[] = all.map((s) => {
          recMap[`${s.skill_name}-${s.version}`] = s
          const rj = _parseRulesJson(s.rules_json_content)
          const isActive = Boolean(s.path)
          return {
            skill_id: `${s.skill_name}-${s.version}`,
            slug: s.skill_name,
            name: rj.scene || s.skill_name || '未知规则',
            app_context: rj.app_context_zh || s.app_context || _slugToZh(s.skill_name),
            scene_tags: _mergeTags(rj),
            status: isActive ? 'active' as const : 'disabled' as const,
            last_updated_ts: isActive ? (s.created_ts || 0) : (s.archived_ts || s.created_ts || 0),
            version: s.version || 'v1',
            task_description: rj.rule_text || '',
          }
        })
        setRealSkills(mapped)
        setRealSkillRecords(recMap)
        // 用最新列表里的 skill 实例替换 selectedSkill，触发详情重新渲染
        const newSelected = mapped.find(s => s.skill_id === skillId)
        if (newSelected) setSelectedSkill(newSelected)
      })
      .catch(() => setRealSkills(null))
  }

  // 多选 tag 切换
  function toggleTag(tag: string) {
    setActiveTags(prev => {
      const next = new Set(prev)
      if (next.has(tag)) next.delete(tag)
      else next.add(tag)
      return next
    })
  }

  // 过滤 + 排序（优先使用后端真实数据，失败时回落 MOCK）
  const filteredSkills = useMemo(() => {
    let list: SkillCardType[] = realSkills ?? MOCK_SKILLS
    if (activeTags.size > 0) {
      list = list.filter(
        s => activeTags.has(s.app_context) || s.scene_tags.some(t => activeTags.has(t))
      )
    }
    if (searchText.trim()) {
      const q = searchText.trim().toLowerCase()
      list = list.filter(
        s =>
          s.name.toLowerCase().includes(q) ||
          s.app_context.toLowerCase().includes(q) ||
          s.scene_tags.some(t => t.toLowerCase().includes(q))
      )
    }
    return [...list].sort((a, b) => STATUS_PRIORITY[a.status] - STATUS_PRIORITY[b.status])
  }, [activeTags, searchText, realSkills])

  // 更丰富的问候语（显示真实规则数量）
  const greetingText = (() => {
    const base = username ?? '用户'
    if (pendingCount > 0) return `${base}，系统有 ${pendingCount} 条新学习结果需要你确认`
    const hour = new Date().getHours()
    const timeStr = hour < 11 ? '早上好' : hour < 18 ? '下午好' : '晚上好'
    const skillCount = (realSkills ?? MOCK_SKILLS).length
    if (skillCount === 0) return `${timeStr}，${base}，开始建立你的第一条隐私规则吧`
    return `${timeStr}，${base}，你的规则库已有 ${skillCount} 条隐私规则`
  })()

  // 从真实 skills 动态提取 tag（替换静态 ALL_SKILL_TAGS）
  const displayTags = useMemo(() => {
    const tagSet = new Set<string>()
    ;(realSkills ?? []).forEach(s => {
      tagSet.add(s.app_context)
      s.scene_tags.forEach(t => tagSet.add(t))
    })
    return [...tagSet].slice(0, 10)
  }, [realSkills])

  return (
    <div style={{ minHeight: '100vh', background: '#F8F6F2', paddingTop: 56 }} className="relative">
      <HaloBackground gradFrom={gradFrom} gradTo={gradTo} intensity="subtle" />

      <Navbar onLogToggle={() => setLogOpen(o => !o)} />

      {/* 主体：卡片区 + 日志面板并排 */}
      <div style={{ display: 'flex', alignItems: 'stretch', height: 'calc(100vh - 56px)', overflow: 'hidden' }} className="relative z-10">

        {/* 左侧内容区 */}
        <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', padding: '0 24px 48px' }}>

          {/* 筛选栏 */}
          <div style={{ paddingTop: 24, paddingBottom: 16 }}>
            {/* 顶行：问候语 + 搜索框 */}
            <div style={{ display: 'flex', alignItems: greetingExpanded ? 'flex-start' : 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>

              {/* 问候语 + 待定规则图标（磁吸文字效果） */}
              <div
                style={{
                  position: 'relative',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  flex: 1,
                  minWidth: 0,
                  cursor: 'default',
                  userSelect: 'none',
                }}
              >
                {/* 底字层 — 始终显示 */}
                <span
                  style={{
                    fontFamily: "'Sora', sans-serif",
                    fontSize: greetingExpanded ? 28 : 20,
                    fontWeight: 300,
                    color: '#1677FF',
                    margin: 0,
                    lineHeight: 1.35,
                    whiteSpace: greetingExpanded ? 'normal' : 'nowrap',
                    overflow: greetingExpanded ? 'visible' : 'hidden',
                    textOverflow: 'ellipsis',
                    transition: 'font-size 0.4s cubic-bezier(0.33,1,0.68,1), white-space 0.3s ease',
                    display: 'block',
                  }}
                >
                  {greetingText}
                </span>

                {/* 右上角 Bell 图标 */}
                <span
                  style={{
                    position: 'absolute',
                    top: greetingExpanded ? -4 : 0,
                    right: 0,
                    flexShrink: 0,
                  }}
                  title={pendingCount > 0 ? `${pendingCount} 条待确认变更` : '暂无待确认变更'}
                >
                  <Bell
                    size={15}
                    style={{
                      color: pendingCount > 0 ? '#F7971E' : '#CCCCCC',
                      fill: pendingCount > 0 ? '#F7971E' : 'none',
                      transition: 'color 0.2s, fill 0.2s',
                    }}
                  />
                </span>
              </div>

              {/* 搜索框 */}
              <input
                type="text"
                placeholder="搜索 Skill..."
                value={searchText}
                onChange={e => setSearchText(e.target.value)}
                style={{
                  fontFamily: "'Sora', sans-serif",
                  fontSize: 13,
                  width: 220,
                  background: 'white',
                  border: '1px solid #E0DFDB',
                  borderRadius: 6,
                  padding: '7px 14px',
                  color: '#0A0A0A',
                  outline: 'none',
                  flexShrink: 0,
                }}
                onFocus={e => {
                  e.target.style.borderColor = gradFrom
                  e.target.style.boxShadow = `0 0 0 2px ${gradFrom}22`
                }}
                onBlur={e => {
                  e.target.style.borderColor = '#E0DFDB'
                  e.target.style.boxShadow = 'none'
                }}
              />
            </div>

            {/* Tag 筛选行（多选，纯色方案） */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 14 }}>
              {/* ALL 按钮 */}
              <button
                type="button"
                onClick={() => setActiveTags(new Set())}
                style={{
                  fontFamily: "'IBM Plex Mono', monospace",
                  fontSize: 11,
                  padding: '3px 11px',
                  borderRadius: 4,
                  border: activeTags.size === 0 ? `1.5px solid #1677FF` : '1px solid #E0DFDB',
                  background: activeTags.size === 0 ? 'rgba(22,119,255,0.08)' : 'transparent',
                  color: activeTags.size === 0 ? '#1677FF' : '#888888',
                  cursor: 'pointer',
                  transition: 'all 0.12s',
                }}
              >
                全部
              </button>
              {displayTags.map(tag => {
                const isActive = activeTags.has(tag)
                const color = getTagColor(tag)
                return (
                  <button
                    key={tag}
                    type="button"
                    onClick={() => toggleTag(tag)}
                    style={{
                      fontFamily: "'IBM Plex Mono', monospace",
                      fontSize: 11,
                      padding: '3px 11px',
                      borderRadius: 4,
                      border: isActive ? `1.5px solid ${color}` : '1px solid #E0DFDB',
                      background: isActive ? getTagBg(tag, 0.12) : 'transparent',
                      color: isActive ? color : '#888888',
                      cursor: 'pointer',
                      transition: 'all 0.12s',
                      fontWeight: isActive ? 600 : 400,
                    }}
                  >
                    {tag}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Skill 卡片网格（列表刷新时淡入） */}
          {filteredSkills.length > 0 ? (
            <motion.div
              key={`skills-${filteredSkills.length}`}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, ease: [0.33, 1, 0.68, 1] }}
              style={{
                display: 'grid',
                gridTemplateColumns: logOpen ? 'repeat(2, 1fr)' : 'repeat(3, 1fr)',
                gap: 14,
              }}
            >
              {filteredSkills.map(skill => (
                <SkillCard
                  key={skill.skill_id}
                  skill={skill}
                  gradFrom={gradFrom}
                  gradTo={gradTo}
                  onClick={() => setSelectedSkill(skill)}
                />
              ))}
            </motion.div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 80 }}>
              <p style={{ fontFamily: "'Sora', sans-serif", fontSize: 14, color: '#AAAAAA', marginBottom: 20 }}>
                {searchText || activeTags.size > 0 ? '没有符合条件的 Skill' : '还没有学到任何隐私规则'}
              </p>
              {!searchText && activeTags.size === 0 && (
                <button
                  style={{
                    fontFamily: "'Sora', sans-serif",
                    fontSize: 13,
                    color: gradFrom,
                    border: `1px solid ${gradFrom}`,
                    background: 'transparent',
                    borderRadius: 6,
                    padding: '8px 20px',
                    cursor: 'pointer',
                  }}
                >
                  完成引导设置
                </button>
              )}
            </div>
          )}
        </div>

        {/* 右侧日志面板 */}
        <LogPanel
          isOpen={logOpen}
          onClose={() => setLogOpen(false)}
          gradFrom={gradFrom}
          gradTo={gradTo}
          userId={user_id}
          token={token}
          onSkillClick={skillName => {
            const found = (realSkills ?? MOCK_SKILLS).find(
              s => s.name === skillName || s.slug === skillName
            )
            if (found) setSelectedSkill(found)
          }}
          onUnreadChange={count => setPendingCount(count)}
        />
      </div>

      {/* Skill 详情抽屉 */}
      <SkillDetailDrawer
        skill={selectedSkill}
        onClose={() => setSelectedSkill(null)}
        gradFrom={gradFrom}
        gradTo={gradTo}
        userId={user_id}
        token={token}
        onDelete={handleSkillRefresh}
        onSave={() => selectedSkill && handleSkillRefresh(selectedSkill.skill_id)}
        skillRecords={realSkillRecords}
      />

      {/* 变更确认弹层 */}
      {showConfirm && (
        <ChangeConfirmModal
          pendingChanges={MOCK_PENDING_CHANGES}
          onClose={handleConfirmClose}
          gradFrom={gradFrom}
          gradTo={gradTo}
          onSkillClick={skillName => {
            const found = (realSkills ?? MOCK_SKILLS).find(
              s => s.name === skillName || s.slug === skillName
            )
            if (found) setSelectedSkill(found)
          }}
        />
      )}
    </div>
  )
}

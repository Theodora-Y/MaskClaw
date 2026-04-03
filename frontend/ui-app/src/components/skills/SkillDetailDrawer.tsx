/**
 * SkillDetailDrawer — 居中卡片式 Skill 详情（不挡导航栏）
 * 展示 Skill 规则内容及进化时间线。
 * 数据来源：优先从 skillRecords（后端 SkillRecord）解析 rules_json/skill_md；
 * 解析失败则回落 MOCK_SKILL_DETAIL。
 */
import { useState, useMemo } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { MoreHorizontal, X, Pencil, Check, Loader2 } from 'lucide-react'
import { GradientDot } from '@/components/ui/GradientDot'
import { MOCK_SKILL_DETAIL } from '@/lib/mockData'
import type { SkillCard, SkillStep, SkillTimelineItem } from '@/lib/mockData'
import { skillApi } from '@/lib/api'
import type { SkillRecord } from '@/lib/api'

interface SkillDetailDrawerProps {
  skill: SkillCard | null
  onClose: () => void
  onDelete?: (skillId: string) => void
  onSave?: () => void
  gradFrom: string
  gradTo: string
  userId?: string | null
  token?: string | null
  skillRecords?: Record<string, SkillRecord>
}

// ── 锁形 SVG 图标 ──────────────────────────────────────────────
function LockIcon({ color }: { color: string }) {
  return (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden>
      <rect x="3" y="7" width="10" height="8" rx="1.5" stroke={color} strokeWidth="1.5" />
      <path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2" stroke={color} strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

// ── 步骤手风琴条目 ─────────────────────────────────────────────
function StepItem({ step, gradFrom }: { step: SkillStep; gradFrom: string }) {
  const [open, setOpen] = useState(true)
  return (
    <div className="mb-2">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-3 py-2 text-left"
        style={{ background: 'none', border: 'none', cursor: 'pointer' }}
      >
        <span style={{
          fontFamily: "'IBM Plex Mono', monospace", fontSize: 12, fontWeight: 600,
          background: `linear-gradient(135deg, ${gradFrom}, ${gradFrom}99)`,
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          backgroundClip: 'text', minWidth: 20, flexShrink: 0,
        }}>
          {String(step.step_num).padStart(2, '0')}
        </span>
        <span style={{ fontFamily: "'Sora', sans-serif", fontSize: 13, fontWeight: 500, color: '#0A0A0A', flex: 1 }}>
          {step.title}
        </span>
        {step.has_privacy_protection && <LockIcon color={gradFrom} />}
        <span style={{
          color: '#CCCCCC', fontSize: 10,
          transform: open ? 'rotate(90deg)' : 'rotate(0deg)',
          transition: 'transform 0.18s', flexShrink: 0,
        }}>▶</span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            style={{ overflow: 'hidden' }}
          >
            <div style={{ background: '#F8F6F2', borderRadius: 6, padding: '12px 16px', marginBottom: 4 }}>
              <p style={{ fontFamily: "'Sora', sans-serif", fontSize: 13, color: '#444444', lineHeight: 1.65, margin: 0 }}>
                {step.action}
              </p>
              {step.exception_handling && (
                <p style={{ fontFamily: "'Sora', sans-serif", fontSize: 12, color: '#F7971E', lineHeight: 1.6, margin: '8px 0 0' }}>
                  ⚠ {step.exception_handling}
                </p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── 时间线条目 ────────────────────────────────────────────────
function TimelineItem({ item, isFirst, gradFrom, gradTo }: {
  item: SkillTimelineItem; isFirst: boolean; gradFrom: string; gradTo: string
}) {
  const dateStr = new Date(item.ts * 1000).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
  return (
    <div className="flex gap-3 relative">
      <div className="flex flex-col items-center" style={{ minWidth: 16 }}>
        <GradientDot gradFrom={gradFrom} gradTo={gradTo} size={8} pulse={isFirst} />
        <div style={{ flex: 1, width: 1.5, background: '#E8E6E0', marginTop: 4 }} />
      </div>
      <div className="pb-5 flex-1">
        <div className="flex items-center gap-2 mb-1">
          <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, color: '#888888' }}>{dateStr}</span>
          <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 10, color: '#888888', border: '1px solid #E0DFDB', borderRadius: 3, padding: '1px 5px' }}>
            {item.type_label}
          </span>
        </div>
        <p style={{ fontFamily: "'Sora', sans-serif", fontSize: 13, color: '#333333', lineHeight: 1.6, margin: 0 }}>{item.summary}</p>
        {item.correction_detail && (
          <p style={{ fontFamily: "'Sora', sans-serif", fontSize: 12, color: '#888888', lineHeight: 1.5, marginTop: 4 }}>{item.correction_detail}</p>
        )}
      </div>
    </div>
  )
}

// ── 区块标题 ──────────────────────────────────────────────────
function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, color: '#888888',
      textTransform: 'uppercase', letterSpacing: '0.08em',
      paddingTop: 20, paddingBottom: 4, borderBottom: '1px solid #F0EEEA', marginBottom: 16,
    }}>
      {children}
    </div>
  )
}

// ── app_context_hint → 中文应用名映射 ─────────────────────────
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
function _appZh(hint: string): string {
  return _APP_ZH_MAP[hint] || hint || ''
}
function _slugToZh(slug: string): string {
  const first = slug.split('-')[0] || ''
  return _APP_ZH_MAP[first] || first
}

// 解析 rules.json content ─────────────────────────────────────
interface _RjResult {
  scene: string
  app_context_zh: string
  rule_text: string
  sensitive_fields: string[]
  scene_description: string
  privacy_constraints: string[]
}
function _parseRulesJson(content: string | null | undefined): _RjResult {
  const base = { scene: '', app_context_zh: '', rule_text: '', sensitive_fields: [], scene_description: '', privacy_constraints: [] }
  if (!content) return base
  try {
    const rj = typeof content === 'string' ? JSON.parse(content) : content
    const hint: string = rj.app_context_hint || ''
    const sf: string[] = []
    for (const raw of [rj.sensitive_field, rj.field]) {
      if (!raw) continue
      const s = Array.isArray(raw) ? raw.join('、') : String(raw)
      s.split(/[、,，]/).forEach(t => { const v = t.trim(); if (v) sf.push(v) })
    }
    const scene = rj.scene || ''
    const rule_text = rj.rule_text || ''
    const constraints: string[] = []
    if (rule_text) constraints.push(rule_text)
    sf.forEach(f => { const label = `需保护信息：${f}`; if (!constraints.includes(label)) constraints.push(label) })
    return {
      scene,
      app_context_zh: _APP_ZH_MAP[hint] || _slugToZh(hint),
      rule_text,
      sensitive_fields: [...new Set(sf)],
      scene_description: scene,
      privacy_constraints: constraints,
    }
  } catch {
    return base
  }
}

// 从 skill_md_content 提取执行步骤行 + 边界情况 ───────────────────
// skill_body 格式：## 执行步骤 → 步骤行 → ## 边界情况 → 边界情况行
// 两类行格式相同（都以 `- [` 开头），只能通过章节标题区分
function _extractStepsAndExceptions(md: string): { steps: SkillStep[], exceptions: string[] } {
  const steps: SkillStep[] = []
  const exceptions: string[] = []
  const lines = md.split('\n')
  let inStepSection = false
  let inExceptionSection = false

  for (const line of lines) {
    // 检测章节标题切换
    if (/^#{1,2}\s/.test(line)) {
      inStepSection = line.includes('执行步骤') || (line.includes('步骤') && !line.includes('边界'))
      inExceptionSection = line.includes('边界情况')
      continue
    }

    // 边界情况行单独收集，不加入步骤列表
    if (inExceptionSection && line.trim().startsWith('- [')) {
      const text = line.replace(/^[-*]\s*\[[ xX]\]\s*/, '').trim()
      if (text) exceptions.push(text)
      continue
    }

    // 步骤行
    if (inStepSection && (line.trim().startsWith('- [ ]') || line.trim().startsWith('-'))) {
      const action = line.replace(/^[-*]\s*\[[ xX]\]\s*/, '').trim()
      if (action) {
        steps.push({
          step_num: steps.length + 1,
          title: action.slice(0, 40),
          action,
          has_privacy_protection: /保护|脱敏|隐藏|mask/.test(action),
        })
      }
    }

    // 遇到下一个二级标题结束
    if (inStepSection && line.startsWith('##')) break
  }

  return { steps, exceptions }
}

// ── 解析 SkillRecord → 详情结构 ──────────────────────────────
function parseDetail(skill: SkillCard, records?: Record<string, SkillRecord>) {
  const record = records?.[skill.skill_id]
  if (!record) return MOCK_SKILL_DETAIL

  const rj = _parseRulesJson(record.rules_json_content)

  let steps: SkillStep[] = []
  // 优先从 rules_json.steps
  try {
    if (record.rules_json_content) {
      const parsed = JSON.parse(record.rules_json_content)
      if (Array.isArray(parsed.steps) && parsed.steps.length > 0) {
        steps = parsed.steps.map((s: any, i: number) => ({
          step_num: s.step_num ?? i + 1,
          title: s.title || `步骤 ${i + 1}`,
          action: s.action || s.description || '',
          exception_handling: s.exception_handling,
          has_privacy_protection: Boolean(s.has_privacy_protection),
        }))
      }
    }
  } catch { /* ignore */ }

  // 尝试从 skill_md_content 提取步骤（区分步骤/边界情况章节）
  if (!steps.length && record.skill_md_content) {
    const { steps: extracted, exceptions } = _extractStepsAndExceptions(record.skill_md_content)
    steps = extracted.map((s, i) => ({
      ...s,
      exception_handling: exceptions[i] || undefined,
    }))
  }

  // scene_description 回退
  const scene_description = rj.scene_description || skill.task_description || `${skill.app_context} · ${skill.name}`

  return {
    ...skill,
    // 中文长场景作 title
    _sceneTitle: rj.scene || skill.task_description || skill.name,
    _appZh: rj.app_context_zh || _appZh(''),
    _tags: [rj.app_context_zh, ...rj.sensitive_fields].filter(Boolean).slice(0, 6),
    content: {
      scene_description,
      privacy_constraints: rj.privacy_constraints.length ? rj.privacy_constraints : MOCK_SKILL_DETAIL.content.privacy_constraints,
      steps: steps.length ? steps : MOCK_SKILL_DETAIL.content.steps,
    },
    timeline: [
      {
        ts: record.created_ts || skill.last_updated_ts,
        event_type: 'added' as const,
        type_label: '规则发布',
        summary: `${skill.name} 已生效`,
        source: record.strategy ? `策略: ${record.strategy}` : '用户纠错',
        correction_detail: record.rule_text || undefined,
      },
    ],
  }
}

// ── 编辑表单 ──────────────────────────────────────────────────
function EditForm({ skill, records, onSave, onCancel, saving }: {
  skill: SkillCard
  records: Record<string, SkillRecord> | undefined
  onSave: (scene: string, rule_text: string) => void
  onCancel: () => void
  saving: boolean
}) {
  // 从 records prop 读取真实 scene / rule_text（SkillCard 本身不含这两个字段）
  const rec = records?.[skill.skill_id]
  const [scene, setScene] = useState(rec?.scene || '')
  const [ruleText, setRuleText] = useState(rec?.rule_text || '')
  return (
    <div style={{ padding: '16px 0 8px' }}>
      <SectionTitle>编辑元数据</SectionTitle>
      <div style={{ marginBottom: 12 }}>
        <label style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, color: '#888888', display: 'block', marginBottom: 4 }}>应用场景</label>
        <input
          type="text" value={scene}
          onChange={e => setScene(e.target.value)}
          style={{ width: '100%', padding: '7px 12px', border: '1px solid #E0DFDB', borderRadius: 6, fontFamily: "'Sora', sans-serif", fontSize: 13, color: '#0A0A0A', boxSizing: 'border-box', outline: 'none' }}
        />
      </div>
      <div style={{ marginBottom: 16 }}>
        <label style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, color: '#888888', display: 'block', marginBottom: 4 }}>规则描述</label>
        <textarea
          value={ruleText}
          onChange={e => setRuleText(e.target.value)}
          rows={3}
          style={{ width: '100%', padding: '7px 12px', border: '1px solid #E0DFDB', borderRadius: 6, fontFamily: "'Sora', sans-serif", fontSize: 13, color: '#0A0A0A', boxSizing: 'border-box', outline: 'none', resize: 'vertical' }}
        />
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <button
          onClick={() => onSave(scene, ruleText)}
          disabled={saving}
          style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 16px', borderRadius: 6, border: 'none', background: saving ? '#CCCCCC' : '#1677FF', color: 'white', fontFamily: "'Sora', sans-serif", fontSize: 13, cursor: saving ? 'not-allowed' : 'pointer' }}
        >
          {saving ? <><Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} />保存中</> : <><Check size={13} />保存</>}
        </button>
        <button
          onClick={onCancel}
          disabled={saving}
          style={{ padding: '7px 16px', borderRadius: 6, border: '1px solid #E0DFDB', background: 'white', color: '#888888', fontFamily: "'Sora', sans-serif", fontSize: 13, cursor: 'pointer' }}
        >
          取消
        </button>
      </div>
    </div>
  )
}

// ── 主组件 ────────────────────────────────────────────────────
export function SkillDetailDrawer({ skill, onClose, onDelete, onSave, gradFrom, gradTo, userId, token, skillRecords }: SkillDetailDrawerProps) {
  const detail = useMemo(() => skill ? parseDetail(skill, skillRecords) : null, [skill, skillRecords])

  const [menuOpen, setMenuOpen] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const [acting, setActing] = useState(false)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)

  function showToast(msg: string) {
    setToast(msg)
    setTimeout(() => setToast(null), 2000)
  }

  async function handleArchive() {
    if (!skill || !userId || acting) return
    setActing(true)
    try {
      await skillApi.archive(userId, skill.slug, skill.version)
      showToast('已停用')
      onClose()
    } catch { showToast('停用失败，请重试') }
    finally { setActing(false) }
  }

  async function handleRestore() {
    if (!skill || !userId || acting) return
    setActing(true)
    try {
      await skillApi.restore(userId, skill.slug, skill.version)
      showToast('已启用')
      onClose()
    } catch { showToast('启用失败，请重试') }
    finally { setActing(false) }
  }

  async function handleDelete() {
    if (!skill || !userId || acting) return
    if (!window.confirm(`确认删除「${skill.name}」？删除后将无法恢复。`)) return
    setActing(true)
    try {
      await skillApi.delete(userId, skill.slug, skill.version)
      showToast('已删除')
      onDelete?.(skill.skill_id)
      onClose()
    } catch { showToast('删除失败，请重试') }
    finally { setActing(false) }
  }

  async function handleEditSave(scene: string, rule_text: string) {
    if (!skill || !userId) return
    setSaving(true)
    try {
      await skillApi.updateMeta(userId, skill.slug, { scene, rule_text })
      showToast('已保存')
      setEditing(false)
      onSave?.()
    } catch { showToast('保存失败，请重试') }
    finally { setSaving(false) }
  }

  const statusLabel: Record<string, string> = { active: '运行中', warning: '警告', conflict: '冲突', disabled: '已停用' }
  const statusColor: Record<string, string> = { active: '#0BA360', warning: '#F7971E', conflict: '#FF416C', disabled: '#AAAAAA' }

  return (
    <AnimatePresence>
      {skill && detail && (
        <>
          {/* 遮罩（从导航栏下方开始，不遮挡导航栏） */}
          <motion.div
            key="drawer-mask"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.22 }}
            style={{
              position: 'fixed', top: 56, left: 0, right: 0, bottom: 0,
              background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(4px)',
              zIndex: 40,
            }}
            onClick={onClose}
          />

          {/* 居中卡片 */}
          <motion.div
            key="drawer-panel"
            initial={{ scale: 0.94, opacity: 0, x: '-50%', y: '-50%' }}
            animate={{ scale: 1, opacity: 1, x: '-50%', y: '-50%' }}
            exit={{ scale: 0.94, opacity: 0, x: '-50%', y: '-50%' }}
            transition={{ type: 'spring', stiffness: 380, damping: 38 }}
            style={{
              position: 'fixed',
              top: '50%',
              left: '50%',
              width: 680,
              maxWidth: '92vw',
              maxHeight: 'calc(100vh - 56px - 48px)',
              zIndex: 50,
              background: 'white',
              borderRadius: 12,
              boxShadow: '0 24px 64px rgba(0,0,0,0.16)',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}
          >
            {/* Toast */}
            {toast && (
              <div style={{
                position: 'absolute', top: 70, right: 24, zIndex: 100,
                background: 'white', border: '1px solid #E0DFDB', borderRadius: 6,
                padding: '8px 16px', boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
                fontFamily: "'Sora', sans-serif", fontSize: 13, color: '#0A0A0A',
              }}>
                {toast}
              </div>
            )}

            {/* 顶部渐变色条 */}
            <div style={{
              height: 3,
              background: `linear-gradient(135deg, ${gradFrom}, ${gradTo})`,
              flexShrink: 0,
            }} />

            {/* 头部 */}
            <div style={{ padding: '20px 24px', borderBottom: '1px solid #F0EEEA', flexShrink: 0 }}>
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  {/* 主标题：中文长场景句 */}
                  <h2 style={{ fontFamily: "'Sora', sans-serif", fontSize: 20, fontWeight: 600, color: '#0A0A0A', margin: 0, lineHeight: 1.35 }}>
                    {detail._sceneTitle}
                  </h2>
                  {/* 副标题：slug（技术标识，小字灰色） */}
                  <p style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, color: '#BBBBBB', margin: '3px 0 0' }}>
                    {skill.name}
                  </p>
                  {/* Tag 行：中文应用 + 敏感字段 */}
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {(detail._tags ?? []).map(tag => (
                      <span key={tag} style={{
                        fontFamily: "'IBM Plex Mono', monospace", fontSize: 11,
                        borderRadius: 4, padding: '2px 8px',
                        background: `linear-gradient(135deg, ${gradFrom}18, ${gradTo}18)`,
                        color: gradFrom,
                      }}>
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>

                {/* 右侧：状态标签 + 三点菜单 + 关闭 */}
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span style={{
                    fontFamily: "'IBM Plex Mono', monospace", fontSize: 12,
                    color: statusColor[skill.status] ?? '#888888',
                    border: `1px solid ${statusColor[skill.status] ?? '#888888'}`,
                    borderRadius: 4, padding: '3px 10px',
                  }}>
                    {statusLabel[skill.status] ?? skill.status}
                  </span>

                  {/* 三点菜单 */}
                  <div style={{ position: 'relative' }}>
                    <button
                      onClick={() => setMenuOpen(o => !o)}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4, borderRadius: 4 }}
                      onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = '#F0EEE9' }}
                      onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}
                    >
                      <MoreHorizontal size={18} style={{ color: '#888888' }} />
                    </button>
                    {menuOpen && (
                      <div style={{
                        position: 'absolute', right: 0, top: 32,
                        width: 120, background: 'white', borderRadius: 8,
                        border: '1px solid #E0DFDB', boxShadow: '0 4px 16px rgba(0,0,0,0.10)',
                        zIndex: 10, overflow: 'hidden',
                      }}>
                        <button
                          onClick={() => { setMenuOpen(false); setEditing(true) }}
                          style={{ width: '100%', textAlign: 'left', padding: '8px 12px', fontSize: 13, fontFamily: "'Sora', sans-serif", background: 'none', border: 'none', cursor: 'pointer', color: '#0A0A0A', display: 'flex', alignItems: 'center', gap: 6 }}
                          onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = '#F0EEE9' }}
                          onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}
                        ><Pencil size={13} />编辑</button>
                        <button
                          onClick={() => { setMenuOpen(false); skill.status === 'disabled' ? handleRestore() : handleArchive() }}
                          disabled={acting}
                          style={{ width: '100%', textAlign: 'left', padding: '8px 12px', fontSize: 13, fontFamily: "'Sora', sans-serif", background: 'none', border: 'none', cursor: acting ? 'not-allowed' : 'pointer', color: acting ? '#AAAAAA' : '#0A0A0A' }}
                          onMouseEnter={e => { if (!acting) (e.currentTarget as HTMLElement).style.background = '#F0EEE9' }}
                          onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}
                        >{skill.status === 'disabled' ? '启用' : '停用'}</button>
                        <button
                          onClick={() => { setMenuOpen(false); handleDelete() }}
                          disabled={acting}
                          style={{ width: '100%', textAlign: 'left', padding: '8px 12px', fontSize: 13, fontFamily: "'Sora', sans-serif", background: 'none', border: 'none', cursor: acting ? 'not-allowed' : 'pointer', color: acting ? '#AAAAAA' : '#FF416C' }}
                          onMouseEnter={e => { if (!acting) (e.currentTarget as HTMLElement).style.background = '#FFF5F6' }}
                          onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}
                        >删除</button>
                      </div>
                    )}
                  </div>

                  <button
                    type="button"
                    onClick={onClose}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: '#AAAAAA', lineHeight: 1, padding: '2px 4px' }}
                    title="关闭"
                  >
                    <X size={18} />
                  </button>
                </div>
              </div>
            </div>

            {/* 规则主体（可滚动） */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '0 24px 24px' }}>

              {/* 编辑表单 */}
              {editing && (
                <EditForm
                  skill={skill}
                  records={skillRecords}
                  onSave={handleEditSave}
                  onCancel={() => setEditing(false)}
                  saving={saving}
                />
              )}

              {/* 场景描述 */}
              <SectionTitle>Scene Description</SectionTitle>
              <p style={{ fontFamily: "'Sora', sans-serif", fontSize: 13, color: '#444444', lineHeight: 1.7, margin: '0 0 16px' }}>
                {detail.content.scene_description}
              </p>

              {/* 隐私约束 */}
              <SectionTitle>Privacy Constraints</SectionTitle>
              <ul className="m-0 p-0 list-none" style={{ paddingBottom: 4 }}>
                {detail.content.privacy_constraints.map((c, i) => (
                  <li key={i} className="flex items-start gap-2 mb-2" style={{ fontFamily: "'Sora', sans-serif", fontSize: 13, color: '#333333', lineHeight: 1.65 }}>
                    <GradientDot gradFrom={gradFrom} gradTo={gradTo} size={6} className="mt-1.5 flex-shrink-0" />
                    {c}
                  </li>
                ))}
              </ul>

              {/* 操作流程 */}
              <SectionTitle>Operation Flow</SectionTitle>
              <div style={{ paddingBottom: 4 }}>
                {detail.content.steps.map(step => (
                  <StepItem key={step.step_num} step={step} gradFrom={gradFrom} />
                ))}
              </div>

              {/* 进化时间线 */}
              <SectionTitle>Evolution Timeline</SectionTitle>
              <div className="pt-2 pb-4">
                {detail.timeline.map((item, i) => (
                  <TimelineItem
                    key={item.ts}
                    item={item}
                    isFirst={i === detail.timeline.length - 1}
                    gradFrom={gradFrom}
                    gradTo={gradTo}
                  />
                ))}
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

export default SkillDetailDrawer

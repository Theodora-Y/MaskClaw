/**
 * ChangeConfirmModal — 变更确认弹层
 * 登录后首次显示，列出所有 pending changes，用户必须逐条确认/拒绝。
 * 全部处理完后「进入系统」按钮激活。顶部带警示橙黄渐变色条。
 */
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { GradientDot } from '@/components/ui/GradientDot'
import type { PendingChange } from '@/lib/mockData'

interface ChangeConfirmModalProps {
  pendingChanges: PendingChange[]
  onClose: () => void
  gradFrom: string
  gradTo: string
  onSkillClick?: (skillName: string) => void
}

type Decision = 'accepted' | 'rejected' | null

// 事件类型 → 标签颜色
const EVENT_TYPE_STYLE: Record<
  PendingChange['event_type'],
  { bg: string; color: string }
> = {
  added:    { bg: '#E8F5E9', color: '#0BA360' },
  conflict: { bg: '#FFEBEE', color: '#FF416C' },
  disabled: { bg: '#F5F5F5', color: '#888888' },
}

export function ChangeConfirmModal({
  pendingChanges,
  onClose,
  gradFrom,
  gradTo,
  onSkillClick,
}: ChangeConfirmModalProps) {
  const [decisions, setDecisions] = useState<Record<string, Decision>>(
    () => Object.fromEntries(pendingChanges.map(c => [c.event_id, null]))
  )

  const allHandled = pendingChanges.every(c => decisions[c.event_id] !== null)

  function decide(eventId: string, d: 'accepted' | 'rejected') {
    setDecisions(prev => ({ ...prev, [eventId]: d }))
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(4px)' }}
    >
      <motion.div
        initial={{ scale: 0.96, opacity: 0, y: 12 }}
        animate={{ scale: 1, opacity: 1, y: 0 }}
        transition={{ type: 'spring', stiffness: 320, damping: 30 }}
        className="bg-white"
        style={{
          width: 520,
          maxWidth: '94vw',
          maxHeight: '88vh',
          display: 'flex',
          flexDirection: 'column',
          borderRadius: 10,
          overflow: 'hidden',
          boxShadow: '0 24px 64px rgba(0,0,0,0.18)',
        }}
      >
        {/* 顶部橙黄渐变警示色条 */}
        <div
          style={{
            height: 3,
            background: 'linear-gradient(135deg, #F7971E, #FFD200)',
            flexShrink: 0,
          }}
        />

        {/* 标题区 */}
        <div style={{ padding: '20px 24px 16px', borderBottom: '1px solid #F0EEEA', flexShrink: 0 }}>
          <div className="flex items-center gap-2 mb-1">
            <GradientDot gradFrom="#F7971E" gradTo="#FFD200" size={8} pulse />
            <span
              style={{
                fontFamily: "'Sora', sans-serif",
                fontSize: 16,
                fontWeight: 600,
                color: '#0A0A0A',
              }}
            >
              学习结果需要你确认
            </span>
          </div>
          <p
            style={{
              fontFamily: "'Sora', sans-serif",
              fontSize: 13,
              color: '#888888',
              margin: 0,
            }}
          >
            在你离开的时候，系统共新学习了 {pendingChanges.length} 条隐私规则。请逐条确认后进入系统。
          </p>
        </div>

        {/* 变更列表 */}
        <div style={{ overflowY: 'auto', flex: 1, padding: '12px 24px' }}>
          {pendingChanges.map((change, idx) => {
            const decision = decisions[change.event_id]
            const typeStyle = EVENT_TYPE_STYLE[change.event_type]

            return (
              <motion.div
                key={change.event_id}
                initial={{ opacity: 0, x: 16 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.06, duration: 0.24, ease: 'easeOut' }}
                style={{
                  padding: '14px 0',
                  borderBottom: idx < pendingChanges.length - 1 ? '1px solid #F5F3EF' : 'none',
                  opacity: decision !== null ? 0.55 : 1,
                  transition: 'opacity 0.2s',
                }}
              >
                {/* 顶行：圆点 + skill 名 + 类型标签 */}
                <div className="flex items-center gap-2 mb-2">
                  <GradientDot gradFrom={gradFrom} gradTo={gradTo} size={7} />
                  <button
                    type="button"
                    onClick={() => onSkillClick?.(change.skill_name)}
                    style={{
                      fontFamily: "'Sora', sans-serif",
                      fontSize: 14,
                      fontWeight: 600,
                      color: '#0A0A0A',
                      background: 'none',
                      border: 'none',
                      cursor: onSkillClick ? 'pointer' : 'default',
                      padding: 0,
                      textDecoration: onSkillClick ? 'underline' : 'none',
                      textDecorationColor: '#CCCCCC',
                      textUnderlineOffset: 2,
                    }}
                  >
                    {change.skill_name}
                  </button>
                  <span
                    style={{
                      fontFamily: "'IBM Plex Mono', monospace",
                      fontSize: 10,
                      background: typeStyle.bg,
                      color: typeStyle.color,
                      borderRadius: 3,
                      padding: '2px 6px',
                      flexShrink: 0,
                    }}
                  >
                    {change.type_label}
                  </span>

                  {/* 决策状态标记 */}
                  {decision !== null && (
                    <span
                      style={{
                        marginLeft: 'auto',
                        fontSize: 13,
                        color: decision === 'accepted' ? '#0BA360' : '#FF416C',
                      }}
                    >
                      {decision === 'accepted' ? '✓ 已确认' : '✗ 已拒绝'}
                    </span>
                  )}
                </div>

                {/* 摘要描述 */}
                <p
                  style={{
                    fontFamily: "'Sora', sans-serif",
                    fontSize: 13,
                    color: '#555555',
                    lineHeight: 1.6,
                    margin: '0 0 10px 18px',
                  }}
                >
                  {change.summary}
                </p>

                {/* 确认/拒绝按钮（未决策时显示） */}
                {decision === null && (
                  <div className="flex gap-2" style={{ paddingLeft: 18 }}>
                    <button
                      type="button"
                      onClick={() => decide(change.event_id, 'accepted')}
                      style={{
                        fontFamily: "'Sora', sans-serif",
                        fontSize: 12,
                        color: '#0BA360',
                        border: '1px solid #0BA360',
                        background: 'none',
                        borderRadius: 4,
                        padding: '4px 14px',
                        cursor: 'pointer',
                      }}
                    >
                      ✓ 确认
                    </button>
                    <button
                      type="button"
                      onClick={() => decide(change.event_id, 'rejected')}
                      style={{
                        fontFamily: "'Sora', sans-serif",
                        fontSize: 12,
                        color: '#FF416C',
                        border: '1px solid #FF416C',
                        background: 'none',
                        borderRadius: 4,
                        padding: '4px 14px',
                        cursor: 'pointer',
                      }}
                    >
                      ✗ 拒绝
                    </button>
                  </div>
                )}
              </motion.div>
            )
          })}
        </div>

        {/* 底部操作区 */}
        <div
          style={{
            padding: '16px 24px',
            borderTop: '1px solid #F0EEEA',
            flexShrink: 0,
          }}
        >
          <AnimatePresence>
            {allHandled ? (
              <motion.button
                key="enter-btn-active"
                type="button"
                initial={{ opacity: 0, scale: 0.97 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.2 }}
                onClick={onClose}
                className="w-full relative overflow-hidden"
                style={{
                  background: `linear-gradient(135deg, ${gradFrom}, ${gradTo})`,
                  border: 'none',
                  borderRadius: 6,
                  padding: '12px 0',
                  cursor: 'pointer',
                  fontFamily: "'Sora', sans-serif",
                  fontSize: 14,
                  fontWeight: 600,
                  color: 'white',
                  boxShadow: `0 4px 16px rgba(0,0,0,0.15)`,
                }}
              >
                {/* pulse 动画光圈 */}
                <span
                  className="absolute inset-0 rounded animate-ping"
                  style={{
                    background: `linear-gradient(135deg, ${gradFrom}40, ${gradTo}40)`,
                    animationDuration: '1.6s',
                  }}
                />
                <span className="relative">进入系统</span>
              </motion.button>
            ) : (
              <button
                key="enter-btn-disabled"
                type="button"
                disabled
                style={{
                  width: '100%',
                  background: '#F0EEEA',
                  border: 'none',
                  borderRadius: 6,
                  padding: '12px 0',
                  cursor: 'not-allowed',
                  fontFamily: "'Sora', sans-serif",
                  fontSize: 14,
                  fontWeight: 600,
                  color: '#AAAAAA',
                }}
              >
                请处理全部 {pendingChanges.filter(c => decisions[c.event_id] === null).length} 条变更
              </button>
            )}
          </AnimatePresence>
        </div>
      </motion.div>
    </div>
  )
}

export default ChangeConfirmModal

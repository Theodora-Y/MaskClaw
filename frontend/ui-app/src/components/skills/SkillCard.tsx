/**
 * SkillCard — 重设计版
 * 布局：顶行 tag pills + 状态徽章 → 日期小字 → 描述行 → 底部大标题
 */
import { GradientCard } from '@/components/ui/GradientCard'
import { getTagColor, getTagBg } from '@/lib/tagColorMap'
import type { SkillCard as SkillCardType } from '@/lib/mockData'

interface SkillCardProps {
  skill: SkillCardType
  gradFrom: string
  gradTo: string
  onClick?: () => void
}

const STATUS_INTENSITY: Record<SkillCardType['status'], 'default' | 'warning' | 'conflict' | 'dim'> = {
  active:   'default',
  warning:  'warning',
  conflict: 'conflict',
  disabled: 'dim',
}

const STATUS_BADGE: Record<SkillCardType['status'], { bg: string; color: string; label: string }> = {
  active:   { bg: 'rgba(7,193,96,0.12)',   color: '#07C160', label: '运行中' },
  warning:  { bg: 'rgba(247,151,30,0.12)', color: '#F7971E', label: '注意' },
  conflict: { bg: 'rgba(255,65,108,0.12)', color: '#FF416C', label: '冲突' },
  disabled: { bg: 'rgba(136,136,136,0.12)',color: '#888888', label: '停用' },
}

function formatDate(ts: number): string {
  const d = new Date(ts * 1000)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${mm}-${dd}`
}

export function SkillCard({ skill, gradFrom, gradTo, onClick }: SkillCardProps) {
  const intensity = STATUS_INTENSITY[skill.status]
  const badge = STATUS_BADGE[skill.status]
  const allTags = [...new Set([skill.app_context, ...skill.scene_tags])]

  return (
    <GradientCard
      gradFrom={gradFrom}
      gradTo={gradTo}
      intensity={intensity}
      hover
      onClick={onClick}
      className="w-full h-full"
    >
      <div style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 8, height: '100%' }}>

        {/* 顶部：Tag pills + 状态徽章 */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
          {/* Tag pills */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, flex: 1, minWidth: 0 }}>
            {allTags.map(tag => (
              <span
                key={tag}
                style={{
                  background: getTagBg(tag, 0.15),
                  color: getTagColor(tag),
                  borderRadius: 4,
                  padding: '2px 7px',
                  fontSize: 11,
                  fontFamily: "'IBM Plex Mono', monospace",
                  fontWeight: 500,
                  whiteSpace: 'nowrap',
                }}
              >
                {tag}
              </span>
            ))}
          </div>

          {/* 状态徽章 */}
          <span
            style={{
              background: badge.bg,
              color: badge.color,
              borderRadius: 20,
              padding: '2px 9px',
              fontSize: 11,
              fontFamily: "'IBM Plex Mono', monospace",
              fontWeight: 600,
              whiteSpace: 'nowrap',
              flexShrink: 0,
              display: 'flex',
              alignItems: 'center',
              gap: 4,
            }}
          >
            <span
              style={{
                width: 5,
                height: 5,
                borderRadius: '50%',
                background: badge.color,
                display: 'inline-block',
                flexShrink: 0,
              }}
            />
            {badge.label}
          </span>
        </div>

        {/* 日期小字 */}
        <div
          style={{
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: 11,
            color: '#AAAAAA',
            letterSpacing: '0.02em',
          }}
        >
          {formatDate(skill.last_updated_ts)}
        </div>

        {/* 描述行（task_description） */}
        {skill.task_description && (
          <div
            style={{
              fontFamily: "'Sora', sans-serif",
              fontSize: 12,
              color: '#666666',
              lineHeight: 1.6,
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
            }}
          >
            {skill.task_description}
          </div>
        )}

        {/* 底部大标题（skill name） */}
        <div
          style={{
            fontFamily: "'Sora', sans-serif",
            fontSize: 16,
            fontWeight: 700,
            color: '#0A0A0A',
            lineHeight: 1.35,
            marginTop: 'auto',
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {skill.name}
        </div>

      </div>
    </GradientCard>
  )
}

export default SkillCard

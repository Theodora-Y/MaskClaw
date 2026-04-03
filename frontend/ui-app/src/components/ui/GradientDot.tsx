/**
 * GradientDot — 渐变色圆点指示器
 * 替代普通实心圆点，用于 Skill 卡片状态、时间线节点等处。
 * 支持实心/空心/pulse 三种变体。
 */
import { cn } from '@/lib/utils'

interface GradientDotProps {
  gradFrom: string
  gradTo: string
  size?: number      // 默认 8px
  pulse?: boolean    // 是否叠加 ping 外圈（用于 conflict/pending 状态）
  hollow?: boolean   // 空心圆（disabled 状态）
  className?: string
}

export function GradientDot({
  gradFrom,
  gradTo,
  size = 8,
  pulse = false,
  hollow = false,
  className,
}: GradientDotProps) {
  const solidStyle: React.CSSProperties = {
    width: size,
    height: size,
    borderRadius: '50%',
    flexShrink: 0,
    background: `linear-gradient(135deg, ${gradFrom}, ${gradTo})`,
    boxShadow: 'inset 0 1px 1px rgba(255,255,255,0.35)',
  }

  const hollowStyle: React.CSSProperties = {
    width: size,
    height: size,
    borderRadius: '50%',
    flexShrink: 0,
    border: `1.5px solid ${gradFrom}`,
    background: 'transparent',
  }

  const dotStyle = hollow ? hollowStyle : solidStyle

  if (!pulse) {
    return (
      <span
        className={cn('inline-block', className)}
        style={dotStyle}
        aria-hidden
      />
    )
  }

  // pulse 模式：外圈 ping 动画
  const pingSize = size + 4
  return (
    <span
      className={cn('relative inline-flex items-center justify-center flex-shrink-0', className)}
      style={{ width: pingSize, height: pingSize }}
      aria-hidden
    >
      {/* ping 外圈 */}
      <span
        className="absolute inset-0 rounded-full animate-ping"
        style={{
          borderRadius: '50%',
          background: `linear-gradient(135deg, ${gradFrom}, ${gradTo})`,
          opacity: 0.35,
        }}
      />
      {/* 实心圆点 */}
      <span
        className="relative"
        style={{
          ...dotStyle,
          width: size,
          height: size,
        }}
      />
    </span>
  )
}

export default GradientDot

/**
 * GradientCard — 渐变边框卡片
 *
 * 使用 CSS padding-box / border-box 双背景实现渐变边框。
 * 内部背景纯白，边框呈用户渐变色。
 * intensity 控制发光强度：'default' 正常，'dim' 停用状态（灰色边框）。
 */
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'

interface GradientCardProps {
  gradFrom?: string
  gradTo?: string
  intensity?: 'default' | 'dim' | 'warning' | 'conflict'
  hover?: boolean
  className?: string
  children: React.ReactNode
  onClick?: () => void
}

const INTENSITY_GRADIENTS = {
  default: null, // 使用 gradFrom/gradTo
  dim:      { from: '#BDBDBD', to: '#D4D4D4' },
  warning:  { from: '#F7971E', to: '#FFD200' },
  conflict: { from: '#FF416C', to: '#FF4B2B' },
}

export function GradientCard({
  gradFrom = '#FF416C',
  gradTo = '#6A82FB',
  intensity = 'default',
  hover = true,
  className,
  children,
  onClick,
}: GradientCardProps) {
  const preset = INTENSITY_GRADIENTS[intensity]
  const from = preset ? preset.from : gradFrom
  const to = preset ? preset.to : gradTo

  const borderGradient = `linear-gradient(135deg, ${from}, ${to})`
  const bgTint = intensity === 'dim'
    ? 'transparent'
    : `linear-gradient(135deg, rgba(${hexToRgbStr(from)},0.03), rgba(${hexToRgbStr(to)},0.03))`

  const cardStyle: React.CSSProperties = {
    background: `${bgTint}, linear-gradient(#fff, #fff) padding-box, ${borderGradient} border-box`,
    border: '1.5px solid transparent',
    borderRadius: '8px',
  }

  if (!hover) {
    return (
      <div style={cardStyle} className={cn('bg-white', className)} onClick={onClick}>
        {children}
      </div>
    )
  }

  return (
    <motion.div
      style={cardStyle}
      className={cn('bg-white cursor-pointer', className)}
      onClick={onClick}
      whileHover={{ y: -2 }}
      transition={{ duration: 0.18, ease: 'easeOut' }}
    >
      {children}
    </motion.div>
  )
}

function hexToRgbStr(hex: string): string {
  const r = parseInt(hex.slice(1,3), 16)
  const g = parseInt(hex.slice(3,5), 16)
  const b = parseInt(hex.slice(5,7), 16)
  return `${r},${g},${b}`
}

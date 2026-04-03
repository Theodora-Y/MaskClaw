/**
 * HaloBackground — 渐变光晕背景
 *
 * 关键技术：mix-blend-mode: multiply + filter: blur(80-110px)
 * 在白色/暖白背景上，multiply 混合让彩色光晕自然融入，形成深度感。
 * opacity 0.22-0.28 配合 multiply 视觉效果约等于 0.10-0.15。
 */
import { motion } from 'framer-motion'

interface HaloBackgroundProps {
  gradFrom?: string
  gradTo?: string
  pulseKey?: number       // 变化时触发脉冲动画
  intensity?: 'full' | 'subtle'  // full=引导页, subtle=主页
}

export function HaloBackground({
  gradFrom = '#FF416C',
  gradTo = '#6A82FB',
  pulseKey = 0,
  intensity = 'full',
}: HaloBackgroundProps) {
  const baseOpacity = intensity === 'subtle' ? 0.13 : 0.26
  const secondOpacity = intensity === 'subtle' ? 0.10 : 0.20
  const thirdOpacity = intensity === 'subtle' ? 0.07 : 0.13

  return (
    <div
      className="fixed inset-0 overflow-hidden pointer-events-none"
      style={{ zIndex: 0 }}
      aria-hidden
    >
      {/* 主光晕：grad-from 色，右上角 */}
      <motion.div
        key={`orb1-${pulseKey}`}
        animate={{
          rotate: [0, 360],
          scale: pulseKey > 0 ? [1, 1.06, 1] : [1, 1.03, 1],
        }}
        transition={{
          rotate: { duration: 28, repeat: Infinity, ease: 'linear' },
          scale: pulseKey > 0
            ? { duration: 0.4, ease: 'easeOut' }
            : { duration: 9, repeat: Infinity, ease: 'easeInOut' },
        }}
        style={{
          position: 'absolute',
          width: 700,
          height: 520,
          top: '-15%',
          right: '-10%',
          borderRadius: '62% 38% 46% 54% / 60% 44% 56% 40%',
          background: gradFrom,
          filter: 'blur(110px)',
          opacity: baseOpacity,
          mixBlendMode: 'multiply' as const,
        }}
      />

      {/* 副光晕：grad-to 色，左下角 */}
      <motion.div
        key={`orb2-${pulseKey}`}
        animate={{
          rotate: [0, -360],
          scale: pulseKey > 0 ? [1, 1.05, 1] : [1, 1.04, 1],
        }}
        transition={{
          rotate: { duration: 38, repeat: Infinity, ease: 'linear' },
          scale: pulseKey > 0
            ? { duration: 0.35, ease: 'easeOut', delay: 0.08 }
            : { duration: 12, repeat: Infinity, ease: 'easeInOut', delay: 4 },
        }}
        style={{
          position: 'absolute',
          width: 560,
          height: 420,
          bottom: '-8%',
          left: '-8%',
          borderRadius: '45% 55% 60% 40% / 50% 42% 58% 50%',
          background: gradTo,
          filter: 'blur(90px)',
          opacity: secondOpacity,
          mixBlendMode: 'multiply' as const,
        }}
      />

      {/* 漂移光晕：渐变混合，中部轻微飘动 */}
      <motion.div
        animate={{
          x: [-30, 30, -30],
          y: [-20, 20, -20],
          scale: pulseKey > 0 ? [1, 1.04, 1] : 1,
        }}
        transition={{
          x: { duration: 22, repeat: Infinity, ease: 'easeInOut' },
          y: { duration: 17, repeat: Infinity, ease: 'easeInOut', delay: 5 },
          scale: pulseKey > 0
            ? { duration: 0.3, ease: 'easeOut', delay: 0.05 }
            : undefined,
        }}
        style={{
          position: 'absolute',
          width: 400,
          height: 300,
          top: '35%',
          left: '55%',
          transform: 'translate(-50%,-50%)',
          borderRadius: '55% 45% 52% 48% / 48% 55% 45% 52%',
          background: `linear-gradient(135deg, ${gradFrom}, ${gradTo})`,
          filter: 'blur(80px)',
          opacity: thirdOpacity,
          mixBlendMode: 'multiply' as const,
        }}
      />
    </div>
  )
}

// 兼容旧引用
export default HaloBackground
export { HaloBackground as OrbBackground }

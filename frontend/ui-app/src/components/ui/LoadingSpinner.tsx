import { Loader2 } from 'lucide-react'

interface LoadingSpinnerProps {
  size?: number
  color?: string
  label?: string
}

/**
 * 统一加载动画：使用与 DemoChatPage 一致的 Lucide Loader2 + animate-spin 样式。
 */
export function LoadingSpinner({ size = 18, color = '#888888', label }: LoadingSpinnerProps) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, padding: '24px 0' }}>
      <Loader2 size={size} className="animate-spin" style={{ color }} />
      {label && (
        <span style={{ fontFamily: "'Sora', sans-serif", fontSize: 13, color }}>
          {label}
        </span>
      )}
    </div>
  )
}

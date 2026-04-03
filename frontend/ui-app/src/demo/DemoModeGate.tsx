/**
 * DemoModeGate — 演示模式顶部Banner遮罩
 * 当 isDemoMode=true 时显示，不影响正常页面渲染
 */
import { useState } from 'react'
import useDemoStore from '@/store/demoStore'
import { DEMO_USERS } from './demoConfig'

export default function DemoModeGate() {
  const { isDemoMode, demoUser } = useDemoStore()
  const [expanded, setExpanded] = useState(false)

  if (!isDemoMode) return null

  const config = DEMO_USERS[demoUser]
  const gradColor = config?.gradient?.from ?? '#7028E4'

  return (
    <>
      {/* 顶部Banner */}
      <div
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          zIndex: 9999,
          background: `linear-gradient(135deg, rgba(15,12,28,0.92), rgba(40,20,80,0.92))`,
          backdropFilter: 'blur(8px)',
          WebkitBackdropFilter: 'blur(8px)',
          borderBottom: '1px solid rgba(112,40,228,0.35)',
          padding: '6px 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
        }}
      >
        {/* 左侧：演示标识 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {/* 脉冲指示灯 */}
          <div style={{ position: 'relative', width: 10, height: 10 }}>
            <div style={{
              position: 'absolute',
              inset: 0,
              borderRadius: '50%',
              background: '#00FF88',
              animation: 'pulse 2s ease-in-out infinite',
            }} />
            <style>{`
              @keyframes pulse {
                0%, 100% { opacity: 1; transform: scale(1); }
                50% { opacity: 0.5; transform: scale(0.85); }
              }
            `}</style>
          </div>
          <span style={{
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: 11,
            color: '#00FF88',
            letterSpacing: '0.08em',
            fontWeight: 600,
          }}>
            演示模式
          </span>
          <div style={{ width: 1, height: 12, background: 'rgba(255,255,255,0.15)' }} />
          <span style={{
            fontFamily: "'Sora', sans-serif",
            fontSize: 12,
            color: 'rgba(255,255,255,0.7)',
          }}>
            {config?.label ?? demoUser}
          </span>
        </div>

        {/* 右侧：说明 + 退出 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button
            onClick={() => setExpanded(e => !e)}
            style={{
              background: 'none',
              border: '1px solid rgba(255,255,255,0.2)',
              borderRadius: 4,
              padding: '2px 10px',
              color: 'rgba(255,255,255,0.6)',
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: 10,
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            {expanded ? '收起 ▲' : '说明 ▾'}
          </button>
          <a
            href="/app/settings"
            style={{
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: 10,
              color: 'rgba(255,255,255,0.4)',
              textDecoration: 'none',
              transition: 'color 0.15s',
            }}
            onMouseEnter={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.8)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.4)')}
          >
            退出演示 ↗
          </a>
        </div>
      </div>

      {/* 展开说明面板 */}
      {expanded && (
        <div style={{
          position: 'fixed',
          top: 38,
          left: 0,
          right: 0,
          zIndex: 9998,
          background: 'rgba(15,12,28,0.96)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
          borderBottom: '1px solid rgba(112,40,228,0.2)',
          padding: '16px 24px',
          display: 'flex',
          gap: 40,
          flexWrap: 'wrap',
        }}>
          <div>
            <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 9, color: '#7028E4', marginBottom: 4, letterSpacing: '0.1em' }}>当前用户</div>
            <div style={{ fontFamily: "'Sora', sans-serif", fontSize: 13, color: 'white' }}>{config?.label}</div>
            <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 10, color: 'rgba(255,255,255,0.5)', marginTop: 2 }}>{config?.occupation}</div>
          </div>
          <div>
            <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 9, color: '#7028E4', marginBottom: 4, letterSpacing: '0.1em' }}>场景描述</div>
            <div style={{ fontFamily: "'Sora', sans-serif", fontSize: 13, color: 'rgba(255,255,255,0.8)', maxWidth: 400, lineHeight: 1.5 }}>{config?.scenario}</div>
          </div>
          <div>
            <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 9, color: '#7028E4', marginBottom: 4, letterSpacing: '0.1em' }}>隐私规则</div>
            <div style={{ fontFamily: "'Sora', sans-serif", fontSize: 13, color: 'rgba(255,255,255,0.8)', maxWidth: 400, lineHeight: 1.5 }}>
              {config?.description}
            </div>
          </div>
        </div>
      )}
    </>
  )
}

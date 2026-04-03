/**
 * Navbar — 顶部导航栏（更新版）
 * - 用户名·职业·头像包成单一可点击块
 * - 左侧 Chat 按钮（宝蓝色，更突出）
 * - 「日志」按钮改为切换 LogPanel
 * - 「设置」保持路由跳转
 */
import { useNavigate, useLocation } from 'react-router-dom'
import useAuthStore from '@/store/authStore'
import { getAvatarUrl } from '@/lib/avatarList'
import logoImg from '@/assets/logo.png'

interface NavbarProps {
  onLogToggle?: () => void
  onProfileClick?: () => void
  /** @deprecated 兼容旧页面 */
  onLogClick?: () => void
  /** @deprecated 兼容旧页面 */
  onSettingsClick?: () => void
}

export function Navbar({ onLogToggle, onProfileClick, onLogClick, onSettingsClick }: NavbarProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const { username, occupation, gradFrom, gradTo, avatarIndex } = useAuthStore()

  const avatarUrl = getAvatarUrl(avatarIndex)
  const isOnChat = location.pathname === '/app/chat' || location.pathname === '/app/demo'

  return (
    <header
      className="fixed top-0 left-0 right-0 z-30 bg-white"
      style={{ height: 56, borderBottom: '1px solid #E8E6E0' }}
    >
      <div className="flex items-center justify-between h-full px-6">

        {/* 左侧：Logo + 品牌名 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <img
            src={logoImg}
            alt="MaskClaw Logo"
            style={{ height: 24, width: 'auto' }}
          />
          <span
            style={{
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: 13,
              color: '#0A0A0A',
              letterSpacing: '0.15em',
              fontWeight: 500,
              userSelect: 'none',
            }}
          >
            maskclaw
          </span>
        </div>

        {/* 右侧：操作区 */}
        <div className="flex items-center gap-4">

          {/* Chat / 返回主页 按钮（突出，宝蓝色） */}
          <button
            onClick={() => navigate(isOnChat ? '/app' : '/app/chat')}
            style={{
              fontFamily: "'Sora', sans-serif",
              fontSize: 14,
              fontWeight: 600,
              color: '#1677FF',
              background: 'rgba(22,119,255,0.08)',
              border: '1px solid rgba(22,119,255,0.25)',
              borderRadius: 6,
              padding: '4px 12px',
              cursor: 'pointer',
              transition: 'all 0.15s',
              letterSpacing: '0.01em',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = 'rgba(22,119,255,0.14)' }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'rgba(22,119,255,0.08)' }}
          >
            {isOnChat ? '← 主页' : 'Chat'}
          </button>

          {/* 日志（切换 LogPanel） */}
          <button
            onClick={onLogToggle ?? onLogClick ?? (() => navigate('/app/log'))}
            style={{
              fontFamily: "'Sora', sans-serif",
              fontSize: 14,
              color: '#888888',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: 0,
              transition: 'color 0.15s',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color = '#0A0A0A' }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color = '#888888' }}
          >
            日志
          </button>

          {/* 设置 */}
          <button
            onClick={onSettingsClick ?? (() => navigate('/app/settings'))}
            style={{
              fontFamily: "'Sora', sans-serif",
              fontSize: 14,
              color: '#888888',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: 0,
              transition: 'color 0.15s',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color = '#0A0A0A' }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color = '#888888' }}
          >
            设置
          </button>

          {/* 分隔线 */}
          <span style={{ color: '#E0DFDB', fontSize: 14 }}>|</span>

          {/* 用户信息块（整体点击进个人信息页） */}
          <button
            onClick={onProfileClick ?? (() => navigate('/app/profile'))}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '4px 6px',
              borderRadius: 6,
              transition: 'background 0.15s',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = '#F0EEE9' }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}
            title="个人信息"
          >
            {/* 用户名 */}
            <span
              style={{
                fontFamily: "'IBM Plex Mono', monospace",
                fontSize: 13,
                color: '#0A0A0A',
              }}
            >
              {username ?? '用户'}
            </span>
            {/* 职业（纯色，避免渐变文字 bug） */}
            {occupation && (
              <>
                <span style={{ color: '#CCCCCC', fontSize: 13 }}>·</span>
                <span
                  style={{
                    fontFamily: "'Sora', sans-serif",
                    fontSize: 12,
                    color: gradFrom,
                  }}
                >
                  {occupation}
                </span>
              </>
            )}
            {/* 头像 */}
            <div
              style={{
                width: 30,
                height: 30,
                borderRadius: '50%',
                background: `linear-gradient(white, white) padding-box, linear-gradient(135deg, ${gradFrom}, ${gradTo}) border-box`,
                border: '2px solid transparent',
                overflow: 'hidden',
                flexShrink: 0,
              }}
            >
              {avatarUrl ? (
                <img
                  src={avatarUrl}
                  alt="avatar"
                  style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                />
              ) : (
                <div
                  style={{
                    width: '100%',
                    height: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: `linear-gradient(135deg, ${gradFrom}, ${gradTo})`,
                    color: 'white',
                    fontSize: 11,
                    fontWeight: 700,
                    fontFamily: "'IBM Plex Mono', monospace",
                  }}
                >
                  {(username ?? 'U')[0].toUpperCase()}
                </div>
              )}
            </div>
          </button>
        </div>
      </div>
    </header>
  )
}

export default Navbar

/**
 * SettingsPage — 设置页 (/app/settings)
 * 两栏布局：左侧导航 + 右侧内容区。
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import useAuthStore from '@/store/authStore'
import useDemoStore from '@/store/demoStore'
import { Navbar } from '@/components/layout/Navbar'
import { HaloBackground } from '@/components/ui/OrbBackground'
import { MOCK_SKILLS } from '@/lib/mockData'
import { gradientCSS, GRADIENT_PRESETS } from '@/lib/colorMap'

type Section = 'account' | 'data' | 'notification' | 'demo' | 'about'

const SECTIONS: { key: Section; label: string }[] = [
  { key: 'account',      label: '账号与安全' },
  { key: 'data',         label: '数据管理' },
  { key: 'notification', label: '通知设置' },
  { key: 'demo',         label: '演示模式' },
  { key: 'about',        label: '关于' },
]

const DEMO_USERS = [
  { key: 'UserA' as const, label: 'UserA — 医疗场景' },
  { key: 'UserB' as const, label: 'UserB — 电商场景' },
  { key: 'UserC' as const, label: 'UserC — 法律场景' },
]

export default function SettingsPage() {
  const navigate = useNavigate()
  const { gradFrom, gradTo, logout } = useAuthStore()

  const [activeSection, setActiveSection] = useState<Section>('account')
  const [notifyEnabled, setNotifyEnabled] = useState<boolean>(() => {
    return localStorage.getItem('maskclaw-notify') !== 'false'
  })
  const { demoUser: storedDemoUser, setDemoUser: _setDemoUser } = useDemoStore()
  const [demoEnabled, setDemoEnabled] = useState(false)
  const [demoUser, setDemoUser] = useState<'UserA'|'UserB'|'UserC'>(storedDemoUser)
  const [toast, setToast] = useState<string | null>(null)

  // Sync demoUser selection to demoStore
  useEffect(() => { _setDemoUser(demoUser) }, [demoUser])

  useEffect(() => {
    localStorage.setItem('maskclaw-notify', notifyEnabled ? 'true' : 'false')
  }, [notifyEnabled])

  function showToast(msg: string) {
    setToast(msg)
    setTimeout(() => setToast(null), 2000)
  }

  function handleLogout() {
    if (window.confirm('确认退出登录？')) {
      logout()
      navigate('/login')
    }
  }

  function handleExportRules() {
    const json = JSON.stringify(MOCK_SKILLS, null, 2)
    const blob = new Blob([json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'maskclaw-rules.json'
    a.click()
    URL.revokeObjectURL(url)
  }

  function handleClearSkills() {
    showToast('功能开发中')
  }

  return (
    <div className="min-h-screen relative" style={{ background: '#F8F6F2', paddingTop: 56 }}>
      <HaloBackground gradFrom={gradFrom} gradTo={gradTo} intensity="subtle" />

      <Navbar
        onLogClick={() => navigate('/app/log')}
        onSettingsClick={() => navigate('/app/settings')}
        onProfileClick={() => navigate('/app/profile')}
      />

      {/* Toast */}
      {toast && (
        <div
          style={{
            position: 'fixed',
            top: 72,
            right: 24,
            background: '#0A0A0A',
            color: 'white',
            padding: '8px 16px',
            borderRadius: 6,
            fontFamily: "'Sora', sans-serif",
            fontSize: 13,
            zIndex: 50,
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
          }}
        >
          {toast}
        </div>
      )}

      <div
        className="relative z-10 flex"
        style={{ maxWidth: 900, margin: '0 auto', padding: '24px 24px 48px' }}
      >
        {/* 左侧导航 */}
        <aside
          style={{
            width: 200,
            flexShrink: 0,
            background: 'white',
            borderRight: '1px solid #E0DFDB',
            borderRadius: '8px 0 0 8px',
            paddingTop: 8,
            paddingBottom: 8,
            alignSelf: 'flex-start',
            position: 'sticky',
            top: 72,
          }}
        >
          {SECTIONS.map(s => {
            const isActive = activeSection === s.key
            return (
              <button
                key={s.key}
                onClick={() => setActiveSection(s.key)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  width: '100%',
                  height: 40,
                  paddingLeft: isActive ? 13 : 16,
                  paddingRight: 16,
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  fontFamily: "'Sora', sans-serif",
                  fontSize: 14,
                  fontWeight: isActive ? 500 : 400,
                  color: isActive ? '#0A0A0A' : '#888888',
                  textAlign: 'left',
                  borderLeft: isActive
                    ? `3px solid ${gradFrom}`
                    : '3px solid transparent',
                  transition: 'all 0.15s',
                }}
              >
                {s.label}
              </button>
            )
          })}
        </aside>

        {/* 右侧内容 */}
        <div
          style={{
            flex: 1,
            paddingLeft: 24,
            display: 'flex',
            flexDirection: 'column',
            gap: 16,
          }}
        >
          {activeSection === 'account' && (
            <AccountSection
              gradFrom={gradFrom}
              gradTo={gradTo}
              onLogout={handleLogout}
            />
          )}
          {activeSection === 'data' && (
            <DataSection
              gradFrom={gradFrom}
              gradTo={gradTo}
              onExport={handleExportRules}
              onClear={handleClearSkills}
            />
          )}
          {activeSection === 'notification' && (
            <NotificationSection
              gradFrom={gradFrom}
              gradTo={gradTo}
              enabled={notifyEnabled}
              onToggle={() => setNotifyEnabled(v => !v)}
            />
          )}
          {activeSection === 'demo' && (
            <DemoSection
              gradFrom={gradFrom}
              gradTo={gradTo}
              enabled={demoEnabled}
              onToggle={() => setDemoEnabled(v => !v)}
              selectedUser={demoUser}
              onSelectUser={setDemoUser}
              onEnterDemo={() => {
                const { setDemoMode } = useDemoStore.getState()
                setDemoMode(true)
                navigate('/app/demo')
              }}
            />
          )}
          {activeSection === 'about' && (
            <AboutSection />
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Section 子组件 ─────────────────────────────────────────────

function SectionCard({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div
      style={{
        background: 'white',
        border: '1px solid #E0DFDB',
        borderRadius: 8,
        padding: 24,
        ...style,
      }}
    >
      {children}
    </div>
  )
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2
      style={{
        fontFamily: "'Sora', sans-serif",
        fontSize: 15,
        fontWeight: 600,
        color: '#0A0A0A',
        margin: '0 0 20px',
      }}
    >
      {children}
    </h2>
  )
}

function Toggle({ enabled, onToggle, gradFrom, gradTo }: {
  enabled: boolean
  onToggle: () => void
  gradFrom: string
  gradTo: string
}) {
  return (
    <button
      onClick={onToggle}
      style={{
        width: 40,
        height: 22,
        borderRadius: 11,
        border: 'none',
        cursor: 'pointer',
        background: enabled
          ? `linear-gradient(135deg, ${gradFrom}, ${gradTo})`
          : '#C4C3BF',
        position: 'relative',
        transition: 'background 0.2s',
        flexShrink: 0,
      }}
    >
      <span
        style={{
          position: 'absolute',
          top: 3,
          left: enabled ? 21 : 3,
          width: 16,
          height: 16,
          borderRadius: '50%',
          background: 'white',
          transition: 'left 0.2s',
          boxShadow: '0 1px 3px rgba(0,0,0,0.15)',
        }}
      />
    </button>
  )
}

function AccountSection({ gradFrom, gradTo, onLogout }: {
  gradFrom: string
  gradTo: string
  onLogout: () => void
}) {
  return (
    <SectionCard>
      <SectionTitle>账号与安全</SectionTitle>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* 修改密码 */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span
            style={{ fontFamily: "'Sora', sans-serif", fontSize: 14, color: '#888888' }}
          >
            修改密码
          </span>
          <span
            style={{
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: 11,
              color: '#888888',
              background: '#F0EEE9',
              padding: '3px 8px',
              borderRadius: 4,
            }}
          >
            功能开发中
          </span>
        </div>

        <div style={{ height: 1, background: '#F0EEE9' }} />

        {/* 退出登录 */}
        <div>
          <button
            onClick={onLogout}
            style={{
              fontFamily: "'Sora', sans-serif",
              fontSize: 14,
              color: '#FF416C',
              background: 'rgba(255,65,108,0.07)',
              border: '1px solid rgba(255,65,108,0.22)',
              borderRadius: 6,
              padding: '8px 20px',
              cursor: 'pointer',
              transition: 'background 0.15s',
            }}
          >
            退出登录
          </button>
        </div>
      </div>
    </SectionCard>
  )
}

function DataSection({ gradFrom, gradTo, onExport, onClear }: {
  gradFrom: string
  gradTo: string
  onExport: () => void
  onClear: () => void
}) {
  return (
    <SectionCard>
      <SectionTitle>数据管理</SectionTitle>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <p
          style={{
            fontFamily: "'Sora', sans-serif",
            fontSize: 13,
            color: '#888888',
            margin: 0,
            lineHeight: 1.6,
          }}
        >
          你的 Skill 数据存储在服务器端，经过端侧加密保护。导出或清空操作均为本地操作，不会影响服务端存储。
        </p>

        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          {/* 导出规则库 */}
          <button
            onClick={onExport}
            style={{
              fontFamily: "'Sora', sans-serif",
              fontSize: 13,
              color: '#0A0A0A',
              background: 'transparent',
              border: '1px solid #E0DFDB',
              borderRadius: 6,
              padding: '8px 20px',
              cursor: 'pointer',
              transition: 'border-color 0.15s',
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLElement).style.borderColor = gradFrom
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLElement).style.borderColor = '#E0DFDB'
            }}
          >
            导出规则库
          </button>

          {/* 清空所有 Skill */}
          <button
            onClick={onClear}
            style={{
              fontFamily: "'Sora', sans-serif",
              fontSize: 13,
              color: '#FF416C',
              background: 'rgba(255,65,108,0.07)',
              border: '1px solid rgba(255,65,108,0.22)',
              borderRadius: 6,
              padding: '8px 20px',
              cursor: 'pointer',
            }}
          >
            清空所有 Skill
          </button>
        </div>
      </div>
    </SectionCard>
  )
}

function NotificationSection({ gradFrom, gradTo, enabled, onToggle }: {
  gradFrom: string
  gradTo: string
  enabled: boolean
  onToggle: () => void
}) {
  return (
    <SectionCard>
      <SectionTitle>通知设置</SectionTitle>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 16,
        }}
      >
        <div>
          <p
            style={{
              fontFamily: "'Sora', sans-serif",
              fontSize: 14,
              color: '#0A0A0A',
              margin: '0 0 4px',
            }}
          >
            登录时自动弹出待确认变更
          </p>
          <p
            style={{
              fontFamily: "'Sora', sans-serif",
              fontSize: 12,
              color: '#888888',
              margin: 0,
            }}
          >
            每次登录后，若有新的进化结果将自动弹出确认弹层
          </p>
        </div>
        <Toggle
          enabled={enabled}
          onToggle={onToggle}
          gradFrom={gradFrom}
          gradTo={gradTo}
        />
      </div>
    </SectionCard>
  )
}

function DemoSection({ gradFrom, gradTo, enabled, onToggle, selectedUser, onSelectUser, onEnterDemo }: {
  gradFrom: string
  gradTo: string
  enabled: boolean
  onToggle: () => void
  selectedUser: string
  onSelectUser: (u: 'UserA'|'UserB'|'UserC') => void
  onEnterDemo: () => void
}) {
  return (
    <SectionCard
      style={{
        paddingTop: 0,
        overflow: 'hidden',
      }}
    >
      {/* 顶部渐变线（演示模式激活时显示） */}
      {enabled && (
        <div
          style={{
            height: 3,
            background: `linear-gradient(90deg, #7028E4, #E5B2CA)`,
            marginBottom: 24,
            marginLeft: -24,
            marginRight: -24,
          }}
        />
      )}
      <div style={{ padding: enabled ? '0' : '24px 0 0', marginTop: enabled ? 0 : -24 }}>
        <div style={{ paddingTop: enabled ? 0 : 0 }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: 20,
              paddingTop: enabled ? 0 : 24,
            }}
          >
            <h2
              style={{
                fontFamily: "'Sora', sans-serif",
                fontSize: 15,
                fontWeight: 600,
                color: '#0A0A0A',
                margin: 0,
              }}
            >
              演示模式
            </h2>
            <Toggle
              enabled={enabled}
              onToggle={onToggle}
              gradFrom={gradFrom}
              gradTo={gradTo}
            />
          </div>

          {enabled && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <p
                style={{
                  fontFamily: "'Sora', sans-serif",
                  fontSize: 13,
                  color: '#888888',
                  margin: '0 0 8px',
                }}
              >
                选择演示场景用户：
              </p>
              {DEMO_USERS.map(u => {
                const isSelected = selectedUser === u.key
                return (
                  <label
                    key={u.key}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                      cursor: 'pointer',
                      padding: '8px 12px',
                      borderRadius: 6,
                      background: isSelected ? `linear-gradient(135deg, rgba(112,40,228,0.05), rgba(229,178,202,0.05))` : 'transparent',
                      border: isSelected ? '1px solid rgba(112,40,228,0.15)' : '1px solid transparent',
                      transition: 'all 0.15s',
                    }}
                  >
                    {/* Radio 圆点 */}
                    <span
                      style={{
                        width: 16,
                        height: 16,
                        borderRadius: '50%',
                        border: `2px solid ${isSelected ? gradFrom : '#C4C3BF'}`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                      }}
                    >
                      {isSelected && (
                        <span
                          style={{
                            width: 8,
                            height: 8,
                            borderRadius: '50%',
                            background: `linear-gradient(135deg, ${gradFrom}, ${gradTo})`,
                          }}
                        />
                      )}
                    </span>
                    <input
                      type="radio"
                      name="demo-user"
                      value={u.key}
                      checked={isSelected}
                      onChange={() => onSelectUser(u.key)}
                      style={{ display: 'none' }}
                    />
                    <span
                      style={{
                        fontFamily: "'Sora', sans-serif",
                        fontSize: 14,
                        color: isSelected ? '#0A0A0A' : '#888888',
                      }}
                    >
                      {u.label}
                    </span>
                  </label>
                )
              })}
              {/* 进入演示按钮 */}
              <button
                onClick={onEnterDemo}
                style={{
                  marginTop: 8,
                  width: '100%',
                  padding: '10px 0',
                  borderRadius: 8,
                  border: 'none',
                  background: `linear-gradient(135deg, ${gradFrom}, ${gradTo})`,
                  color: 'white',
                  fontFamily: "'Sora', sans-serif",
                  fontSize: 14,
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                  transition: 'opacity 0.15s',
                }}
                onMouseEnter={e => (e.currentTarget.style.opacity = '0.85')}
                onMouseLeave={e => (e.currentTarget.style.opacity = '1')}
              >
                进入演示
              </button>
            </div>
          )}
        </div>
      </div>
    </SectionCard>
  )
}

function AboutSection() {
  return (
    <SectionCard>
      <SectionTitle>关于</SectionTitle>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <span
          style={{
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: 12,
            color: '#888888',
          }}
        >
          v0.1.0
        </span>
        <p
          style={{
            fontFamily: "'Sora', sans-serif",
            fontSize: 14,
            color: '#0A0A0A',
            margin: 0,
            lineHeight: 1.7,
          }}
        >
          MaskClaw — 学习你的隐私习惯，端侧自进化保护
        </p>
        <p
          style={{
            fontFamily: "'Sora', sans-serif",
            fontSize: 13,
            color: '#888888',
            margin: 0,
            lineHeight: 1.7,
          }}
        >
          通过观察你的行为模式，MaskClaw 自动学习并演化隐私保护规则，在不影响使用体验的前提下，为你的敏感数据建立主动防护屏障。
        </p>
      </div>
    </SectionCard>
  )
}

/**
 * ProfilePage — 个人信息配置页 (/app/profile)
 * 单列 640px 居中，支持头像选择、渐变色选择、资料编辑。
 */
import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import useAuthStore from '@/store/authStore'
import { Navbar } from '@/components/layout/Navbar'
import { HaloBackground } from '@/components/ui/OrbBackground'
import { AVATAR_LIST, getAvatarUrl } from '@/lib/avatarList'
import { GRADIENT_PRESETS } from '@/lib/colorMap'
import type { GradientPair } from '@/lib/colorMap'
import { getTagColor, getTagBg } from '@/lib/tagColorMap'
import { api } from '@/lib/api'

const GRADIENT_OPTIONS: GradientPair[] = Object.values(GRADIENT_PRESETS)

export default function ProfilePage() {
  const navigate = useNavigate()
  const {
    user_id, token, username, occupation, apps, sensitive_fields,
    gradFrom, gradTo, avatarIndex,
    setGradient, setAvatarIndex, setProfile,
  } = useAuthStore()

  // 本地编辑状态
  const [localUsername, setLocalUsername] = useState(username ?? '')
  const [localOccupation, setLocalOccupation] = useState(occupation ?? '')
  const [localApps, setLocalApps] = useState<string[]>(apps ?? [])
  const [localFields, setLocalFields] = useState<string[]>(sensitive_fields ?? [])
  const [localAvatar, setLocalAvatar] = useState(avatarIndex)

  // UI 状态
  const [avatarDrawerOpen, setAvatarDrawerOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  // 添加标签的输入状态
  const [addingApp, setAddingApp] = useState(false)
  const [newApp, setNewApp] = useState('')
  const [addingField, setAddingField] = useState(false)
  const [newField, setNewField] = useState('')

  const appInputRef = useRef<HTMLInputElement>(null)
  const fieldInputRef = useRef<HTMLInputElement>(null)

  // 获取 profile 数据
  useEffect(() => {
    if (!user_id) return
    setLoading(true)
    fetch(`/user/profile/${user_id}`, {
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data) {
          if (data.username) setLocalUsername(data.username)
          if (data.occupation) setLocalOccupation(data.occupation)
          if (data.apps) setLocalApps(data.apps)
          if (data.sensitive_fields) setLocalFields(data.sensitive_fields)
          // 同步后端存储的头像/渐变色到 store
          if (typeof data.avatar_index === 'number') {
            setLocalAvatar(data.avatar_index)
            setAvatarIndex(data.avatar_index)
          }
          if (data.grad_from && data.grad_to) {
            setGradient(data.grad_from, data.grad_to)
          }
        }
      })
      .catch(() => {/* use store defaults */})
      .finally(() => setLoading(false))
  }, [user_id])

  useEffect(() => {
    if (addingApp && appInputRef.current) {
      appInputRef.current.focus()
    }
  }, [addingApp])

  useEffect(() => {
    if (addingField && fieldInputRef.current) {
      fieldInputRef.current.focus()
    }
  }, [addingField])

  function showToast(msg: string) {
    setToast(msg)
    setTimeout(() => setToast(null), 2000)
  }

  async function handleSave() {
    if (!user_id) return
    setSaving(true)
    try {
      await api.updateProfile(user_id, {
        username: localUsername,
        occupation: localOccupation,
        apps: localApps,
        sensitive_fields: localFields,
        onboarding_done: true,
        avatar_index: localAvatar,
        grad_from: gradFrom,
        grad_to: gradTo,
      })
      setProfile(localOccupation, localApps, localFields)
      setAvatarIndex(localAvatar)
      showToast('已保存')
      setTimeout(() => navigate('/app'), 600)
    } catch (err) {
      // 解析后端返回的错误信息并展示，不静默跳走
      const msg = err instanceof Error ? err.message : String(err)
      showToast(msg)
      // 仍然可以保存到本地 store 作为 fallback，但不自动跳转
      setProfile(localOccupation, localApps, localFields)
      setAvatarIndex(localAvatar)
    } finally {
      setSaving(false)
    }
  }

  function handleAddApp() {
    const v = newApp.trim()
    if (v && !localApps.includes(v)) {
      setLocalApps(prev => [...prev, v])
    }
    setNewApp('')
    setAddingApp(false)
  }

  function handleAddField() {
    const v = newField.trim()
    if (v && !localFields.includes(v)) {
      setLocalFields(prev => [...prev, v])
    }
    setNewField('')
    setAddingField(false)
  }

  const avatarUrl = getAvatarUrl(localAvatar)

  if (loading) {
    return (
      <div className="min-h-screen" style={{ background: '#F8F6F2', paddingTop: 56 }}>
        <HaloBackground gradFrom={gradFrom} gradTo={gradTo} intensity="subtle" />
        <Navbar
          onLogClick={() => navigate('/app/log')}
          onSettingsClick={() => navigate('/app/settings')}
          onProfileClick={() => navigate('/app/profile')}
        />
        <div className="flex items-center justify-center" style={{ paddingTop: 120 }}>
          <div
            className="animate-pulse"
            style={{
              width: 480,
              height: 320,
              background: '#F0EEE9',
              borderRadius: 8,
            }}
          />
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen relative" style={{ background: '#F8F6F2', paddingTop: 56, paddingBottom: 80 }}>
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

      {/* 头像选择抽屉 */}
      <AnimatePresence>
        {avatarDrawerOpen && (
          <>
            {/* 遮罩 */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              style={{
                position: 'fixed',
                inset: 0,
                background: 'rgba(0,0,0,0.25)',
                zIndex: 40,
              }}
              onClick={() => setAvatarDrawerOpen(false)}
            />
            {/* 抽屉 */}
            <motion.div
              initial={{ x: 320 }}
              animate={{ x: 0 }}
              exit={{ x: 320 }}
              transition={{ type: 'spring', damping: 28, stiffness: 280 }}
              style={{
                position: 'fixed',
                top: 0,
                right: 0,
                bottom: 0,
                width: 320,
                background: 'white',
                zIndex: 41,
                boxShadow: '-4px 0 20px rgba(0,0,0,0.1)',
                overflowY: 'auto',
                padding: 24,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                <h3
                  style={{
                    fontFamily: "'Sora', sans-serif",
                    fontSize: 16,
                    fontWeight: 600,
                    color: '#0A0A0A',
                    margin: 0,
                  }}
                >
                  选择头像
                </h3>
                <button
                  onClick={() => setAvatarDrawerOpen(false)}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    fontSize: 18,
                    color: '#888888',
                    padding: 0,
                    lineHeight: 1,
                  }}
                >
                  ✕
                </button>
              </div>

              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(4, 1fr)',
                  gap: 12,
                }}
              >
                {AVATAR_LIST.map((url, idx) => {
                  const isSelected = localAvatar === idx
                  return (
                    <button
                      key={idx}
                      onClick={() => {
                        setLocalAvatar(idx)
                        setAvatarIndex(idx)
                        setAvatarDrawerOpen(false)
                      }}
                      style={{
                        position: 'relative',
                        width: 56,
                        height: 56,
                        borderRadius: '50%',
                        padding: 0,
                        cursor: 'pointer',
                        border: 'none',
                        background: isSelected
                          ? `linear-gradient(white, white) padding-box, linear-gradient(135deg, ${gradFrom}, ${gradTo}) border-box`
                          : 'transparent',
                        outline: isSelected ? '2px solid transparent' : 'none',
                        overflow: 'hidden',
                      }}
                    >
                      <img
                        src={url}
                        alt={`avatar-${idx}`}
                        style={{
                          width: 48,
                          height: 48,
                          borderRadius: '50%',
                          objectFit: 'cover',
                          display: 'block',
                          margin: '4px auto 0',
                        }}
                      />
                      {isSelected && (
                        <span
                          style={{
                            position: 'absolute',
                            bottom: 0,
                            right: 0,
                            width: 16,
                            height: 16,
                            borderRadius: '50%',
                            background: `linear-gradient(135deg, ${gradFrom}, ${gradTo})`,
                            color: 'white',
                            fontSize: 10,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                          }}
                        >
                          ✓
                        </span>
                      )}
                    </button>
                  )
                })}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      <main
        className="relative z-10"
        style={{ maxWidth: 640, margin: '0 auto', padding: '24px 24px 0' }}
      >
        {/* 返回 */}
        <div style={{ marginBottom: 8 }}>
          <button
            onClick={() => navigate('/app')}
            style={{
              fontFamily: "'Sora', sans-serif",
              fontSize: 13,
              color: '#888888',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: 0,
            }}
          >
            ← 返回主页
          </button>
        </div>

        <h1
          style={{
            fontFamily: "'Sora', sans-serif",
            fontSize: 20,
            fontWeight: 600,
            color: '#0A0A0A',
            marginBottom: 20,
          }}
        >
          个人信息
        </h1>

        {/* Section 1: 基本信息 */}
        <div
          style={{
            background: 'white',
            border: '1px solid #E0DFDB',
            borderRadius: 8,
            padding: 24,
            marginBottom: 16,
          }}
        >
          <h2
            style={{
              fontFamily: "'Sora', sans-serif",
              fontSize: 15,
              fontWeight: 600,
              color: '#0A0A0A',
              margin: '0 0 20px',
            }}
          >
            基本信息
          </h2>

          {/* 头像 + 渐变色选择 */}
          <div className="flex items-start gap-6" style={{ marginBottom: 24 }}>
            {/* 头像 */}
            <div style={{ position: 'relative', flexShrink: 0 }}>
              <button
                onClick={() => setAvatarDrawerOpen(true)}
                style={{
                  width: 56,
                  height: 56,
                  borderRadius: '50%',
                  padding: 2,
                  cursor: 'pointer',
                  background: `linear-gradient(white, white) padding-box, linear-gradient(135deg, ${gradFrom}, ${gradTo}) border-box`,
                  border: '2px solid transparent',
                  overflow: 'hidden',
                }}
              >
                {avatarUrl ? (
                  <img
                    src={avatarUrl}
                    alt="avatar"
                    style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '50%', display: 'block' }}
                  />
                ) : (
                  <span
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      width: '100%',
                      height: '100%',
                      background: `linear-gradient(135deg, ${gradFrom}, ${gradTo})`,
                      color: 'white',
                      fontSize: 18,
                      fontWeight: 600,
                      fontFamily: "'IBM Plex Mono', monospace",
                      borderRadius: '50%',
                    }}
                  >
                    {(localUsername || 'U')[0].toUpperCase()}
                  </span>
                )}
              </button>
              {/* 铅笔图标 */}
              <span
                style={{
                  position: 'absolute',
                  bottom: 0,
                  right: -2,
                  width: 18,
                  height: 18,
                  borderRadius: '50%',
                  background: `linear-gradient(135deg, ${gradFrom}, ${gradTo})`,
                  color: 'white',
                  fontSize: 9,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  boxShadow: '0 1px 4px rgba(0,0,0,0.2)',
                }}
                onClick={() => setAvatarDrawerOpen(true)}
              >
                ✏
              </span>
            </div>

            {/* 渐变色选择 */}
            <div>
              <p
                style={{
                  fontFamily: "'Sora', sans-serif",
                  fontSize: 13,
                  color: '#888888',
                  margin: '0 0 8px',
                }}
              >
                我的颜色
              </p>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {GRADIENT_OPTIONS.map((g, i) => {
                  const isActive = gradFrom === g.from && gradTo === g.to
                  return (
                    <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                      <button
                        onClick={() => setGradient(g.from, g.to)}
                        style={{
                          width: 40,
                          height: 14,
                          borderRadius: 4,
                          border: 'none',
                          cursor: 'pointer',
                          background: `linear-gradient(135deg, ${g.from}, ${g.to})`,
                          padding: 0,
                          transition: 'transform 0.15s',
                          transform: isActive ? 'scale(1.08)' : 'scale(1)',
                        }}
                        title={g.name}
                      />
                      {isActive && (
                        <div
                          style={{
                            width: 40,
                            height: 2,
                            borderRadius: 1,
                            background: `linear-gradient(135deg, ${g.from}, ${g.to})`,
                          }}
                        />
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          </div>

          {/* 用户名 */}
          <div style={{ marginBottom: 16 }}>
            <label
              style={{
                display: 'block',
                fontFamily: "'Sora', sans-serif",
                fontSize: 13,
                color: '#888888',
                marginBottom: 6,
              }}
            >
              用户名
            </label>
            <input
              type="text"
              value={localUsername}
              onChange={e => setLocalUsername(e.target.value)}
              style={{
                width: '100%',
                fontFamily: "'Sora', sans-serif",
                fontSize: 14,
                color: '#0A0A0A',
                background: 'white',
                border: '1px solid #E0DFDB',
                borderRadius: 6,
                padding: '8px 14px',
                outline: 'none',
                boxSizing: 'border-box',
              }}
              onFocus={e => {
                e.target.style.borderColor = gradFrom
                e.target.style.boxShadow = `0 0 0 2px ${gradFrom}20`
              }}
              onBlur={e => {
                e.target.style.borderColor = '#E0DFDB'
                e.target.style.boxShadow = 'none'
              }}
            />
          </div>

          {/* 邮箱（不可修改） */}
          <div style={{ marginBottom: 16 }}>
            <label
              style={{
                display: 'block',
                fontFamily: "'Sora', sans-serif",
                fontSize: 13,
                color: '#888888',
                marginBottom: 6,
              }}
            >
              邮箱
            </label>
            <input
              type="email"
              value="（已绑定）"
              disabled
              style={{
                width: '100%',
                fontFamily: "'Sora', sans-serif",
                fontSize: 14,
                color: '#888888',
                background: '#F0EEE9',
                border: '1px solid #E0DFDB',
                borderRadius: 6,
                padding: '8px 14px',
                outline: 'none',
                boxSizing: 'border-box',
                cursor: 'not-allowed',
              }}
            />
          </div>

          {/* 职业/身份 */}
          <div>
            <label
              style={{
                display: 'block',
                fontFamily: "'Sora', sans-serif",
                fontSize: 13,
                color: '#888888',
                marginBottom: 6,
              }}
            >
              职业 / 身份
            </label>
            <input
              type="text"
              value={localOccupation}
              onChange={e => setLocalOccupation(e.target.value)}
              placeholder="如：医生、程序员、律师…"
              style={{
                width: '100%',
                fontFamily: "'Sora', sans-serif",
                fontSize: 14,
                color: '#0A0A0A',
                background: 'white',
                border: '1px solid #E0DFDB',
                borderRadius: 6,
                padding: '8px 14px',
                outline: 'none',
                boxSizing: 'border-box',
              }}
              onFocus={e => {
                e.target.style.borderColor = gradFrom
                e.target.style.boxShadow = `0 0 0 2px ${gradFrom}20`
              }}
              onBlur={e => {
                e.target.style.borderColor = '#E0DFDB'
                e.target.style.boxShadow = 'none'
              }}
            />
          </div>
        </div>

        {/* Section 2: 常用应用 */}
        <div
          style={{
            background: 'white',
            border: '1px solid #E0DFDB',
            borderRadius: 8,
            padding: 24,
            marginBottom: 16,
          }}
        >
          <h2
            style={{
              fontFamily: "'Sora', sans-serif",
              fontSize: 15,
              fontWeight: 600,
              color: '#0A0A0A',
              margin: '0 0 16px',
            }}
          >
            常用应用
          </h2>

          <div className="flex flex-wrap gap-2">
            {localApps.map((app, i) => (
              <span
                key={i}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '4px 10px',
                  borderRadius: 4,
                  background: getTagBg(app, 0.12),
                  fontFamily: "'Sora', sans-serif",
                  fontSize: 13,
                  color: getTagColor(app),
                }}
              >
                {app}
                <button
                  onClick={() => setLocalApps(prev => prev.filter((_, j) => j !== i))}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: 0,
                    color: '#888888',
                    fontSize: 12,
                    lineHeight: 1,
                    display: 'flex',
                    alignItems: 'center',
                  }}
                >
                  ✕
                </button>
              </span>
            ))}

            {/* 添加 */}
            {addingApp ? (
              <input
                ref={appInputRef}
                type="text"
                value={newApp}
                onChange={e => setNewApp(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter') handleAddApp()
                  if (e.key === 'Escape') { setAddingApp(false); setNewApp('') }
                }}
                onBlur={handleAddApp}
                placeholder="输入应用名…"
                style={{
                  fontFamily: "'Sora', sans-serif",
                  fontSize: 13,
                  width: 120,
                  border: `1px solid ${gradFrom}`,
                  borderRadius: 4,
                  padding: '4px 8px',
                  outline: 'none',
                  color: '#0A0A0A',
                }}
              />
            ) : (
              <button
                onClick={() => setAddingApp(true)}
                style={{
                  fontFamily: "'Sora', sans-serif",
                  fontSize: 13,
                  color: '#888888',
                  background: 'transparent',
                  border: '1px dashed #C4C3BF',
                  borderRadius: 4,
                  padding: '4px 12px',
                  cursor: 'pointer',
                  transition: 'border-color 0.15s, color 0.15s',
                }}
                onMouseEnter={e => {
                  (e.currentTarget as HTMLElement).style.borderColor = gradFrom
                  ;(e.currentTarget as HTMLElement).style.color = gradFrom
                }}
                onMouseLeave={e => {
                  (e.currentTarget as HTMLElement).style.borderColor = '#C4C3BF'
                  ;(e.currentTarget as HTMLElement).style.color = '#888888'
                }}
              >
                + 添加
              </button>
            )}
          </div>
        </div>

        {/* Section 3: 敏感信息偏好 */}
        <div
          style={{
            background: 'white',
            border: '1px solid #E0DFDB',
            borderRadius: 8,
            padding: 24,
            marginBottom: 24,
          }}
        >
          <h2
            style={{
              fontFamily: "'Sora', sans-serif",
              fontSize: 15,
              fontWeight: 600,
              color: '#0A0A0A',
              margin: '0 0 16px',
            }}
          >
            敏感信息偏好
          </h2>

          <div className="flex flex-wrap gap-2">
            {localFields.map((field, i) => (
              <span
                key={i}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '4px 10px',
                  borderRadius: 4,
                  background: getTagBg(field, 0.12),
                  fontFamily: "'Sora', sans-serif",
                  fontSize: 13,
                  color: getTagColor(field),
                }}
              >
                {field}
                <button
                  onClick={() => setLocalFields(prev => prev.filter((_, j) => j !== i))}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: 0,
                    color: '#888888',
                    fontSize: 12,
                    lineHeight: 1,
                    display: 'flex',
                    alignItems: 'center',
                  }}
                >
                  ✕
                </button>
              </span>
            ))}

            {addingField ? (
              <input
                ref={fieldInputRef}
                type="text"
                value={newField}
                onChange={e => setNewField(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter') handleAddField()
                  if (e.key === 'Escape') { setAddingField(false); setNewField('') }
                }}
                onBlur={handleAddField}
                placeholder="如：手机号、地址…"
                style={{
                  fontFamily: "'Sora', sans-serif",
                  fontSize: 13,
                  width: 140,
                  border: `1px solid ${gradFrom}`,
                  borderRadius: 4,
                  padding: '4px 8px',
                  outline: 'none',
                  color: '#0A0A0A',
                }}
              />
            ) : (
              <button
                onClick={() => setAddingField(true)}
                style={{
                  fontFamily: "'Sora', sans-serif",
                  fontSize: 13,
                  color: '#888888',
                  background: 'transparent',
                  border: '1px dashed #C4C3BF',
                  borderRadius: 4,
                  padding: '4px 12px',
                  cursor: 'pointer',
                  transition: 'border-color 0.15s, color 0.15s',
                }}
                onMouseEnter={e => {
                  (e.currentTarget as HTMLElement).style.borderColor = gradFrom
                  ;(e.currentTarget as HTMLElement).style.color = gradFrom
                }}
                onMouseLeave={e => {
                  (e.currentTarget as HTMLElement).style.borderColor = '#C4C3BF'
                  ;(e.currentTarget as HTMLElement).style.color = '#888888'
                }}
              >
                + 添加
              </button>
            )}
          </div>
        </div>

        {/* 保存按钮 */}
        <button
          onClick={handleSave}
          disabled={saving}
          style={{
            width: '100%',
            padding: '12px 0',
            background: saving
              ? '#C4C3BF'
              : `linear-gradient(135deg, ${gradFrom}, ${gradTo})`,
            border: 'none',
            borderRadius: 6,
            color: 'white',
            fontFamily: "'Sora', sans-serif",
            fontSize: 15,
            fontWeight: 600,
            cursor: saving ? 'not-allowed' : 'pointer',
            transition: 'background 0.2s',
          }}
        >
          {saving ? '保存中…' : '保存修改'}
        </button>
      </main>
    </div>
  )
}

// 辅助：hex → rgba（内联版本，避免再导入）
function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1,3), 16)
  const g = parseInt(hex.slice(3,5), 16)
  const b = parseInt(hex.slice(5,7), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

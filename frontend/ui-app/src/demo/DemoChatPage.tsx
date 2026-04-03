/**
 * DemoChatPage — /app/demo
 * 视觉与 ChatPage 一致：三栏、用户气泡、底部输入、标题栏为对话名；纯前端模拟 AutoGLM。
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Plus, Loader2, Play, X, Brain, CheckCircle, Shield, Zap } from 'lucide-react'
import useAuthStore from '@/store/authStore'
import useDemoStore from '@/store/demoStore'
import { Navbar } from '@/components/layout/Navbar'
import { HaloBackground } from '@/components/ui/OrbBackground'
import { LogPanel } from '@/components/log/LogPanel'
import { gradientCSS, type GradientPair } from '@/lib/colorMap'
import { DEMO_USERS } from './demoConfig'

type Phase = 'idle' | 'submitting' | 'thinking' | 'complete' | 'cancelled'

interface ThinkingStep {
  phase: Phase | 'waiting'
  text: string
}

const FOOD_DELIVERY_STEPS: ThinkingStep[] = [
  { phase: 'thinking', text: 'autoGLM 已接收命令，正在解析任务结构...' },
  { phase: 'thinking', text: '正在查找相关 Skill 规则库...' },
  { phase: 'thinking', text: '分析任务：帮我在美团点一份黄焖鸡米饭' },
  { phase: 'thinking', text: 'autoGLM 正在决策：分析用户意图与风险等级...' },
  { phase: 'thinking', text: '检测到涉及个人信息：收货地址、联系电话、支付账户' },
  { phase: 'thinking', text: '对照隐私规则进行检查...' },
  { phase: 'thinking', text: '发现 2 处隐私风险，已自动脱敏处理' },
  { phase: 'thinking', text: '正在打开美团 App，进入下单流程' },
  { phase: 'thinking', text: '订单已提交，正在等待商家接单确认...' },
  { phase: 'complete', text: '✓ 操作完成 — 美团订单 #20260327001 已成功提交' },
]

const STEP_DELAYS = [2500, 3000, 2000, 8000, 5000, 4000, 4000, 3000, 3000, 3000]

function DualRingLoader({ size = 14 }: { size?: number }) {
  return (
    <div className="relative inline-flex" style={{ width: size, height: size }}>
      <span
        className="absolute rounded-full animate-spin-slow"
        style={{
          inset: 0,
          borderRadius: '50%',
          border: `${Math.max(2, size / 5)}px solid rgba(22,119,255,0.2)`,
          borderTopColor: '#1677FF',
        }}
      />
      <style>{`
        @keyframes spinSlow { to { transform: rotate(360deg); } }
        .animate-spin-slow { animation: spinSlow 1.5s linear infinite; }
      `}</style>
    </div>
  )
}

function ThinkingCard({ step, index, total }: { step: ThinkingStep; index: number; total: number }) {
  const isComplete = step.phase === 'complete'
  const isRunning = step.phase === 'thinking' && index === total - 1

  return (
    <motion.div
      initial={{ opacity: 0, y: 16, scale: 0.97 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: 'easeOut' }}
      style={{
        background: isComplete ? 'rgba(0,170,68,0.04)' : 'rgba(22,119,255,0.04)',
        border: `1px solid ${isComplete ? 'rgba(0,170,68,0.2)' : 'rgba(22,119,255,0.15)'}`,
        borderRadius: 14,
        padding: '16px 20px',
        marginBottom: 12,
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div style={{
        position: 'absolute', left: 0, top: 0, bottom: 0, width: 4,
        background: isComplete
          ? 'linear-gradient(180deg, #00AA44, #00CC55)'
          : 'linear-gradient(180deg, #1677FF, #4090FF)',
        borderRadius: '4px 0 0 4px',
      }} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
        <div style={{
          width: 26, height: 26, borderRadius: '50%',
          background: isComplete ? '#00AA44' : '#1677FF',
          display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
        }}>
          {isComplete
            ? <CheckCircle size={14} color="white" />
            : <Brain size={13} color="white" />
          }
        </div>
        <div>
          <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 10, color: '#888888' }}>
            思考 {index + 1} / {total}
          </div>
          <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, color: isComplete ? '#00AA44' : '#1677FF', fontWeight: 600 }}>
            {isComplete ? 'AUTO_COMPLETE' : 'AUTO_THINKING'}
          </div>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 3 }}>
          {[...Array(total)].map((_, i) => (
            <div key={i} style={{
              width: i <= index ? (isComplete ? 20 : 8) : 6, height: 6, borderRadius: 3,
              background: i <= index ? (isComplete ? '#00AA44' : '#1677FF') : '#E8E8E8',
              transition: 'all 0.3s ease',
            }} />
          ))}
        </div>
      </div>

      <div style={{
        fontFamily: "'Sora', sans-serif", fontSize: 14,
        color: isComplete ? '#00AA44' : '#0A0A0A',
        fontWeight: isComplete ? 600 : 400,
        lineHeight: 1.7, paddingLeft: 4,
      }}>
        {isRunning ? (
          <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <DualRingLoader size={14} />
            <span style={{ color: '#888888' }}>{step.text}</span>
          </span>
        ) : step.text}
      </div>
    </motion.div>
  )
}

function PrivacySummary() {
  const decisions = [
    { field: '收货地址', action: 'mask', detail: '已脱敏：显示「北京市朝阳区***」而非完整地址' },
    { field: '联系电话', action: 'mask', detail: '已脱敏：138****8888 替代真实号码' },
    { field: '支付账户', action: 'allow', detail: '已放行：支付信息经加密通道传输' },
  ]
  const cfg = {
    mask:  { color: '#FF9500', bg: 'rgba(255,149,0,0.06)', border: 'rgba(255,149,0,0.2)', label: '已脱敏', Icon: Shield },
    allow: { color: '#00AA44', bg: 'rgba(0,170,68,0.06)',  border: 'rgba(0,170,68,0.2)', label: '已放行', Icon: CheckCircle },
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.3 }}
      style={{
        background: 'white', borderRadius: 12, padding: '16px 20px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
        border: '1px solid #E8E8E8', marginTop: 12,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <Shield size={14} style={{ color: '#1677FF' }} />
        <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, color: '#1677FF', fontWeight: 600, letterSpacing: '0.06em' }}>
          隐私决策摘要
        </span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {decisions.map((d, i) => {
          const c = cfg[d.action as keyof typeof cfg] ?? cfg.allow
          const Icon = c.Icon
          return (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '8px 12px', borderRadius: 8,
              background: c.bg, border: `1px solid ${c.border}`,
            }}>
              <Icon size={14} style={{ color: c.color, flexShrink: 0 }} />
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                  <span style={{ fontFamily: "'Sora', sans-serif", fontSize: 13, fontWeight: 600, color: '#0A0A0A' }}>{d.field}</span>
                  <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 10, color: c.color, fontWeight: 600, padding: '1px 6px', borderRadius: 4, background: `${c.color}15` }}>
                    {c.label}
                  </span>
                </div>
                <div style={{ fontFamily: "'Sora', sans-serif", fontSize: 11, color: '#888888', lineHeight: 1.5 }}>{d.detail}</div>
              </div>
            </div>
          )
        })}
      </div>
    </motion.div>
  )
}

export default function DemoChatPage() {
  const navigate = useNavigate()
  const { gradFrom, gradTo } = useAuthStore()
  const { demoUser, setDemoMode } = useDemoStore()
  const config = DEMO_USERS[demoUser] ?? DEMO_USERS['UserC']
  const grad: GradientPair = config.gradient

  const [input, setInput] = useState('')
  const [logOpen, setLogOpen] = useState(false)
  const [phase, setPhase] = useState<Phase>('idle')
  const [currentStep, setCurrentStep] = useState(-1)
  const [completedSteps, setCompletedSteps] = useState<ThinkingStep[]>([])
  /** 已发送的用户指令（用于气泡与标题） */
  const [userSentText, setUserSentText] = useState<string | null>(null)
  const [convTitle, setConvTitle] = useState('新任务')

  const scrollRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([])

  const isRunning = phase === 'submitting' || phase === 'thinking'

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [completedSteps.length, currentStep, userSentText, phase])

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 150) + 'px'
    }
  }, [input])

  const clearTimers = useCallback(() => {
    timersRef.current.forEach(t => clearTimeout(t))
    timersRef.current = []
  }, [])

  const resetSimulation = useCallback(() => {
    clearTimers()
    setPhase('idle')
    setCurrentStep(-1)
    setCompletedSteps([])
    setUserSentText(null)
    setConvTitle('新任务')
  }, [clearTimers])

  const exitDemo = useCallback(() => {
    clearTimers()
    setDemoMode(false)
    navigate('/app/settings')
  }, [clearTimers, navigate, setDemoMode])

  const executeTask = useCallback(() => {
    const text = input.trim()
    if (!text || isRunning) return

    clearTimers()
    setUserSentText(text)
    const title = text.slice(0, 20) + (text.length > 20 ? '...' : '')
    setConvTitle(title)
    setInput('')
    setCompletedSteps([])
    setCurrentStep(-1)
    setPhase('submitting')

    const t1 = setTimeout(() => {
      setPhase('thinking')
      setCurrentStep(0)

      let accDelay = STEP_DELAYS[0]
      for (let i = 0; i < FOOD_DELIVERY_STEPS.length; i++) {
        const delay = accDelay
        const t = setTimeout(() => {
          setCompletedSteps(prev => [...prev, FOOD_DELIVERY_STEPS[i]])
          setCurrentStep(i + 1)
        }, delay)
        timersRef.current.push(t)
        accDelay += STEP_DELAYS[i + 1] ?? 0
      }

      const totalMs = STEP_DELAYS.reduce((a, b) => a + b, 0) + STEP_DELAYS[0]
      const tDone = setTimeout(() => setPhase('complete'), totalMs)
      timersRef.current.push(tDone)
    }, 2000)
    timersRef.current.push(t1)
  }, [input, isRunning, clearTimers])

  useEffect(() => {
    return () => clearTimers()
  }, [clearTimers])

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      executeTask()
    }
  }

  const headerTitle = userSentText ? convTitle : 'AutoGLM 执行'

  return (
    <div style={{ minHeight: '100vh', background: '#F8F6F2', paddingTop: 56 }} className="relative">
      <HaloBackground gradFrom={gradFrom} gradTo={gradTo} intensity="subtle" />
      <Navbar onLogToggle={() => setLogOpen(o => !o)} />

      {/* 左下角退出演示：仅绿色圆点，无文字 */}
      <button
        type="button"
        title="退出演示"
        aria-label="退出演示"
        onClick={exitDemo}
        style={{
          position: 'fixed',
          left: 16,
          bottom: 16,
          width: 14,
          height: 14,
          borderRadius: '50%',
          background: '#22C55E',
          border: '2px solid rgba(255,255,255,0.9)',
          boxShadow: '0 1px 4px rgba(0,0,0,0.12)',
          cursor: 'pointer',
          zIndex: 50,
          padding: 0,
        }}
      />

      <div style={{ display: 'flex', height: 'calc(100vh - 56px)', overflow: 'hidden' }} className="relative z-10">

        <div style={{
          width: 240, flexShrink: 0,
          background: '#FFFFFF', borderRight: '1px solid #E0DFDB',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}>
          <div style={{ padding: '14px 12px', borderBottom: '1px solid #E0DFDB' }}>
            <button
              disabled
              style={{
                width: '100%',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                padding: '8px 0',
                borderRadius: 6,
                background: gradientCSS(grad),
                color: 'white',
                border: 'none',
                fontFamily: "'Sora', sans-serif",
                fontSize: 13, fontWeight: 600,
                cursor: 'default', opacity: 0.6,
              }}
            >
              <Plus size={14} /> 新建任务
            </button>
          </div>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            <button
              style={{
                width: '100%', textAlign: 'left',
                padding: '10px 12px',
                background: '#F0EEE9',
                border: 'none',
                borderLeft: `3px solid ${gradFrom}`,
                cursor: 'default',
                display: 'flex', alignItems: 'center', gap: 8,
              }}
            >
              <Zap size={13} style={{ color: '#888888', flexShrink: 0 }} />
              <span style={{
                fontFamily: "'Sora', sans-serif", fontSize: 12, color: '#0A0A0A',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {convTitle}
              </span>
            </button>
          </div>
        </div>

        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minHeight: 0, background: '#F8F6F2' }}>

          <div style={{
            padding: '12px 24px',
            borderBottom: '1px solid #E0DFDB',
            background: '#FFFFFF',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            flexShrink: 0,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Zap size={16} style={{ color: gradFrom }} />
              <span style={{ fontFamily: "'Sora', sans-serif", fontSize: 14, fontWeight: 600, color: '#0A0A0A' }}>
                {headerTitle}
              </span>
            </div>

            {phase !== 'idle' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                {phase === 'submitting' && (
                  <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 12, color: gradFrom }}>
                    提交中...
                  </span>
                )}
                {phase === 'thinking' && (
                  <>
                    <Loader2 size={14} className="animate-spin" style={{ color: gradFrom }} />
                    <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 12, color: '#888888' }}>
                      执行中 ({completedSteps.length} 步)
                    </span>
                  </>
                )}
                {phase === 'complete' && (
                  <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 12, color: '#00AA44' }}>
                    ✓ 完成 ({completedSteps.length} 步)
                  </span>
                )}
                {phase === 'cancelled' && (
                  <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 12, color: '#FF9500' }}>
                    已取消
                  </span>
                )}
                {(phase === 'complete' || phase === 'cancelled') && (
                  <button onClick={resetSimulation} style={{
                    padding: '4px 8px', borderRadius: 4, border: '1px solid #E0E0E0',
                    background: '#FFFFFF', fontFamily: "'Sora', sans-serif", fontSize: 11, cursor: 'pointer',
                  }}>
                    重置
                  </button>
                )}
              </div>
            )}
          </div>

          <div ref={scrollRef} style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '24px 32px 16px' }}>

            {phase === 'idle' && !userSentText && (
              <div style={{ textAlign: 'center', paddingTop: 80 }}>
                <div style={{
                  width: 64, height: 64, borderRadius: '50%',
                  background: `${gradFrom}15`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px',
                }}>
                  <Zap size={28} style={{ color: gradFrom }} />
                </div>
                <div style={{ fontFamily: "'Sora', sans-serif", fontSize: 18, fontWeight: 500, color: '#0A0A0A', marginBottom: 8 }}>
                  AutoGLM 任务执行
                </div>
                <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 12, color: '#888888' }}>
                  描述任务，AutoGLM 将自动执行并展示处理过程
                </div>
              </div>
            )}

            {userSentText && (
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
                <div style={{
                  maxWidth: '70%',
                  padding: '10px 14px',
                  borderRadius: '12px 12px 4px 12px',
                  background: gradientCSS(grad),
                  color: '#FFFFFF',
                  fontFamily: "'Sora', sans-serif",
                  fontSize: 13,
                  lineHeight: 1.6,
                  boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}>
                  {userSentText}
                </div>
              </div>
            )}

            {phase === 'submitting' && (
              <div style={{ textAlign: 'center', paddingTop: 40 }}>
                <Loader2 size={32} className="animate-spin" style={{ color: gradFrom, marginBottom: 16 }} />
                <div style={{ fontFamily: "'Sora', sans-serif", fontSize: 14, color: '#888888' }}>
                  正在提交任务...
                </div>
              </div>
            )}

            {(phase === 'thinking' || phase === 'complete') && (
              <>
                {completedSteps.map((step, i) => (
                  <ThinkingCard key={i} step={step} index={i} total={FOOD_DELIVERY_STEPS.length} />
                ))}
                {phase === 'complete' && <PrivacySummary />}
              </>
            )}
          </div>

          <div style={{
            padding: '12px 32px 20px',
            borderTop: '1px solid #E0DFDB',
            background: '#FFFFFF',
            flexShrink: 0,
          }}>
            <div style={{
              display: 'flex', alignItems: 'flex-end', gap: 10,
              background: '#F8F6F2', borderRadius: 8,
              border: '1px solid #E0DFDB', padding: '8px 12px',
            }}>
              <textarea
                ref={textareaRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="描述任务，如：帮我在淘宝填收货地址..."
                rows={1}
                disabled={phase === 'submitting' || phase === 'thinking'}
                style={{
                  flex: 1, resize: 'none', border: 'none', background: 'transparent',
                  fontFamily: "'Sora', sans-serif", fontSize: 13, color: '#0A0A0A',
                  outline: 'none', lineHeight: 1.5, maxHeight: 150,
                }}
              />
              {isRunning && (
                <button
                  onClick={() => { clearTimers(); setPhase('cancelled') }}
                  style={{
                    width: 32, height: 32, borderRadius: 6,
                    border: '1px solid #E0E0E0', background: '#FFFFFF',
                    color: '#FF2D55', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    cursor: 'pointer', flexShrink: 0,
                  }}
                >
                  <X size={14} />
                </button>
              )}
              <button
                onClick={executeTask}
                disabled={!input.trim() || isRunning}
                style={{
                  width: 32, height: 32, borderRadius: 6, border: 'none',
                  background: input.trim() && !isRunning ? gradientCSS(grad) : '#E0E0E0',
                  color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  cursor: input.trim() && !isRunning ? 'pointer' : 'not-allowed',
                  flexShrink: 0, transition: 'background 0.15s',
                }}
              >
                <Play size={14} />
              </button>
            </div>
            <div style={{
              marginTop: 8, fontFamily: "'IBM Plex Mono', monospace",
              fontSize: 10, color: '#AAAAAA', textAlign: 'center',
            }}>
              执行模式：任务将在 AutoGLM 中执行，结果实时展示
            </div>
          </div>
        </div>

        <LogPanel
          isOpen={logOpen}
          onClose={() => setLogOpen(false)}
          gradFrom={gradFrom}
          gradTo={gradTo}
          userId="demo-user"
          token={null}
        />
      </div>
    </div>
  )
}

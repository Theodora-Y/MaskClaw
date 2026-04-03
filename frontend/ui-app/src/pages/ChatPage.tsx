/**
 * ChatPage — AutoGLM 任务执行页面
 * 左侧对话历史列表 (240px) | 主执行区域 | 右侧可召唤日志面板
 * 
 * 用户输入任务 → 调用 Windows 后端 AutoGLM API → 通过 SSE 流实时展示日志
 */
import { useState, useRef, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { Send, Plus, Loader2, Play, X, CheckCircle, Zap } from 'lucide-react'
import useAuthStore from '@/store/authStore'
import { Navbar } from '@/components/layout/Navbar'
import { HaloBackground } from '@/components/ui/OrbBackground'
import { LogPanel } from '@/components/log/LogPanel'
import { gradientCSS, type GradientPair } from '@/lib/colorMap'

// API 配置 - 通过 Vite 代理转发到 Windows 后端
// 前端请求 /autoglm/* → Vite 代理 → 127.0.0.1:28080 (SSH 隧道) → Windows 后端
const API_BASE = '/autoglm'

// ============== 类型定义 ==============

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  ts: number
}

interface Conversation {
  id: string
  title: string
  messages: Message[]
  createdAt: number
}

// 任务日志摘要（SSE 流推送的日志格式 - 待定，先用占位）
interface LogSummary {
  step: number
  action: string          // 当前执行的操作
  app_context: string     // 应用场景，如 "微信"、"淘宝"
  status: 'running' | 'success' | 'error' | 'warning'
  description: string      // 操作描述
  timestamp: number       // 时间戳
  detail?: string         // 详细信息（可选）
  screenshot?: string     // 截图 base64（可选）
  privacy_action?: 'mask' | 'block' | 'allow' | 'ask'
  privacy_message?: string
}

// 任务状态
interface TaskState {
  taskId: string | null
  status: 'idle' | 'submitting' | 'running' | 'completed' | 'failed' | 'cancelled'
  // 执行中的当前日志（上面显示）
  runningLog: LogSummary | null
  // 日志详情列表（下面不断追加）
  logDetails: string[]
  error: string | null
}

// ============== 常量 ==============

const STORAGE_KEY = 'maskclaw-autoglm-history'

// ============== 工具函数 ==============

function loadConversations(): Conversation[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch { return [] }
}

function saveConversations(convs: Conversation[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(convs.slice(0, 20)))
}

function makeId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 6)
}

// ============== API 调用 ==============

// AutoGLM Windows 后端接口
// 提交任务 - POST /autoglm/api/task/run
async function submitTask(taskDescription: string, userId: string): Promise<{ task_id: string; stream_url: string }> {
  const res = await fetch(`${API_BASE}/api/task/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
      task: taskDescription,
      user_id: userId,  // 添加 user_id 用于日志存储
    }),
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`提交任务失败: ${err}`)
  }
  return res.json()
}

// 取消任务
async function cancelTask(taskId: string): Promise<void> {
  await fetch(`${API_BASE}/api/task/cancel/${taskId}`, {
    method: 'POST',
  })
}

// SSE 流 URL
function getSseUrl(streamUrl: string, token: string | null): string {
  return `${API_BASE}${streamUrl}${token ? `?auth=${encodeURIComponent(token)}` : ''}`
}

// ============== 可视化摘要组件 ==============

function LogSummaryCard({ summary, index, gradFrom }: { summary: LogSummary; index: number; gradFrom: string }) {
  const { step, action, app_context, status, description, timestamp, detail, screenshot, privacy_action, privacy_message } = summary

  // 安全默认值
  const safeStatus = status || 'running'
  const safeTimestamp = timestamp ? new Date(timestamp * 1000) : new Date()
  const safeStep = step ?? index + 1

  const statusColor = {
    'running': '#0066FF',   // 蓝色 - 执行中
    'success': '#00AA44',  // 绿色 - 成功
    'error': '#FF2D55',     // 红色 - 错误
    'warning': '#FF9500',  // 橙色 - 警告
  }[safeStatus] || '#888888'

  const privacyActionMap: Record<string, string> = {
    'mask': '#FF9500',   // 橙色 - 已脱敏
    'block': '#FF2D55',  // 红色 - 已阻止
    'allow': '#00AA44',  // 绿色 - 已放行
    'ask': '#0066FF',    // 蓝色 - 待确认
  }
  const privacyColor = privacyActionMap[privacy_action || ''] || '#888888'

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.08, 0.5) }}
      style={{
        background: '#FFFFFF',
        borderRadius: 12,
        padding: 16,
        marginBottom: 12,
        boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
        borderLeft: `4px solid ${statusColor}`,
      }}
    >
      {/* 步骤序号 + 操作描述 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
        <div style={{
          width: 28, height: 28,
          borderRadius: '50%',
          background: safeStatus === 'running' ? '#0066FF' : statusColor,
          color: '#FFFFFF',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 12, fontWeight: 600, fontFamily: "'IBM Plex Mono', monospace",
          flexShrink: 0,
        }}>
          {safeStatus === 'running' ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            safeStep
          )}
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontFamily: "'Sora', sans-serif", fontSize: 14, fontWeight: 500, color: '#0A0A0A' }}>
            {description || action || '执行中'}
          </div>
          <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, color: '#888888' }}>
            {app_context || 'AutoGLM'} · {safeTimestamp.toLocaleTimeString('zh-CN')}
          </div>
        </div>
        <div style={{
          padding: '4px 8px',
          borderRadius: 4,
          background: `${statusColor}15`,
          color: statusColor,
          fontSize: 11,
          fontFamily: "'IBM Plex Mono', monospace",
          fontWeight: 500,
        }}>
          {safeStatus.toUpperCase()}
        </div>
      </div>

      {/* 隐私处理结果 */}
      {privacy_action && privacy_message && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '8px 10px',
          background: `${privacyColor}10`,
          borderRadius: 6,
          marginBottom: 8,
        }}>
          {privacy_action === 'mask' && <CheckCircle size={14} style={{ color: privacyColor }} />}
          {privacy_action === 'block' && <X size={14} style={{ color: privacyColor }} />}
          {privacy_action === 'allow' && <CheckCircle size={14} style={{ color: privacyColor }} />}
          <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, color: privacyColor }}>
            {privacy_action.toUpperCase()}: {privacy_message}
          </span>
        </div>
      )}

      {/* 详细信息 */}
      {detail && (
        <div style={{
          fontFamily: "'Sora', sans-serif",
          fontSize: 12,
          color: '#666666',
          lineHeight: 1.5,
          padding: '8px 10px',
          background: '#F8F6F2',
          borderRadius: 6,
        }}>
          {detail}
        </div>
      )}

      {/* 截图预览 */}
      {screenshot && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 10, color: '#888888', marginBottom: 4 }}>
            截图
          </div>
          <img
            src={`data:image/jpeg;base64,${screenshot}`}
            alt="操作截图"
            style={{ width: '100%', borderRadius: 6, maxHeight: 200, objectFit: 'contain' }}
          />
        </div>
      )}
    </motion.div>
  )
}

// ============== 主组件 ==============

export default function ChatPage() {
  const { user_id, token, gradFrom, gradTo } = useAuthStore()

  const [conversations, setConversations] = useState<Conversation[]>(loadConversations)
  const [activeConvId, setActiveConvId] = useState<string | null>(conversations[0]?.id ?? null)
  const [input, setInput] = useState('')
  const [logOpen, setLogOpen] = useState(false)
  const [task, setTask] = useState<TaskState>({ taskId: null, status: 'idle', error: null, runningLog: null, logDetails: [] })

  const scrollRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const eventSourceRef = useRef<EventSource | null>(null)

  const activeConv = conversations.find(c => c.id === activeConvId)
  const messages = activeConv?.messages ?? []

  // 保存对话
  useEffect(() => { saveConversations(conversations) }, [conversations])

  // 自动滚动到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages.length, task.logDetails.length])

  // 自动调节 textarea 高度
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 150) + 'px'
    }
  }, [input])

  // 清理 SSE 连接
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
    }
  }, [])

  function createConversation() {
    const conv: Conversation = { id: makeId(), title: '新建任务', messages: [], createdAt: Date.now() }
    setConversations(prev => [conv, ...prev])
    setActiveConvId(conv.id)
  }

  // 提交任务到 AutoGLM
  const executeTask = useCallback(async () => {
    if (!input.trim() || task.status === 'running') return

    let convId = activeConvId
    if (!convId) {
      const conv: Conversation = { id: makeId(), title: input.trim().slice(0, 20) + (input.trim().length > 20 ? '...' : ''), messages: [], createdAt: Date.now() }
      setConversations(prev => [conv, ...prev])
      convId = conv.id
      setActiveConvId(conv.id)
    }

    const userMsg: Message = { id: makeId(), role: 'user', content: input.trim(), ts: Date.now() }
    setConversations(prev => prev.map(c =>
      c.id === convId ? { ...c, messages: [...c.messages, userMsg] } : c
    ))

    setInput('')
    setTask(prev => ({ ...prev, status: 'submitting', error: null, runningLog: null, logDetails: [] }))

    try {
      // 1. 提交任务
      const { task_id, stream_url } = await submitTask(input.trim(), user_id || 'unknown')
      setTask(prev => ({ ...prev, taskId: task_id, status: 'running' }))

      // 2. 连接 SSE 流
      const eventSource = new EventSource(getSseUrl(stream_url, token))
      eventSourceRef.current = eventSource

      eventSource.addEventListener('connected', () => {
        console.log('SSE connected')
      })

      // log_summary - Windows 后端发送的日志事件
      eventSource.addEventListener('log_summary', (e) => {
        try {
          const data = JSON.parse(e.data)
          const actionMeta = data.action_metadata || {}
          const outcome = data.outcome || {}
          
          // 提取日志内容
          const description = actionMeta.description || outcome.message || JSON.stringify(data)
          const action = actionMeta.action || 'log'
          const appContext = actionMeta.app_context || 'AutoGLM'
          
          setTask(prev => ({
            ...prev,
            // 上面：更新当前执行状态
            runningLog: {
              step: prev.logDetails.length + 1,
              action: action,
              app_context: appContext,
              status: 'running',
              description: description,
              timestamp: Date.now() / 1000,
              detail: outcome.message || null,
            },
            // 下面：追加日志详情
            logDetails: [...prev.logDetails, description],
          }))
        } catch (err) {
          // 如果解析失败，直接显示原始数据
          const rawData = e.data
          setTask(prev => ({
            ...prev,
            runningLog: {
              step: prev.logDetails.length + 1,
              action: 'log',
              app_context: 'AutoGLM',
              status: 'running',
              description: String(rawData),
              timestamp: Date.now() / 1000,
            },
            logDetails: [...prev.logDetails, String(rawData)],
          }))
        }
      })

      // task_completed - 任务完成
      eventSource.addEventListener('task_completed', (e) => {
        try {
          const data = JSON.parse(e.data)
          setTask(prev => ({ ...prev, status: 'completed' }))
        } catch {
          setTask(prev => ({ ...prev, status: 'completed' }))
        }
        eventSource.close()
      })

      // task_error - 任务错误
      eventSource.addEventListener('task_error', (e) => {
        try {
          const data = JSON.parse(e.data)
          setTask(prev => ({ ...prev, status: 'failed', error: data.error || '任务执行失败' }))
        } catch {
          setTask(prev => ({ ...prev, status: 'failed', error: '任务执行失败' }))
        }
        eventSource.close()
      })

      // task_cancelled - 任务取消
      eventSource.addEventListener('task_cancelled', () => {
        setTask(prev => ({ ...prev, status: 'cancelled' }))
        eventSource.close()
      })

      // ping - 心跳（忽略）
      eventSource.addEventListener('ping', () => {
        // 忽略心跳
      })

      eventSource.onerror = () => {
        if (task.status === 'running') {
          setTask(prev => ({ ...prev, status: 'failed', error: '连接中断，请检查 AutoGLM 服务' }))
        }
        eventSource.close()
      }

    } catch (error: any) {
      setTask(prev => ({ ...prev, status: 'failed', error: error.message }))
    }
  }, [input, task.status, activeConvId, token])

  // 取消任务
  const cancelCurrentTask = useCallback(async () => {
    if (task.taskId && task.status === 'running') {
      await cancelTask(task.taskId)
    }
  }, [task.taskId, task.status])

  // 回车提交
  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      executeTask()
    }
  }

  // 重置任务状态
  const resetTask = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }
    setTask({ taskId: null, status: 'idle', error: null, runningLog: null, logDetails: [] })
  }

  const grad: GradientPair = { from: gradFrom, to: gradTo, name: '' }

  return (
    <div style={{ minHeight: '100vh', background: '#F8F6F2', paddingTop: 56 }} className="relative">
      <HaloBackground gradFrom={gradFrom} gradTo={gradTo} intensity="subtle" />
      <Navbar onLogToggle={() => setLogOpen(o => !o)} />

      <div style={{ display: 'flex', height: 'calc(100vh - 56px)', overflow: 'hidden' }} className="relative z-10">

        {/* 左侧对话历史 */}
        <div style={{
          width: 240, flexShrink: 0,
          background: '#FFFFFF', borderRight: '1px solid #E0DFDB',
          display: 'flex', flexDirection: 'column',
          overflow: 'hidden',
        }}>
          <div style={{ padding: '14px 12px', borderBottom: '1px solid #E0DFDB' }}>
            <button
              onClick={createConversation}
              style={{
                width: '100%',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                padding: '8px 0',
                borderRadius: 6,
                background: gradientCSS(grad),
                color: 'white',
                border: 'none', cursor: 'pointer',
                fontFamily: "'Sora', sans-serif",
                fontSize: 13, fontWeight: 600,
              }}
            >
              <Plus size={14} /> 新建任务
            </button>
          </div>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {conversations.map(conv => (
              <button
                key={conv.id}
                onClick={() => setActiveConvId(conv.id)}
                style={{
                  width: '100%',
                  textAlign: 'left',
                  padding: '10px 12px',
                  background: conv.id === activeConvId ? '#F0EEE9' : 'transparent',
                  border: 'none',
                  borderLeft: conv.id === activeConvId ? `3px solid ${gradFrom}` : '3px solid transparent',
                  cursor: 'pointer',
                  transition: 'all 0.12s',
                  display: 'flex', alignItems: 'center', gap: 8,
                }}
              >
                <Zap size={13} style={{ color: '#888888', flexShrink: 0 }} />
                <span style={{
                  fontFamily: "'Sora', sans-serif",
                  fontSize: 12, color: '#0A0A0A',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {conv.title}
                </span>
              </button>
            ))}
            {conversations.length === 0 && (
              <div style={{ padding: 20, textAlign: 'center', fontFamily: "'Sora', sans-serif", fontSize: 12, color: '#AAAAAA' }}>
                点击上方创建新任务
              </div>
            )}
          </div>
        </div>

        {/* 主执行区域 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: '#F8F6F2' }}>

          {/* 任务状态栏 */}
          <div style={{
            padding: '12px 24px',
            borderBottom: '1px solid #E0DFDB',
            background: '#FFFFFF',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Zap size={16} style={{ color: gradFrom }} />
              <span style={{ fontFamily: "'Sora', sans-serif", fontSize: 14, fontWeight: 600, color: '#0A0A0A' }}>
                AutoGLM 执行
              </span>
            </div>

            {/* 任务状态 */}
            {task.status !== 'idle' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                {task.status === 'running' && (
                  <>
                    <Loader2 size={14} className="animate-spin" style={{ color: gradFrom }} />
                    <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 12, color: '#888888' }}>
                      执行中 ({task.logDetails.length} 步)
                    </span>
                  </>
                )}
                {task.status === 'submitting' && (
                  <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 12, color: gradFrom }}>
                    提交中...
                  </span>
                )}
                {task.status === 'completed' && (
                  <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 12, color: '#00AA44' }}>
                    ✓ 完成 ({task.logDetails.length} 步)
                  </span>
                )}
                {task.status === 'failed' && (
                  <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 12, color: '#FF2D55' }}>
                    ✗ 失败
                  </span>
                )}
                {task.status === 'cancelled' && (
                  <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 12, color: '#FF9500' }}>
                    已取消
                  </span>
                )}
                {(task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled') && (
                  <button
                    onClick={resetTask}
                    style={{
                      padding: '4px 8px',
                      borderRadius: 4,
                      border: '1px solid #E0E0E0',
                      background: '#FFFFFF',
                      fontFamily: "'Sora', sans-serif",
                      fontSize: 11,
                      cursor: 'pointer',
                    }}
                  >
                    重置
                  </button>
                )}
              </div>
            )}
          </div>

          {/* 内容区：用户消息 + 执行日志 */}
          <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', padding: '24px 32px 16px' }}>

            {/* 空闲状态 */}
            {task.status === 'idle' && messages.length === 0 && (
              <div style={{ textAlign: 'center', paddingTop: 80 }}>
                <div style={{
                  width: 64, height: 64,
                  borderRadius: '50%',
                  background: `${gradFrom}15`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  margin: '0 auto 16px',
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

            {/* 提交中 */}
            {task.status === 'submitting' && (
              <div style={{ textAlign: 'center', paddingTop: 40 }}>
                <Loader2 size={32} className="animate-spin" style={{ color: gradFrom, marginBottom: 16 }} />
                <div style={{ fontFamily: "'Sora', sans-serif", fontSize: 14, color: '#888888' }}>
                  正在提交任务...
                </div>
              </div>
            )}

            {/* 用户消息 */}
            {messages.filter(m => m.role === 'user').map(msg => (
              <div
                key={msg.id}
                style={{
                  display: 'flex',
                  justifyContent: 'flex-end',
                  marginBottom: 16,
                }}
              >
                <div
                  style={{
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
                  }}
                >
                  {msg.content}
                </div>
              </div>
            ))}

            {/* 执行中：上面显示当前卡片，下面显示日志列表 */}
            {(task.status === 'running' || task.status === 'submitting') && (
              <div>
                {/* 上面：当前执行状态卡片 */}
                {task.runningLog && (
                  <LogSummaryCard summary={task.runningLog} index={0} gradFrom={gradFrom} />
                )}

                {/* 下面：日志详情列表 */}
                <div style={{
                  marginTop: 16,
                  background: '#FFFFFF',
                  borderRadius: 12,
                  padding: 12,
                  boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
                }}>
                  <div style={{
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: 10,
                    color: '#888888',
                    marginBottom: 8,
                  }}>
                    执行日志 ({task.logDetails.length} 条)
                  </div>
                  <div style={{
                    maxHeight: 300,
                    overflowY: 'auto',
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: 11,
                    color: '#666666',
                    lineHeight: 1.6,
                  }}>
                    {task.logDetails.map((log, i) => (
                      <div key={i} style={{
                        padding: '2px 0',
                        borderBottom: i < task.logDetails.length - 1 ? '1px solid #F0EEE9' : 'none',
                      }}>
                        <span style={{ color: '#AAAAAA', marginRight: 8 }}>[{i + 1}]</span>
                        {log}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* 任务错误 */}
            {task.error && (
              <div style={{
                padding: '12px 16px',
                borderRadius: 8,
                background: 'rgba(255,45,85,0.08)',
                border: '1px solid rgba(255,45,85,0.2)',
                fontFamily: "'Sora', sans-serif",
                fontSize: 12,
                color: '#FF2D55',
              }}>
                错误: {task.error}
              </div>
            )}

            {/* 任务完成：显示总结 */}
            {task.status === 'completed' && task.runningLog && (
              <div>
                {/* 最终状态卡片 */}
                <LogSummaryCard
                  summary={{ ...task.runningLog, status: 'success', action: 'completed' }}
                  index={0}
                  gradFrom={gradFrom}
                />

                {/* 日志总结 */}
                <div style={{
                  marginTop: 16,
                  background: '#FFFFFF',
                  borderRadius: 12,
                  padding: 12,
                  boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
                }}>
                  <div style={{
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: 10,
                    color: '#888888',
                    marginBottom: 8,
                  }}>
                    执行日志 ({task.logDetails.length} 条)
                  </div>
                  <div style={{
                    maxHeight: 400,
                    overflowY: 'auto',
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: 11,
                    color: '#666666',
                    lineHeight: 1.6,
                  }}>
                    {task.logDetails.map((log, i) => (
                      <div key={i} style={{
                        padding: '2px 0',
                        borderBottom: i < task.logDetails.length - 1 ? '1px solid #F0EEE9' : 'none',
                      }}>
                        <span style={{ color: '#AAAAAA', marginRight: 8 }}>[{i + 1}]</span>
                        {log}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* 输入区 */}
          <div style={{
            padding: '12px 32px 20px',
            borderTop: '1px solid #E0DFDB',
            background: '#FFFFFF',
          }}>
            <div style={{
              display: 'flex', alignItems: 'flex-end', gap: 10,
              background: '#F8F6F2',
              borderRadius: 8,
              border: '1px solid #E0DFDB',
              padding: '8px 12px',
            }}>
              <textarea
                ref={textareaRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="描述任务，如：帮我在淘宝填收货地址..."
                rows={1}
                disabled={task.status === 'running' || task.status === 'submitting'}
                style={{
                  flex: 1,
                  resize: 'none',
                  border: 'none',
                  background: 'transparent',
                  fontFamily: "'Sora', sans-serif",
                  fontSize: 13,
                  color: '#0A0A0A',
                  outline: 'none',
                  lineHeight: 1.5,
                  maxHeight: 150,
                }}
              />

              {/* 取消按钮（执行中） */}
              {task.status === 'running' && (
                <button
                  onClick={cancelCurrentTask}
                  style={{
                    width: 32, height: 32,
                    borderRadius: 6,
                    border: '1px solid #E0E0E0',
                    background: '#FFFFFF',
                    color: '#FF2D55',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    cursor: 'pointer',
                    flexShrink: 0,
                  }}
                >
                  <X size={14} />
                </button>
              )}

              {/* 发送/执行按钮 */}
              <button
                onClick={executeTask}
                disabled={!input.trim() || task.status === 'running' || task.status === 'submitting'}
                style={{
                  width: 32, height: 32,
                  borderRadius: 6,
                  border: 'none',
                  background: input.trim() && task.status === 'idle' ? gradientCSS(grad) : '#E0E0E0',
                  color: 'white',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  cursor: input.trim() && task.status === 'idle' ? 'pointer' : 'not-allowed',
                  flexShrink: 0,
                  transition: 'background 0.15s',
                }}
              >
                <Play size={14} />
              </button>
            </div>

            <div style={{
              marginTop: 8,
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: 10,
              color: '#AAAAAA',
              textAlign: 'center',
            }}>
              按 Enter 提交任务 · 任务将在 AutoGLM 中执行
            </div>
          </div>
        </div>

        {/* 右侧日志面板 */}
        <LogPanel
          isOpen={logOpen}
          onClose={() => setLogOpen(false)}
          gradFrom={gradFrom}
          gradTo={gradTo}
          userId={user_id}
          token={token}
        />
      </div>
    </div>
  )
}

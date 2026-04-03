import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { motion, AnimatePresence } from "framer-motion"
import { Eye, EyeOff, Loader2 } from "lucide-react"
import { Particles } from "@/components/ui/Particles"
import useAuthStore from "@/store/authStore"
import { api, getErrorMessage, ERROR_MESSAGES } from "@/lib/api"
import { cn } from "@/lib/utils"

type InputState = "idle" | "username" | "email" | "password" | "confirm"

export default function RegisterPage() {
  const navigate = useNavigate()
  const { setAuth } = useAuthStore()

  const [username, setUsername] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [showPwd, setShowPwd] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)
  const [inputState, setInputState] = useState<InputState>("idle")
  const [bursting, setBursting] = useState(false)

  const particleProps = {
    idle:     { color: "#888888", staticity: 90, centerGravity: 0 },
    username: { color: "#777777", staticity: 80, centerGravity: 0.2 },
    email:    { color: "#666666", staticity: 70, centerGravity: 0.35 },
    password: { color: "#555555", staticity: 60, centerGravity: 0.5 },
    confirm:  { color: "#444444", staticity: 55, centerGravity: 0.6 },
  }[inputState]

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")

    if (password !== confirm) {
      setError(ERROR_MESSAGES.password_mismatch)
      return
    }
    if (password.length < 6) {
      setError(ERROR_MESSAGES.password_too_short)
      return
    }
    if (!email.includes("@")) {
      setError("请输入有效的邮箱地址")
      return
    }

    setLoading(true)
    try {
      const data = await api.register(email, password, username)
      setAuth(data.user_id, data.token, data.username, data.onboarding_done)
      setBursting(true)
      setTimeout(() => navigate("/onboarding"), 800)
    } catch (err) {
      setError(getErrorMessage(err))
      setLoading(false)
    }
  }

  const inputClass = (hasError?: boolean) =>
    cn(
      "w-full px-4 py-3 rounded-lg border text-sm bg-white/50 text-[#0A0A0A]",
      "placeholder:text-[#CCCCCC] outline-none transition-all duration-200",
      hasError
        ? "border-red-400 focus:border-red-500"
        : "border-[#E0E0E0] focus:border-[#0A0A0A]",
      "focus:bg-white/80"
    )

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-[#F5F5F5] flex">
      <Particles
        className="absolute inset-0 z-0"
        quantity={90}
        {...particleProps}
      />

      {/* Burst overlay */}
      <AnimatePresence>
        {bursting && (
          <motion.div
            className="absolute inset-0 z-50 pointer-events-none"
            initial={{ opacity: 0 }}
            animate={{ opacity: [0, 0.7, 0] }}
            transition={{ duration: 0.8, times: [0, 0.4, 1] }}
            style={{
              background: "radial-gradient(circle at 50% 50%, #7700FF88 0%, #7700FF44 40%, transparent 70%)",
            }}
          />
        )}
      </AnimatePresence>

      {/* Left brand */}
      <div className="relative z-10 flex flex-col justify-between w-[40%] h-full px-14 py-12 select-none">
        <div />
        <div>
          <h1 className="font-mono text-[2.5rem] font-semibold tracking-[0.2em] text-[#0A0A0A] leading-none">
            MaskClaw
          </h1>
          <p className="mt-4 text-[#888888] text-[0.9rem] leading-relaxed max-w-[260px]">
            学习你的隐私习惯，<br />端侧自进化保护
          </p>
        </div>
        <p className="font-mono text-[0.7rem] text-[#BBBBBB] tracking-wider">
          v0.1.0-demo
        </p>
      </div>

      {/* Right form */}
      <div className="relative z-10 flex items-center justify-center w-[60%] h-full">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          className="w-[400px] rounded-2xl border border-white/30 p-10"
          style={{
            backdropFilter: "blur(20px)",
            WebkitBackdropFilter: "blur(20px)",
            background: "rgba(255,255,255,0.62)",
            boxShadow: "0 8px 40px rgba(0,0,0,0.06)",
          }}
        >
          <h2 className="text-xl font-semibold text-[#0A0A0A] mb-7">创建账号</h2>

          <form onSubmit={handleSubmit} noValidate>
            {/* Username */}
            <div className="mb-4">
              <label className="block font-mono text-xs text-[#888888] mb-2 tracking-wider uppercase">
                用户名（显示名称）
              </label>
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                onFocus={() => setInputState("username")}
                onBlur={() => setInputState("idle")}
                placeholder="如：张医生"
                className={inputClass()}
              />
            </div>

            {/* Email */}
            <div className="mb-4">
              <label className="block font-mono text-xs text-[#888888] mb-2 tracking-wider uppercase">
                邮箱
              </label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                onFocus={() => setInputState("email")}
                onBlur={() => setInputState("idle")}
                placeholder="your@email.com"
                autoComplete="email"
                className={inputClass(!!error)}
              />
            </div>

            {/* Password */}
            <div className="mb-4">
              <label className="block font-mono text-xs text-[#888888] mb-2 tracking-wider uppercase">
                密码
              </label>
              <div className="relative">
                <input
                  type={showPwd ? "text" : "password"}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  onFocus={() => setInputState("password")}
                  onBlur={() => setInputState("idle")}
                  placeholder="至少 6 位"
                  autoComplete="new-password"
                  className={inputClass(!!error) + " pr-11"}
                />
                <button type="button" onClick={() => setShowPwd(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#AAAAAA] hover:text-[#555555] transition-colors" tabIndex={-1}>
                  {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {/* Confirm */}
            <div className="mb-5">
              <label className="block font-mono text-xs text-[#888888] mb-2 tracking-wider uppercase">
                确认密码
              </label>
              <div className="relative">
                <input
                  type={showConfirm ? "text" : "password"}
                  value={confirm}
                  onChange={e => setConfirm(e.target.value)}
                  onFocus={() => setInputState("confirm")}
                  onBlur={() => setInputState("idle")}
                  placeholder="再输入一次"
                  autoComplete="new-password"
                  className={inputClass(!!error) + " pr-11"}
                />
                <button type="button" onClick={() => setShowConfirm(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#AAAAAA] hover:text-[#555555] transition-colors" tabIndex={-1}>
                  {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <AnimatePresence>
              {error && (
                <motion.p
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="text-red-500 text-xs mb-4"
                >
                  {error}
                </motion.p>
              )}
            </AnimatePresence>

            <motion.button
              type="submit"
              disabled={loading}
              whileHover={{ backgroundColor: "#7700FF" }}
              whileTap={{ scale: 0.98 }}
              className="w-full py-3 rounded-lg text-sm font-medium text-white transition-colors duration-300 disabled:opacity-60 flex items-center justify-center gap-2"
              style={{ backgroundColor: "#0A0A0A" }}
            >
              {loading ? (
                <><Loader2 size={15} className="animate-spin" /><span>创建中...</span></>
              ) : "创建账号"}
            </motion.button>
          </form>

          <p className="mt-6 text-center text-sm text-[#888888]">
            已有账号？{" "}
            <Link to="/login" className="text-[#0A0A0A] font-medium hover:underline underline-offset-2">
              登录
            </Link>
          </p>
        </motion.div>
      </div>
    </div>
  )
}

import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { motion, AnimatePresence } from "framer-motion"
import { Loader2, ChevronRight, ChevronLeft, CheckCircle2 } from "lucide-react"
import { OrbBackground } from "@/components/ui/OrbBackground"
import { getAccentColor, getGradient, hexToRgba } from "@/lib/colorMap"
import { TagPill, AddTagInput } from "@/components/ui/TagPill"
import useAuthStore from "@/store/authStore"
import { api, getErrorMessage } from "@/lib/api"
import { generateRules } from "@/lib/ruleGen"
import { cn } from "@/lib/utils"

// ─── Occupation data ──────────────────────────────────────────────────────────
const OCCUPATION_TAGS = [
  "医生", "护士", "律师", "教师", "带货主播", "自媒体创作者",
  "财务/会计", "HR", "销售", "程序员", "学生", "自由职业",
  "企业管理者", "普通职员",
]

// ─── App recommendations by occupation keyword ───────────────────────────────
const RECOMMENDED_APPS: Record<string, string[]> = {
  医: ["微信", "HIS系统", "钉钉", "支付宝"],
  护: ["微信", "HIS系统", "钉钉", "支付宝"],
  主播: ["抖音", "微信", "小红书", "支付宝", "淘宝/天猫"],
  创作: ["抖音", "微信", "小红书", "支付宝", "淘宝/天猫"],
  财务: ["钉钉", "微信", "支付宝", "京东"],
  会计: ["钉钉", "微信", "支付宝", "京东"],
  律师: ["钉钉", "微信", "支付宝", "京东"],
  程序员: ["钉钉", "飞书", "微信", "支付宝"],
  技术: ["钉钉", "飞书", "微信", "支付宝"],
  学生: ["微信", "支付宝", "京东", "小红书"],
}

const ALL_APPS = [
  "微信", "支付宝", "钉钉", "飞书", "HIS系统", "抖音",
  "淘宝/天猫", "京东", "小红书", "QQ", "微博",
]

const SENSITIVE_FIELDS = [
  "手机号", "家庭住址", "身份证", "银行卡", "医疗记录",
  "工作内容", "行程位置", "收款信息", "家庭成员信息", "工资收入",
]

function getRecommendedApps(occupation: string): string[] {
  for (const [key, apps] of Object.entries(RECOMMENDED_APPS)) {
    if (occupation.includes(key)) return apps
  }
  return ["微信", "支付宝", "钉钉", "京东"]
}

// ─── Progress bar ─────────────────────────────────────────────────────────────
function ProgressBar({ step, accent }: { step: number; accent: string }) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 flex gap-1.5 h-[3px]">
        {[1, 2, 3].map(s => (
          <motion.div
            key={s}
            className="flex-1 rounded-full"
            animate={{ backgroundColor: s <= step ? accent : "#E0E0E0" }}
            transition={{ duration: 0.4 }}
          />
        ))}
      </div>
      <span className="font-mono text-xs text-[#888888] tracking-wider shrink-0">
        {step} / 3
      </span>
    </div>
  )
}

// ─── Step 1: Identity ─────────────────────────────────────────────────────────
function Step1({
  occupation, setOccupation, accentColor, onNext,
}: {
  occupation: string
  setOccupation: (v: string) => void
  accentColor: string
  onNext: () => void
}) {
  const [pulse, setPulse] = useState(false)

  const handleTagClick = (tag: string) => {
    setOccupation(tag)
    setPulse(true)
    setTimeout(() => setPulse(false), 300)
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-[#0A0A0A] mb-2">先认识一下你</h1>
      <p className="text-[#888888] text-sm mb-7">
        这会帮助系统生成你的初始保护方案
      </p>

      <div className="mb-5">
        <label className="block font-mono text-xs text-[#888888] mb-2 tracking-wider uppercase">
          职业 / 身份
        </label>
        <input
          type="text"
          value={occupation}
          onChange={e => setOccupation(e.target.value)}
          placeholder="自由输入，如：急诊科医生、带货主播、HR经理..."
          className="w-full px-4 py-3 rounded-lg border border-[#E0E0E0] bg-white/60 text-sm text-[#0A0A0A] placeholder:text-[#CCCCCC] outline-none focus:bg-white/80 transition-all"
          style={{ "--tw-ring-color": accentColor } as React.CSSProperties}
          onFocus={e => { e.currentTarget.style.borderColor = accentColor }}
          onBlur={e => { e.currentTarget.style.borderColor = "#E0E0E0" }}
        />
      </div>

      <div className="mb-8">
        <p className="font-mono text-xs text-[#888888] mb-3 tracking-wider uppercase">
          快速选择
        </p>
        <div className="flex flex-wrap gap-2">
          {OCCUPATION_TAGS.map(tag => (
            <TagPill
              key={tag}
              label={tag}
              selected={occupation === tag}
              accentColor={accentColor}
              onClick={() => { handleTagClick(tag); setPulse(false) }}
            />
          ))}
        </div>
      </div>

      <motion.button
        type="button"
        onClick={onNext}
        disabled={!occupation.trim()}
        whileHover={occupation.trim() ? { scale: 1.01 } : {}}
        whileTap={occupation.trim() ? { scale: 0.98 } : {}}
        className="flex items-center gap-2 px-6 py-3 rounded-lg text-sm font-medium text-white disabled:opacity-40 transition-opacity"
        style={{ backgroundColor: accentColor }}
      >
        下一步
        <ChevronRight size={15} />
      </motion.button>

      {/* Hidden pulse trigger */}
      {pulse && <span className="sr-only" />}
    </div>
  )
}

// ─── Step 2: Apps & Sensitive ─────────────────────────────────────────────────
function Step2({
  occupation,
  selectedApps, setSelectedApps,
  selectedSensitive, setSelectedSensitive,
  accentColor,
  onNext, onBack,
}: {
  occupation: string
  selectedApps: string[]; setSelectedApps: (v: string[]) => void
  selectedSensitive: string[]; setSelectedSensitive: (v: string[]) => void
  accentColor: string
  onNext: () => void; onBack: () => void
}) {
  const [extraApps, setExtraApps] = useState<string[]>([])
  const [extraSensitive, setExtraSensitive] = useState<string[]>([])
  const [pulse, setPulse] = useState(false)

  const recommended = getRecommendedApps(occupation)
  const otherApps = ALL_APPS.filter(a => !recommended.includes(a))

  const toggleApp = (app: string) => {
    setPulse(true)
    setTimeout(() => setPulse(false), 300)
    setSelectedApps(
      selectedApps.includes(app)
        ? selectedApps.filter(a => a !== app)
        : [...selectedApps, app]
    )
  }

  const toggleSensitive = (field: string) => {
    setPulse(true)
    setTimeout(() => setPulse(false), 300)
    setSelectedSensitive(
      selectedSensitive.includes(field)
        ? selectedSensitive.filter(f => f !== field)
        : [...selectedSensitive, field]
    )
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-[#0A0A0A] mb-2">
        你常用什么，在意什么？
      </h1>
      <p className="text-[#888888] text-sm mb-7">多选，可随时修改</p>

      {/* Apps */}
      <div className="mb-6">
        <p className="text-sm font-medium text-[#0A0A0A] mb-3">你常用哪些应用？</p>

        {recommended.length > 0 && (
          <div className="mb-3">
            <span className="font-mono text-[10px] text-[#888888] tracking-wider uppercase mr-2">推荐</span>
            <div className="inline-flex flex-wrap gap-2 mt-1">
              {recommended.map(app => (
                <TagPill key={app} label={app} selected={selectedApps.includes(app)}
                  accentColor={accentColor} onClick={() => toggleApp(app)} />
              ))}
            </div>
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          {otherApps.map(app => (
            <TagPill key={app} label={app} selected={selectedApps.includes(app)}
              accentColor={accentColor} onClick={() => toggleApp(app)} />
          ))}
          {extraApps.map(app => (
            <TagPill key={app} label={app} selected={selectedApps.includes(app)}
              accentColor={accentColor} onClick={() => toggleApp(app)} />
          ))}
          <AddTagInput
            accentColor={accentColor}
            onAdd={v => {
              setExtraApps(e => [...e, v])
              setSelectedApps([...selectedApps, v])
            }}
          />
        </div>
      </div>

      <div className="h-px bg-[#E0E0E0] my-6" />

      {/* Sensitive fields */}
      <div className="mb-8">
        <p className="text-sm font-medium text-[#0A0A0A] mb-3">哪些信息对你最敏感？</p>
        <div className="flex flex-wrap gap-2">
          {SENSITIVE_FIELDS.map(field => (
            <TagPill key={field} label={field} selected={selectedSensitive.includes(field)}
              accentColor={accentColor} onClick={() => toggleSensitive(field)} />
          ))}
          {extraSensitive.map(field => (
            <TagPill key={field} label={field} selected={selectedSensitive.includes(field)}
              accentColor={accentColor} onClick={() => toggleSensitive(field)} />
          ))}
          <AddTagInput
            accentColor={accentColor}
            onAdd={v => {
              setExtraSensitive(e => [...e, v])
              setSelectedSensitive([...selectedSensitive, v])
            }}
          />
        </div>
      </div>

      <div className="flex gap-3">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-1.5 px-5 py-3 rounded-lg text-sm text-[#888888] border border-[#E0E0E0] hover:border-[#AAAAAA] transition-colors"
        >
          <ChevronLeft size={15} />
          上一步
        </button>
        <motion.button
          type="button"
          onClick={onNext}
          whileHover={{ scale: 1.01 }}
          whileTap={{ scale: 0.98 }}
          className="flex items-center gap-2 px-6 py-3 rounded-lg text-sm font-medium text-white"
          style={{ backgroundColor: accentColor }}
        >
          下一步
          <ChevronRight size={15} />
        </motion.button>
      </div>

      {pulse && <span className="sr-only" />}
    </div>
  )
}

// ─── Step 3: Confirm plan ─────────────────────────────────────────────────────
function Step3({
  occupation, selectedApps, selectedSensitive,
  accentColor, loading, onBack, onFinish,
}: {
  occupation: string; selectedApps: string[]; selectedSensitive: string[]
  accentColor: string; loading: boolean; onBack: () => void; onFinish: () => void
}) {
  const rules = generateRules(occupation, selectedApps, selectedSensitive)

  return (
    <div>
      <h1 className="text-2xl font-semibold text-[#0A0A0A] mb-2">
        你的初始保护方案已生成
      </h1>
      <p className="text-[#888888] text-sm mb-8">
        基于你的职业和常用应用，系统为你预置了以下规则
      </p>

      {/* Rules list */}
      <div className="space-y-3 mb-6">
        {rules.map((rule, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.1, duration: 0.3 }}
            className="flex items-start gap-3"
          >
            <span
              className="mt-[5px] w-2 h-2 rounded-full shrink-0"
              style={{ backgroundColor: accentColor }}
            />
            <p className="text-sm text-[#0A0A0A] leading-relaxed">{rule}</p>
          </motion.div>
        ))}
      </div>

      {/* Summary chips */}
      {(selectedApps.length > 0 || selectedSensitive.length > 0) && (
        <div className="rounded-xl p-4 mb-8" style={{ backgroundColor: hexToRgba(accentColor, 0.06) }}>
          <div className="flex flex-wrap gap-1.5">
            {selectedApps.slice(0, 4).map(a => (
              <span key={a} className="font-mono text-xs px-2 py-0.5 rounded border"
                style={{ borderColor: hexToRgba(accentColor, 0.3), color: accentColor }}>
                {a}
              </span>
            ))}
            {selectedSensitive.slice(0, 4).map(f => (
              <span key={f} className="font-mono text-xs px-2 py-0.5 rounded border border-[#E0E0E0] text-[#888888]">
                {f}
              </span>
            ))}
          </div>
        </div>
      )}

      <p className="text-xs text-[#AAAAAA] mb-8 leading-relaxed">
        这只是起点，系统会在你使用过程中持续学习和更新这些规则
      </p>

      <div className="flex gap-3">
        <button
          type="button"
          onClick={onBack}
          disabled={loading}
          className="flex items-center gap-1.5 px-5 py-3 rounded-lg text-sm text-[#888888] border border-[#E0E0E0] hover:border-[#AAAAAA] transition-colors disabled:opacity-40"
        >
          <ChevronLeft size={15} />
          上一步
        </button>
        <motion.button
          type="button"
          onClick={onFinish}
          disabled={loading}
          whileHover={!loading ? { scale: 1.01 } : {}}
          whileTap={!loading ? { scale: 0.98 } : {}}
          className="flex items-center gap-2 px-6 py-3 rounded-lg text-sm font-medium text-white disabled:opacity-60"
          style={{ backgroundColor: accentColor }}
        >
          {loading ? (
            <><Loader2 size={15} className="animate-spin" /><span>提交中...</span></>
          ) : (
            <><CheckCircle2 size={15} /><span>进入系统</span></>
          )}
        </motion.button>
      </div>
    </div>
  )
}

// ─── Main OnboardingPage ──────────────────────────────────────────────────────
export default function OnboardingPage() {
  const navigate = useNavigate()
  const { user_id, token, username, setProfile, setAccentColor, logout } = useAuthStore()

  const [step, setStep] = useState(1)
  const [occupation, setOccupation] = useState("")
  const [selectedApps, setSelectedApps] = useState<string[]>([])
  const [selectedSensitive, setSelectedSensitive] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [orbPulse, setOrbPulse] = useState(false)

  const accentColor = getAccentColor(occupation) || "#7700FF"
  const { from: gradFrom, to: gradTo } = getGradient(occupation)

  const triggerPulse = () => {
    setOrbPulse(true)
    setTimeout(() => setOrbPulse(false), 350)
  }

  const handleNext = () => {
    triggerPulse()
    setStep(s => s + 1)
  }

  const handleBack = () => {
    setStep(s => s - 1)
  }

  const [savingError, setSavingError] = useState<string | null>(null)

  const handleFinish = async () => {
    setLoading(true)
    setSavingError(null)
    try {
      if (!user_id || !token) {
        setSavingError("登录已失效，请重新登录")
        setLoading(false)
        return
      }
      // 写入 profile + 播种默认 Skill（两步合一）
      const result = await api.completeOnboarding(user_id, {
        username: username ?? undefined,
        occupation,
        apps: selectedApps,
        sensitive_fields: selectedSensitive,
        onboarding_done: true,
        grad_from: gradFrom,
        grad_to: gradTo,
      })
      console.info(`[onboarding] seeded ${result.seeded_skills} default skills`)
      setProfile(occupation, selectedApps, selectedSensitive)
      setAccentColor(accentColor)
      triggerPulse()
      setTimeout(() => navigate("/app"), 600)
    } catch (err: any) {
      const msg = getErrorMessage(err)
      // 401 认证失效：清除 token 并引导重新登录
      if (err?.isAuthError || msg.includes("invalid_token") || msg.includes("missing_auth")) {
        logout()
        setSavingError("登录已失效，正在跳转登录页...")
        setTimeout(() => navigate("/login"), 1500)
      } else {
        setSavingError(msg)
      }
      console.error(msg)
    } finally {
      setLoading(false)
    }
  }

  const stepVariants = {
    initial: { opacity: 0, x: 30 },
    animate: { opacity: 1, x: 0 },
    exit:    { opacity: 0, x: -30 },
  }

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-[#F7F7F7]">
      {/* Orb background */}
      <OrbBackground gradFrom={gradFrom} gradTo={gradTo} pulseKey={orbPulse ? Date.now() : 0} />

      <div className="relative z-10 flex flex-col h-full">
        {/* Header */}
        <div className="flex items-center justify-between px-10 py-6">
          <span className="font-mono text-sm font-medium tracking-[0.15em] text-[#0A0A0A]">
            MaskClaw
          </span>
          <div className="w-64">
            <ProgressBar step={step} accent={accentColor} />
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 flex items-center justify-center px-4 pb-8">
          <div className="w-full max-w-[560px]">
            <motion.div
              className="bg-white/70 rounded-2xl border border-white/40 p-10"
              style={{
                backdropFilter: "blur(16px)",
                WebkitBackdropFilter: "blur(16px)",
                boxShadow: `0 8px 40px ${hexToRgba(accentColor, 0.08)}`,
              }}
            >
              <AnimatePresence mode="wait">
                {step === 1 && (
                  <motion.div key="step1" variants={stepVariants}
                    initial="initial" animate="animate" exit="exit"
                    transition={{ duration: 0.25 }}>
                    <Step1
                      occupation={occupation}
                      setOccupation={v => {
                        setOccupation(v)
                        triggerPulse()
                      }}
                      accentColor={accentColor}
                      onNext={handleNext}
                    />
                  </motion.div>
                )}

                {step === 2 && (
                  <motion.div key="step2" variants={stepVariants}
                    initial="initial" animate="animate" exit="exit"
                    transition={{ duration: 0.25 }}>
                    <Step2
                      occupation={occupation}
                      selectedApps={selectedApps}
                      setSelectedApps={setSelectedApps}
                      selectedSensitive={selectedSensitive}
                      setSelectedSensitive={setSelectedSensitive}
                      accentColor={accentColor}
                      onNext={handleNext}
                      onBack={handleBack}
                    />
                  </motion.div>
                )}

                {step === 3 && (
                  <motion.div key="step3" variants={stepVariants}
                    initial="initial" animate="animate" exit="exit"
                    transition={{ duration: 0.25 }}>
                    <Step3
                      occupation={occupation}
                      selectedApps={selectedApps}
                      selectedSensitive={selectedSensitive}
                      accentColor={accentColor}
                      loading={loading}
                      onBack={handleBack}
                      onFinish={handleFinish}
                    />
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>

            {savingError && (
              <motion.div
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-3 text-center text-xs text-red-500 font-mono"
              >
                保存失败：{savingError}
              </motion.div>
            )}

            {/* Greeting below card */}
            {username && (
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.4 }}
                className="text-center text-xs text-[#AAAAAA] mt-4 font-mono tracking-wider"
              >
                你好，{username}
              </motion.p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

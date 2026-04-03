/**
 * TagPill — selectable pill tag component.
 * Used in Onboarding Step 1 (occupation chips) and Step 2 (app/sensitive field chips).
 */
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { hexToRgba } from "@/lib/colorMap"

interface TagPillProps {
  label: string
  selected?: boolean
  accentColor?: string
  gradTo?: string
  onClick?: () => void
  className?: string
  size?: "sm" | "md"
}

export function TagPill({
  label,
  selected = false,
  accentColor = "#7700FF",
  gradTo,
  onClick,
  className,
  size = "md",
}: TagPillProps) {
  const selectedBackground = gradTo
    ? `linear-gradient(135deg, ${accentColor}, ${gradTo})`
    : accentColor

  return (
    <motion.button
      type="button"
      onClick={onClick}
      whileTap={{ scale: 0.95 }}
      animate={{
        y: selected ? -2 : 0,
        boxShadow: selected
          ? `0 4px 12px ${hexToRgba(accentColor, 0.25)}`
          : "0 0 0 transparent",
      }}
      transition={{ duration: 0.15, ease: "easeOut" }}
      className={cn(
        "relative inline-flex items-center rounded border transition-colors duration-150 cursor-pointer select-none",
        size === "md" ? "px-3.5 py-1.5 text-sm" : "px-2.5 py-1 text-xs",
        selected
          ? "border-transparent text-white"
          : "border-[#E0E0E0] bg-transparent text-[#0A0A0A] hover:border-[#AAAAAA]",
        className
      )}
      style={selected ? { background: selectedBackground } : undefined}
    >
      {label}
    </motion.button>
  )
}

interface AddTagInputProps {
  accentColor?: string
  onAdd: (value: string) => void
}

export function AddTagInput({ accentColor = "#7700FF", onAdd }: AddTagInputProps) {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      const v = e.currentTarget.value.trim()
      if (v) {
        onAdd(v)
        e.currentTarget.value = ""
      }
    }
  }
  return (
    <span className="inline-flex items-center rounded border border-dashed border-[#CCCCCC] px-3.5 py-1.5 text-sm">
      <input
        type="text"
        placeholder="+ 添加其他"
        onKeyDown={handleKeyDown}
        className="bg-transparent outline-none text-[#888888] placeholder-[#CCCCCC] w-20 text-sm"
        style={{ minWidth: 80 }}
        onFocus={(e) => {
          e.currentTarget.parentElement!.style.borderColor = accentColor
        }}
        onBlur={(e) => {
          e.currentTarget.parentElement!.style.borderColor = "#CCCCCC"
        }}
      />
    </span>
  )
}

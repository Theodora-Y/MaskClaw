/**
 * Particles — from Magic UI (https://magicui.design/r/particles)
 * Adapted: added centerGravity prop for input-based attraction effect.
 */
"use client"

import React, {
  useEffect,
  useRef,
  useState,
  type ComponentPropsWithoutRef,
} from "react"
import { cn } from "@/lib/utils"

interface MousePosition {
  x: number
  y: number
}

function useMousePosition(): MousePosition {
  const [pos, setPos] = useState<MousePosition>({ x: 0, y: 0 })
  useEffect(() => {
    const h = (e: MouseEvent) => setPos({ x: e.clientX, y: e.clientY })
    window.addEventListener("mousemove", h)
    return () => window.removeEventListener("mousemove", h)
  }, [])
  return pos
}

interface ParticlesProps extends ComponentPropsWithoutRef<"div"> {
  className?: string
  quantity?: number
  staticity?: number
  ease?: number
  size?: number
  refresh?: boolean
  color?: string
  vx?: number
  vy?: number
  /** 0-1: extra gravity toward canvas center (for input focus effect) */
  centerGravity?: number
}

function hexToRgb(hex: string): number[] {
  hex = hex.replace("#", "")
  if (hex.length === 3) hex = hex.split("").map(c => c + c).join("")
  const n = parseInt(hex, 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}

type Circle = {
  x: number; y: number
  translateX: number; translateY: number
  size: number; alpha: number; targetAlpha: number
  dx: number; dy: number; magnetism: number
}

export const Particles: React.FC<ParticlesProps> = ({
  className = "",
  quantity = 100,
  staticity = 80,
  ease = 50,
  size = 0.5,
  refresh = false,
  color = "#555555",
  vx = 0, vy = 0,
  centerGravity = 0,
  ...props
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const ctx = useRef<CanvasRenderingContext2D | null>(null)
  const circles = useRef<Circle[]>([])
  const mousePos = useMousePosition()
  const mouse = useRef({ x: 0, y: 0 })
  const canvasSize = useRef({ w: 0, h: 0 })
  const dpr = typeof window !== "undefined" ? window.devicePixelRatio : 1
  const rafID = useRef<number | null>(null)

  const initCanvas = () => {
    if (!containerRef.current || !canvasRef.current || !ctx.current) return
    const w = containerRef.current.offsetWidth
    const h = containerRef.current.offsetHeight
    canvasSize.current = { w, h }
    canvasRef.current.width = w * dpr
    canvasRef.current.height = h * dpr
    canvasRef.current.style.width = `${w}px`
    canvasRef.current.style.height = `${h}px`
    ctx.current.scale(dpr, dpr)
    circles.current = []
    for (let i = 0; i < quantity; i++) {
      const c = circleParams()
      drawCircle(c)
    }
  }

  const circleParams = (): Circle => {
    const { w, h } = canvasSize.current
    return {
      x: Math.random() * w,
      y: Math.random() * h,
      translateX: 0, translateY: 0,
      size: Math.random() * 2 + size,
      alpha: 0,
      targetAlpha: parseFloat((Math.random() * 0.5 + 0.1).toFixed(2)),
      dx: (Math.random() - 0.5) * 0.08,
      dy: (Math.random() - 0.5) * 0.08,
      magnetism: 0.1 + Math.random() * 4,
    }
  }

  const rgb = hexToRgb(color)

  const drawCircle = (c: Circle, update = false) => {
    if (!ctx.current) return
    ctx.current.translate(c.translateX, c.translateY)
    ctx.current.beginPath()
    ctx.current.arc(c.x, c.y, c.size, 0, Math.PI * 2)
    ctx.current.fillStyle = `rgba(${rgb.join(",")},${c.alpha})`
    ctx.current.fill()
    ctx.current.setTransform(dpr, 0, 0, dpr, 0, 0)
    if (!update) circles.current.push(c)
  }

  const clearCtx = () => {
    if (ctx.current) {
      ctx.current.clearRect(0, 0, canvasSize.current.w, canvasSize.current.h)
    }
  }

  const animate = () => {
    clearCtx()
    const { w, h } = canvasSize.current
    circles.current.forEach((c, i) => {
      const edge = [
        c.x + c.translateX - c.size,
        w - c.x - c.translateX - c.size,
        c.y + c.translateY - c.size,
        h - c.y - c.translateY - c.size,
      ]
      const closest = Math.min(...edge)
      const fade = Math.max(0, Math.min(1, closest / 20))
      c.alpha += (c.targetAlpha * fade - c.alpha) * 0.05

      c.x += c.dx + vx
      c.y += c.dy + vy

      // Mouse magnetism
      c.translateX += (mouse.current.x / (staticity / c.magnetism) - c.translateX) / ease
      c.translateY += (mouse.current.y / (staticity / c.magnetism) - c.translateY) / ease

      // Center gravity (used when user is typing)
      if (centerGravity > 0) {
        const cx = w / 2, cy = h / 2
        const dx = cx - c.x, dy = cy - c.y
        c.x += dx * centerGravity * 0.0015
        c.y += dy * centerGravity * 0.0015
      }

      drawCircle(c, true)

      // Respawn out-of-bounds particles
      if (c.x < -c.size || c.x > w + c.size || c.y < -c.size || c.y > h + c.size) {
        circles.current.splice(i, 1)
        drawCircle(circleParams())
      }
    })
    rafID.current = requestAnimationFrame(animate)
  }

  useEffect(() => {
    if (canvasRef.current) ctx.current = canvasRef.current.getContext("2d")
    initCanvas()
    rafID.current = requestAnimationFrame(animate)
    const onResize = () => setTimeout(initCanvas, 200)
    window.addEventListener("resize", onResize)
    return () => {
      if (rafID.current) cancelAnimationFrame(rafID.current)
      window.removeEventListener("resize", onResize)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [color, quantity])

  useEffect(() => {
    if (!canvasRef.current) return
    const rect = canvasRef.current.getBoundingClientRect()
    const { w, h } = canvasSize.current
    const x = mousePos.x - rect.left - w / 2
    const y = mousePos.y - rect.top - h / 2
    if (Math.abs(x) < w / 2 && Math.abs(y) < h / 2) {
      mouse.current = { x, y }
    }
  }, [mousePos])

  useEffect(() => { initCanvas() }, [refresh])

  return (
    <div
      ref={containerRef}
      className={cn("pointer-events-none", className)}
      aria-hidden="true"
      {...props}
    >
      <canvas ref={canvasRef} className="size-full" />
    </div>
  )
}

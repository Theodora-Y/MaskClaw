"use client"

import type React from "react"
import { useRef, useState, useCallback, useEffect } from "react"

interface MagneticTextProps {
  text: string
  hoverText?: string
  className?: string
  /** 文字颜色，默认 #0A0A0A */
  color?: string
  /** 悬浮圆形颜色，默认 #4169E1（宝蓝色） */
  circleColor?: string
  /** 文字大小，默认 48px */
  fontSize?: number
}

export function MagneticText({
  text = "CREATIVE",
  hoverText = "EXPLORE",
  className,
  color = "#0A0A0A",
  circleColor = "#4169E1",
  fontSize = 48,
}: MagneticTextProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const circleRef = useRef<HTMLDivElement>(null)
  const innerTextRef = useRef<HTMLDivElement>(null)
  const [isHovered, setIsHovered] = useState(false)
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 })

  const mousePos = useRef({ x: 0, y: 0 })
  const currentPos = useRef({ x: 0, y: 0 })
  const animationFrameRef = useRef<number | undefined>(undefined)

  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        setContainerSize({
          width: containerRef.current.offsetWidth,
          height: containerRef.current.offsetHeight,
        })
      }
    }
    updateSize()
    window.addEventListener("resize", updateSize)
    return () => window.removeEventListener("resize", updateSize)
  }, [])

  useEffect(() => {
    const lerp = (start: number, end: number, factor: number) => start + (end - start) * factor

    const animate = () => {
      currentPos.current.x = lerp(currentPos.current.x, mousePos.current.x, 0.15)
      currentPos.current.y = lerp(currentPos.current.y, mousePos.current.y, 0.15)

      if (circleRef.current) {
        circleRef.current.style.transform =
          `translate(${currentPos.current.x}px, ${currentPos.current.y}px) translate(-50%, -50%)`
      }

      if (innerTextRef.current) {
        innerTextRef.current.style.transform =
          `translate(${-currentPos.current.x}px, ${-currentPos.current.y}px)`
      }

      animationFrameRef.current = requestAnimationFrame(animate)
    }

    animationFrameRef.current = requestAnimationFrame(animate)
    return () => {
      if (animationFrameRef.current !== undefined) {
        cancelAnimationFrame(animationFrameRef.current)
      }
    }
  }, [])

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return
    const rect = containerRef.current.getBoundingClientRect()
    mousePos.current = {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    }
  }, [])

  const handleMouseEnter = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return
    const rect = containerRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    mousePos.current = { x, y }
    currentPos.current = { x, y }
    setIsHovered(true)
  }, [])

  const handleMouseLeave = useCallback(() => {
    setIsHovered(false)
  }, [])

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={className}
      style={{
        position: "relative",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        cursor: "default",
        userSelect: "none",
        fontSize,
        fontFamily: "'Sora', sans-serif",
        fontWeight: 700,
        letterSpacing: "0.05em",
        color,
      }}
    >
      {/* Base text layer */}
      <span>{text}</span>

      {/* Hover circle with reversed text */}
      <div
        ref={circleRef}
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          pointerEvents: "none",
          borderRadius: "50%",
          background: circleColor,
          overflow: "hidden",
          width: isHovered ? 150 : 0,
          height: isHovered ? 150 : 0,
          transition:
            "width 0.5s cubic-bezier(0.33, 1, 0.68, 1), height 0.5s cubic-bezier(0.33, 1, 0.68, 1)",
          willChange: "transform, width, height",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <div
          ref={innerTextRef}
          style={{
            position: "absolute",
            width: containerSize.width,
            height: containerSize.height,
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            willChange: "transform",
          }}
        >
          <span
            style={{
              fontSize,
              fontFamily: "'Sora', sans-serif",
              fontWeight: 700,
              letterSpacing: "0.05em",
              color: "white",
              whiteSpace: "nowrap",
            }}
          >
            {hoverText}
          </span>
        </div>
      </div>
    </div>
  )
}

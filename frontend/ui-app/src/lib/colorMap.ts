/**
 * 职业→渐变色对映射
 * 每个用户有 from/to 二色渐变，而非单一 hex。
 * 这是视觉核心：白底上用 multiply 混合的渐变光晕。
 */

export interface GradientPair {
  from: string
  to: string
  name: string
}

/** 五种渐变色系，每种对应一类职业 */
export const GRADIENT_PRESETS: Record<string, GradientPair> = {
  cool:    { from: '#00C6FF', to: '#0072FF', name: 'Cool 冷蓝' },
  warm:    { from: '#F7971E', to: '#FFD200', name: 'Warm 琥珀' },
  nature:  { from: '#0BA360', to: '#3CBA92', name: 'Nature 自然' },
  electric:{ from: '#7028E4', to: '#E5B2CA', name: 'Electric 电弧' },
  rose:    { from: '#FF416C', to: '#6A82FB', name: 'Rose 玫瑰' },
}

export const DEFAULT_GRADIENT: GradientPair = GRADIENT_PRESETS.rose

/** 职业关键词 → 渐变色系 */
const OCCUPATION_GRADIENT_MAP: Array<[string[], keyof typeof GRADIENT_PRESETS]> = [
  [['医生','护士','医疗','急诊','外科','内科','药剂','牙医','卫生','健康'], 'cool'],
  [['主播','带货','自媒体','创作者','博主','网红','up主','直播','设计','艺术'], 'warm'],
  [['财务','会计','律师','法律','法务','审计','税务','金融','银行','保险'], 'nature'],
  [['程序员','开发','工程师','技术','算法','前端','后端','数据','ai','it'], 'electric'],
]

export function getGradient(occupation: string): GradientPair {
  if (!occupation) return DEFAULT_GRADIENT
  const lower = occupation.toLowerCase()
  for (const [keywords, preset] of OCCUPATION_GRADIENT_MAP) {
    if (keywords.some(k => lower.includes(k))) {
      return GRADIENT_PRESETS[preset]
    }
  }
  return DEFAULT_GRADIENT
}

/** 渐变对 → CSS linear-gradient 字符串 */
export function gradientCSS(g: GradientPair, deg = 135): string {
  return `linear-gradient(${deg}deg, ${g.from}, ${g.to})`
}

/** 渐变对 → 极淡背景色调（用于卡片激活底色） */
export function gradientTint(g: GradientPair, opacity = 0.05): string {
  return `linear-gradient(135deg, ${hexToRgba(g.from, opacity)}, ${hexToRgba(g.to, opacity)})`
}

/** hex → rgba */
export function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1,3), 16)
  const g = parseInt(hex.slice(3,5), 16)
  const b = parseInt(hex.slice(5,7), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

/** 兼容：保留旧的 getAccentColor，返回 from 颜色 */
export function getAccentColor(occupation: string): string {
  return getGradient(occupation).from
}

export const DEFAULT_ACCENT = DEFAULT_GRADIENT.from

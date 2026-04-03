/**
 * tagColorMap.ts — App/场景 Tag 固定颜色映射
 * 参考各大应用品牌色，固定分配，保持视觉一致性。
 * 未收录的 tag 用稳定 hash 从 PALETTE 取色，相同名称永远同一颜色。
 */

const FIXED_TAG_COLORS: Record<string, string> = {
  // 社交通讯
  '微信': '#07C160',
  'wechat': '#07C160',
  'WeChat': '#07C160',
  // 电商
  '淘宝': '#FF6900',
  '天猫': '#FF6900',
  '淘宝/天猫': '#FF6900',
  '京东': '#E1251B',
  // 支付
  '支付宝': '#1677FF',
  // 短视频/内容
  '抖音': '#FF0050',
  '小红书': '#FF2442',
  '微博': '#E6162D',
  'QQ': '#12B7F5',
  // 办公
  '钉钉': '#2979FF',
  '飞书': '#3370FF',
  'HIS系统': '#0BA360',
  'OA': '#2979FF',
  // 场景/字段类（固定但中性）
  '通用': '#888888',
  '外部人员': '#7028E4',
  '陌生人': '#7028E4',
  '医疗记录': '#0BA360',
  '手机号': '#F7971E',
  '家庭住址': '#FF416C',
  '银行卡': '#1677FF',
  '身份证': '#FF9500',
  '行程位置': '#00CCAA',
  '工作内容': '#6B7280',
  '收款信息': '#1677FF',
  '表单填写': '#888888',
  '医疗顾问': '#0BA360',
}

// 兜底色盘（7种，经过调色保持和谐）
const PALETTE = [
  '#7028E4', // 紫
  '#0BA360', // 绿
  '#F7971E', // 橙
  '#1677FF', // 蓝
  '#FF416C', // 红
  '#00CCAA', // 青
  '#6B7280', // 灰蓝
]

function hashColor(str: string): string {
  let h = 0
  for (let i = 0; i < str.length; i++) {
    h = (h * 31 + str.charCodeAt(i)) >>> 0
  }
  return PALETTE[h % PALETTE.length]
}

export function getTagColor(tag: string): string {
  return FIXED_TAG_COLORS[tag] ?? hashColor(tag)
}

/** 返回淡色背景（低透明度，用于 tag 背景） */
export function getTagBg(tag: string, opacity = 0.12): string {
  const hex = getTagColor(tag)
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r},${g},${b},${opacity})`
}

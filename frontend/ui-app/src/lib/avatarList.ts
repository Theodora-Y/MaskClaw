/**
 * 头像资产列表
 * 使用 Vite import.meta.glob 动态导入 assets/Avatars_ Professions set/ 下所有 PNG。
 * 返回 URL 字符串数组，按文件名排序以保证顺序稳定。
 */

const modules = import.meta.glob<{ default: string }>(
  '../assets/Avatars_ Professions set/*.png',
  { eager: true }
)

export const AVATAR_LIST: string[] = Object.entries(modules)
  .sort(([a], [b]) => a.localeCompare(b))
  .map(([, mod]) => mod.default)

export const AVATAR_COUNT = AVATAR_LIST.length

/** 根据 index 获取头像 URL，越界时循环 */
export function getAvatarUrl(index: number): string {
  if (AVATAR_LIST.length === 0) return ''
  return AVATAR_LIST[Math.abs(index) % AVATAR_LIST.length]
}

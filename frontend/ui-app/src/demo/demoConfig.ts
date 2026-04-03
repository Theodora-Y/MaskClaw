import type { GradientPair } from '@/lib/colorMap'

/**
 * 三个演示用户的完整配置
 * 用于演示模式场景展示，不影响真实用户数据
 */
export interface DemoUserConfig {
  key: 'UserA' | 'UserB' | 'UserC'
  label: string
  occupation: string
  username: string
  gradient: GradientPair
  description: string
  scenario: string
  /** AutoGLM 演示场景的初始任务描述 */
  autoGLMTask: string
}

export const DEMO_USERS: Record<string, DemoUserConfig> = {
  UserA: {
    key: 'UserA',
    label: 'UserA — 医疗场景',
    occupation: '医生',
    username: '演示医生',
    gradient: { from: '#00C6FF', to: '#0072FF', name: 'Cool 冷蓝' },
    description: '医院急诊科医生，日常接触大量患者隐私信息。',
    scenario: '医疗隐私保护 · 处方单脱敏 · 病历访问控制',
    autoGLMTask: '帮我在钉钉工作群中发送一条消息给科室护士长，内容包含今日患者的姓名和诊断结果。',
  },
  UserB: {
    key: 'UserB',
    label: 'UserB — 电商场景',
    occupation: '主播',
    username: '演示主播',
    gradient: { from: '#F7971E', to: '#FFD200', name: 'Warm 琥珀' },
    description: '带货主播，日常直播中需要处理商品信息和粉丝数据。',
    scenario: '直播数据保护 · 商品信息脱敏 · 粉丝隐私',
    autoGLMTask: '帮我登录小红书，草拟一篇带货笔记，分享今天直播的商品链接和粉丝互动数据。',
  },
  UserC: {
    key: 'UserC',
    label: 'UserC — 职员场景',
    occupation: '一般职员',
    username: '演示职员',
    gradient: { from: '#0BA360', to: '#3CBA92', name: 'Nature 自然' },
    description: '公司职员，日常工作中处理各类文档和通讯信息。',
    scenario: '办公信息安全 · 文件传输保护 · 通讯隐私',
    autoGLMTask: '帮我在美团点一份黄焖鸡米饭，选择商家后提交订单。',
  },
}

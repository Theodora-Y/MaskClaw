/**
 * 前端 Mock 数据
 * 用于尚未实现后端接口的页面。
 * 所有 mock 数据在后端接口完善后逐步替换。
 */

// --- Skill 卡片（主页）---

export type SkillStatus = 'active' | 'warning' | 'conflict' | 'disabled'

export interface SkillCard {
  skill_id: string
  slug: string        // 英文标识名，API 调用专用
  name: string        // 中文展示名（来自 rj.scene）
  app_context: string
  scene_tags: string[]
  status: SkillStatus
  last_updated_ts: number
  version: string
  task_description?: string
}

export const MOCK_SKILLS: SkillCard[] = [
  {
    skill_id: 'wechat-medical-v1',
    slug: 'wechat-medical',
    name: '微信病历传输规范',
    app_context: '微信',
    scene_tags: ['医疗记录', '外部人员'],
    status: 'active',
    last_updated_ts: 1742688000, // 2026-03-23
    version: 'v1',
    task_description: '在微信聊天窗口中发送含医疗记录的消息时，不得向非医疗系统内人员发送原始病历文件',
  },
  {
    skill_id: 'alipay-receipt-v1',
    slug: 'alipay-receipt',
    name: '支付宝收款码行为',
    app_context: '支付宝',
    scene_tags: ['收款信息', '陌生人'],
    status: 'warning',
    last_updated_ts: 1742774400, // 2026-03-24
    version: 'v1',
    task_description: '使用支付宝扫描商家收款码完成支付时，支付记录不得将含金额的截图发给他人',
  },
  {
    skill_id: 'dingtalk-contact-v1',
    slug: 'dingtalk-contact',
    name: 'OA 联系方式外传保护',
    app_context: '钉钉',
    scene_tags: ['工作内容', '外部渠道'],
    status: 'active',
    last_updated_ts: 1742860800, // 2026-03-25
    version: 'v1',
    task_description: '在钉钉的工作群聊中发送消息时，工作群消息仅限群内可见，不得转发至外部渠道',
  },
  {
    skill_id: 'home-address-v1',
    slug: 'home-address',
    name: '家庭住址保护',
    app_context: '通用',
    scene_tags: ['家庭住址', '表单填写'],
    status: 'conflict',
    last_updated_ts: 1742947200, // 2026-03-26
    version: 'v1',
    task_description: '在各类表单中填写个人信息时，家庭住址不得与工作地址混淆，涉密表单需使用脱敏地址',
  },
  {
    skill_id: 'phone-share-v1',
    slug: 'phone-share',
    name: '手机号分享管控',
    app_context: '通用',
    scene_tags: ['手机号', '陌生人'],
    status: 'disabled',
    last_updated_ts: 1742947200, // 2026-03-26
    version: 'v1',
    task_description: '通过任何渠道向陌生人分享手机号前需二次确认，防止个人信息被滥用',
  },
]

// --- Skill 详情（抽屉）---

export interface SkillStep {
  step_num: number
  title: string
  action: string
  exception_handling?: string
  has_privacy_protection: boolean
}

export interface SkillTimelineItem {
  ts: number
  event_type: 'added' | 'conflict' | 'disabled'
  type_label: string
  summary: string
  source: string
  correction_detail?: string
}

export interface SkillDetail extends SkillCard {
  _sceneTitle?: string
  _appZh?: string
  _tags?: string[]
  content: {
    scene_description: string
    privacy_constraints: string[]
    steps: SkillStep[]
  }
  timeline: SkillTimelineItem[]
}

export const MOCK_SKILL_DETAIL: SkillDetail = {
  ...MOCK_SKILLS[0],
  content: {
    scene_description: '微信 · 发送含医疗记录的消息',
    privacy_constraints: [
      '不得向非医疗系统内人员发送原始病历文件',
      '消息内容含诊断信息时，需确认接收方身份',
    ],
    steps: [
      {
        step_num: 1,
        title: '检测消息内容',
        action: '识别消息中是否包含医疗记录、诊断结论、检查报告等敏感字段',
        has_privacy_protection: true,
      },
      {
        step_num: 2,
        title: '核验接收方',
        action: '查询通讯录确认对方是否在医疗系统白名单内',
        exception_handling: '若无法确认接收方身份，暂停发送并弹出确认弹层',
        has_privacy_protection: true,
      },
      {
        step_num: 3,
        title: '执行发送',
        action: '确认通过后执行发送，同时记录本次操作到行为日志',
        has_privacy_protection: false,
      },
    ],
  },
  timeline: [
    {
      ts: 1742313600,
      event_type: 'added',
      type_label: '规则新增',
      summary: '首次触发：向非系统内联系人发送含诊断结论的消息',
      source: '用户纠错',
      correction_detail: '用户手动拒绝了发送操作，系统记录并生成此规则',
    },
    {
      ts: 1742227200,
      event_type: 'conflict',
      type_label: '规则待确认',
      summary: '规则与新触发场景产生冲突，需重新审核边界条件',
      source: '自动推导',
    },
  ],
}

// --- 待确认变更（登录后弹层）---

export interface PendingChange {
  event_id: string
  skill_name: string
  event_type: 'added' | 'conflict' | 'disabled'
  type_label: string
  summary: string
  ts: number
  date_str: string
}

export const MOCK_PENDING_CHANGES: PendingChange[] = [
  {
    event_id: 'mock-pending-1',
    skill_name: '微信病历传输规范',
    event_type: 'added',
    type_label: '新增规则',
    summary: '在微信场景下，含手机号的消息发送给陌生人时将被拦截',
    ts: 1742313600,
    date_str: '2026年3月23日',
  },
  {
    event_id: 'mock-pending-2',
    skill_name: '支付宝收款码行为',
    event_type: 'conflict',
    type_label: '规则待确认',
    summary: '支付宝收款码分享时，自动隐去真实金额字段',
    ts: 1742313600,
    date_str: '2026年3月23日',
  },
]

// --- 问候语工具 ---
export function getGreeting(username: string, pendingCount: number): string {
  const hour = new Date().getHours()
  const timeStr = hour < 11 ? '早上好' : hour < 18 ? '下午好' : '晚上好'
  if (pendingCount > 0) {
    return `${username}，系统有 ${pendingCount} 条新学习结果需要你确认`
  }
  return `${timeStr}，${username}`
}

// --- 所有可用 Tag 筛选 ---
export const ALL_SKILL_TAGS = ['微信', '支付宝', '钉钉', '飞书', '通用', '医疗记录', '手机号', '家庭住址', '工作内容', '收款信息']

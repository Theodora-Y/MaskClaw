/**
 * Local rule generation for Onboarding Step 3.
 * These are descriptive text rules generated from the user's Step1/2 choices.
 * NOT real Skill data — just human-readable previews shown during onboarding.
 */

const APP_RULE_TEMPLATES: Record<string, (sensitive: string[]) => string[]> = {
  '微信': (s) => [
    s.includes('手机号')
      ? '微信场景下，含手机号的消息发送给陌生人时将被拦截'
      : '微信场景下，敏感信息发送前需确认',
    '微信朋友圈截图中包含联系方式时将提示遮码',
  ],
  '支付宝': () => [
    '支付宝场景下，收款码展示操作直接放行',
    '支付宝表单中银行卡字段需二次确认后填写',
  ],
  '钉钉': (s) => [
    s.includes('工作内容')
      ? '钉钉日报/周报中涉及项目进展时，自动标记为工作内部内容'
      : '钉钉中含敏感信息的文件发送前需确认',
  ],
  '飞书': (s) => [
    s.includes('工作内容')
      ? '飞书文档中含工作内容标签时，限制外部分享'
      : '飞书中敏感附件发送前需确认',
  ],
  '抖音': () => [
    '抖音评论区中含个人联系方式时将被拦截提示',
  ],
  '小红书': () => [
    '小红书笔记发布前，扫描是否含个人位置信息',
  ],
  '淘宝/天猫': (s) => [
    s.includes('家庭住址')
      ? '淘宝收货地址自动填写时，需确认后提交'
      : '淘宝下单时地址字段需确认',
  ],
  '京东': (s) => [
    s.includes('银行卡')
      ? '京东支付时银行卡操作需二次确认'
      : '京东下单地址需确认后提交',
  ],
}

const SENSITIVE_RULE_TEMPLATES: Record<string, string> = {
  '手机号':     '任意场景下，手机号粘贴到陌生应用前需确认',
  '家庭住址':   '填写表单时，家庭住址字段需要你确认后才执行',
  '身份证':     '身份证号输入场景下，自动检测并提示是否确认提交',
  '银行卡':     '银行卡号在非支付场景下填写时，将触发警告提示',
  '医疗记录':   '医疗相关信息粘贴到社交平台时将被拦截',
  '工作内容':   '包含项目名称或工作文件的粘贴操作，将被标记为工作机密',
  '行程位置':   '位置信息分享给陌生联系人时将弹出确认',
  '收款信息':   '收款二维码仅在主动展示时放行，截图分享需确认',
  '家庭成员信息': '涉及家庭成员姓名/关系的文本，在陌生应用中将被提示',
  '工资收入':   '收入相关信息粘贴到社交平台时将被拦截',
}

export function generateRules(
  occupation: string,
  apps: string[],
  sensitiveFields: string[]
): string[] {
  const rules: string[] = []

  // App-based rules (max 2 apps)
  for (const app of apps.slice(0, 3)) {
    const gen = APP_RULE_TEMPLATES[app]
    if (gen) {
      const appRules = gen(sensitiveFields)
      rules.push(...appRules.slice(0, 1))
    }
  }

  // Sensitive field rules (max 2)
  for (const field of sensitiveFields.slice(0, 3)) {
    const rule = SENSITIVE_RULE_TEMPLATES[field]
    if (rule && !rules.includes(rule)) {
      rules.push(rule)
    }
  }

  // Occupation-specific fallback
  if (rules.length === 0) {
    rules.push(`基于你的职业「${occupation || '通用'}」，系统将为常见敏感字段开启保护`)
    rules.push('常用应用中的个人信息分享将触发二次确认')
    rules.push('粘贴含手机号或地址的文本到陌生应用时将被提示')
  }

  // Ensure 3-5 rules
  if (rules.length < 3) {
    rules.push('系统会在你使用过程中自动学习并补充更多规则')
  }

  return rules.slice(0, 5)
}

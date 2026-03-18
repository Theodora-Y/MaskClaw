# Confidence 计算策略

## 用途
衡量一组用户纠错日志是否足够可信、值得提炼成规则。
confidence 由脚本计算，不由 MiniCPM 输出。

## 触发条件
同一组 (user_id, action, app_context) 下：
- 有效纠正次数 >= 2 才进入计算
- 有效纠正 = correction_type 为 user_modified 或 user_interrupted
  且 correction_value != original_value

## 计算公式

confidence = count_score * 0.3
           + consistency_score * 0.3
           + strength_score * 0.2
           + validity_ratio * 0.2

### 信号1：count_score（有效次数）
count_score = min(有效纠正次数 / 5, 1.0)
2次 → 0.4，3次 → 0.6，5次及以上 → 1.0

### 信号2：consistency_score（纠正方向一致性）
取所有 correction_value 中出现最多的值，计算其占比。
例：3次都改成"公司地址" → 3/3 = 1.0
    2次"公司地址"1次"丰巢快递柜" → 2/3 = 0.67
全为 user_interrupted（无 correction_value）→ 固定 0.5

### 信号3：strength_score（行为强度）
strength_score = 0.7 + 0.3 * (interrupted次数 / 有效纠正总数)
全为 user_modified → 0.7
全为 user_interrupted → 1.0

### 信号4：validity_ratio（有效纠正占比）
validity_ratio = 有效纠正次数 / 该组全部记录数
防止"偶尔纠正"被误判为稳定偏好

## 阈值决策
confidence >= 0.6 → 进入 MiniCPM 提炼流程
confidence < 0.6  → 写入 candidate_rules_pending.jsonl，继续观察

## 示例
UserB 的 fill_home_address 在 forms_registration 场景下：
  记录1：user_modified，original=家庭住址，correction=公司地址
  记录2：user_modified，original=家庭住址，correction=公司地址
  记录3：user_interrupted，original=家庭住址，correction=null

  有效纠正：3条（original != correction 或 interrupted）
  count_score = 3/5 = 0.60
  consistency_score = 2/2 = 1.0（只有2条有值，都是公司地址）
  strength_score = 0.7 + 0.3*(1/3) = 0.80
  validity_ratio = 3/3 = 1.0

  confidence = 0.60*0.3 + 1.0*0.3 + 0.80*0.2 + 1.0*0.2
             = 0.18 + 0.30 + 0.16 + 0.20 = 0.84 ✅ 进入提炼流程
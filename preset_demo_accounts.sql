-- Demo accounts preset for maskclaw.db
-- Usage:
--   sqlite3 maskclaw.db < preset_demo_accounts.sql

INSERT OR IGNORE INTO users (
    user_id, username, email, password_hash,
    occupation, apps, sensitive_fields, onboarding_done, created_ts
) VALUES (
    'demo_UserA',
    '张医生',
    'demo_usera@maskclaw.dev',
    '$2b$12$o7PV9YEuUUx3uedyLJ0k1eWo0AKA6OFYaNEHBSeltzcFssMmJoRD2',
    '医疗顾问',
    '["微信","HIS系统","钉钉","支付宝"]',
    '["医疗记录","手机号","家庭住址","身份证"]',
    1,
    1700000000
);

INSERT OR IGNORE INTO users (
    user_id, username, email, password_hash,
    occupation, apps, sensitive_fields, onboarding_done, created_ts
) VALUES (
    'demo_UserB',
    '李主播',
    'demo_userb@maskclaw.dev',
    '$2b$12$1d1w8B9leTytrfsLiL2ZNelMg3X0XzpgOjDy5uafEjw27J9VfKy/q',
    '带货主播',
    '["微信","抖音","淘宝/天猫","支付宝","小红书"]',
    '["手机号","家庭住址","收款信息","行程位置"]',
    1,
    1700000000
);

INSERT OR IGNORE INTO users (
    user_id, username, email, password_hash,
    occupation, apps, sensitive_fields, onboarding_done, created_ts
) VALUES (
    'demo_UserC',
    '王明',
    'demo_userc@maskclaw.dev',
    '$2b$12$vwlVN52ESZWe9OP399G8NuCxzQXRuafXYym6zoH0Lp2.adODJSKzC',
    '普通职员',
    '["微信","支付宝","钉钉","京东"]',
    '["手机号","身份证","银行卡","家庭住址"]',
    1,
    1700000000
);

"""Skill registry package.

Tables:
- skills: L2 隐私规则版本管理
- session_trace: 会话轨迹重建（SOP 进化用）
- sop_draft: SOP 草稿（多轮迭代中）
- sop_version: 已发布的 SOP 版本
"""

from .skill_db import SkillDB

__all__ = ["SkillDB"]

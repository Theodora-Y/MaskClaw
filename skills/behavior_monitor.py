# skills/behavior_monitor.py
import time
import threading
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import queue

class SessionLogger:
    """Session 管理和持久化"""
    
    def __init__(self, base_dir: str = "logs"):
        self.base_dir = Path(base_dir)
        self.session_dir = None
        self.log_file = None
        self.screenshot_dir = None
        self._lock = threading.Lock()
        
    def create_session(self) -> str:
        """创建新的 session 文件夹"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.base_dir / f"session_{timestamp}"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        
        self.screenshot_dir = self.session_dir / "screenshots"
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_file = self.session_dir / "action_trace.jsonl"
        print(f"📁 Session 创建成功: {self.session_dir}")
        return str(self.session_dir)
    
    def write_log(self, entry: Dict[str, Any]):
        """线程安全的日志写入"""
        with self._lock:
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except Exception as e:
                print(f"❌ 日志写入失败: {e}")
    
    def save_screenshot(self, image_data: bytes, suffix: str = "") -> str:
        """保存截图"""
        if not self.screenshot_dir:
            return ""
        timestamp = datetime.now().strftime("%H%M%S_%f")
        filename = f"{timestamp}{suffix}.png"
        path = self.screenshot_dir / filename
        try:
            with open(path, "wb") as f:
                f.write(image_data)
            return str(path)
        except Exception as e:
            print(f"❌ 截图保存失败: {e}")
            return ""


class BehaviorMonitor:
    """
    全生命周期用户行为捕获与对抗审计
    """
    
    def __init__(self, device=None, base_dir: str = "logs"):
        self.device = device  # u2 实例，可选
        self.session = SessionLogger(base_dir)
        self.session.create_session()
        
        self.is_monitoring = True
        self.monitor_thread = None
        self._lock = threading.Lock()
        
        # 状态记录
        self.last_agent_action: Optional[Dict] = None
        self.conflict_logs: List[Dict] = []
        self.all_logs: List[Dict] = []
        
        # 事件队列，用于异步记录
        self.event_queue = queue.Queue()
        
    def register_agent_action(self, target_id: str, text: str, reason: str = "", 
                              action_type: str = "input", screenshot: bool = True):
        """
        Agent 行为登记
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "role": "Agent",
            "action": action_type,
            "target_id": target_id,
            "content": text,
            "reason": reason,
            "screenshot_path": ""
        }
        
        # 截图
        if screenshot and self.device:
            try:
                img = self.device.screenshot()
                if img:
                    entry["screenshot_path"] = self.session.save_screenshot(img, f"_agent_{action_type}")
            except Exception as e:
                print(f"⚠️ 截图失败: {e}")
        
        self.last_agent_action = {
            "entry": entry,
            "timestamp": time.time(),
            "target_id": target_id
        }
        
        self._log_event(entry)
        print(f"🤖 Agent 操作登记: {action_type} [{target_id}] <- {text}")
    
    def register_user_action(self, action: str, target_id: str = "", content: str = ""):
        """
        用户行为登记
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "role": "User",
            "action": action,
            "target_id": target_id,
            "content": content,
            "reason": "",
            "screenshot_path": ""
        }
        
        if self.device:
            try:
                img = self.device.screenshot()
                if img:
                    entry["screenshot_path"] = self.session.save_screenshot(img, f"_user_{action}")
            except Exception as e:
                pass
        
        self._log_event(entry)
        print(f"👤 User 操作登记: {action} [{target_id}] <- {content}")
        
        # 检查是否与 Agent 动作冲突
        self._check_conflict(entry)
    
    def register_system_event(self, event: str, details: str = ""):
        """系统事件登记"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "role": "System",
            "action": event,
            "target_id": "",
            "content": details,
            "reason": "",
            "screenshot_path": ""
        }
        self._log_event(entry)
        print(f"⚙️ System 事件: {event} - {details}")
    
    def _log_event(self, entry: Dict):
        """记录事件"""
        self.session.write_log(entry)
        with self._lock:
            self.all_logs.append(entry)
    
    def _check_conflict(self, user_entry: Dict):
        """冲突检测"""
        if not self.last_agent_action:
            return
            
        agent_entry = self.last_agent_action["entry"]
        agent_time = self.last_agent_action["timestamp"]
        user_time = datetime.fromisoformat(user_entry["timestamp"]).timestamp()
        
        # 5秒窗口内检测冲突
        if user_time - agent_time <= 5.0:
            conflict = {
                "timestamp": datetime.now().isoformat(),
                "agent_action": agent_entry,
                "user_action": user_entry,
                "time_diff_seconds": user_time - agent_time,
                "is_conflict": True
            }
            with self._lock:
                self.conflict_logs.append(conflict)
            print(f"⚠️ 检测到冲突! Agent {agent_entry['action']} 后用户 {user_entry['action']}")
    
    def analyze_conflicts(self) -> List[Dict]:
        """
        冲突分析 - 使用内置分析器进行深度分析
        """
        analysis_results = []
        
        for conflict in self.conflict_logs:
            result = ConflictAnalyzer().analyze(
                agent_logs=[conflict["agent_action"]],
                user_logs=[conflict["user_action"]],
                ui_context=""
            )
            analysis_results.append({
                "conflict": conflict,
                "analysis": result
            })
        
        return analysis_results
    
    def _monitor_loop(self):
        """后台监控线程"""
        while self.is_monitoring:
            try:
                if self.device:
                    # 监控当前 App
                    try:
                        current = self.device.app_current()
                        pkg = current.get("package", "")
                        if pkg:
                            self.register_system_event("app_foreground", pkg)
                    except:
                        pass
            except Exception as e:
                print(f"⚠️ 监控异常: {e}")
            
            time.sleep(2)
    
    def start(self):
        """启动监控"""
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("🔔 BehaviorMonitor 已启动")
    
    def stop(self):
        """停止监控"""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        print("🛑 BehaviorMonitor 已停止")
    
    def get_logs(self) -> List[Dict]:
        """获取所有日志"""
        with self._lock:
            return self.all_logs.copy()
    
    def get_conflicts(self) -> List[Dict]:
        """获取冲突日志"""
        with self._lock:
            return self.conflict_logs.copy()


class ConflictAnalyzer:
    """冲突分析器 - 使用 LLM 分析对抗性交互"""
    
    def __init__(self):
        pass
    
    def analyze(self, agent_logs: List[Dict], user_logs: List[Dict], 
               ui_screenshot_desc: str = "") -> Dict:
        """
        分析冲突类型
        """
        # 构建分析 prompt
        agent_str = "\n".join([
            f"- {log.get('action')} {log.get('target_id')}: {log.get('content')}"
            for log in agent_logs
        ])
        user_str = "\n".join([
            f"- {log.get('action')} {log.get('target_id')}: {log.get('content')}"
            for log in user_logs
        ])
        
        # 简化分析逻辑
        user_action = user_logs[0].get("action", "") if user_logs else ""
        content = user_logs[0].get("content", "") if user_logs else ""
        
        # 意图冲突检测
        is_conflict = user_action in ["delete", "clear", "undo", "back", "cancel"]
        
        # 敏感信息检测
        sensitive_keywords = ["密码", "账号", "手机", "身份证", "银行卡", "地址", "姓名"]
        is_sensitive = any(kw in content for kw in sensitive_keywords)
        
        if is_conflict:
            if is_sensitive:
                conflict_type = "PRIVACY_CONCERN"
                confidence = 0.85
                should_update_rag = True
            else:
                conflict_type = "ACCURACY_ERROR"
                confidence = 0.7
                should_update_rag = False
        else:
            conflict_type = "SYSTEM_FLOW"
            confidence = 0.5
            should_update_rag = False
        
        return {
            "is_conflict": is_conflict,
            "conflict_type": conflict_type,
            "confidence_score": confidence,
            "explanation": f"用户执行了 '{user_action}'，疑似{'隐私担忧' if is_sensitive else '操作纠正'}",
            "should_update_rag": should_update_rag
        }


# --- 使用示例 ---
if __name__ == "__main__":
    # 模拟使用
    monitor = BehaviorMonitor(device=None, base_dir="logs")
    monitor.start()
    
    # 模拟 Agent 操作
    monitor.register_agent_action(
        target_id="com.app:id/address_input",
        text="北京市海淀区二月里小区三栋",
        reason="用户要求填写收货地址",
        action_type="input"
    )
    
    time.sleep(1)
    
    # 模拟用户纠错
    monitor.register_user_action(
        action="clear",
        target_id="com.app:id/address_input",
        content=""
    )
    
    time.sleep(2)
    
    # 分析冲突
    conflicts = monitor.get_conflicts()
    print(f"\n共检测到 {len(conflicts)} 个冲突")
    
    # 停止监控
    monitor.stop()

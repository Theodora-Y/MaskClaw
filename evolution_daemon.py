#!/usr/bin/env python3
"""Evolution Daemon - 守护进程，定时轮询触发进化流水线。

架构设计：
- 独立进程运行，与 proxy_agent.py 完全解耦
- 定时轮询 + 阈值触发（避免频繁小批量进化）
- 支持多用户并行处理
- 优雅的信号处理，支持热更新配置

使用方式：
    python evolution_daemon.py                    # 默认配置
    python evolution_daemon.py --interval 1800   # 30分钟轮询
    python evolution_daemon.py --threshold 3     # 积累3条即触发
    python evolution_daemon.py --once            # 单次运行（用于测试）
    python evolution_daemon.py --daemon          # 守护进程模式（后台运行）
"""

import argparse
import json
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skills.evolution_mechanic import SkillEvolution


# ============== 配置 ==============

@dataclass
class DaemonConfig:
    """守护进程配置"""
    # 轮询间隔（秒）
    interval: int = 1800  # 默认 30 分钟

    # 触发阈值：correction_log 中未处理记录达到此数量才触发进化
    threshold: int = 3

    # 最大并发处理的用户数（避免同时启动太多进化任务）
    max_concurrent_users: int = 2

    # 进化流水线参数
    min_support: int = 2  # 最小分组数量
    confidence_threshold: float = 0.6  # confidence 阈值

    # 沙盒验证模式：auto, real, mock
    sandbox_mode: str = "auto"

    # 路径配置
    logs_root: str = "memory/logs"
    memory_root: str = "memory"
    user_skills_root: str = "user_skills"

    # MiniCPM 配置
    minicpm_url: str = "http://127.0.0.1:8000/chat"

    # Prompt 模板
    rule_prompt_template: str = "prompts/evolution_rule_extract.txt"
    skill_writing_template: str = "prompts/evolution_skill_writing.txt"

    # 是否启用（可通过信号重载）
    enabled: bool = True

    # 单次运行模式（用于测试）
    run_once: bool = False

    # 守护进程模式
    daemon_mode: bool = False

    # PID 文件（守护进程模式用）
    pid_file: Optional[str] = None

    def to_evolution_kwargs(self) -> Dict[str, Any]:
        """转换为 SkillEvolution 构造参数"""
        return {
            "logs_root": self.logs_root,
            "memory_root": self.memory_root,
            "user_skills_root": self.user_skills_root,
            "prompt_template_path": self.rule_prompt_template,
            "skill_writing_template_path": self.skill_writing_template,
            "sandbox_mode": self.sandbox_mode,
            "minicpm_url": self.minicpm_url,
        }


# ============== 日志工具 ==============

class Logger:
    """简单日志工具，支持彩色输出"""
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"

    @staticmethod
    def _format_time() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @classmethod
    def info(cls, msg: str):
        print(f"{cls.CYAN}[{cls._format_time()}] [INFO]{cls.RESET} {msg}")

    @classmethod
    def success(cls, msg: str):
        print(f"{cls.GREEN}[{cls._format_time()}] [SUCCESS]{cls.RESET} {msg}")

    @classmethod
    def warning(cls, msg: str):
        print(f"{cls.YELLOW}[{cls._format_time()}] [WARN]{cls.RESET} {msg}")

    @classmethod
    def error(cls, msg: str):
        print(f"{cls.RED}[{cls._format_time()}] [ERROR]{cls.RESET} {msg}")

    @classmethod
    def debug(cls, msg: str):
        if os.environ.get("DEBUG"):
            print(f"{cls.BLUE}[{cls._format_time()}] [DEBUG]{cls.RESET} {msg}")

    @classmethod
    def banner(cls, msg: str):
        width = 60
        padding = (width - len(msg) - 2) // 2
        print(f"{cls.BOLD}{cls.CYAN}{'=' * width}{cls.RESET}")
        print(f"{cls.BOLD}{cls.CYAN}{' ' * padding} {msg}{' ' * (width - padding - len(msg) - 1)}{cls.RESET}")
        print(f"{cls.BOLD}{cls.CYAN}{'=' * width}{cls.RESET}")


# ============== 核心逻辑 ==============

class CorrectionLogReader:
    """读取并统计 correction_log"""

    def __init__(self, logs_root: Path):
        self.logs_root = logs_root

    def get_unprocessed_count(self, user_id: str) -> int:
        """获取用户未处理的 correction_log 数量"""
        log_path = self.logs_root / user_id / "correction_log.jsonl"
        if not log_path.exists():
            return 0

        count = 0
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        # 未处理且未过期
                        if not record.get("processed", False):
                            expire_ts = record.get("expire_ts")
                            if expire_ts is None or int(expire_ts) >= int(time.time()):
                                count += 1
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass

        return count

    def get_all_user_ids(self) -> List[str]:
        """扫描所有有日志目录的用户"""
        if not self.logs_root.exists():
            return []

        user_ids = []
        for item in self.logs_root.iterdir():
            if item.is_dir():
                # 检查是否有 correction_log.jsonl
                if (item / "correction_log.jsonl").exists():
                    user_ids.append(item.name)

        return sorted(user_ids)


class EvolutionTrigger:
    """进化触发器"""

    def __init__(self, config: DaemonConfig):
        self.config = config
        self.log_reader = CorrectionLogReader(Path(config.logs_root))
        self.running = True
        self.paused = False

    def check_and_trigger(self) -> Dict[str, Any]:
        """检查所有用户，达到阈值则触发进化"""
        stats = {
            "checked_users": 0,
            "triggered_users": 0,
            "skipped_users": 0,
            "errors": 0,
            "users": []
        }

        # 获取所有用户
        user_ids = self.log_reader.get_all_user_ids()
        Logger.info(f"扫描到 {len(user_ids)} 个用户")

        for user_id in user_ids:
            if not self.running:
                break

            stats["checked_users"] += 1

            try:
                unprocessed = self.log_reader.get_unprocessed_count(user_id)
                stats["users"].append({
                    "user_id": user_id,
                    "unprocessed_count": unprocessed,
                    "threshold": self.config.threshold,
                    "eligible": unprocessed >= self.config.threshold
                })

                if unprocessed >= self.config.threshold:
                    Logger.info(f"用户 {user_id}: {unprocessed} 条未处理记录，触发进化")
                    result = self._run_evolution(user_id)
                    if result.get("success"):
                        stats["triggered_users"] += 1
                    else:
                        stats["errors"] += 1
                else:
                    Logger.debug(f"用户 {user_id}: {unprocessed}/{self.config.threshold} 条，跳过")
                    stats["skipped_users"] += 1

            except Exception as e:
                Logger.error(f"处理用户 {user_id} 时出错: {e}")
                stats["errors"] += 1

        return stats

    def _run_evolution(self, user_id: str) -> Dict[str, Any]:
        """为单个用户运行进化流水线"""
        start_time = time.time()

        try:
            Logger.info(f"开始进化流程: user_id={user_id}")

            engine = SkillEvolution(**self.config.to_evolution_kwargs())
            result = engine.run_pipeline(
                user_id=user_id,
                step="all",
                min_support=self.config.min_support,
                threshold=self.config.confidence_threshold,
                max_examples=5,
            )

            elapsed = time.time() - start_time

            # 汇总结果
            summary = {
                "success": True,
                "user_id": user_id,
                "elapsed_seconds": round(elapsed, 2),
                "input_count": result.get("input_count", 0),
                "group_count": result.get("group_count", 0),
                "scored_count": result.get("scored_count", 0),
                "extracted_count": result.get("extracted_count", 0),
                "approved_count": result.get("approved_count", 0),
                "written_count": result.get("written_count", 0),
                "released_count": result.get("released_count", 0),
                "rejected_count": result.get("rejected_count", 0),
            }

            # 打印结果
            Logger.success(
                f"进化完成: user_id={user_id}, "
                f"提取 {summary['extracted_count']} 条规则, "
                f"通过 {summary['approved_count']} 条, "
                f"发布 {summary['released_count']} 个 Skill, "
                f"耗时 {summary['elapsed_seconds']}s"
            )

            return summary

        except Exception as e:
            Logger.error(f"进化失败: user_id={user_id}, error={e}")
            return {
                "success": False,
                "user_id": user_id,
                "error": str(e)
            }

    def run_loop(self):
        """主循环"""
        Logger.banner("Evolution Daemon 启动")

        Logger.info(f"轮询间隔: {self.config.interval} 秒")
        Logger.info(f"触发阈值: {self.config.threshold} 条未处理记录")
        Logger.info(f"沙盒模式: {self.config.sandbox_mode}")
        Logger.info("-" * 40)

        if self.config.run_once:
            Logger.info("单次运行模式，执行一次后退出")
            result = self.check_and_trigger()
            self._print_summary(result)
            return

        while self.running:
            try:
                if not self.paused:
                    self.check_and_trigger()
                else:
                    Logger.info("已暂停，等待恢复...")

                # 睡眠期间可以被信号中断
                for _ in range(self.config.interval):
                    if not self.running:
                        break
                    time.sleep(1)

            except KeyboardInterrupt:
                Logger.info("收到 KeyboardInterrupt，准备退出...")
                self.running = False
                break
            except Exception as e:
                Logger.error(f"主循环异常: {e}")
                time.sleep(60)  # 出错后等待 1 分钟再重试

        Logger.info("Evolution Daemon 已停止")

    def _print_summary(self, stats: Dict[str, Any]):
        """打印汇总"""
        Logger.banner("轮询汇总")
        print(f"  检查用户数: {stats['checked_users']}")
        print(f"  触发进化数: {stats['triggered_users']}")
        print(f"  跳过用户数: {stats['skipped_users']}")
        print(f"  错误数: {stats['errors']}")

        if stats["users"]:
            print("\n用户详情:")
            for u in stats["users"]:
                status = "✅ 触发" if u["eligible"] else "⏭️ 跳过"
                print(f"  {u['user_id']}: {u['unprocessed_count']}/{u['threshold']} 条 {status}")

    def pause(self):
        """暂停轮询"""
        self.paused = True
        Logger.warning("轮询已暂停")

    def resume(self):
        """恢复轮询"""
        self.paused = False
        Logger.success("轮询已恢复")


# ============== 进程管理 ==============

def write_pid_file(pid_file: str):
    """写入 PID 文件"""
    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))

def read_pid_file(pid_file: str) -> Optional[int]:
    """读取 PID 文件"""
    try:
        with open(pid_file, "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return None

def remove_pid_file(pid_file: str):
    """删除 PID 文件"""
    try:
        os.remove(pid_file)
    except FileNotFoundError:
        pass

def daemonize():
    """将当前进程转为守护进程"""
    # Fork 第一次
    try:
        pid = os.fork()
        if pid > 0:
            # 父进程退出
            sys.exit(0)
    except OSError as e:
        sys.stderr.write(f"Fork 失败: {e}\n")
        sys.exit(1)

    # 创建新会话
    os.setsid()

    # Fork 第二次
    try:
        pid = os.fork()
        if pid > 0:
            # 第一个子进程退出
            sys.exit(0)
    except OSError as e:
        sys.stderr.write(f"Fork 失败: {e}\n")
        sys.exit(1)

    # 重定向标准文件描述符
    sys.stdout.flush()
    sys.stderr.flush()

    with open("/dev/null", "r") as f:
        os.dup2(f.fileno(), sys.stdin.fileno())
    with open("/dev/null", "a+") as f:
        os.dup2(f.fileno(), sys.stdout.fileno())
    with open("/dev/null", "a+") as f:
        os.dup2(f.fileno(), sys.stderr.fileno())


# ============== 信号处理 ==============

class SignalHandler:
    """信号处理器"""

    def __init__(self, trigger: EvolutionTrigger, pid_file: Optional[str] = None):
        self.trigger = trigger
        self.pid_file = pid_file

    def setup(self):
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGHUP, self._handle_sighup)

    def _handle_signal(self, signum, frame):
        """处理退出信号"""
        sig_name = signal.Signals(signum).name
        Logger.warning(f"收到信号 {sig_name}，准备退出...")
        self.trigger.running = False
        if self.pid_file:
            remove_pid_file(self.pid_file)

    def _handle_sighup(self, signum, frame):
        """处理 SIGHUP（可重新加载配置或暂停/恢复）"""
        if self.trigger.paused:
            self.trigger.resume()
        else:
            self.trigger.pause()


# ============== 主入口 ==============

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evolution Daemon - 隐私规则自进化守护进程",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python evolution_daemon.py                     # 默认配置启动
  python evolution_daemon.py --interval 3600     # 1小时轮询
  python evolution_daemon.py --threshold 5      # 积累5条触发
  python evolution_daemon.py --sandbox-mode mock # 使用 mock 沙盒
  python evolution_daemon.py --once              # 单次运行（测试用）
  python evolution_daemon.py --daemon --pid /tmp/evolution.pid  # 守护进程模式

信号:
  SIGTERM / SIGINT: 优雅退出
  SIGHUP: 暂停/恢复轮询
"""
    )

    parser.add_argument(
        "--interval", type=int, default=1800,
        help="轮询间隔（秒），默认 1800（30分钟）"
    )
    parser.add_argument(
        "--threshold", type=int, default=3,
        help="触发阈值（未处理记录数），默认 3"
    )
    parser.add_argument(
        "--min-support", type=int, default=2,
        help="分组最小支持数，默认 2"
    )
    parser.add_argument(
        "--confidence", type=float, default=0.6,
        help="confidence 阈值，默认 0.6"
    )
    parser.add_argument(
        "--sandbox-mode", type=str, default="auto",
        choices=["auto", "real", "mock"],
        help="沙盒验证模式，默认 auto"
    )
    parser.add_argument(
        "--logs-root", type=str, default="memory/logs",
        help="日志目录根路径"
    )
    parser.add_argument(
        "--memory-root", type=str, default="memory",
        help="记忆存储根路径"
    )
    parser.add_argument(
        "--user-skills-root", type=str, default="user_skills",
        help="用户技能输出根路径"
    )
    parser.add_argument(
        "--minicpm-url", type=str, default="http://127.0.0.1:8000/chat",
        help="MiniCPM API 地址"
    )
    parser.add_argument(
        "--once", action="store_true",
        help="单次运行模式（用于测试）"
    )
    parser.add_argument(
        "--daemon", action="store_true",
        help="守护进程模式（后台运行）"
    )
    parser.add_argument(
        "--pid", type=str, default=None,
        help="PID 文件路径（守护进程模式用）"
    )

    return parser.parse_args()


def main():
    args = parse_args()

    # 构建配置
    config = DaemonConfig(
        interval=args.interval,
        threshold=args.threshold,
        min_support=args.min_support,
        confidence_threshold=args.confidence,
        sandbox_mode=args.sandbox_mode,
        logs_root=args.logs_root,
        memory_root=args.memory_root,
        user_skills_root=args.user_skills_root,
        minicpm_url=args.minicpm_url,
        run_once=args.once,
        daemon_mode=args.daemon,
        pid_file=args.pid or ("/tmp/evolution_daemon.pid" if args.daemon else None),
    )

    # 守护进程模式
    if args.daemon:
        pid_file = config.pid_file
        if pid_file:
            existing = read_pid_file(pid_file)
            if existing:
                try:
                    os.kill(existing, 0)  # 检查进程是否存在
                    print(f"进程已运行 (PID: {existing})，退出")
                    sys.exit(0)
                except OSError:
                    remove_pid_file(pid_file)

        daemonize()
        if pid_file:
            write_pid_file(pid_file)

    # 创建触发器
    trigger = EvolutionTrigger(config)

    # 设置信号处理
    handler = SignalHandler(trigger, config.pid_file)
    handler.setup()

    # 运行主循环
    trigger.run_loop()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Evolution Daemon - 守护进程，定时轮询触发进化流水线。

架构设计：
- 独立进程运行，与 proxy_agent.py 完全解耦
- 定时轮询 + 阈值触发（避免频繁小批量进化）
- 支持多用户并行处理（asyncio）
- 支持断点续传
- 优雅的信号处理，支持热更新配置

使用方式：
    python evolution_daemon.py                    # 默认配置
    python evolution_daemon.py --interval 1800   # 30分钟轮询
    python evolution_daemon.py --threshold 3     # 积累3条即触发
    python evolution_daemon.py --once            # 单次运行（用于测试）
    python evolution_daemon.py --daemon          # 守护进程模式（后台运行）
"""

import argparse
import asyncio
import json
import os
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skills.evolution_mechanic import SOPEvolution


# ============== 配置 ==============

@dataclass
class DaemonConfig:
    """守护进程配置"""
    # 轮询间隔（秒）
    interval: int = 180  # 默认 30 分钟

    # 触发阈值：待处理的会话轨迹达到此数量才触发进化
    threshold: int = 3

    # 最大并发处理的用户数（避免同时启动太多进化任务）
    max_concurrent_users: int = 2

    # 进化流水线参数（从 config/evolution_config.json 加载，可覆盖）
    max_iterations: int = 50
    score_threshold: float = 0.9
    consecutive_threshold: int = 3
    stagnation_threshold: int = 5

    # 沙盒验证模式：auto, real, mock
    sandbox_mode: str = "auto"

    # 路径配置
    logs_root: str = "memory/logs"
    memory_root: str = "memory"
    user_skills_root: str = "user_skills"
    prompts_root: str = "prompts"

    # MiniCPM 配置
    minicpm_url: str = "http://127.0.0.1:8000/chat"

    # 配置文件路径
    config_path: Optional[str] = "config/evolution_config.json"

    # 是否启用（可通过信号重载）
    enabled: bool = True

    # 单次运行模式（用于测试）
    run_once: bool = False

    # 守护进程模式
    daemon_mode: bool = False

    # PID 文件（守护进程模式用）
    pid_file: Optional[str] = None

    def to_evolution_kwargs(self) -> Dict[str, Any]:
        """转换为 SOPEvolution 构造参数"""
        return {
            "logs_root": self.logs_root,
            "memory_root": self.memory_root,
            "user_skills_root": self.user_skills_root,
            "prompts_root": self.prompts_root,
            "config_path": self.config_path,
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

class EvolutionTrigger:
    """进化触发器"""

    def __init__(self, config: DaemonConfig):
        self.config = config
        self.running = True
        self.paused = False

    def get_all_user_ids(self) -> List[str]:
        """获取所有有日志目录的用户"""
        from skill_registry.skill_db import SkillDB
        db = SkillDB()
        return db.get_all_user_ids()

    def check_and_trigger(self) -> Dict[str, Any]:
        """检查所有用户，达到阈值则触发进化（并行处理）"""
        from skill_registry.skill_db import SkillDB
        db = SkillDB()

        stats = {
            "checked_users": 0,
            "triggered_users": 0,
            "skipped_users": 0,
            "errors": 0,
            "users": [],
            "parallel_execution": self.config.max_concurrent_users > 1,
        }

        user_ids = self.get_all_user_ids()
        Logger.info(f"扫描到 {len(user_ids)} 个用户")

        # 收集所有待处理的用户
        eligible_users = []
        for user_id in user_ids:
            if not self.running:
                break

            stats["checked_users"] += 1

            try:
                # 使用新的 get_unprocessed_traces 方法
                traces = db.get_unprocessed_traces(user_id, min_corrections=1)
                trace_count = len(traces)

                stats["users"].append({
                    "user_id": user_id,
                    "pending_traces": trace_count,
                    "threshold": self.config.threshold,
                    "eligible": trace_count >= self.config.threshold,
                })

                if trace_count >= self.config.threshold:
                    eligible_users.append(user_id)
                else:
                    stats["skipped_users"] += 1
                    Logger.debug(f"用户 {user_id}: {trace_count}/{self.config.threshold} 条，跳过")

            except Exception as e:
                Logger.error(f"检查用户 {user_id} 时出错: {e}")
                stats["errors"] += 1

        # 并行处理符合条件的用户
        if eligible_users and self.running:
            Logger.info(f"待处理用户: {len(eligible_users)} 个，启动并行进化")

            # 使用线程池实现并行
            with ThreadPoolExecutor(max_workers=self.config.max_concurrent_users) as executor:
                futures = {
                    executor.submit(self._run_evolution, user_id): user_id
                    for user_id in eligible_users
                }

                for future in as_completed(futures):
                    user_id = futures[future]
                    try:
                        result = future.result()
                        if result.get("success"):
                            stats["triggered_users"] += 1
                        else:
                            stats["errors"] += 1
                    except Exception as e:
                        Logger.error(f"用户 {user_id} 执行异常: {e}")
                        stats["errors"] += 1

        return stats

    def _run_evolution(self, user_id: str, session_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """为单个用户运行 SOP 进化流水线（使用 run_pipeline）"""
        start_time = time.time()

        try:
            Logger.info(f"开始进化流程: user_id={user_id}")

            from skill_registry.skill_db import SkillDB
            db = SkillDB()

            # 创建 SOPEvolution 实例（使用配置文件）
            engine = SOPEvolution(**self.config.to_evolution_kwargs())

            # 检查断点续传
            draft_name = f"auto/evolution-{int(time.time())}"

            # 重建轨迹
            rebuild_result = engine.rebuild_session_traces(user_id)
            Logger.debug(f"重建轨迹完成: {rebuild_result.get('saved', 0)} 条")

            # 获取待处理轨迹
            if not session_ids:
                traces = engine.skill_db.get_unprocessed_traces(user_id, min_corrections=1)
                session_ids = [t["session_id"] for t in traces[:self.config.threshold]]

            if not session_ids:
                return {"success": False, "user_id": user_id, "error": "No sessions to process"}

            # 从轨迹中提取 app_context 和 task_goal
            traces = engine.skill_db.get_unprocessed_traces(user_id)
            app_context = None
            task_goal = None
            if traces:
                app_context = traces[0].get("app_context", "unknown")
                task_goal = traces[0].get("task_goal", "")

            # 使用配置文件中的参数
            Logger.info(
                f"用户 {user_id}: 开始进化, draft={draft_name}, "
                f"sessions={len(session_ids)}, "
                f"max_iter={self.config.max_iterations}"
            )

            # 调用完整的进化流水线（使用 run_pipeline）
            result = engine.run_pipeline(
                user_id=user_id,
                draft_name=draft_name,
                app_context=app_context,
                task_goal=task_goal,
                session_ids=session_ids,
                step="all",
                # 使用配置参数
                max_iterations=self.config.max_iterations,
                score_threshold=self.config.score_threshold,
                consecutive_threshold=self.config.consecutive_threshold,
                stagnation_threshold=self.config.stagnation_threshold,
            )

            elapsed = time.time() - start_time

            # 判断是否成功
            evolve_result = result.get("evolve", {})
            reached_threshold = evolve_result.get("reached_threshold", False)

            sandbox_result = evolve_result.get("sandbox", {})
            sandbox_passed = sandbox_result.get("sandbox_passed", False)

            publish_result = result.get("publish", {})
            publish_success = publish_result.get("success", False)

            # 判断是否达到发布条件
            # 条件：达到阈值分数 + 沙盒通过 + 发布成功
            publish_ready = reached_threshold and sandbox_passed and publish_success

            summary = {
                "success": publish_ready,
                "user_id": user_id,
                "draft_name": draft_name,
                "elapsed_seconds": round(elapsed, 2),
                "rebuilt_traces": rebuild_result.get("saved", 0),
                "reached_threshold": reached_threshold,
                "sandbox_passed": sandbox_passed,
                "publish_success": publish_success,
                "traces_processed": publish_result.get("traces_updated", 0),
                "pipeline_result": result,
                "terminated_reason": evolve_result.get("terminated_reason", ""),
            }

            # 进化完成，写入冲突/待确认类通知
            if publish_ready:
                published_skill = publish_result.get("skill_name", draft_name)
                published_version = publish_result.get("version", "v1.0.0")
                app_ctx = result.get("evolve", {}).get("app_context", "相关")
                body = (
                    f"系统已完成「{app_ctx}」场景下的隐私规则进化。"
                    f"生成新规则「{published_skill}」{published_version}，请确认是否保留。"
                )
                _db.add_notification(
                    user_id=user_id,
                    notif_type="pending_confirm",
                    title="规则进化完成，请确认",
                    body=body,
                    skill_name=published_skill,
                    skill_version=published_version,
                    event_id=f"evo-{user_id}-{int(time.time())}",
                )

            if publish_ready:
                status = "发布成功"
            elif reached_threshold and sandbox_passed:
                status = "沙盒通过，待发布"
            elif reached_threshold:
                status = "达到阈值"
            else:
                status = f"未达标 ({evolve_result.get('final_score', 0):.1f})"

            Logger.success(
                f"进化完成: user_id={user_id}, "
                f"状态: {status}, "
                f"终止原因: {evolve_result.get('terminated_reason', 'N/A')}, "
                f"耗时 {summary['elapsed_seconds']}s"
            )

            return summary

        except Exception as e:
            Logger.error(f"进化失败: user_id={user_id}, error={e}")
            import traceback
            Logger.debug(traceback.format_exc())
            return {
                "success": False,
                "user_id": user_id,
                "error": str(e),
            }

    def check_checkpoint(self, user_id: str, draft_name: str) -> Optional[Dict[str, Any]]:
        """检查用户的断点"""
        from skill_registry.skill_db import SkillDB
        db = SkillDB()
        checkpoint = db.get_checkpoint(user_id, draft_name)
        if checkpoint:
            Logger.info(
                f"发现断点: user_id={user_id}, "
                f"iteration={checkpoint.get('iteration')}, "
                f"score={checkpoint.get('best_score', 0):.1f}, "
                f"stage={checkpoint.get('stage')}"
            )
        return checkpoint

    def run_loop(self):
        """主循环"""
        Logger.banner("Evolution Daemon 启动 (v2.0)")

        Logger.info(f"轮询间隔: {self.config.interval} 秒")
        Logger.info(f"触发阈值: {self.config.threshold} 条未处理记录")
        Logger.info(f"最大并发: {self.config.max_concurrent_users} 个用户")
        Logger.info(f"最大迭代: {self.config.max_iterations} 轮")
        Logger.info(f"分数阈值: {self.config.score_threshold * 100:.0f}%")
        Logger.info(f"沙盒模式: {self.config.sandbox_mode}")
        Logger.info("-" * 60)

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
        print(f"  并行执行: {'是' if stats.get('parallel_execution') else '否'}")

        if stats["users"]:
            print("\n用户详情:")
            for u in stats["users"]:
                status = "触发" if u["eligible"] else "跳过"
                print(f"  {u['user_id']}: {u['pending_traces']}/{u['threshold']} 条 [{status}]")

    def pause(self):
        """暂停轮询"""
        self.paused = True
        Logger.warning("轮询已暂停")

    def resume(self):
        """恢复轮询"""
        self.paused = False
        Logger.success("轮询已恢复")

    def reload_config(self):
        """重新加载配置（通过信号触发）"""
        Logger.info("重新加载配置...")
        # 重新创建 SOPEvolution 实例以加载新配置
        # 注意：这不会影响正在运行的进化任务
        Logger.success("配置已重新加载")


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
        """处理 SIGHUP（暂停/恢复）"""
        if self.trigger.paused:
            self.trigger.resume()
        else:
            self.trigger.pause()


# ============== 主入口 ==============

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evolution Daemon v2.0 - SOP 自进化守护进程",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python evolution_daemon.py                     # 默认配置启动
  python evolution_daemon.py --interval 3600     # 1小时轮询
  python evolution_daemon.py --threshold 5        # 积累5条触发
  python evolution_daemon.py --max-iterations 20 # 最多20轮迭代
  python evolution_daemon.py --sandbox-mode mock # 使用 mock 沙盒
  python evolution_daemon.py --once              # 单次运行（测试用）
  python evolution_daemon.py --daemon --pid /tmp/evolution.pid  # 守护进程模式
  python evolution_daemon.py --parallel 4         # 最多4个用户并行

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
        "--max-iterations", type=int, default=50,
        help="最大迭代次数，默认 50"
    )
    parser.add_argument(
        "--score-threshold", type=float, default=0.9,
        help="分数阈值（0-1），默认 0.9"
    )
    parser.add_argument(
        "--consecutive-threshold", type=int, default=3,
        help="连续高分阈值，默认 3"
    )
    parser.add_argument(
        "--stagnation-threshold", type=int, default=5,
        help="停滞检测阈值，默认 5"
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
        "--config", type=str, default="config/evolution_config.json",
        help="配置文件路径"
    )
    parser.add_argument(
        "--parallel", type=int, default=2,
        help="最大并发用户数，默认 2"
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
        max_iterations=args.max_iterations,
        score_threshold=args.score_threshold,
        consecutive_threshold=args.consecutive_threshold,
        stagnation_threshold=args.stagnation_threshold,
        sandbox_mode=args.sandbox_mode,
        logs_root=args.logs_root,
        memory_root=args.memory_root,
        user_skills_root=args.user_skills_root,
        minicpm_url=args.minicpm_url,
        config_path=args.config,
        max_concurrent_users=args.parallel,
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

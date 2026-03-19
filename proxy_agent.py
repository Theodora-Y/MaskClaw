# proxy_agent.py - 隐私保护前置代理（核心骨架）
# 串联：Hook拦截 + Self-RAG检索 + MiniCPM分析 + SmartMasker打码 + ChromaDB存储 + 云端转发

import os
import sys
import json
import base64
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
from io import BytesIO
from PIL import Image

# ============== 路径配置 ==============
PROJECT_ROOT = Path(__file__).parent
PROMPTS_DIR = PROJECT_ROOT / "prompts"
MEMORY_DIR = PROJECT_ROOT / "memory"
CHROMA_STORAGE_DIR = MEMORY_DIR / "chroma_storage"
TEMP_DIR = PROJECT_ROOT / "temp"
SKILLS_DIR = PROJECT_ROOT / "skills"
MODEL_SERVER_DIR = PROJECT_ROOT / "model_server"

# 创建必要目录
PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
MEMORY_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# ============== 基础设施（文件/编码/临时文件） ==============

def guess_mime_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in [".jpg", ".jpeg"]:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    return "application/octet-stream"


def safe_suffix(filename: str, default: str = ".jpg") -> str:
    suffix = Path(filename).suffix
    if not suffix or len(suffix) > 10:
        return default
    return suffix


class TempFileManager:
    def __init__(self, temp_dir: Path = TEMP_DIR):
        self._temp_dir = temp_dir
        self._paths: List[Path] = []

    def write_bytes(self, content: bytes, suffix: str) -> Path:
        name = f"tmp_{os.urandom(8).hex()}{suffix}"
        p = self._temp_dir / name
        p.write_bytes(content)
        self._paths.append(p)
        return p

    def cleanup(self) -> None:
        for p in self._paths:
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass
        self._paths.clear()


class SafeScreenshot:
    """与 Open-AutoGLM 的 Screenshot 最小兼容结构。"""

    def __init__(self, base64_data: str, width: int, height: int):
        self.base64_data = base64_data
        self.width = width
        self.height = height
        # 隐私元数据（供 Open-AutoGLM 读取）
        self.privacy_metadata: Optional[Dict[str, Any]] = None


class ProcessResult:
    def __init__(
        self,
        *,
        screenshot: SafeScreenshot,
        masked_image_bytes: bytes,
        masked_mime_type: str,
        matched_rules: List[Dict[str, Any]],
        analysis: Dict[str, Any],
        masked_count: int,
    ):
        self.screenshot = screenshot
        self.masked_image_bytes = masked_image_bytes
        self.masked_mime_type = masked_mime_type
        self.matched_rules = matched_rules
        self.analysis = analysis
        self.masked_count = masked_count

# ============== Prompt 加载器 ==============
class PromptLoader:
    """加载 Prompt 模板"""
    
    def __init__(self, prompts_dir: Path = PROMPTS_DIR):
        self.prompts_dir = prompts_dir
        self._cache = {}
    
    def load(self, prompt_name: str) -> str:
        """加载指定名称的 Prompt 文件"""
        if prompt_name in self._cache:
            return self._cache[prompt_name]
        
        prompt_path = self.prompts_dir / f"{prompt_name}.txt"
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt 文件不存在: {prompt_path}")
        
        with open(prompt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        self._cache[prompt_name] = content
        return content
    
    def format(self, prompt_name: str, **kwargs) -> str:
        """加载并格式化 Prompt"""
        import re
        # 每次强制重新加载，避免缓存问题
        self._cache.pop(prompt_name, None)
        template = self.load(prompt_name)
        
        # 使用正则只替换单个花括号包围的占位符 {key}
        def replace_placeholder(match):
            key = match.group(1)
            if key in kwargs:
                return str(kwargs[key])
            return match.group(0)  # 保持原样
        
        # 替换 {key} 格式的占位符（不匹配 {{...}} 或 {{{key}}}）
        template = re.sub(r'\{(\w+)\}', replace_placeholder, template)
        
        return template


# ============== ChromaDB 存储 ==============
class ChromaMemory:
    """ChromaDB 向量存储"""
    
    def __init__(self, storage_dir: Path = CHROMA_STORAGE_DIR):
        self.storage_dir = storage_dir
        self.collection_name = "privacy_rules"
        self._client = None
        self._collection = None
        self._rules_file = self.storage_dir / "rules.json"
        self._last_rules_mtime: float = 0  # 记录 rules.json 的修改时间
        self._loaded_rule_ids: set = set()  # 记录已加载的规则 ID
        self._initialize()
    
    def _initialize(self):
        """初始化 ChromaDB"""
        try:
            import chromadb
            from chromadb.config import Settings
        except ImportError:
            print("⚠️ chromadb 未安装，将使用内存存储")
            self._client = None
            self._collection = None
            return
        
        self._client = chromadb.PersistentClient(
            path=str(self.storage_dir),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # 获取或创建 collection
        try:
            self._collection = self._client.get_collection(name=self.collection_name)
        except:
            self._collection = self._client.create_collection(
                name=self.collection_name,
                metadata={"description": "隐私保护规则库"}
            )
        
        # 初始化时加载规则
        self._check_and_reload_rules()
    
    def _check_and_reload_rules(self):
        """检查并热更新 rules.json"""
        if not self._rules_file.exists():
            return
        
        try:
            current_mtime = self._rules_file.stat().st_mtime
            if current_mtime > self._last_rules_mtime:
                # 文件被修改，重新加载
                print(f"\n🔄 检测到 rules.json 变化，正在热更新...")
                self._load_rules_from_file()
                self._last_rules_mtime = current_mtime
        except Exception as e:
            pass
    
    def _load_rules_from_file(self):
        """从 rules.json 加载规则（支持热更新）"""
        if not self._rules_file.exists():
            print(f"⚠️ 规则文件不存在: {self._rules_file}")
            return
        
        try:
            with open(self._rules_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            rules = data.get("rules", [])
            
            # 获取当前 ChromaDB 中的所有规则 ID
            try:
                existing_data = self._collection.get(include=["ids"])
                existing_ids = set(existing_data.get("ids", []) or [])
            except:
                existing_ids = set()
            
            # 记录当前文件的规则 ID
            current_rule_ids = set()
            
            for rule in rules:
                rule_id = str(rule.get("id") or f"rule_{os.urandom(6).hex()}")
                current_rule_ids.add(rule_id)
                
                if rule_id not in self._loaded_rule_ids:
                    # 新规则，添加到 ChromaDB
                    self.add_rule(rule)
                    self._loaded_rule_ids.add(rule_id)
            
            # 找出被删除的规则（存在于 ChromaDB 但不在 rules.json 中）
            deleted_ids = existing_ids - current_rule_ids
            if deleted_ids:
                try:
                    self._collection.delete(ids=list(deleted_ids))
                    print(f"   🗑️ 已删除 {len(deleted_ids)} 条失效规则")
                    self._loaded_rule_ids -= deleted_ids
                except Exception as e:
                    print(f"   ⚠️ 删除失效规则失败: {e}")
            
            print(f"   ✅ 已同步 {len(rules)} 条规则（新增: {len(current_rule_ids - existing_ids)}, 删除: {len(deleted_ids)}）")
            
        except Exception as e:
            print(f"⚠️ 加载规则失败: {e}")
    
    def add_rule(self, rule: Dict[str, Any]) -> bool:
        """添加规则到向量库（允许扩展字段）"""
        if self._collection is None:
            return False
        
        try:
            rule_id = str(rule.get("id") or f"rule_{os.urandom(6).hex()}")
            
            # 如果是新增的规则，记录 ID
            self._loaded_rule_ids.add(rule_id)
            
            scenario = str(rule.get("scenario", ""))
            target_field = str(rule.get("target_field", ""))
            document = str(rule.get("document", ""))
            doc = f"场景: {scenario}, 目标字段: {target_field}, 规则: {document}".strip()
            self._collection.add(
                documents=[doc],
                ids=[rule_id],
                metadatas=[rule],
            )
            return True
        except Exception as e:
            print(f"⚠️ 添加规则失败: {e}")
            return False
    
    def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """检索相关规则"""
        # 每次检索前检查是否需要热更新
        self._check_and_reload_rules()
        
        if self._collection is None:
            return []
        
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=top_k,
                include=["documents", "distances", "metadatas"],
            )
            
            retrieved = []
            if results and results.get('documents'):
                for i, doc in enumerate(results['documents'][0]):
                    retrieved.append({
                        "document": doc,
                        "distance": results["distances"][0][i] if results.get("distances") else 0,
                        "metadata": results["metadatas"][0][i] if results.get("metadatas") else None,
                    })
            
            return retrieved
        except Exception as e:
            print(f"⚠️ 检索失败: {e}")
            return []

    def list_rules(self, limit: int = 200) -> List[Dict[str, Any]]:
        # 每次列出规则前检查是否需要热更新
        self._check_and_reload_rules()
        
        if self._collection is None:
            return []
        try:
            data = self._collection.get(include=["documents", "metadatas"], limit=limit)
            ids = data.get("ids") or []
            docs = data.get("documents") or []
            metas = data.get("metadatas") or []
            out: List[Dict[str, Any]] = []
            for i in range(min(len(ids), len(docs))):
                out.append(
                    {"id": ids[i], "document": docs[i], "metadata": metas[i] if i < len(metas) else None}
                )
            return out
        except Exception:
            return []


class RuleRepository:
    """rules.json 是事实来源，ChromaDB 仅作为检索索引。"""

    def __init__(self, rules_file: Path = CHROMA_STORAGE_DIR / "rules.json"):
        self.rules_file = rules_file
        self.rules_file.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> List[Dict[str, Any]]:
        if not self.rules_file.exists():
            return []
        try:
            data = json.loads(self.rules_file.read_text(encoding="utf-8"))
            rules = data.get("rules", [])
            return rules if isinstance(rules, list) else []
        except Exception:
            return []

    def upsert(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        rules = self.load()
        rule_id = str(rule.get("id") or f"rule_{os.urandom(6).hex()}")
        rule = {**rule, "id": rule_id}
        idx = next((i for i, r in enumerate(rules) if str(r.get("id")) == rule_id), None)
        if idx is None:
            rules.append(rule)
        else:
            rules[idx] = rule
        self.rules_file.write_text(
            json.dumps({"rules": rules}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return rule


# ============== MiniCPM API 客户端 ==============
class MiniCPMClient:
    """MiniCPM API 客户端"""

    # 默认最大分辨率限制（可动态调整）
    DEFAULT_MAX_SIZE = 4096  # 支持更大的分辨率
    MAX_WIDTH = 4096
    MAX_HEIGHT = 4096

    def __init__(self, api_url: str = "http://127.0.0.1:8000/chat",
                 max_width: int = None, max_height: int = None):
        self.api_url = api_url
        # 支持运行时配置最大分辨率
        self.max_width = max_width or self.MAX_WIDTH
        self.max_height = max_height or self.MAX_HEIGHT

    def extract_task_entities(self, user_command: str) -> List[str]:
        """从用户指令中提取任务关键实体（人名、账号、联系方式等）"""
        import re
        
        entities = []
        
        # 1. 提取带"给/向/对 xxx"模式的人名
        # "给张三发消息" -> 张三
        pattern1 = re.findall(r'给([\u4e00-\u9fa5]{2,4})发', user_command)
        pattern2 = re.findall(r'向([\u4e00-\u9fa5]{2,4})说', user_command)
        pattern3 = re.findall(r'对([\u4e00-\u9fa5]{2,4})说', user_command)
        entities.extend(pattern1 + pattern2 + pattern3)
        
        # 2. 提取"和xxx的"模式
        # "查看和李四的聊天记录" -> 李四
        pattern4 = re.findall(r'和([\u4e00-\u9fa5]{2,4})的', user_command)
        entities.extend(pattern4)
        
        # 3. 提取"@xxx"或"at xxx"模式
        at_names = re.findall(r'@(\w+)', user_command)
        entities.extend(at_names)
        
        # 4. 提取带引号的关键词（更精准）
        quoted = re.findall(r'["\']([^"\']{2,20})["\']', user_command)
        entities.extend(quoted)
        
        # 5. 提取微信号/手机号模式
        wechat_ids = re.findall(r'微信[号ID]?[:：]?(\w{6,20})', user_command)
        phone_nums = re.findall(r'1[3-9]\d{9}', user_command)
        entities.extend(wechat_ids + phone_nums)
        
        # 6. 常见指令词（需要过滤掉）
        stop_words = {
            '打开', '关闭', '给', '发', '看', '点击', '发送', '删除', '添加', '搜索',
            '找到', '进入', '返回', '提交', '填写', '登录', '注册', '点赞', '评论',
            '转发', '分享', '关注', '取消', '第一个', '第二条', '最后', '请', '帮我',
            '一下', '这个', '那个', '什么', '怎么', '如何', '帮忙', '告诉', '查询',
            '查看', '浏览', '聊天', '记录', '消息', '信息', '内容', '图片', '照片',
            '视频', '文件', '文档', '通讯录', '联系人', '电话', '地址', '名字', '姓名',
            '红包', '转账', '付款', '快递', '订单', '商品', '看看'
        }
        
        # 过滤
        entities = [e for e in entities if e not in stop_words and len(e) >= 2]
        
        # 去重
        entities = list(set(entities))
        
        return entities if entities else ["无明确实体"]

    def _preprocess_image(self, image_path: str) -> str:
        """
        预处理图片：确保图片尺寸在模型限制范围内
        支持手机原生高分辨率截图（如 1224x2688）
        """
        from PIL import Image
        import os

        if not os.path.exists(image_path):
            return image_path

        try:
            img = Image.open(image_path)
            width, height = img.size

            # 检查是否需要缩放
            if width <= self.max_width and height <= self.max_height:
                return image_path  # 无需处理

            # 计算缩放比例（保持宽高比）
            # 优先保证长边不超过限制
            scale_w = self.max_width / width
            scale_h = self.max_height / height
            scale = min(scale_w, scale_h, 1.0)  # 取最小值，确保不放大

            if scale < 1.0:
                new_width = int(width * scale)
                new_height = int(height * scale)

                # 使用高质量缩放（LANCZOS）
                resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # 保存处理后的图片（覆盖原文件或创建新文件）
                processed_path = image_path.replace('.png', '_processed.png').replace('.jpg', '_processed.jpg')
                resized_img.save(processed_path, quality=95)

                print(f"📐 图片已缩放: {width}x{height} -> {new_width}x{new_height}")
                return processed_path

        except Exception as e:
            print(f"⚠️ 图片预处理失败: {e}")

        return image_path
    
    def chat(self, prompt: str, image_path: Optional[str] = None) -> Dict[str, Any]:
        """调用 MiniCPM 进行推理"""
        import requests

        # 预处理图片（如果存在）
        processed_image_path = None
        if image_path and os.path.exists(image_path):
            processed_image_path = self._preprocess_image(image_path)

        try:
            files = {}
            data = {"prompt": prompt}

            if processed_image_path and os.path.exists(processed_image_path):
                with open(processed_image_path, 'rb') as f:
                    files['image'] = ('screenshot.png', f.read(), 'image/png')
            
            response = requests.post(
                self.api_url,
                data=data,
                files=files if files else None,
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    return {"success": True, "response": result.get("response", "")}
                return {"success": False, "error": result.get("message", "Unknown error")}
            return {"success": False, "error": f"HTTP {response.status_code}"}
            
        except ImportError:
            return {"success": False, "error": "requests 库未安装"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def decide_retrieval(self, scene_description: str, user_task: str, prompt_loader: PromptLoader) -> bool:
        """Self-RAG: 判断是否需要检索"""
        prompt = prompt_loader.format(
            "retrieval_decision",
            scene_description=scene_description,
            user_task=user_task
        )
        
        result = self.chat(prompt)
        if result.get("success"):
            response = result["response"].strip()
            return "[Retrieve]" in response
        return False
    
    def assess_relevance(self, scene_description: str, retrieved_docs: List[str], 
                        prompt_loader: PromptLoader) -> List[Tuple[str, bool]]:
        """Self-RAG: 评估检索结果相关性"""
        if not retrieved_docs:
            return []
        
        # 格式化检索内容
        content = "\n\n".join([f"片段 {i+1}: {doc}" for i, doc in enumerate(retrieved_docs)])
        
        prompt = prompt_loader.format(
            "relevance_assessment",
            retrieved_content=content,
            scene_description=scene_description
        )
        
        result = self.chat(prompt)
        if not result.get("success"):
            return [(doc, True) for doc in retrieved_docs]  # 默认都相关
        
        # 解析结果
        response = result["response"]
        relevance_results = []
        
        for i, doc in enumerate(retrieved_docs):
            # 简单解析：检查是否标记为 [Relevant]
            is_relevant = f"片段 {i+1}: [Relevant]" in response or "[Relevant]" in response
            relevance_results.append((doc, is_relevant))
        
        return relevance_results
    
    def analyze_privacy(self, image_path: str, user_command: str, prompt_loader: PromptLoader = None) -> Dict[str, Any]:
        """分析图片中的隐私信息"""
        # 使用外部 Prompt 文件
        if prompt_loader is None:
            from pathlib import Path
            prompt_loader = PromptLoader()
        
        # 提取任务关键实体
        task_entities = self.extract_task_entities(user_command)
        task_entities_str = "、".join(task_entities)
        
        prompt = prompt_loader.format(
            "privacy_analysis",
            user_command=user_command,
            task_entities=task_entities_str
        )
        
        result = self.chat(prompt, image_path)
        
        if result.get("success"):
            try:
                import re
                response_text = result["response"]
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    analysis = json.loads(json_match.group())
                    # 保存任务实体，供后续处理使用
                    analysis["_task_entities"] = task_entities
                    return {"success": True, "analysis": analysis}
                return {"success": True, "analysis": {"raw_response": response_text, "_task_entities": task_entities}}
            except (json.JSONDecodeError, re.error):
                return {"success": True, "analysis": {"raw_response": result["response"], "_task_entities": task_entities}}
        return result


# ============== Smart Masker 打码服务 ==============
class SmartMasker:
    """隐私打码服务"""
    
    def __init__(self):
        self._masker = None
    
    def _get_masker(self):
        """延迟加载打码器"""
        if self._masker is None:
            try:
                from skills.smart_masker import VisualMasker
                self._masker = VisualMasker()
            except ImportError:
                print("⚠️ smart_masker 模块未找到")
                return None
        return self._masker
    
    def mask(self, image_path: str, sensitive_texts: List[str],
             output_path: Optional[str] = None) -> Dict[str, Any]:
        """对图片中的敏感信息进行打码"""
        masker = self._get_masker()
        if masker is None:
            return {"success": False, "error": "打码器不可用"}
        
        if output_path is None:
            filename = f"masked_{Path(image_path).stem}.jpg"
            output_path = str(TEMP_DIR / filename)
        
        try:
            result_path, masked_count = masker.mask_sensitive_info(
                image_path=image_path,
                sensitive_texts=sensitive_texts,
                output_path=output_path
            )
            
            return {
                "success": True,
                "output_path": result_path,
                "masked_count": masked_count
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


# ============== Hook 拦截器 ==============
class ScreenshotHook:
    """截图函数 Hook 拦截器"""
    
    _original_get_screenshot = None
    _is_installed = False
    
    @classmethod
    def install(cls, privacy_agent: 'PrivacyProxyAgent'):
        """安装 Hook"""
        if cls._is_installed:
            print("⚠️ Hook 已安装")
            return
        
        try:
            # 动态导入 device_factory
            sys.path.insert(0, str(PROJECT_ROOT / "Open-AutoGLM-main"))
            from phone_agent import device_factory
            
            # 保存原始函数
            cls._original_get_screenshot = device_factory.get_screenshot
            
            # Monkey Patch
            def hooked_get_screenshot(device_id=None):
                # 1. 调用原始函数获取截图（通常包含 base64_data）
                original_screenshot = cls._original_get_screenshot(device_id)

                # 2. 取出图片 bytes（不在 Hook 层落盘）
                img_bytes: Optional[bytes] = None
                if hasattr(original_screenshot, "base64_data") and getattr(original_screenshot, "base64_data"):
                    try:
                        img_bytes = base64.b64decode(original_screenshot.base64_data)
                    except Exception:
                        img_bytes = None
                if img_bytes is None and hasattr(original_screenshot, "data") and getattr(original_screenshot, "data"):
                    try:
                        img_bytes = original_screenshot.data
                    except Exception:
                        img_bytes = None

                # 3. 调用隐私代理（由 agent 负责临时文件与清理）
                if img_bytes is None:
                    return original_screenshot

                user_command = privacy_agent.last_user_command or "分析当前页面"
                result = privacy_agent.process_image_bytes(img_bytes, "screenshot.png", user_command)
                return result.screenshot
            
            # 替换函数
            device_factory.get_screenshot = hooked_get_screenshot
            cls._is_installed = True
            print("✅ Hook 拦截器已安装")
            
        except ImportError as e:
            print(f"⚠️ 无法导入 device_factory: {e}")
        except Exception as e:
            print(f"⚠️ Hook 安装失败: {e}")
    
    @classmethod
    def uninstall(cls):
        """卸载 Hook"""
        if not cls._is_installed or cls._original_get_screenshot is None:
            return
        
        try:
            from phone_agent import device_factory
            device_factory.get_screenshot = cls._original_get_screenshot
            cls._is_installed = False
            print("✅ Hook 已卸载")
        except Exception as e:
            print(f"⚠️ Hook 卸载失败: {e}")
    
    @staticmethod
    def _save_screenshot(screenshot) -> str:
        """将 Screenshot 对象保存为临时文件"""
        try:
            # Screenshot 对象可能有 base64_data 属性
            if hasattr(screenshot, 'base64_data'):
                img_data = base64.b64decode(screenshot.base64_data)
            elif hasattr(screenshot, 'data'):
                img_data = screenshot.data
            else:
                # 尝试直接使用
                img_data = screenshot
            
            # 保存到临时文件
            temp_path = TEMP_DIR / f"screenshot_{os.urandom(8).hex()}.png"
            with open(temp_path, 'wb') as f:
                f.write(img_data)
            
            return str(temp_path)
        except Exception as e:
            print(f"⚠️ 保存截图失败: {e}")
            return ""


# ============== 隐私代理核心类 ==============
class PrivacyProxyAgent:
    """隐私保护前置代理 - 核心骨架"""
    
    def __init__(self):
        # 初始化各组件
        self.prompt_loader = PromptLoader()
        self.rule_repo = RuleRepository()
        self.chroma_memory = ChromaMemory()
        self.minicpm_client = MiniCPMClient()
        self.smart_masker = SmartMasker()
        
        # 状态
        self.last_user_command = None
        self.last_matched_rules = []
        
        print("🔒 隐私代理初始化完成")

    def upsert_rule(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        """写入 rules.json（事实来源），并更新 ChromaDB 索引（检索用）。"""
        stored = self.rule_repo.upsert(rule)
        self.chroma_memory.add_rule(stored)
        return stored

    def list_rules(self, limit: int = 200) -> List[Dict[str, Any]]:
        rules = self.rule_repo.load()
        if rules:
            return rules[:limit]
        return self.chroma_memory.list_rules(limit=limit)

    def process_image_bytes(self, image_bytes: bytes, filename: str, user_command: str, user_id: str) -> ProcessResult:
        """
        供 HTTP 层调用：bytes → 完整调度 → bytes + JSON
        
        Args:
            image_bytes: 截图字节数据
            filename: 文件名
            user_command: 用户指令
            user_id: 用户唯一标识（必填，用于行为日志隔离）
        """
        if not user_id:
            raise ValueError("user_id 不能为空，用于用户行为日志隔离")
        tfm = TempFileManager()
        try:
            input_path = tfm.write_bytes(image_bytes, safe_suffix(filename))
            screenshot = self.process_screenshot(str(input_path), user_command, user_id)
            masked_bytes = (
                base64.b64decode(screenshot.base64_data)
                if screenshot and getattr(screenshot, "base64_data", None)
                else image_bytes
            )
            analysis = getattr(screenshot, "analysis", {}) if screenshot else {}
            masked_count = int(getattr(screenshot, "masked_count", 0) or 0) if screenshot else 0
            
            # 将隐私元数据写入 screenshot 对象，供 Open-AutoGLM 读取
            if screenshot:
                screenshot.privacy_metadata = {
                    "matched_rules": self.last_matched_rules,
                    "masked_count": masked_count,
                }
            
            return ProcessResult(
                screenshot=screenshot,
                masked_image_bytes=masked_bytes,
                masked_mime_type=guess_mime_type(filename),
                matched_rules=self.last_matched_rules,
                analysis=analysis if isinstance(analysis, dict) else {"raw": analysis},
                masked_count=masked_count,
            )
        finally:
            tfm.cleanup()
    
    def process_screenshot(self, image_path: str, user_command: str, user_id: str) -> SafeScreenshot:
        """
        处理截图的核心流程：
        1. Self-RAG 检索规则
        2. MiniCPM 分析隐私信息
        3. Smart Masker 打码
        4. 记录行为日志（写入 memory/logs/{user_id}/）
        
        Args:
            image_path: 截图路径
            user_command: 用户指令
            user_id: 用户唯一标识（必填）
        """
        self.last_user_command = user_command
        
        # 基于截图内容进行规则检索
        matched_rules = self._selfrag_retrieve(image_path, user_command)
        self.last_matched_rules = matched_rules
        formatted_rules = self._format_rules(matched_rules)

        privacy_analysis = self.minicpm_client.analyze_privacy(
            image_path=image_path,
            user_command=user_command,
            prompt_loader=self.prompt_loader
        )
        
        sensitive_texts: List[str] = []
        need_mask = False
        analysis: Dict[str, Any] = {}
        task_target_entities: List[str] = []  # 任务目标实体
        
        if privacy_analysis.get("success"):
            analysis = privacy_analysis.get("analysis", {}) or {}
            if isinstance(analysis, dict):
                # 调试：打印完整的 MiniCPM 分析结果
                print(f"\n🔍 MiniCPM 隐私分析结果:")
                print(f"   task_target_entities: {analysis.get('task_target_entities', [])}")
                print(f"   privacy_concerns: {analysis.get('privacy_concerns', [])}")
                print(f"   mask_plan: {analysis.get('mask_plan', [])}")
                print(f"   need_mask: {analysis.get('need_mask', False)}")
                
                # 保存任务目标实体
                task_target_entities = analysis.get("task_target_entities", [])
                
                # 新格式：使用 mask_plan（支持 action 字段）
                mask_plan = analysis.get("mask_plan", [])
                if mask_plan:
                    for item in mask_plan:
                        if isinstance(item, dict):
                            action = item.get("action", "MASK")
                            if action == "MASK":
                                # 需要打码的项
                                if item.get("text"):
                                    sensitive_texts.append(str(item["text"]))
                            elif action == "KEEP_AS_TASK_TARGET":
                                # 任务目标，豁免打码
                                print(f"   🔑 豁免打码（任务目标）: {item.get('text')}")
                    need_mask = bool(sensitive_texts)
                else:
                    # 兼容旧格式：使用 sensitive_info
                    for info in analysis.get("sensitive_info", []) or []:
                        if isinstance(info, dict) and info.get("text"):
                            sensitive_texts.append(str(info["text"]))
                    need_mask = bool(analysis.get("need_mask", bool(sensitive_texts)))
            
            # 后处理：自动补充遗漏的常见隐私类型（兜底机制）
            import re
            # 读取原始截图进行 OCR
            ocr_texts = self._get_ocr_texts(image_path)
            all_text = " ".join(ocr_texts)
            
            # 自动识别手机号（11位数字）
            phone_pattern = re.compile(r'\b1[3-9]\d{9}\b')
            found_phones = phone_pattern.findall(all_text)
            
            # 检查是否已识别，未识别的自动补充
            existing_mask_texts = [s.lower() for s in sensitive_texts]
            for phone in found_phones:
                if phone not in existing_mask_texts and phone not in task_target_entities:
                    sensitive_texts.append(phone)
                    print(f"   📱 自动补充识别手机号: {phone}")
                    need_mask = True
            
            # 自动识别身份证号（18位）
            id_pattern = re.compile(r'\b[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b')
            found_ids = id_pattern.findall(all_text)
            for id_num in found_ids:
                if id_num not in existing_mask_texts:
                    sensitive_texts.append(id_num)
                    print(f"   🪪 自动补充识别身份证号: {id_num[:6]}****{id_num[-4:]}")
                    need_mask = True
        
        masked_image_path = None
        masked_count = 0
        if need_mask and sensitive_texts:
            mask_result = self.smart_masker.mask(
                image_path=image_path,
                sensitive_texts=sensitive_texts
            )
            
            if mask_result.get("success"):
                masked_image_path = mask_result["output_path"]
                masked_count = int(mask_result.get("masked_count", 0) or 0)
            else:
                masked_image_path = image_path
        else:
            masked_image_path = image_path
        
        screenshot_obj = self._load_as_screenshot(masked_image_path)

        # 挂载调试/返回信息（不影响 Hook 兼容）
        screenshot_obj.analysis = analysis
        screenshot_obj.masked_count = masked_count

        # 记录行为日志
        self._log_behavior(
            user_id=user_id,
            matched_rules=matched_rules,
            analysis=analysis,
            need_mask=need_mask,
            sensitive_texts=sensitive_texts,
            masked_count=masked_count,
        )

        return screenshot_obj

    def _log_behavior(
        self,
        user_id: str,
        matched_rules: List[Dict[str, Any]],
        analysis: Dict[str, Any],
        need_mask: bool,
        sensitive_texts: List[str],
        masked_count: int,
    ) -> None:
        """记录行为日志到 memory/logs/{user_id}/（用户目录隔离）"""
        try:
            from skills.behavior_monitor import log_event

            # 从 analysis 中提取 app_context
            app_context = analysis.get("app_context", "unknown")
            task_target_entities = analysis.get("task_target_entities", [])
            mask_plan = analysis.get("mask_plan", [])

            # 根据是否有匹配的规则和打码需求决定 resolution
            if matched_rules and need_mask:
                resolution = "mask"
                level = 1
            elif matched_rules:
                resolution = "allow"
                level = 1
            else:
                # 无匹配规则，不处理
                return

            # 为每个敏感字段记录一条日志
            pii_types = []
            for item in mask_plan:
                if isinstance(item, dict):
                    pii_type = item.get("pii_type", "unknown")
                    if pii_type not in pii_types:
                        pii_types.append(pii_type)

            log_event(
                user_id=user_id,
                app_context=app_context,
                action="agent_process_screenshot",
                field=",".join([str(t) for t in task_target_entities]) or "unknown",
                resolution=resolution,
                level=level,
                value_preview=f"{len(sensitive_texts)} items masked" if sensitive_texts else "no sensitive data",
                pii_types_involved=pii_types,
            )
        except Exception as e:
            print(f"⚠️ 记录行为日志失败: {e}")

    def _selfrag_retrieve(self, image_path: str, user_command: str) -> List[Dict[str, Any]]:
        """
        Self-RAG 检索流程（基于截图内容）
        1. 使用 MiniCPM 分析截图，生成场景描述
        2. 基于场景描述判断是否需要检索
        3. ChromaDB 检索
        4. 评估相关性
        """
        print("\n" + "=" * 60)
        print("🔍 隐私规则检索流程")
        print("=" * 60)
        
        # Step 1: 使用 MiniCPM 分析截图内容，生成场景描述作为检索 query
        print("\n[Step 1] 📷 分析截图内容...")
        scene_description = self._analyze_scene_description(image_path, user_command)
        
        if not scene_description:
            print("   ⚠️ 无法生成场景描述，跳过检索")
            print("=" * 60 + "\n")
            return []
        
        print(f"   📝 场景描述: {scene_description}")
        
        # Step 2: 判断是否需要检索
        print("\n[Step 2] 🤖 判断是否需要检索...")
        need_retrieve = self.minicpm_client.decide_retrieval(
            scene_description, 
            user_command,
            self.prompt_loader
        )
        
        if not need_retrieve:
            print("   ℹ️  MiniCPM 判断当前场景无需外部检索")
            print("=" * 60 + "\n")
            return []
        
        # Step 3: ChromaDB 检索（使用场景描述作为 query）
        print("\n[Step 3] 🔎 ChromaDB 检索...")
        print(f"   Query: {scene_description[:80]}...")
        raw_results = self.chroma_memory.retrieve(scene_description)
        
        if not raw_results:
            print("   ℹ️  ChromaDB 无匹配结果")
            print("=" * 60 + "\n")
            return []
        
        print(f"   📄 检索到 {len(raw_results)} 条候选规则")
        
        # Step 4: 评估相关性
        print("\n[Step 4] 📊 评估规则相关性...")
        retrieved_docs = [r["document"] for r in raw_results]
        relevance_results = self.minicpm_client.assess_relevance(
            scene_description, 
            retrieved_docs,
            self.prompt_loader
        )
        
        # 打印每条规则的相关性评估结果
        for i, (doc, is_relevant) in enumerate(relevance_results):
            status = "✅ 相关" if is_relevant else "❌ 不相关"
            # 截取规则描述
            doc_preview = doc[:60] + "..." if len(doc) > 60 else doc
            print(f"   {i+1}. {status}: {doc_preview}")
        
        # Step 5: 过滤相关结果
        matched = []
        for (doc, is_relevant) in relevance_results:
            if is_relevant:
                matched.append({"document": doc})
        
        print(f"\n[Result] ✅ 匹配到 {len(matched)} 条相关规则")
        print("=" * 60 + "\n")
        
        return matched
    
    def _analyze_scene_description(self, image_path: str, user_command: str) -> str:
        """使用 MiniCPM 分析截图，生成场景描述（用于规则检索）"""
        prompt = f"""分析这张截图，描述当前界面场景。

用户任务: {user_command}

请描述：
1. 当前是什么应用/页面（如：微信聊天页、淘宝商品页、登录页等）
2. 页面包含哪些关键元素（如：搜索框、输入框、按钮列表等）
3. 是否有明显的隐私敏感元素（如：手机号输入框、身份证号、地址栏等）

请用简洁的中文描述场景，20-50字即可。"""
        
        result = self.minicpm_client.chat(prompt, image_path)
        
        if result.get("success"):
            return result.get("response", "").strip()
        return ""
    
    def _format_rules(self, rules: List[Dict[str, Any]]) -> str:
        """格式化规则为文本"""
        if not rules:
            return "无特定规则匹配"
        
        formatted = []
        for i, rule in enumerate(rules):
            doc = rule.get("document", "")
            formatted.append(f"{i+1}. {doc}")
        return "\n".join(formatted)
    
    def _get_ocr_texts(self, image_path: str) -> List[str]:
        """使用 RapidOCR 提取图片中的所有文本"""
        import cv2
        from rapidocr import RapidOCR
        
        ocr_engine = RapidOCR()
        image = cv2.imread(image_path)
        
        if image is None:
            return []
        
        result = ocr_engine(image)
        if result is None:
            return []
        
        # RapidOCR 返回 RapidOCROutput 对象，有 txts, boxes, scores 属性
        # txts 是 tuple 类型
        texts = getattr(result, 'txts', None)
        if texts:
            return [str(t) for t in texts if t]
        return []
        
        text = ""
        for i, rule in enumerate(rules, 1):
            text += f"\n规则 {i}:\n{rule.get('document', '')}\n"
        return text
    
    def _load_as_screenshot(self, image_path: str) -> SafeScreenshot:
        """将图片文件加载为 Screenshot 对象"""
        try:
            with open(image_path, 'rb') as f:
                img_data = f.read()
            
            # 转换为 base64
            b64_data = base64.b64encode(img_data).decode('utf-8')
            
            # 获取图片尺寸
            img = Image.open(BytesIO(img_data))
            width, height = img.size
            
            return SafeScreenshot(b64_data, width, height)
            
        except Exception as e:
            print(f"⚠️ 加载截图失败: {e}")
            # 返回空截图
            return SafeScreenshot("", 0, 0)


# ============== 全局实例 ==============
_privacy_agent = None

def get_privacy_agent() -> PrivacyProxyAgent:
    """获取全局隐私代理实例"""
    global _privacy_agent
    if _privacy_agent is None:
        _privacy_agent = PrivacyProxyAgent()
    return _privacy_agent


def install_hook():
    """安装 Hook 拦截器"""
    agent = get_privacy_agent()
    ScreenshotHook.install(agent)


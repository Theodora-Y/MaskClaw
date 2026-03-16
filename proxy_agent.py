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
        template = self.load(prompt_name)
        return template.format(**kwargs)


# ============== ChromaDB 存储 ==============
class ChromaMemory:
    """ChromaDB 向量存储"""
    
    def __init__(self, storage_dir: Path = CHROMA_STORAGE_DIR):
        self.storage_dir = storage_dir
        self.collection_name = "privacy_rules"
        self._client = None
        self._collection = None
        self._rules_file = self.storage_dir / "rules.json"
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
            # 从 rules.json 加载默认规则
            self._load_rules_from_file()
    
    def _load_rules_from_file(self):
        """从 rules.json 加载默认规则"""
        if not self._rules_file.exists():
            print(f"⚠️ 规则文件不存在: {self._rules_file}")
            return
        
        try:
            with open(self._rules_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            rules = data.get("rules", [])
            for rule in rules:
                self.add_rule(rule)
            
            print(f"✅ 已从 rules.json 加载 {len(rules)} 条规则")
        except Exception as e:
            print(f"⚠️ 加载规则失败: {e}")
    
    def add_rule(self, rule: Dict[str, Any]) -> bool:
        """添加规则到向量库（允许扩展字段）"""
        if self._collection is None:
            return False
        
        try:
            rule_id = str(rule.get("id") or f"rule_{os.urandom(6).hex()}")
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
    
    def decide_retrieval(self, user_question: str, prompt_loader: PromptLoader) -> bool:
        """Self-RAG: 判断是否需要检索"""
        prompt = prompt_loader.format(
            "retrieval_decision",
            user_question=user_question
        )
        
        result = self.chat(prompt)
        if result.get("success"):
            response = result["response"].strip()
            return "[Retrieve]" in response
        return False
    
    def assess_relevance(self, user_question: str, retrieved_docs: List[str], 
                        prompt_loader: PromptLoader) -> List[Tuple[str, bool]]:
        """Self-RAG: 评估检索结果相关性"""
        if not retrieved_docs:
            return []
        
        # 格式化检索内容
        content = "\n\n".join([f"片段 {i+1}: {doc}" for i, doc in enumerate(retrieved_docs)])
        
        prompt = prompt_loader.format(
            "relevance_assessment",
            retrieved_content=content,
            user_question=user_question
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
    
    def analyze_privacy(self, image_path: str, user_command: str, 
                       matched_rules: str) -> Dict[str, Any]:
        """分析图片中的隐私信息"""
        prompt = f"""你是一个隐私安全代理。请分析这张截图：

用户指令: {user_command}

本地 RAG 规则:
{matched_rules}

请分析：
1. 这张图片中包含哪些敏感/隐私信息？（如：姓名、手机号、地址、银行卡、身份证等）
2. 每个敏感信息的具体文字内容是什么？
3. 需要对这些信息进行打码处理吗？

输出格式（JSON）：
{{
  "sensitive_info": [
    {{"type": "手机号", "text": "13812345678", "location": "截图顶部输入框"}},
    {{"type": "地址", "text": "北京市朝阳区xx小区", "location": "收货地址栏"}}
  ],
  "need_mask": true/false,
  "reasoning": "分析理由"
}}
"""
        
        result = self.chat(prompt, image_path)
        
        if result.get("success"):
            try:
                import re
                response_text = result["response"]
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    analysis = json.loads(json_match.group())
                    return {"success": True, "analysis": analysis}
                return {"success": True, "analysis": {"raw_response": response_text}}
            except (json.JSONDecodeError, re.error):
                return {"success": True, "analysis": {"raw_response": result["response"]}}
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

    def process_image_bytes(self, image_bytes: bytes, filename: str, user_command: str) -> ProcessResult:
        """
        供 HTTP 层调用：bytes → 完整调度 → bytes + JSON
        """
        tfm = TempFileManager()
        try:
            input_path = tfm.write_bytes(image_bytes, safe_suffix(filename))
            screenshot = self.process_screenshot(str(input_path), user_command)
            masked_bytes = (
                base64.b64decode(screenshot.base64_data)
                if screenshot and getattr(screenshot, "base64_data", None)
                else image_bytes
            )
            analysis = getattr(screenshot, "analysis", {}) if screenshot else {}
            masked_count = int(getattr(screenshot, "masked_count", 0) or 0) if screenshot else 0
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
    
    def process_screenshot(self, image_path: str, user_command: str) -> SafeScreenshot:
        """
        处理截图的核心流程：
        1. Self-RAG 检索规则
        2. MiniCPM 分析隐私信息
        3. Smart Masker 打码
        4. 返回处理后的截图
        """
        self.last_user_command = user_command
        
        matched_rules = self._selfrag_retrieve(user_command)
        self.last_matched_rules = matched_rules
        formatted_rules = self._format_rules(matched_rules)

        privacy_analysis = self.minicpm_client.analyze_privacy(
            image_path=image_path,
            user_command=user_command,
            matched_rules=formatted_rules
        )
        
        sensitive_texts: List[str] = []
        need_mask = False
        analysis: Dict[str, Any] = {}
        
        if privacy_analysis.get("success"):
            analysis = privacy_analysis.get("analysis", {}) or {}
            if isinstance(analysis, dict):
                for info in analysis.get("sensitive_info", []) or []:
                    if isinstance(info, dict) and info.get("text"):
                        sensitive_texts.append(str(info["text"]))
                need_mask = bool(analysis.get("need_mask", bool(sensitive_texts)))
        
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
        return screenshot_obj
    
    def _selfrag_retrieve(self, user_command: str) -> List[Dict[str, Any]]:
        """Self-RAG 检索流程"""
        # 1. 判断是否需要检索
        need_retrieve = self.minicpm_client.decide_retrieval(
            user_command, 
            self.prompt_loader
        )
        
        if not need_retrieve:
            print("   MiniCPM 判断无需外部检索")
            return []
        
        # 2. ChromaDB 检索
        print("   正在检索 ChromaDB...")
        raw_results = self.chroma_memory.retrieve(user_command)
        
        if not raw_results:
            return []
        
        # 3. 评估相关性
        retrieved_docs = [r["document"] for r in raw_results]
        relevance_results = self.minicpm_client.assess_relevance(
            user_command, 
            retrieved_docs,
            self.prompt_loader
        )
        
        # 4. 过滤相关结果
        matched = []
        for (doc, is_relevant) in relevance_results:
            if is_relevant:
                matched.append({"document": doc})
        
        return matched
    
    def _format_rules(self, rules: List[Dict[str, Any]]) -> str:
        """格式化规则为文本"""
        if not rules:
            return "无特定规则匹配"
        
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


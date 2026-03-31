"""RAG 客户端 - 封装 ChromaDB 向量检索功能"""

import json
import logging
from typing import Any, Dict, List, Optional

import chromadb

logger = logging.getLogger(__name__)


class RAGClient:
    """RAG 向量检索客户端"""

    def __init__(
        self,
        persist_directory: str = "memory/chroma_storage",
        collection_name: str = "default",
    ):
        self.persist_directory = persist_directory
        self._client: Optional[chromadb.PersistentClient] = None

    @property
    def client(self) -> chromadb.PersistentClient:
        """延迟初始化 ChromaDB 客户端"""
        if self._client is None:
            self._client = chromadb.PersistentClient(path=self.persist_directory)
        return self._client

    def query(
        self,
        query_text: str,
        collection_name: str = "default",
        where: Optional[Dict[str, Any]] = None,
        top_k: int = 3,
    ) -> Dict[str, Any]:
        """查询向量数据库

        Args:
            query_text: 查询文本
            collection_name: 集合名称
            where: 过滤条件（如 {"app_context": "hospital_oa"}）
            top_k: 返回数量

        Returns:
            {
                "documents": [...],      # 匹配的文档内容
                "metadatas": [...],       # 元数据
                "distances": [...],       # 距离/相似度
            }
        """
        try:
            collection = self.client.get_collection(name=collection_name)

            results = collection.query(
                query_texts=[query_text],
                n_results=top_k,
                where=where,
            )

            return {
                "documents": results.get("documents", [[]])[0],
                "metadatas": results.get("metadatas", [[]])[0],
                "distances": results.get("distances", [[]])[0],
            }

        except Exception as e:
            logger.warning(f"RAG query failed: {e}")
            return {"documents": [], "metadatas": [], "distances": []}

    def add_rule(
        self,
        rule_text: str,
        collection_name: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
        rule_id: Optional[str] = None,
    ) -> bool:
        """添加规则到向量数据库

        Args:
            rule_text: 规则文本内容
            collection_name: 集合名称
            metadata: 元数据
            rule_id: 规则 ID（可选）

        Returns:
            是否添加成功
        """
        try:
            collection = self.client.get_or_create_collection(name=collection_name)

            import uuid
            from time import time

            doc_id = rule_id or str(uuid.uuid4())
            metadata = metadata or {}
            metadata["created_ts"] = int(time())

            collection.add(
                documents=[rule_text],
                metadatas=[metadata],
                ids=[doc_id],
            )

            return True

        except Exception as e:
            logger.warning(f"RAG add_rule failed: {e}")
            return False

    def get_collection_stats(self, collection_name: str = "default") -> Dict[str, Any]:
        """获取集合统计信息"""
        try:
            collection = self.client.get_collection(name=collection_name)
            return {
                "name": collection_name,
                "count": collection.count(),
                "metadata": collection.metadata,
            }
        except Exception as e:
            return {"error": str(e)}
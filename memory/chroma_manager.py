"""Chroma translation layer for evolution and proxy retrieval."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class ChromaManager:
	"""Manage rule persistence between Chroma and rules.json backup.

	Main API:
	- add_rule(user_id, rule_dict) -> str | None
	- get_allow_history(user_id) -> list[dict]
	- rule_exists(user_id, rule_text) -> bool
	- get_rules_by_user(user_id) -> list[dict]
	- deprecate_rule(rule_id) -> bool
	"""

	REQUIRED_FIELDS = ["rule_id", "rule_text", "scene", "sensitive_field", "strategy"]

	def __init__(
		self,
		storage_dir: str = "memory/chroma_storage",
		collection_name: str = "privacy_rules",
		rules_file_name: str = "rules.json",
		duplicate_distance_threshold: float = 0.08,
	) -> None:
		self.storage_dir = Path(storage_dir)
		self.storage_dir.mkdir(parents=True, exist_ok=True)
		self.collection_name = collection_name
		self.rules_file = self.storage_dir / rules_file_name
		self.duplicate_distance_threshold = duplicate_distance_threshold
		self._file_lock = threading.Lock()
		self._client = None
		self._collection = None

		self._ensure_rules_file()
		self._init_chroma()

	def _ensure_rules_file(self) -> None:
		if not self.rules_file.exists():
			self.rules_file.write_text(json.dumps({"rules": []}, ensure_ascii=False, indent=2), encoding="utf-8")

	def _init_chroma(self) -> None:
		try:
			import chromadb
			from chromadb.config import Settings

			self._client = chromadb.PersistentClient(
				path=str(self.storage_dir),
				settings=Settings(anonymized_telemetry=False),
			)
			try:
				self._collection = self._client.get_collection(name=self.collection_name)
			except Exception:
				self._collection = self._client.create_collection(name=self.collection_name)
		except Exception:
			self._client = None
			self._collection = None

	def _load_rules(self) -> List[Dict[str, Any]]:
		try:
			data = json.loads(self.rules_file.read_text(encoding="utf-8"))
			rules = data.get("rules", [])
			return rules if isinstance(rules, list) else []
		except Exception:
			return []

	def _save_rules(self, rules: List[Dict[str, Any]]) -> None:
		with self._file_lock:
			self.rules_file.write_text(
				json.dumps({"rules": rules}, ensure_ascii=False, indent=2),
				encoding="utf-8",
			)

	@staticmethod
	def _build_document(rule: Dict[str, Any]) -> str:
		return str(rule.get("rule_text") or rule.get("document") or "").strip()

	def _validate_rule(self, rule: Dict[str, Any]) -> bool:
		for key in self.REQUIRED_FIELDS:
			if rule.get(key) in (None, ""):
				return False
		if str(rule.get("strategy", "")).strip().lower() not in {"block", "replace"}:
			return False
		return True

	def _normalize_rule(self, user_id: str, rule: Dict[str, Any]) -> Dict[str, Any]:
		now = int(time.time())
		rule_id = str(rule.get("rule_id") or f"{user_id}_{now}_{os.urandom(3).hex()}")
		scene = str(rule.get("scene") or rule.get("scenario") or "")
		field = str(rule.get("sensitive_field") or rule.get("target_field") or "")
		rule_text = self._build_document(rule)

		normalized = {
			**rule,
			"id": str(rule.get("id") or rule_id),
			"rule_id": rule_id,
			"user_id": user_id,
			"scene": scene,
			"scenario": str(rule.get("scenario") or scene),
			"sensitive_field": field,
			"target_field": str(rule.get("target_field") or field),
			"rule_text": rule_text,
			"document": str(rule.get("document") or rule_text),
			"status": str(rule.get("status") or "active"),
			"created_ts": int(rule.get("created_ts") or now),
		}
		return normalized

	def rule_exists(self, user_id: str, rule_text: str) -> bool:
		if not rule_text.strip():
			return False

		if self._collection is None:
			# Fallback: exact text match in backup.
			for r in self._load_rules():
				if str(r.get("user_id", "")) == user_id and str(r.get("document", "")).strip() == rule_text.strip():
					return True
			return False

		try:
			result = self._collection.query(
				query_texts=[rule_text],
				n_results=1,
				where={"user_id": user_id},
				include=["distances"],
			)
			distances = (result or {}).get("distances") or []
			if not distances or not distances[0]:
				return False
			best_distance = float(distances[0][0])
						# cosine_similarity >= 0.92 is roughly equivalent to distance <= 0.08
			return best_distance <= self.duplicate_distance_threshold
		except Exception:
			return False

	def add_rule(self, user_id: str, rule_dict: Dict[str, Any]) -> Optional[str]:
		normalized = self._normalize_rule(user_id, rule_dict)

		if not self._validate_rule(normalized):
			return None

		if self.rule_exists(user_id, str(normalized.get("rule_text", ""))):
			return None

		# 1) Upsert into Chroma.
		if self._collection is not None:
			try:
				self._collection.upsert(
					ids=[normalized["id"]],
					documents=[self._build_document(normalized)],
					metadatas=[normalized],
				)
			except Exception:
				return None

		# 2) Sync rules.json backup.
		rules = self._load_rules()
		idx = next((i for i, r in enumerate(rules) if str(r.get("id")) == normalized["id"]), None)
		if idx is None:
			rules.append(normalized)
		else:
			rules[idx] = normalized
		self._save_rules(rules)

		return str(normalized["rule_id"])

	def get_allow_history(self, user_id: str) -> List[Dict[str, Any]]:
		behavior_path = self.storage_dir.parent / "logs" / user_id / "behavior_log.jsonl"
		if not behavior_path.exists():
			return []

		rows: List[Dict[str, Any]] = []
		try:
			with behavior_path.open("r", encoding="utf-8") as f:
				for line in f:
					line = line.strip()
					if not line:
						continue
					item = json.loads(line)
					if str(item.get("resolution", "")) != "allow":
						continue
					rows.append(
						{
							"app_context": item.get("app_context"),
							"action": item.get("action"),
							"field": item.get("field"),
							"event_id": item.get("event_id"),
						}
					)
		except Exception:
			return []
		return rows

	def get_rules_by_user(self, user_id: str) -> List[Dict[str, Any]]:
		out: List[Dict[str, Any]] = []

		if self._collection is not None:
			try:
				data = self._collection.get(
					where={"user_id": user_id, "status": "active"},
					include=["metadatas"],
				)
				for m in (data or {}).get("metadatas") or []:
					if isinstance(m, dict):
						out.append(m)
			except Exception:
				out = []

		if out:
			return out

		# Fallback backup scan.
		for r in self._load_rules():
			if str(r.get("user_id", "")) == user_id and str(r.get("status", "active")) == "active":
				out.append(r)
		return out

	def deprecate_rule(self, rule_id: str) -> bool:
		# Update JSON backup first.
		rules = self._load_rules()
		target = None
		for r in rules:
			if str(r.get("rule_id", "")) == rule_id or str(r.get("id", "")) == rule_id:
				r["status"] = "deprecated"
				target = r
				break
		if target is None:
			return False
		self._save_rules(rules)

		# Update Chroma metadata by upsert.
		if self._collection is not None:
			try:
				self._collection.upsert(
					ids=[str(target.get("id") or target.get("rule_id"))],
					documents=[self._build_document(target)],
					metadatas=[target],
				)
			except Exception:
				return False
		return True

	# Compatibility wrappers used by existing runtime code.
	def write_rule(self, rule: Dict[str, Any], *, check_duplicate: bool = True, duplicate_threshold: float = 0.08) -> Dict[str, Any]:
		user_id = str(rule.get("user_id") or "shared")
		old_threshold = self.duplicate_distance_threshold
		self.duplicate_distance_threshold = duplicate_threshold
		try:
			if check_duplicate and self.rule_exists(user_id, str(rule.get("rule_text") or rule.get("document") or "")):
				return {"written": False, "reason": "duplicate_rule", "rule": rule, "matched_rule": None}
			rid = self.add_rule(user_id, rule)
			return {"written": rid is not None, "reason": None if rid else "write_failed", "rule": self._normalize_rule(user_id, rule), "matched_rule": None}
		finally:
			self.duplicate_distance_threshold = old_threshold

	def query_allow_history(self, user_id: str, *, app_context: Optional[str] = None, action: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
		rows = self.get_allow_history(user_id)
		out: List[Dict[str, Any]] = []
		for r in rows:
			if app_context and str(r.get("app_context", "")) != app_context:
				continue
			if action and str(r.get("action", "")) != action:
				continue
			out.append(r)
			if len(out) >= limit:
				break
		return out


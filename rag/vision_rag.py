"""Local screenshot → MiniCPM evidence → rule retrieval → per-region decision.

Use --evidence-json to replay a locally reviewed model response without a
running MiniCPM service. Printed results contain no raw OCR values.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from .decision import DecisionEngine
from .evidence import Evidence
from .retriever import RuleRetriever
from .semantic import SemanticRuleRetriever


VISION_PROMPT = """请只在本机分析这张截图，输出一个 JSON 对象，不要 Markdown。
字段：app, page, task, recipient, recipient_trust, pii_types, sensitivities,
regions（每项包含 text, pii_type, bbox=[左,上,右,下], confidence）, model_confidence。
识别手机号、住址、姓名、聊天正文、人脸等敏感区域；bbox 必须是原图像素坐标。
不要做 ALLOW/MASK/ASK 决策，也不要猜测看不清的文字；不确定的类型写 unknown_sensitive。
recipient 指截图将要提供给谁；如果截图中无法判断，写 unknown。
"""


def _json_object(value: str) -> dict[str, Any]:
    raw = value.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Vision response must be a JSON object")
    return parsed


def call_minicpm(image: Path, url: str) -> dict[str, Any]:
    import requests

    with image.open("rb") as stream:
        response = requests.post(url, data={"prompt": VISION_PROMPT},
                                 files={"image": (image.name, stream, "image/jpeg")}, timeout=180)
    response.raise_for_status()
    body = response.json()
    if body.get("status") != "success":
        raise RuntimeError(f"MiniCPM service error: {body.get('message', 'unknown')}")
    return _json_object(body["response"])


def validate_evidence(image: Path, payload: dict[str, Any], recipient: str | None = None) -> Evidence:
    from PIL import Image

    if recipient:
        payload = {**payload, "recipient": recipient}
    evidence = Evidence.from_dict(payload)
    with Image.open(image) as source:
        width, height = source.size
    if not 0 <= evidence.model_confidence <= 1:
        raise ValueError("model_confidence must be in [0, 1]")
    for region in evidence.regions:
        if len(region.bbox) != 4:
            raise ValueError(f"Missing bbox for {region.pii_type}")
        x1, y1, x2, y2 = region.bbox
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            raise ValueError(f"Invalid bbox for {region.pii_type}")
        if not 0 <= region.confidence <= 1:
            raise ValueError(f"Invalid confidence for {region.pii_type}")
    located = {region.pii_type for region in evidence.regions}
    if not set(evidence.pii_types).issubset(located):
        raise ValueError("Every pii_type needs a located region")
    return evidence


def _judge_fields(url: str, evidence: Evidence, candidates: list[list[dict]]) -> list[dict]:
    """Ask the on-device model to choose only from retrieved rule IDs."""
    import requests

    cases = [{"index": i, "pii_type": region.pii_type,
              "rules": rules} for i, (region, rules) in enumerate(zip(evidence.regions, candidates))]
    prompt = ("只根据给出的证据标签与候选规则决定每个 index 的动作。"
              "输出 JSON：{\"decisions\":[{\"index\":0,\"action\":\"MASK\",\"rule_id\":\"...\"}]}。"
              "action 仅可为 ALLOW/MASK/ASK；rule_id 必须来自该 index 候选规则。"
              "候选不足时用 ASK 和 null rule_id。不要使用未给出的信息。\n"
              + json.dumps({"app": evidence.app, "page": evidence.page, "task": evidence.task,
                            "recipient": evidence.recipient, "fields": cases}, ensure_ascii=False))
    response = requests.post(url, data={"prompt": prompt}, timeout=180)
    response.raise_for_status()
    body = response.json()
    if body.get("status") != "success":
        raise RuntimeError(f"Local judge error: {body.get('message', 'unknown')}")
    parsed = _json_object(body["response"])
    decisions = parsed.get("decisions")
    if not isinstance(decisions, list):
        raise ValueError("Judge response requires decisions list")
    return decisions


def analyze(evidence: Evidence, retriever: RuleRetriever | None = None,
            judge_url: str | None = None,
            judge: Callable[[Evidence, list[list[dict]]], list[dict]] | None = None) -> dict[str, Any]:
    engine = DecisionEngine(retriever)
    fields = []
    candidate_groups = []
    for region in evidence.regions:
        single = replace(evidence, pii_types=[region.pii_type], regions=[region])
        decision = engine.decide(single)
        candidates = engine.retriever.retrieve(single, top_k=8, min_score=engine.min_match_score)
        candidate_groups.append([{"rule_id": item.rule.rule_id, "action": item.rule.action,
                                  "description": item.rule.description} for item in candidates])
        fields.append({"pii_type": region.pii_type, "bbox": region.bbox,
                       "action": decision.action, "rule_id": decision.selected_rule_id,
                       "score": round(decision.confidence, 3)})
    if (judge_url or judge) and fields:
        proposed = judge(evidence, candidate_groups) if judge else _judge_fields(judge_url, evidence, candidate_groups)
        by_index = {item.get("index"): item for item in proposed if isinstance(item, dict)}
        for index, field in enumerate(fields):
            item = by_index.get(index, {})
            selected = next((rule for rule in candidate_groups[index]
                             if rule["rule_id"] == item.get("rule_id") and
                             rule["action"] == item.get("action")), None)
            if selected and (item["action"] != "ALLOW" or field["action"] == "ALLOW"):
                field["action"], field["rule_id"] = item["action"], item["rule_id"]
            else:
                field["action"], field["rule_id"] = "ASK", None
    if evidence.model_confidence < 0.6 or any(region.confidence < 0.5 for region in evidence.regions):
        action = "ASK"
    elif any(field["action"] == "ASK" for field in fields):
        action = "ASK"
    elif any(field["action"] == "MASK" for field in fields):
        action = "MASK"
    else:
        action = "ALLOW"
    # ASK means the screenshot must not be forwarded, even if some boxes are known.
    return {"action": action, "app": evidence.app, "page": evidence.page,
            "recipient": evidence.recipient, "fields": fields,
            "regions_to_mask": [f for f in fields if f["action"] == "MASK"] if action == "MASK" else [],
            "retrieval": "semantic" if isinstance(engine.retriever, SemanticRuleRetriever) else "metadata_lexical",
            "judgement": "cloud_model" if judge else ("local_model" if judge_url else "deterministic")}


def main() -> None:
    parser = argparse.ArgumentParser(description="Local screenshot privacy RAG")
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--evidence-json", type=Path,
                        help="locally reviewed MiniCPM JSON; skips live vision inference")
    parser.add_argument("--minicpm-url", default="http://127.0.0.1:8000/chat")
    parser.add_argument("--embedding-model", type=Path,
                        help="existing local SentenceTransformer model directory")
    parser.add_argument("--recipient", help="downstream recipient override, e.g. 第三方")
    parser.add_argument("--judge-url", help="optional local text judge /chat URL")
    parser.add_argument("--no-judge", action="store_true", help="use deterministic decisions")
    args = parser.parse_args()
    payload = (_json_object(args.evidence_json.read_text(encoding="utf-8"))
               if args.evidence_json else call_minicpm(args.image, args.minicpm_url))
    evidence = validate_evidence(args.image, payload, args.recipient)
    retriever = SemanticRuleRetriever(args.embedding_model) if args.embedding_model else RuleRetriever()
    judge_url = None if args.no_judge or args.evidence_json else args.minicpm_url
    if args.judge_url:
        judge_url = args.judge_url
    print(json.dumps(analyze(evidence, retriever, judge_url), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

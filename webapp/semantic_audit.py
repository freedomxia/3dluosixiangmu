from __future__ import annotations

import json
from typing import Any

from webapp.model_client import OpenAICompatibleClient, VisionImage
from webapp.parsing import parse_json_object


PROMPT_AUDIT_SYSTEM = """
你是皓月3D提示词的独立语义审查器。你不是提示词作者，不接受草稿自报的 PASS，
必须重新查看图1需求图、图2风格图、任务分类、丰富趣味开关和完整草稿。
只输出一个 JSON 对象，不要 Markdown，不要改写提示词。

输出契约：
{
  "pass": false,
  "errors": [{"code": "稳定错误码", "message": "中文说明", "evidence": "草稿中的短证据或缺失位置"}],
  "warnings": [{"code": "稳定警告码", "message": "中文说明", "evidence": "短证据"}],
  "summary": "一句结论",
  "checks": {
    "hard_requirements": "pass | fail | n/a",
    "reference_scope": "pass | fail | n/a",
    "layout_permission": "pass | fail | n/a",
    "enrichment_event": "pass | fail | n/a",
    "reachability": "pass | fail | n/a",
    "clustering": "pass | fail | n/a",
    "positive_prompt_coverage": "pass | fail | n/a"
  }
}

硬门禁：
- 丰富开启且不是严格复刻时，创意方向为空或 N/A：ENRICHMENT_NA_FORBIDDEN。
- 创意只有材质、颜色、圆角、厚度、包边、拼缝、结构收口或硬修改复述：CREATIVE_ONLY_MATERIAL。
- 角色场景没有“发起者—对象—可见反馈”，无角色场景没有功能输入—处理—反馈：CREATIVE_NO_EVENT。
- 动作需拉长肢体、跨越原间距/阻挡、移动冻结角色或物件才成立：CREATIVE_UNREACHABLE。
- 多个分散动作没有同一因果链：CREATIVE_SCATTERED_ACTIONS。
- 创意方向没有以同一对象、动作和反馈进入正向提示词：CREATIVE_NOT_IN_POSITIVE_PROMPT。
- 同时要求姿态/朝向完全不变和转头/伸手/重心变化，或位置不变同时重新聚拢：CREATIVE_LAYOUT_CONFLICT。
- 重构任务只有“紧凑”形容词，没有共同底座和实体接触链，或形成物件岛：CREATIVE_CLUSTERING_FAILED。
- 局部参考目标集合、原位置、数量、连接或不扩散范围不清：TARGET_SCOPE_AMBIGUOUS；已扩散：TARGET_SCOPE_SPREAD。
- 图1红线删除目标及残留/收口未进入正向提示词：REDLINE_DELETE_MISSING。
- 硬修改被通用材质、背景或重复禁令稀释：PROMPT_DILUTION。

某条条件新增不安全只代表跳过该条，不能据此豁免默认丰富。LOCK_LAYOUT_EDIT 不得为聚拢而重排；
它的创意必须使用既有对象在原占位内自然可达。图2的内容不得进入画面。
PROJECT-BG 是全任务 L0 强制规则：删除图1外部森林、天空、街景、房间、远景、无边界草地等环境，
并改为单一中性灰无缝建模展示背景，永远不属于 TARGET_SCOPE_SPREAD 或布局越权；
有边界且承托主体的有限底座仍须保留。局部参考范围门禁只审查主体模型构件、角色、材质和附着内容的扩散。
只要 errors 非空，pass 必须为 false；pass 为 true 时 errors 必须为空。
""".strip()


IMAGE_AUDIT_SYSTEM = """
你是皓月3D生成结果的独立需求符合度审查器。输入依次为图1需求图和本轮生成结果图；
正向提示词是已审查的目标终态。PixPark平台内容审核通过不等于需求符合度通过。
逐张比较硬修改、红线删除、角色/物件数量、局部参考范围、布局权限、创意事件、
聚拢与共同承托、灰色背景、文字/Logo和可建接触。只输出 JSON，不要 Markdown，
不要自动要求重生，也不要把结果图当新参考。

输出契约：
{
  "pass": false,
  "errors": [{"code": "稳定错误码", "message": "中文说明", "evidence": "可见证据"}],
  "warnings": [{"code": "稳定警告码", "message": "中文说明", "evidence": "可见证据"}],
  "summary": "一句总判断或最小修正方向",
  "per_image": [{"index": 1, "pass": false, "errors": [{"code": "错误码", "message": "说明", "evidence": "证据"}]}],
  "best_indices": [1]
}

每张图都必须有 per_image 条目，index 从1开始。整体 pass 只在至少一张结果满足全部硬要求时为 true；
errors 记录四张共有的关键失败。不得用画面好看抵消硬要求遗漏。
""".strip()


async def audit_prompt(
    client: OpenAICompatibleClient,
    *,
    classification: dict[str, Any],
    enrichment_enabled: bool,
    note: str,
    draft: str,
    images: list[VisionImage],
) -> dict[str, Any]:
    user_text = (
        "独立审查下面这版完整交付。第一张图是图1需求图，第二张图是图2风格图。\n"
        f"任务分类：{json.dumps(classification, ensure_ascii=False)}\n"
        f"ENRICHMENT_ENABLED={'true' if enrichment_enabled else 'false'}\n"
        f"用户补充：{note or '无'}\n\n"
        f"待审草稿：\n{draft}"
    )
    raw = await client.complete(
        system_prompt=PROMPT_AUDIT_SYSTEM,
        user_text=user_text,
        images=images,
        temperature=0,
        max_tokens=4000,
    )
    return normalize_prompt_audit(parse_json_object(raw))


async def audit_generated_images(
    client: OpenAICompatibleClient,
    *,
    positive_prompt: str,
    note: str,
    source_image: VisionImage,
    generated_images: list[VisionImage],
) -> dict[str, Any]:
    user_text = (
        f"用户补充：{note or '无'}\n"
        f"已审查正向提示词：\n{positive_prompt}\n\n"
        f"图像顺序：第1张输入是图1需求图；之后依次是方案1至方案{len(generated_images)}。"
    )
    raw = await client.complete(
        system_prompt=IMAGE_AUDIT_SYSTEM,
        user_text=user_text,
        images=[source_image, *generated_images],
        temperature=0,
        max_tokens=5000,
    )
    return normalize_image_audit(
        parse_json_object(raw),
        expected_count=len(generated_images),
    )


def normalize_prompt_audit(value: dict[str, Any]) -> dict[str, Any]:
    errors = _normalize_findings(value.get("errors"), default_code="SEMANTIC_ERROR")
    warnings = _normalize_findings(value.get("warnings"), default_code="SEMANTIC_WARNING")
    checks_raw = value.get("checks")
    checks: dict[str, str] = {}
    if isinstance(checks_raw, dict):
        for key, item in checks_raw.items():
            status = str(item).strip().lower()
            if status not in {"pass", "fail", "n/a"}:
                status = "fail"
            checks[str(key)] = status

    claimed_pass = bool(value.get("pass"))
    failed_check = any(item == "fail" for item in checks.values())
    if not claimed_pass and not errors:
        errors.append(
            {
                "code": "SEMANTIC_REVIEW_INCOMPLETE",
                "message": "审查器拒绝草稿但没有提供可修正的错误。",
                "evidence": "pass=false 且 errors 为空",
            }
        )
    if claimed_pass and failed_check and not errors:
        errors.append(
            {
                "code": "SEMANTIC_CHECK_CONFLICT",
                "message": "审查结论与逐项门禁互相冲突。",
                "evidence": "checks 中存在 fail",
            }
        )
    passed = claimed_pass and not errors and not failed_check
    return {
        "status": "passed" if passed else "failed",
        "pass": passed,
        "errors": errors,
        "warnings": warnings,
        "summary": str(value.get("summary") or "独立语义审查未给出摘要。"),
        "checks": checks,
    }


def normalize_image_audit(
    value: dict[str, Any],
    *,
    expected_count: int,
) -> dict[str, Any]:
    errors = _normalize_findings(value.get("errors"), default_code="IMAGE_REQUIREMENT_ERROR")
    warnings = _normalize_findings(value.get("warnings"), default_code="IMAGE_REQUIREMENT_WARNING")
    rows: list[dict[str, Any]] = []
    raw_rows = value.get("per_image")
    if isinstance(raw_rows, list):
        by_index: dict[int, dict[str, Any]] = {}
        for raw in raw_rows:
            if not isinstance(raw, dict):
                continue
            try:
                index = int(raw.get("index"))
            except (TypeError, ValueError):
                continue
            if index < 1 or index > expected_count or index in by_index:
                continue
            item_errors = _normalize_findings(
                raw.get("errors"), default_code="IMAGE_REQUIREMENT_ERROR"
            )
            by_index[index] = {
                "index": index,
                "pass": bool(raw.get("pass")) and not item_errors,
                "errors": item_errors,
            }
        rows = [
            by_index.get(
                index,
                {
                    "index": index,
                    "pass": False,
                    "errors": [
                        {
                            "code": "IMAGE_AUDIT_MISSING",
                            "message": "该方案缺少独立审查结论。",
                            "evidence": "per_image 条目缺失",
                        }
                    ],
                },
            )
            for index in range(1, expected_count + 1)
        ]

    if len(rows) != expected_count:
        rows = [
            {
                "index": index,
                "pass": False,
                "errors": [
                    {
                        "code": "IMAGE_AUDIT_MISSING",
                        "message": "该方案缺少独立审查结论。",
                        "evidence": "per_image 结构不完整",
                    }
                ],
            }
            for index in range(1, expected_count + 1)
        ]

    passing = [row["index"] for row in rows if row["pass"]]
    raw_best = value.get("best_indices")
    best_indices: list[int] = []
    if isinstance(raw_best, list):
        for item in raw_best:
            try:
                index = int(item)
            except (TypeError, ValueError):
                continue
            if index in passing and index not in best_indices:
                best_indices.append(index)
    if not best_indices:
        best_indices = passing

    passed = bool(value.get("pass")) and bool(passing) and not errors
    return {
        "status": "passed" if passed else "failed",
        "pass": passed,
        "errors": errors,
        "warnings": warnings,
        "summary": str(value.get("summary") or "结果图需求符合度审查未给出摘要。"),
        "per_image": rows,
        "best_indices": best_indices,
    }


def _normalize_findings(value: Any, *, default_code: str) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    findings: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, str):
            message = item.strip()
            if message:
                findings.append(
                    {"code": default_code, "message": message, "evidence": ""}
                )
            continue
        if not isinstance(item, dict):
            continue
        message = str(item.get("message") or "").strip()
        if not message:
            continue
        code = str(item.get("code") or default_code).strip().upper()
        findings.append(
            {
                "code": code,
                "message": message,
                "evidence": str(item.get("evidence") or "").strip(),
            }
        )
    return findings

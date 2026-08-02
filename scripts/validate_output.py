#!/usr/bin/env python3
"""Validate deterministic parts of a haoyue-3d-concept delivery."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


MAIN_TITLE = "纯净生图提示词复制区"
NEGATIVE_TITLE = "纯净负面提示词复制区"
CREATIVE_TITLE = "创意方向"

INTERNAL_TOKENS = (
    "TASK_TYPE",
    "RECOMPOSE_SCENE",
    "LOCK_LAYOUT_EDIT",
    "STRICT_REPLICA",
    "FREEZE",
    "EDITABLE",
    "PROMPT_AUDIT",
    "PASS",
    "BLOCKED",
    "SKILL",
    "需求解析表",
    "图像职责绑定",
    "项目路径",
    "Skill自动匹配",
    "Skill 自动匹配",
)

PATH_PATTERNS = (
    r"/Users/",
    r"[A-Za-z]:\\",
    r"\.(?:png|jpe?g|webp|gif|md)(?:\b|$)",
)

ANNIVERSARY_PATTERNS = (
    r"周年",
    r"\banniversary\b",
    r"\b\d+(?:st|nd|rd|th)\b",
)


def extract_code_block(text: str, title: str) -> str | None:
    heading = re.search(
        rf"^#{{1,6}}\s*(?:\d+[.)、]\s*)?{re.escape(title)}\s*$",
        text,
        flags=re.MULTILINE,
    )
    if not heading:
        return None
    tail = text[heading.end() :]
    block = re.search(r"```(?:text|markdown)?[ \t]*\n(.*?)\n```", tail, flags=re.DOTALL)
    return block.group(1).strip() if block else None


def extract_section(text: str, title: str) -> str | None:
    heading = re.search(
        rf"^#{{1,6}}\s*(?:\d+[.)、]\s*)?{re.escape(title)}\s*$",
        text,
        flags=re.MULTILINE,
    )
    if not heading:
        return None
    tail = text[heading.end() :]
    next_heading = re.search(r"^#{1,6}\s+", tail, flags=re.MULTILINE)
    end = next_heading.start() if next_heading else len(tail)
    return tail[:end].strip()


def validate_block(
    block: str,
    *,
    label: str,
    require_image_contract: bool,
    require_gray_background: bool,
    allow_aspect_ratio: bool,
    anniversary_source: str,
) -> list[str]:
    errors: list[str] = []

    if not block:
        return [f"{label}为空"]

    if re.search(r"图\s*[3-9](?!\d)", block):
        errors.append(f"{label}引用了图3或更高图号")

    if require_image_contract:
        if "图1" not in block:
            errors.append(f"{label}缺少图1职责")
        if "图2" not in block:
            errors.append(f"{label}缺少图2风格职责")

    if require_gray_background:
        for term in ("中性灰", "无缝", "建模展示背景"):
            if term not in block:
                errors.append(f"{label}缺少背景硬词：{term}")

    for token in INTERNAL_TOKENS:
        if token.isascii():
            found = re.search(rf"\b{re.escape(token)}\b", block) is not None
        else:
            found = token in block
        if found:
            errors.append(f"{label}泄露内部字段：{token}")

    if re.search(r"\{[^{}\n]+\}", block):
        errors.append(f"{label}残留花括号占位符")

    if re.search(r"^#{1,6}\s|^\s*[-*+]\s|^\s*\d+[.)、]\s", block, flags=re.MULTILINE):
        errors.append(f"{label}不是连续自然语言，含标题或列表")

    for pattern in PATH_PATTERNS:
        if re.search(pattern, block, flags=re.IGNORECASE):
            errors.append(f"{label}包含文件路径或文件名")
            break

    if not allow_aspect_ratio and re.search(r"(?:生成\s*)?1\s*[:：]\s*1", block):
        errors.append(f"{label}含未经允许的1:1画幅标志")

    if anniversary_source == "forbidden":
        for pattern in ANNIVERSARY_PATTERNS:
            if re.search(pattern, block, flags=re.IGNORECASE):
                errors.append(f"{label}出现无来源周年内容")
                break

    return errors


def validate_document(
    text: str,
    *,
    require_negative: bool,
    allow_aspect_ratio: bool,
    anniversary_source: str,
    task_type: str | None = None,
    enrichment_enabled: bool = False,
) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []

    main = extract_code_block(text, MAIN_TITLE)
    if main is None:
        errors.append(f"缺少“{MAIN_TITLE}”标题或其代码块")
    else:
        errors.extend(
            validate_block(
                main,
                label="主提示词复制区",
                require_image_contract=True,
                require_gray_background=True,
                allow_aspect_ratio=allow_aspect_ratio,
                anniversary_source=anniversary_source,
            )
        )

    negative = extract_code_block(text, NEGATIVE_TITLE)
    if require_negative and negative is None:
        errors.append(f"缺少“{NEGATIVE_TITLE}”标题或其代码块")
    elif negative is not None:
        errors.extend(
            validate_block(
                negative,
                label="负面提示词复制区",
                require_image_contract=False,
                require_gray_background=False,
                allow_aspect_ratio=allow_aspect_ratio,
                anniversary_source="unknown",
            )
        )

    main_heading_count = len(
        re.findall(
            rf"^#{{1,6}}\s*(?:\d+[.)、]\s*)?{re.escape(MAIN_TITLE)}\s*$",
            text,
            flags=re.MULTILINE,
        )
    )
    if main_heading_count > 1:
        warnings.append("检测到多个主提示词复制区标题，请人工确认只交付一个最终版本")

    if enrichment_enabled and task_type != "STRICT_REPLICA":
        creative = extract_section(text, CREATIVE_TITLE)
        if creative is None:
            errors.append("[ENRICHMENT_NA_FORBIDDEN] 丰富趣味开启时缺少“创意方向”章节")
        else:
            normalized = re.sub(r"[\s`*_：:。；;，,（）()]", "", creative).upper()
            if normalized in {"", "N/A", "NA", "不适用", "无"}:
                errors.append(
                    "[ENRICHMENT_NA_FORBIDDEN] 丰富趣味开启且非严格复刻时，创意方向不得为 N/A"
                )

    return {
        "pass": not errors,
        "errors": errors,
        "warnings": warnings,
    }


def read_input(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="检查皓月3D提示词交付中的机械硬门禁。"
    )
    parser.add_argument("input", help="待检查的Markdown文件；使用 - 从stdin读取")
    parser.add_argument(
        "--skip-negative",
        action="store_true",
        help="当前任务明确不需要正式负面提示词时使用",
    )
    parser.add_argument(
        "--task-type",
        choices=("RECOMPOSE_SCENE", "LOCK_LAYOUT_EDIT", "ASSET", "STRICT_REPLICA"),
        default=None,
        help="任务类型；与 --enrichment-enabled 共同启用确定性丰富门禁",
    )
    parser.add_argument(
        "--enrichment-enabled",
        action="store_true",
        help="本轮开启丰富趣味",
    )
    parser.add_argument(
        "--allow-aspect-ratio",
        action="store_true",
        help="用户本轮明确要求显示1:1时使用",
    )
    parser.add_argument(
        "--anniversary-source",
        choices=("allowed", "forbidden", "unknown"),
        default="unknown",
        help="周年来源状态；forbidden会拒绝主提示词中的周年内容",
    )
    parser.add_argument("--json", action="store_true", help="输出JSON结果")
    args = parser.parse_args()

    try:
        text = read_input(args.input)
    except (OSError, UnicodeError) as exc:
        result = {"pass": False, "errors": [f"读取失败：{exc}"], "warnings": []}
    else:
        result = validate_document(
            text,
            require_negative=not args.skip_negative,
            allow_aspect_ratio=args.allow_aspect_ratio,
            anniversary_source=args.anniversary_source,
            task_type=args.task_type,
            enrichment_enabled=args.enrichment_enabled,
        )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        status = "PASS" if result["pass"] else "FAIL"
        print(status)
        for error in result["errors"]:
            print(f"ERROR: {error}")
        for warning in result["warnings"]:
            print(f"WARN: {warning}")

    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

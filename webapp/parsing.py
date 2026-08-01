from __future__ import annotations

import json
import re
from typing import Any


DELIVERY_HEADINGS = (
    "识别到的需求文字",
    "需求解析表",
    "双图职责与风格策略",
    "任务类型与布局权限",
    "创意方向",
    "纯净生图提示词复制区",
    "纯净负面提示词复制区",
    "提示词审查",
    "自检报告",
    "建模要点清单",
)


def parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("模型没有返回 JSON 对象")
        value = json.loads(text[start : end + 1])

    if not isinstance(value, dict):
        raise ValueError("模型返回的任务分类不是 JSON 对象")
    return value


def parse_markdown_sections(markdown: str) -> dict[str, str]:
    heading_pattern = re.compile(
        r"^#{1,6}\s*(?:\d+[.)、]\s*)?(" 
        + "|".join(re.escape(title) for title in DELIVERY_HEADINGS)
        + r")\s*$",
        flags=re.MULTILINE,
    )
    matches = list(heading_pattern.finditer(markdown))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        sections[match.group(1)] = markdown[start:end].strip()
    return sections


def strip_single_code_fence(value: str) -> str:
    match = re.fullmatch(
        r"```(?:text|markdown)?[ \t]*\n(.*?)\n```",
        value.strip(),
        flags=re.DOTALL,
    )
    return match.group(1).strip() if match else value.strip()

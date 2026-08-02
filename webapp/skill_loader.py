from __future__ import annotations

from pathlib import Path
from typing import Any


class SkillSourceError(RuntimeError):
    """Skill 文件缺失或不可读。"""


ALWAYS_REFERENCES = (
    "annotation-parsing.md",
    "prompt-contract.md",
    "prompt-audit.md",
)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise SkillSourceError(f"无法读取 Skill 规则：{path.name}") from exc


def build_skill_prompt(
    skill_root: Path,
    classification: dict[str, Any],
    *,
    enrichment_enabled: bool = False,
) -> str:
    skill_file = skill_root / "SKILL.md"
    references_dir = skill_root / "references"

    parts = [
        "以下内容是本任务唯一有效的 Skill 规则。严格执行，不要引用项目外资料。",
        f"\n\n===== SKILL.md =====\n{_read(skill_file)}",
    ]

    selected = list(ALWAYS_REFERENCES)
    task_type = classification.get("task_type")
    if task_type in {"LOCK_LAYOUT_EDIT", "STRICT_REPLICA"}:
        selected.append("layout-lock.md")
    elif task_type == "RECOMPOSE_SCENE":
        selected.append("recompose-scene.md")
        if classification.get("needs_creative_cases"):
            selected.append("creative-cases.md")

    triggers = classification.get("triggers") or {}
    if triggers.get("special_material"):
        selected.append("style-and-materials.md")
    if triggers.get("text_logo_time"):
        selected.append("text-logo-time.md")
    if triggers.get("haoyue_brand"):
        selected.append("brand-haoyue.md")
    if enrichment_enabled:
        selected.append("enrichment.md")

    for filename in dict.fromkeys(selected):
        parts.append(
            f"\n\n===== references/{filename} =====\n"
            f"{_read(references_dir / filename)}"
        )

    parts.append(
        "\n\n===== 运行要求 =====\n"
        "你正在网站后台执行该 Skill。只处理本次图1和用户本轮文字；"
        "第二张输入图片固定是图2风格参考图。"
        f"本轮丰富趣味开关为 ENRICHMENT_ENABLED={'true' if enrichment_enabled else 'false'}；"
        "该开关只能在完成需求终态与布局权限后生效。"
        "完成图文对照、自检和必要内部重写后，只输出 Skill 规定的最终 Markdown 交付，"
        "不要输出思考过程、JSON、寒暄或代码围栏外的额外说明。"
    )
    return "".join(parts)

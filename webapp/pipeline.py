from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import os
import shutil
import tempfile
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from scripts.validate_output import validate_document
from webapp.config import Settings
from webapp.model_client import (
    ModelAPIError,
    OpenAICompatibleClient,
    VisionImage,
)
from webapp.parsing import (
    parse_json_object,
    parse_markdown_sections,
    strip_single_code_fence,
)
from webapp.pixpark_client import (
    RESULT_IMAGE_COUNT,
    PixParkClient,
    PixParkError,
    PixParkRejected,
    PixParkStateStore,
    PixParkTimeout,
)
from webapp.skill_loader import SkillSourceError, build_skill_prompt

CLASSIFIER_PROMPT = """
你是皓月 3D 需求解析 Skill 的任务路由器。只分析当前上传的图1和用户补充文字，
不要生成最终提示词。严格输出一个 JSON 对象，不要 Markdown，不要解释。

字段契约：
{
  "task_type": "RECOMPOSE_SCENE | LOCK_LAYOUT_EDIT | ASSET | STRICT_REPLICA",
  "needs_creative_cases": false,
  "triggers": {
    "special_material": false,
    "text_logo_time": false,
    "haoyue_brand": false
  },
  "clarification": {
    "required": false,
    "reason": "none | unreadable_annotation | conflict | pending_asset | stale_time_value",
    "question": ""
  },
  "anniversary_source": "allowed | forbidden | unknown",
  "allow_aspect_ratio": false,
  "requested_aspect_ratio": "none | 1:1 | other | unknown",
  "routing_summary": "一句简短中文依据"
}

路由规则：
- 完整成熟效果图只改局部，选 LOCK_LAYOUT_EDIT。
- 严格复刻、只转材质、只换指定角色或部位，选 STRICT_REPLICA。
- 单体角色、产品、机械或道具，选 ASSET。
- 素材照、粗稿、散乱拼贴或明确要求重设计，选 RECOMPOSE_SCENE。
- 只有批注无法可靠识别、要求互相冲突、出现待提供内容、或时效数字可能过期时，
  clarification.required 才为 true，并只给一个用户可以直接回答的问题。
- 图中或补充文字出现特殊材质时触发 special_material。
- 出现文字、数字、周年、年份、期数、Logo 或徽章时触发 text_logo_time。
- 出现皓月螺丝小人、螺丝 Logo 或职业服装时触发 haoyue_brand。
- 用户明确要求画幅比例时 allow_aspect_ratio 为 true。
- 未要求画幅比例时 requested_aspect_ratio 为 none；明确要求 1:1 时为 1:1；
  明确要求其他比例时为 other；看不清或互相冲突时为 unknown。
""".strip()

logger = logging.getLogger(__name__)
ACTIVE_STATUSES = {
    "queued",
    "analyzing",
    "composing",
    "validating",
    "repairing",
    "generating_image",
    "needs_input",
}


class QueueCapacityError(RuntimeError):
    """当前任务队列已达到部署者配置的安全上限。"""


class JobStorageError(RuntimeError):
    """任务的临时持久化状态无法安全读写。"""


@dataclass
class JobRecord:
    id: str
    filename: str
    media_type: str
    image_bytes: bytes
    note: str
    enrichment_enabled: bool = False
    status: str = "queued"
    step: str = "等待处理"
    message: str = "任务已进入处理队列。"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    classification: dict[str, Any] | None = None
    question: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    clarification_rounds: int = 0
    source_path: Path | None = field(default=None, repr=False)
    recovery_action: str | None = field(default=None, repr=False)
    task: asyncio.Task[None] | None = field(default=None, repr=False)

    def public(self) -> dict[str, Any]:
        source_available = bool(
            self.image_bytes
            or (self.source_path is not None and self.source_path.is_file())
        )
        return {
            "id": self.id,
            "short_id": self.id[:8].upper(),
            "filename": self.filename,
            "media_type": self.media_type,
            "note": self.note,
            "enrichment_enabled": self.enrichment_enabled,
            "source_image_url": (
                f"/api/jobs/{self.id}/source-image" if source_available else None
            ),
            "status": self.status,
            "step": self.step,
            "message": self.message,
            "question": self.question,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class JobFileStore:
    """TTL-scoped task metadata and source images stored below the runtime dir."""

    VERSION = 1
    _MEDIA_EXTENSIONS: ClassVar[dict[str, str]] = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
    }

    def __init__(self, root: Path, *, ttl_seconds: int) -> None:
        self.root = root.expanduser().resolve()
        self.ttl_seconds = ttl_seconds
        try:
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.root.chmod(0o700)
        except OSError as exc:
            raise JobStorageError("无法创建任务临时存储目录。") from exc

    def create(self, record: JobRecord) -> None:
        directory = self._directory(record.id)
        extension = self._MEDIA_EXTENSIONS.get(record.media_type)
        if extension is None:
            raise JobStorageError("需求图格式不支持临时保存。")
        source_path = directory / f"source{extension}"
        try:
            directory.mkdir(mode=0o700)
            directory.chmod(0o700)
            self._atomic_write_bytes(source_path, record.image_bytes)
            record.source_path = source_path
            self.save(record)
        except (OSError, JobStorageError) as exc:
            shutil.rmtree(directory, ignore_errors=True)
            if isinstance(exc, JobStorageError):
                raise
            raise JobStorageError("无法保存任务需求图。") from exc

    def save(self, record: JobRecord) -> None:
        directory = self._directory(record.id)
        source_name = (
            record.source_path.name
            if record.source_path is not None
            and record.source_path.parent == directory
            else None
        )
        payload = {
            "version": self.VERSION,
            "id": record.id,
            "filename": record.filename,
            "media_type": record.media_type,
            "source_name": source_name,
            "note": record.note,
            "enrichment_enabled": record.enrichment_enabled,
            "status": record.status,
            "step": record.step,
            "message": record.message,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "classification": record.classification,
            "question": record.question,
            "result": record.result,
            "error": record.error,
            "clarification_rounds": record.clarification_rounds,
        }
        try:
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            self._atomic_write_text(
                directory / "metadata.json",
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            )
        except OSError as exc:
            raise JobStorageError("无法保存任务状态。") from exc

    def load(self) -> dict[str, JobRecord]:
        records: dict[str, JobRecord] = {}
        cutoff = time.time() - self.ttl_seconds
        try:
            directories = list(self.root.iterdir())
        except OSError as exc:
            raise JobStorageError("无法读取任务临时存储目录。") from exc

        for directory in directories:
            if (
                not directory.is_dir()
                or directory.is_symlink()
                or not self._valid_job_id(directory.name)
            ):
                continue
            metadata_path = directory / "metadata.json"
            try:
                payload = json.loads(metadata_path.read_text(encoding="utf-8"))
                record = self._record_from_payload(directory, payload)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                logger.warning("忽略损坏的任务状态：%s", directory.name)
                continue
            if record.updated_at < cutoff:
                self.delete(record.id)
                continue
            records[record.id] = record
        return records

    def delete(self, job_id: str) -> None:
        directory = self._directory(job_id)
        try:
            shutil.rmtree(directory, ignore_errors=False)
        except FileNotFoundError:
            return
        except OSError as exc:
            raise JobStorageError("无法清理过期任务文件。") from exc

    def _record_from_payload(
        self,
        directory: Path,
        payload: Any,
    ) -> JobRecord:
        if not isinstance(payload, dict):
            raise TypeError("invalid metadata")
        job_id = str(payload.get("id") or "")
        if job_id != directory.name or not self._valid_job_id(job_id):
            raise ValueError("invalid job id")
        updated_at = float(payload.get("updated_at"))
        created_at = float(payload.get("created_at"))
        source_name = payload.get("source_name")
        source_path: Path | None = None
        image_bytes = b""
        if isinstance(source_name, str) and Path(source_name).name == source_name:
            candidate = directory / source_name
            if candidate.is_file() and not candidate.is_symlink():
                source_path = candidate
                image_bytes = candidate.read_bytes()

        status = str(payload.get("status") or "failed")
        recovery_action = None
        if status in {"queued", "analyzing", "composing", "validating", "repairing"}:
            recovery_action = "model"
        elif status == "generating_image":
            recovery_action = "image"

        classification = payload.get("classification")
        result = payload.get("result")
        return JobRecord(
            id=job_id,
            filename=str(payload.get("filename") or "未命名需求图"),
            media_type=str(payload.get("media_type") or ""),
            image_bytes=image_bytes,
            note=str(payload.get("note") or ""),
            enrichment_enabled=bool(payload.get("enrichment_enabled")),
            status=status,
            step=str(payload.get("step") or "任务已恢复"),
            message=str(payload.get("message") or "任务状态已恢复。"),
            created_at=created_at,
            updated_at=updated_at,
            classification=(classification if isinstance(classification, dict) else None),
            question=(
                str(payload["question"])
                if payload.get("question") is not None
                else None
            ),
            result=result if isinstance(result, dict) else None,
            error=(str(payload["error"]) if payload.get("error") is not None else None),
            clarification_rounds=int(payload.get("clarification_rounds") or 0),
            source_path=source_path,
            recovery_action=recovery_action,
        )

    def _directory(self, job_id: str) -> Path:
        if not self._valid_job_id(job_id):
            raise JobStorageError("任务编号格式无效。")
        return self.root / job_id

    @staticmethod
    def _valid_job_id(job_id: str) -> bool:
        return len(job_id) == 32 and all(character in "0123456789abcdef" for character in job_id)

    @staticmethod
    def _atomic_write_bytes(path: Path, data: bytes) -> None:
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
                temporary = Path(handle.name)
            temporary.chmod(0o600)
            os.replace(temporary, path)
            path.chmod(0o600)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @classmethod
    def _atomic_write_text(cls, path: Path, text: str) -> None:
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
                temporary = Path(handle.name)
            temporary.chmod(0o600)
            os.replace(temporary, path)
            path.chmod(0o600)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


class JobManager:
    def __init__(
        self,
        settings: Settings,
        client: OpenAICompatibleClient | None = None,
        pixpark_factory: Callable[[Settings], PixParkClient] = PixParkClient,
        storage_dir: Path | None = None,
    ) -> None:
        self.settings = settings
        self.client = client or OpenAICompatibleClient(settings)
        self.pixpark_factory = pixpark_factory
        self.store = (
            JobFileStore(storage_dir, ttl_seconds=settings.job_ttl_seconds)
            if storage_dir is not None
            else None
        )
        self.jobs: dict[str, JobRecord] = self.store.load() if self.store else {}
        self.model_semaphore = asyncio.Semaphore(settings.max_concurrent_jobs)
        self.image_semaphore = asyncio.Semaphore(
            settings.max_concurrent_image_jobs
        )

    def create(
        self,
        *,
        filename: str,
        media_type: str,
        image_bytes: bytes,
        note: str,
        enrichment_enabled: bool = False,
    ) -> JobRecord:
        self._cleanup()
        if not self.settings.model_configured:
            raise ModelAPIError("管理员尚未配置模型 API。")
        if not self.settings.style_reference_configured:
            raise SkillSourceError(
                "管理员尚未配置固定的图2风格参考图。"
                "请将图片放到 config/style-reference.png，或设置 STYLE_REFERENCE_PATH。"
            )
        if self.active_count() >= self.settings.max_pending_jobs:
            raise QueueCapacityError("当前任务较多，请稍后再试。")

        record = JobRecord(
            id=uuid.uuid4().hex,
            filename=filename,
            media_type=media_type,
            image_bytes=image_bytes,
            note=note.strip(),
            enrichment_enabled=bool(enrichment_enabled),
        )
        self.jobs[record.id] = record
        try:
            if self.store:
                self.store.create(record)
        except JobStorageError:
            self.jobs.pop(record.id, None)
            raise
        record.task = asyncio.create_task(self._run(record))
        return record

    def start_recovered(self) -> None:
        for record in self.jobs.values():
            action = record.recovery_action
            record.recovery_action = None
            if action == "model":
                if not record.image_bytes:
                    self._fail(record, "服务重启后未找到原始需求图，无法继续处理。")
                    continue
                self._update(
                    record,
                    status="queued",
                    step="恢复处理",
                    message="服务已恢复，任务正在重新进入解析队列。",
                    error=None,
                )
                record.task = asyncio.create_task(self._run(record))
            elif action == "image":
                resumable = False
                try:
                    resumable = self.pixpark_factory(
                        self.settings
                    ).state_store.has_task(record.id)
                except PixParkError:
                    pass
                if resumable:
                    self._update(
                        record,
                        status="generating_image",
                        step="恢复结果图任务",
                        message="服务已恢复，正在继续查询原来的 PixPark 任务。",
                        error=None,
                    )
                    self._update_image(
                        record,
                        status="polling",
                        message="正在继续查询原来的 PixPark 任务。",
                        resumable=False,
                    )
                    record.task = asyncio.create_task(self._run_image_resume(record))
                else:
                    self._update_image(
                        record,
                        status="failed",
                        message=(
                            "服务重启时结果图任务尚未保存远端编号；"
                            "为避免重复扣费，未自动重新提交。"
                        ),
                        resumable=False,
                    )
                    self._complete(record)

    def get(self, job_id: str) -> JobRecord | None:
        self._cleanup()
        record = self.jobs.get(job_id)
        if record is not None:
            return record
        return self._recover_image_record(job_id)

    def active_count(self) -> int:
        self._cleanup()
        return sum(
            record.status in ACTIVE_STATUSES for record in self.jobs.values()
        )

    def history(self, *, limit: int = 30) -> list[dict[str, Any]]:
        self._cleanup()
        records = sorted(
            self.jobs.values(),
            key=lambda record: record.updated_at,
            reverse=True,
        )
        items: list[dict[str, Any]] = []
        for record in records[:limit]:
            image = (record.result or {}).get("image")
            image_status = image.get("status") if isinstance(image, dict) else None
            items.append(
                {
                    "id": record.id,
                    "short_id": record.id[:8].upper(),
                    "filename": record.filename,
                    "source_image_url": (
                        f"/api/jobs/{record.id}/source-image"
                        if record.source_path is not None
                        and record.source_path.is_file()
                        else None
                    ),
                    "status": record.status,
                    "step": record.step,
                    "message": record.message,
                    "created_at": record.created_at,
                    "updated_at": record.updated_at,
                    "has_prompt": bool(
                        (record.result or {}).get("positive_prompt")
                    ),
                    "image_status": image_status,
                }
            )
        return items

    def resume(self, job_id: str, answer: str) -> JobRecord:
        record = self.jobs.get(job_id)
        if record is None:
            raise KeyError(job_id)
        if record.status != "needs_input":
            raise ValueError("当前任务不需要补充信息。")
        answer = answer.strip()
        if not answer:
            raise ValueError("请填写补充信息。")
        if record.clarification_rounds >= self.settings.max_clarification_rounds:
            raise ValueError("补充次数已达上限，请返回修改需求图后重新提交。")

        record.note = (
            f"{record.note}\n针对追问的补充：{answer}".strip()
        )
        record.clarification_rounds += 1
        record.question = None
        record.classification = None
        self._update(
            record,
            status="queued",
            step="继续处理",
            message="已收到补充信息，正在重新解析。",
        )
        record.task = asyncio.create_task(self._run(record))
        return record

    def cancel(self, job_id: str) -> None:
        record = self.jobs.pop(job_id, None)
        if record is None:
            raise KeyError(job_id)
        record.image_bytes = b""
        if record.task and not record.task.done():
            record.task.cancel()
        if self.store:
            self.store.delete(job_id)

    def resume_image(self, job_id: str) -> JobRecord:
        record = self.get(job_id)
        if record is None:
            raise KeyError(job_id)
        if record.task and not record.task.done():
            raise ValueError("当前任务仍在处理中。")
        image = (record.result or {}).get("image")
        if not isinstance(image, dict) or not image.get("resumable"):
            raise ValueError("当前结果图没有可恢复的远端任务。")
        self._update(
            record,
            status="generating_image",
            step="继续生成结果图",
            message="正在继续查询原来的 PixPark 任务，不会重复提交。",
            error=None,
        )
        self._update_image(
            record,
            status="polling",
            message="正在继续查询原来的 PixPark 任务。",
            resumable=False,
        )
        record.task = asyncio.create_task(self._run_image_resume(record))
        return record

    def generate_image(self, job_id: str) -> JobRecord:
        record = self.jobs.get(job_id)
        if record is None:
            raise KeyError(job_id)
        if record.task and not record.task.done():
            raise ValueError("当前任务仍在处理中。")
        if not self.settings.image_generation_ready:
            raise ValueError("PixPark 当前未启用或尚未配置。")
        if record.status != "prompt_ready":
            raise ValueError("当前任务没有待确认的提示词。")
        image = (record.result or {}).get("image")
        if not isinstance(image, dict) or image.get("status") != "ready":
            raise ValueError("当前提示词不满足结果图生成条件。")
        if not record.image_bytes:
            raise ValueError("原始需求图已经释放，请重新上传后解析。")

        self._discard_previous_image_task(record.id)
        self._update(
            record,
            status="generating_image",
            step="生成结果图",
            message=f"已确认提示词，正在一次生成 {RESULT_IMAGE_COUNT} 张结果图。",
            error=None,
        )
        self._update_image(
            record,
            status="queued",
            message=f"等待 PixPark {RESULT_IMAGE_COUNT} 张图片队列。",
            resumable=False,
        )
        record.task = asyncio.create_task(self._run_image_generation(record))
        return record

    def regenerate_prompt(self, job_id: str) -> JobRecord:
        record = self.jobs.get(job_id)
        if record is None:
            raise KeyError(job_id)
        if record.task and not record.task.done():
            raise ValueError("当前任务仍在处理中。")
        if record.status not in {"prompt_ready", "complete"}:
            raise ValueError("当前任务还不能重新生成创意和提示词。")
        if not record.image_bytes:
            raise ValueError("原始需求图已经释放，请重新上传后解析。")

        record.classification = None
        record.question = None
        record.result = None
        record.error = None
        record.clarification_rounds = 0
        self._update(
            record,
            status="queued",
            step="重新生成创意与提示词",
            message="保留图1、补充要求和丰富趣味选项，正在重新走完整解析与审查。",
        )
        record.task = asyncio.create_task(self._run(record))
        return record

    def regenerate_image(self, job_id: str) -> JobRecord:
        record = self.jobs.get(job_id)
        if record is None:
            raise KeyError(job_id)
        if record.task and not record.task.done():
            raise ValueError("当前任务仍在处理中。")
        if not self.settings.image_generation_ready:
            raise ValueError("PixPark 当前未启用或尚未配置。")
        if record.status != "complete":
            raise ValueError("当前任务还没有可重新生成的结果图。")
        if not record.image_bytes:
            raise ValueError("原始需求图已经释放，请重新上传后解析。")
        if not str((record.result or {}).get("positive_prompt") or "").strip():
            raise ValueError("当前任务缺少已审查的正向提示词。")
        image = (record.result or {}).get("image")
        if not isinstance(image, dict):
            raise ValueError("当前任务缺少结果图状态。")
        if image.get("resumable"):
            raise ValueError("当前 PixPark 任务仍可继续查询，请先使用“继续查询原任务”。")

        self._discard_previous_image_task(record.id)
        self._update(
            record,
            status="generating_image",
            step="重新生成结果图",
            message=(
                f"保留已确认提示词，正在创建一组新的 "
                f"{RESULT_IMAGE_COUNT} 张结果图。"
            ),
            error=None,
        )
        self._update_image(
            record,
            status="queued",
            message=f"等待新的 PixPark {RESULT_IMAGE_COUNT} 张图片队列。",
            url=None,
            urls=[],
            count=0,
            resumable=False,
        )
        record.task = asyncio.create_task(self._run_image_generation(record))
        return record

    def _discard_previous_image_task(self, job_id: str) -> None:
        PixParkStateStore(
            self.settings.generated_dir / "pixpark-state"
        ).discard(job_id)

    def _recover_image_record(self, job_id: str) -> JobRecord | None:
        try:
            state = PixParkStateStore(
                self.settings.generated_dir / "pixpark-state"
            ).read(job_id)
        except PixParkError:
            return None

        task_code = str(state.get("taskCode") or "").strip()
        if not task_code:
            return None

        remote_status = str(state.get("status") or "").strip().lower()
        raw_output_names = state.get("outputNames")
        if isinstance(raw_output_names, list):
            output_names = [
                str(name).strip()
                for name in raw_output_names
                if str(name).strip()
            ]
        else:
            legacy_output = str(state.get("outputName") or "").strip()
            output_names = [legacy_output] if legacy_output else []
        outputs_are_safe = bool(output_names) and all(
            Path(name).name == name
            and Path(name).suffix.lower() in {".png", ".jpg", ".webp"}
            and (self.settings.generated_dir / name).is_file()
            for name in output_names
        )
        image_urls = (
            [f"/generated/{name}" for name in output_names]
            if outputs_are_safe
            else []
        )

        if remote_status == "rejected":
            image_status = "rejected"
            image_message = "远端任务已结束，且没有审核通过的结果图。"
            resumable = False
        elif image_urls:
            image_status = (
                "completed"
                if len(image_urls) >= RESULT_IMAGE_COUNT
                else "partial"
            )
            image_message = (
                f"已从持久化任务状态恢复 {len(image_urls)} 张结果图。"
            )
            resumable = False
        else:
            image_status = (
                "timeout"
                if remote_status in {"created", "polling", "timeout"}
                else "failed"
            )
            image_message = (
                "服务曾中断，但远端任务编号已保存；"
                "可继续查询同一个 PixPark 任务，不会重复创建。"
            )
            resumable = True

        record = JobRecord(
            id=job_id,
            filename="已恢复的结果图任务",
            media_type="",
            image_bytes=b"",
            note="",
            status="complete",
            step="已恢复结果图任务",
            message=image_message,
            result={
                "markdown": "",
                "positive_prompt": "",
                "negative_prompt": "",
                "sections": {},
                "validation": {"pass": True, "errors": []},
                "repair_attempts": 0,
                "recovered_image_only": True,
                "image": {
                    "status": image_status,
                    "url": image_urls[0] if image_urls else None,
                    "urls": image_urls,
                    "count": len(image_urls),
                    "expected_count": RESULT_IMAGE_COUNT,
                    "alt": "恢复查询后的 3D 建模参考结果组图",
                    "message": image_message,
                    "resumable": resumable,
                },
            },
        )
        self.jobs[job_id] = record
        self._persist(record)
        return record

    def cleanup_expired(self) -> None:
        self._cleanup()

    async def _run(self, record: JobRecord) -> None:
        try:
            async with self.model_semaphore:
                await self._classify(record)
                if record.status == "needs_input":
                    return
                await self._generate_prompt(record)
            self._complete_prompt(record)
        except asyncio.CancelledError:
            record.image_bytes = b""
            raise
        except ModelAPIError:
            logger.warning("模型服务调用失败", exc_info=True)
            self._fail(record, "模型服务暂时不可用，请稍后重新提交。")
        except SkillSourceError:
            logger.warning("Skill 或风格参考读取失败", exc_info=True)
            self._fail(record, "后台规则或风格参考暂时不可用，请联系管理员。")
        except ValueError:
            logger.warning("模型输出未通过处理要求", exc_info=True)
            self._fail(record, "模型输出未通过结构检查，请重新提交或联系管理员。")
        except Exception:
            logger.exception("任务处理出现未预期错误")
            self._fail(record, "服务发生未预期错误，请重新提交或联系管理员。")
        finally:
            record.task = None

    async def _classify(self, record: JobRecord) -> None:
        self._update(
            record,
            status="analyzing",
            step="读取需求图",
            message="正在识别批注、箭头、文字和布局权限。",
        )
        user_text = (
            "这是当前任务唯一的图1需求图。"
            f"\n用户补充文字：{record.note or '无'}"
        )
        raw = await self.client.complete(
            system_prompt=CLASSIFIER_PROMPT,
            user_text=user_text,
            images=[VisionImage(record.image_bytes, record.media_type)],
            temperature=0,
            max_tokens=1800,
        )
        classification = _normalize_classification(parse_json_object(raw))
        record.classification = classification

        clarification = classification["clarification"]
        if clarification["required"]:
            if (
                record.clarification_rounds
                >= self.settings.max_clarification_rounds
            ):
                raise ValueError("模型在补充后仍无法确认需求。")
            self._update(
                record,
                status="needs_input",
                step="需要一项补充",
                message="图片中有一处无法安全推断，请补充后继续。",
                question=clarification["question"],
            )

    async def _generate_prompt(self, record: JobRecord) -> None:
        assert record.classification is not None
        classification = record.classification
        skill_prompt = build_skill_prompt(
            self.settings.skill_root,
            classification,
            enrichment_enabled=record.enrichment_enabled,
        )
        style_image = _read_style_image(self.settings.style_reference_path)

        self._update(
            record,
            status="composing",
            step="生成建模提示词",
            message="正在按当前任务类型组装双图职责和可建结构。",
        )
        user_text = (
            "现在执行正式交付。\n"
            "第一张输入图片是图1完整需求图；第二张输入图片是图2固定人工建模风格参考图。\n"
            f"用户本轮补充文字：{record.note or '无'}\n"
            "运行选项："
            f"ENRICHMENT_ENABLED={'true' if record.enrichment_enabled else 'false'}。"
            "该选项不得覆盖图1批注、删除项、主体锁或布局权限。\n"
            "任务路由结果仅供执行规则选择，不得原样泄露到纯净复制区：\n"
            f"{json.dumps(classification, ensure_ascii=False)}"
        )
        images = [
            VisionImage(record.image_bytes, record.media_type),
            style_image,
        ]
        draft = await self.client.complete(
            system_prompt=skill_prompt,
            user_text=user_text,
            images=images,
        )

        attempts = 0
        validation: dict[str, Any]
        while True:
            self._update(
                record,
                status="validating",
                step="审查输出",
                message="正在检查图号、复制区、灰色背景和内部字段。",
            )
            validation = validate_document(
                draft,
                require_negative=True,
                allow_aspect_ratio=bool(classification["allow_aspect_ratio"]),
                anniversary_source=classification["anniversary_source"],
            )
            if validation["pass"] or attempts >= self.settings.repair_attempts:
                break

            attempts += 1
            self._update(
                record,
                status="repairing",
                step="自动修正",
                message=f"发现机械门禁问题，正在进行第 {attempts} 次修正。",
            )
            repair_text = (
                "上一版交付没有通过机械校验。重新查看图1和图2，"
                "保持已经正确的需求终态，只修复列出的错误，然后重新输出完整最终 Markdown。\n"
                f"校验错误：{json.dumps(validation['errors'], ensure_ascii=False)}\n\n"
                f"上一版交付：\n{draft}"
            )
            draft = await self.client.complete(
                system_prompt=skill_prompt,
                user_text=repair_text,
                images=images,
                temperature=0.05,
            )

        if not validation["pass"]:
            raise ValueError(
                "模型输出在自动修正后仍未通过校验："
                + "；".join(str(item) for item in validation["errors"])
            )

        sections = parse_markdown_sections(draft)
        positive = strip_single_code_fence(
            sections.get("纯净生图提示词复制区", "")
        )
        negative = strip_single_code_fence(
            sections.get("纯净负面提示词复制区", "")
        )

        record.result = {
            "markdown": draft,
            "positive_prompt": positive,
            "negative_prompt": negative,
            "sections": sections,
            "validation": validation,
            "repair_attempts": attempts,
            "image": {
                "status": self._initial_image_status(classification),
                "url": None,
                "urls": [],
                "count": 0,
                "expected_count": RESULT_IMAGE_COUNT,
                "alt": "本任务后续生成的 3D 建模参考结果组图",
                "message": self._initial_image_message(classification),
                "resumable": False,
            },
        }

    def _can_generate_image(self, record: JobRecord) -> bool:
        image = (record.result or {}).get("image")
        return isinstance(image, dict) and image.get("status") == "ready"

    def _initial_image_status(self, classification: dict[str, Any]) -> str:
        if not self.settings.image_generation_enabled:
            return "disabled"
        if not self.settings.pixpark_configured:
            return "unavailable"
        if classification.get("requested_aspect_ratio") == "other":
            return "incompatible_aspect_ratio"
        return "ready"

    def _initial_image_message(self, classification: dict[str, Any]) -> str:
        status = self._initial_image_status(classification)
        messages = {
            "disabled": "结果图生成未启用；提示词仍可正常使用。",
            "unavailable": "PixPark 尚未配置；提示词仍可正常使用。",
            "incompatible_aspect_ratio": (
                "用户要求的画幅不是 1:1，与当前 PixPark 固定接口不兼容，"
                "因此没有自动生图。"
            ),
            "ready": (
                "提示词已通过审查；请先人工核对，"
                f"确认后一次生成 {RESULT_IMAGE_COUNT} 张结果图。"
            ),
        }
        return messages[status]

    async def _run_image_generation(self, record: JobRecord) -> None:
        try:
            await self._generate_image(record)
        finally:
            record.task = None

    async def _generate_image(self, record: JobRecord) -> None:
        assert record.result is not None
        self._update(
            record,
            status="generating_image",
            step="生成结果图",
            message=f"提示词已通过审查，正在一次生成 {RESULT_IMAGE_COUNT} 张结果图。",
        )
        self._update_image(
            record,
            status="queued",
            message=f"等待 PixPark {RESULT_IMAGE_COUNT} 张图片队列。",
            resumable=False,
        )
        try:
            async with self.image_semaphore:
                client = self.pixpark_factory(self.settings)
                result = await client.generate(
                    job_id=record.id,
                    input_filename=record.filename,
                    input_media_type=record.media_type,
                    input_bytes=record.image_bytes,
                    prompt=str(record.result.get("positive_prompt") or ""),
                    on_status=lambda status, message: self._image_progress(
                        record, status, message
                    ),
                )
            self._apply_image_result(record, result)
        except PixParkTimeout as exc:
            self._update_image(
                record,
                status="timeout",
                message=str(exc),
                resumable=True,
            )
        except PixParkRejected as exc:
            self._update_image(
                record,
                status="rejected",
                message=str(exc),
                resumable=False,
            )
        except PixParkError as exc:
            resumable = False
            try:
                resumable = self.pixpark_factory(
                    self.settings
                ).state_store.has_task(record.id)
            except PixParkError:
                pass
            self._update_image(
                record,
                status="failed",
                message=str(exc),
                resumable=resumable,
            )
        except Exception:
            logger.exception("PixPark 图片阶段出现未预期错误")
            self._update_image(
                record,
                status="failed",
                message="结果图生成发生未预期错误；已完成的提示词不受影响。",
                resumable=False,
            )
        self._complete(record)

    async def _run_image_resume(self, record: JobRecord) -> None:
        try:
            async with self.image_semaphore:
                client = self.pixpark_factory(self.settings)
                result = await client.resume(
                    job_id=record.id,
                    on_status=lambda status, message: self._image_progress(
                        record, status, message
                    ),
                )
            self._apply_image_result(record, result)
        except asyncio.CancelledError:
            return
        except PixParkTimeout as exc:
            self._update_image(
                record,
                status="timeout",
                message=str(exc),
                resumable=True,
            )
        except PixParkRejected as exc:
            self._update_image(
                record,
                status="rejected",
                message=str(exc),
                resumable=False,
            )
        except PixParkError as exc:
            resumable = False
            try:
                resumable = self.pixpark_factory(
                    self.settings
                ).state_store.has_task(record.id)
            except PixParkError:
                pass
            self._update_image(
                record,
                status="failed",
                message=str(exc),
                resumable=resumable,
            )
        except Exception:
            logger.exception("PixPark 恢复查询出现未预期错误")
            self._update_image(
                record,
                status="failed",
                message="继续查询结果图时发生未预期错误。",
                resumable=False,
            )
        finally:
            self._complete(record)
            record.task = None

    def _image_progress(
        self,
        record: JobRecord,
        status: str,
        message: str,
    ) -> None:
        self._update(
            record,
            status="generating_image",
            step="生成结果图",
            message=message,
        )
        self._update_image(
            record,
            status=status,
            message=message,
            resumable=False,
        )

    def _apply_image_result(
        self,
        record: JobRecord,
        result: Any,
    ) -> None:
        filenames = tuple(
            name
            for name in getattr(result, "filenames", ())
            if isinstance(name, str) and name
        )
        if not filenames:
            raise PixParkError("PixPark 没有返回可展示的结果图文件。")
        urls = [f"/generated/{name}" for name in filenames]
        count = len(urls)
        status = (
            "completed" if count >= RESULT_IMAGE_COUNT else "partial"
        )
        message = (
            f"{count} 张结果图已生成并通过 PixPark 审核。"
            if status == "completed"
            else (
                f"PixPark 本次返回 {count}/{RESULT_IMAGE_COUNT} 张审核通过结果；"
                "已保留可用图片。"
            )
        )
        self._update_image(
            record,
            status=status,
            url=urls[0],
            urls=urls,
            count=count,
            expected_count=RESULT_IMAGE_COUNT,
            message=message,
            resumable=False,
        )

    def _update_image(self, record: JobRecord, **values: Any) -> None:
        if record.result is None:
            return
        image = record.result.setdefault("image", {})
        if not isinstance(image, dict):
            image = {}
            record.result["image"] = image
        image.update(values)
        record.updated_at = time.time()
        self._persist(record)

    def _complete(self, record: JobRecord) -> None:
        self._update(
            record,
            status="complete",
            step="结果图已更新",
            message="提示词与结果图已经关联到同一个任务。",
        )

    def _complete_prompt(self, record: JobRecord) -> None:
        self._update(
            record,
            status="prompt_ready",
            step="提示词待确认",
            message="提示词已通过结构检查；请先核对，确认后再生成结果图。",
        )

    def _update(self, record: JobRecord, **values: Any) -> None:
        for key, value in values.items():
            setattr(record, key, value)
        record.updated_at = time.time()
        self._persist(record)

    def _fail(self, record: JobRecord, error: str) -> None:
        self._update(
            record,
            status="failed",
            step="处理失败",
            message="本次任务没有生成结果。",
            error=error,
        )

    def _cleanup(self) -> None:
        cutoff = time.time() - self.settings.job_ttl_seconds
        expired = [
            job_id
            for job_id, record in self.jobs.items()
            if record.updated_at < cutoff
        ]
        for job_id in expired:
            record = self.jobs.pop(job_id)
            record.image_bytes = b""
            if record.task and not record.task.done():
                record.task.cancel()
            if self.store:
                try:
                    self.store.delete(job_id)
                except JobStorageError:
                    logger.warning("无法清理过期任务文件：%s", job_id, exc_info=True)

    def _persist(self, record: JobRecord) -> None:
        if not self.store:
            return
        try:
            self.store.save(record)
        except JobStorageError:
            logger.exception("任务状态持久化失败：%s", record.id)


def _read_style_image(path: Path) -> VisionImage:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise SkillSourceError("无法读取固定的图2风格参考图。") from exc
    media_type = mimetypes.guess_type(path.name)[0] or "image/png"
    if media_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise SkillSourceError("图2风格参考图必须是 PNG、JPEG 或 WebP。")
    return VisionImage(data=data, media_type=media_type)


def _normalize_classification(value: dict[str, Any]) -> dict[str, Any]:
    allowed_types = {
        "RECOMPOSE_SCENE",
        "LOCK_LAYOUT_EDIT",
        "ASSET",
        "STRICT_REPLICA",
    }
    task_type = value.get("task_type")
    if task_type not in allowed_types:
        raise ValueError("模型返回了无效的任务类型。")

    triggers = value.get("triggers")
    if not isinstance(triggers, dict):
        triggers = {}
    clarification = value.get("clarification")
    if not isinstance(clarification, dict):
        clarification = {}

    required = bool(clarification.get("required"))
    question = str(clarification.get("question") or "").strip()
    if required and not question:
        question = "请补充图片中无法确认的最终要求。"

    anniversary_source = value.get("anniversary_source", "unknown")
    if anniversary_source not in {"allowed", "forbidden", "unknown"}:
        anniversary_source = "unknown"

    return {
        "task_type": task_type,
        "needs_creative_cases": bool(value.get("needs_creative_cases")),
        "triggers": {
            "special_material": bool(triggers.get("special_material")),
            "text_logo_time": bool(triggers.get("text_logo_time")),
            "haoyue_brand": bool(triggers.get("haoyue_brand")),
        },
        "clarification": {
            "required": required,
            "reason": str(clarification.get("reason") or "none"),
            "question": question,
        },
        "anniversary_source": anniversary_source,
        "allow_aspect_ratio": bool(value.get("allow_aspect_ratio")),
        "requested_aspect_ratio": (
            value.get("requested_aspect_ratio")
            if value.get("requested_aspect_ratio")
            in {"none", "1:1", "other", "unknown"}
            else ("unknown" if value.get("allow_aspect_ratio") else "none")
        ),
        "routing_summary": str(value.get("routing_summary") or ""),
    }

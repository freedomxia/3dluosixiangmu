from __future__ import annotations

import asyncio
import io
import time
import warnings
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field

from webapp.config import (
    load_settings,
    public_configuration,
    runtime_config_store,
)
from webapp.model_client import ModelAPIError
from webapp.pipeline import JobManager, JobStorageError, QueueCapacityError
from webapp.skill_loader import SkillSourceError

settings = load_settings()


def _job_storage_dir() -> Path:
    return runtime_config_store(settings).path.parent / "jobs"


manager = JobManager(settings, storage_dir=_job_storage_dir())


class UploadBodyTooLarge(Exception):
    pass


class UploadBodyLimitMiddleware:
    def __init__(self, app, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send) -> None:
        path = scope.get("path", "")
        is_job_upload = path == "/api/jobs" or (
            path.startswith("/api/jobs/") and path.endswith("/revise")
        )
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or not is_job_upload
        ):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length:
            try:
                if int(content_length) > self.max_bytes:
                    await self._reject(scope, receive, send)
                    return
            except ValueError:
                pass

        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise UploadBodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except UploadBodyTooLarge:
            await self._reject(scope, receive, send)

    @staticmethod
    async def _reject(scope, receive, send) -> None:
        response = JSONResponse(
            {"detail": "上传内容超过服务器允许的大小。"},
            status_code=413,
        )
        await response(scope, receive, send)


class SubmissionRateLimiter:
    def __init__(self, limit: int, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.events: dict[str, deque[float]] = defaultdict(deque)
        self.lock = asyncio.Lock()

    async def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        async with self.lock:
            events = self.events[key]
            while events and events[0] < cutoff:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            return True


rate_limiter = SubmissionRateLimiter(settings.max_jobs_per_minute)
configuration_lock = asyncio.Lock()


async def _cleanup_loop() -> None:
    while True:
        await asyncio.sleep(60)
        manager.cleanup_expired()


@asynccontextmanager
async def lifespan(_: FastAPI):
    manager.start_recovered()
    cleanup_task = asyncio.create_task(_cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="皓月 3D 需求解析",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)
app.add_middleware(
    UploadBodyLimitMiddleware,
    max_bytes=settings.max_upload_mb * 1024 * 1024 + 1024 * 1024,
)

app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
app.mount(
    "/generated",
    StaticFiles(directory=settings.generated_dir, check_dir=False),
    name="generated",
)


class ResumeRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=1000)


class ServiceConfigRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    model_base_url: str = Field(min_length=1, max_length=2048)
    model_name: str = Field(min_length=1, max_length=200)
    model_api_key: str = Field(default="", max_length=8192)
    clear_model_api_key: bool = False
    pixpark_token: str = Field(default="", max_length=8192)
    clear_pixpark_token: bool = False
    image_generation_enabled: bool = False


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' blob: data:; "
        "style-src 'self'; script-src 'self'; connect-src 'self'; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    )
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(settings.static_dir / "index.html")


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok" if settings.ready else "degraded",
        "ready": settings.ready,
    }


@app.get("/ready")
async def ready() -> JSONResponse:
    status_code = 200 if settings.ready else 503
    return JSONResponse(
        {
            "status": "ready" if settings.ready else "not_ready",
            "ready": settings.ready,
        },
        status_code=status_code,
    )


@app.get("/api/status")
async def service_status() -> dict[str, object]:
    return {
        "ready": settings.ready,
        "model_configured": settings.model_configured,
        "style_reference_configured": settings.style_reference_configured,
        "image_generation_enabled": settings.image_generation_enabled,
        "pixpark_configured": settings.pixpark_configured,
        "image_generation_ready": settings.image_generation_ready,
        "max_upload_mb": settings.max_upload_mb,
        "max_image_dimension": settings.max_image_dimension,
    }


@app.get("/api/config")
async def get_service_config() -> dict[str, object]:
    return {
        **public_configuration(settings),
        "active_jobs": manager.active_count(),
        "max_upload_mb": settings.max_upload_mb,
        "max_image_dimension": settings.max_image_dimension,
    }


@app.post("/api/config")
async def update_service_config(
    body: ServiceConfigRequest,
) -> dict[str, object]:
    global settings, manager, rate_limiter

    parsed_url = urlsplit(body.model_base_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise HTTPException(
            status_code=422,
            detail="模型地址必须是完整的 http:// 或 https:// 地址。",
        )
    if parsed_url.username or parsed_url.password:
        raise HTTPException(
            status_code=422,
            detail="模型地址不能包含用户名或密码，请使用独立 API Key。",
        )
    if parsed_url.fragment:
        raise HTTPException(
            status_code=422,
            detail="模型地址不能包含 # 片段。",
        )
    if body.clear_model_api_key and body.model_api_key:
        raise HTTPException(
            status_code=422,
            detail="API Key 不能同时填写新值并选择清除。",
        )
    if body.clear_pixpark_token and body.pixpark_token:
        raise HTTPException(
            status_code=422,
            detail="PixPark Token 不能同时填写新值并选择清除。",
        )

    next_model_key = (
        "" if body.clear_model_api_key else body.model_api_key or settings.model_api_key
    )
    next_pixpark_token = (
        "" if body.clear_pixpark_token else body.pixpark_token or settings.pixpark_token
    )
    if body.image_generation_enabled and not next_pixpark_token:
        raise HTTPException(
            status_code=422,
            detail="启用结果图生成前，请先填写 PixPark Token。",
        )

    async with configuration_lock:
        active_jobs = manager.active_count()
        if active_jobs:
            raise HTTPException(
                status_code=409,
                detail=f"当前有 {active_jobs} 个任务未结束，请结束后再修改配置。",
            )
        store = runtime_config_store(settings)
        try:
            store.write(
                {
                    "MODEL_BASE_URL": body.model_base_url.rstrip("/"),
                    "MODEL_NAME": body.model_name,
                    "MODEL_API_KEY": next_model_key,
                    "PIX_PARK_TOKEN": next_pixpark_token,
                    "IMAGE_GENERATION_ENABLED": (
                        "true" if body.image_generation_enabled else "false"
                    ),
                }
            )
            next_settings = load_settings()
        except RuntimeError as exc:
            raise HTTPException(
                status_code=500,
                detail="配置未能安全保存，请检查生成目录权限。",
            ) from exc

        settings = next_settings
        next_manager = JobManager(settings, storage_dir=_job_storage_dir())
        next_manager.jobs = manager.jobs
        manager = next_manager
        rate_limiter = SubmissionRateLimiter(settings.max_jobs_per_minute)

    return {
        **public_configuration(settings),
        "active_jobs": 0,
        "max_upload_mb": settings.max_upload_mb,
        "max_image_dimension": settings.max_image_dimension,
        "message": "服务配置已保存并立即生效。",
    }


async def _read_verified_upload(image: UploadFile) -> tuple[str, str, bytes]:
    content_type = (image.content_type or "").lower()
    if content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(
            status_code=415,
            detail="只支持 PNG、JPEG 或 WebP 图片。",
        )

    data = await image.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"图片不能超过 {settings.max_upload_mb} MB。",
        )
    if not data:
        raise HTTPException(status_code=400, detail="上传的图片为空。")

    verified_media_type = _verify_image(data, content_type)
    return Path(image.filename or "需求图").name, verified_media_type, data


async def _enforce_submission_rate(request: Request) -> None:
    client_host = request.client.host if request.client else "unknown"
    if not await rate_limiter.allow(client_host):
        raise HTTPException(
            status_code=429,
            detail="提交过于频繁，请一分钟后再试。",
            headers={"Retry-After": "60"},
        )


@app.post("/api/jobs", status_code=202)
async def create_job(
    request: Request,
    image: UploadFile = File(...),
    note: str = Form(default="", max_length=1000),
    enrichment_enabled: bool = Form(default=False),
) -> dict[str, object]:
    await _enforce_submission_rate(request)
    filename, verified_media_type, data = await _read_verified_upload(image)

    try:
        record = manager.create(
            filename=filename,
            media_type=verified_media_type,
            image_bytes=data,
            note=note,
            enrichment_enabled=enrichment_enabled,
        )
    except QueueCapacityError as exc:
        raise HTTPException(
            status_code=429,
            detail=str(exc),
            headers={"Retry-After": "15"},
        ) from exc
    except JobStorageError as exc:
        raise HTTPException(
            status_code=507,
            detail="服务器无法安全保存任务，请检查运行目录空间和权限。",
        ) from exc
    except (ModelAPIError, SkillSourceError) as exc:
        raise HTTPException(
            status_code=503,
            detail="服务尚未完成后台配置，请联系管理员。",
        ) from exc
    return record.public()


@app.get("/api/jobs")
async def list_jobs(
    limit: int = Query(default=30, ge=1, le=100),
) -> dict[str, object]:
    return {"items": manager.history(limit=limit)}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, object]:
    record = manager.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="任务不存在或已经过期。")
    return record.public()


@app.get("/api/jobs/{job_id}/source-image")
async def get_job_source_image(job_id: str) -> FileResponse:
    record = manager.get(job_id)
    if (
        record is None
        or record.source_path is None
        or not record.source_path.is_file()
    ):
        raise HTTPException(status_code=404, detail="任务需求图不存在或已经过期。")
    return FileResponse(
        record.source_path,
        media_type=record.media_type,
        headers={"Content-Disposition": "inline"},
    )


@app.post("/api/jobs/{job_id}/revise", status_code=202)
async def revise_job(
    request: Request,
    job_id: str,
    image: UploadFile | None = File(default=None),
    note: str = Form(default="", max_length=1000),
    enrichment_enabled: bool = Form(default=False),
) -> dict[str, object]:
    await _enforce_submission_rate(request)
    replacement: tuple[str, str, bytes] | None = None
    if image is not None:
        replacement = await _read_verified_upload(image)

    try:
        record = manager.revise(
            job_id,
            filename=replacement[0] if replacement else None,
            media_type=replacement[1] if replacement else None,
            image_bytes=replacement[2] if replacement else None,
            note=note,
            enrichment_enabled=enrichment_enabled,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="原任务不存在或已经过期。") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except QueueCapacityError as exc:
        raise HTTPException(
            status_code=429,
            detail=str(exc),
            headers={"Retry-After": "15"},
        ) from exc
    except JobStorageError as exc:
        raise HTTPException(
            status_code=507,
            detail="服务器无法安全保存修订任务，请检查运行目录空间和权限。",
        ) from exc
    except (ModelAPIError, SkillSourceError) as exc:
        raise HTTPException(
            status_code=503,
            detail="服务尚未完成后台配置，请联系管理员。",
        ) from exc
    return record.public()


@app.post("/api/jobs/{job_id}/resume", status_code=202)
async def resume_job(job_id: str, body: ResumeRequest) -> dict[str, object]:
    try:
        record = manager.resume(job_id, body.answer)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="任务不存在或已经过期。") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return record.public()


@app.post("/api/jobs/{job_id}/image", status_code=202)
async def generate_image(job_id: str) -> dict[str, object]:
    try:
        record = manager.generate_image(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="任务不存在或已经过期。") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return record.public()


@app.post("/api/jobs/{job_id}/prompt/regenerate", status_code=202)
async def regenerate_prompt(job_id: str) -> dict[str, object]:
    try:
        record = manager.regenerate_prompt(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="任务不存在或已经过期。") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return record.public()


@app.post("/api/jobs/{job_id}/image/regenerate", status_code=202)
async def regenerate_image(job_id: str) -> dict[str, object]:
    try:
        record = manager.regenerate_image(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="任务不存在或已经过期。") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return record.public()


@app.post("/api/jobs/{job_id}/image/resume", status_code=202)
async def resume_image(job_id: str) -> dict[str, object]:
    try:
        record = manager.resume_image(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="任务不存在或已经过期。") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return record.public()


@app.delete("/api/jobs/{job_id}", status_code=204)
async def cancel_job(job_id: str) -> None:
    try:
        manager.cancel(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="任务不存在或已经结束。") from exc


def _verify_image(data: bytes, declared_media_type: str) -> str:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as opened:
                width, height = opened.size
                image_format = opened.format
                opened.verify()
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise HTTPException(status_code=400, detail="图片文件损坏或无法识别。") from exc

    media_types = {
        "PNG": "image/png",
        "JPEG": "image/jpeg",
        "WEBP": "image/webp",
    }
    verified_media_type = media_types.get(image_format or "")
    if verified_media_type is None:
        raise HTTPException(status_code=415, detail="图片格式不受支持。")
    if verified_media_type != declared_media_type:
        raise HTTPException(
            status_code=415,
            detail="图片内容与声明格式不一致，请重新导出后上传。",
        )
    if width < 320 or height < 320:
        raise HTTPException(
            status_code=400,
            detail="图片尺寸过小，请上传宽高至少 320 像素的完整需求图。",
        )
    if (
        width > settings.max_image_dimension
        or height > settings.max_image_dimension
        or width * height > settings.max_image_pixels
    ):
        raise HTTPException(
            status_code=400,
            detail="图片分辨率过大，请缩小后重新上传。",
        )
    return verified_media_type

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

RUNTIME_CONFIG_FILENAME = "runtime-settings.json"
RUNTIME_CONFIG_KEYS = {
    "MODEL_BASE_URL",
    "MODEL_API_KEY",
    "MODEL_NAME",
    "IMAGE_GENERATION_ENABLED",
    "PIX_PARK_TOKEN",
}


class RuntimeConfigStore:
    """Persist page-managed deployment settings without exposing their values."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def read(self) -> dict[str, str]:
        if not self.path.is_file():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("页面运行时配置文件损坏或无法读取。") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("页面运行时配置文件格式不正确。")

        result: dict[str, str] = {}
        for key, value in payload.items():
            if key not in RUNTIME_CONFIG_KEYS or not isinstance(value, str):
                continue
            result[key] = value
        return result

    def write(self, values: dict[str, str]) -> None:
        payload = {
            key: str(value)
            for key, value in values.items()
            if key in RUNTIME_CONFIG_KEYS
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
                temp_path = Path(handle.name)
            temp_path.chmod(0o600)
            os.replace(temp_path, self.path)
            self.path.chmod(0o600)
        except OSError as exc:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            raise RuntimeError("无法保存页面运行时配置。") from exc


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(
    name: str,
    default: int,
    *,
    minimum: int,
    maximum: int | None = None,
) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} 必须是整数，当前值为 {raw!r}。") from exc
    if value < minimum or (maximum is not None and value > maximum):
        upper = f" 且不大于 {maximum}" if maximum is not None else ""
        raise RuntimeError(f"{name} 必须不小于 {minimum}{upper}。")
    return value


def _as_float(name: str, default: float, *, minimum: float) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} 必须是数字，当前值为 {raw!r}。") from exc
    if value < minimum:
        raise RuntimeError(f"{name} 必须不小于 {minimum}。")
    return value


@dataclass(frozen=True)
class Settings:
    project_root: Path
    skill_root: Path
    static_dir: Path
    generated_dir: Path
    style_reference_path: Path
    model_base_url: str
    model_api_key: str
    model_name: str
    model_timeout_seconds: float
    model_max_tokens: int
    max_upload_mb: int
    max_image_pixels: int
    max_image_dimension: int
    max_concurrent_jobs: int
    max_pending_jobs: int
    max_jobs_per_minute: int
    job_ttl_seconds: int
    max_clarification_rounds: int
    repair_attempts: int
    image_generation_enabled: bool
    max_concurrent_image_jobs: int
    pixpark_endpoint: str
    pixpark_token: str
    pixpark_timeout_seconds: float
    pixpark_upload_timeout_seconds: float
    pixpark_download_timeout_seconds: float
    pixpark_max_wait_seconds: float
    pixpark_poll_interval_seconds: float
    pixpark_max_download_mb: int

    @property
    def model_configured(self) -> bool:
        return bool(self.model_base_url and self.model_name)

    @property
    def style_reference_configured(self) -> bool:
        return self.style_reference_path.is_file()

    @property
    def ready(self) -> bool:
        return self.model_configured and self.style_reference_configured

    @property
    def pixpark_configured(self) -> bool:
        return bool(self.pixpark_endpoint and self.pixpark_token)

    @property
    def image_generation_ready(self) -> bool:
        return self.image_generation_enabled and self.pixpark_configured


def load_settings() -> Settings:
    project_root = Path(__file__).resolve().parent.parent
    load_dotenv(project_root / ".env")
    skill_root = Path(os.getenv("SKILL_ROOT", str(project_root))).expanduser().resolve()
    static_dir = project_root / "webapp" / "static"
    generated_dir = (
        Path(os.getenv("GENERATED_DIR", str(project_root / "generated")))
        .expanduser()
        .resolve()
    )
    try:
        generated_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(f"无法创建生成目录：{generated_dir}") from exc
    runtime_dir = (
        Path(os.getenv("RUNTIME_DIR", str(project_root / ".runtime")))
        .expanduser()
        .resolve()
    )
    try:
        runtime_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(f"无法创建运行时配置目录：{runtime_dir}") from exc
    runtime_values = RuntimeConfigStore(runtime_dir / RUNTIME_CONFIG_FILENAME).read()
    for key, value in runtime_values.items():
        os.environ[key] = value

    return Settings(
        project_root=project_root,
        skill_root=skill_root,
        static_dir=static_dir,
        generated_dir=generated_dir,
        style_reference_path=Path(
            os.getenv(
                "STYLE_REFERENCE_PATH",
                str(project_root / "config" / "style-reference.png"),
            )
        )
        .expanduser()
        .resolve(),
        model_base_url=os.getenv("MODEL_BASE_URL", "").strip(),
        model_api_key=os.getenv("MODEL_API_KEY", "").strip(),
        model_name=os.getenv("MODEL_NAME", "").strip(),
        model_timeout_seconds=_as_float("MODEL_TIMEOUT_SECONDS", 180, minimum=10),
        model_max_tokens=_as_int(
            "MODEL_MAX_TOKENS", 12000, minimum=1000, maximum=100000
        ),
        max_upload_mb=_as_int("MAX_UPLOAD_MB", 15, minimum=1, maximum=100),
        max_image_pixels=_as_int("MAX_IMAGE_PIXELS", 40_000_000, minimum=102_400),
        max_image_dimension=_as_int(
            "MAX_IMAGE_DIMENSION", 12_000, minimum=320, maximum=50_000
        ),
        max_concurrent_jobs=_as_int("MAX_CONCURRENT_JOBS", 2, minimum=1, maximum=16),
        max_pending_jobs=_as_int("MAX_PENDING_JOBS", 8, minimum=1, maximum=100),
        max_jobs_per_minute=_as_int("MAX_JOBS_PER_MINUTE", 10, minimum=1, maximum=1000),
        job_ttl_seconds=_as_int("JOB_TTL_SECONDS", 3600, minimum=300),
        max_clarification_rounds=_as_int(
            "MAX_CLARIFICATION_ROUNDS", 2, minimum=0, maximum=5
        ),
        repair_attempts=_as_int("REPAIR_ATTEMPTS", 2, minimum=0, maximum=5),
        image_generation_enabled=_as_bool(
            os.getenv("IMAGE_GENERATION_ENABLED"), default=False
        ),
        max_concurrent_image_jobs=_as_int(
            "MAX_CONCURRENT_IMAGE_JOBS", 1, minimum=1, maximum=8
        ),
        pixpark_endpoint=os.getenv(
            "PIX_PARK_ENDPOINT",
            "https://mcp.wedobest.com.cn/mcp/PixPark/http",
        ).strip(),
        pixpark_token=os.getenv("PIX_PARK_TOKEN", "").strip(),
        pixpark_timeout_seconds=_as_float("PIX_PARK_TIMEOUT_SECONDS", 45, minimum=5),
        pixpark_upload_timeout_seconds=_as_float(
            "PIX_PARK_UPLOAD_TIMEOUT_SECONDS", 90, minimum=5
        ),
        pixpark_download_timeout_seconds=_as_float(
            "PIX_PARK_DOWNLOAD_TIMEOUT_SECONDS", 60, minimum=5
        ),
        pixpark_max_wait_seconds=_as_float("PIX_PARK_MAX_WAIT_SECONDS", 240, minimum=1),
        pixpark_poll_interval_seconds=_as_float(
            "PIX_PARK_POLL_INTERVAL_SECONDS", 3, minimum=1
        ),
        pixpark_max_download_mb=_as_int(
            "PIX_PARK_MAX_DOWNLOAD_MB", 64, minimum=1, maximum=512
        ),
    )


def runtime_config_store(settings: Settings) -> RuntimeConfigStore:
    runtime_dir = (
        Path(os.getenv("RUNTIME_DIR", str(settings.project_root / ".runtime")))
        .expanduser()
        .resolve()
    )
    return RuntimeConfigStore(runtime_dir / RUNTIME_CONFIG_FILENAME)


def public_configuration(settings: Settings) -> dict[str, Any]:
    config_path = runtime_config_store(settings).path
    try:
        config_location = str(config_path.relative_to(settings.project_root))
    except ValueError:
        config_location = "服务器私有运行目录/runtime-settings.json"
    return {
        "model_base_url": settings.model_base_url,
        "model_name": settings.model_name,
        "model_api_key_configured": bool(settings.model_api_key),
        "pixpark_token_configured": bool(settings.pixpark_token),
        "image_generation_enabled": settings.image_generation_enabled,
        "style_reference_configured": settings.style_reference_configured,
        "model_configured": settings.model_configured,
        "pixpark_configured": settings.pixpark_configured,
        "image_generation_ready": settings.image_generation_ready,
        "ready": settings.ready,
        "runtime_config_location": config_location,
    }

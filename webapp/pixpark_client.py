from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from PIL import Image, UnidentifiedImageError

from webapp.config import Settings

RESULT_IMAGE_COUNT = 4
FIXED_CONTRACT = {
    "version": 3,
    "imageScale": "1:1",
    "resolution": "4K",
    "imageNum": RESULT_IMAGE_COUNT,
    "enableGoogleSearch": False,
}
ALLOWED_IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}
REJECTION_WORDS = ("敏感", "侵权", "失败", "拒绝", "违规", "不支持")
JOB_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")
StatusCallback = Callable[[str, str], None]


class PixParkError(RuntimeError):
    """PixPark 调用无法继续或需要人工处理。"""


class PixParkTimeout(PixParkError):
    """已有 taskCode 的任务超过本次等待窗口，可恢复查询。"""


class PixParkRejected(PixParkError):
    """PixPark 明确拒绝任务或没有审核通过的结果。"""


@dataclass(frozen=True)
class PixParkImageResult:
    task_code: str
    filenames: tuple[str, ...]

    @property
    def filename(self) -> str:
        return self.filenames[0] if self.filenames else ""


class PixParkStateStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, job_id: str) -> Path:
        if not JOB_ID_PATTERN.fullmatch(job_id):
            raise PixParkError("图片任务编号无效。")
        return self.root / f"{job_id}.json"

    def read(self, job_id: str) -> dict[str, Any]:
        path = self.path_for(job_id)
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise PixParkError("没有找到可恢复的 PixPark 任务。") from exc
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise PixParkError("PixPark 任务状态文件损坏或不可读。") from exc
        if not isinstance(value, dict):
            raise PixParkError("PixPark 任务状态格式无效。")
        return value

    def has_task(self, job_id: str) -> bool:
        try:
            value = self.read(job_id)
        except PixParkError:
            return False
        return bool(str(value.get("taskCode") or "").strip())

    def discard(self, job_id: str) -> None:
        """Forget a previous remote task before starting a fresh image batch."""
        path = self.path_for(job_id)
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            raise PixParkError("无法清理上一轮 PixPark 任务状态。") from exc

    def write(
        self,
        job_id: str,
        *,
        status: str,
        task_code: str,
        task_status: Any = None,
        output_name: str | None = None,
        output_names: list[str] | tuple[str, ...] | None = None,
        error: str | None = None,
    ) -> None:
        path = self.path_for(job_id)
        normalized_names = [
            str(name).strip()
            for name in (output_names or ())
            if str(name).strip()
        ]
        if not normalized_names and output_name:
            normalized_names = [str(output_name).strip()]
        payload = {
            "jobId": job_id,
            "status": status,
            "taskCode": task_code,
            "taskStatus": task_status,
            "outputName": normalized_names[0] if normalized_names else None,
            "outputNames": normalized_names,
            "error": _safe_error(error),
            "fixedContract": FIXED_CONTRACT,
            "updatedAt": int(time.time()),
        }
        temporary = path.with_suffix(".json.tmp")
        try:
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temporary, path)
        except OSError as exc:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise PixParkError("无法安全保存 PixPark 任务编号。") from exc


class PixParkClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.state_store = PixParkStateStore(
            settings.generated_dir / "pixpark-state"
        )
        self._request_id = 0
        self._session_id: str | None = None

    async def generate(
        self,
        *,
        job_id: str,
        input_filename: str,
        input_media_type: str,
        input_bytes: bytes,
        prompt: str,
        on_status: StatusCallback,
    ) -> PixParkImageResult:
        if not self.settings.pixpark_configured:
            raise PixParkError("PixPark Token 尚未配置。")
        prompt = prompt.strip()
        if not prompt:
            raise PixParkError("审查通过的正向提示词为空。")

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.settings.pixpark_timeout_seconds)
        ) as client:
            await self._initialize(client)
            try:
                style_data = self.settings.style_reference_path.read_bytes()
            except OSError as exc:
                raise PixParkError("无法读取固定图2风格参考图。") from exc
            style_media_type = _media_type_for_path(
                self.settings.style_reference_path
            )
            if style_media_type is None:
                raise PixParkError("固定图2风格参考图格式不受支持。")

            on_status("uploading", "正在上传图1需求图（1/2）。")
            requirement_url = await self._upload_image(
                client,
                filename=Path(input_filename).name,
                media_type=input_media_type,
                data=input_bytes,
            )
            on_status("uploading", "正在上传图2风格参考图（2/2）。")
            style_url = await self._upload_image(
                client,
                filename=self.settings.style_reference_path.name,
                media_type=style_media_type,
                data=style_data,
            )

            on_status(
                "creating",
                f"正在创建唯一的 PixPark v3 四图任务（{RESULT_IMAGE_COUNT} 张）。",
            )
            created = await self._call_tool(
                client,
                "imageGenerationUsingPOST",
                {
                    "imageUrls": [requirement_url, style_url],
                    "inputPrompt": prompt,
                    **FIXED_CONTRACT,
                },
            )
            task_code = str(created.get("taskCode") or "").strip()
            if not task_code:
                raise PixParkError("PixPark 创建结果缺少 taskCode。")

            self.state_store.write(
                job_id,
                status="created",
                task_code=task_code,
            )
            interval = _positive_float(
                created.get("roundPeriod"),
                self.settings.pixpark_poll_interval_seconds,
            )
            return await self._poll_and_download(
                client,
                job_id=job_id,
                task_code=task_code,
                interval=interval,
                on_status=on_status,
            )

    async def resume(
        self,
        *,
        job_id: str,
        on_status: StatusCallback,
    ) -> PixParkImageResult:
        if not self.settings.pixpark_configured:
            raise PixParkError("PixPark Token 尚未配置。")
        state = self.state_store.read(job_id)
        task_code = str(state.get("taskCode") or "").strip()
        if not task_code:
            raise PixParkError("状态文件中没有可恢复的 taskCode。")

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.settings.pixpark_timeout_seconds)
        ) as client:
            await self._initialize(client)
            return await self._poll_and_download(
                client,
                job_id=job_id,
                task_code=task_code,
                interval=self.settings.pixpark_poll_interval_seconds,
                on_status=on_status,
            )

    async def _initialize(self, client: httpx.AsyncClient) -> None:
        self._session_id = None
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {
                    "name": "haoyue-pixpark-adapter",
                    "version": "0.1.0",
                },
            },
        }
        response, message = await self._post_rpc(client, payload)
        result = message.get("result")
        if not isinstance(result, dict):
            raise PixParkError("PixPark Initialize 缺少结果对象。")
        self._session_id = (
            response.headers.get("Mcp-Session-Id")
            or str(result.get("sessionId") or "").strip()
            or None
        )

        notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }
        try:
            await client.post(
                self.settings.pixpark_endpoint,
                headers=self._headers(),
                json=notification,
            )
        except httpx.HTTPError:
            pass

    async def _upload_image(
        self,
        client: httpx.AsyncClient,
        *,
        filename: str,
        media_type: str,
        data: bytes,
    ) -> str:
        if not data:
            raise PixParkError("待上传图片为空。")
        if media_type not in ALLOWED_IMAGE_TYPES:
            raise PixParkError("PixPark 只接受 PNG、JPEG 或 WebP 输入图。")
        upload_data = await self._call_tool(
            client,
            "presignedPutUsingPOST",
            {
                "filename": Path(filename).name,
                "contentType": media_type,
                "expireSeconds": 86400,
            },
        )
        upload_url = str(upload_data.get("uploadUrl") or "").strip()
        public_url = str(upload_data.get("publicUrl") or "").strip()
        _require_public_url(upload_url, "预签名上传地址")
        _require_public_url(public_url, "公网图片地址")

        try:
            response = await client.put(
                upload_url,
                headers={"Content-Type": media_type},
                content=data,
                timeout=self.settings.pixpark_upload_timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise PixParkError("上传图片到 PixPark 对象存储失败。") from exc
        if response.is_error:
            raise PixParkError(
                f"PixPark 图片上传返回 HTTP {response.status_code}。"
            )
        return public_url

    async def _poll_and_download(
        self,
        client: httpx.AsyncClient,
        *,
        job_id: str,
        task_code: str,
        interval: float,
        on_status: StatusCallback,
    ) -> PixParkImageResult:
        deadline = time.monotonic() + self.settings.pixpark_max_wait_seconds
        interval = max(interval, 1.0)
        while time.monotonic() < deadline:
            on_status(
                "polling",
                f"PixPark 正在生成 {RESULT_IMAGE_COUNT} 张结果图。",
            )
            data = await self._call_tool(
                client,
                "queryTaskUsingPOST",
                {"taskCode": task_code},
            )
            task_status = data.get("taskStatus")
            self.state_store.write(
                job_id,
                status="polling",
                task_code=task_code,
                task_status=task_status,
            )

            if task_status == 2 or str(task_status) == "2":
                result_items = data.get("result")
                if not isinstance(result_items, list):
                    result_items = []
                approved_urls = [
                    str(item.get("targetImageUrl") or "").strip()
                    for item in result_items
                    if isinstance(item, dict)
                    and item.get("imageAuditStatus") is True
                    and str(item.get("targetImageUrl") or "").strip()
                ][:RESULT_IMAGE_COUNT]
                if not approved_urls:
                    self.state_store.write(
                        job_id,
                        status="rejected",
                        task_code=task_code,
                        task_status=task_status,
                        error="任务完成但没有审核通过的结果图。",
                    )
                    raise PixParkRejected("PixPark 没有返回审核通过的结果图。")

                for approved_url in approved_urls:
                    _require_public_url(approved_url, "结果图地址")
                on_status(
                    "downloading",
                    f"{len(approved_urls)} 张结果已通过审核，正在下载。",
                )
                filenames: list[str] = []
                try:
                    for index, approved_url in enumerate(approved_urls, start=1):
                        on_status(
                            "downloading",
                            f"正在下载第 {index}/{len(approved_urls)} 张结果图。",
                        )
                        filenames.append(
                            await self._download_result(
                                client,
                                job_id=job_id,
                                url=approved_url,
                                slot=index,
                            )
                        )
                except Exception:
                    for filename in filenames:
                        try:
                            (self.settings.generated_dir / filename).unlink(
                                missing_ok=True
                            )
                        except OSError:
                            pass
                    raise

                self.state_store.write(
                    job_id,
                    status="completed",
                    task_code=task_code,
                    task_status=task_status,
                    output_names=filenames,
                )
                return PixParkImageResult(
                    task_code=task_code,
                    filenames=tuple(filenames),
                )

            if _contains_rejection(data):
                self.state_store.write(
                    job_id,
                    status="rejected",
                    task_code=task_code,
                    task_status=task_status,
                    error="PixPark 明确拒绝或终止任务。",
                )
                raise PixParkRejected("PixPark 明确拒绝或终止了本次任务。")
            await asyncio.sleep(interval)

        self.state_store.write(
            job_id,
            status="timeout",
            task_code=task_code,
            error="超过本次等待时间，可继续查询同一任务。",
        )
        raise PixParkTimeout("结果图仍在生成，可稍后继续查询同一任务。")

    async def _download_result(
        self,
        client: httpx.AsyncClient,
        *,
        job_id: str,
        url: str,
        slot: int | None = None,
    ) -> str:
        try:
            async with client.stream(
                "GET",
                url,
                timeout=self.settings.pixpark_download_timeout_seconds,
            ) as response:
                if response.is_error:
                    raise PixParkError(
                        f"PixPark 结果图下载返回 HTTP {response.status_code}。"
                    )
                limit = self.settings.pixpark_max_download_mb * 1024 * 1024
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > limit:
                    raise PixParkError("PixPark 结果图超过下载大小限制。")

                # PixPark 对象存储偶尔会把 JPEG 错误标成 image/png。
                # 先写入无类型临时文件，再让 Pillow 按真实文件头决定扩展名；
                # MIME 只作为传输元数据，不能成为文件格式的事实来源。
                slot_suffix = f"-{slot}" if slot is not None else ""
                temporary = (
                    self.settings.generated_dir
                    / f".{job_id}{slot_suffix}.download.tmp"
                )
                total = 0
                try:
                    with temporary.open("wb") as handle:
                        async for chunk in response.aiter_bytes():
                            total += len(chunk)
                            if total > limit:
                                raise PixParkError(
                                    "PixPark 结果图超过下载大小限制。"
                                )
                            handle.write(chunk)
                    if total == 0:
                        raise PixParkError("PixPark 结果图内容为空。")
                    extension = _detect_downloaded_image(
                        temporary,
                        max_pixels=self.settings.max_image_pixels,
                    )
                    filename = f"{job_id}{slot_suffix}{extension}"
                    destination = self.settings.generated_dir / filename
                    os.replace(temporary, destination)
                except Exception:
                    temporary.unlink(missing_ok=True)
                    raise
                return filename
        except PixParkError:
            raise
        except (httpx.HTTPError, OSError, ValueError) as exc:
            raise PixParkError("下载或保存 PixPark 结果图失败。") from exc

    async def _call_tool(
        self,
        client: httpx.AsyncClient,
        name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        _, message = await self._post_rpc(client, payload)
        result = message.get("result")
        if not isinstance(result, dict):
            raise PixParkError(f"PixPark 工具 {name} 缺少结果对象。")
        content = result.get("content")
        if not isinstance(content, list):
            raise PixParkError(f"PixPark 工具 {name} 缺少文本结果。")
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "text":
                continue
            try:
                business = json.loads(str(item.get("text") or ""))
            except json.JSONDecodeError as exc:
                raise PixParkError(
                    f"PixPark 工具 {name} 返回了无效业务 JSON。"
                ) from exc
            if not isinstance(business, dict):
                raise PixParkError(f"PixPark 工具 {name} 业务结果格式无效。")
            if str(business.get("code")) != "200":
                raise PixParkError(
                    f"PixPark 工具 {name} 返回业务错误："
                    f"{_safe_error(str(business.get('message') or '未知错误'))}"
                )
            data = business.get("data")
            if not isinstance(data, dict):
                raise PixParkError(f"PixPark 工具 {name} 缺少业务数据。")
            return data
        raise PixParkError(f"PixPark 工具 {name} 没有返回文本内容。")

    async def _post_rpc(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, Any],
    ) -> tuple[httpx.Response, dict[str, Any]]:
        try:
            response = await client.post(
                self.settings.pixpark_endpoint,
                headers=self._headers(),
                json=payload,
            )
        except httpx.TimeoutException as exc:
            raise PixParkError("PixPark MCP 请求超时。") from exc
        except httpx.HTTPError as exc:
            raise PixParkError("无法连接 PixPark MCP 服务。") from exc
        if response.is_error:
            raise PixParkError(
                f"PixPark MCP 返回 HTTP {response.status_code}。"
            )
        message = parse_mcp_response(
            response.text,
            response.headers.get("Content-Type", ""),
            payload.get("id"),
        )
        error = message.get("error")
        if isinstance(error, dict):
            raise PixParkError(
                "PixPark RPC 错误："
                + _safe_error(str(error.get("message") or "未知错误"))
            )
        return response, message

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.settings.pixpark_token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    def _next_request_id(self) -> int:
        self._request_id += 1
        return self._request_id


def parse_mcp_response(
    text: str,
    content_type: str,
    request_id: Any,
) -> dict[str, Any]:
    if content_type.lower().startswith("text/event-stream"):
        candidates: list[dict[str, Any]] = []
        for line in text.splitlines():
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if not payload or payload == "[DONE]":
                continue
            try:
                value = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                candidates.append(value)
        for value in candidates:
            if request_id is None or value.get("id") == request_id:
                return value
        raise PixParkError("PixPark SSE 响应中没有匹配的 JSON-RPC 消息。")
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PixParkError("PixPark 返回了无效 JSON-RPC。") from exc
    if not isinstance(value, dict):
        raise PixParkError("PixPark JSON-RPC 响应格式无效。")
    if request_id is not None and value.get("id") != request_id:
        raise PixParkError("PixPark JSON-RPC 响应 ID 不匹配。")
    return value


def _require_public_url(value: str, label: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise PixParkError(f"{label}不是可访问的 HTTP(S) URL。")
    if parsed.username or parsed.password:
        raise PixParkError(f"{label}不得包含 URL 凭据。")
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise PixParkError(f"{label}不得指向本机地址。")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return
    if not address.is_global:
        raise PixParkError(f"{label}不得指向内网或保留地址。")


def _media_type_for_path(path: Path) -> str | None:
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(path.suffix.lower())


def _detect_downloaded_image(
    path: Path,
    *,
    max_pixels: int,
) -> str:
    extensions = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}
    try:
        with Image.open(path) as opened:
            if opened.width * opened.height > max_pixels:
                raise PixParkError("PixPark 结果图像素总量超过限制。")
            extension = extensions.get(str(opened.format or "").upper())
            if extension is None:
                raise PixParkError("PixPark 结果图不是受支持的图片格式。")
            opened.verify()
            return extension
    except PixParkError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise PixParkError("PixPark 结果文件不是有效图片。") from exc


def _positive_float(value: Any, fallback: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = fallback
    return max(parsed, 1.0)


def _contains_rejection(value: dict[str, Any]) -> bool:
    text = json.dumps(value, ensure_ascii=False)
    return any(word in text for word in REJECTION_WORDS)


def _safe_error(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"https?://\S+", "[已隐藏URL]", value)
    text = re.sub(r"Bearer\s+\S+", "Bearer [已隐藏]", text, flags=re.IGNORECASE)
    return text[:300]

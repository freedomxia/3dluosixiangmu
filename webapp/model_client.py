from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

import httpx

from webapp.config import Settings


class ModelAPIError(RuntimeError):
    """模型服务返回了无法继续处理的错误。"""


@dataclass(frozen=True)
class VisionImage:
    data: bytes
    media_type: str

    def as_data_url(self) -> str:
        encoded = base64.b64encode(self.data).decode("ascii")
        return f"data:{self.media_type};base64,{encoded}"


class OpenAICompatibleClient:
    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.transport = transport

    @property
    def endpoint(self) -> str:
        base = self.settings.model_base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return f"{base}/chat/completions"

    async def complete(
        self,
        *,
        system_prompt: str,
        user_text: str,
        images: list[VisionImage],
        temperature: float = 0.15,
        max_tokens: int | None = None,
    ) -> str:
        if not self.settings.model_configured:
            raise ModelAPIError("管理员尚未配置模型地址和模型名称。")

        content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
        for image in images:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": image.as_data_url(), "detail": "high"},
                }
            )

        headers = {"Content-Type": "application/json"}
        if self.settings.model_api_key:
            headers["Authorization"] = f"Bearer {self.settings.model_api_key}"

        payload = {
            "model": self.settings.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens or self.settings.model_max_tokens,
            # 正式提示词生成可能持续数分钟。流式响应会尽早建立响应头并持续
            # 传输数据，避免兼容网关把“长时间没有任何响应”的请求提前断开。
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.settings.model_timeout_seconds),
                transport=self.transport,
            ) as client:
                async with client.stream(
                    "POST",
                    self.endpoint,
                    headers=headers,
                    json=payload,
                ) as response:
                    if response.is_error:
                        await response.aread()
                        detail = _extract_error_detail(response)
                        raise ModelAPIError(
                            f"模型服务返回 {response.status_code}：{detail}"
                        )

                    content_type = response.headers.get("content-type", "")
                    if "text/event-stream" in content_type.lower():
                        return await _read_streamed_text(response)

                    # 少数 OpenAI 兼容服务会忽略 stream=true 并返回普通 JSON；
                    # 保留兼容路径，避免把本来有效的响应误判为失败。
                    await response.aread()
                    return _read_json_text(response)
        except ModelAPIError:
            raise
        except httpx.TimeoutException as exc:
            raise ModelAPIError(
                "模型响应超时。请稍后重试，或由管理员提高 MODEL_TIMEOUT_SECONDS。"
            ) from exc
        except httpx.HTTPError as exc:
            raise ModelAPIError(f"无法连接模型服务：{exc}") from exc

def _extract_error_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:300] or "未知错误"

    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])[:300]
        if isinstance(error, str):
            return error[:300]
        if body.get("message"):
            return str(body["message"])[:300]
    return str(body)[:300]


async def _read_streamed_text(response: httpx.Response) -> str:
    text_parts: list[str] = []
    async for line in response.aiter_lines():
        if not line.startswith("data:"):
            continue
        raw_event = line[5:].strip()
        if not raw_event:
            continue
        if raw_event == "[DONE]":
            break

        try:
            event = json.loads(raw_event)
            choice = event["choices"][0]
            delta = choice.get("delta") or choice.get("message") or {}
            content = delta.get("content")
        except (json.JSONDecodeError, KeyError, IndexError, TypeError, AttributeError):
            continue

        text = _normalize_message_content(content)
        if text:
            text_parts.append(text)

    combined = "".join(text_parts).strip()
    if combined:
        return combined
    raise ModelAPIError("模型服务没有返回文本内容。")


def _read_json_text(response: httpx.Response) -> str:
    try:
        data = response.json()
        message_content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise ModelAPIError("模型服务返回了无法识别的响应格式。") from exc

    combined = _normalize_message_content(message_content).strip()
    if combined:
        return combined
    raise ModelAPIError("模型服务没有返回文本内容。")


def _normalize_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        return "\n".join(part for part in text_parts if part)
    return ""

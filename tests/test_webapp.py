from __future__ import annotations

import asyncio
import io
import json
import stat
import tempfile
import unittest
from pathlib import Path

import httpx
from PIL import Image

from webapp.config import RuntimeConfigStore, Settings, public_configuration
from webapp.model_client import ModelAPIError, OpenAICompatibleClient
from webapp.parsing import (
    parse_json_object,
    parse_markdown_sections,
    strip_single_code_fence,
)
from webapp.pipeline import JobManager, QueueCapacityError
from webapp.pixpark_client import (
    FIXED_CONTRACT,
    RESULT_IMAGE_COUNT,
    PixParkClient,
    PixParkImageResult,
    PixParkRejected,
    PixParkStateStore,
    parse_mcp_response,
)
from webapp.skill_loader import build_skill_prompt

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VALID_OUTPUT = (PROJECT_ROOT / "tests" / "fixtures" / "valid-output.md").read_text(
    encoding="utf-8"
)


class FakeModelClient:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, **kwargs) -> str:
        self.calls += 1
        if self.calls == 1:
            return """
            {
              "task_type": "LOCK_LAYOUT_EDIT",
              "needs_creative_cases": false,
              "triggers": {
                "special_material": false,
                "text_logo_time": false,
                "haoyue_brand": false
              },
              "clarification": {
                "required": false,
                "reason": "none",
                "question": ""
              },
              "anniversary_source": "unknown",
              "allow_aspect_ratio": false,
              "requested_aspect_ratio": "none",
              "routing_summary": "成熟布局局部修改"
            }
            """
        return VALID_OUTPUT


class OtherRatioModelClient(FakeModelClient):
    async def complete(self, **kwargs) -> str:
        if self.calls == 0:
            self.calls += 1
            return """
            {
              "task_type": "LOCK_LAYOUT_EDIT",
              "needs_creative_cases": false,
              "triggers": {
                "special_material": false,
                "text_logo_time": false,
                "haoyue_brand": false
              },
              "clarification": {
                "required": false,
                "reason": "none",
                "question": ""
              },
              "anniversary_source": "unknown",
              "allow_aspect_ratio": true,
              "requested_aspect_ratio": "other",
              "routing_summary": "用户要求非方形画幅"
            }
            """
        self.calls += 1
        return VALID_OUTPUT


class FakePixPark:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.prompts: list[str] = []

    async def generate(self, **kwargs) -> PixParkImageResult:
        self.prompts.append(kwargs["prompt"])
        kwargs["on_status"]("polling", "测试图片生成中。")
        outputs: list[str] = []
        for index, color in enumerate(
            ("purple", "teal", "orange", "navy"),
            start=1,
        ):
            output = (
                self.settings.generated_dir
                / f"{kwargs['job_id']}-{index}.png"
            )
            Image.new("RGB", (32, 32), color).save(output)
            outputs.append(output.name)
        return PixParkImageResult(
            task_code="test-task-code",
            filenames=tuple(outputs),
        )


def make_settings(
    style_path: Path,
    *,
    generated_dir: Path | None = None,
    image_generation_enabled: bool = False,
) -> Settings:
    return Settings(
        project_root=PROJECT_ROOT,
        skill_root=PROJECT_ROOT,
        static_dir=PROJECT_ROOT / "webapp" / "static",
        generated_dir=generated_dir or PROJECT_ROOT / "generated",
        style_reference_path=style_path,
        model_base_url="https://model.example/v1",
        model_api_key="test",
        model_name="vision-test",
        model_timeout_seconds=10,
        model_max_tokens=12000,
        max_upload_mb=15,
        max_image_pixels=40_000_000,
        max_image_dimension=12_000,
        max_concurrent_jobs=1,
        max_pending_jobs=8,
        max_jobs_per_minute=10,
        job_ttl_seconds=3600,
        max_clarification_rounds=2,
        repair_attempts=1,
        image_generation_enabled=image_generation_enabled,
        max_concurrent_image_jobs=1,
        pixpark_endpoint="https://mcp.example.test/http",
        pixpark_token="test-pixpark-token" if image_generation_enabled else "",
        pixpark_timeout_seconds=10,
        pixpark_upload_timeout_seconds=10,
        pixpark_download_timeout_seconds=10,
        pixpark_max_wait_seconds=10,
        pixpark_poll_interval_seconds=1,
        pixpark_max_download_mb=8,
    )


class ModelClientStreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_streaming_response_is_accumulated(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            self.assertTrue(payload["stream"])
            stream = "\n\n".join(
                [
                    'data: {"choices":[{"delta":{"content":"纯净"}}]}',
                    'data: {"choices":[{"delta":{"content":"提示词"}}]}',
                    "data: [DONE]",
                    "",
                ]
            ).encode("utf-8")
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=stream,
            )

        client = OpenAICompatibleClient(
            make_settings(PROJECT_ROOT / "config" / "style-reference.png"),
            transport=httpx.MockTransport(handler),
        )
        result = await client.complete(
            system_prompt="system",
            user_text="user",
            images=[],
        )
        self.assertEqual(result, "纯净提示词")

    async def test_non_streaming_compatible_response_still_works(self) -> None:
        async def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json={"choices": [{"message": {"content": "普通响应"}}]},
            )

        client = OpenAICompatibleClient(
            make_settings(PROJECT_ROOT / "config" / "style-reference.png"),
            transport=httpx.MockTransport(handler),
        )
        result = await client.complete(
            system_prompt="system",
            user_text="user",
            images=[],
        )
        self.assertEqual(result, "普通响应")

    async def test_streaming_error_keeps_provider_detail(self) -> None:
        async def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(
                403,
                json={"error": {"message": "用户额度不足"}},
            )

        client = OpenAICompatibleClient(
            make_settings(PROJECT_ROOT / "config" / "style-reference.png"),
            transport=httpx.MockTransport(handler),
        )
        with self.assertRaisesRegex(ModelAPIError, "用户额度不足"):
            await client.complete(
                system_prompt="system",
                user_text="user",
                images=[],
            )


class RuntimeConfigTests(unittest.TestCase):
    def test_runtime_config_is_private_atomic_and_allowlisted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime-settings.json"
            store = RuntimeConfigStore(path)
            store.write(
                {
                    "MODEL_BASE_URL": "https://model.example/v1",
                    "MODEL_API_KEY": "model-secret",
                    "MODEL_NAME": "vision-test",
                    "PIX_PARK_TOKEN": "pixpark-secret",
                    "IMAGE_GENERATION_ENABLED": "true",
                    "UNSUPPORTED_SECRET": "must-not-be-written",
                }
            )

            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("UNSUPPORTED_SECRET", text)
            self.assertEqual(store.read()["PIX_PARK_TOKEN"], "pixpark-secret")


class DurableJobStorageTests(unittest.IsolatedAsyncioTestCase):
    async def test_completed_task_and_source_survive_manager_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            style_path = root / "style-reference.png"
            storage_dir = root / "runtime" / "jobs"
            Image.new("RGB", (400, 400), "gray").save(style_path)
            source = _make_image_bytes()
            first = JobManager(
                make_settings(style_path),
                client=FakeModelClient(),
                storage_dir=storage_dir,
            )
            record = first.create(
                filename="重启恢复.png",
                media_type="image/png",
                image_bytes=source,
                note="保留蓝色主体",
                enrichment_enabled=True,
            )
            assert record.task is not None
            await record.task
            self.assertEqual(record.status, "prompt_ready", record.error)

            second = JobManager(
                make_settings(style_path),
                client=FakeModelClient(),
                storage_dir=storage_dir,
            )
            recovered = second.get(record.id)
            self.assertIsNotNone(recovered)
            assert recovered is not None
            self.assertEqual(recovered.status, "prompt_ready")
            self.assertEqual(recovered.note, "保留蓝色主体")
            self.assertTrue(recovered.enrichment_enabled)
            self.assertEqual(recovered.image_bytes, source)
            self.assertTrue(recovered.source_path and recovered.source_path.is_file())
            public = recovered.public()
            self.assertEqual(public["short_id"], record.id[:8].upper())
            self.assertEqual(
                public["source_image_url"],
                f"/api/jobs/{record.id}/source-image",
            )
            [history] = second.history()
            self.assertEqual(history["source_image_url"], public["source_image_url"])

    async def test_interrupted_model_task_requeues_without_new_job_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            style_path = root / "style-reference.png"
            storage_dir = root / "runtime" / "jobs"
            Image.new("RGB", (400, 400), "gray").save(style_path)
            blocker = asyncio.Event()

            class BlockingClient:
                async def complete(self, **kwargs) -> str:
                    await blocker.wait()
                    return VALID_OUTPUT

            first = JobManager(
                make_settings(style_path),
                client=BlockingClient(),
                storage_dir=storage_dir,
            )
            record = first.create(
                filename="处理中.png",
                media_type="image/png",
                image_bytes=_make_image_bytes(),
                note="",
            )
            for _ in range(100):
                if record.status == "analyzing":
                    break
                await asyncio.sleep(0.01)
            self.assertEqual(record.status, "analyzing")
            assert record.task is not None
            record.task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await record.task

            second = JobManager(
                make_settings(style_path),
                client=FakeModelClient(),
                storage_dir=storage_dir,
            )
            recovered = second.get(record.id)
            self.assertIsNotNone(recovered)
            assert recovered is not None
            second.start_recovered()
            self.assertEqual(recovered.id, record.id)
            self.assertIsNotNone(recovered.task)
            assert recovered.task is not None
            await recovered.task
            self.assertEqual(recovered.status, "prompt_ready", recovered.error)

    async def test_expiry_deletes_metadata_and_source_together(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            style_path = root / "style-reference.png"
            storage_dir = root / "runtime" / "jobs"
            Image.new("RGB", (400, 400), "gray").save(style_path)
            settings = make_settings(style_path)
            object.__setattr__(settings, "job_ttl_seconds", 300)
            manager = JobManager(
                settings,
                client=FakeModelClient(),
                storage_dir=storage_dir,
            )
            record = manager.create(
                filename="即将过期.png",
                media_type="image/png",
                image_bytes=_make_image_bytes(),
                note="",
            )
            assert record.task is not None
            await record.task
            record.updated_at = 0
            assert manager.store is not None
            manager.store.save(record)
            task_dir = storage_dir / record.id
            self.assertTrue(task_dir.is_dir())
            manager.cleanup_expired()
            self.assertFalse(task_dir.exists())
            self.assertIsNone(manager.get(record.id))


class FrontendWorkflowTests(unittest.TestCase):
    def test_analysis_keeps_source_and_output_visible_in_same_workbench(self) -> None:
        html = (PROJECT_ROOT / "webapp" / "static" / "index.html").read_text(
            encoding="utf-8"
        )
        script = (PROJECT_ROOT / "webapp" / "static" / "app.js").read_text(
            encoding="utf-8"
        )
        styles = (PROJECT_ROOT / "webapp" / "static" / "styles.css").read_text(
            encoding="utf-8"
        )

        self.assertIn('<div class="output-column">', html)
        self.assertIn("prepareResultForProcessing();", script)
        self.assertNotIn("elements.resultStation.hidden = true;", script)
        self.assertIn(
            "原图和补充要求保留在左侧；通过审查的提示词会直接出现在这里。",
            script,
        )
        self.assertIn(
            "grid-template-columns: minmax(0, 1.06fr) minmax(0, 0.94fr);",
            styles,
        )
        self.assertNotIn(
            '.intake-station > :not(.station-heading)',
            styles,
        )

    def test_selected_upload_uses_adaptive_media_canvas(self) -> None:
        styles = (PROJECT_ROOT / "webapp" / "static" / "styles.css").read_text(
            encoding="utf-8"
        )

        self.assertIn("grid-template-rows: minmax(0, 1fr) auto;", styles)
        self.assertIn("grid-column: 1 / -1;", styles)
        self.assertIn("object-fit: contain;", styles)
        self.assertIn("height: clamp(180px, 58vw, 280px);", styles)
        self.assertNotIn("max-height: 190px;", styles)

    def test_four_image_generation_uses_one_action_and_result_grid(self) -> None:
        html = (PROJECT_ROOT / "webapp" / "static" / "index.html").read_text(
            encoding="utf-8"
        )
        script = (PROJECT_ROOT / "webapp" / "static" / "app.js").read_text(
            encoding="utf-8"
        )
        styles = (PROJECT_ROOT / "webapp" / "static" / "styles.css").read_text(
            encoding="utf-8"
        )

        self.assertIn('id="generatedImageGrid"', html)
        self.assertIn("确认提示词，一次生成 4 张", html)
        self.assertIn('id="regeneratePromptButton"', html)
        self.assertIn('id="regenerateImageButton"', html)
        self.assertIn('id="resultImageDialog"', html)
        self.assertIn("getSafeGeneratedImageUrls", script)
        self.assertIn("renderGeneratedImages", script)
        self.assertIn("openResultImagePreview", script)
        self.assertNotIn('link.target = "_blank"', script)
        self.assertIn("/prompt/regenerate", script)
        self.assertIn("/image/regenerate", script)
        self.assertIn(".generated-image-grid", styles)
        self.assertIn(
            "grid-template-columns: repeat(2, minmax(0, 1fr));",
            styles,
        )

    def test_running_job_can_move_to_background_while_starting_another(self) -> None:
        html = (PROJECT_ROOT / "webapp" / "static" / "index.html").read_text(
            encoding="utf-8"
        )
        script = (PROJECT_ROOT / "webapp" / "static" / "app.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('id="backgroundTaskButton"', html)
        self.assertIn("selectedJobId: null", script)
        self.assertIn("runningJobIds: new Set()", script)
        self.assertIn("taskStore: new Map()", script)
        self.assertIn("pendingDraft: null", script)
        self.assertIn("Promise.all(", script)
        self.assertIn("preserveBackground: true", script)
        self.assertNotIn("jobId: null", script)
        self.assertNotIn("当前任务仍在处理，完成后再打开其他记录。", script)

    def test_history_is_persistent_and_selection_rejects_stale_responses(self) -> None:
        html = (PROJECT_ROOT / "webapp" / "static" / "index.html").read_text(
            encoding="utf-8"
        )
        script = (PROJECT_ROOT / "webapp" / "static" / "app.js").read_text(
            encoding="utf-8"
        )
        styles = (PROJECT_ROOT / "webapp" / "static" / "styles.css").read_text(
            encoding="utf-8"
        )

        history_tag = html.split('class="history-rail"', 1)[1].split(">", 1)[0]
        self.assertNotIn("hidden", history_tag)
        self.assertNotIn('id="historyTrigger"', html)
        self.assertNotIn('id="historyCloseButton"', html)
        self.assertNotIn("setHistoryOpen", script)
        self.assertNotIn("syncHistoryLayout", script)
        self.assertNotIn("data-history-open", styles)
        self.assertNotIn('body[data-config-open="true"] .workspace-layout', styles)
        self.assertIn("elements.productionLine.before(elements.configStation)", script)
        self.assertIn("grid-template-columns: 248px minmax(0, 1fr);", styles)
        self.assertIn("selectionVersion !== state.selectionVersion", script)
        self.assertIn("state.selectedJobId !== jobId", script)
        self.assertIn("job.source_image_url", script)
        self.assertIn("persistTaskUiState", script)

    def test_public_configuration_never_returns_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            style_path = Path(directory) / "style-reference.png"
            Image.new("RGB", (40, 40), "gray").save(style_path)
            settings = make_settings(style_path, image_generation_enabled=True)
            object.__setattr__(settings, "model_api_key", "model-secret-7f4a")
            object.__setattr__(
                settings,
                "pixpark_token",
                "pixpark-secret-2d9c",
            )

            payload = public_configuration(settings)
            serialized = json.dumps(payload)
            self.assertTrue(payload["model_api_key_configured"])
            self.assertTrue(payload["pixpark_token_configured"])
            self.assertNotIn(settings.model_api_key, serialized)
            self.assertNotIn(settings.pixpark_token, serialized)


class ParsingTests(unittest.TestCase):
    def test_json_fence_is_removed(self) -> None:
        value = parse_json_object('```json\n{"task_type":"ASSET"}\n```')
        self.assertEqual(value["task_type"], "ASSET")

    def test_delivery_sections_are_extracted(self) -> None:
        sections = parse_markdown_sections(VALID_OUTPUT)
        prompt = strip_single_code_fence(sections["纯净生图提示词复制区"])
        self.assertIn("图1", prompt)
        self.assertNotIn("```", prompt)


class SkillLoaderTests(unittest.TestCase):
    def test_always_attaches_internal_index_and_semantic_audit_rules(self) -> None:
        prompt = build_skill_prompt(
            PROJECT_ROOT,
            {
                "task_type": "LOCK_LAYOUT_EDIT",
                "needs_creative_cases": False,
                "triggers": {},
            },
        )
        self.assertIn("图1内部手写序号绑定", prompt)
        self.assertIn("REDLINE_LEDGER", prompt)
        self.assertIn("生图指令清晰度门禁", prompt)
        self.assertIn("图1内部手写序号N", prompt)

    def test_only_selected_reference_body_is_attached(self) -> None:
        prompt = build_skill_prompt(
            PROJECT_ROOT,
            {
                "task_type": "LOCK_LAYOUT_EDIT",
                "needs_creative_cases": False,
                "triggers": {
                    "special_material": True,
                    "text_logo_time": True,
                    "haoyue_brand": True,
                },
            },
        )
        self.assertIn("===== references/layout-lock.md =====", prompt)
        self.assertIn("===== references/style-and-materials.md =====", prompt)
        self.assertIn("===== references/text-logo-time.md =====", prompt)
        self.assertIn("===== references/brand-haoyue.md =====", prompt)
        self.assertNotIn("===== references/creative-cases.md =====", prompt)

    def test_enrichment_reference_is_opt_in(self) -> None:
        classification = {
            "task_type": "ASSET",
            "needs_creative_cases": False,
            "triggers": {},
        }
        plain = build_skill_prompt(PROJECT_ROOT, classification)
        enriched = build_skill_prompt(
            PROJECT_ROOT,
            classification,
            enrichment_enabled=True,
        )
        self.assertNotIn("===== references/enrichment.md =====", plain)
        self.assertNotIn("## 条件新增优先级", plain)
        self.assertIn("===== references/enrichment.md =====", enriched)
        self.assertIn("## 条件新增优先级", enriched)
        self.assertIn("ENRICHMENT_ENABLED=true", enriched)


class PipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_complete_job_returns_prompt_review_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            style_path = Path(directory) / "style-reference.png"
            Image.new("RGB", (400, 400), "gray").save(style_path)
            client = FakeModelClient()
            manager = JobManager(make_settings(style_path), client=client)

            image_buffer = io.BytesIO()
            Image.new("RGB", (400, 400), "white").save(image_buffer, format="PNG")
            image_buffer.seek(0)
            image_bytes = image_buffer.read()

            record = manager.create(
                filename="需求图.png",
                media_type="image/png",
                image_bytes=image_bytes,
                note="只改局部",
            )

            for _ in range(100):
                if record.status in {"prompt_ready", "failed"}:
                    break
                await asyncio.sleep(0.01)

            self.assertEqual(record.status, "prompt_ready", record.error)
            self.assertEqual(client.calls, 2)
            self.assertTrue(record.result["validation"]["pass"])
            self.assertEqual(record.result["image"]["status"], "disabled")
            self.assertIsNone(record.result["image"]["url"])

    async def test_enabled_image_generation_waits_for_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            style_path = root / "style-reference.png"
            generated_dir = root / "generated"
            generated_dir.mkdir()
            Image.new("RGB", (400, 400), "gray").save(style_path)
            fake_pixpark = FakePixPark(
                make_settings(
                    style_path,
                    generated_dir=generated_dir,
                    image_generation_enabled=True,
                )
            )
            settings = fake_pixpark.settings
            manager = JobManager(
                settings,
                client=FakeModelClient(),
                pixpark_factory=lambda _: fake_pixpark,
            )
            record = manager.create(
                filename="需求图.png",
                media_type="image/png",
                image_bytes=_make_image_bytes(),
                note="",
                enrichment_enabled=True,
            )

            for _ in range(200):
                if record.status in {"prompt_ready", "failed"}:
                    break
                await asyncio.sleep(0.01)

            self.assertEqual(record.status, "prompt_ready", record.error)
            self.assertTrue(record.result["validation"]["pass"])
            self.assertEqual(record.result["image"]["status"], "ready")
            self.assertEqual(fake_pixpark.prompts, [])
            self.assertTrue(record.image_bytes)

            manager.generate_image(record.id)
            for _ in range(200):
                if record.status in {"complete", "failed"}:
                    break
                await asyncio.sleep(0.01)

            self.assertEqual(record.status, "complete", record.error)
            self.assertEqual(record.result["image"]["status"], "completed")
            self.assertTrue(record.result["image"]["url"].startswith("/generated/"))
            self.assertEqual(
                len(record.result["image"]["urls"]),
                RESULT_IMAGE_COUNT,
            )
            self.assertEqual(
                record.result["image"]["count"],
                RESULT_IMAGE_COUNT,
            )
            self.assertEqual(
                record.result["image"]["expected_count"],
                RESULT_IMAGE_COUNT,
            )
            self.assertEqual(
                record.result["image"]["url"],
                record.result["image"]["urls"][0],
            )
            self.assertEqual(fake_pixpark.prompts, [record.result["positive_prompt"]])
            self.assertTrue(record.image_bytes)

            fake_model = manager.client
            fake_model.calls = 0
            manager.regenerate_prompt(record.id)
            for _ in range(200):
                if record.status in {"prompt_ready", "failed"}:
                    break
                await asyncio.sleep(0.01)

            self.assertEqual(record.status, "prompt_ready", record.error)
            self.assertEqual(fake_model.calls, 2)
            self.assertTrue(record.result["validation"]["pass"])
            self.assertEqual(record.result["image"]["status"], "ready")
            self.assertTrue(record.image_bytes)

            manager.generate_image(record.id)
            for _ in range(200):
                if record.status in {"complete", "failed"}:
                    break
                await asyncio.sleep(0.01)

            manager.regenerate_image(record.id)
            for _ in range(200):
                if record.status in {"complete", "failed"}:
                    break
                await asyncio.sleep(0.01)

            self.assertEqual(record.status, "complete", record.error)
            self.assertEqual(len(fake_pixpark.prompts), 3)
            self.assertTrue(record.image_bytes)

    async def test_partial_image_batch_is_preserved_and_labeled(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            style_path = root / "style-reference.png"
            generated_dir = root / "generated"
            generated_dir.mkdir()
            Image.new("RGB", (400, 400), "gray").save(style_path)
            settings = make_settings(
                style_path,
                generated_dir=generated_dir,
                image_generation_enabled=True,
            )

            class PartialPixPark:
                async def generate(self, **kwargs) -> PixParkImageResult:
                    outputs: list[str] = []
                    for index in range(1, 3):
                        output = (
                            settings.generated_dir
                            / f"{kwargs['job_id']}-{index}.png"
                        )
                        Image.new("RGB", (32, 32), "cyan").save(output)
                        outputs.append(output.name)
                    return PixParkImageResult(
                        task_code="partial-task",
                        filenames=tuple(outputs),
                    )

            manager = JobManager(
                settings,
                client=FakeModelClient(),
                pixpark_factory=lambda _: PartialPixPark(),
            )
            record = manager.create(
                filename="需求图.png",
                media_type="image/png",
                image_bytes=_make_image_bytes(),
                note="",
            )
            for _ in range(200):
                if record.status in {"prompt_ready", "failed"}:
                    break
                await asyncio.sleep(0.01)

            manager.generate_image(record.id)
            for _ in range(200):
                if record.status in {"complete", "failed"}:
                    break
                await asyncio.sleep(0.01)

            self.assertEqual(record.status, "complete", record.error)
            self.assertEqual(record.result["image"]["status"], "partial")
            self.assertEqual(record.result["image"]["count"], 2)
            self.assertEqual(record.result["image"]["expected_count"], 4)
            self.assertEqual(len(record.result["image"]["urls"]), 2)
            self.assertIn("2/4", record.result["image"]["message"])

    async def test_non_square_request_skips_fixed_square_generator(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            style_path = root / "style-reference.png"
            generated_dir = root / "generated"
            generated_dir.mkdir()
            Image.new("RGB", (400, 400), "gray").save(style_path)
            settings = make_settings(
                style_path,
                generated_dir=generated_dir,
                image_generation_enabled=True,
            )
            fake_pixpark = FakePixPark(settings)
            manager = JobManager(
                settings,
                client=OtherRatioModelClient(),
                pixpark_factory=lambda _: fake_pixpark,
            )
            record = manager.create(
                filename="需求图.png",
                media_type="image/png",
                image_bytes=_make_image_bytes(),
                note="保持 16:9",
            )

            for _ in range(200):
                if record.status in {"prompt_ready", "failed"}:
                    break
                await asyncio.sleep(0.01)

            self.assertEqual(record.status, "prompt_ready", record.error)
            self.assertEqual(
                record.result["image"]["status"],
                "incompatible_aspect_ratio",
            )
            self.assertEqual(fake_pixpark.prompts, [])
            self.assertTrue(record.image_bytes)

    async def test_history_lists_prompt_ready_job_without_prompt_body(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            style_path = Path(directory) / "style-reference.png"
            Image.new("RGB", (400, 400), "gray").save(style_path)
            manager = JobManager(make_settings(style_path), client=FakeModelClient())
            record = manager.create(
                filename="历史需求图.png",
                media_type="image/png",
                image_bytes=_make_image_bytes(),
                note="",
            )

            for _ in range(100):
                if record.status in {"prompt_ready", "failed"}:
                    break
                await asyncio.sleep(0.01)

            [summary] = manager.history()
            self.assertEqual(summary["id"], record.id)
            self.assertEqual(summary["status"], "prompt_ready")
            self.assertTrue(summary["has_prompt"])
            self.assertNotIn("positive_prompt", summary)

    async def test_queue_capacity_rejects_new_job(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            style_path = Path(directory) / "style-reference.png"
            Image.new("RGB", (400, 400), "gray").save(style_path)
            settings = make_settings(style_path)
            object.__setattr__(settings, "max_pending_jobs", 1)
            manager = JobManager(settings, client=FakeModelClient())
            image_bytes = _make_image_bytes()

            first = manager.create(
                filename="第一张.png",
                media_type="image/png",
                image_bytes=image_bytes,
                note="",
            )
            with self.assertRaises(QueueCapacityError):
                manager.create(
                    filename="第二张.png",
                    media_type="image/png",
                    image_bytes=image_bytes,
                    note="",
                )
            manager.cancel(first.id)
            await asyncio.sleep(0)

    async def test_cancel_releases_job_and_image_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            style_path = Path(directory) / "style-reference.png"
            Image.new("RGB", (400, 400), "gray").save(style_path)
            manager = JobManager(
                make_settings(style_path),
                client=FakeModelClient(),
            )
            record = manager.create(
                filename="需求图.png",
                media_type="image/png",
                image_bytes=_make_image_bytes(),
                note="",
            )

            manager.cancel(record.id)
            await asyncio.sleep(0)

            self.assertIsNone(manager.get(record.id))
            self.assertEqual(record.image_bytes, b"")


class PixParkContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_download_uses_real_image_format_when_mime_is_wrong(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            style_path = root / "style-reference.png"
            generated_dir = root / "generated"
            generated_dir.mkdir()
            Image.new("RGB", (40, 40), "gray").save(style_path)
            settings = make_settings(
                style_path,
                generated_dir=generated_dir,
                image_generation_enabled=True,
            )
            image_buffer = io.BytesIO()
            Image.new("RGB", (64, 64), "orange").save(
                image_buffer,
                format="JPEG",
            )

            async def handler(_: httpx.Request) -> httpx.Response:
                return httpx.Response(
                    200,
                    headers={"Content-Type": "image/png"},
                    content=image_buffer.getvalue(),
                )

            client = PixParkClient(settings)
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as http_client:
                filename = await client._download_result(
                    http_client,
                    job_id="f" * 32,
                    url="https://cdn.example.test/result.png",
                )

            self.assertEqual(filename, f"{'f' * 32}.jpg")
            with Image.open(generated_dir / filename) as saved:
                self.assertEqual(saved.format, "JPEG")

    async def test_generation_uploads_two_independent_reference_images(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            style_path = root / "style-reference.png"
            generated_dir = root / "generated"
            generated_dir.mkdir()
            Image.new("RGB", (40, 40), "gray").save(style_path)
            settings = make_settings(
                style_path,
                generated_dir=generated_dir,
                image_generation_enabled=True,
            )

            class CapturingClient(PixParkClient):
                def __init__(self, configured: Settings) -> None:
                    super().__init__(configured)
                    self.tool_calls: list[tuple[str, dict]] = []
                    self.uploads: list[dict] = []
                    self.state_existed_before_poll = False

                async def _initialize(self, client) -> None:
                    return None

                async def _upload_image(self, client, **kwargs) -> str:
                    self.uploads.append(kwargs)
                    return (
                        "https://cdn.example.test/"
                        f"input-{len(self.uploads)}.png"
                    )

                async def _call_tool(self, client, name, arguments):
                    self.tool_calls.append((name, arguments))
                    return {"taskCode": "task-123", "roundPeriod": 1}

                async def _poll_and_download(self, client, **kwargs):
                    self.state_existed_before_poll = (
                        self.state_store.read(kwargs["job_id"])["taskCode"]
                        == kwargs["task_code"]
                    )
                    return PixParkImageResult(
                        task_code=kwargs["task_code"],
                        filenames=tuple(
                            f"{kwargs['job_id']}-{index}.png"
                            for index in range(1, RESULT_IMAGE_COUNT + 1)
                        ),
                    )

            input_bytes = _make_image_bytes()
            client = CapturingClient(settings)
            await client.generate(
                job_id="a" * 32,
                input_filename="需求图.png",
                input_media_type="image/png",
                input_bytes=input_bytes,
                prompt="纯净正向提示词",
                on_status=lambda *_: None,
            )

            self.assertEqual(len(client.uploads), 2)
            self.assertEqual(client.uploads[0]["filename"], "需求图.png")
            self.assertEqual(client.uploads[0]["media_type"], "image/png")
            self.assertEqual(client.uploads[0]["data"], input_bytes)
            self.assertEqual(
                client.uploads[1]["filename"],
                "style-reference.png",
            )
            self.assertEqual(client.uploads[1]["media_type"], "image/png")
            self.assertEqual(
                client.uploads[1]["data"],
                style_path.read_bytes(),
            )
            name, arguments = client.tool_calls[0]
            self.assertEqual(name, "imageGenerationUsingPOST")
            self.assertEqual(
                arguments["imageUrls"],
                [
                    "https://cdn.example.test/input-1.png",
                    "https://cdn.example.test/input-2.png",
                ],
            )
            self.assertEqual(arguments["inputPrompt"], "纯净正向提示词")
            self.assertNotIn("negativePrompt", arguments)
            self.assertEqual(arguments["imageNum"], RESULT_IMAGE_COUNT)
            self.assertTrue(client.state_existed_before_poll)
            self.assertEqual(len(client.tool_calls), 1)
            for key, value in FIXED_CONTRACT.items():
                self.assertEqual(arguments[key], value)

    async def test_resume_queries_same_task_without_recreating(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            style_path = root / "style-reference.png"
            generated_dir = root / "generated"
            generated_dir.mkdir()
            Image.new("RGB", (40, 40), "gray").save(style_path)
            settings = make_settings(
                style_path,
                generated_dir=generated_dir,
                image_generation_enabled=True,
            )

            class ResumeClient(PixParkClient):
                def __init__(self, configured: Settings) -> None:
                    super().__init__(configured)
                    self.polled_task_code = ""

                async def _initialize(self, client) -> None:
                    return None

                async def _poll_and_download(self, client, **kwargs):
                    self.polled_task_code = kwargs["task_code"]
                    return PixParkImageResult(
                        task_code=kwargs["task_code"],
                        filenames=tuple(
                            f"{kwargs['job_id']}-{index}.png"
                            for index in range(1, RESULT_IMAGE_COUNT + 1)
                        ),
                    )

            client = ResumeClient(settings)
            client.state_store.write(
                "c" * 32,
                status="timeout",
                task_code="existing-remote-task",
            )
            result = await client.resume(
                job_id="c" * 32,
                on_status=lambda *_: None,
            )
            self.assertEqual(client.polled_task_code, "existing-remote-task")
            self.assertEqual(result.task_code, "existing-remote-task")

    async def test_job_manager_recovers_remote_image_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            style_path = root / "style-reference.png"
            generated_dir = root / "generated"
            generated_dir.mkdir()
            Image.new("RGB", (40, 40), "gray").save(style_path)
            settings = make_settings(
                style_path,
                generated_dir=generated_dir,
                image_generation_enabled=True,
            )
            job_id = "e" * 32
            PixParkStateStore(generated_dir / "pixpark-state").write(
                job_id,
                status="timeout",
                task_code="persisted-remote-task",
            )

            class ResumeOnlyPixPark:
                generate_calls = 0
                resume_calls = 0

                def __init__(self, configured: Settings) -> None:
                    self.settings = configured

                async def generate(self, **kwargs):
                    type(self).generate_calls += 1
                    raise AssertionError("恢复流程不得重新创建任务")

                async def resume(self, **kwargs):
                    type(self).resume_calls += 1
                    outputs: list[str] = []
                    for index in range(1, RESULT_IMAGE_COUNT + 1):
                        output = (
                            self.settings.generated_dir
                            / f"{kwargs['job_id']}-{index}.png"
                        )
                        Image.new("RGB", (32, 32), "teal").save(output)
                        outputs.append(output.name)
                    return PixParkImageResult(
                        task_code="persisted-remote-task",
                        filenames=tuple(outputs),
                    )

            manager = JobManager(
                settings,
                client=FakeModelClient(),
                pixpark_factory=ResumeOnlyPixPark,
            )
            recovered = manager.get(job_id)
            self.assertIsNotNone(recovered)
            assert recovered is not None
            self.assertTrue(recovered.result["recovered_image_only"])
            self.assertTrue(recovered.result["image"]["resumable"])

            resumed = manager.resume_image(job_id)
            assert resumed.task is not None
            await resumed.task
            self.assertEqual(ResumeOnlyPixPark.generate_calls, 0)
            self.assertEqual(ResumeOnlyPixPark.resume_calls, 1)
            self.assertEqual(resumed.result["image"]["status"], "completed")
            self.assertEqual(
                len(resumed.result["image"]["urls"]),
                RESULT_IMAGE_COUNT,
            )

    async def test_completed_but_unapproved_result_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            style_path = root / "style-reference.png"
            generated_dir = root / "generated"
            generated_dir.mkdir()
            Image.new("RGB", (40, 40), "gray").save(style_path)
            settings = make_settings(
                style_path,
                generated_dir=generated_dir,
                image_generation_enabled=True,
            )

            class AuditClient(PixParkClient):
                async def _initialize(self, client) -> None:
                    return None

                async def _call_tool(self, client, name, arguments):
                    self.assert_query_name = name
                    return {
                        "taskStatus": 2,
                        "result": [
                            {
                                "imageAuditStatus": False,
                                "targetImageUrl": "https://cdn.example.test/rejected.png",
                            }
                        ],
                    }

            client = AuditClient(settings)
            client.state_store.write(
                "d" * 32,
                status="created",
                task_code="unapproved-task",
            )
            with self.assertRaises(PixParkRejected):
                await client.resume(
                    job_id="d" * 32,
                    on_status=lambda *_: None,
                )
            self.assertEqual(client.assert_query_name, "queryTaskUsingPOST")

    async def test_completed_task_downloads_four_approved_images(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            style_path = root / "style-reference.png"
            generated_dir = root / "generated"
            generated_dir.mkdir()
            Image.new("RGB", (40, 40), "gray").save(style_path)
            settings = make_settings(
                style_path,
                generated_dir=generated_dir,
                image_generation_enabled=True,
            )

            class BatchClient(PixParkClient):
                def __init__(self, configured: Settings) -> None:
                    super().__init__(configured)
                    self.download_slots: list[int] = []

                async def _initialize(self, client) -> None:
                    return None

                async def _call_tool(self, client, name, arguments):
                    self.query_name = name
                    return {
                        "taskStatus": 2,
                        "result": [
                            {
                                "imageAuditStatus": True,
                                "targetImageUrl": (
                                    f"https://cdn.example.test/result-{index}.png"
                                ),
                            }
                            for index in range(1, RESULT_IMAGE_COUNT + 1)
                        ]
                        + [
                            {
                                "imageAuditStatus": False,
                                "targetImageUrl": (
                                    "https://cdn.example.test/rejected.png"
                                ),
                            }
                        ],
                    }

                async def _download_result(
                    self,
                    client,
                    *,
                    job_id,
                    url,
                    slot=None,
                ):
                    assert slot is not None
                    self.download_slots.append(slot)
                    output = self.settings.generated_dir / f"{job_id}-{slot}.png"
                    Image.new("RGB", (32, 32), "blue").save(output)
                    return output.name

            job_id = "9" * 32
            client = BatchClient(settings)
            client.state_store.write(
                job_id,
                status="created",
                task_code="four-image-task",
            )
            result = await client.resume(
                job_id=job_id,
                on_status=lambda *_: None,
            )

            self.assertEqual(client.query_name, "queryTaskUsingPOST")
            self.assertEqual(
                client.download_slots,
                list(range(1, RESULT_IMAGE_COUNT + 1)),
            )
            self.assertEqual(len(result.filenames), RESULT_IMAGE_COUNT)
            state = client.state_store.read(job_id)
            self.assertEqual(state["status"], "completed")
            self.assertEqual(state["outputNames"], list(result.filenames))

    async def test_state_file_excludes_credentials_and_signed_urls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = PixParkStateStore(Path(directory))
            store.write(
                "b" * 32,
                status="created",
                task_code="remote-task",
                error=(
                    "Bearer secret-token "
                    "https://signed.example.test/object?signature=secret"
                ),
            )
            text = store.path_for("b" * 32).read_text(encoding="utf-8")
            data = json.loads(text)
            self.assertEqual(data["taskCode"], "remote-task")
            self.assertNotIn("secret-token", text)
            self.assertNotIn("signed.example.test", text)

    async def test_sse_response_selects_matching_request_id(self) -> None:
        message = parse_mcp_response(
            'data: {"jsonrpc":"2.0","id":1,"result":{}}\n\n'
            'data: {"jsonrpc":"2.0","id":2,"result":{"ok":true}}\n\n',
            "text/event-stream",
            2,
        )
        self.assertTrue(message["result"]["ok"])


def _make_image_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (400, 400), "white").save(buffer, format="PNG")
    return buffer.getvalue()


if __name__ == "__main__":
    unittest.main()

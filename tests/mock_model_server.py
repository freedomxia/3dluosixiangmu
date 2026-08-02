"""本地浏览器验收用的 OpenAI 兼容模型桩。"""

from __future__ import annotations

import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VALID_OUTPUT = (PROJECT_ROOT / "tests" / "fixtures" / "valid-output.md").read_text(
    encoding="utf-8"
)

CLASSIFICATION = json.dumps(
    {
        "task_type": "LOCK_LAYOUT_EDIT",
        "needs_creative_cases": False,
        "triggers": {
            "special_material": False,
            "text_logo_time": False,
            "haoyue_brand": False,
        },
        "clarification": {
            "required": False,
            "reason": "none",
            "question": "",
        },
        "anniversary_source": "unknown",
        "allow_aspect_ratio": False,
        "requested_aspect_ratio": "none",
        "routing_summary": "浏览器验收用成熟布局任务",
    },
    ensure_ascii=False,
)

PROMPT_AUDIT = json.dumps(
    {
        "pass": True,
        "errors": [],
        "warnings": [],
        "summary": "浏览器验收语义审查通过",
        "checks": {
            "hard_requirements": "pass",
            "reference_scope": "pass",
            "layout_permission": "pass",
            "enrichment_event": "pass",
            "reachability": "pass",
            "clustering": "pass",
            "positive_prompt_coverage": "pass",
        },
    },
    ensure_ascii=False,
)

IMAGE_AUDIT = json.dumps(
    {
        "pass": True,
        "errors": [],
        "warnings": [],
        "summary": "浏览器验收结果图复查通过",
        "per_image": [
            {"index": index, "pass": True, "errors": []}
            for index in range(1, 5)
        ],
        "best_indices": [1, 2, 3, 4],
    },
    ensure_ascii=False,
)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        delay = float(os.getenv("MOCK_MODEL_DELAY_SECONDS", "0") or 0)
        if delay > 0:
            time.sleep(delay)
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length))
        system_text = body["messages"][0]["content"]
        if "任务路由器" in system_text:
            content = CLASSIFICATION
        elif "独立语义审查器" in system_text:
            content = PROMPT_AUDIT
        elif "生成结果的独立需求符合度审查器" in system_text:
            content = IMAGE_AUDIT
        else:
            content = VALID_OUTPUT
        payload = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": content,
                        }
                    }
                ]
            },
            ensure_ascii=False,
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 19000), Handler).serve_forever()

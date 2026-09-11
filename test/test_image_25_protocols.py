"""2.5 从 HTTP/任务入口贯通到统一图片请求的离线集成回归。"""

import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import ai
from api.errors import install_exception_handlers
from services.image_task_service import ImageTaskService
from services.protocol import openai_v1_chat_complete as chat
from services.protocol import openai_v1_image_edit as edits
from services.protocol import openai_v1_image_generations as generations
from services.protocol import openai_v1_response as responses
from services.protocol.conversation import ImageOutput
from test.test_image_task_service import wait_for_task


MODEL = "gpt-image-2.5-sunburst"
HEADERS = {"Authorization": "Bearer chatgpt2api"}
USAGE = {"input_tokens": 20, "output_tokens": 60, "total_tokens": 80}
IMAGE = base64.b64encode(b"fixture").decode("ascii")


class Image25ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.upstream_usage = USAGE

        def image_pool(request):
            self.requests.append(request)
            return iter([ImageOutput(
                kind="result", model=request.model, index=1, total=1,
                data=[{"b64_json": IMAGE, "url": "/images/fixture.png"}],
                usage=self.upstream_usage,
                usage_source="upstream" if self.upstream_usage is not None else "unavailable",
            )])

        for module in (generations, edits, chat, responses):
            patcher = mock.patch.object(module, "stream_image_outputs_with_pool", side_effect=image_pool)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(ai, "filter_or_log", mock.AsyncMock())
        patcher.start()
        self.addCleanup(patcher.stop)
        app = FastAPI()
        install_exception_handlers(app)
        app.include_router(ai.create_router())
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_generations_preserves_model_quality_and_real_usage(self):
        response = self.client.post("/v1/images/generations", headers=HEADERS, json={
            "prompt": "fixture", "model": MODEL, "quality": "max", "size": "2048x2048",
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.requests[0].model, MODEL)
        self.assertEqual(self.requests[0].quality, "max")
        self.assertEqual(self.requests[0].size, "2048x2048")
        self.assertEqual(response.json()["usage"], USAGE)
        self.assertEqual(response.json()["usage_source"], "upstream")

    def test_generations_does_not_fabricate_25_usage(self):
        self.upstream_usage = None
        response = self.client.post("/v1/images/generations", headers=HEADERS, json={"prompt": "fixture", "model": MODEL})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn("usage", response.json())
        self.assertEqual(response.json()["usage_source"], "unavailable")

    def test_legacy_default_is_not_changed_to_25(self):
        response = self.client.post("/v1/images/generations", headers=HEADERS, json={"prompt": "fixture"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.requests[0].model, "gpt-image-2")

    def test_stream_generation_keeps_upstream_usage(self):
        response = self.client.post("/v1/images/generations", headers=HEADERS, json={"prompt": "fixture", "model": MODEL, "stream": True})
        payloads = [json.loads(line[5:]) for line in response.text.splitlines() if line.startswith("data:") and line[5:].strip() != "[DONE]"]
        self.assertEqual(payloads[0]["model"], MODEL)
        self.assertEqual(payloads[0]["usage"], USAGE)

    def test_multipart_edit_uses_25_and_all_reference_images(self):
        response = self.client.post("/v1/images/edits", headers=HEADERS, data={
            "prompt": "edit", "model": MODEL, "quality": "xhigh", "size": "1024x1024",
        }, files=[("image", ("one.png", b"one", "image/png")), ("image", ("two.png", b"two", "image/png"))])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.requests[0].model, MODEL)
        self.assertEqual(self.requests[0].quality, "xhigh")
        self.assertEqual(len(self.requests[0].images), 2)

    def test_invalid_25_options_return_400_before_pool(self):
        for extra in ({"size": "1024x1365"}, {"quality": "hd"}):
            response = self.client.post("/v1/images/generations", headers=HEADERS, json={"prompt": "fixture", "model": MODEL, **extra})
            self.assertEqual(response.status_code, 400, response.text)
            self.assertEqual(response.json()["error"]["code"], "invalid_parameter")
        self.assertEqual(self.requests, [])

    def test_responses_reads_tool_model_separately_from_outer_model(self):
        response = self.client.post("/v1/responses", headers=HEADERS, json={
            "model": "gpt-5", "input": "fixture",
            "tools": [{"type": "image_generation", "model": MODEL, "quality": "max", "size": "2048x2048"}],
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["model"], "gpt-5")
        self.assertEqual(response.json()["usage"], USAGE)
        self.assertEqual(self.requests[0].model, MODEL)
        self.assertEqual(self.requests[0].quality, "max")

    def test_responses_keeps_legacy_top_level_image_model(self):
        response = self.client.post("/v1/responses", headers=HEADERS, json={
            "model": "codex-gpt-image-2", "input": "fixture", "tools": [{"type": "image_generation"}],
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.requests[0].model, "codex-gpt-image-2")

    def test_responses_preserves_multiple_images_in_typed_message(self):
        def image_part(data):
            return {"type": "input_image", "image_url": "data:image/png;base64," + base64.b64encode(data).decode()}

        response = self.client.post("/v1/responses", headers=HEADERS, json={
            "model": "gpt-5",
            "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "edit"}, image_part(b"one"), image_part(b"two")]}],
            "tools": [{"type": "image_generation", "model": MODEL}],
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(self.requests[0].images), 2)

    def test_responses_without_usage_does_not_report_estimate(self):
        self.upstream_usage = None
        response = self.client.post("/v1/responses", headers=HEADERS, json={
            "model": "gpt-5", "input": "fixture", "tools": [{"type": "image_generation", "model": MODEL}],
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn("usage", response.json())
        self.assertEqual(response.json()["usage_source"], "unavailable")

    def test_unknown_response_tool_model_is_rejected(self):
        response = self.client.post("/v1/responses", headers=HEADERS, json={
            "model": "gpt-5", "input": "fixture", "stream": True,
            "tools": [{"type": "image_generation", "model": "unknown-image-model"}],
        })
        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(self.requests, [])

    def test_chat_image_modes_forward_quality_and_size(self):
        for streaming in (False, True):
            response = self.client.post("/v1/chat/completions", headers=HEADERS, json={
                "model": MODEL, "messages": [{"role": "user", "content": "fixture"}],
                "size": "2048x2048", "quality": "xhigh", "stream": streaming,
            })
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(self.requests[-1].size, "2048x2048")
            self.assertEqual(self.requests[-1].quality, "xhigh")

    def test_image_task_persists_usage_source_and_model(self):
        owner = {"id": "fixture-owner", "role": "user"}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tasks.json"
            service = ImageTaskService(path, generation_handler=lambda _body: {"data": [{"url": "/fixture"}], "usage_source": "unavailable"})
            service.submit_generation(owner, client_task_id="fixture", prompt="fixture", model=MODEL, size=None)
            task = wait_for_task(service, owner, "fixture", "success")
            self.assertEqual(task["model"], MODEL)
            self.assertEqual(task["usage_source"], "unavailable")
            restored = ImageTaskService(path).list_tasks(owner, ["fixture"])["items"][0]
            self.assertEqual(restored["usage_source"], "unavailable")


if __name__ == "__main__":
    unittest.main()

"""网页 GIF 的公开接口回归；动画样本为本地合成，不代表上游能力。"""

import base64
import json
from io import BytesIO
from unittest import mock

from PIL import Image

from services import openai_backend_api as backend_module
from api import image_tasks as image_tasks_api
from services.image_task_service import ImageTaskService
from services.config import config
from test.test_free_web_image import HEADERS
from test.test_web_image_26 import WebImageResumeFixture


def animated_gif() -> bytes:
    stream = BytesIO()
    Image.new("RGB", (16, 12), "red").save(
        stream, format="GIF", save_all=True,
        append_images=[Image.new("RGB", (16, 12), "blue")],
        duration=[200, 300], loop=0,
    )
    return stream.getvalue()


class WebGifTests(WebImageResumeFixture):
    def test_image_capabilities_exposes_only_gif_controls_to_authenticated_clients(self):
        self.enable_fixture_upstream()
        self.client.app.include_router(image_tasks_api.create_router())
        with mock.patch.dict(config.data, {"image_web_gif_enabled": False, "image_gif_poll_timeout_secs": 480}):
            response = self.client.get("/api/image-capabilities", headers=HEADERS)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"web_gif_enabled": False, "gif_poll_timeout_secs": 480})
        self.assertEqual(self.client.get("/api/image-capabilities").status_code, 401)
        self.assertEqual(self.requests, [])

    def test_generation_preserves_real_animation_and_uses_a_gif_url(self):
        self.enable_fixture_upstream()
        original = animated_gif()
        with mock.patch.object(backend_module.OpenAIBackendAPI, "download_image_bytes", return_value=[original]):
            response = self.client.post("/v1/images/generations", headers=HEADERS, json={
                "model": "gpt-image-2.6-flare", "prompt": "生成小球左右移动的循环动画",
                "output_format": "gif", "response_format": "b64_json",
            })
        self.assertEqual(response.status_code, 200, response.text)
        item = response.json()["data"][0]
        self.assertEqual(base64.b64decode(item["b64_json"]), original)
        self.assertTrue(item["url"].endswith(".gif"), item["url"])
        with Image.open(BytesIO(base64.b64decode(item["b64_json"]))) as image:
            self.assertEqual(image.format, "GIF")
            self.assertEqual(image.n_frames, 2)

    def test_frame_options_are_prompt_hints_and_do_not_require_exact_frame_counts(self):
        self.enable_fixture_upstream()
        with mock.patch.object(backend_module.OpenAIBackendAPI, "download_image_bytes", return_value=[animated_gif()]):
            response = self.client.post("/v1/images/generations", headers=HEADERS, json={
                "model": "gpt-image-2.6-sunburst", "prompt": "生成连续循环动画",
                "output_format": " GIF ", "frame_count": "9", "frame_duration_ms": "200",
                "response_format": "url",
            })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["data"][0]["url"].endswith(".gif"))
        self.assertNotIn("b64_json", response.json()["data"][0])
        for request in self.requests:
            payload = request.get("json", {})
            self.assertEqual(payload.get("model"), "gpt-image-2.6-sunburst")
            for field in ("output_format", "frame_count", "frame_duration_ms"):
                self.assertNotIn(field, payload)
        submission = next(item["json"] for item in self.requests if item["url"].endswith("/f/conversation"))
        prompt = submission["messages"][0]["content"]["parts"][0]
        self.assertIn("多帧动画 GIF", prompt)
        self.assertIn("9 帧", prompt)
        self.assertIn("200 毫秒", prompt)

    def test_static_reference_edits_preserve_the_gif_target_in_json_and_multipart(self):
        self.enable_fixture_upstream()
        original = animated_gif()
        reference = self.image
        options = {
            "model": "gpt-image-2.6-flare", "prompt": "让参考图中的小球上下移动",
            "output_format": "gif", "frame_count": "5", "frame_duration_ms": "300",
        }
        cases = (
            {"data": options, "files": {"image": ("reference.png", reference, "image/png")}},
            {"json": {**options, "images": [{"image_url": "data:image/png;base64," + base64.b64encode(reference).decode()}]}},
        )
        with mock.patch.object(backend_module.OpenAIBackendAPI, "download_image_bytes", return_value=[original]):
            for arguments in cases:
                with self.subTest(kind=next(iter(arguments))):
                    self.requests.clear()
                    self.accounts.update_account("fixture-web-free", {"quota": 3, "status": "正常"})
                    response = self.client.post("/v1/images/edits", headers=HEADERS, **arguments)
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(base64.b64decode(response.json()["data"][0]["b64_json"]), original)
                    submission = next(item["json"] for item in self.requests if item["url"].endswith("/f/conversation"))
                    prompt = "".join(part for part in submission["messages"][0]["content"]["parts"] if isinstance(part, str))
                    self.assertIn("5 帧", prompt)
                    self.assertIn("300 毫秒", prompt)
                    self.assertEqual(len(submission["messages"][0]["metadata"]["attachments"]), 1)

    def test_chat_preserves_gif_in_streaming_and_complete_responses(self):
        self.enable_fixture_upstream()
        original = animated_gif()
        with mock.patch.object(backend_module.OpenAIBackendAPI, "download_image_bytes", return_value=[original]):
            for stream in (False, True):
                with self.subTest(stream=stream):
                    self.requests.clear()
                    response = self.client.post("/v1/chat/completions", headers=HEADERS, json={
                        "model": "gpt-image-2.6-flare", "messages": [{"role": "user", "content": "生成真实循环动画"}],
                        "output_format": "gif", "frame_count": 9, "stream": stream,
                    })
                    self.assertEqual(response.status_code, 200, response.text)
                    if stream:
                        chunks = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ") and line != "data: [DONE]"]
                        self.assertTrue(all("error" not in chunk for chunk in chunks), chunks)
                        content = "".join(choice.get("delta", {}).get("content", "") for chunk in chunks for choice in chunk.get("choices", []))
                    else:
                        content = response.json()["choices"][0]["message"]["content"]
                    self.assertIn("data:image/gif;base64,", content)
                    self.assertIn(base64.b64encode(original).decode(), content)

    def test_responses_merges_gif_hints_without_overriding_them_with_png_defaults(self):
        self.enable_fixture_upstream()
        original = animated_gif()
        for top_format, tool_format in (("png", "gif"), ("gif", "png")):
            for stream in (False, True):
                with self.subTest(top_format=top_format, stream=stream):
                    self.accounts.update_account("fixture-web-free", {"quota": 3, "status": "正常"})
                    self.requests.clear()
                    with mock.patch.object(backend_module.OpenAIBackendAPI, "download_image_bytes", return_value=[original]):
                        response = self.client.post("/v1/responses", headers=HEADERS, json={
                            "model": "gpt-5", "input": "生成真实多帧循环动画", "stream": stream,
                            "output_format": top_format, "frame_count": 9,
                            "tools": [{"type": "image_generation", "model": "gpt-image-2.6-flare",
                                       "output_format": tool_format, "frame_duration_ms": 200}],
                        })
                    self.assertEqual(response.status_code, 200, response.text)
                    if stream:
                        chunks = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ") and line != "data: [DONE]"]
                        self.assertTrue(all("error" not in chunk for chunk in chunks), chunks)
                        body = next(chunk["response"] for chunk in chunks if chunk.get("type") == "response.completed")
                    else:
                        body = response.json()
                    self.assertEqual(body["model"], "gpt-5")
                    self.assertEqual(base64.b64decode(body["output"][0]["result"]), original)
                    submission = next(item["json"] for item in self.requests if item["url"].endswith("/f/conversation"))
                    self.assertIn("9 帧", submission["messages"][0]["content"]["parts"][0])

    def test_task_reload_preserves_gif_hints_and_resumes_the_original_conversation(self):
        task_path = self.enable_resume_poll_fixture()
        original = animated_gif()
        timeout = backend_module.ImagePollTimeoutError("ChatGPT 生图超时")
        timeout.conversation_id = "fixture-conversation"
        with mock.patch.object(backend_module.OpenAIBackendAPI, "download_image_bytes", side_effect=[timeout, [original]]):
            response = self.client.post("/api/image-tasks/generations", headers=HEADERS, json={
                "client_task_id": "gif-resume-reload", "model": "gpt-image-2.6-flare", "prompt": "生成循环动画",
                "output_format": "gif", "frame_count": 9, "frame_duration_ms": 200,
            })
            self.assertEqual(response.status_code, 200, response.text)
            failed = self.wait_for_http_task("gif-resume-reload")
            self.assertEqual(failed["status"], "error", failed)
            self.assertEqual(failed.get("output_format"), "gif", failed)
            self.assertEqual(failed.get("frame_count"), 9, failed)
            self.assertEqual(failed.get("frame_duration_ms"), 200, failed)
            with mock.patch.object(image_tasks_api, "image_task_service", ImageTaskService(task_path)):
                resumed = self.client.post("/api/image-tasks/gif-resume-reload/resume-poll", headers=HEADERS, json={"extra_timeout_secs": 5})
                self.assertEqual(resumed.status_code, 200, resumed.text)
                task = self.wait_for_http_task("gif-resume-reload")
        self.assertEqual(task["status"], "success", task)
        self.assertEqual(task.get("output_format"), "gif", task)
        self.assertEqual(task["conversation_id"], "fixture-conversation")
        self.assertEqual(base64.b64decode(task["data"][0]["b64_json"]), original)
        self.assertTrue(task["data"][0]["url"].endswith(".gif"))
        self.assertEqual(sum(item["url"].endswith("/f/conversation") for item in self.requests), 1)

    def test_gif_requests_ignore_static_companion_previews(self):
        self.enable_fixture_upstream()
        original = animated_gif()
        for payloads in ([original, self.image], [self.image, original]):
            with self.subTest(gif_first=payloads[0] == original):
                self.requests.clear()
                self.accounts.update_account("fixture-web-free", {"quota": 3, "status": "正常"})
                with mock.patch.object(backend_module.OpenAIBackendAPI, "download_image_bytes", return_value=payloads):
                    response = self.client.post("/v1/images/generations", headers=HEADERS, json={
                        "model": "gpt-image-2.6-flare", "prompt": "生成循环动画", "output_format": "gif",
                    })
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(len(response.json()["data"]), 1)
                self.assertEqual(base64.b64decode(response.json()["data"][0]["b64_json"]), original)
                self.assertEqual(sum(item["url"].endswith("/f/conversation") for item in self.requests), 1)

    def test_animated_references_are_rejected_before_mask_compositing(self):
        self.enable_fixture_upstream()
        original = animated_gif()
        with mock.patch.object(backend_module.OpenAIBackendAPI, "download_image_bytes", return_value=[original]):
            response = self.client.post("/v1/images/edits", headers=HEADERS, json={
                "model": "gpt-image-2.6-flare", "prompt": "继续修改动画", "output_format": "gif",
                "images": [{"image_url": "data:image/gif;base64," + base64.b64encode(original).decode()}],
                "mask": "data:image/png;base64," + base64.b64encode(self.image).decode(),
            })
        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(response.json()["error"]["param"], "image")
        self.assertEqual(self.requests, [])

    def test_animated_masks_are_rejected_before_compositing(self):
        self.enable_fixture_upstream()
        mask = animated_gif()
        for multipart in (False, True):
            with self.subTest(multipart=multipart):
                options = {"model": "gpt-image-2.6-flare", "prompt": "生成循环动画", "output_format": "gif"}
                arguments = (
                    {"data": options, "files": {
                        "image": ("reference.png", self.image, "image/png"),
                        "mask": ("mask.gif", mask, "image/gif"),
                    }} if multipart else {"json": {
                        **options, "images": [{"image_url": "data:image/png;base64," + base64.b64encode(self.image).decode()}],
                        "mask": "data:image/gif;base64," + base64.b64encode(mask).decode(),
                    }}
                )
                response = self.client.post("/v1/images/edits", headers=HEADERS, **arguments)
                self.assertEqual(response.status_code, 400, response.text)
                self.assertEqual(response.json()["error"]["param"], "mask")
                self.assertEqual(self.requests, [])

    def test_damaged_gif_inputs_cannot_be_flattened_to_their_decodable_first_frame(self):
        self.enable_fixture_upstream()
        # 这个固定截断样本的首帧可读，但后续帧目录已损坏，不能先合成为静态 PNG。
        damaged = animated_gif()[:91]
        with Image.open(BytesIO(damaged)) as first_frame:
            first_frame.convert("RGBA").load()
        for param in ("image", "mask"):
            for multipart in (False, True):
                with self.subTest(param=param, multipart=multipart):
                    reference = damaged if param == "image" else self.image
                    mask = damaged if param == "mask" else self.image
                    reference_mime = "image/gif" if param == "image" else "image/png"
                    mask_mime = "image/gif" if param == "mask" else "image/png"
                    options = {"model": "gpt-image-2.6-flare", "prompt": "生成循环动画", "output_format": "gif"}
                    arguments = (
                        {"data": options, "files": {
                            "image": ("reference", reference, reference_mime), "mask": ("mask", mask, mask_mime),
                        }} if multipart else {"json": {
                            **options, "images": [{"image_url": f"data:{reference_mime};base64," + base64.b64encode(reference).decode()}],
                            "mask": f"data:{mask_mime};base64," + base64.b64encode(mask).decode(),
                        }}
                    )
                    response = self.client.post("/v1/images/edits", headers=HEADERS, **arguments)
                    self.assertEqual(response.status_code, 400, response.text)
                    self.assertEqual(response.json()["error"]["param"], param)
                    self.assertEqual(self.requests, [])

    def test_responses_does_not_hide_an_unsupported_top_level_format(self):
        self.enable_fixture_upstream()
        with mock.patch.object(backend_module.OpenAIBackendAPI, "download_image_bytes", return_value=[animated_gif()]):
            response = self.client.post("/v1/responses", headers=HEADERS, json={
                "model": "gpt-5", "input": "生成循环动画", "stream": True, "output_format": "jpeg",
                "tools": [{"type": "image_generation", "model": "gpt-image-2.6-flare", "output_format": "gif"}],
            })
        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(response.json()["error"]["param"], "output_format")
        self.assertEqual(self.requests, [])

    def test_non_animated_or_corrupt_results_fail_without_regeneration(self):
        self.enable_fixture_upstream()
        single = BytesIO()
        Image.new("RGB", (16, 12), "red").save(single, format="GIF")
        for payload in (self.image, single.getvalue(), animated_gif()[:-20], b"<svg></svg>"):
            with self.subTest(header=payload[:6]):
                self.requests.clear()
                self.accounts.update_account("fixture-web-free", {"quota": 3, "status": "正常"})
                with mock.patch.object(backend_module.OpenAIBackendAPI, "download_image_bytes", return_value=[payload]):
                    response = self.client.post("/v1/images/generations", headers=HEADERS, json={
                        "model": "gpt-image-2.6-flare", "prompt": "生成循环动画", "output_format": "gif",
                    })
                self.assertEqual(response.status_code, 502, response.text)
                self.assertEqual(response.json()["error"]["code"], "animated_gif_not_generated")
                self.assertEqual(sum(item["url"].endswith("/f/conversation") for item in self.requests), 1)

    def test_invalid_frame_hints_are_rejected_before_upstream_calls(self):
        self.enable_fixture_upstream()
        for param, value in (("frame_count", 1), ("frame_count", 17), ("frame_count", True),
                             ("frame_count", 9.5), ("frame_count", "9.0"),
                             ("frame_duration_ms", 19), ("frame_duration_ms", 2001)):
            with self.subTest(param=param, value=value):
                response = self.client.post("/v1/images/generations", headers=HEADERS, json={
                    "model": "gpt-image-2.6-flare", "prompt": "生成循环动画", "output_format": "gif", param: value,
                })
                self.assertEqual(response.status_code, 400, response.text)
                self.assertEqual(response.json()["error"]["param"], param)
                self.assertEqual(response.json()["error"]["code"], "invalid_parameter")
                self.assertEqual(self.requests, [])

    def test_gif_gate_and_unsupported_models_are_checked_before_using_accounts(self):
        self.enable_fixture_upstream()
        with mock.patch.dict(config.data, {"image_web_gif_enabled": False}):
            response = self.client.post("/v1/images/generations", headers=HEADERS, json={
                "model": "gpt-image-2.6-flare", "prompt": "生成循环动画", "output_format": "gif",
            })
        self.assertEqual(response.status_code, 400, response.text)
        for model in ("gpt-image-2", "gpt-image-2.5", "codex-gpt-image-2"):
            response = self.client.post("/v1/images/generations", headers=HEADERS, json={
                "model": model, "prompt": "生成循环动画", "output_format": "gif",
            })
            self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(self.requests, [])

    def test_resumed_gif_task_does_not_accept_a_static_result_after_reload(self):
        task_path = self.enable_resume_poll_fixture()
        timeout = backend_module.ImagePollTimeoutError("ChatGPT 生图超时")
        timeout.conversation_id = "fixture-conversation"
        with mock.patch.object(backend_module.OpenAIBackendAPI, "download_image_bytes", side_effect=[timeout, [self.image]]):
            self.client.post("/api/image-tasks/generations", headers=HEADERS, json={
                "client_task_id": "gif-static-resume", "model": "gpt-image-2.6-sunburst", "prompt": "生成循环动画", "output_format": "gif",
            })
            self.assertEqual(self.wait_for_http_task("gif-static-resume")["status"], "error")
            with mock.patch.object(image_tasks_api, "image_task_service", ImageTaskService(task_path)):
                self.client.post("/api/image-tasks/gif-static-resume/resume-poll", headers=HEADERS, json={"extra_timeout_secs": 5})
                task = self.wait_for_http_task("gif-static-resume")
        self.assertEqual(task["status"], "error", task)
        self.assertEqual(task["data"], [])
        self.assertEqual(task.get("output_format"), "gif", task)
        self.assertIn("多帧动画 GIF", task["error"])
        self.assertEqual(sum(item["url"].endswith("/f/conversation") for item in self.requests), 1)

"""网页 Image 2.6 的 HTTP 契约回归；只使用隔离账号和外部请求替身。"""

import base64
import json
from io import BytesIO
from pathlib import Path
import tempfile
import time
from unittest import mock

from PIL import Image

from api import image_tasks as image_tasks_api
from services import openai_backend_api as backend_module
from services.image_task_service import ImageTaskService
from test.test_free_web_image import HEADERS, FixtureResponse, FixtureSession, WebImageFixture


class WebImage26Tests(WebImageFixture):
    def test_generation_sends_the_selected_web_variant_in_both_requests(self):
        self.enable_fixture_upstream()
        for requested, expected in (
            ("gpt-image-2.6-flare", "gpt-image-2.6-flare"),
            ("gpt-image-2.6-sunburst", "gpt-image-2.6-sunburst"),
            ("gpt-image-2.6", "gpt-image-2.6-sunburst"),
        ):
            with self.subTest(model=requested):
                self.requests.clear()
                response = self.client.post("/v1/images/generations", headers=HEADERS, json={
                    "model": requested, "prompt": "画一个蓝色圆形", "size": "1024x1024",
                })
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(base64.b64decode(response.json()["data"][0]["b64_json"]), self.image)
                self.assertEqual([item["json"]["model"] for item in self.requests], [expected, expected])
                self.assertTrue(all(item["json"]["system_hints"] == ["picture_v2"] for item in self.requests))
                self.assertTrue(all("/backend-api/f/conversation" in item["url"] for item in self.requests))

    def test_web_variant_uses_password_account_in_a_mixed_pool(self):
        self.accounts.delete_accounts(["fixture-web-free"])
        self.accounts.add_account_items([
            {"access_token": "fixture-codex-plus", "source_type": "codex", "type": "Plus", "status": "正常", "quota": 10},
            {"access_token": "fixture-password-free", "source_type": "password", "type": "free", "status": "正常", "quota": 3},
        ])
        self.enable_fixture_upstream()
        response = self.client.post("/v1/images/generations", headers=HEADERS, json={
            "model": "gpt-image-2.6-sunburst", "prompt": "fixture",
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(all(
            item["headers"]["Authorization"] == "Bearer fixture-password-free"
            for item in self.requests
        ))

    def test_no_web_quota_does_not_use_an_available_codex_account(self):
        self.accounts.update_account("fixture-web-free", {"quota": 0})
        self.accounts.add_account_items([
            {"access_token": "fixture-codex-plus", "source_type": "codex", "type": "Plus", "status": "正常", "quota": 10},
        ])
        self.enable_fixture_upstream()
        response = self.client.post("/v1/images/generations", headers=HEADERS, json={
            "model": "gpt-image-2.6", "prompt": "fixture",
        })
        self.assertEqual(response.status_code, 429, response.text)
        self.assertEqual(response.json()["error"]["code"], "insufficient_quota")
        self.assertEqual(self.requests, [])

    def test_password_oauth_and_default_web_sources_can_request_variants(self):
        self.enable_fixture_upstream()
        for source, account_type in (("web", "free"), ("password", "Plus"), ("oauth_login", "Team"), (None, "Pro")):
            with self.subTest(source=source):
                self.accounts.update_account("fixture-web-free", {
                    "source_type": source, "type": account_type, "quota": 1, "status": "正常",
                })
                self.requests.clear()
                response = self.client.post("/v1/images/generations", headers=HEADERS, json={
                    "model": "gpt-image-2.6-flare", "prompt": "fixture",
                })
                self.assertEqual(response.status_code, 200, response.text)
                self.assertTrue(all(
                    item["headers"]["Authorization"] == "Bearer fixture-web-free"
                    for item in self.requests
                ))

    def test_account_source_is_rechecked_after_refresh(self):
        self.enable_fixture_upstream()
        refreshed = {**self.accounts.get_account("fixture-web-free"), "source_type": "codex", "type": "Plus"}
        with mock.patch.object(self.accounts, "fetch_remote_info", return_value=refreshed):
            response = self.client.post("/v1/images/generations", headers=HEADERS, json={
                "model": "gpt-image-2.6-flare", "prompt": "fixture",
            })
        self.assertEqual(response.status_code, 429, response.text)
        self.assertEqual(self.requests, [])

    def test_missing_upstream_usage_is_unknown_in_json_and_streaming_results(self):
        self.enable_fixture_upstream()
        for streaming in (False, True):
            with self.subTest(stream=streaming):
                response = self.client.post("/v1/images/generations", headers=HEADERS, json={
                    "model": "gpt-image-2.6-sunburst", "prompt": "fixture", "stream": streaming,
                })
                self.assertEqual(response.status_code, 200, response.text)
                if streaming:
                    results = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: {")]
                    results = [item for item in results if item.get("data")]
                else:
                    results = [response.json()]
                self.assertTrue(results)
                for item in results:
                    self.assertNotIn("usage", item)
                    self.assertEqual(item["usage_source"], "unavailable")

    def test_model_catalog_owns_web_metadata_and_rejects_codex_only_pool(self):
        models = ("gpt-image-2.6", "gpt-image-2.6-sunburst", "gpt-image-2.6-flare")

        def anonymous_catalog():
            return {"object": "list", "data": [
                {"id": model, "object": "model", "metadata": {"route": "codex"}}
                for model in models
            ]}

        for has_web_account in (True, False):
            with self.subTest(has_web_account=has_web_account):
                if not has_web_account:
                    self.accounts.delete_accounts(["fixture-web-free"])
                    self.accounts.add_account_items([
                        {"access_token": "fixture-codex-plus", "source_type": "codex", "type": "Plus", "status": "正常", "quota": 10},
                    ])
                with mock.patch.object(backend_module.OpenAIBackendAPI, "list_models", side_effect=anonymous_catalog):
                    response = self.client.get("/v1/models", headers=HEADERS)
                self.assertEqual(response.status_code, 200, response.text)
                by_id = {item["id"]: item for item in response.json()["data"]}
                if has_web_account:
                    for model in models:
                        self.assertEqual(by_id[model]["metadata"]["route"], "web")
                    self.assertEqual(
                        by_id["gpt-image-2.6"]["metadata"]["upstream_requested_model"],
                        "gpt-image-2.6-sunburst",
                    )
                else:
                    self.assertTrue(all(model not in by_id for model in models))

    def test_native_controls_are_rejected_before_a_web_request(self):
        self.enable_fixture_upstream()
        for param, value in (("complexity", "high"), ("output_format", "gif"), ("frame_count", 9), ("quality", "max")):
            with self.subTest(param=param):
                self.accounts.update_account("fixture-web-free", {"quota": 1, "status": "正常"})
                self.requests.clear()
                response = self.client.post("/v1/images/generations", headers=HEADERS, json={
                    "model": "gpt-image-2.6-flare", "prompt": "fixture", param: value,
                })
                self.assertEqual(response.status_code, 400, response.text)
                self.assertEqual(response.json()["error"]["param"], param)
                self.assertEqual(self.requests, [])

    def test_edit_rejects_native_controls_before_decoding_or_uploading(self):
        self.enable_fixture_upstream()
        response = self.client.post("/v1/images/edits", headers=HEADERS, json={
            "model": "gpt-image-2.6-flare", "prompt": "fixture", "complexity": "high",
            "images": [{"image_url": "data:image/png;base64," + base64.b64encode(self.image).decode()}],
        })
        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(response.json()["error"]["param"], "complexity")
        self.assertEqual(self.requests, [])

    def test_streaming_chat_and_responses_validate_before_sending_headers(self):
        self.enable_fixture_upstream()
        for path, body in (
            ("/v1/chat/completions", {
                "model": "gpt-image-2.6-flare", "messages": [{"role": "user", "content": "fixture"}],
                "complexity": "high", "stream": True,
            }),
            ("/v1/responses", {
                "model": "gpt-5", "input": "fixture", "stream": True,
                "tools": [{"type": "image_generation", "model": "gpt-image-2.6-flare", "complexity": "high"}],
            }),
        ):
            with self.subTest(path=path):
                self.requests.clear()
                response = self.client.post(path, headers=HEADERS, json=body)
                self.assertEqual(response.status_code, 400, response.text)
                self.assertEqual(response.json()["error"]["param"], "complexity")
                self.assertEqual(self.requests, [])

    def test_task_native_options_are_rejected_before_creating_work(self):
        self.enable_fixture_upstream()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        service = ImageTaskService(Path(directory.name) / "tasks.json")
        patcher = mock.patch.object(image_tasks_api, "image_task_service", service)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client.app.include_router(image_tasks_api.create_router())
        response = self.client.post("/api/image-tasks/generations", headers=HEADERS, json={
            "client_task_id": "native-options", "model": "gpt-image-2.6-flare", "prompt": "fixture",
            "complexity": "high",
        })
        # 错误实现会创建任务；等待其结束以保持隔离测试的清理边界。
        if response.status_code == 200:
            for _ in range(80):
                items = self.client.get("/api/image-tasks", headers=HEADERS).json().get("items", [])
                if items and all(item.get("status") not in {"pending", "running"} for item in items):
                    break
                time.sleep(0.02)
        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(response.json()["detail"]["error"]["param"], "complexity")
        self.assertEqual(self.requests, [])

    def test_model_permission_error_is_preserved_and_legacy_web_still_works(self):
        self.enable_fixture_upstream()

        class PermissionSession(FixtureSession):
            def post(self, url, **kwargs):
                if url.endswith("/f/conversation/prepare") and kwargs["json"]["model"].startswith("gpt-image-2.6"):
                    self.requests.append({"url": url, **kwargs})
                    denied = FixtureResponse({"error": {
                        "message": "This account cannot use the selected image model",
                        "type": "permission_error", "code": "model_not_available", "param": "model",
                    }})
                    denied.status_code = 403
                    return denied
                return super().post(url, **kwargs)

        with mock.patch.object(backend_module.requests, "Session", side_effect=lambda **_kwargs: PermissionSession(self.requests)):
            denied = self.client.post("/v1/images/generations", headers=HEADERS, json={
                "model": "gpt-image-2.6-flare", "prompt": "fixture",
            })
            self.assertEqual(denied.status_code, 403, denied.text)
            self.assertEqual(denied.json()["error"]["code"], "model_not_available")
            self.assertEqual(denied.json()["error"]["param"], "model")
            old = self.client.post("/v1/images/generations", headers=HEADERS, json={
                "model": "gpt-image-2.5", "prompt": "fixture",
            })
        self.assertEqual(old.status_code, 200, old.text)

    def test_permission_rejection_can_try_another_web_account_without_switching_model(self):
        self.enable_fixture_upstream()
        self.accounts.add_account_items([
            {"access_token": "fixture-web-plus", "source_type": "password", "type": "Plus", "status": "正常", "quota": 3},
        ])

        class LimitedSession(FixtureSession):
            def post(self, url, **kwargs):
                if url.endswith("/f/conversation/prepare") and kwargs["headers"]["Authorization"] == "Bearer fixture-web-free":
                    self.requests.append({"url": url, **kwargs})
                    denied = FixtureResponse({"error": {
                        "message": "Image model unavailable for this account", "type": "permission_error",
                        "code": "model_not_available", "param": "model",
                    }})
                    denied.status_code = 403
                    return denied
                return super().post(url, **kwargs)

        with mock.patch.object(backend_module.requests, "Session", side_effect=lambda **_kwargs: LimitedSession(self.requests)):
            response = self.client.post("/v1/images/generations", headers=HEADERS, json={
                "model": "gpt-image-2.6-flare", "prompt": "fixture",
            })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(all(item["json"]["model"] == "gpt-image-2.6-flare" for item in self.requests))
        self.assertEqual(self.requests[-1]["headers"]["Authorization"], "Bearer fixture-web-plus")

    def test_animated_output_is_rejected_without_a_second_submission(self):
        self.enable_fixture_upstream()
        stream = BytesIO()
        Image.new("RGB", (8, 8), "red").save(
            stream, format="GIF", save_all=True, append_images=[Image.new("RGB", (8, 8), "blue")],
        )
        with mock.patch.object(backend_module.OpenAIBackendAPI, "download_image_bytes", return_value=[stream.getvalue()]):
            response = self.client.post("/v1/images/generations", headers=HEADERS, json={
                "model": "gpt-image-2.6-sunburst", "prompt": "fixture",
            })
        self.assertEqual(response.status_code, 502, response.text)
        self.assertEqual(response.json()["error"]["code"], "unsupported_image_format")
        self.assertEqual(sum(item["url"].endswith("/f/conversation") for item in self.requests), 1)

    def test_chat_embeds_jpeg_with_the_correct_data_url_type(self):
        self.enable_fixture_upstream()
        stream = BytesIO()
        Image.new("RGB", (8, 8), "red").save(stream, format="JPEG")
        with mock.patch.object(backend_module.OpenAIBackendAPI, "download_image_bytes", return_value=[stream.getvalue()]):
            response = self.client.post("/v1/chat/completions", headers=HEADERS, json={
                "model": "gpt-image-2.6-flare", "messages": [{"role": "user", "content": "fixture"}],
            })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("data:image/jpeg;base64,", response.json()["choices"][0]["message"]["content"])

    def test_edits_chat_and_responses_keep_web_model_and_unknown_usage(self):
        self.enable_fixture_upstream()
        self.accounts.update_account("fixture-web-free", {"quota": 20})
        reference = "data:image/png;base64," + base64.b64encode(self.image).decode()
        cases = (
            ("/v1/images/edits", {"model": "gpt-image-2.6-flare", "prompt": "fixture", "images": [{"image_url": reference}]}, "gpt-image-2.6-flare"),
            ("/v1/chat/completions", {"model": "gpt-image-2.6-sunburst", "messages": [{"role": "user", "content": "fixture"}]}, "gpt-image-2.6-sunburst"),
            ("/v1/responses", {"model": "gpt-5", "input": "fixture", "tools": [{"type": "image_generation", "model": "gpt-image-2.6"}]}, "gpt-image-2.6-sunburst"),
        )
        for path, body, expected in cases:
            with self.subTest(path=path):
                self.requests.clear()
                response = self.client.post(path, headers=HEADERS, json=body)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["usage_source"], "unavailable")
                self.assertNotIn("usage", response.json())
                stages = [item for item in self.requests if "/f/conversation" in item["url"]]
                self.assertEqual([item["json"]["model"] for item in stages], [expected, expected])
        self.requests.clear()
        edited = self.client.post("/v1/images/edits", headers=HEADERS, data={
            "model": "gpt-image-2.6", "prompt": "合并两张参考图",
        }, files=[("image", ("one.png", self.image, "image/png")), ("image", ("two.png", self.image, "image/png"))])
        self.assertEqual(edited.status_code, 200, edited.text)
        final = [item for item in self.requests if item["url"].endswith("/f/conversation")][0]["json"]
        self.assertEqual(final["model"], "gpt-image-2.6-sunburst")
        self.assertEqual(len(final["messages"][0]["metadata"]["attachments"]), 2)

    def test_generation_task_persists_web_model_and_unknown_usage(self):
        self.enable_fixture_upstream()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        service = ImageTaskService(Path(directory.name) / "tasks.json")
        patcher = mock.patch.object(image_tasks_api, "image_task_service", service)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client.app.include_router(image_tasks_api.create_router())
        created = self.client.post("/api/image-tasks/generations", headers=HEADERS, json={
            "client_task_id": "web26-success", "model": "gpt-image-2.6-flare", "prompt": "fixture",
        })
        self.assertEqual(created.status_code, 200, created.text)
        task = {}
        for _ in range(100):
            [task] = self.client.get("/api/image-tasks", headers=HEADERS, params={"ids": "web26-success"}).json()["items"]
            if task["status"] not in {"pending", "running", "queued"}:
                break
            time.sleep(0.02)
        self.assertEqual(task["status"], "success", task)
        self.assertEqual(task["model"], "gpt-image-2.6-flare")
        self.assertEqual(task["usage_source"], "unavailable")
        self.assertTrue(all(item["json"]["model"] == "gpt-image-2.6-flare" for item in self.requests))

    def test_model_permission_rotation_is_bounded_and_keeps_the_real_error(self):
        self.enable_fixture_upstream()
        self.accounts.add_account_items([
            {"access_token": f"fixture-web-{index}", "source_type": "web", "type": "free", "status": "正常", "quota": 3}
            for index in range(4)
        ])

        class UnavailableSession(FixtureSession):
            def post(self, url, **kwargs):
                self.requests.append({"url": url, **kwargs})
                denied = FixtureResponse({"error": {
                    "message": "Model access unavailable", "type": "permission_error",
                    "code": "model_not_available", "param": "model",
                }})
                denied.status_code = 403
                return denied

        with mock.patch.object(backend_module.requests, "Session", side_effect=lambda **_kwargs: UnavailableSession(self.requests)):
            response = self.client.post("/v1/images/generations", headers=HEADERS, json={
                "model": "gpt-image-2.6-flare", "prompt": "fixture",
            })
        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(response.json()["error"]["code"], "model_not_available")
        self.assertEqual(len(self.requests), 3)
        self.assertEqual(len({item["headers"]["Authorization"] for item in self.requests}), 3)
        self.assertTrue(all(item["json"]["model"] == "gpt-image-2.6-flare" for item in self.requests))

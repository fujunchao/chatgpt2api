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
from services import image_task_service as image_task_module, openai_backend_api as backend_module
from services.config import config
from services.image_task_service import ImageTaskService
from test.test_free_web_image import HEADERS, FixtureResponse, FixtureSession, WebImageFixture


class WebImage26Tests(WebImageFixture):
    def enable_resume_poll_fixture(self):
        self.enable_fixture_upstream()

        class ResumeSession(FixtureSession):
            def get(self, url, **kwargs):
                self.requests.append({"url": url, "method": "GET", **kwargs})
                if "/backend-api/tasks" in url:
                    return FixtureResponse({"tasks": []})
                if url.endswith("/backend-api/conversation/fixture-conversation"):
                    return FixtureResponse({"mapping": {"fixture-output": {"message": {
                        "author": {"role": "tool", "name": "image_gen"},
                        "content": {"content_type": "multimodal_text", "parts": [{
                            "content_type": "image_asset_pointer",
                            "asset_pointer": "file-service://file_00000000111111111111111111111111",
                        }]},
                    }}}})
                raise AssertionError(f"未配置的恢复请求：{url}")

        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        service = ImageTaskService(Path(directory.name) / "tasks.json")
        for patcher in (
            mock.patch.object(image_tasks_api, "image_task_service", service),
            mock.patch.object(image_task_module, "account_service", self.accounts),
            mock.patch.object(backend_module.requests, "Session", side_effect=lambda **_kwargs: ResumeSession(self.requests)),
            mock.patch.dict(config.data, {"image_poll_initial_wait_secs": 0, "image_check_before_hit_enabled": False}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client.app.include_router(image_tasks_api.create_router())
        return Path(directory.name) / "tasks.json"

    def wait_for_http_task(self, task_id):
        for _ in range(100):
            [task] = self.client.get("/api/image-tasks", headers=HEADERS, params={"ids": task_id}).json()["items"]
            if task["status"] not in {"pending", "queued", "running"}:
                return task
            time.sleep(0.02)
        self.fail(f"任务未在测试时限内完成：{task}")

    def test_resume_poll_uses_original_web_account_and_marks_unknown_usage(self):
        self.enable_resume_poll_fixture()
        timeout = backend_module.ImagePollTimeoutError("ChatGPT 生图超时")
        timeout.conversation_id = "fixture-conversation"
        with mock.patch.object(backend_module.OpenAIBackendAPI, "download_image_bytes", side_effect=[timeout, [self.image]]):
            created = self.client.post("/api/image-tasks/generations", headers=HEADERS, json={
                "client_task_id": "web26-resume", "model": "gpt-image-2.6-flare", "prompt": "fixture",
            })
            self.assertEqual(created.status_code, 200, created.text)
            failed = self.wait_for_http_task("web26-resume")
            self.assertEqual(failed["status"], "error", failed)
            self.assertEqual(failed["conversation_id"], "fixture-conversation")
            resumed = self.client.post("/api/image-tasks/web26-resume/resume-poll", headers=HEADERS, json={"extra_timeout_secs": 5})
            self.assertEqual(resumed.status_code, 200, resumed.text)
            task = self.wait_for_http_task("web26-resume")
        self.assertEqual(task["status"], "success", task)
        self.assertEqual(task["model"], "gpt-image-2.6-flare")
        self.assertEqual(task["usage_source"], "unavailable")
        self.assertNotIn("usage", task)
        self.assertEqual(base64.b64decode(task["data"][0]["b64_json"]), self.image)
        self.assertEqual(sum(item["url"].endswith("/f/conversation") for item in self.requests), 1)
        polls = [item for item in self.requests if item["url"].endswith("/backend-api/conversation/fixture-conversation")]
        self.assertTrue(polls)
        self.assertTrue(all(item["headers"]["Authorization"] == "Bearer fixture-web-free" for item in polls))

    def test_resume_poll_rejects_unsupported_formats_without_resubmitting(self):
        self.enable_resume_poll_fixture()
        stream = BytesIO()
        Image.new("RGB", (8, 8), "red").save(
            stream, format="GIF", save_all=True, append_images=[Image.new("RGB", (8, 8), "blue")],
        )
        for index, payload in enumerate((b'<svg xmlns="http://www.w3.org/2000/svg"></svg>', stream.getvalue())):
            with self.subTest(index=index):
                self.requests.clear()
                timeout = backend_module.ImagePollTimeoutError("ChatGPT 生图超时")
                timeout.conversation_id = "fixture-conversation"
                task_id = f"web26-resume-format-{index}"
                with mock.patch.object(backend_module.OpenAIBackendAPI, "download_image_bytes", side_effect=[timeout, [payload]]):
                    self.client.post("/api/image-tasks/generations", headers=HEADERS, json={
                        "client_task_id": task_id, "model": "gpt-image-2.6-sunburst", "prompt": "fixture",
                    })
                    self.assertEqual(self.wait_for_http_task(task_id)["status"], "error")
                    resumed = self.client.post(f"/api/image-tasks/{task_id}/resume-poll", headers=HEADERS, json={"extra_timeout_secs": 5})
                    self.assertEqual(resumed.status_code, 200, resumed.text)
                    task = self.wait_for_http_task(task_id)
                self.assertEqual(task["status"], "error", task)
                self.assertIn("静态 PNG/JPEG/WebP", task["error"])
                self.assertEqual(task["data"], [])
                self.assertEqual(sum(item["url"].endswith("/f/conversation") for item in self.requests), 1)

    def test_resume_poll_keeps_original_account_when_its_source_changes(self):
        self.enable_resume_poll_fixture()
        timeout = backend_module.ImagePollTimeoutError("ChatGPT 生图超时")
        timeout.conversation_id = "fixture-conversation"
        with mock.patch.object(backend_module.OpenAIBackendAPI, "download_image_bytes", side_effect=timeout):
            self.client.post("/api/image-tasks/generations", headers=HEADERS, json={
                "client_task_id": "web26-resume-source", "model": "gpt-image-2.6-flare", "prompt": "fixture",
            })
            self.assertEqual(self.wait_for_http_task("web26-resume-source")["status"], "error")
        self.accounts.update_account("fixture-web-free", {"source_type": "codex", "type": "Plus"})
        self.accounts.add_account_items([
            {"access_token": "fixture-another-web", "source_type": "web", "type": "free", "status": "正常", "quota": 3},
        ])
        self.requests.clear()
        self.client.post("/api/image-tasks/web26-resume-source/resume-poll", headers=HEADERS, json={"extra_timeout_secs": 5})
        task = self.wait_for_http_task("web26-resume-source")
        self.assertEqual(task["status"], "error", task)
        self.assertIn("原网页账号", task["error"])
        self.assertEqual(self.requests, [])

    def test_resume_poll_after_reload_preserves_the_original_conversation(self):
        task_path = self.enable_resume_poll_fixture()
        timeout = backend_module.ImagePollTimeoutError("ChatGPT 生图超时")
        timeout.conversation_id = "fixture-conversation"
        with mock.patch.object(backend_module.OpenAIBackendAPI, "download_image_bytes", side_effect=[timeout, [self.image]]):
            self.client.post("/api/image-tasks/generations", headers=HEADERS, json={
                "client_task_id": "web26-resume-reload", "model": "gpt-image-2.6-flare", "prompt": "fixture",
            })
            self.assertEqual(self.wait_for_http_task("web26-resume-reload")["status"], "error")
            with mock.patch.object(image_tasks_api, "image_task_service", ImageTaskService(task_path)):
                resumed = self.client.post("/api/image-tasks/web26-resume-reload/resume-poll", headers=HEADERS, json={"extra_timeout_secs": 5})
                self.assertEqual(resumed.status_code, 200, resumed.text)
                task = self.wait_for_http_task("web26-resume-reload")
        self.assertEqual(task["status"], "success", task)
        self.assertEqual(task["model"], "gpt-image-2.6-flare")
        self.assertEqual(task["conversation_id"], "fixture-conversation")
        self.assertEqual(task["usage_source"], "unavailable")
        self.assertEqual(sum(item["url"].endswith("/f/conversation") for item in self.requests), 1)

    def test_receive_failure_after_submission_does_not_send_the_image_again(self):
        self.enable_fixture_upstream()
        for failure in (
            "curl: (56) Recv failure: Connection reset by peer",
            "curl: (55) Failed sending data: Connection aborted",
            "curl: (52) Empty reply from server: Remote disconnected",
        ):
            with self.subTest(failure=failure):
                self.requests.clear()

                class ResetSession(FixtureSession):
                    def post(self, url, **kwargs):
                        if url.endswith("/f/conversation"):
                            self.requests.append({"url": url, **kwargs})
                            raise RuntimeError(failure)
                        return super().post(url, **kwargs)

                    def get(self, url, **kwargs):
                        self.requests.append({"url": url, "method": "GET", **kwargs})
                        if "/backend-api/conversations?" in url:
                            return FixtureResponse({"items": []})
                        raise AssertionError(f"未配置的恢复查询：{url}")

                with mock.patch.object(backend_module.requests, "Session", side_effect=lambda **_kwargs: ResetSession(self.requests)):
                    response = self.client.post("/v1/images/generations", headers=HEADERS, json={
                        "model": "gpt-image-2.6-flare", "prompt": "fixture",
                    })
                self.assertEqual(response.status_code, 502, response.text)
                self.assertEqual(response.json()["error"]["code"], "image_stream_interrupted")
                self.assertEqual(sum(item["url"].endswith("/f/conversation") for item in self.requests), 1)

    def test_tls_handshake_failure_before_submission_can_retry_safely(self):
        self.enable_fixture_upstream()
        failed = False

        class HandshakeSession(FixtureSession):
            def post(self, url, **kwargs):
                nonlocal failed
                if url.endswith("/f/conversation") and not failed:
                    failed = True
                    self.requests.append({"url": url, "failed_before_submission": True, **kwargs})
                    raise RuntimeError("curl: (35) TLS connect error: Connection reset by peer")
                return super().post(url, **kwargs)

        with mock.patch.object(backend_module.requests, "Session", side_effect=lambda **_kwargs: HandshakeSession(self.requests)):
            response = self.client.post("/v1/images/generations", headers=HEADERS, json={
                "model": "gpt-image-2.6-flare", "prompt": "fixture",
            })
        self.assertEqual(response.status_code, 200, response.text)
        submissions = [item for item in self.requests if item["url"].endswith("/f/conversation")]
        self.assertEqual(len(submissions), 2)
        self.assertTrue(submissions[0]["failed_before_submission"])
        self.assertEqual(len(response.json()["data"]), 1)

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

    def test_cva_default_png_is_compatible_with_web_image_edits(self):
        self.enable_fixture_upstream()
        response = self.client.post("/v1/images/edits", headers=HEADERS, data={
            "model": "gpt-image-2.6-flare", "prompt": "将参考图改为红色",
            "output_format": "png",
        }, files={"image": ("reference.png", self.image, "image/png")})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(base64.b64decode(response.json()["data"][0]["b64_json"]), self.image)
        stages = [item for item in self.requests if "/f/conversation" in item["url"]]
        self.assertEqual([item["json"]["model"] for item in stages], ["gpt-image-2.6-flare", "gpt-image-2.6-flare"])
        self.assertTrue(all("output_format" not in item["json"] for item in stages))

    def test_cva_default_png_is_compatible_with_web_image_generation(self):
        self.enable_fixture_upstream()
        for output_format in ("png", " PNG "):
            with self.subTest(output_format=output_format):
                self.requests.clear()
                self.accounts.update_account("fixture-web-free", {"quota": 3, "status": "正常"})
                response = self.client.post("/v1/images/generations", headers=HEADERS, json={
                    "model": "gpt-image-2.6-sunburst", "prompt": "画一个蓝色圆形", "output_format": output_format,
                })
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(base64.b64decode(response.json()["data"][0]["b64_json"]), self.image)
                self.assertEqual([item["json"]["model"] for item in self.requests], ["gpt-image-2.6-sunburst", "gpt-image-2.6-sunburst"])
                self.assertTrue(all("output_format" not in item["json"] for item in self.requests))

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

    def test_responses_rejects_top_level_native_controls_before_sending_headers(self):
        self.enable_fixture_upstream()
        for model, tool in (
            ("gpt-image-2.6-flare", {"type": "image_generation"}),
            ("gpt-5", {"type": "image_generation", "model": "gpt-image-2.6-sunburst"}),
        ):
            for stream in (False, True):
                with self.subTest(model=model, stream=stream):
                    self.requests.clear()
                    response = self.client.post("/v1/responses", headers=HEADERS, json={
                        "model": model, "input": "fixture", "tools": [tool],
                        "stream": stream, "output_format": "gif",
                    })
                    self.assertEqual(response.status_code, 400, response.text)
                    self.assertEqual(response.json()["error"]["param"], "output_format")
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

    def test_multi_image_permission_rotation_is_bounded_for_the_whole_request(self):
        self.enable_fixture_upstream()
        self.accounts.add_account_items([
            {"access_token": f"fixture-web-{index}", "source_type": "web", "type": "free", "status": "正常", "quota": 8}
            for index in range(4)
        ])

        class UnavailableSession(FixtureSession):
            def post(self, url, **kwargs):
                self.requests.append({"url": url, **kwargs})
                time.sleep(0.02)
                denied = FixtureResponse({"error": {
                    "message": "Model access unavailable", "type": "permission_error",
                    "code": "model_not_available", "param": "model",
                }})
                denied.status_code = 403
                return denied

        for parallel in (False, True):
            with (
                self.subTest(parallel=parallel),
                mock.patch.dict(config.data, {"image_parallel_generation": parallel}),
                mock.patch.object(backend_module.requests, "Session", side_effect=lambda **_kwargs: UnavailableSession(self.requests)),
            ):
                self.requests.clear()
                response = self.client.post("/v1/images/generations", headers=HEADERS, json={
                    "model": "gpt-image-2.6-flare", "prompt": "fixture", "n": 4,
                })
                self.assertEqual(response.status_code, 403, response.text)
                self.assertEqual(response.json()["error"]["code"], "model_not_available")
                self.assertEqual(len(self.requests), 3)
                self.assertEqual(len({item["headers"]["Authorization"] for item in self.requests}), 3)
                self.assertTrue(all(item["json"]["model"] == "gpt-image-2.6-flare" for item in self.requests))

    def test_successful_multi_image_generation_keeps_all_four_results(self):
        self.enable_fixture_upstream()
        self.accounts.update_account("fixture-web-free", {"quota": 20})
        with mock.patch.dict(config.data, {"image_parallel_generation": True}):
            response = self.client.post("/v1/images/generations", headers=HEADERS, json={
                "model": "gpt-image-2.6-sunburst", "prompt": "fixture", "n": 4,
            })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()["data"]), 4)
        self.assertEqual(response.json()["usage_source"], "unavailable")
        self.assertEqual(sum(item["url"].endswith("/f/conversation") for item in self.requests), 4)

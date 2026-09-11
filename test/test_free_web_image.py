"""Free 网页图片入口的离线回归；只使用虚构账号和隔离存储。"""

import base64
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from curl_cffi.const import CurlHttpVersion

from api import accounts as accounts_api, ai
from api.errors import install_exception_handlers
from services.account_service import AccountService
from services import openai_backend_api as backend_module
from services.config import config
from services.image_task_service import ImageTaskService
from services.openai_backend_api import ChatRequirements
from services.protocol import conversation, openai_v1_image_generations, openai_v1_models
from services.storage.json_storage import JSONStorageBackend
from test.test_image_task_service import wait_for_task


WEB_MODEL = "gpt-image-2.5"
HEADERS = {"Authorization": "Bearer chatgpt2api"}


class FixtureResponse:
    status_code = 200

    def __init__(self, body=None, events=()):
        self.body = body or {}
        self.events = events
        self.text = json.dumps(self.body)
        self.headers = {}

    def json(self):
        return self.body

    def iter_lines(self):
        for event in self.events:
            yield ("data: " + json.dumps(event)).encode()
        yield b"data: [DONE]"

    def close(self):
        pass


class FixtureSession:
    """只模拟外部 HTTP：实际 Web 请求构造、SSE 解析及账号调度继续运行。"""

    def __init__(self, requests):
        self.headers = {}
        self.requests = requests
        self.uploads = 0

    def post(self, url, **kwargs):
        self.requests.append({"url": url, **deepcopy(kwargs)})
        if url.endswith("/f/conversation/prepare"):
            return FixtureResponse({"conduit_token": "fixture-conduit"})
        if url.endswith("/f/conversation"):
            return FixtureResponse(events=[{
                "conversation_id": "fixture-conversation",
                "message": {
                    "author": {"role": "tool", "name": "image_gen"},
                    "status": "finished_successfully",
                    "content": {"content_type": "multimodal_text", "parts": [{
                        "content_type": "image_asset_pointer",
                        "asset_pointer": "file-service://file_00000000111111111111111111111111",
                    }]},
                },
            }])
        if url.endswith("/backend-api/files"):
            self.uploads += 1
            return FixtureResponse({"file_id": f"fixture-reference-{self.uploads}", "upload_url": "https://example.invalid/upload"})
        if url.endswith("/uploaded"):
            return FixtureResponse()
        raise AssertionError(f"未配置的外部请求：{url}")

    def put(self, url, **kwargs):
        if url != "https://example.invalid/upload":
            raise AssertionError(f"未配置的上传地址：{url}")
        return FixtureResponse()

    def close(self):
        pass


class FreeWebImageTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        storage = JSONStorageBackend(Path(directory.name) / "accounts.json")
        storage.save_accounts([{
            "access_token": "fixture-web-free", "source_type": "web", "type": "free",
            "status": "正常", "quota": 3,
        }])
        self.accounts = AccountService(storage)
        for module in (conversation, openai_v1_models, backend_module):
            patcher = mock.patch.object(module, "account_service", self.accounts)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(openai_v1_models.OpenAIBackendAPI, "list_models", side_effect=lambda: {"object": "list", "data": []})
        patcher.start()
        self.addCleanup(patcher.stop)
        app = FastAPI()
        install_exception_handlers(app)
        app.include_router(ai.create_router())
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def enable_fixture_upstream(self):
        self.requests = []
        stream = BytesIO()
        Image.new("RGB", (32, 32), "blue").save(stream, format="PNG")
        self.image = stream.getvalue()
        self.remote_checks = []

        def check_account(token, _event=""):
            self.remote_checks.append(token)
            return self.accounts.get_account(token)

        patchers = [
            mock.patch.object(self.accounts, "fetch_remote_info", side_effect=check_account),
            mock.patch.object(backend_module.requests, "Session", side_effect=lambda **_kwargs: FixtureSession(self.requests)),
            mock.patch.object(backend_module.OpenAIBackendAPI, "_bootstrap"),
            mock.patch.object(backend_module.OpenAIBackendAPI, "_get_chat_requirements", return_value=ChatRequirements("fixture-requirements")),
            mock.patch.object(backend_module.OpenAIBackendAPI, "resolve_conversation_image_urls", return_value=["https://example.invalid/result.png"]),
            mock.patch.object(backend_module.OpenAIBackendAPI, "download_image_bytes", return_value=[self.image]),
            mock.patch.dict(config.data, {"image_remove_conversation_after_result": False}),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    @staticmethod
    def semantic_payload(payload):
        """只消除与模型选择无关的随机消息标识和发送时间。"""
        payload = deepcopy(payload)
        payload.pop("parent_message_id", None)
        if "partial_query" in payload:
            payload["partial_query"].pop("id", None)
        for message in payload.get("messages", []):
            message.pop("id", None)
            message.pop("create_time", None)
        return payload

    def test_free_generation_reuses_the_working_legacy_web_request(self):
        self.enable_fixture_upstream()
        requests_by_model = []
        for model in ("gpt-image-2", WEB_MODEL):
            self.requests.clear()
            response = self.client.post("/v1/images/generations", headers=HEADERS, json={
                "model": model, "prompt": "画一个蓝色圆形", "quality": "high", "size": "1024x1024",
            })
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(base64.b64decode(response.json()["data"][0]["b64_json"]), self.image)
            self.assertEqual(len(self.requests), 2)
            requests_by_model.append([self.semantic_payload(item["json"]) for item in self.requests])
        self.assertEqual(requests_by_model[0], requests_by_model[1])
        self.assertEqual([payload["model"] for payload in requests_by_model[1]], ["gpt-5-3", "gpt-5-3"])
        self.assertEqual(self.remote_checks, ["fixture-web-free", "fixture-web-free"])
        self.assertEqual(self.requests[-1]["http_version"], CurlHttpVersion.V1_1)

    def test_browser_oauth_login_free_account_exposes_and_uses_web_alias(self):
        self.accounts.delete_accounts(["fixture-web-free"])

        def refresh_web_account(token, *_args, **_kwargs):
            return self.accounts.update_account(token, {"type": "free", "status": "正常", "quota": 3})

        app = FastAPI()
        install_exception_handlers(app)
        app.include_router(accounts_api.create_router())
        app.include_router(ai.create_router())
        with (
            mock.patch.object(accounts_api, "account_service", self.accounts),
            mock.patch.object(accounts_api.oauth_login_service, "finish", return_value={
                "access_token": "fixture-oauth-free", "refresh_token": "fixture-refresh", "id_token": "fixture-id",
            }),
            mock.patch.object(self.accounts, "fetch_remote_info", side_effect=refresh_web_account),
            TestClient(app) as client,
        ):
            login = client.post("/api/accounts/oauth/finish", headers=HEADERS, json={
                "session_id": "fixture-session", "callback": "fixture-code",
            })
            self.assertEqual(login.status_code, 200, login.text)
            [account] = login.json()["items"]
            self.assertEqual(account["type"], "free")
            self.assertEqual(account["source_type"], "oauth_login")
            self.assertEqual(account["status"], "正常")
            response = client.get("/v1/models", headers=HEADERS)
            self.assertEqual(response.status_code, 200, response.text)
            ids = {item["id"] for item in response.json()["data"]}
            self.assertIn(WEB_MODEL, ids)
            self.assertNotIn("gpt-image-2.5-flare", ids)

            self.enable_fixture_upstream()
            generated = client.post("/v1/images/generations", headers=HEADERS, json={"model": WEB_MODEL, "prompt": "fixture"})
            self.assertEqual(generated.status_code, 200, generated.text)
            self.assertEqual([item["json"]["model"] for item in self.requests], ["gpt-5-3", "gpt-5-3"])
            self.assertEqual(self.remote_checks, ["fixture-oauth-free"])

    def test_free_edit_reuses_legacy_request_and_keeps_all_references(self):
        self.enable_fixture_upstream()
        requests_by_model = []
        for model in ("gpt-image-2", WEB_MODEL):
            self.requests.clear()
            response = self.client.post("/v1/images/edits", headers=HEADERS, data={
                "model": model, "prompt": "合并两张参考图", "quality": "high", "size": "1024x1024",
            }, files=[("image", ("one.png", self.image, "image/png")), ("image", ("two.png", self.image, "image/png"))])
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(base64.b64decode(response.json()["data"][0]["b64_json"]), self.image)
            stages = [item for item in self.requests if "/f/conversation" in item["url"]]
            self.assertEqual(len(stages), 2)
            payload = stages[-1]["json"]
            self.assertEqual(payload["model"], "gpt-5-3")
            self.assertEqual(payload["system_hints"], ["picture_v2"])
            self.assertEqual(len(payload["messages"][0]["metadata"]["attachments"]), 2)
            self.assertEqual(payload["messages"][0]["content"]["parts"][0]["asset_pointer"], "file-service://fixture-reference-1")
            self.assertEqual(payload["messages"][0]["content"]["parts"][1]["asset_pointer"], "file-service://fixture-reference-2")
            requests_by_model.append([self.semantic_payload(item["json"]) for item in stages])
        self.assertEqual(requests_by_model[0], requests_by_model[1])

    def test_free_json_edit_uses_the_web_alias(self):
        self.enable_fixture_upstream()
        response = self.client.post("/v1/images/edits", headers=HEADERS, json={
            "model": WEB_MODEL, "prompt": "fixture",
            "images": [{"image_url": "data:image/png;base64," + base64.b64encode(self.image).decode()}],
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["usage_source"], "unavailable")
        self.assertEqual(len(self.requests[-1]["json"]["messages"][0]["metadata"]["attachments"]), 1)

    def test_web_alias_chooses_password_free_instead_of_codex_account(self):
        self.accounts.delete_accounts(["fixture-web-free"])
        self.accounts.add_account_items([
            {"access_token": "fixture-codex-plus", "source_type": "codex", "type": "Plus", "status": "正常", "quota": 10},
            {"access_token": "fixture-password-free", "source_type": "password", "type": "free", "status": "正常", "quota": 3},
        ])
        self.enable_fixture_upstream()
        response = self.client.post("/v1/images/generations", headers=HEADERS, json={"model": WEB_MODEL, "prompt": "fixture"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.remote_checks, ["fixture-password-free"])
        self.assertEqual(self.accounts.get_account("fixture-codex-plus")["quota"], 10)
        self.assertEqual(self.accounts.get_account("fixture-password-free")["quota"], 2)

    def test_web_auto_result_does_not_invent_known_engine_usage(self):
        self.enable_fixture_upstream()
        for streaming in (False, True):
            response = self.client.post("/v1/images/generations", headers=HEADERS, json={
                "model": WEB_MODEL, "prompt": "fixture", "stream": streaming,
            })
            self.assertEqual(response.status_code, 200, response.text)
            if streaming:
                events = [json.loads(line[5:]) for line in response.text.splitlines() if line.startswith("data:") and line[5:].strip() != "[DONE]"]
                [result] = [event for event in events if event.get("object") == "image.generation.result"]
            else:
                result = response.json()
            self.assertNotIn("usage", result)
            self.assertEqual(result["usage_source"], "unavailable")

    def test_account_catalog_and_selection_agree_on_web_sources(self):
        self.enable_fixture_upstream()
        for source, expected in (("web", True), ("password", True), ("oauth_login", True), (None, True), ("codex", False), ("unknown", False)):
            with self.subTest(source=source):
                self.accounts.update_account("fixture-web-free", {"source_type": source, "quota": 3, "status": "正常"})
                self.requests.clear()
                self.remote_checks.clear()
                models = self.client.get("/v1/models", headers=HEADERS).json()["data"]
                self.assertEqual(WEB_MODEL in {item["id"] for item in models}, expected)
                response = self.client.post("/v1/images/generations", headers=HEADERS, json={"model": WEB_MODEL, "prompt": "fixture"})
                self.assertEqual(response.status_code, 200 if expected else 429, response.text)
                self.assertEqual(len(self.remote_checks), 1 if expected else 0)
                self.assertEqual(len(self.requests), 2 if expected else 0)

    def test_no_web_quota_does_not_fall_back_to_paid_codex(self):
        self.enable_fixture_upstream()
        self.accounts.add_account_items([
            {"access_token": "fixture-codex-plus", "source_type": "codex", "type": "Plus", "status": "正常", "quota": 10},
        ])
        for updates in ({"status": "正常", "quota": 0}, {"status": "禁用", "quota": 3}, {"status": "限流", "quota": 3}):
            with self.subTest(updates=updates):
                self.accounts.update_account("fixture-web-free", updates)
                response = self.client.post("/v1/images/generations", headers=HEADERS, json={"model": WEB_MODEL, "prompt": "fixture"})
                self.assertEqual(response.status_code, 429, response.text)
                self.assertEqual(response.json()["error"]["code"], "insufficient_quota")
                self.assertIn("web image quota", response.json()["error"]["message"])
        self.assertEqual(self.requests, [])
        self.assertEqual(self.remote_checks, [])
        self.assertEqual(self.accounts.get_account("fixture-codex-plus")["quota"], 10)

    def test_refreshed_account_source_must_still_be_web(self):
        self.enable_fixture_upstream()
        changed_account = {**self.accounts.get_account("fixture-web-free"), "source_type": "codex", "type": "Plus"}
        with mock.patch.object(self.accounts, "fetch_remote_info", return_value=changed_account):
            response = self.client.post("/v1/images/generations", headers=HEADERS, json={"model": WEB_MODEL, "prompt": "fixture"})
        self.assertEqual(response.status_code, 429, response.text)
        self.assertEqual(self.requests, [])

    def test_free_account_cannot_use_codex_variants_through_web_fallback(self):
        self.enable_fixture_upstream()
        for model in ("gpt-image-2.5-flare", "gpt-image-2.5-sunburst", "codex-gpt-image-2.5"):
            with self.subTest(model=model):
                response = self.client.post("/v1/images/generations", headers=HEADERS, json={"model": model, "prompt": "fixture"})
                self.assertEqual(response.status_code, 429, response.text)
                self.assertIn("codex image quota", response.json()["error"]["message"])
        self.assertEqual(self.requests, [])
        self.assertEqual(self.remote_checks, [])

    def test_anonymous_catalog_cannot_claim_or_duplicate_local_web_capability(self):
        def anonymous_catalog():
            return {"object": "list", "data": [{"id": WEB_MODEL, "owned_by": "upstream", "description": "fixture"}] * 2}

        with mock.patch.object(openai_v1_models.OpenAIBackendAPI, "list_models", side_effect=anonymous_catalog):
            response = self.client.get("/v1/models", headers=HEADERS)
            aliases = [item for item in response.json()["data"] if item["id"] == WEB_MODEL]
            self.assertEqual(len(aliases), 1)
            self.assertEqual(aliases[0]["owned_by"], "chatgpt2api")
            self.assertFalse(aliases[0]["metadata"]["variant_selection"])
            self.accounts.update_account("fixture-web-free", {"source_type": "codex", "type": "Plus"})
            response = self.client.get("/v1/models", headers=HEADERS)
            self.assertNotIn(WEB_MODEL, {item["id"] for item in response.json()["data"]})

    def test_responses_tool_and_chat_use_free_web_route(self):
        self.enable_fixture_upstream()
        self.accounts.update_account("fixture-web-free", {"quota": 10})
        for streaming in (False, True):
            for path, body in (
                ("/v1/responses", {"model": "gpt-5", "input": "fixture", "tools": [{"type": "image_generation", "model": WEB_MODEL}]}),
                ("/v1/chat/completions", {"model": WEB_MODEL, "messages": [{"role": "user", "content": "fixture"}]}),
            ):
                with self.subTest(path=path, stream=streaming):
                    self.requests.clear()
                    response = self.client.post(path, headers=HEADERS, json={**body, "stream": streaming})
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual([item["json"]["model"] for item in self.requests], ["gpt-5-3", "gpt-5-3"])
                    if not streaming:
                        self.assertNotIn("usage", response.json())
                        self.assertEqual(response.json()["usage_source"], "unavailable")
        self.assertEqual(self.remote_checks, ["fixture-web-free"] * 4)

    def test_image_task_preserves_web_alias_and_unknown_usage(self):
        self.enable_fixture_upstream()
        owner = {"id": "fixture-owner", "role": "user"}
        with tempfile.TemporaryDirectory() as directory:
            service = ImageTaskService(Path(directory) / "tasks.json", generation_handler=openai_v1_image_generations.handle)
            service.submit_generation(owner, client_task_id="web-auto", prompt="fixture", model=WEB_MODEL, size=None)
            task = wait_for_task(service, owner, "web-auto", "success")
            self.assertEqual(task["model"], WEB_MODEL)
            self.assertEqual(task["usage_source"], "unavailable")
            self.assertEqual(self.remote_checks, ["fixture-web-free"])

    def test_free_account_catalog_explains_web_auto_alias(self):
        response = self.client.get("/v1/models", headers=HEADERS)
        self.assertEqual(response.status_code, 200, response.text)
        models = {item["id"]: item for item in response.json()["data"]}
        self.assertIn(WEB_MODEL, models)
        self.assertIn("gpt-image-2", models)
        self.assertNotIn("gpt-image-2.5-flare", models)
        self.assertNotIn("codex-gpt-image-2.5", models)
        self.assertEqual(models[WEB_MODEL]["metadata"]["route"], "web")
        self.assertEqual(models[WEB_MODEL]["metadata"]["model_selection"], "upstream_auto")
        self.assertFalse(models[WEB_MODEL]["metadata"]["variant_selection"])
        self.assertIn("官网自动选择", models[WEB_MODEL]["description"])


if __name__ == "__main__":
    unittest.main()

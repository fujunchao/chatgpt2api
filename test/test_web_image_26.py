"""网页 Image 2.6 的 HTTP 契约回归；只使用隔离账号和外部请求替身。"""

import base64
from unittest import mock

from test.test_free_web_image import HEADERS, WebImageFixture


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

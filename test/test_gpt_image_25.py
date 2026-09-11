"""2.5 的 Codex 请求、模型发现、用量和账号约束回归。"""

import base64
import io
import json
from http.client import IncompleteRead
import unittest
from unittest import mock
from urllib.error import HTTPError

from services.openai_backend_api import OpenAIBackendAPI
from services.config import config
from services.protocol import conversation as module
from services.protocol import openai_v1_models as models
from services.protocol.conversation import ConversationRequest, ImageGenerationError, ImageOutput
from utils.helper import UpstreamHTTPError
from utils.image_tokens import resolve_image_usage, sum_token_usages


USAGE = {"input_tokens": 12, "output_tokens": 34, "total_tokens": 46, "input_tokens_details": {"cached_tokens": 2}}
IMAGE_B64 = base64.b64encode(b"fixture-image").decode("ascii")


class GPTImage25Tests(unittest.TestCase):
    def test_actual_codex_request_contains_selected_tool_model(self):
        cases = {
            "codex-gpt-image-2": "gpt-image-2",
            "gpt-image-2.5-flare": "gpt-image-2.5-flare",
            "gpt-image-2.5-sunburst": "gpt-image-2.5-sunburst",
            "pro-codex-gpt-image-2.5-sunburst": "gpt-image-2.5-sunburst",
        }
        for public_model, expected in cases.items():
            with self.subTest(model=public_model):
                backend = OpenAIBackendAPI.__new__(OpenAIBackendAPI)
                backend.access_token = "fixture-token"
                backend.base_url = "https://example.invalid"
                backend._ensure_codex_source_account = mock.Mock()
                raw = io.BytesIO(json.dumps({"output": [{"type": "image_generation_call", "result": IMAGE_B64}], "usage": USAGE}).encode())
                raw.headers = {"content-type": "application/json"}
                raw.status = 200
                with mock.patch("services.openai_backend_api.urllib.request.urlopen", return_value=raw) as send:
                    events = list(backend.iter_codex_image_response_events(
                        "fixture", model=public_model, size="1024x1024", quality="high",
                    ))
                payload = json.loads(send.call_args.args[0].data)
                self.assertEqual(payload["model"], "gpt-5.5")
                self.assertEqual(payload["tools"][0]["model"], expected)
                self.assertEqual(payload["tools"][0]["quality"], "high")
                self.assertEqual(payload["tools"][0]["action"], "generate")
                self.assertEqual(events[0]["usage"], USAGE)

    def test_variant_and_reference_images_reach_codex_adapter(self):
        backend = mock.Mock()
        image = {"type": "image_generation_call", "id": "image-1", "result": IMAGE_B64}
        backend.iter_codex_image_response_events.return_value = iter([
            {"type": "response.output_item.done", "item": image},
            {"type": "response.completed", "response": {"output": [image], "usage": USAGE}},
        ])
        with mock.patch.object(module, "format_image_result", side_effect=lambda items, *_args: {"data": items}):
            [result] = list(module.stream_codex_image_outputs(backend, ConversationRequest(
                model="gpt-image-2.5-sunburst", images=["reference"], quality="max", size="2048x2048",
            )))
        kwargs = backend.iter_codex_image_response_events.call_args.kwargs
        self.assertEqual(kwargs["model"], "gpt-image-2.5-sunburst")
        self.assertEqual(kwargs["images"], ["reference"])
        self.assertEqual(kwargs["quality"], "max")
        self.assertEqual(len(result.data), 1)
        self.assertEqual(result.usage, USAGE)
        self.assertEqual(result.usage_source, "upstream")

    def test_http_error_body_failure_preserves_upstream_status(self):
        for failure in (TimeoutError("read timeout"), IncompleteRead(b"partial", 100)):
            backend = OpenAIBackendAPI.__new__(OpenAIBackendAPI)
            backend.access_token = "fixture"
            backend.base_url = "https://example.invalid"
            backend._ensure_codex_source_account = mock.Mock()
            fp = mock.Mock()
            fp.read.side_effect = failure
            error = HTTPError("https://example.invalid/codex", 403, "forbidden", {}, fp)
            with self.subTest(error=type(failure).__name__), mock.patch(
                "services.openai_backend_api.urllib.request.urlopen", side_effect=error,
            ):
                with self.assertRaises(UpstreamHTTPError) as caught:
                    list(backend.iter_codex_image_response_events("fixture", model="gpt-image-2.5-flare"))
            self.assertEqual(caught.exception.status_code, 403)
            fp.close.assert_called_once()

    def test_25_without_upstream_usage_is_explicitly_unknown(self):
        backend = mock.Mock()
        backend.iter_codex_image_response_events.return_value = iter([
            {"type": "image_generation_call", "result": IMAGE_B64},
        ])
        with mock.patch.object(module, "format_image_result", return_value={"data": [{"b64_json": IMAGE_B64}]}):
            [result] = list(module.stream_codex_image_outputs(backend, ConversationRequest(model="gpt-image-2.5-flare")))
        self.assertIsNone(result.usage)
        self.assertEqual(result.to_chunk()["usage_source"], "unavailable")
        self.assertNotIn("usage", result.to_chunk())

    def test_paid_codex_account_is_required_for_25(self):
        backend = mock.Mock()
        result = ImageOutput(kind="result", model="gpt-image-2.5-flare", index=1, total=1, data=[{"url": "/fixture"}])
        with (
            mock.patch.object(module, "OpenAIBackendAPI", return_value=backend),
            mock.patch.object(module.account_service, "get_available_access_token", return_value="fixture") as choose,
            mock.patch.object(module.account_service, "get_account", return_value={}),
            mock.patch.object(module.account_service, "mark_image_result") as mark,
            mock.patch.object(module, "stream_codex_image_outputs", return_value=iter([result])),
            mock.patch.object(module, "stream_image_outputs") as web,
        ):
            module._generate_single_image(ConversationRequest(model="gpt-image-2.5-flare"), 1, 1)
        self.assertEqual(choose.call_args.kwargs, {"plan_type": None, "source_type": "codex", "plan_types": ("plus", "team", "pro")})
        web.assert_not_called()
        mark.assert_called_once_with("fixture", True)
        backend.close.assert_called_once()

    def test_plan_prefix_remains_an_account_filter(self):
        with mock.patch.object(module.account_service, "get_available_access_token", side_effect=RuntimeError("no available pro image quota")) as choose:
            with self.assertRaises(ImageGenerationError) as caught:
                module._generate_single_image(ConversationRequest(model="pro-codex-gpt-image-2.5-sunburst"), 1, 1)
        self.assertEqual(choose.call_args.kwargs["plan_type"], "pro")
        self.assertEqual(choose.call_args.kwargs["source_type"], "codex")
        self.assertEqual(caught.exception.status_code, 429)

    def test_codex_connection_timeout_is_not_resubmitted(self):
        backend = OpenAIBackendAPI.__new__(OpenAIBackendAPI)
        backend.access_token = "fixture"
        backend.base_url = "https://example.invalid"
        backend._ensure_codex_source_account = mock.Mock()
        backend.close = mock.Mock()
        with (
            mock.patch.object(module, "OpenAIBackendAPI", return_value=backend),
            mock.patch.object(module.account_service, "get_available_access_token", return_value="fixture") as choose,
            mock.patch.object(module.account_service, "get_account", return_value={}),
            mock.patch.object(module.account_service, "mark_image_result"),
            mock.patch("services.openai_backend_api.urllib.request.urlopen", side_effect=TimeoutError("operation timed out")) as send,
        ):
            with self.assertRaises(ImageGenerationError) as caught:
                module._generate_single_image(ConversationRequest(model="gpt-image-2.5-flare"), 1, 1)
        self.assertEqual(caught.exception.code, "image_stream_interrupted")
        choose.assert_called_once()
        send.assert_called_once()
        backend.close.assert_called_once()

    def test_model_permission_error_does_not_delete_or_retry_account(self):
        backend = mock.Mock()
        error = UpstreamHTTPError("codex", 403, {"error": {"message": "model not allowed", "code": "model_not_allowed"}})
        with (
            mock.patch.object(module, "OpenAIBackendAPI", return_value=backend),
            mock.patch.object(module.account_service, "get_available_access_token", return_value="fixture") as choose,
            mock.patch.object(module.account_service, "get_account", return_value={}),
            mock.patch.object(module.account_service, "mark_image_result") as mark,
            mock.patch.object(module.account_service, "remove_invalid_token") as remove,
            mock.patch.object(module, "stream_codex_image_outputs", side_effect=error),
        ):
            with self.assertRaises(ImageGenerationError) as caught:
                module._generate_single_image(ConversationRequest(model="gpt-image-2.5-flare"), 1, 1)
        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(caught.exception.code, "model_not_allowed")
        choose.assert_called_once()
        mark.assert_called_once_with("fixture", False)
        remove.assert_not_called()
        backend.close.assert_called_once()

    def test_parallel_failures_preserve_structured_status(self):
        for status, code in ((403, "model_not_allowed"), (429, "insufficient_quota")):
            error = ImageGenerationError("fixture", status_code=status, code=code, param="model")
            with self.subTest(status=status), mock.patch.dict(config.data, {"image_parallel_generation": True}), mock.patch.object(
                module, "_generate_single_image", side_effect=error,
            ):
                with self.assertRaises(ImageGenerationError) as caught:
                    list(module.stream_image_outputs_with_pool(ConversationRequest(model="gpt-image-2.5-flare", n=2)))
            self.assertEqual(caught.exception.status_code, status)
            self.assertEqual(caught.exception.code, code)
            self.assertEqual(caught.exception.param, "model")

    def test_invalid_options_fail_before_selecting_account(self):
        with mock.patch.object(module.account_service, "get_available_access_token") as choose:
            with self.assertRaises(ImageGenerationError) as caught:
                ConversationRequest(model="gpt-image-2.5-flare", size="1024x1365")
        self.assertEqual(caught.exception.param, "size")
        choose.assert_not_called()

    def test_catalog_only_adds_25_for_eligible_codex_accounts(self):
        for account, expected in [
            ({"source_type": "web", "type": "Plus"}, False),
            ({"source_type": "codex", "type": "free"}, False),
            ({"source_type": "codex", "type": "Plus", "status": "禁用"}, False),
            ({"source_type": "codex", "type": "Team", "status": "正常"}, True),
        ]:
            with self.subTest(account=account), mock.patch.object(models.account_service, "list_accounts", return_value=[account]), mock.patch.object(
                models.OpenAIBackendAPI, "list_models", return_value={"object": "list", "data": []},
            ):
                ids = {item["id"] for item in models.list_models()["data"]}
            self.assertEqual("gpt-image-2.5-sunburst" in ids, expected)
            self.assertEqual("gpt-image-2.5-flare" in ids, expected)

    def test_image_catalog_survives_anon_catalog_failure(self):
        with mock.patch.object(models.account_service, "list_accounts", return_value=[{"source_type": "codex", "type": "Plus"}]), mock.patch.object(
            models.OpenAIBackendAPI, "list_models", side_effect=RuntimeError("catalog unavailable"),
        ):
            ids = {item["id"] for item in models.list_models()["data"]}
        self.assertIn("gpt-image-2.5-flare", ids)

    def test_multiple_results_sum_upstream_usage_once_per_call(self):
        outputs = [ImageOutput(kind="result", model="gpt-image-2.5-flare", index=i, total=2, data=[{"url": f"/{i}"}], usage=USAGE, usage_source="upstream") for i in (1, 2)]
        result = module.collect_image_outputs(outputs)
        self.assertEqual(result["usage"]["total_tokens"], 92)
        self.assertEqual(result["usage"]["input_tokens_details"]["cached_tokens"], 4)
        self.assertEqual(result["usage_source"], "upstream")
        self.assertEqual(USAGE["total_tokens"], 46)

    def test_partial_usage_is_not_reported_as_a_complete_total(self):
        outputs = [
            ImageOutput(kind="result", model="gpt-image-2.5-flare", index=1, total=2, data=[{"url": "/1"}], usage=USAGE, usage_source="upstream"),
            ImageOutput(kind="result", model="gpt-image-2.5-flare", index=2, total=2, data=[{"url": "/2"}], usage_source="unavailable"),
        ]
        result = module.collect_image_outputs(outputs)
        self.assertNotIn("usage", result)
        self.assertEqual(result["usage_source"], "unavailable")

    def test_usage_fallback_only_applies_to_legacy_models(self):
        usage, source = resolve_image_usage(model="gpt-image-2.5-flare", upstream_usage=None, input_text_tokens=10, items=[{"url": "/fixture"}], quality="max")
        self.assertIsNone(usage)
        self.assertEqual(source, "unavailable")
        legacy, source = resolve_image_usage(model="gpt-image-2", upstream_usage=None, input_text_tokens=10, items=[{"url": "/fixture"}])
        self.assertGreater(legacy["output_tokens"], 0)
        self.assertEqual(source, "estimated")
        self.assertEqual(sum_token_usages([{"input_tokens": 2, "output_tokens": 3}])["total_tokens"], 5)


if __name__ == "__main__":
    unittest.main()

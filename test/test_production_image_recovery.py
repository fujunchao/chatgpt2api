"""生产补丁回归：限定提交阶段恢复，保留会话归属和资源生命周期。"""

import unittest
from types import SimpleNamespace
from unittest import mock

from curl_cffi.const import CurlHttpVersion

from services.config import config
from services.openai_backend_api import ImagePollTimeoutError, ImageStreamInterruptedError, OpenAIBackendAPI
from services.protocol import conversation as module
from services.protocol.conversation import ConversationRequest, ImageGenerationError, ImageOutput


class ProductionImageRecoveryTests(unittest.TestCase):
    def make_backend(self):
        backend = OpenAIBackendAPI.__new__(OpenAIBackendAPI)
        backend.base_url = "https://example.invalid"
        backend.access_token = "fixture-token"
        backend.session = mock.Mock()
        backend.session.post.return_value.status_code = 200
        backend._image_headers = mock.Mock(return_value={})
        backend._report_progress = mock.Mock()
        return backend

    def test_only_image_sse_uses_production_transport_options(self):
        backend = self.make_backend()
        backend._start_image_generation("fixture", None, "fixture", "gpt-image-2", message_id="request-id")
        kwargs = backend.session.post.call_args.kwargs
        self.assertEqual(kwargs["http_version"], CurlHttpVersion.V1_1)
        self.assertEqual(kwargs["timeout"], (30, 90))
        self.assertTrue(kwargs["stream"])
        self.assertEqual(kwargs["json"]["messages"][0]["id"], "request-id")

    def test_bootstrap_error_is_not_treated_as_a_submitted_image(self):
        backend = self.make_backend()
        error = RuntimeError("curl: (92) preflight failure")
        backend._bootstrap = mock.Mock(side_effect=error)
        with self.assertRaises(RuntimeError) as caught:
            list(backend._stream_picture_conversation("fixture", "gpt-image-2", []))
        self.assertIs(caught.exception, error)

    def test_submission_timeout_carries_exact_message_id(self):
        for code in (28, 92):
            with self.subTest(code=code):
                backend = self.make_backend()
                backend._bootstrap = mock.Mock()
                backend._get_chat_requirements = mock.Mock(return_value=None)
                backend._prepare_image_conversation = mock.Mock(return_value="conduit")
                backend._start_image_generation = mock.Mock(side_effect=RuntimeError(f"curl: ({code}) interrupted"))
                with self.assertRaises(ImageStreamInterruptedError) as caught:
                    list(backend._stream_picture_conversation("fixture", "gpt-image-2", []))
                self.assertEqual(caught.exception.message_id, backend._start_image_generation.call_args.kwargs["message_id"])
                self.assertGreater(caught.exception.started_at, 0)

    def test_body_interruption_closes_the_response(self):
        backend = self.make_backend()
        backend._bootstrap = mock.Mock()
        backend._get_chat_requirements = mock.Mock(return_value=None)
        backend._prepare_image_conversation = mock.Mock(return_value="conduit")
        response = mock.Mock()
        backend._start_image_generation = mock.Mock(return_value=response)
        with mock.patch("services.openai_backend_api.iter_sse_payloads", side_effect=RuntimeError("curl: (92) stream")):
            with self.assertRaises(ImageStreamInterruptedError):
                list(backend._stream_picture_conversation("fixture", "gpt-image-2", []))
        response.close.assert_called_once()

    def successful_outputs(self, events, backend):
        backend.resolve_conversation_image_urls.return_value = ["https://example.invalid/result"]
        backend.download_image_bytes.return_value = [b"fixture"]
        with (
            mock.patch.object(module, "conversation_events", return_value=events),
            mock.patch.object(module, "format_image_result", return_value={"data": [{"url": "/images/fixture.png"}]}),
            mock.patch.object(module, "_remove_image_conversation_later"),
            mock.patch.object(module, "_get_detailed_error_from_tasks", return_value=""),
        ):
            return list(module.stream_image_outputs(backend, ConversationRequest(model="gpt-image-2", prompt="fixture")))

    def test_known_conversation_and_file_ids_are_preserved(self):
        def events():
            yield {"type": "conversation.event", "conversation_id": "exact-conversation", "file_ids": ["file-result"], "text": ""}
            raise ImageStreamInterruptedError("curl: (92)", "request-id", 100)

        backend = mock.Mock()
        outputs = self.successful_outputs(events(), backend)
        self.assertEqual(outputs[-1].kind, "result")
        backend.find_conversation_by_message_id.assert_not_called()
        args = backend.resolve_conversation_image_urls.call_args.args
        self.assertEqual(args[:2], ("exact-conversation", ["file-result"]))

    def test_missing_conversation_uses_message_id_not_prompt(self):
        def events():
            raise ImageStreamInterruptedError("curl: (28)", "request-id", 100)
            yield

        backend = mock.Mock()
        backend.find_conversation_by_message_id.return_value = "matched"
        outputs = self.successful_outputs(events(), backend)
        self.assertEqual(outputs[-1].conversation_id, "matched")
        backend.find_conversation_by_message_id.assert_called_once_with("request-id", 100)
        backend.find_conversation_by_prompt.assert_not_called()

    def test_unknown_submission_does_not_silently_select_latest(self):
        backend = mock.Mock()
        backend.find_conversation_by_message_id.return_value = ""
        with mock.patch.object(module, "conversation_events", side_effect=ImageStreamInterruptedError("curl: (28)", "id", 100)):
            with self.assertRaises(ImageGenerationError) as caught:
                list(module.stream_image_outputs(backend, ConversationRequest(model="gpt-image-2")))
        self.assertEqual(caught.exception.code, "image_stream_interrupted")
        backend.resolve_conversation_image_urls.assert_not_called()
        backend.find_conversation_by_prompt.assert_not_called()

    def test_recovered_submission_is_not_retried_after_poll_or_download_failure(self):
        for failure_stage in ("poll", "download"):
            with self.subTest(stage=failure_stage):
                backend = mock.Mock()
                backend.find_conversation_by_message_id.return_value = "accepted-conversation"
                backend.resolve_conversation_image_urls.return_value = ["https://example.invalid/image"]
                if failure_stage == "poll":
                    backend.resolve_conversation_image_urls.side_effect = ImagePollTimeoutError("图片轮询超时")
                else:
                    backend.download_image_bytes.side_effect = RuntimeError("curl: (35) interrupted download")
                with (
                    mock.patch.object(module, "OpenAIBackendAPI", return_value=backend),
                    mock.patch.object(module.account_service, "get_available_access_token", return_value="fixture") as choose,
                    mock.patch.object(module.account_service, "get_account", return_value={}),
                    mock.patch.object(module.account_service, "mark_image_result"),
                    mock.patch.object(module, "conversation_events", side_effect=ImageStreamInterruptedError("curl: (28)", "request-id", 100)) as submit,
                    mock.patch.object(module, "_get_detailed_error_from_tasks", return_value=""),
                ):
                    with self.assertRaises((ImagePollTimeoutError, ImageGenerationError)):
                        module._generate_single_image(ConversationRequest(model="gpt-image-2"), 1, 1)
                choose.assert_called_once()
                submit.assert_called_once()
                backend.close.assert_called_once()

    def test_blocked_state_is_not_cleared_by_recovery(self):
        def events():
            yield {"type": "conversation.event", "conversation_id": "blocked", "blocked": True, "text": "rejected"}
            raise ImageStreamInterruptedError("curl: (92)", "id", 100)

        backend = mock.Mock()
        with mock.patch.object(module, "conversation_events", return_value=events()):
            with self.assertRaises(ImageGenerationError) as caught:
                list(module.stream_image_outputs(backend, ConversationRequest(model="gpt-image-2")))
        self.assertEqual(caught.exception.code, "content_policy_violation")
        backend.find_conversation_by_message_id.assert_not_called()

    def test_tool_invocation_keeps_polling_after_intermediate_text(self):
        backend = mock.Mock()
        events = iter([{
            "type": "conversation.done", "conversation_id": "active", "text": "Generating image",
            "tool_invoked": True, "turn_use_case": "multimodal", "file_ids": [],
        }])
        outputs = self.successful_outputs(events, backend)
        self.assertEqual(outputs[-1].kind, "result")
        backend.resolve_conversation_image_urls.assert_called_once()

    def test_strict_lookup_rejects_unrelated_image_title_and_latest_item(self):
        backend = self.make_backend()
        backend._list_recent_conversations = mock.Mock(return_value=[{"id": "other", "title": "Image", "update_time": 100}])
        backend._get_conversation = mock.Mock(return_value={"mapping": {"node": {"message": {"id": "different", "author": {"role": "user"}}}}})
        self.assertEqual(backend.find_conversation_by_message_id("request-id", 100), "")

    def test_strict_lookup_requires_exact_user_message(self):
        backend = self.make_backend()
        backend._list_recent_conversations = mock.Mock(return_value=[
            {"id": "old", "update_time": 10}, {"id": "other", "update_time": 100}, {"id": "right", "update_time": 101},
        ])
        backend._get_conversation = mock.Mock(side_effect=[
            {"mapping": {"n": {"message": {"id": "request-id", "author": {"role": "assistant"}}}}},
            {"mapping": {"n": {"message": {"id": "request-id", "author": {"role": "user"}}}}},
        ])
        self.assertEqual(backend.find_conversation_by_message_id("request-id", 100), "right")
        self.assertEqual([call.args[0] for call in backend._get_conversation.call_args_list], ["other", "right"])

    def test_text_backend_is_closed_on_failure(self):
        backend = mock.Mock()
        with mock.patch.object(module, "OpenAIBackendAPI", return_value=backend), mock.patch.object(
            module, "conversation_events", side_effect=RuntimeError("upstream failed"),
        ):
            with self.assertRaises(RuntimeError):
                list(module.stream_text_deltas(SimpleNamespace(access_token="fixture"), ConversationRequest()))
        backend.close.assert_called_once()

    def test_image_failure_closes_backend_and_accounts_once(self):
        backend = mock.Mock()
        with (
            mock.patch.object(module, "OpenAIBackendAPI", return_value=backend),
            mock.patch.object(module.account_service, "get_available_access_token", return_value="fixture"),
            mock.patch.object(module.account_service, "get_account", return_value={}),
            mock.patch.object(module.account_service, "mark_image_result") as mark,
            mock.patch.object(module, "stream_image_outputs", return_value=iter([
                ImageOutput(kind="progress", model="gpt-image-2", index=1, total=1),
            ])),
        ):
            with self.assertRaises(ImageGenerationError):
                module._generate_single_image(ConversationRequest(model="gpt-image-2"), 1, 1)
        backend.close.assert_called_once()
        mark.assert_called_once_with("fixture", False)

    def test_cleanup_uses_its_own_connection_and_respects_setting(self):
        original = SimpleNamespace(access_token="fixture")
        cleanup = mock.MagicMock()
        cleanup.__enter__.return_value = cleanup

        def start_thread(**kwargs):
            return SimpleNamespace(start=kwargs["target"])

        with (
            mock.patch.dict(config.data, {"image_remove_conversation_after_result": True}),
            mock.patch.object(module, "OpenAIBackendAPI", return_value=cleanup) as constructor,
            mock.patch.object(module.threading, "Thread", side_effect=start_thread),
        ):
            module._remove_image_conversation_later(original, "conversation-id")
        constructor.assert_called_once_with(access_token="fixture")
        cleanup.delete_conversation.assert_called_once_with("conversation-id")
        cleanup.__exit__.assert_called_once()
        with mock.patch.dict(config.data, {"image_remove_conversation_after_result": False}), mock.patch.object(module.threading, "Thread") as thread:
            module._remove_image_conversation_later(original, "conversation-id")
        thread.assert_not_called()


if __name__ == "__main__":
    unittest.main()

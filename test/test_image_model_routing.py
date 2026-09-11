"""模型名称与 2.5 参数校验回归；不加载应用或访问上游。"""

import unittest

from utils.image_models import (
    ImageModelParameterError,
    codex_tool_model,
    image_model_qualities,
    is_codex_image_model,
    is_gpt_image_25_model,
    is_supported_image_model,
    split_image_model,
    validate_image_options,
)


class ImageModelRoutingTests(unittest.TestCase):
    def test_original_models_keep_their_routes(self):
        self.assertTrue(is_supported_image_model("gpt-image-2"))
        self.assertFalse(is_codex_image_model("gpt-image-2"))
        self.assertEqual(codex_tool_model("codex-gpt-image-2"), "gpt-image-2")
        self.assertEqual(split_image_model("Plus-codex-gpt-image-2"), ("plus", "codex-gpt-image-2"))

    def test_both_variants_reach_their_own_tool_model(self):
        for variant in ("flare", "sunburst"):
            tool_model = f"gpt-image-2.5-{variant}"
            for model in (tool_model, f"codex-{tool_model}", f"team-codex-{tool_model}"):
                with self.subTest(model=model):
                    self.assertTrue(is_codex_image_model(model))
                    self.assertTrue(is_gpt_image_25_model(model))
                    self.assertEqual(codex_tool_model(model), tool_model)

    def test_short_codex_alias_explicitly_selects_flare(self):
        self.assertEqual(codex_tool_model("codex-gpt-image-2.5"), "gpt-image-2.5-flare")

    def test_unknown_models_do_not_silently_fall_back(self):
        for model in ("plus-gpt-image-2.5", "gpt-image-3.0", "plus-gpt-image-2", "gpt-image-2-5"):
            self.assertFalse(is_supported_image_model(model))
            with self.assertRaises(ImageModelParameterError):
                codex_tool_model(model)

    def test_bare_25_is_a_web_alias_not_a_codex_variant(self):
        self.assertEqual(split_image_model(" GPT-IMAGE-2.5 "), (None, "gpt-image-2.5"))
        self.assertTrue(is_supported_image_model("gpt-image-2.5"))
        self.assertFalse(is_codex_image_model("gpt-image-2.5"))
        self.assertFalse(is_gpt_image_25_model("gpt-image-2.5"))
        self.assertNotIn("max", image_model_qualities("gpt-image-2.5"))
        with self.assertRaises(ImageModelParameterError):
            codex_tool_model("gpt-image-2.5")

    def test_only_25_exposes_extra_quality_levels(self):
        self.assertIn("xhigh", image_model_qualities("gpt-image-2.5-flare"))
        self.assertIn("max", image_model_qualities("pro-codex-gpt-image-2.5-sunburst"))
        self.assertNotIn("max", image_model_qualities("codex-gpt-image-2"))

    def test_valid_25_options(self):
        for size in (None, "auto", "1024x1024", "1008x1344", "2048x2048", "3840x2160"):
            with self.subTest(size=size):
                actual_size, quality = validate_image_options("gpt-image-2.5-flare", size, " XHIGH ")
                self.assertEqual(actual_size, size)
                self.assertEqual(quality, "xhigh")

    def test_invalid_size_or_quality_has_parameter_name(self):
        for size in ("1024x1365", "4096x4096", "256x256", "512x2048", "10000x1024", "wrong"):
            with self.subTest(size=size), self.assertRaises(ImageModelParameterError) as caught:
                validate_image_options("codex-gpt-image-2.5-sunburst", size, "auto")
            self.assertEqual(caught.exception.param, "size")
        with self.assertRaises(ImageModelParameterError) as caught:
            validate_image_options("gpt-image-2.5-flare", None, "hd")
        self.assertEqual(caught.exception.param, "quality")

    def test_legacy_options_are_not_rejected(self):
        self.assertEqual(validate_image_options("gpt-image-2", "1024x1365", "hd"), ("1024x1365", "hd"))


if __name__ == "__main__":
    unittest.main()

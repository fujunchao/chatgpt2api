"""只使用合成图片和临时存储，验证当前 GIF 阻断与已有动画保护。"""

from pathlib import Path
import tempfile
import json
import sys
from io import BytesIO
from unittest import mock

from PIL import Image

sys.path.insert(0, str(Path.cwd()))

from utils.image_format import inspect_image, image_mime_type
from utils.image_models import validate_web_image_26_request_options, ImageModelParameterError
from services.image_storage_service import ImageStorageService, ImageStorageError, _is_image_rel
from services.protocol.conversation import encode_generated_image, ImageGenerationError
from services import image_service


out = Path(tempfile.gettempdir()) / "gif26-local-2026-11-12"
out.mkdir(parents=True, exist_ok=True)
stream = BytesIO()
Image.new("RGB", (16, 16), "red").save(
    stream,
    format="GIF",
    save_all=True,
    append_images=[Image.new("RGB", (16, 16), "blue")],
    duration=[200, 300],
    loop=0,
)
payload = stream.getvalue()
(out / "synthetic-two-frame.gif").write_bytes(payload)
info = inspect_image(payload, verify=True)
results = {
    "probe_scope": "synthetic local payloads only; no provider requests",
    "gif": {
        "format": info.format,
        "extension": info.extension,
        "mime": info.mime_type,
        "animated": info.animated,
        "supported_static": info.supported_static,
    },
}
with Image.open(BytesIO(payload)) as gif:
    results["gif"]["frame_count"] = gif.n_frames
    results["gif"]["durations"] = [
        gif.seek(index) or gif.info.get("duration") for index in range(gif.n_frames)
    ]
assert info.format == "GIF" and info.animated and results["gif"]["frame_count"] == 2
assert image_mime_type(payload) == "image/gif"
try:
    validate_web_image_26_request_options("gpt-image-2.6-flare", {"output_format": "gif"})
except ImageModelParameterError as exc:
    results["request_gate"] = {"rejected": True, "param": exc.param}
else:
    raise AssertionError("GIF request unexpectedly accepted")
try:
    encode_generated_image(payload, "gpt-image-2.6-sunburst")
except ImageGenerationError as exc:
    results["result_gate"] = {
        "rejected": True, "code": exc.code, "status_code": exc.status_code,
    }
else:
    raise AssertionError("GIF result unexpectedly accepted")
with tempfile.TemporaryDirectory(prefix="gif26-probe-storage-") as directory:
    root = Path(directory)
    fake_config = mock.Mock()
    fake_config.images_dir = root / "images"
    fake_config.image_thumbnails_dir = root / "thumbnails"
    fake_config.base_url = "http://example.invalid"
    fake_config.cleanup_old_images.return_value = 0
    fake_config.get_image_storage_settings.return_value = {"mode": "local"}
    with mock.patch("services.image_storage_service.config", fake_config):
        service = ImageStorageService(root / "image-index.json")
        results["gif_generated_path_suffix"] = Path(service.make_relative_path(payload)).suffix
        assert results["gif_generated_path_suffix"] == ".png"
        results["gif_extension_whitelisted"] = _is_image_rel("2026/11/12/example.gif")
        assert not results["gif_extension_whitelisted"]
        try:
            service.save(payload, "http://example.invalid")
        except ImageStorageError:
            results["storage_gate"] = {
                "rejected": True,
                "writes_before_reject": fake_config.cleanup_old_images.call_count,
            }
        else:
            raise AssertionError("GIF storage unexpectedly accepted")
        assert results["storage_gate"]["writes_before_reject"] == 0
        png_stream = BytesIO()
        Image.new("RGB", (16, 16), "green").save(png_stream, format="PNG")
        png = png_stream.getvalue()
        stored = service.save(png, "http://example.invalid")
        results["png_baseline"] = {
            "extension": Path(stored.rel).suffix,
            "original_bytes_kept": (fake_config.images_dir / stored.rel).read_bytes() == png,
        }
        assert results["png_baseline"]["original_bytes_kept"]
        misnamed_gif = fake_config.images_dir / "animation-as-png.png"
        misnamed_gif.parent.mkdir(parents=True, exist_ok=True)
        misnamed_gif.write_bytes(payload)
        with (
            mock.patch.object(image_service, "config", fake_config),
            mock.patch.object(image_service, "image_storage_service", service),
        ):
            before = misnamed_gif.read_bytes()
            image_service.compress_images(60)
            results["animation_compression"] = {
                "original_bytes_kept": before == misnamed_gif.read_bytes(),
            }
            assert results["animation_compression"]["original_bytes_kept"]
            poster = image_service.ensure_thumbnail("animation-as-png.png")
            with Image.open(poster) as image:
                results["poster_thumbnail"] = {
                    "format": image.format,
                    "frame_count": getattr(image, "n_frames", 1),
                    "original_gif_kept": payload == misnamed_gif.read_bytes(),
                }
            assert results["poster_thumbnail"]["format"] == "PNG"
            assert results["poster_thumbnail"]["original_gif_kept"]
            local_preview = image_service.get_image_response("animation-as-png.png")
            results["misnamed_local_preview_mime"] = local_preview.headers["content-type"]
            assert results["misnamed_local_preview_mime"] == "image/png"
(out / "local-probe-results.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8",
)
print(json.dumps(results, ensure_ascii=True, indent=2))
print("RESULT_FILE=" + str(out / "local-probe-results.json"))

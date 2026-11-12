from __future__ import annotations

import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from PIL import Image

from services.image_storage_service import ImageStorageService
from services import image_service


def png_bytes() -> bytes:
    path = Path(tempfile.gettempdir()) / "chatgpt2api-test-image.png"
    Image.new("RGB", (2, 2), color=(255, 0, 0)).save(path, format="PNG")
    return path.read_bytes()


class FakeWebDAVClient:
    uploaded: dict[str, bytes] = {}
    deleted: list[str] = []
    content_types: dict[str, str] = {}

    def __init__(self, _settings):
        pass

    def put(self, rel: str, payload: bytes, content_type: str = "image/png") -> str:
        self.uploaded[rel] = payload
        self.content_types[rel] = content_type
        return f"https://dav.example.test/{rel}"

    def get(self, rel: str) -> bytes:
        return self.uploaded[rel]

    def delete(self, rel: str) -> bool:
        self.deleted.append(rel)
        self.uploaded.pop(rel, None)
        return True

    def test(self) -> dict[str, object]:
        self.put(".chatgpt2api_webdav_test.txt", b"chatgpt2api webdav test\n")
        self.delete(".chatgpt2api_webdav_test.txt")
        return {"ok": True, "status": 200, "error": None}


class ImageStorageServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data_dir = Path(self.tmp.name)
        self.images_dir = self.data_dir / "images"
        self.settings = {
            "enabled": False,
            "mode": "local",
            "webdav_url": "",
            "webdav_username": "",
            "webdav_password": "",
            "webdav_root_path": "chatgpt2api/images",
            "public_base_url": "",
        }
        self.config_patcher = mock.patch("services.image_storage_service.config")
        self.mock_config = self.config_patcher.start()
        self.addCleanup(self.config_patcher.stop)
        self.mock_config.images_dir = self.images_dir
        self.mock_config.base_url = "http://app.test"
        self.mock_config.cleanup_old_images.return_value = 0
        self.mock_config.get_image_storage_settings.side_effect = lambda: dict(self.settings)
        FakeWebDAVClient.uploaded = {}
        FakeWebDAVClient.deleted = []
        FakeWebDAVClient.content_types = {}

    def service(self) -> ImageStorageService:
        return ImageStorageService(self.data_dir / "image_index.json")

    def test_local_mode_saves_to_local_directory(self):
        stored = self.service().save(png_bytes(), "http://app.test")

        self.assertEqual(stored.storage, "local")
        self.assertTrue((self.images_dir / stored.rel).is_file())
        self.assertEqual(stored.url, f"http://app.test/images/{stored.rel}")

    def test_static_formats_keep_original_bytes_extension_and_webdav_type(self):
        self.settings.update({"enabled": True, "mode": "both", "webdav_url": "https://dav.example.test"})
        for image_format, extension, mime in (("JPEG", ".jpg", "image/jpeg"), ("WEBP", ".webp", "image/webp")):
            with self.subTest(format=image_format):
                stream = BytesIO()
                Image.new("RGB", (3, 2), "red").save(stream, format=image_format)
                original = stream.getvalue()
                with mock.patch("services.image_storage_service.WebDAVClient", FakeWebDAVClient):
                    stored = self.service().save(original, "http://app.test")
                self.assertTrue(stored.rel.endswith(extension), stored.rel)
                self.assertEqual((self.images_dir / stored.rel).read_bytes(), original)
                self.assertEqual(FakeWebDAVClient.content_types[stored.rel], mime)

    def test_remote_preview_and_download_use_actual_image_type(self):
        self.settings.update({"enabled": True, "mode": "webdav", "webdav_url": "https://dav.example.test"})
        stream = BytesIO()
        Image.new("RGB", (3, 2), "red").save(stream, format="JPEG")
        original = stream.getvalue()
        service = self.service()
        with (
            mock.patch("services.image_storage_service.WebDAVClient", FakeWebDAVClient),
            mock.patch.object(image_service, "image_storage_service", service),
        ):
            stored = service.save(original, "http://app.test")
            preview = image_service.get_image_response(stored.rel)
            download = image_service.get_image_download_response(stored.rel)
        self.assertEqual(preview.headers["content-type"], "image/jpeg")
        self.assertEqual(download.headers["content-type"], "image/jpeg")
        self.assertIn(".jpg", download.headers["content-disposition"])
        self.assertEqual(preview.body, original)
        self.assertEqual(download.body, original)

    def test_storage_cleanup_dry_run_includes_jpeg_and_webp(self):
        for image_format in ("JPEG", "WEBP"):
            stream = BytesIO()
            Image.new("RGB", (8, 8), "red").save(stream, format=image_format)
            self.service().save(stream.getvalue(), "http://app.test")
        with (
            mock.patch.object(image_service, "config", self.mock_config),
            mock.patch("shutil.disk_usage", return_value=SimpleNamespace(free=0)),
        ):
            result = image_service.delete_to_target(1, dry_run=True)
        self.assertEqual(result["removed"], 2)
        self.assertEqual(len(list(self.images_dir.rglob("*.jpg"))), 1)
        self.assertEqual(len(list(self.images_dir.rglob("*.webp"))), 1)

    def test_compression_keeps_jpeg_encoding_and_includes_its_extension(self):
        image = Image.new("RGB", (96, 96))
        image.putdata([(x * 17 % 256, y * 31 % 256, x * y % 256) for y in range(96) for x in range(96)])
        stream = BytesIO()
        image.save(stream, format="JPEG", quality=100)
        stored = self.service().save(stream.getvalue(), "http://app.test")
        with mock.patch.object(image_service, "config", self.mock_config):
            result = image_service.compress_images(quality=40)
        self.assertEqual(result["compressed"], 1)
        path = self.images_dir / stored.rel
        with Image.open(path) as compressed:
            self.assertEqual(compressed.format, "JPEG")
        self.assertLess(path.stat().st_size, len(stream.getvalue()))

    def test_webdav_mode_uploads_without_local_file(self):
        self.settings.update({
            "enabled": True,
            "mode": "webdav",
            "webdav_url": "https://dav.example.test",
            "webdav_password": "secret",
        })
        with mock.patch("services.image_storage_service.WebDAVClient", FakeWebDAVClient):
            stored = self.service().save(png_bytes(), "http://app.test")
            payload = self.service().get_bytes(stored.rel)

        self.assertEqual(stored.storage, "webdav")
        self.assertFalse((self.images_dir / stored.rel).exists())
        self.assertIn(stored.rel, FakeWebDAVClient.uploaded)
        self.assertEqual(payload, FakeWebDAVClient.uploaded[stored.rel])

    def test_list_items_ignores_non_image_files(self):
        image = png_bytes()
        image_path = self.images_dir / "2026" / "05" / "07" / "sample.png"
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(image)
        (self.images_dir / ".DS_Store").write_text("not an image", encoding="utf-8")
        (self.images_dir / "2026" / ".DS_Store").write_text("not an image", encoding="utf-8")

        items = self.service().list_items("http://app.test")

        self.assertEqual([item["rel"] for item in items], ["2026/05/07/sample.png"])
        self.assertEqual(items[0]["storage"], "local")

    def test_both_mode_saves_to_local_and_webdav(self):
        self.settings.update({
            "enabled": True,
            "mode": "both",
            "webdav_url": "https://dav.example.test",
            "webdav_password": "secret",
            "public_base_url": "https://cdn.example.test/images",
        })
        with mock.patch("services.image_storage_service.WebDAVClient", FakeWebDAVClient):
            stored = self.service().save(png_bytes(), "http://app.test")

        self.assertEqual(stored.storage, "both")
        self.assertTrue((self.images_dir / stored.rel).is_file())
        self.assertIn(stored.rel, FakeWebDAVClient.uploaded)
        self.assertEqual(stored.url, f"https://cdn.example.test/images/{stored.rel}")

    def test_test_webdav_writes_and_deletes_probe_file(self):
        self.settings.update({
            "enabled": True,
            "mode": "webdav",
            "webdav_url": "https://dav.example.test",
            "webdav_password": "secret",
        })
        with mock.patch("services.image_storage_service.WebDAVClient", FakeWebDAVClient):
            result = self.service().test_webdav()

        self.assertTrue(result["ok"])
        self.assertIn(".chatgpt2api_webdav_test.txt", FakeWebDAVClient.deleted)


if __name__ == "__main__":
    unittest.main()

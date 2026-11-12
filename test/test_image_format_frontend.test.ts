import { expect, test } from "bun:test";
import { imageDataUrl, imageFileExtension, imageMimeType } from "../web/src/lib/image-data";

test("下载和引用图使用真实 JPEG/WebP 格式", () => {
  const jpeg = { b64_json: "/9j/4A==", mime_type: "image/png" };
  expect(imageMimeType(jpeg)).toBe("image/jpeg");
  expect(imageDataUrl(jpeg)).toStartWith("data:image/jpeg;base64,");
  expect(imageFileExtension(imageMimeType(jpeg))).toBe("jpg");
  const webp = { b64_json: btoa("RIFF0000WEBP") };
  expect(imageMimeType(webp)).toBe("image/webp");
  expect(imageFileExtension(imageMimeType(webp))).toBe("webp");
});

test("URL 和旧 PNG 结果可用且不误改文件类型", () => {
  expect(imageMimeType({ url: "https://example.test/image.jpeg?download=1" })).toBe("image/jpeg");
  expect(imageMimeType({ b64_json: "iVBORw0KGgo=" })).toBe("image/png");
  expect(imageFileExtension(imageMimeType({}))).toBe("png");
});

test("GIF 原始字节决定播放类型和下载后缀", () => {
  for (const signature of ["GIF87a", "GIF89a"]) {
    const image = { b64_json: btoa(signature + "\0".repeat(12)), mime_type: "image/png" };
    expect(imageMimeType(image)).toBe("image/gif");
    expect(imageDataUrl(image)).toStartWith("data:image/gif;base64,");
    expect(imageFileExtension(imageMimeType(image))).toBe("gif");
  }
  expect(imageMimeType({ url: "https://example.test/animation.GIF?download=1" })).toBe("image/gif");
  expect(imageMimeType({ mime_type: "image/gif" })).toBe("image/gif");
});

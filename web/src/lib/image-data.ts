/** 保留网页实际返回的静态图片类型；旧 PNG 数据仍可正常显示和下载。 */
export type ImagePayload = { b64_json?: string; url?: string; mime_type?: string };

export function imageMimeType(image: ImagePayload): string {
  if (image.b64_json) {
    try {
      const header = atob(image.b64_json.slice(0, 32));
      if (header.charCodeAt(0) === 0xff && header.charCodeAt(1) === 0xd8) return "image/jpeg";
      if (header.startsWith("RIFF") && header.slice(8, 12) === "WEBP") return "image/webp";
      if (header.startsWith("\x89PNG")) return "image/png";
    } catch {
      // 不完整的旧缓存交给已有图片加载逻辑处理。
    }
  }
  const reported = image.mime_type?.split(";", 1)[0].trim().toLowerCase();
  if (reported && ["image/png", "image/jpeg", "image/webp"].includes(reported)) return reported;
  const path = image.url?.split(/[?#]/, 1)[0].toLowerCase() || "";
  if (/\.jpe?g$/.test(path)) return "image/jpeg";
  if (path.endsWith(".webp")) return "image/webp";
  return "image/png";
}

export function imageFileExtension(mime: string): string {
  if (mime === "image/jpeg") return "jpg";
  if (mime === "image/webp") return "webp";
  return "png";
}

export function imageDataUrl(image: ImagePayload): string {
  return `data:${imageMimeType(image)};base64,${image.b64_json || ""}`;
}

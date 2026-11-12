/** 按原始字节保留静态图片与 GIF 类型，播放和下载使用同一份内容。 */
export type ImagePayload = { b64_json?: string; url?: string; mime_type?: string };

export function imageMimeType(image: ImagePayload): string {
  if (image.b64_json) {
    try {
      const header = atob(image.b64_json.slice(0, 32));
      if (header.startsWith("GIF87a") || header.startsWith("GIF89a")) return "image/gif";
      if (header.charCodeAt(0) === 0xff && header.charCodeAt(1) === 0xd8) return "image/jpeg";
      if (header.startsWith("RIFF") && header.slice(8, 12) === "WEBP") return "image/webp";
      if (header.startsWith("\x89PNG")) return "image/png";
    } catch {
      // 不完整的旧缓存交给已有图片加载逻辑处理。
    }
  }
  const reported = image.mime_type?.split(";", 1)[0].trim().toLowerCase();
  if (reported && ["image/png", "image/jpeg", "image/webp", "image/gif"].includes(reported)) return reported;
  const path = image.url?.split(/[?#]/, 1)[0].toLowerCase() || "";
  if (/\.jpe?g$/.test(path)) return "image/jpeg";
  if (path.endsWith(".webp")) return "image/webp";
  if (path.endsWith(".gif")) return "image/gif";
  return "image/png";
}

export function imageFileExtension(mime: string): string {
  if (mime === "image/gif") return "gif";
  if (mime === "image/jpeg") return "jpg";
  if (mime === "image/webp") return "webp";
  return "png";
}

export function imageDataUrl(image: ImagePayload): string {
  return `data:${imageMimeType(image)};base64,${image.b64_json || ""}`;
}

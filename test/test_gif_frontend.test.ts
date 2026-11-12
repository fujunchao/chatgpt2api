import { describe, expect, mock, test } from "bun:test";

// 只替换浏览器数据库边界，公开历史接口仍执行真实的读写与规范化逻辑。
mock.module("../web/node_modules/localforage", () => ({
  default: {
    createInstance: () => {
      const items = new Map<string, unknown>();
      return {
        getItem: async (key: string) => structuredClone(items.get(key) ?? null),
        setItem: async (key: string, value: unknown) => { items.set(key, structuredClone(value)); return value; },
        removeItem: async (key: string) => { items.delete(key); },
      };
    },
  },
}));

const { listImageConversations, saveImageConversation } = await import("../web/src/store/image-conversations");
const { createImageGenerationTask, createImageEditTask, generateImage, editImage } = await import("../web/src/lib/api");
const { request } = await import("../web/src/lib/request");

describe("GIF 图片历史", () => {
  test("重新读取历史保留 GIF 目标、帧提示和实际动画信息", async () => {
    await saveImageConversation({
      id: "gif-history", title: "小球循环弹跳", createdAt: "2026-11-12T12:00:00Z", updatedAt: "2026-11-12T12:00:00Z",
      turns: [{
        id: "gif-turn", prompt: "小球循环弹跳", model: "gpt-image-2.6-flare", mode: "generate",
        referenceImages: [], count: 1, size: "1024x1024", ratio: "1:1", tier: "1k", quality: "auto",
        outputFormat: "gif", frameCount: 8, frameDurationMs: 150,
        images: [{
          id: "gif-result", taskId: "gif-task", status: "success", url: "/images/bounce.gif",
          mime_type: "image/gif", output_format: "gif", frame_count: 9,
          frame_durations_ms: [200, 200, 200, 200, 200, 200, 200, 200, 200], duration_ms: 1800,
          loop: 0, durationMs: 61500,
        }],
        createdAt: "2026-11-12T12:00:00Z", status: "success",
      }],
    });
    const turn = (await listImageConversations()).find((item) => item.id === "gif-history")!.turns[0];
    expect(turn.outputFormat).toBe("gif");
    expect(turn.frameCount).toBe(8);
    expect(turn.frameDurationMs).toBe(150);
    expect(turn.images[0].mime_type).toBe("image/gif");
    expect(turn.images[0].frame_count).toBe(9);
    expect(turn.images[0].duration_ms).toBe(1800);
    expect(turn.images[0].durationMs).toBe(61500);
  });
});

describe("GIF 图片请求", () => {
  test("直接生成、编辑及持久任务都把 GIF 目标和帧提示发送到 HTTP 接口", async () => {
    const received: Array<{ path: string; body: Record<string, unknown> }> = [];
    const server = Bun.serve({
      hostname: "127.0.0.1", port: 0,
      async fetch(incoming) {
        const multipart = incoming.headers.get("content-type")?.includes("multipart/form-data");
        const body = multipart
          ? Object.fromEntries((await incoming.formData()).entries())
          : await incoming.json();
        received.push({ path: new URL(incoming.url).pathname, body });
        return Response.json({ id: "gif-task", status: "queued", created: 1, data: [] });
      },
    });
    const originalBaseURL = request.defaults.baseURL;
    request.defaults.baseURL = server.url.toString();
    try {
      const options = { output_format: "gif" as const, frame_count: 8, frame_duration_ms: 150 };
      const reference = new File(["static-reference"], "reference.png", { type: "image/png" });
      await createImageGenerationTask("generate-task", "小球跳动", "gpt-image-2.6", "1024x1024", "auto", options);
      await createImageEditTask("edit-task", reference, "小球跳动", "gpt-image-2.6-flare", "1024x1024", "auto", options);
      await generateImage("小球跳动", "gpt-image-2.6", "1024x1024", "auto", options);
      await editImage(reference, "小球跳动", "gpt-image-2.6-flare", "1024x1024", "auto", options);
      expect(received.map((item) => item.path)).toEqual([
        "/api/image-tasks/generations", "/api/image-tasks/edits", "/v1/images/generations", "/v1/images/edits",
      ]);
      for (const { body } of received) {
        expect(body.output_format).toBe("gif");
        expect(Number(body.frame_count)).toBe(8);
        expect(Number(body.frame_duration_ms)).toBe(150);
      }
      expect(received[1].body.image).toBeInstanceOf(File);
    } finally {
      request.defaults.baseURL = originalBaseURL;
      server.stop(true);
    }
  });
});

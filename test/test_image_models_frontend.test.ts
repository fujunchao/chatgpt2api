import { describe, expect, test } from "bun:test";
import {
  imageQualityOptions,
  imageModelDescription,
  imageModelLabel,
  isCodexImageModel,
  isGptImage25Model,
  isWebAutoImageModel,
  normalizeImageQuality,
} from "../web/src/lib/image-models";

describe("2.5 图片界面能力", () => {
  test("免费 Web 入口与 Codex 变体在名称和能力说明上分开", () => {
    expect(isWebAutoImageModel(" GPT-IMAGE-2.5 ")).toBe(true);
    expect(isCodexImageModel("gpt-image-2.5")).toBe(false);
    expect(isWebAutoImageModel("gpt-image-2.5-flare")).toBe(false);
    expect(imageModelLabel("gpt-image-2.5")).toBe("gpt-image-2.5 · Web 自动");
    expect(imageModelLabel("gpt-image-2.5-flare")).toContain("Codex");
    expect(imageModelDescription("gpt-image-2.5")).toContain("Free");
    expect(imageModelDescription("gpt-image-2.5")).toContain("具体版本未知");
    expect(imageModelDescription("gpt-image-2.5")).toContain("不能指定 Flare / Sunburst");
    expect(imageQualityOptions("gpt-image-2.5").map((option) => option.value)).toEqual(["auto", "low", "medium", "high"]);
    expect(normalizeImageQuality("gpt-image-2.5", "max")).toBe("auto");
  });

  test("官方名称与显式 Codex 别名使用相同能力", () => {
    for (const name of ["gpt-image-2.5-flare", "gpt-image-2.5-sunburst", "codex-gpt-image-2.5", "pro-codex-gpt-image-2.5-sunburst"]) {
      expect(isGptImage25Model(name)).toBe(true);
      expect(isCodexImageModel(name)).toBe(true);
      expect(imageQualityOptions(name).map((option) => option.value)).toContain("max");
    }
  });

  test("旧模型路由不变", () => {
    expect(isCodexImageModel("gpt-image-2")).toBe(false);
    expect(isCodexImageModel("team-codex-gpt-image-2")).toBe(true);
    expect(isGptImage25Model("gpt-image-2.5")).toBe(false);
    expect(imageQualityOptions("gpt-image-2")).toHaveLength(4);
  });

  test("切回旧模型时复位新质量档位", () => {
    expect(normalizeImageQuality("gpt-image-2", "max")).toBe("auto");
    expect(normalizeImageQuality("gpt-image-2.5-sunburst", "xhigh")).toBe("xhigh");
    expect(normalizeImageQuality("gpt-image-2.5-flare", "invalid")).toBe("auto");
    expect(normalizeImageQuality("gpt-image-2", "high")).toBe("high");
  });
});

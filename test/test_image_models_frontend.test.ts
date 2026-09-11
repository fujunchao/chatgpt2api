import { describe, expect, test } from "bun:test";
import {
  imageQualityOptions,
  isCodexImageModel,
  isGptImage25Model,
  normalizeImageQuality,
} from "../web/src/lib/image-models";

describe("2.5 图片界面能力", () => {
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

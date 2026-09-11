/** 与后端保持一致：裸 2.5 是 Web 自动入口，带变体的裸名称仍走 Codex。 */
export function isWebAutoImageModel(model: string): boolean {
  return model.trim().toLowerCase() === "gpt-image-2.5";
}

/** 此谓词只识别 Codex 2.5 请求选项，不代表上游已确认图片引擎身份。 */
export function isGptImage25Model(model: string): boolean {
  return /^(?:gpt-image-2\.5-(?:flare|sunburst)|(?:(?:plus|team|pro)-)?codex-gpt-image-2\.5(?:-(?:flare|sunburst))?)$/.test(
    model.trim().toLowerCase(),
  );
}

export function isCodexImageModel(model: string): boolean {
  return isGptImage25Model(model) || /^(?:(?:plus|team|pro)-)?codex-gpt-image-2$/.test(model.trim().toLowerCase());
}

export function imageModelLabel(model: string): string {
  if (isWebAutoImageModel(model)) return `${model} · Web 自动`;
  if (isCodexImageModel(model)) return `${model} · Codex`;
  return model;
}

export function imageModelDescription(model: string): string {
  if (isWebAutoImageModel(model)) {
    return "使用网页账号额度（包括 Free）。复用 gpt-image-2 的网页请求；图片引擎由官网自动选择，具体版本未知，不能指定 Flare / Sunburst。尺寸和质量仅作为提示，以上游实际结果为准。";
  }
  if (isCodexImageModel(model)) {
    return "使用 Codex 图片通道，需 Codex 来源的 Plus / Team / Pro 账号；模型、尺寸和质量参数是否生效，以上游实际结果为准。";
  }
  return "";
}

const baseQualities = [
  { value: "auto", label: "自动" },
  { value: "low", label: "低" },
  { value: "medium", label: "中" },
  { value: "high", label: "高" },
];

export function imageQualityOptions(model: string) {
  return isGptImage25Model(model)
    ? [...baseQualities, { value: "xhigh", label: "超高" }, { value: "max", label: "最高" }]
    : baseQualities;
}

export function normalizeImageQuality(model: string, quality: string): string {
  return imageQualityOptions(model).some((option) => option.value === quality) ? quality : "auto";
}

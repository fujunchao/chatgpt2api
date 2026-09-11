/** 与后端模型注册表保持一致的界面能力，避免把 2.5 的裸名称误当成 Web 模型。 */
export function isGptImage25Model(model: string): boolean {
  return /^(?:gpt-image-2\.5-(?:flare|sunburst)|(?:(?:plus|team|pro)-)?codex-gpt-image-2\.5(?:-(?:flare|sunburst))?)$/.test(
    model.trim().toLowerCase(),
  );
}

export function isCodexImageModel(model: string): boolean {
  return isGptImage25Model(model) || /^(?:(?:plus|team|pro)-)?codex-gpt-image-2$/.test(model.trim().toLowerCase());
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

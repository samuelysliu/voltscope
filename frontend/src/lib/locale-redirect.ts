import type { Locale } from "@/lib/i18n";

type HeaderReader = Pick<Headers, "get">;

const COUNTRY_HEADERS = [
  "x-vercel-ip-country",
  "cf-ipcountry",
  "cloudfront-viewer-country",
  "x-appengine-country",
  "x-country-code"
] as const;

const CHINESE_REGIONS = new Set(["TW", "HK", "MO", "CN"]);

function countryCode(headers: HeaderReader): string | null {
  for (const header of COUNTRY_HEADERS) {
    const value = headers.get(header)?.trim().toUpperCase();
    if (value && /^[A-Z]{2}$/.test(value) && value !== "XX") return value;
  }
  return null;
}

function localeFromLanguages(value: string | null): Locale {
  if (!value) return "en";
  const languages = value
    .split(",")
    .map((part, index) => {
      const [language, ...parameters] = part.trim().toLowerCase().split(";");
      const qualityParameter = parameters.find((parameter) => parameter.trim().startsWith("q="));
      const quality = qualityParameter ? Number(qualityParameter.trim().slice(2)) : 1;
      return { language, quality: Number.isFinite(quality) ? quality : 0, index };
    })
    .sort((left, right) => right.quality - left.quality || left.index - right.index);

  for (const { language } of languages) {
    if (language === "zh" || language.startsWith("zh-")) return "zh";
    if (language === "en" || language.startsWith("en-")) return "en";
  }
  return "en";
}

export function preferredLocale(headers: HeaderReader): Locale {
  const country = countryCode(headers);
  if (country) return CHINESE_REGIONS.has(country) ? "zh" : "en";
  return localeFromLanguages(headers.get("accept-language"));
}

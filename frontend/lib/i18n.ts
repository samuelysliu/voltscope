export const locales = ["zh", "en"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = "zh";

export function isLocale(value: string): value is Locale {
  return locales.includes(value as Locale);
}

export function alternateLocale(locale: Locale): Locale {
  return locale === "zh" ? "en" : "zh";
}

export function localeName(locale: Locale): string {
  return locale === "zh" ? "繁體中文" : "English";
}

export function dbLocale(locale: Locale): string {
  return locale === "zh" ? "zh-TW" : "en";
}

export function htmlLang(locale: Locale): string {
  return locale === "zh" ? "zh-TW" : "en";
}

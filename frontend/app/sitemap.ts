import type { MetadataRoute } from "next";
import { getHome, listArticles, type ArticleSummary } from "@/lib/api";
import type { Locale } from "@/lib/i18n";

const API_BASE_URL = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

function dbLocale(locale: Locale) {
  return locale === "zh" ? "zh-TW" : "en";
}

async function listAllPublishedArticles(locale: Locale): Promise<ArticleSummary[]> {
  const pageSize = 100;
  const items: ArticleSummary[] = [];
  for (let page = 1; page <= 50; page += 1) {
    try {
      const response = await fetch(
        `${API_BASE_URL}/public/articles?locale=${encodeURIComponent(dbLocale(locale))}&page=${page}&page_size=${pageSize}`,
        { next: { revalidate: 300 } }
      );
      if (!response.ok) break;
      const data = (await response.json()) as { items?: ArticleSummary[]; total?: number };
      const pageItems = data.items || [];
      items.push(...pageItems);
      if (items.length >= (data.total || 0) || pageItems.length < pageSize) break;
    } catch {
      break;
    }
  }
  if (items.length) return items;
  return listArticles(locale);
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const host = process.env.FRONTEND_URL || "http://localhost:3000";
  const locales: Locale[] = ["zh", "en"];
  const now = new Date();
  const entries: MetadataRoute.Sitemap = [];

  for (const locale of locales) {
    const home = await getHome(locale);
    const articles = await listAllPublishedArticles(locale);
    entries.push({
      url: `${host}/${locale}`,
      lastModified: now,
      alternates: { languages: { "zh-TW": `${host}/zh`, en: `${host}/en`, "x-default": `${host}/zh` } }
    });
    entries.push({ url: `${host}/${locale}/articles`, lastModified: now });
    for (const topic of home.topics) {
      entries.push({
        url: `${host}/${locale}/topics/${topic.slug}`,
        lastModified: now,
        alternates: {
          languages: {
            "zh-TW": `${host}/zh/topics/${topic.slug}`,
            en: `${host}/en/topics/${topic.slug}`,
            "x-default": `${host}/zh/topics/${topic.slug}`
          }
        }
      });
    }
    for (const article of articles) {
      entries.push({
        url: `${host}/${locale}/articles/${article.slug}`,
        lastModified: new Date(article.updated_at),
        alternates: {
          languages: {
            "zh-TW": `${host}/zh/articles/${article.slug}`,
            en: `${host}/en/articles/${article.slug}`,
            "x-default": `${host}/zh/articles/${article.slug}`
          }
        }
      });
    }
  }

  return entries;
}

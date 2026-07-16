import { z } from "zod";
import { dbLocale, type Locale } from "./i18n";

const API_BASE_URL = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

const TopicSchema = z.object({
  id: z.string(),
  slug: z.string(),
  name_zh: z.string(),
  name_en: z.string(),
  description_zh: z.string().nullable().optional(),
  description_en: z.string().nullable().optional()
});

export type Topic = z.infer<typeof TopicSchema>;

const ArticleSummarySchema = z.object({
  id: z.string(),
  title: z.string(),
  slug: z.string(),
  excerpt: z.string(),
  locale: z.string(),
  published_at: z.string().nullable(),
  updated_at: z.string(),
  hero_image_url: z.string().nullable().optional(),
  thumbnail_url: z.string().nullable().optional(),
  views_count: z.number().default(0),
  likes_count: z.number().default(0),
  comments_count: z.number().default(0),
  topics: z.array(TopicSchema).default([])
});

export type ArticleSummary = z.infer<typeof ArticleSummarySchema>;

const ArticleSchema = ArticleSummarySchema.extend({
  status: z.string(),
  is_featured: z.boolean(),
  show_ads: z.boolean().default(true),
  og_image_url: z.string().nullable().optional(),
  content_html: z.string(),
  content_text: z.string(),
  seo_title: z.string().nullable().optional(),
  seo_description: z.string().nullable().optional(),
  canonical_url: z.string().nullable().optional(),
  author: z.object({
    id: z.string(),
    slug: z.string(),
    display_name: z.string(),
    bio_zh: z.string().nullable().optional(),
    bio_en: z.string().nullable().optional()
  }),
  tags: z.array(z.object({ id: z.string(), slug: z.string(), name_zh: z.string(), name_en: z.string() })).default([])
});

export type Article = z.infer<typeof ArticleSchema>;

const CommentSchema = z.object({
  id: z.string(),
  author_name: z.string(),
  body: z.string(),
  status: z.string(),
  created_at: z.string()
});

export type PublicComment = z.infer<typeof CommentSchema>;

const AdSchema = z.object({
  id: z.string(),
  name: z.string().nullable().optional(),
  image_url: z.string().nullable().optional(),
  target_url: z.string(),
  alt_text: z.string(),
  placement: z.string(),
  weight: z.number().default(0)
});

export type PublicAd = z.infer<typeof AdSchema>;

const HomeSchema = z.object({
  latest_articles: z.array(ArticleSummarySchema),
  featured_articles: z.array(ArticleSummarySchema),
  topics: z.array(TopicSchema),
  active_home_ads: z.array(AdSchema)
});

export type HomeData = z.infer<typeof HomeSchema>;

const TopicPageSchema = z.object({
  topic: TopicSchema,
  articles: z.array(ArticleSummarySchema),
  total: z.number(),
  page: z.number(),
  page_size: z.number()
});

export type TopicPageData = z.infer<typeof TopicPageSchema>;

const ArticleDetailSchema = z.object({
  article: ArticleSchema,
  translation: ArticleSchema,
  topics: z.array(TopicSchema),
  comments: z.array(CommentSchema),
  ads: z.array(AdSchema),
  previous_article: ArticleSummarySchema.nullable(),
  next_article: ArticleSummarySchema.nullable()
});

export type ArticleDetail = z.infer<typeof ArticleDetailSchema>;

const fallbackTopics: Topic[] = [
  { id: "ev", slug: "ev", name_zh: "電動車", name_en: "Electric Vehicles" },
  { id: "charging", slug: "charging", name_zh: "充電", name_en: "Charging" },
  { id: "charging-station", slug: "charging-station", name_zh: "充電樁", name_en: "Charging Stations" },
  { id: "charging-deals", slug: "charging-deals", name_zh: "充電優惠", name_en: "Charging Deals" },
  { id: "smart-mobility", slug: "smart-mobility", name_zh: "智慧移動", name_en: "Smart Mobility" },
  { id: "energy", slug: "energy", name_zh: "能源", name_en: "Energy" },
  { id: "energy-storage", slug: "energy-storage", name_zh: "儲能", name_en: "Energy Storage" }
];

const fallbackImage = "https://images.unsplash.com/photo-1593941707882-a5bba14938c7?auto=format&fit=crop&w=1400&q=80";

function fallbackArticle(locale: Locale): Article {
  const isZh = locale === "zh";
  return {
    id: "demo",
    status: "published",
    is_featured: true,
    show_ads: true,
    hero_image_url: fallbackImage,
    thumbnail_url: fallbackImage,
    og_image_url: fallbackImage,
    views_count: 0,
    likes_count: 0,
    comments_count: 0,
    published_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    locale: dbLocale(locale),
    title: isZh ? "電動車充電入門" : "EV charging basics",
    slug: "ev-charging-basics",
    excerpt: isZh
      ? "理解充電速度、接頭、居家安裝與日常補能規劃。"
      : "A practical guide to charging speeds, connectors, home setup, and daily charging planning.",
    content_html: isZh
      ? "<p>規劃電動車充電時，先確認每日里程、電路容量與接頭相容性。公共快充適合長途補能，居家慢充則適合日常使用。</p><h2>重點摘要</h2><p>好的充電策略需要同時考慮安全、電費、車款相容性與未來擴充。</p>"
      : "<p>EV charging planning starts with daily range, circuit capacity, and connector compatibility. Public fast charging fits road trips, while home charging is best for daily use.</p><h2>Key takeaways</h2><p>A good charging strategy balances safety, energy cost, vehicle compatibility, and future expansion.</p>",
    content_text: isZh
      ? "規劃電動車充電時，先確認每日里程、電路容量與接頭相容性。"
      : "EV charging planning starts with daily range, circuit capacity, and connector compatibility.",
    seo_title: isZh ? "電動車充電入門" : "EV Charging Basics",
    seo_description: isZh ? "快速理解電動車充電速度、接頭與居家安裝。" : "Learn the basics of EV charging speeds, connectors, and home setup.",
    canonical_url: null,
    author: { id: "author", slug: "editorial-team", display_name: "Editorial Team", bio_zh: "能源與充電技術編輯團隊", bio_en: "Energy editors" },
    tags: [],
    topics: [fallbackTopics[1]]
  };
}

function summarize(article: Article): ArticleSummary {
  const {
    id,
    title,
    slug,
    excerpt,
    locale,
    published_at,
    updated_at,
    hero_image_url,
    thumbnail_url,
    views_count,
    likes_count,
    comments_count,
    topics
  } = article;
  return { id, title, slug, excerpt, locale, published_at, updated_at, hero_image_url, thumbnail_url, views_count, likes_count, comments_count, topics };
}

async function getJson<Schema extends z.ZodTypeAny>(path: string, schema: Schema, revalidate = 60): Promise<z.infer<Schema> | null> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, { next: { revalidate } });
    if (!response.ok) return null;
    return schema.parse(await response.json());
  } catch {
    return null;
  }
}

export async function getHome(locale: Locale): Promise<HomeData> {
  const result = await getJson(`/public/home?locale=${encodeURIComponent(dbLocale(locale))}`, HomeSchema);
  if (result) return result;
  const article = fallbackArticle(locale);
  return {
    latest_articles: [summarize(article)],
    featured_articles: [summarize(article)],
    topics: fallbackTopics,
    active_home_ads: []
  };
}

export async function listArticles(locale: Locale, topic?: string, q?: string): Promise<ArticleSummary[]> {
  if (topic) {
    const page = await getTopicPage(locale, topic);
    return page.articles.length ? page.articles : [summarize(fallbackArticle(locale))];
  }
  const path = q
    ? `/public/search?locale=${encodeURIComponent(dbLocale(locale))}&q=${encodeURIComponent(q)}`
    : `/public/articles?locale=${encodeURIComponent(dbLocale(locale))}`;
  const schema = z.object({ items: z.array(ArticleSchema) });
  const result = await getJson(path, schema);
  return result?.items.length ? result.items.map(summarize) : [summarize(fallbackArticle(locale))];
}

export async function getArticleDetail(locale: Locale, slug: string): Promise<ArticleDetail | null> {
  const result = await getJson(`/public/articles/${encodeURIComponent(dbLocale(locale))}/${encodeURIComponent(slug)}`, ArticleDetailSchema, 0);
  if (result) return result;
  if (slug !== "ev-charging-basics") return null;
  const article = fallbackArticle(locale);
  return {
    article,
    translation: article,
    topics: article.topics,
    comments: [],
    ads: [],
    previous_article: null,
    next_article: null
  };
}

export async function getArticle(locale: Locale, slug: string): Promise<Article | null> {
  return (await getArticleDetail(locale, slug))?.article ?? null;
}

export async function listTopics(): Promise<Topic[]> {
  const result = await getJson("/public/topics", z.array(TopicSchema));
  return result?.length ? result : fallbackTopics;
}

export async function getTopicPage(locale: Locale, slug: string, page = 1): Promise<TopicPageData> {
  const result = await getJson(
    `/public/topics/${encodeURIComponent(dbLocale(locale))}/${encodeURIComponent(slug)}?page=${page}`,
    TopicPageSchema
  );
  if (result) return result;
  const topic = fallbackTopics.find((item) => item.slug === slug) ?? fallbackTopics[0];
  return { topic, articles: [summarize(fallbackArticle(locale))], total: 1, page, page_size: 12 };
}

export async function listTags() {
  return listTopics();
}

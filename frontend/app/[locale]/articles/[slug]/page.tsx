import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArticleEngagement } from "@/components/article-engagement";
import { Badge } from "@/src/components/ui/badge";
import { Button } from "@/src/components/ui/button";
import { getArticleDetail, type PublicAd } from "@/lib/api";
import { htmlLang, type Locale } from "@/lib/i18n";

export const dynamic = "force-dynamic";

const fallbackImage = "https://images.unsplash.com/photo-1593941707882-a5bba14938c7?auto=format&fit=crop&w=1400&q=80";

function absoluteUrl(value: string, host: string) {
  if (value.startsWith("http://") || value.startsWith("https://")) return value;
  return `${host}${value.startsWith("/") ? value : `/${value}`}`;
}

function splitArticleHtml(html: string): [string, string] {
  const paragraphEnds = Array.from(html.matchAll(/<\/p>/gi));
  if (paragraphEnds.length < 2) return [html, ""];
  const middle = paragraphEnds[Math.floor(paragraphEnds.length / 2) - 1];
  const index = (middle.index || 0) + middle[0].length;
  return [html.slice(0, index), html.slice(index)];
}

function AdSlot({ ads, className = "" }: { ads: PublicAd[]; className?: string }) {
  if (!ads.length) return null;
  return (
    <aside className={`space-y-3 ${className}`} aria-label="Advertisement">
      {ads.map((ad) => (
        <a className="block overflow-hidden rounded-lg border border-line bg-white" href={ad.target_url} key={ad.id} rel="noreferrer sponsored" target="_blank">
          {ad.image_url ? <img className="w-full object-cover" src={ad.image_url} alt={ad.alt_text} loading="lazy" /> : null}
        </a>
      ))}
    </aside>
  );
}

export async function generateMetadata({ params }: { params: Promise<{ locale: Locale; slug: string }> }): Promise<Metadata> {
  const { locale, slug } = await params;
  const detail = await getArticleDetail(locale, slug);
  if (!detail) return {};
  const article = detail.article;
  const host = process.env.FRONTEND_URL || "http://localhost:3000";
  const image = absoluteUrl(article.og_image_url || article.hero_image_url || article.thumbnail_url || fallbackImage, host);
  const canonical = article.canonical_url ? absoluteUrl(article.canonical_url, host) : `${host}/${locale}/articles/${article.slug}`;
  return {
    title: article.seo_title || article.title,
    description: article.seo_description || article.excerpt,
    alternates: {
      canonical,
      languages: {
        "zh-TW": `${host}/zh/articles/${article.slug}`,
        en: `${host}/en/articles/${article.slug}`,
        "x-default": `${host}/zh/articles/${article.slug}`
      }
    },
    openGraph: {
      title: article.seo_title || article.title,
      description: article.seo_description || article.excerpt,
      type: "article",
      publishedTime: article.published_at || undefined,
      modifiedTime: article.updated_at,
      images: [{ url: image, alt: article.title }]
    }
  };
}

export default async function ArticlePage({ params }: { params: Promise<{ locale: Locale; slug: string }> }) {
  const { locale, slug } = await params;
  const detail = await getArticleDetail(locale, slug);
  if (!detail) notFound();
  const article = detail.article;
  const host = process.env.FRONTEND_URL || "http://localhost:3000";
  const sourceImage = article.hero_image_url || article.thumbnail_url;
  const image = sourceImage ? absoluteUrl(sourceImage, host) : undefined;
  const articleUrl = `${host}/${locale}/articles/${article.slug}`;
  const topicNames = detail.topics.map((topic) => (locale === "zh" ? topic.name_zh : topic.name_en));
  const topicSlugs = new Set(detail.topics.map((topic) => topic.slug));
  const additionalTags = article.tags.filter((tag) => !topicSlugs.has(tag.slug));
  const [firstArticleHtml, secondArticleHtml] = splitArticleHtml(article.content_html);
  const topAds = detail.ads.filter((ad) => ad.placement === "article_top");
  const middleAds = detail.ads.filter((ad) => ad.placement === "article_middle");
  const bottomAds = detail.ads.filter((ad) => ad.placement === "article_bottom");
  const sidebarAds = detail.ads.filter((ad) => ad.placement === "sidebar");
  const jsonLd = [
    {
      "@context": "https://schema.org",
      "@type": "Organization",
      name: "VoltScope",
      url: host
    },
    {
      "@context": "https://schema.org",
      "@type": "WebSite",
      name: "VoltScope",
      url: host,
      inLanguage: htmlLang(locale)
    },
    {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      itemListElement: [
        { "@type": "ListItem", position: 1, name: locale === "zh" ? "首頁" : "Home", item: `${host}/${locale}` },
        { "@type": "ListItem", position: 2, name: locale === "zh" ? "文章" : "Articles", item: `${host}/${locale}/articles` },
        { "@type": "ListItem", position: 3, name: article.title, item: articleUrl }
      ]
    },
    {
      "@context": "https://schema.org",
      "@type": "Article",
      headline: article.title,
      description: article.excerpt,
      image,
      datePublished: article.published_at,
      dateModified: article.updated_at,
      author: { "@type": "Person", name: article.author.display_name },
      publisher: { "@type": "Organization", name: "VoltScope" },
      mainEntityOfPage: articleUrl,
      inLanguage: htmlLang(locale),
      keywords: topicNames.join(", ")
    }
  ];

  return (
    <main>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <article className="mx-auto max-w-3xl px-4 py-10">
        <nav className="mb-6 flex flex-wrap items-center gap-3 text-sm text-zinc-600">
          <Link className="font-semibold text-signal" href={`/${locale}`}>
            {locale === "zh" ? "回首頁" : "Home"}
          </Link>
          <span>VoltScope / {locale === "zh" ? "文章" : "Articles"}</span>
        </nav>
        <header>
          <div className="flex flex-wrap gap-2">
            {detail.topics.map((topic) => (
              <Badge key={topic.slug} variant="secondary">
                <Link href={`/${locale}/topics/${topic.slug}`}>{locale === "zh" ? topic.name_zh : topic.name_en}</Link>
              </Badge>
            ))}
            {additionalTags.map((tag) => (
              <Badge key={tag.slug} variant="outline">
                {locale === "zh" ? tag.name_zh : tag.name_en}
              </Badge>
            ))}
          </div>
          <h1 className="mt-4 text-4xl font-bold leading-tight md:text-5xl">{article.title}</h1>
          <p className="mt-4 text-lg leading-8 text-zinc-700">{article.excerpt}</p>
          <div className="mt-5 flex flex-wrap gap-3 text-sm text-zinc-600">
            <span>{article.author.display_name}</span>
            <span>{article.published_at ? new Date(article.published_at).toLocaleDateString(locale === "zh" ? "zh-TW" : "en-US") : ""}</span>
            <span>{locale === "zh" ? "更新" : "Updated"} {new Date(article.updated_at).toLocaleDateString(locale === "zh" ? "zh-TW" : "en-US")}</span>
          </div>
          {image ? <img className="mt-8 aspect-[16/9] w-full rounded-lg object-cover" src={image} alt={article.title} /> : null}
        </header>

        {article.show_ads ? <AdSlot ads={topAds} className="mt-8" /> : null}

        <section className="article-body mt-8" dangerouslySetInnerHTML={{ __html: firstArticleHtml }} />
        {article.show_ads ? <AdSlot ads={middleAds} className="my-8" /> : null}
        {secondArticleHtml ? <section className="article-body" dangerouslySetInnerHTML={{ __html: secondArticleHtml }} /> : null}

        {article.show_ads ? <AdSlot ads={bottomAds} className="mt-10" /> : null}
        {article.show_ads ? <AdSlot ads={sidebarAds} className="mt-10" /> : null}

        <div className="mt-10 grid gap-4 border-y border-line py-6 md:grid-cols-2">
          {detail.previous_article ? (
            <Link className="rounded-lg border border-line p-4" href={`/${locale}/articles/${detail.previous_article.slug}`}>
              <span className="text-sm text-zinc-500">{locale === "zh" ? "上一篇" : "Previous"}</span>
              <p className="mt-1 font-semibold">{detail.previous_article.title}</p>
            </Link>
          ) : <div />}
          {detail.next_article ? (
            <Link className="rounded-lg border border-line p-4 md:text-right" href={`/${locale}/articles/${detail.next_article.slug}`}>
              <span className="text-sm text-zinc-500">{locale === "zh" ? "下一篇" : "Next"}</span>
              <p className="mt-1 font-semibold">{detail.next_article.title}</p>
            </Link>
          ) : <div />}
        </div>

        <ArticleEngagement
          articleId={article.id}
          locale={locale}
          initialViews={article.views_count}
          likes={article.likes_count}
          comments={detail.comments}
        />

        <div className="mt-10">
          <Button asChild variant="outline">
            <Link href={`/${locale}/articles`}>{locale === "zh" ? "回文章列表" : "Back to articles"}</Link>
          </Button>
        </div>
      </article>
    </main>
  );
}

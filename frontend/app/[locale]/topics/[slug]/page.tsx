import type { Metadata } from "next";
import { ArticleCard } from "@/components/article-card";
import { getTopicPage } from "@/lib/api";
import type { Locale } from "@/lib/i18n";

export const revalidate = 60;

export async function generateMetadata({ params }: { params: Promise<{ locale: Locale; slug: string }> }): Promise<Metadata> {
  const { locale, slug } = await params;
  const page = await getTopicPage(locale, slug);
  const title = locale === "zh" ? page.topic.name_zh : page.topic.name_en;
  const description = locale === "zh" ? page.topic.description_zh : page.topic.description_en;
  return {
    title,
    description: description || `${title} - VoltScope`,
    alternates: {
      canonical: `/${locale}/topics/${slug}`,
      languages: { "zh-TW": `/zh/topics/${slug}`, en: `/en/topics/${slug}`, "x-default": `/zh/topics/${slug}` }
    }
  };
}

export default async function TopicPage({ params, searchParams }: { params: Promise<{ locale: Locale; slug: string }>; searchParams: Promise<{ page?: string }> }) {
  const { locale, slug } = await params;
  const { page: pageParam } = await searchParams;
  const pageNumber = pageParam ? Number(pageParam) : 1;
  const data = await getTopicPage(locale, slug, Number.isFinite(pageNumber) && pageNumber > 0 ? pageNumber : 1);
  const title = locale === "zh" ? data.topic.name_zh : data.topic.name_en;
  const description = locale === "zh" ? data.topic.description_zh : data.topic.description_en;
  return (
    <main className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="text-4xl font-bold">{title}</h1>
      {description ? <p className="mt-3 max-w-2xl text-zinc-700">{description}</p> : null}
      <p className="mt-3 text-sm text-zinc-500">
        {locale === "zh" ? "共" : "Total"} {data.total} {locale === "zh" ? "篇文章" : "articles"}
      </p>
      <div className="mt-6 grid gap-5">
        {data.articles.map((article) => (
          <ArticleCard key={article.id} article={article} locale={locale} />
        ))}
      </div>
    </main>
  );
}

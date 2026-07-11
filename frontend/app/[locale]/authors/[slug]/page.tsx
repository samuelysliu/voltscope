import { ArticleCard } from "@/components/article-card";
import { listArticles } from "@/lib/api";
import type { Locale } from "@/lib/i18n";

export default async function AuthorPage({ params }: { params: Promise<{ locale: Locale; slug: string }> }) {
  const { locale, slug } = await params;
  const articles = await listArticles(locale);
  return (
    <main className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="text-4xl font-bold">{slug === "editorial-team" ? "Editorial Team" : slug}</h1>
      <p className="mt-3 max-w-2xl leading-7 text-zinc-700">
        {locale === "zh" ? "電動車、充電與智慧移動科技作者頁。" : "Author profile for electric vehicles, charging, and smart mobility."}
      </p>
      <div className="mt-8 grid gap-5">
        {articles.map((article) => (
          <ArticleCard key={article.id} article={article} locale={locale} />
        ))}
      </div>
    </main>
  );
}

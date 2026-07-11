import { ArticleCard } from "@/components/article-card";
import { Button } from "@/src/components/ui/button";
import { Input } from "@/src/components/ui/input";
import { listArticles } from "@/lib/api";
import type { Locale } from "@/lib/i18n";

export default async function SearchPage({ params, searchParams }: { params: Promise<{ locale: Locale }>; searchParams: Promise<{ q?: string }> }) {
  const { locale } = await params;
  const { q } = await searchParams;
  const articles = q ? await listArticles(locale, undefined, q) : [];
  return (
    <main className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="text-4xl font-bold">{locale === "zh" ? "搜尋" : "Search"}</h1>
      <form className="mt-6 flex max-w-xl gap-2">
        <Input className="min-w-0 flex-1" name="q" defaultValue={q || ""} />
        <Button>{locale === "zh" ? "搜尋" : "Search"}</Button>
      </form>
      <div className="mt-8 grid gap-5">
        {articles.map((article) => (
          <ArticleCard key={article.id} article={article} locale={locale} />
        ))}
        {q && articles.length === 0 ? <p>{locale === "zh" ? "找不到結果。" : "No results found."}</p> : null}
      </div>
    </main>
  );
}

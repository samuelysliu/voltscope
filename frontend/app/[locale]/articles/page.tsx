import Link from "next/link";
import { ArticleCard } from "@/components/article-card";
import { listArticles, listTopics } from "@/lib/api";
import { Button } from "@/src/components/ui/button";
import type { Locale } from "@/lib/i18n";

export default async function ArticlesPage({ params }: { params: Promise<{ locale: Locale }> }) {
  const { locale } = await params;
  const [articles, topics] = await Promise.all([listArticles(locale), listTopics()]);
  return (
    <main className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="text-4xl font-bold">{locale === "zh" ? "文章" : "Articles"}</h1>
      <p className="mt-3 max-w-2xl text-zinc-700">
        {locale === "zh" ? "最新電動車、充電與智慧移動內容。" : "Latest coverage on electric vehicles, charging, and smart mobility."}
      </p>
      <nav className="mt-6 flex flex-wrap gap-3" aria-label={locale === "zh" ? "文章分類" : "Article categories"}>
        {topics.map((topic) => (
          <Button asChild variant="outline" size="sm" key={topic.slug}>
            <Link href={`/${locale}/topics/${topic.slug}`}>{locale === "zh" ? topic.name_zh : topic.name_en}</Link>
          </Button>
        ))}
      </nav>
      <div className="mt-6 grid gap-5">
        {articles.map((article) => (
          <ArticleCard key={article.id} article={article} locale={locale} />
        ))}
      </div>
    </main>
  );
}

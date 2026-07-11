import type { Metadata } from "next";
import Link from "next/link";
import { ArticleCard } from "@/components/article-card";
import { Button } from "@/src/components/ui/button";
import { getHome } from "@/lib/api";
import { type Locale } from "@/lib/i18n";

export const revalidate = 60;

export async function generateMetadata({ params }: { params: Promise<{ locale: Locale }> }): Promise<Metadata> {
  const { locale } = await params;
  return {
    title: locale === "zh" ? "電馳誌 VoltScope｜電動車、充電與智慧移動科技媒體" : "VoltScope",
    description: locale === "zh" ? "追蹤電動車、充電、充電樁、充電優惠與智慧移動科技。" : "Electric Vehicles, Charging & Smart Mobility.",
    alternates: {
      canonical: `/${locale}`,
      languages: { "zh-TW": "/zh", en: "/en", "x-default": "/zh" }
    },
    openGraph: {
      title: locale === "zh" ? "電馳誌 VoltScope" : "VoltScope",
      description: locale === "zh" ? "電動車、充電與智慧移動科技媒體。" : "Electric Vehicles, Charging & Smart Mobility.",
      type: "website"
    }
  };
}

export default async function HomePage({ params }: { params: Promise<{ locale: Locale }> }) {
  const { locale } = await params;
  const home = await getHome(locale);
  const hero = home.featured_articles[0] || home.latest_articles[0];
  const heroImage = hero?.hero_image_url || hero?.thumbnail_url || "https://images.unsplash.com/photo-1593941707882-a5bba14938c7?auto=format&fit=crop&w=1600&q=80";
  return (
    <main>
      <section className="relative overflow-hidden bg-graphite text-white">
        <img className="absolute inset-0 h-full w-full object-cover opacity-35" src={heroImage} alt="" />
        <div className="absolute inset-0 bg-gradient-to-r from-graphite via-graphite/85 to-graphite/20" />
        <div className="relative mx-auto grid max-w-6xl gap-8 px-4 py-16 md:grid-cols-[1.1fr_0.9fr] md:py-20">
          <div className="min-h-[360px] content-center">
            <p className="mb-4 text-sm font-semibold uppercase tracking-normal text-energy">
              {locale === "zh" ? "電動車、充電與智慧移動科技媒體" : "Electric Vehicles, Charging & Smart Mobility"}
            </p>
            <h1 className="max-w-3xl text-4xl font-bold leading-tight md:text-6xl">
              {locale === "zh" ? "電馳誌 VoltScope" : "VoltScope"}
            </h1>
            <p className="mt-5 max-w-2xl text-lg leading-8 text-zinc-100">
              {locale === "zh"
                ? "追蹤電動車、充電樁、充電優惠與智慧移動產業，整理真正值得讀的技術與市場脈動。"
                : "Signals and analysis across electric vehicles, charging networks, charging deals, and smart mobility."}
            </p>
          </div>
          {hero ? (
            <div className="self-end border-l border-white/25 pl-6">
              <p className="text-sm text-zinc-300">{locale === "zh" ? "焦點文章" : "Featured"}</p>
              <h2 className="mt-3 text-2xl font-bold">
                <Link className="transition-colors hover:text-energy" href={`/${locale}/articles/${hero.slug}`}>{hero.title}</Link>
              </h2>
              <p className="mt-3 leading-7 text-zinc-200">{hero.excerpt}</p>
            </div>
          ) : null}
        </div>
      </section>

      {home.featured_articles.length > 1 ? (
        <section className="bg-panel">
          <div className="mx-auto max-w-6xl px-4 py-10">
            <h2 className="mb-5 text-2xl font-bold">{locale === "zh" ? "焦點文章" : "Featured articles"}</h2>
            <div className="grid gap-5">
              {home.featured_articles.slice(0, 3).map((article) => (
                <ArticleCard key={article.id} article={article} locale={locale} />
              ))}
            </div>
          </div>
        </section>
      ) : null}

      <section className="border-y border-line bg-white">
        <div className="mx-auto max-w-6xl px-4 py-8">
          <h2 className="text-xl font-bold">{locale === "zh" ? "依分類瀏覽" : "Browse by category"}</h2>
          <nav className="mt-4 flex flex-wrap gap-3" aria-label={locale === "zh" ? "文章分類" : "Article categories"}>
            {home.topics.map((topic) => (
              <Button asChild variant="outline" key={topic.slug}>
                <Link href={`/${locale}/topics/${topic.slug}`}>{locale === "zh" ? topic.name_zh : topic.name_en}</Link>
              </Button>
            ))}
          </nav>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-10">
        <div className="mb-4 flex items-end justify-between">
          <h2 className="text-2xl font-bold">{locale === "zh" ? "最新文章" : "Latest articles"}</h2>
          <Button asChild variant="link">
            <Link href={`/${locale}/articles`}>{locale === "zh" ? "全部文章" : "All articles"}</Link>
          </Button>
        </div>
        <div className="grid gap-5">
          {home.latest_articles.map((article) => (
            <ArticleCard key={article.id} article={article} locale={locale} />
          ))}
        </div>
      </section>
    </main>
  );
}

import Link from "next/link";
import { Eye, Heart, MessageCircle } from "lucide-react";
import { Badge } from "@/src/components/ui/badge";
import { Card, CardContent } from "@/src/components/ui/card";
import type { ArticleSummary } from "@/lib/api";
import type { Locale } from "@/lib/i18n";

export function ArticleCard({ article, locale }: { article: ArticleSummary; locale: Locale }) {
  return (
    <Card className="rounded-lg border-line shadow-none">
      <CardContent className="p-5">
          <div className="mb-3 flex flex-wrap gap-2">
            {article.topics.map((topic) => (
              <Badge key={topic.slug} variant="secondary">
                <Link href={`/${locale}/topics/${topic.slug}`}>{locale === "zh" ? topic.name_zh : topic.name_en}</Link>
              </Badge>
            ))}
          </div>
          <h2 className="text-2xl font-bold leading-tight">
            <Link href={`/${locale}/articles/${article.slug}`}>{article.title}</Link>
          </h2>
          <p className="mt-3 line-clamp-3 text-base leading-7 text-zinc-700">{article.excerpt}</p>
          <div className="mt-4 flex flex-wrap items-center gap-4 text-sm text-zinc-600">
            <span>{article.published_at ? new Date(article.published_at).toLocaleDateString(locale === "zh" ? "zh-TW" : "en-US") : ""}</span>
            <span className="inline-flex items-center gap-1">
              <Eye size={16} /> {article.views_count}
            </span>
            <span className="inline-flex items-center gap-1">
              <Heart size={16} /> {article.likes_count}
            </span>
            <span className="inline-flex items-center gap-1">
              <MessageCircle size={16} /> {article.comments_count}
            </span>
          </div>
      </CardContent>
    </Card>
  );
}

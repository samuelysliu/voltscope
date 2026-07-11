import { NextResponse } from "next/server";
import { listArticles } from "@/lib/api";
import { isLocale } from "@/lib/i18n";

export async function GET(_request: Request, { params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!isLocale(locale)) return new NextResponse("Not found", { status: 404 });
  const host = process.env.FRONTEND_URL || "http://localhost:3000";
  const articles = await listArticles(locale);
  const items = articles
    .map(
      (article) => `<item><title>${article.title}</title><link>${host}/${locale}/articles/${article.slug}</link><description>${article.excerpt}</description><pubDate>${new Date(article.published_at || article.updated_at).toUTCString()}</pubDate></item>`
    )
    .join("");
  return new NextResponse(`<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>VoltScope</title><link>${host}/${locale}</link><description>VoltScope feed</description>${items}</channel></rss>`, {
    headers: { "content-type": "application/rss+xml; charset=utf-8" }
  });
}

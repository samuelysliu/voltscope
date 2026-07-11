"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Button } from "@/src/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/src/components/ui/card";
import { Input } from "@/src/components/ui/input";
import { Textarea } from "@/src/components/ui/textarea";
import { clearAdminToken, getAdminToken, adminApiBase } from "./auth";
import { RichTextEditor } from "./rich-text-editor";

type Author = { id: string; slug: string; display_name: string };
type Topic = { id: string; slug: string; name_zh: string; name_en: string };
type ArticleItem = {
  id: string;
  status: string;
  title: string;
  slug: string;
  excerpt: string;
  is_featured: boolean;
  show_ads: boolean;
  topics: Topic[];
};
type ArticleDetail = {
  id: string;
  author_id: string;
  status: string;
  is_featured: boolean;
  show_ads: boolean;
  hero_image_url: string | null;
  thumbnail_url: string | null;
  og_image_url: string | null;
  topic_ids: string[];
  translations: TranslationState[];
};
type TranslationState = {
  locale: string;
  title: string;
  slug: string;
  excerpt: string;
  content_html: string;
  content_text: string;
  seo_title?: string | null;
  seo_description?: string | null;
  translation_status?: string;
};

const emptyTranslation = (locale: "zh-TW" | "en"): TranslationState => ({
  locale,
  title: "",
  slug: "",
  excerpt: "",
  content_html: "<p></p>",
  content_text: "",
  seo_title: "",
  seo_description: "",
  translation_status: "draft"
});

function slugify(value: string) {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

function htmlToText(html: string) {
  return html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
}

export function ArticlesManager() {
  const [token, setToken] = useState<string | null>(null);
  const [authors, setAuthors] = useState<Author[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [articles, setArticles] = useState<ArticleItem[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState("draft");
  const [authorId, setAuthorId] = useState("");
  const [isFeatured, setIsFeatured] = useState(false);
  const [showAds, setShowAds] = useState(true);
  const [heroImageUrl, setHeroImageUrl] = useState("");
  const [topicIds, setTopicIds] = useState<string[]>([]);
  const [translations, setTranslations] = useState<TranslationState[]>([emptyTranslation("zh-TW"), emptyTranslation("en")]);
  const apiBase = adminApiBase();

  const previewHref = useMemo(() => {
    const zh = translations.find((item) => item.locale === "zh-TW");
    return zh?.slug ? `/zh/articles/${zh.slug}` : "/zh";
  }, [translations]);

  async function authedFetch(path: string, init: RequestInit = {}) {
    if (!token) throw new Error("missing token");
    return fetch(`${apiBase}${path}`, {
      ...init,
      headers: { ...(init.headers || {}), authorization: `Bearer ${token}` }
    });
  }

  async function loadData(activeToken = token) {
    if (!activeToken) return;
    const headers = { authorization: `Bearer ${activeToken}` };
    const [authorResponse, topicResponse, articleResponse] = await Promise.all([
      fetch(`${apiBase}/admin/authors`, { headers }),
      fetch(`${apiBase}/admin/topics`, { headers }),
      fetch(`${apiBase}/admin/articles`, { headers })
    ]);
    if ([authorResponse, topicResponse, articleResponse].some((response) => response.status === 401 || response.status === 403)) {
      clearAdminToken();
      setToken(null);
      return;
    }
    const nextAuthors = (await authorResponse.json()) as Author[];
    setAuthors(nextAuthors);
    setTopics(await topicResponse.json());
    const articleData = (await articleResponse.json()) as { items: ArticleItem[] };
    setArticles(articleData.items);
    if (!authorId && nextAuthors[0]) setAuthorId(nextAuthors[0].id);
  }

  useEffect(() => {
    const activeToken = getAdminToken();
    setToken(activeToken);
    if (activeToken) void loadData(activeToken);
  }, []);

  function resetForm() {
    setEditingId(null);
    setStatus("draft");
    setIsFeatured(false);
    setShowAds(true);
    setHeroImageUrl("");
    setTopicIds([]);
    setTranslations([emptyTranslation("zh-TW"), emptyTranslation("en")]);
  }

  function updateTranslation(locale: string, patch: Partial<TranslationState>) {
    setTranslations((items) => items.map((item) => (item.locale === locale ? { ...item, ...patch } : item)));
  }

  async function editArticle(articleId: string) {
    const response = await authedFetch(`/admin/articles/${articleId}`);
    if (!response.ok) {
      setMessage("讀取文章失敗。");
      return;
    }
    const data = (await response.json()) as ArticleDetail;
    setEditingId(data.id);
    setStatus(data.status);
    setAuthorId(data.author_id);
    setIsFeatured(data.is_featured);
    setShowAds(data.show_ads);
    setHeroImageUrl(data.hero_image_url || "");
    setTopicIds(data.topic_ids || []);
    const nextTranslations = ["zh-TW", "en"].map((locale) => data.translations.find((item) => item.locale === locale) || emptyTranslation(locale as "zh-TW" | "en"));
    setTranslations(nextTranslations);
  }

  async function uploadImage(file: File): Promise<string> {
    const form = new FormData();
    form.append("file", file);
    const response = await authedFetch("/admin/uploads/image", { method: "POST", body: form });
    if (!response.ok) throw new Error("upload failed");
    const data = (await response.json()) as { url: string };
    return data.url;
  }

  async function uploadHero(file: File | undefined) {
    if (!file) return;
    try {
      setHeroImageUrl(await uploadImage(file));
    } catch {
      setMessage("圖片上傳失敗，請確認格式與大小。");
    }
  }

  async function saveArticle(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    const payload = {
      author_id: authorId || null,
      status,
      is_featured: isFeatured,
      show_ads: showAds,
      hero_image_url: heroImageUrl || null,
      thumbnail_url: heroImageUrl || null,
      og_image_url: heroImageUrl || null,
      topic_ids: topicIds,
      translations: translations.map((item) => ({
        ...item,
        slug: item.slug || slugify(item.title),
        content_text: htmlToText(item.content_html),
        translation_status: status === "published" ? "published" : item.translation_status || "draft"
      }))
    };
    const response = await authedFetch(editingId ? `/admin/articles/${editingId}` : "/admin/articles", {
      method: editingId ? "PUT" : "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      setMessage("儲存文章失敗，請確認 slug 未重複且欄位完整。");
      return;
    }
    setMessage(editingId ? "文章已更新。" : "文章已建立。");
    resetForm();
    await loadData();
  }

  async function articleAction(articleId: string, action: "publish" | "delete") {
    const response = await authedFetch(`/admin/articles/${articleId}${action === "delete" ? "" : `/${action}`}`, {
      method: action === "delete" ? "DELETE" : "POST"
    });
    setMessage(response.ok ? "文章狀態已更新。" : "操作失敗。");
    await loadData();
  }

  if (!token) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-3xl font-bold">{"文章"}</h1>
        <p className="mt-4 text-zinc-700">請先登入後台。</p>
        <Button asChild className="mt-6">
          <Link href="/login">前往登入</Link>
        </Button>
      </main>
    );
  }

  return (
    <main className="mx-auto grid max-w-7xl gap-8 px-4 py-10 xl:grid-cols-[0.9fr_1.1fr]">
      <section>
        <div className="flex items-center justify-between gap-4">
          <h1 className="text-3xl font-bold">文章管理</h1>
          <Button variant="outline" onClick={resetForm}>新增文章</Button>
        </div>
        {message ? <p className="mt-4 rounded border border-line bg-white p-3 text-sm">{message}</p> : null}
        <div className="mt-6 space-y-4">
          {articles.map((article) => (
            <Card className="shadow-none" key={article.id}>
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h2 className="font-bold">{article.title}</h2>
                    <p className="mt-1 line-clamp-2 text-sm text-zinc-600">{article.excerpt}</p>
                    <p className="mt-2 text-xs uppercase text-zinc-500">
                      {article.status} · {article.is_featured ? "featured" : "normal"} · {article.show_ads ? "ads on" : "ads off"}
                    </p>
                  </div>
                  <Link className="shrink-0 rounded bg-graphite px-3 py-2 text-sm text-white" href={`/zh/articles/${article.slug}`}>
                    預覽
                  </Link>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button variant="outline" size="sm" onClick={() => void editArticle(article.id)}>編輯</Button>
                  {article.status !== "published" ? (
                    <Button variant="outline" size="sm" onClick={() => void articleAction(article.id, "publish")}>發布</Button>
                  ) : null}
                  <Button variant="destructive" size="sm" onClick={() => void articleAction(article.id, "delete")}>刪除</Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <Card className="shadow-none">
        <CardHeader>
          <CardTitle>{editingId ? "編輯文章" : "新增文章"}</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-5" onSubmit={saveArticle}>
            <div className="grid gap-3 md:grid-cols-2">
              <label className="text-sm font-semibold">
                狀態
                <select className="mt-1 h-10 w-full rounded-md border border-input bg-background px-3 text-sm" value={status} onChange={(event) => setStatus(event.target.value)}>
                  <option value="draft">draft</option>
                  <option value="published">published</option>
                  <option value="archived">archived</option>
                </select>
              </label>
              <label className="text-sm font-semibold">
                作者
                <select className="mt-1 h-10 w-full rounded-md border border-input bg-background px-3 text-sm" value={authorId} onChange={(event) => setAuthorId(event.target.value)}>
                  {authors.map((author) => (
                    <option key={author.id} value={author.id}>{author.display_name}</option>
                  ))}
                </select>
              </label>
            </div>
            <div className="flex flex-wrap gap-4 text-sm">
              <label className="inline-flex items-center gap-2"><input type="checkbox" checked={isFeatured} onChange={(event) => setIsFeatured(event.target.checked)} /> 焦點文章</label>
              <label className="inline-flex items-center gap-2"><input type="checkbox" checked={showAds} onChange={(event) => setShowAds(event.target.checked)} /> 顯示廣告</label>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-semibold">主圖</label>
              <Input value={heroImageUrl} onChange={(event) => setHeroImageUrl(event.target.value)} placeholder="/uploads/example.webp 或 https://..." />
              <Input type="file" accept="image/png,image/jpeg,image/webp,image/gif" onChange={(event) => void uploadHero(event.target.files?.[0])} />
            </div>
            <div className="space-y-2">
              <p className="text-sm font-semibold">主題標籤</p>
              <div className="flex flex-wrap gap-3">
                {topics.map((topic) => (
                  <label className="inline-flex items-center gap-2 text-sm" key={topic.id}>
                    <input
                      type="checkbox"
                      checked={topicIds.includes(topic.id)}
                      onChange={(event) =>
                        setTopicIds((items) => event.target.checked ? [...items, topic.id] : items.filter((item) => item !== topic.id))
                      }
                    />
                    {topic.name_zh}
                  </label>
                ))}
              </div>
            </div>

            {translations.map((translation) => (
              <Card className="shadow-none" key={translation.locale}>
                <CardHeader>
                  <CardTitle className="text-lg">{translation.locale === "zh-TW" ? "中文內容" : "英文內容"}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Input
                    placeholder="Title"
                    required
                    value={translation.title}
                    onChange={(event) => updateTranslation(translation.locale, { title: event.target.value, slug: translation.slug || slugify(event.target.value) })}
                  />
                  <Input placeholder="Slug" required value={translation.slug} onChange={(event) => updateTranslation(translation.locale, { slug: slugify(event.target.value) })} />
                  <Textarea placeholder="Excerpt" required value={translation.excerpt} onChange={(event) => updateTranslation(translation.locale, { excerpt: event.target.value })} />
                  <Input placeholder="SEO title" value={translation.seo_title || ""} onChange={(event) => updateTranslation(translation.locale, { seo_title: event.target.value })} />
                  <Textarea placeholder="SEO description" value={translation.seo_description || ""} onChange={(event) => updateTranslation(translation.locale, { seo_description: event.target.value })} />
                  <RichTextEditor
                    value={translation.content_html}
                    onChange={(html) => updateTranslation(translation.locale, { content_html: html, content_text: htmlToText(html) })}
                    onUploadImage={uploadImage}
                  />
                </CardContent>
              </Card>
            ))}

            <div className="flex flex-wrap gap-2">
              <Button>{editingId ? "更新文章" : "建立文章"}</Button>
              <Button asChild type="button" variant="outline">
                <a href={previewHref}>預覽前台</a>
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}

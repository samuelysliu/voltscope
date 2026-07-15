"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  FilePlus2,
  Pencil,
  RotateCcw,
  Search,
  Send,
  Trash2,
  X
} from "lucide-react";
import { Button } from "@/src/components/ui/button";
import { Input } from "@/src/components/ui/input";
import { Textarea } from "@/src/components/ui/textarea";
import { adminApiBase, clearAdminToken, getAdminToken } from "./auth";
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
  created_at: string;
  updated_at: string;
  topics: Topic[];
};
type ArticleListResponse = {
  items: ArticleItem[];
  total: number;
  page: number;
  page_size: number;
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
type ArticleFilters = {
  q: string;
  status: string;
  topic: string;
  created_from: string;
  created_to: string;
};
type ApiErrorPayload = {
  error?: {
    code?: string;
    message?: string;
    details?: { locale?: string; slug?: string };
  };
};

const PAGE_SIZE = 20;
const emptyFilters: ArticleFilters = { q: "", status: "", topic: "", created_from: "", created_to: "" };

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

function statusLabel(value: string) {
  const labels: Record<string, string> = { draft: "草稿", published: "已發布", archived: "已封存" };
  return labels[value] || value;
}

function statusClassName(value: string) {
  if (value === "published") return "border-green-200 bg-green-50 text-green-800";
  if (value === "archived") return "border-zinc-300 bg-zinc-100 text-zinc-700";
  return "border-amber-200 bg-amber-50 text-amber-800";
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("zh-TW", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function filterParams(filters: ArticleFilters, page: number) {
  const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
  Object.entries(filters).forEach(([key, value]) => {
    if (value.trim()) params.set(key, value.trim());
  });
  return params;
}

type ArticlesManagerProps = {
  initialArticleId?: string;
  openNewInitially?: boolean;
};

export function ArticlesManager({ initialArticleId, openNewInitially = false }: ArticlesManagerProps = {}) {
  const [isMounted, setIsMounted] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [authors, setAuthors] = useState<Author[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [articles, setArticles] = useState<ArticleItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [filters, setFilters] = useState<ArticleFilters>(emptyFilters);
  const [appliedFilters, setAppliedFilters] = useState<ArticleFilters>(emptyFilters);
  const [message, setMessage] = useState("");
  const [editorError, setEditorError] = useState("");
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [activeLocale, setActiveLocale] = useState<"zh-TW" | "en">("zh-TW");
  const [status, setStatus] = useState("draft");
  const [authorId, setAuthorId] = useState("");
  const [isFeatured, setIsFeatured] = useState(false);
  const [showAds, setShowAds] = useState(true);
  const [heroImageUrl, setHeroImageUrl] = useState("");
  const [topicIds, setTopicIds] = useState<string[]>([]);
  const [translations, setTranslations] = useState<TranslationState[]>([emptyTranslation("zh-TW"), emptyTranslation("en")]);
  const apiBase = adminApiBase();
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const previewHref = useMemo(() => {
    const zh = translations.find((item) => item.locale === "zh-TW");
    return zh?.slug ? `/zh/articles/${zh.slug}` : "/zh";
  }, [translations]);

  function handleUnauthorized(response: Response) {
    if (response.status !== 401 && response.status !== 403) return false;
    clearAdminToken();
    setToken(null);
    setIsEditorOpen(false);
    return true;
  }

  async function authedFetch(path: string, init: RequestInit = {}, activeToken = token) {
    if (!activeToken) throw new Error("missing token");
    return fetch(`${apiBase}${path}`, {
      ...init,
      headers: { ...(init.headers || {}), authorization: `Bearer ${activeToken}` }
    });
  }

  async function loadMetadata(activeToken: string) {
    const headers = { authorization: `Bearer ${activeToken}` };
    const [authorResponse, topicResponse] = await Promise.all([
      fetch(`${apiBase}/admin/authors`, { headers }),
      fetch(`${apiBase}/admin/topics`, { headers })
    ]);
    if ([authorResponse, topicResponse].some(handleUnauthorized)) return;
    if (!authorResponse.ok || !topicResponse.ok) {
      setMessage("無法載入作者或主題資料。");
      return;
    }
    const nextAuthors = (await authorResponse.json()) as Author[];
    setAuthors(nextAuthors);
    setTopics((await topicResponse.json()) as Topic[]);
    setAuthorId((current) => current || nextAuthors[0]?.id || "");
  }

  async function loadArticles(activeToken: string, nextFilters: ArticleFilters, nextPage: number) {
    setIsLoading(true);
    try {
      const response = await fetch(`${apiBase}/admin/articles?${filterParams(nextFilters, nextPage)}`, {
        headers: { authorization: `Bearer ${activeToken}` }
      });
      if (handleUnauthorized(response)) return;
      if (!response.ok) {
        setMessage("無法載入文章列表。");
        return;
      }
      const data = (await response.json()) as ArticleListResponse;
      setArticles(data.items);
      setTotal(data.total);
      setPage(data.page);
    } catch {
      setMessage("無法連線到文章服務。");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    const activeToken = getAdminToken();
    setIsMounted(true);
    setToken(activeToken);
    if (!activeToken) return;

    void Promise.all([loadMetadata(activeToken), loadArticles(activeToken, emptyFilters, 1)]).then(async () => {
      if (initialArticleId) await editArticle(initialArticleId, activeToken);
      else if (openNewInitially) setIsEditorOpen(true);
    });
  }, [initialArticleId, openNewInitially]);

  useEffect(() => {
    if (!isEditorOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !isSaving) setIsEditorOpen(false);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isEditorOpen, isSaving]);

  function resetForm() {
    setEditingId(null);
    setStatus("draft");
    setAuthorId(authors[0]?.id || "");
    setIsFeatured(false);
    setShowAds(true);
    setHeroImageUrl("");
    setTopicIds([]);
    setTranslations([emptyTranslation("zh-TW"), emptyTranslation("en")]);
    setActiveLocale("zh-TW");
    setEditorError("");
  }

  function openNewArticle() {
    resetForm();
    setIsEditorOpen(true);
  }

  function closeEditor() {
    if (isSaving) return;
    setIsEditorOpen(false);
    setEditorError("");
  }

  function updateTranslation(locale: string, patch: Partial<TranslationState>) {
    setTranslations((items) => items.map((item) => (item.locale === locale ? { ...item, ...patch } : item)));
  }

  async function editArticle(articleId: string, activeToken = token) {
    setEditorError("");
    const response = await authedFetch(`/admin/articles/${articleId}`, {}, activeToken);
    if (handleUnauthorized(response)) return;
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
    setTranslations(
      ["zh-TW", "en"].map(
        (locale) => data.translations.find((item) => item.locale === locale) || emptyTranslation(locale as "zh-TW" | "en")
      )
    );
    setActiveLocale("zh-TW");
    setIsEditorOpen(true);
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
      setEditorError("圖片上傳失敗，請確認格式與大小。");
    }
  }

  async function saveArticle(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || isSaving) return;
    const incompleteTranslation = translations.find(
      (item) => !item.title.trim() || !item.slug.trim() || !item.excerpt.trim() || !htmlToText(item.content_html)
    );
    if (incompleteTranslation) {
      setActiveLocale(incompleteTranslation.locale as "zh-TW" | "en");
      setEditorError(`${incompleteTranslation.locale === "zh-TW" ? "中文" : "英文"}內容尚未填寫完整。`);
      return;
    }

    setIsSaving(true);
    setEditorError("");
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
    try {
      const response = await authedFetch(editingId ? `/admin/articles/${editingId}` : "/admin/articles", {
        method: editingId ? "PUT" : "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (handleUnauthorized(response)) return;
      if (!response.ok) {
        const error = (await response.json().catch(() => ({}))) as ApiErrorPayload;
        setEditorError(
          error.error?.code === "ARTICLE_SLUG_CONFLICT"
            ? `Slug「${error.error.details?.slug || "目前輸入值"}」已被其他文章使用，請更換後再儲存。`
            : "儲存文章失敗，請確認欄位完整後再試。"
        );
        return;
      }
      setMessage(editingId ? "文章已更新。" : "文章已建立。");
      setIsEditorOpen(false);
      resetForm();
      await loadArticles(token, appliedFilters, editingId ? page : 1);
    } catch {
      setEditorError("無法連線到文章服務，請稍後再試。");
    } finally {
      setIsSaving(false);
    }
  }

  async function articleAction(articleId: string, action: "publish" | "delete") {
    if (!token) return;
    if (action === "delete" && !window.confirm("確定要刪除這篇文章嗎？")) return;
    const response = await authedFetch(`/admin/articles/${articleId}${action === "delete" ? "" : `/${action}`}`, {
      method: action === "delete" ? "DELETE" : "POST"
    });
    if (handleUnauthorized(response)) return;
    setMessage(response.ok ? (action === "delete" ? "文章已刪除。" : "文章已發布。") : "操作失敗。");
    const nextPage = action === "delete" && articles.length === 1 && page > 1 ? page - 1 : page;
    await loadArticles(token, appliedFilters, nextPage);
  }

  async function applyFilters(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    if (filters.created_from && filters.created_to && filters.created_from > filters.created_to) {
      setMessage("建立日期的起日不能晚於迄日。");
      return;
    }
    setMessage("");
    setAppliedFilters(filters);
    await loadArticles(token, filters, 1);
  }

  async function clearFilters() {
    if (!token) return;
    setFilters(emptyFilters);
    setAppliedFilters(emptyFilters);
    setMessage("");
    await loadArticles(token, emptyFilters, 1);
  }

  async function changePage(nextPage: number) {
    if (!token || nextPage < 1 || nextPage > totalPages || nextPage === page) return;
    await loadArticles(token, appliedFilters, nextPage);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const activeTranslation = translations.find((item) => item.locale === activeLocale) || translations[0];

  if (!isMounted) {
    return (
      <main className="mx-auto max-w-[1500px] px-4 py-8 lg:px-6">
        <h1 className="text-3xl font-bold">文章管理</h1>
        <p className="mt-4 text-sm text-zinc-600">正在載入文章管理...</p>
      </main>
    );
  }

  if (!token) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-3xl font-bold">文章管理</h1>
        <p className="mt-4 text-zinc-700">請先登入後台。</p>
        <Button asChild className="mt-6">
          <Link href="/login">前往登入</Link>
        </Button>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-[1500px] px-4 py-8 lg:px-6">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">文章管理</h1>
          <p className="mt-1 text-sm text-zinc-600">共 {total} 篇文章，每頁顯示 {PAGE_SIZE} 篇</p>
        </div>
        <Button onClick={openNewArticle}>
          <FilePlus2 className="h-4 w-4" />
          新增文章
        </Button>
      </header>

      <form className="mt-6 border-y border-line bg-zinc-50 px-4 py-4" onSubmit={applyFilters}>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[minmax(240px,2fr)_1fr_1fr_1fr_1fr_auto]">
          <label className="text-sm font-semibold">
            關鍵字
            <Input
              className="mt-1 bg-white"
              placeholder="搜尋標題、摘要或文章內容"
              value={filters.q}
              onChange={(event) => setFilters({ ...filters, q: event.target.value })}
            />
          </label>
          <label className="text-sm font-semibold">
            狀態
            <select
              className="mt-1 h-10 w-full rounded-md border border-input bg-white px-3 text-sm"
              value={filters.status}
              onChange={(event) => setFilters({ ...filters, status: event.target.value })}
            >
              <option value="">全部狀態</option>
              <option value="draft">草稿</option>
              <option value="published">已發布</option>
              <option value="archived">已封存</option>
            </select>
          </label>
          <label className="text-sm font-semibold">
            主題標籤
            <select
              className="mt-1 h-10 w-full rounded-md border border-input bg-white px-3 text-sm"
              value={filters.topic}
              onChange={(event) => setFilters({ ...filters, topic: event.target.value })}
            >
              <option value="">全部主題</option>
              {topics.map((topic) => (
                <option key={topic.id} value={topic.slug}>{topic.name_zh}</option>
              ))}
            </select>
          </label>
          <label className="text-sm font-semibold">
            建立日期（起）
            <Input
              className="mt-1 bg-white"
              type="date"
              value={filters.created_from}
              onChange={(event) => setFilters({ ...filters, created_from: event.target.value })}
            />
          </label>
          <label className="text-sm font-semibold">
            建立日期（迄）
            <Input
              className="mt-1 bg-white"
              type="date"
              value={filters.created_to}
              onChange={(event) => setFilters({ ...filters, created_to: event.target.value })}
            />
          </label>
          <div className="flex items-end gap-2">
            <Button className="flex-1" disabled={isLoading}>
              <Search className="h-4 w-4" />
              搜尋
            </Button>
            <Button type="button" size="icon" variant="outline" title="清除篩選" onClick={() => void clearFilters()} disabled={isLoading}>
              <RotateCcw className="h-4 w-4" />
              <span className="sr-only">清除篩選</span>
            </Button>
          </div>
        </div>
      </form>

      {message ? <p className="mt-4 border border-line bg-white p-3 text-sm">{message}</p> : null}

      <section className="mt-5 overflow-x-auto border border-line bg-white" aria-busy={isLoading}>
        <table className="w-full min-w-[1050px] table-fixed text-left text-sm">
          <thead className="border-b border-line bg-zinc-50 text-xs text-zinc-600">
            <tr>
              <th className="w-[38%] px-4 py-3 font-semibold">文章</th>
              <th className="w-[10%] px-3 py-3 font-semibold">狀態</th>
              <th className="w-[18%] px-3 py-3 font-semibold">主題</th>
              <th className="w-[15%] px-3 py-3 font-semibold">建立時間</th>
              <th className="w-[8%] px-3 py-3 font-semibold">設定</th>
              <th className="w-[11%] px-4 py-3 text-right font-semibold">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {articles.map((article) => (
              <tr className="align-top hover:bg-zinc-50" key={article.id}>
                <td className="px-4 py-4">
                  <p className="font-semibold text-zinc-950">{article.title}</p>
                  <p className="mt-1 line-clamp-2 text-xs leading-5 text-zinc-600">{article.excerpt || "沒有摘要"}</p>
                </td>
                <td className="px-3 py-4">
                  <span className={`inline-flex rounded border px-2 py-1 text-xs font-semibold ${statusClassName(article.status)}`}>
                    {statusLabel(article.status)}
                  </span>
                </td>
                <td className="px-3 py-4">
                  <div className="flex flex-wrap gap-1">
                    {article.topics.length ? article.topics.map((topic) => (
                      <span className="rounded border border-zinc-200 bg-zinc-50 px-2 py-1 text-xs" key={topic.id}>{topic.name_zh}</span>
                    )) : <span className="text-xs text-zinc-500">未設定</span>}
                  </div>
                </td>
                <td className="px-3 py-4 text-xs leading-5 text-zinc-600">{formatDateTime(article.created_at)}</td>
                <td className="px-3 py-4 text-xs leading-5 text-zinc-600">
                  <p>{article.is_featured ? "焦點" : "一般"}</p>
                  <p>{article.show_ads ? "顯示廣告" : "不顯示廣告"}</p>
                </td>
                <td className="px-4 py-4">
                  <div className="flex justify-end gap-1">
                    <Button asChild size="icon" variant="ghost" title="預覽文章">
                      <Link href={`/zh/articles/${article.slug}`} target="_blank">
                        <ExternalLink className="h-4 w-4" />
                        <span className="sr-only">預覽文章</span>
                      </Link>
                    </Button>
                    <Button size="icon" variant="ghost" title="編輯文章" onClick={() => void editArticle(article.id)}>
                      <Pencil className="h-4 w-4" />
                      <span className="sr-only">編輯文章</span>
                    </Button>
                    {article.status !== "published" ? (
                      <Button size="icon" variant="ghost" title="發布文章" onClick={() => void articleAction(article.id, "publish")}>
                        <Send className="h-4 w-4" />
                        <span className="sr-only">發布文章</span>
                      </Button>
                    ) : null}
                    <Button size="icon" variant="ghost" className="text-red-700 hover:text-red-800" title="刪除文章" onClick={() => void articleAction(article.id, "delete")}>
                      <Trash2 className="h-4 w-4" />
                      <span className="sr-only">刪除文章</span>
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!articles.length && !isLoading ? <p className="px-4 py-12 text-center text-sm text-zinc-600">找不到符合條件的文章。</p> : null}
        {isLoading ? <p className="px-4 py-12 text-center text-sm text-zinc-600">正在載入文章...</p> : null}
      </section>

      <nav className="mt-4 flex items-center justify-between gap-4" aria-label="文章分頁">
        <p className="text-sm text-zinc-600">第 {page} / {totalPages} 頁</p>
        <div className="flex gap-2">
          <Button type="button" variant="outline" disabled={isLoading || page <= 1} onClick={() => void changePage(page - 1)}>
            <ChevronLeft className="h-4 w-4" />
            上一頁
          </Button>
          <Button type="button" variant="outline" disabled={isLoading || page >= totalPages} onClick={() => void changePage(page + 1)}>
            下一頁
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </nav>

      {isEditorOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 p-2 sm:p-5"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closeEditor();
          }}
        >
          <section
            aria-labelledby="article-editor-title"
            aria-modal="true"
            className="flex max-h-[calc(100vh-1rem)] w-full max-w-6xl flex-col overflow-hidden rounded-md bg-white shadow-2xl sm:max-h-[calc(100vh-2.5rem)]"
            role="dialog"
          >
            <header className="flex shrink-0 items-center justify-between border-b border-line px-4 py-3 sm:px-6">
              <div>
                <h2 className="text-xl font-bold" id="article-editor-title">{editingId ? "編輯文章" : "新增文章"}</h2>
                <p className="mt-1 text-xs text-zinc-600">{editingId ? "修改文章內容與發布設定" : "建立中文與英文版本"}</p>
              </div>
              <Button type="button" size="icon" variant="ghost" title="關閉編輯視窗" onClick={closeEditor} disabled={isSaving}>
                <X className="h-5 w-5" />
                <span className="sr-only">關閉編輯視窗</span>
              </Button>
            </header>

            <form className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6" id="article-editor-form" onSubmit={saveArticle}>
              {editorError ? <p className="mb-5 border border-red-200 bg-red-50 p-3 text-sm text-red-800">{editorError}</p> : null}

              <section className="grid gap-4 border-b border-line pb-6 lg:grid-cols-2">
                <label className="text-sm font-semibold">
                  狀態
                  <select className="mt-1 h-10 w-full rounded-md border border-input bg-background px-3 text-sm" value={status} onChange={(event) => setStatus(event.target.value)}>
                    <option value="draft">草稿</option>
                    <option value="published">已發布</option>
                    <option value="archived">已封存</option>
                  </select>
                </label>
                <label className="text-sm font-semibold">
                  作者
                  <select className="mt-1 h-10 w-full rounded-md border border-input bg-background px-3 text-sm" value={authorId} onChange={(event) => setAuthorId(event.target.value)}>
                    {authors.map((author) => <option key={author.id} value={author.id}>{author.display_name}</option>)}
                  </select>
                </label>
                <div className="flex flex-wrap items-center gap-5 text-sm lg:col-span-2">
                  <label className="inline-flex items-center gap-2">
                    <input type="checkbox" checked={isFeatured} onChange={(event) => setIsFeatured(event.target.checked)} />
                    焦點文章
                  </label>
                  <label className="inline-flex items-center gap-2">
                    <input type="checkbox" checked={showAds} onChange={(event) => setShowAds(event.target.checked)} />
                    顯示廣告
                  </label>
                </div>
                <div className="space-y-2 lg:col-span-2">
                  <label className="text-sm font-semibold" htmlFor="article-hero-url">主圖</label>
                  <div className="grid gap-2 lg:grid-cols-[1fr_280px]">
                    <Input id="article-hero-url" value={heroImageUrl} onChange={(event) => setHeroImageUrl(event.target.value)} placeholder="/uploads/example.webp 或 https://..." />
                    <Input type="file" accept="image/png,image/jpeg,image/webp,image/gif" onChange={(event) => void uploadHero(event.target.files?.[0])} />
                  </div>
                </div>
                <fieldset className="lg:col-span-2">
                  <legend className="text-sm font-semibold">主題標籤</legend>
                  <div className="mt-2 flex max-h-28 flex-wrap gap-x-4 gap-y-2 overflow-y-auto border-y border-line py-3">
                    {topics.map((topic) => (
                      <label className="inline-flex items-center gap-2 text-sm" key={topic.id}>
                        <input
                          type="checkbox"
                          checked={topicIds.includes(topic.id)}
                          onChange={(event) => setTopicIds((items) => event.target.checked ? [...items, topic.id] : items.filter((item) => item !== topic.id))}
                        />
                        {topic.name_zh}
                      </label>
                    ))}
                  </div>
                </fieldset>
              </section>

              <section className="pt-6">
                <div className="mb-4 inline-flex rounded-md border border-input p-1" aria-label="文章語言">
                  {(["zh-TW", "en"] as const).map((locale) => (
                    <button
                      className={`h-8 rounded px-4 text-sm font-semibold ${activeLocale === locale ? "bg-graphite text-white" : "text-zinc-600 hover:bg-zinc-100"}`}
                      key={locale}
                      onClick={() => setActiveLocale(locale)}
                      type="button"
                    >
                      {locale === "zh-TW" ? "中文內容" : "英文內容"}
                    </button>
                  ))}
                </div>
                <div className="space-y-4" key={activeTranslation.locale}>
                  <label className="block text-sm font-semibold">
                    標題
                    <Input
                      className="mt-1"
                      value={activeTranslation.title}
                      onChange={(event) => updateTranslation(activeTranslation.locale, { title: event.target.value, slug: activeTranslation.slug || slugify(event.target.value) })}
                    />
                  </label>
                  <label className="block text-sm font-semibold">
                    Slug
                    <Input className="mt-1" value={activeTranslation.slug} onChange={(event) => updateTranslation(activeTranslation.locale, { slug: slugify(event.target.value) })} />
                  </label>
                  <label className="block text-sm font-semibold">
                    摘要
                    <Textarea className="mt-1" value={activeTranslation.excerpt} onChange={(event) => updateTranslation(activeTranslation.locale, { excerpt: event.target.value })} />
                  </label>
                  <div className="grid gap-4 lg:grid-cols-2">
                    <label className="block text-sm font-semibold">
                      SEO 標題
                      <Input className="mt-1" value={activeTranslation.seo_title || ""} onChange={(event) => updateTranslation(activeTranslation.locale, { seo_title: event.target.value })} />
                    </label>
                    <label className="block text-sm font-semibold">
                      SEO 說明
                      <Textarea className="mt-1 min-h-10" value={activeTranslation.seo_description || ""} onChange={(event) => updateTranslation(activeTranslation.locale, { seo_description: event.target.value })} />
                    </label>
                  </div>
                  <div>
                    <p className="mb-1 text-sm font-semibold">文章內容</p>
                    <RichTextEditor
                      value={activeTranslation.content_html}
                      onChange={(html) => updateTranslation(activeTranslation.locale, { content_html: html, content_text: htmlToText(html) })}
                      onUploadImage={uploadImage}
                    />
                  </div>
                </div>
              </section>
            </form>

            <footer className="flex shrink-0 flex-wrap items-center justify-end gap-2 border-t border-line bg-zinc-50 px-4 py-3 sm:px-6">
              <Button asChild type="button" variant="outline">
                <a href={previewHref} target="_blank" rel="noreferrer">
                  <ExternalLink className="h-4 w-4" />
                  預覽前台
                </a>
              </Button>
              <Button type="button" variant="outline" onClick={closeEditor} disabled={isSaving}>取消</Button>
              <Button type="submit" form="article-editor-form" disabled={isSaving}>
                {isSaving ? "儲存中..." : editingId ? "更新文章" : "建立文章"}
              </Button>
            </footer>
          </section>
        </div>
      ) : null}
    </main>
  );
}

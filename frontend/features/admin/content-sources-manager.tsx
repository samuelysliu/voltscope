"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/src/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/src/components/ui/card";
import { Input } from "@/src/components/ui/input";
import { Textarea } from "@/src/components/ui/textarea";
import { adminApiBase, clearAdminToken, getAdminToken } from "./auth";

type ContentSource = {
  id: string;
  name: string;
  homepage_url: string;
  list_url: string | null;
  rss_url: string | null;
  domain: string;
  source_group: string;
  region: string;
  default_language: string;
  trust_level: string;
  enabled: boolean;
  allowed_topics: string[];
  crawl_method: string;
  quota_role: string;
  allow_auto_publish: boolean;
  requires_review: boolean;
  crawl_frequency_minutes: number;
  max_candidates_per_run: number;
  consecutive_failures: number;
  health_status: string;
};

type CrawlerRun = {
  id: string;
  job_type: string;
  status: string;
  candidates_found: number;
  candidates_accepted: number;
  error_message: string | null;
  created_at: string;
};

type CrawlCandidate = {
  source_url: string;
  title: string;
  excerpt: string | null;
  parser_type: string;
  confidence_score: number | null;
};

type ContentSourceDetail = ContentSource & {
  recent_crawler_runs: CrawlerRun[];
};

type TestCrawlResult = {
  source: ContentSource;
  run: CrawlerRun;
  candidates: CrawlCandidate[];
};

const emptyForm = {
  name: "",
  homepage_url: "https://example.com",
  list_url: "",
  rss_url: "",
  source_group: "international_media",
  region: "international",
  default_language: "en",
  trust_level: "medium",
  enabled: true,
  allowed_topics: "ev,charging",
  crawl_method: "rss",
  quota_role: "international_daily",
  allow_auto_publish: false,
  requires_review: true,
  crawl_frequency_minutes: 360,
  max_candidates_per_run: 10
};

function authHeaders(token: string) {
  return { authorization: `Bearer ${token}` };
}

function statusLabel(value: string) {
  const labels: Record<string, string> = {
    healthy: "正常",
    failed: "失敗",
    degraded: "異常",
    disabled: "停用",
    success: "成功",
    partial_success: "部分成功",
    running: "執行中"
  };
  return labels[value] || value;
}

function groupLabel(value: string) {
  const labels: Record<string, string> = {
    taiwan_media: "台灣媒體",
    international_media: "國際媒體",
    government: "政府",
    local_government: "地方政府",
    charging_operator: "充電營運商",
    official_brand: "官方品牌",
    research_report: "研究報告",
    community_signal: "社群訊號"
  };
  return labels[value] || value;
}

function quotaLabel(value: string) {
  const labels: Record<string, string> = {
    taiwan_daily: "台灣每日配額",
    international_daily: "國際每日配額",
    event_driven: "事件型",
    reference_only: "僅參考"
  };
  return labels[value] || value;
}

function boolLabel(value: boolean) {
  return value ? "是" : "否";
}

export function ContentSourcesManager() {
  const [token, setToken] = useState<string | null>(null);
  const [sources, setSources] = useState<ContentSource[]>([]);
  const [selected, setSelected] = useState<ContentSourceDetail | null>(null);
  const [crawlResult, setCrawlResult] = useState<TestCrawlResult | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [filters, setFilters] = useState({ source_group: "", region: "", enabled: "", quota_role: "" });
  const [form, setForm] = useState({ ...emptyForm });
  const apiBase = adminApiBase();

  function handleUnauthorized(response: Response) {
    if (response.status === 401 || response.status === 403) {
      clearAdminToken();
      setToken(null);
      return true;
    }
    return false;
  }

  function formPayload() {
    return {
      ...form,
      list_url: form.list_url.trim() ? form.list_url.trim() : null,
      rss_url: form.rss_url.trim() ? form.rss_url.trim() : null,
      allowed_topics: form.allowed_topics.split(",").map((item) => item.trim()).filter(Boolean),
      crawl_frequency_minutes: Number(form.crawl_frequency_minutes),
      max_candidates_per_run: Number(form.max_candidates_per_run)
    };
  }

  function sourceToForm(source: ContentSource) {
    setEditingId(source.id);
    setForm({
      name: source.name,
      homepage_url: source.homepage_url,
      list_url: source.list_url || "",
      rss_url: source.rss_url || "",
      source_group: source.source_group,
      region: source.region,
      default_language: source.default_language,
      trust_level: source.trust_level,
      enabled: source.enabled,
      allowed_topics: source.allowed_topics.join(","),
      crawl_method: source.crawl_method,
      quota_role: source.quota_role,
      allow_auto_publish: source.allow_auto_publish,
      requires_review: source.requires_review,
      crawl_frequency_minutes: source.crawl_frequency_minutes,
      max_candidates_per_run: source.max_candidates_per_run
    });
  }

  async function load(activeToken = token) {
    if (!activeToken) return;
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    const response = await fetch(`${apiBase}/admin/content-sources${params.size ? `?${params}` : ""}`, {
      headers: authHeaders(activeToken)
    });
    if (handleUnauthorized(response)) return;
    if (!response.ok) {
      setMessage("無法載入內容來源。");
      return;
    }
    setSources(await response.json());
  }

  async function loadDetail(sourceId: string) {
    if (!token) return;
    const response = await fetch(`${apiBase}/admin/content-sources/${sourceId}`, { headers: authHeaders(token) });
    if (handleUnauthorized(response)) return;
    if (!response.ok) {
      setMessage("無法載入來源詳情。");
      return;
    }
    setSelected(await response.json());
  }

  useEffect(() => {
    const activeToken = getAdminToken();
    setToken(activeToken);
    if (activeToken) void load(activeToken);
  }, []);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    const response = await fetch(`${apiBase}/admin/content-sources${editingId ? `/${editingId}` : ""}`, {
      method: editingId ? "PUT" : "POST",
      headers: { ...authHeaders(token), "content-type": "application/json" },
      body: JSON.stringify(formPayload())
    });
    if (handleUnauthorized(response)) return;
    setMessage(response.ok ? "內容來源已儲存。" : "內容來源儲存失敗。");
    if (response.ok) {
      const saved = (await response.json()) as ContentSource;
      setEditingId(null);
      setForm({ ...emptyForm });
      await load();
      await loadDetail(saved.id);
    }
  }

  async function setSourceEnabled(source: ContentSource, enabled: boolean) {
    if (!token) return;
    const response = await fetch(`${apiBase}/admin/content-sources/${source.id}/${enabled ? "enable" : "disable"}`, {
      method: "POST",
      headers: authHeaders(token)
    });
    if (handleUnauthorized(response)) return;
    setMessage(response.ok ? (enabled ? "來源已啟用。" : "來源已停用。") : "來源狀態更新失敗。");
    await load();
    if (selected?.id === source.id) await loadDetail(source.id);
  }

  async function disableViaDelete(source: ContentSource) {
    if (!token) return;
    const response = await fetch(`${apiBase}/admin/content-sources/${source.id}`, {
      method: "DELETE",
      headers: authHeaders(token)
    });
    if (handleUnauthorized(response)) return;
    setMessage(response.ok ? "來源已停用。" : "來源停用失敗。");
    await load();
    if (selected?.id === source.id) await loadDetail(source.id);
  }

  async function testCrawl(source: ContentSource) {
    if (!token) return;
    setTestingId(source.id);
    setMessage("正在測試抓取...");
    const response = await fetch(`${apiBase}/admin/content-sources/${source.id}/test-crawl`, {
      method: "POST",
      headers: authHeaders(token)
    });
    setTestingId(null);
    if (handleUnauthorized(response)) return;
    if (!response.ok) {
      setMessage("測試抓取失敗。");
      return;
    }
    const result = (await response.json()) as TestCrawlResult;
    setCrawlResult(result);
    setMessage(`測試抓取 ${statusLabel(result.run.status)}：找到 ${result.run.candidates_found} 篇候選。`);
    await load();
    await loadDetail(source.id);
  }

  if (!token) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-3xl font-bold">{"內容來源"}</h1>
        <p className="mt-4 text-zinc-700">{"請先登入管理員帳號。"}</p>
        <Button asChild className="mt-6">
          <Link href="/login">{"前往登入"}</Link>
        </Button>
      </main>
    );
  }

  return (
    <main className="mx-auto grid max-w-6xl gap-8 px-4 py-10 lg:grid-cols-[1fr_420px]">
      <section className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">{"內容來源"}</h1>
          <p className="mt-2 text-sm text-zinc-600">{"管理 AI 擄文會使用的新聞來源，可啟用、停用或測試抓取結果。"}</p>
        </div>
        <form
          className="grid gap-3 rounded border border-line bg-white p-4 md:grid-cols-5"
          onSubmit={(event) => {
            event.preventDefault();
            void load();
          }}
        >
          <select className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={filters.source_group} onChange={(event) => setFilters({ ...filters, source_group: event.target.value })}>
            <option value="">{"全部類別"}</option>
            <option value="taiwan_media">{"台灣媒體"}</option>
            <option value="international_media">{"國際媒體"}</option>
            <option value="government">{"政府"}</option>
            <option value="charging_operator">{"充電營運商"}</option>
          </select>
          <select className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={filters.region} onChange={(event) => setFilters({ ...filters, region: event.target.value })}>
            <option value="">{"全部地區"}</option>
            <option value="taiwan">{"台灣"}</option>
            <option value="international">{"國際"}</option>
          </select>
          <select className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={filters.enabled} onChange={(event) => setFilters({ ...filters, enabled: event.target.value })}>
            <option value="">{"不限狀態"}</option>
            <option value="true">{"啟用"}</option>
            <option value="false">{"停用"}</option>
          </select>
          <select className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={filters.quota_role} onChange={(event) => setFilters({ ...filters, quota_role: event.target.value })}>
            <option value="">{"全部配額"}</option>
            <option value="taiwan_daily">{"台灣每日"}</option>
            <option value="international_daily">{"國際每日"}</option>
            <option value="event_driven">{"事件型"}</option>
            <option value="reference_only">{"僅參考"}</option>
          </select>
          <Button>{"篩選"}</Button>
        </form>
        {message ? <p className="rounded border border-line bg-white p-3 text-sm">{message}</p> : null}

        <div className="space-y-4">
          {sources.map((source) => (
            <Card className="shadow-none" key={source.id}>
              <CardContent className="grid gap-4 p-4 md:grid-cols-[1fr_auto] md:items-start">
                <button className="text-left" onClick={() => void loadDetail(source.id)}>
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-semibold">{source.name}</p>
                    <span className="rounded border border-line px-2 py-0.5 text-xs">{statusLabel(source.health_status)}</span>
                    <span className="rounded border border-line px-2 py-0.5 text-xs">{source.enabled ? "啟用" : "停用"}</span>
                  </div>
                  <p className="mt-1 break-all text-sm text-zinc-600">{source.domain}</p>
                  <p className="mt-2 text-sm text-zinc-700">
                    {groupLabel(source.source_group)} / {source.region === "taiwan" ? "台灣" : "國際"} / {quotaLabel(source.quota_role)}
                  </p>
                  <p className="mt-1 text-xs text-zinc-500">
                    {"主題"} {source.allowed_topics.join(", ") || "-"} / {"連續失敗"} {source.consecutive_failures}
                  </p>
                </button>
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="outline" onClick={() => sourceToForm(source)}>{"編輯"}</Button>
                  <Button size="sm" variant="outline" disabled={testingId === source.id} onClick={() => void testCrawl(source)}>
                    {testingId === source.id ? "測試中" : "測試抓取"}
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => void setSourceEnabled(source, !source.enabled)}>
                    {source.enabled ? "停用" : "啟用"}
                  </Button>
                  <Button size="sm" variant="destructive" onClick={() => void disableViaDelete(source)}>{"停用"}</Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {selected ? (
          <Card className="shadow-none">
            <CardHeader>
              <CardTitle>{selected.name}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-2 text-sm md:grid-cols-3">
                <p><strong>{"首頁"}</strong><br /><a className="break-all underline" href={selected.homepage_url} target="_blank" rel="noreferrer">{selected.homepage_url}</a></p>
                <p><strong>{"列表頁"}</strong><br />{selected.list_url || "-"}</p>
                <p><strong>{"RSS"}</strong><br />{selected.rss_url || "-"}</p>
                <p><strong>{"抓取方式"}</strong><br />{selected.crawl_method} / {selected.crawl_frequency_minutes} {"分鐘"}</p>
                <p><strong>{"需審核"}</strong><br />{boolLabel(selected.requires_review)}</p>
                <p><strong>{"允許自動發布"}</strong><br />{boolLabel(selected.allow_auto_publish)}</p>
              </div>

              {crawlResult?.source.id === selected.id ? (
                <div className="space-y-2">
                  <h2 className="font-semibold">{"最新測試抓取"}</h2>
                  <div className="rounded border border-line p-3 text-sm">
                    <p className="font-semibold">
                      {statusLabel(crawlResult.run.status)} / {"找到"} {crawlResult.run.candidates_found} / {"接受"} {crawlResult.run.candidates_accepted}
                    </p>
                    {crawlResult.run.error_message ? <p className="mt-2 text-red-600">{crawlResult.run.error_message}</p> : null}
                  </div>
                  {crawlResult.candidates.map((candidate) => (
                    <div className="rounded border border-line p-3 text-sm" key={candidate.source_url}>
                      <p className="font-semibold">{candidate.title}</p>
                      <p className="mt-1 text-xs text-zinc-500">
                        {candidate.parser_type} / {"信心分數"} {candidate.confidence_score ?? "-"}
                      </p>
                      <a className="mt-2 block break-all text-xs underline" href={candidate.source_url} target="_blank" rel="noreferrer">
                        {candidate.source_url}
                      </a>
                      {candidate.excerpt ? <p className="mt-2 text-zinc-700">{candidate.excerpt}</p> : null}
                    </div>
                  ))}
                </div>
              ) : null}

              <div className="space-y-2">
                <h2 className="font-semibold">{"最近抓取紀錄"}</h2>
                {selected.recent_crawler_runs.length ? (
                  selected.recent_crawler_runs.map((run) => (
                    <div className="rounded border border-line p-3 text-sm" key={run.id}>
                      <p className="font-semibold">
                        {statusLabel(run.status)} / {run.job_type} / {"找到"} {run.candidates_found}
                      </p>
                      <p className="mt-1 text-xs text-zinc-500">{new Date(run.created_at).toLocaleString()}</p>
                      {run.error_message ? <p className="mt-2 text-red-600">{run.error_message}</p> : null}
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-zinc-600">{"尚無抓取紀錄。"}</p>
                )}
              </div>
            </CardContent>
          </Card>
        ) : null}
      </section>

      <Card className="h-fit shadow-none">
        <CardHeader>
          <CardTitle>{editingId ? "編輯來源" : "新增來源"}</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-3" onSubmit={submit}>
            <Input required placeholder={"來源名稱"} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
            <Input required placeholder={"首頁網址"} value={form.homepage_url} onChange={(event) => setForm({ ...form, homepage_url: event.target.value })} />
            <Input placeholder={"列表頁網址"} value={form.list_url} onChange={(event) => setForm({ ...form, list_url: event.target.value })} />
            <Input placeholder={"RSS 網址"} value={form.rss_url} onChange={(event) => setForm({ ...form, rss_url: event.target.value })} />
            <div className="grid gap-2 sm:grid-cols-2">
              <select className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={form.source_group} onChange={(event) => setForm({ ...form, source_group: event.target.value })}>
                <option value="taiwan_media">{"台灣媒體"}</option>
                <option value="international_media">{"國際媒體"}</option>
                <option value="government">{"政府"}</option>
                <option value="charging_operator">{"充電營運商"}</option>
                <option value="official_brand">{"官方品牌"}</option>
                <option value="research_report">{"研究報告"}</option>
              </select>
              <select className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={form.region} onChange={(event) => setForm({ ...form, region: event.target.value })}>
                <option value="taiwan">{"台灣"}</option>
                <option value="international">{"國際"}</option>
              </select>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <select className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={form.default_language} onChange={(event) => setForm({ ...form, default_language: event.target.value })}>
                <option value="zh">{"中文"}</option>
                <option value="en">{"英文"}</option>
                <option value="mixed">{"混合"}</option>
              </select>
              <select className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={form.trust_level} onChange={(event) => setForm({ ...form, trust_level: event.target.value })}>
                <option value="high">{"高信任"}</option>
                <option value="medium">{"中信任"}</option>
                <option value="low">{"低信任"}</option>
              </select>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <select className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={form.crawl_method} onChange={(event) => setForm({ ...form, crawl_method: event.target.value })}>
                <option value="rss">RSS</option>
                <option value="api">API</option>
                <option value="html">HTML</option>
                <option value="playwright">Playwright</option>
                <option value="hybrid">{"混合"}</option>
              </select>
              <select className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={form.quota_role} onChange={(event) => setForm({ ...form, quota_role: event.target.value })}>
                <option value="taiwan_daily">{"台灣每日"}</option>
                <option value="international_daily">{"國際每日"}</option>
                <option value="event_driven">{"事件型"}</option>
                <option value="reference_only">{"僅參考"}</option>
              </select>
            </div>
            <Textarea placeholder={"允許主題，以逗號分隔"} value={form.allowed_topics} onChange={(event) => setForm({ ...form, allowed_topics: event.target.value })} />
            <div className="grid gap-2 sm:grid-cols-2">
              <Input type="number" min={15} value={form.crawl_frequency_minutes} onChange={(event) => setForm({ ...form, crawl_frequency_minutes: Number(event.target.value) })} />
              <Input type="number" min={1} value={form.max_candidates_per_run} onChange={(event) => setForm({ ...form, max_candidates_per_run: Number(event.target.value) })} />
            </div>
            <div className="grid gap-2 text-sm">
              <label className="flex items-center gap-2"><input type="checkbox" checked={form.enabled} onChange={(event) => setForm({ ...form, enabled: event.target.checked })} /> {"啟用"}</label>
              <label className="flex items-center gap-2"><input type="checkbox" checked={form.allow_auto_publish} onChange={(event) => setForm({ ...form, allow_auto_publish: event.target.checked })} /> {"允許自動發布"}</label>
              <label className="flex items-center gap-2"><input type="checkbox" checked={form.requires_review} onChange={(event) => setForm({ ...form, requires_review: event.target.checked })} /> {"需要人工審核"}</label>
            </div>
            <div className="flex gap-2">
              <Button>{editingId ? "儲存" : "新增"}</Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setEditingId(null);
                  setForm({ ...emptyForm });
                }}
              >
                {"重置"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}

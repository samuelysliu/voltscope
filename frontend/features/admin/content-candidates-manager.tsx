"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/src/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/src/components/ui/card";
import { adminApiBase, clearAdminToken, getAdminToken } from "./auth";

type ContentSource = {
  id: string;
  name: string;
  domain: string;
  quota_role: string;
  enabled: boolean;
};

type ContentCandidate = {
  id: string;
  crawler_run_id: string;
  source_id: string;
  source_name: string | null;
  source_url: string;
  canonical_url: string | null;
  source_title: string;
  source_excerpt: string | null;
  source_author: string | null;
  source_published_at: string | null;
  fetched_at: string;
  relevance_score: number | null;
  novelty_score: number | null;
  quota_category: string;
  decision: string;
  rejection_reason: string | null;
  created_at: string;
};

type CandidateList = {
  items: ContentCandidate[];
  total: number;
  page: number;
  page_size: number;
};

type IngestResult = {
  created_count: number;
  duplicate_count: number;
  rejected_count: number;
  candidates: ContentCandidate[];
};

type GenerationJob = {
  id: string;
  candidate_id: string;
  status: string;
  model_name: string;
  error_message: string | null;
  generated_article_id: string | null;
  quality_gate_result: QualityGateResult | null;
};

type GenerateResult = {
  article_id: string | null;
  article_status: string;
  job: GenerationJob;
};

type QualityGateIssue = {
  code: string;
  severity: string;
  message: string;
};

type QualityGateResult = {
  pass: boolean;
  issues: QualityGateIssue[];
  critical_count: number;
  warning_count: number;
  recommendation: string;
};

type ApiErrorPayload = {
  error?: {
    code?: string;
    message?: string;
    details?: QualityGateResult;
  };
};

function authHeaders(token: string) {
  return { authorization: `Bearer ${token}` };
}

function score(value: number | null) {
  return value === null ? "-" : value.toFixed(2);
}

function formatDateTime(value: string | null) {
  return value ? new Date(value).toLocaleString() : "-";
}

function decisionLabel(value: string) {
  const labels: Record<string, string> = {
    pending: "待處理",
    accepted: "待處理",
    rejected: "已拒絕",
    generated: "已產文",
    published: "已產文",
    failed: "待處理"
  };
  return labels[value] || value;
}

function categoryLabel(value: string) {
  const labels: Record<string, string> = {
    taiwan_media: "台灣媒體",
    international_media: "國際媒體",
    event_driven: "事件型",
    reference_only: "參考來源"
  };
  return labels[value] || value;
}

function severityLabel(value: string) {
  const labels: Record<string, string> = {
    critical: "嚴重",
    warning: "警告",
    info: "提醒"
  };
  return labels[value] || value;
}

function qualityIssueMessage(issue: QualityGateIssue) {
  const messages: Record<string, string> = {
    source_sentence_overlap_too_high: "文章與來源文字過度相似，需重新改寫",
    en_article_short: "英文文章字數不足",
    zh_article_short: "中文文章字數不足",
    missing_source_attribution: "文章缺少原始來源連結",
    insufficient_verified_facts: "可驗證事實不足三項",
    zh_title_not_localized: "中文標題未完成在地化",
    zh_title_contains_source_title: "中文標題過度沿用來源標題",
    generic_article_template_detected: "文章包含制式或編輯流程用語",
    source_url_not_whitelisted: "文章來源不在允許清單內"
  };
  return messages[issue.code] || issue.message;
}

function generationErrorMessage(code?: string, fallback?: string) {
  const messages: Record<string, string> = {
    AI_PROVIDER_NOT_CONFIGURED: "尚未設定 Mistral API 金鑰，無法產生文章。",
    SOURCE_ARTICLE_FETCH_FAILED: "無法讀取原始新聞內容，已停止產文。",
    SOURCE_REDIRECT_NOT_ALLOWED: "來源頁面跳轉至未授權網域，已停止產文。",
    SOURCE_MATERIAL_INSUFFICIENT: "原始新聞的可驗證資料不足，已停止產文。",
    SOURCE_FACTS_INSUFFICIENT: "AI 無法從原文確立足夠事實，已停止產文。",
    AI_ARTICLE_INVALID: "AI 回傳的文章格式不完整，已停止產文。",
    ARTICLE_GENERATION_QUALITY_GATE_FAILED: "文章未通過品質檢查，不會建立草稿。",
    AI_GENERATION_FAILED: "AI 服務呼叫失敗，請稍後重試。"
  };
  return (code && messages[code]) || fallback || "產生文章失敗。";
}

function wait(milliseconds: number) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

export function ContentCandidatesManager() {
  const [token, setToken] = useState<string | null>(null);
  const [sources, setSources] = useState<ContentSource[]>([]);
  const [items, setItems] = useState<ContentCandidate[]>([]);
  const [total, setTotal] = useState(0);
  const [message, setMessage] = useState("");
  const [selectedSourceId, setSelectedSourceId] = useState("");
  const [filters, setFilters] = useState({ decision: "", quota_category: "", source_id: "" });
  const [isRunning, setIsRunning] = useState(false);
  const [generatingId, setGeneratingId] = useState<string | null>(null);
  const [latestArticleId, setLatestArticleId] = useState<string | null>(null);
  const [latestGate, setLatestGate] = useState<QualityGateResult | null>(null);
  const [generationJobs, setGenerationJobs] = useState<Record<string, GenerationJob>>({});
  const apiBase = adminApiBase();

  function handleUnauthorized(response: Response) {
    if (response.status === 401 || response.status === 403) {
      clearAdminToken();
      setToken(null);
      return true;
    }
    return false;
  }

  async function loadSources(activeToken = token) {
    if (!activeToken) return;
    const response = await fetch(`${apiBase}/admin/content-sources?enabled=true`, { headers: authHeaders(activeToken) });
    if (handleUnauthorized(response)) return;
    if (!response.ok) {
      setMessage("無法載入內容來源。");
      return;
    }
    const rows = (await response.json()) as ContentSource[];
    setSources(rows);
    setSelectedSourceId((current) => current || rows[0]?.id || "");
  }

  async function loadCandidates(activeToken = token) {
    if (!activeToken) return;
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    const response = await fetch(`${apiBase}/admin/content-pipeline/candidates${params.size ? `?${params}` : ""}`, {
      headers: authHeaders(activeToken)
    });
    if (handleUnauthorized(response)) return;
    if (!response.ok) {
      setMessage("無法載入候選內容。");
      return;
    }
    const data = (await response.json()) as CandidateList;
    setItems(data.items);
    setTotal(data.total);
  }

  async function loadGenerationJobs(activeToken = token) {
    if (!activeToken) return;
    const response = await fetch(`${apiBase}/admin/content-pipeline/generation-jobs`, { headers: authHeaders(activeToken) });
    if (handleUnauthorized(response) || !response.ok) return;
    const jobs = (await response.json()) as GenerationJob[];
    setGenerationJobs(
      jobs.reduce<Record<string, GenerationJob>>((latest, job) => {
        if (!latest[job.candidate_id]) latest[job.candidate_id] = job;
        return latest;
      }, {})
    );
  }

  useEffect(() => {
    const activeToken = getAdminToken();
    setToken(activeToken);
    if (activeToken) {
      void loadSources(activeToken);
      void loadCandidates(activeToken);
      void loadGenerationJobs(activeToken);
    }
  }, []);

  async function crawlSelectedSource() {
    if (!token || !selectedSourceId) return;
    setIsRunning(true);
    setMessage("正在擄取來源並建立候選內容...");
    const response = await fetch(`${apiBase}/admin/content-sources/${selectedSourceId}/crawl-candidates`, {
      method: "POST",
      headers: authHeaders(token)
    });
    setIsRunning(false);
    if (handleUnauthorized(response)) return;
    if (!response.ok) {
      setMessage("擄取候選內容失敗。");
      return;
    }
    const result = (await response.json()) as IngestResult;
    setMessage(`新增 ${result.created_count} 筆，重複 ${result.duplicate_count} 筆，排除 ${result.rejected_count} 筆`);
    await loadCandidates();
  }

  async function rejectCandidate(candidate: ContentCandidate) {
    if (!token) return;
    const response = await fetch(`${apiBase}/admin/content-pipeline/candidates/${candidate.id}/reject`, {
      method: "POST",
      headers: { ...authHeaders(token), "content-type": "application/json" },
      body: JSON.stringify({ reason: "管理員判定不適合產文" })
    });
    if (handleUnauthorized(response)) return;
    if (!response.ok) {
      const payload = (await response.json().catch(() => ({}))) as ApiErrorPayload;
      setMessage(payload.error?.message || "更新候選內容失敗。");
      return;
    }
    if (!filters.decision) {
      setItems((current) => current.filter((item) => item.id !== candidate.id));
      setTotal((current) => Math.max(0, current - 1));
    }
    setMessage(candidate.decision === "generated" || candidate.decision === "published" ? "候選內容已拒絕，關聯文章已移除。" : "候選內容已拒絕。");
    await loadCandidates();
  }

  async function generateArticle(candidate: ContentCandidate) {
    if (!token) return;
    setGeneratingId(candidate.id);
    setLatestArticleId(null);
    setLatestGate(null);
    setMessage("正在產生文章...");
    try {
      const response = await fetch(`${apiBase}/admin/content-pipeline/candidates/${candidate.id}/generate`, {
        method: "POST",
        headers: authHeaders(token)
      });
      if (handleUnauthorized(response)) return;
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as ApiErrorPayload;
        if (payload.error?.details?.issues) setLatestGate(payload.error.details);
        setMessage(generationErrorMessage(payload.error?.code, payload.error?.message));
        return;
      }

      const result = (await response.json()) as GenerateResult;
      setMessage("已排入背景產文，可繼續瀏覽後台。");
      for (let attempt = 0; attempt < 180; attempt += 1) {
        await wait(3000);
        let jobResponse: Response;
        try {
          jobResponse = await fetch(`${apiBase}/admin/content-pipeline/generation-jobs/${result.job.id}`, {
            headers: authHeaders(token)
          });
        } catch {
          if (attempt < 179) continue;
          setMessage("無法取得產文進度，請重新整理頁面查看結果。");
          return;
        }
        if (handleUnauthorized(jobResponse)) return;
        if (!jobResponse.ok) continue;

        const job = (await jobResponse.json()) as GenerationJob;
        if (job.status === "success") {
          setLatestArticleId(job.generated_article_id);
          setLatestGate(job.quality_gate_result);
          setMessage(`文章已產生，模型 ${job.model_name}`);
          await loadCandidates();
          await loadGenerationJobs();
          return;
        }
        if (job.status === "failed") {
          setLatestGate(job.quality_gate_result);
          setMessage(job.quality_gate_result ? "文章未通過品質檢查，請查看下方原因。" : job.error_message || "產生文章失敗。");
          await loadCandidates();
          await loadGenerationJobs();
          return;
        }
        setMessage("正在背景產生中英文章...");
      }
      setMessage("產文仍在背景執行，請稍後重新整理頁面。");
    } catch {
      setMessage("無法連線到產文服務，請稍後重試。");
    } finally {
      setGeneratingId(null);
    }
  }

  if (!token) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-3xl font-bold">{"候選內容"}</h1>
        <p className="mt-4 text-zinc-700">{"請先登入管理員帳號。"}</p>
        <Button asChild className="mt-6">
          <Link href="/login">{"前往登入"}</Link>
        </Button>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-10">
      <section className="space-y-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">{"候選內容"}</h1>
            <p className="mt-2 text-sm text-zinc-600">{"審核擄取回來的候選資料，確認後再產生文章。"}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <select className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={selectedSourceId} onChange={(event) => setSelectedSourceId(event.target.value)}>
              {sources.map((source) => <option key={source.id} value={source.id}>{source.name}</option>)}
            </select>
            <Button disabled={isRunning || !selectedSourceId} onClick={() => void crawlSelectedSource()}>
              {isRunning ? "擷取中" : "擷取候選內容"}
            </Button>
          </div>
        </div>

        <form
          className="grid gap-3 rounded border border-line bg-white p-4 md:grid-cols-4"
          onSubmit={(event) => {
            event.preventDefault();
            void loadCandidates();
          }}
        >
          <select className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={filters.source_id} onChange={(event) => setFilters({ ...filters, source_id: event.target.value })}>
            <option value="">{"全部來源"}</option>
            {sources.map((source) => (
              <option key={source.id} value={source.id}>
                {source.name}
              </option>
            ))}
          </select>
          <select className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={filters.decision} onChange={(event) => setFilters({ ...filters, decision: event.target.value })}>
            <option value="">{"全部狀態"}</option>
            <option value="pending">{decisionLabel("pending")}</option>
            <option value="generated">{decisionLabel("generated")}</option>
            <option value="rejected">{decisionLabel("rejected")}</option>
          </select>
          <select className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={filters.quota_category} onChange={(event) => setFilters({ ...filters, quota_category: event.target.value })}>
            <option value="">{"全部配額"}</option>
            <option value="taiwan_media">{categoryLabel("taiwan_media")}</option>
            <option value="international_media">{categoryLabel("international_media")}</option>
            <option value="event_driven">{categoryLabel("event_driven")}</option>
            <option value="reference_only">{categoryLabel("reference_only")}</option>
          </select>
          <Button>{"篩選"}</Button>
        </form>

        {message ? (
          <p className="rounded border border-line bg-white p-3 text-sm">
            {message}
            {latestArticleId ? (
              <>
                {" "}
                <Link className="underline" href={`/admin/articles/${latestArticleId}/edit`}>
                  {"編輯文章"}
                </Link>
              </>
            ) : null}
          </p>
        ) : null}
        <p className="text-sm text-zinc-600">{total} {"筆候選內容"}</p>
        {latestGate ? (
          <div className="rounded border border-line bg-white p-3 text-sm">
            <p className="font-semibold">
              {"品質檢查"} {latestGate.pass ? "通過" : "未通過"} / {"嚴重"} {latestGate.critical_count} / {"警告"} {latestGate.warning_count}
            </p>
            {latestGate.issues.length ? (
              <ul className="mt-2 space-y-1">
                {latestGate.issues.map((item, index) => (
                  <li key={`${item.code}-${index}`}>
                    {severityLabel(item.severity)}: {qualityIssueMessage(item)}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}

        <div className="space-y-4">
          {items.map((candidate) => (
            <Card className="shadow-none" key={candidate.id}>
              <CardContent className="space-y-3 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold">{candidate.source_title}</p>
                    <p className="mt-1 text-xs text-zinc-500">
                      {candidate.source_name || candidate.source_id} / {categoryLabel(candidate.quota_category)} / {decisionLabel(candidate.decision)}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant="outline" disabled={generatingId === candidate.id || candidate.decision === "rejected" || candidate.decision === "generated" || candidate.decision === "published"} onClick={() => void generateArticle(candidate)}>
                      {generatingId === candidate.id ? "產生中" : "產生文章"}
                    </Button>
                    <Button size="sm" variant="destructive" disabled={generatingId === candidate.id} onClick={() => void rejectCandidate(candidate)}>
                      {"拒絕"}
                    </Button>
                  </div>
                </div>
                <div className="grid gap-2 text-sm sm:grid-cols-3">
                  <p><strong>{"相關度"}</strong><br />{score(candidate.relevance_score)}</p>
                  <p><strong>{"新鮮度"}</strong><br />{score(candidate.novelty_score)}</p>
                  <p><strong>{"擄取時間"}</strong><br />{formatDateTime(candidate.fetched_at)}</p>
                </div>
                <a className="block break-all text-sm underline" href={candidate.source_url} target="_blank" rel="noreferrer">
                  {candidate.source_url}
                </a>
                {candidate.source_excerpt ? <p className="text-sm text-zinc-700">{candidate.source_excerpt}</p> : null}
                {generationJobs[candidate.id]?.quality_gate_result?.issues.length ? (
                  <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800">
                    <p className="font-semibold">未通過品質檢查</p>
                    <ul className="mt-1 space-y-1">
                      {generationJobs[candidate.id].quality_gate_result?.issues.map((issue, index) => (
                        <li key={`${issue.code}-${index}`}>{qualityIssueMessage(issue)}</li>
                      ))}
                    </ul>
                  </div>
                ) : candidate.rejection_reason ? (
                  <p className="text-sm text-red-600">
                    {candidate.rejection_reason === "failed_quality_gate"
                      ? "未通過品質檢查"
                      : candidate.rejection_reason === "generation_interrupted"
                        ? "產文因服務重啟而中斷，請重新執行"
                        : candidate.rejection_reason}
                  </p>
                ) : null}
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

    </main>
  );
}

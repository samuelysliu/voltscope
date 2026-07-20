"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/src/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/src/components/ui/card";
import { Input } from "@/src/components/ui/input";
import { adminApiBase, clearAdminToken, getAdminToken } from "./auth";

type DailyReport = {
  id: string;
  report_date: string;
  status: string;
  total_published: number;
  total_ready_for_review: number;
  taiwan_media_count: number;
  international_count: number;
  event_driven_count: number;
  quota_met: boolean;
  quota_detail: Record<string, unknown>;
  failed_sources: unknown[] | null;
  degraded_sources: unknown[] | null;
  message: string | null;
  updated_at: string;
};

type ReportList = {
  items: DailyReport[];
  total: number;
};

type RunResult = {
  report: DailyReport;
  generated_article_ids: string[];
  selected_candidate_ids: string[];
  skipped: boolean;
};

type RunAccepted = {
  run_id: string;
  report_date: string;
  status: "queued" | "running";
  already_running: boolean;
};

type ContentSource = {
  id: string;
  name: string;
  domain: string;
  enabled: boolean;
};

function authHeaders(token: string) {
  return { authorization: `Bearer ${token}` };
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    success: "成功",
    warning: "警示",
    failed: "失敗",
    running: "執行中"
  };
  return labels[status] || status;
}

function quotaLabel(value: boolean) {
  return value ? "已達成" : "未達成";
}

function reportMetric(report: DailyReport, key: string) {
  const value = report.quota_detail[key];
  return typeof value === "number" ? value : 0;
}

function reportIds(report: DailyReport, key: string) {
  const value = report.quota_detail[key];
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function delay(milliseconds: number) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

export function ContentPipelineDashboard() {
  const [token, setToken] = useState<string | null>(null);
  const [reports, setReports] = useState<DailyReport[]>([]);
  const [message, setMessage] = useState("");
  const [runDate, setRunDate] = useState(new Date().toISOString().slice(0, 10));
  const [sources, setSources] = useState<ContentSource[]>([]);
  const [sourceId, setSourceId] = useState("");
  const [articleCount, setArticleCount] = useState(5);
  const [force, setForce] = useState(false);
  const [dryRun, setDryRun] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [lastRun, setLastRun] = useState<RunResult | null>(null);
  const apiBase = adminApiBase();

  function handleUnauthorized(response: Response) {
    if (response.status === 401 || response.status === 403) {
      clearAdminToken();
      setToken(null);
      return true;
    }
    return false;
  }

  async function loadReports(activeToken = token) {
    if (!activeToken) return;
    const response = await fetch(`${apiBase}/admin/content-pipeline/reports`, { headers: authHeaders(activeToken) });
    if (handleUnauthorized(response)) return;
    if (!response.ok) {
      setMessage("無法載入執行紀錄。");
      return;
    }
    const data = (await response.json()) as ReportList;
    setReports(data.items);
  }

  async function loadSources(activeToken = token) {
    if (!activeToken) return;
    const response = await fetch(`${apiBase}/admin/content-sources?enabled=true`, { headers: authHeaders(activeToken) });
    if (handleUnauthorized(response)) return;
    if (!response.ok) {
      setMessage("無法載入內容來源。");
      return;
    }
    setSources((await response.json()) as ContentSource[]);
  }

  useEffect(() => {
    const activeToken = getAdminToken();
    setToken(activeToken);
    if (activeToken) {
      void loadReports(activeToken);
      void loadSources(activeToken);
    }
  }, []);

  async function runPipeline() {
    if (!token) return;
    setIsRunning(true);
    const selectedSource = sources.find((source) => source.id === sourceId);
    setMessage(`正在從${selectedSource ? `「${selectedSource.name}」` : "所有啟用來源"}撈取文章，目標 ${articleCount} 篇...`);
    try {
      const response = await fetch(`${apiBase}/admin/content-pipeline/run-now`, {
        method: "POST",
        headers: { ...authHeaders(token), "content-type": "application/json" },
        body: JSON.stringify({
          date: runDate,
          force,
          dry_run: dryRun,
          source_id: sourceId || null,
          article_count: articleCount
        })
      });
      if (handleUnauthorized(response)) return;
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        setMessage(error.error?.message || "執行 AI 撈文失敗。");
        return;
      }
      const accepted = (await response.json()) as RunAccepted;
      setMessage(accepted.already_running ? "此日期已有任務執行中，正在追蹤進度..." : "AI 撈文已排入背景執行，正在追蹤進度...");

      for (let attempt = 0; attempt < 360; attempt += 1) {
        await delay(5000);
        const reportResponse = await fetch(`${apiBase}/admin/content-pipeline/reports/${accepted.report_date}`, {
          headers: authHeaders(token)
        });
        if (handleUnauthorized(reportResponse)) return;
        if (!reportResponse.ok) continue;
        const report = (await reportResponse.json()) as DailyReport;
        const reportRunId = report.quota_detail.manual_run_id;
        if (report.status === "running" || (typeof reportRunId === "string" && reportRunId !== accepted.run_id)) continue;

        const result: RunResult = {
          report,
          generated_article_ids: reportIds(report, "generated_article_ids"),
          selected_candidate_ids: reportIds(report, "attempted_candidate_ids"),
          skipped: report.quota_detail.skipped === "lock_exists"
        };
        setLastRun(result);
        const failedCount = reportMetric(report, "generation_failure_total");
        setMessage(
          report.status === "failed"
            ? `執行失敗：嘗試 ${result.selected_candidate_ids.length} 篇，失敗 ${failedCount} 篇。請查看下方執行明細。`
            : result.skipped
              ? "已跳過：目前有另一個執行中的任務。"
              : `執行完成：嘗試 ${result.selected_candidate_ids.length} 篇，產生 ${result.generated_article_ids.length} 篇草稿。`
        );
        await loadReports(token);
        return;
      }
      setMessage("AI 撈文仍在背景執行，請稍後重新整理查看最新報表。");
    } catch {
      setMessage("無法連線至 AI 撈文服務，請確認 Backend 狀態後重試。");
    } finally {
      setIsRunning(false);
    }
  }

  if (!token) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-3xl font-bold">{"AI 撈文"}</h1>
        <p className="mt-4 text-zinc-700">{"請先登入管理員帳號。"}</p>
        <Button asChild className="mt-6">
          <Link href="/login">{"前往登入"}</Link>
        </Button>
      </main>
    );
  }

  return (
    <main className="mx-auto grid max-w-6xl gap-8 px-4 py-10 lg:grid-cols-[360px_1fr]">
      <aside className="space-y-6">
        <Card className="shadow-none">
          <CardHeader>
            <CardTitle>{"手動執行 AI 撈文"}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input type="date" value={runDate} onChange={(event) => setRunDate(event.target.value)} />
            <label className="block space-y-1 text-sm">
              <span>{"內容來源"}</span>
              <select
                className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={sourceId}
                onChange={(event) => setSourceId(event.target.value)}
              >
                <option value="">{"所有啟用來源"}</option>
                {sources.map((source) => (
                  <option key={source.id} value={source.id}>{`${source.name} (${source.domain})`}</option>
                ))}
              </select>
            </label>
            <label className="block space-y-1 text-sm">
              <span>{"文章數量（1 至 20）"}</span>
              <Input
                type="number"
                min={1}
                max={20}
                required
                value={articleCount}
                onChange={(event) => setArticleCount(Math.min(20, Math.max(1, Number(event.target.value) || 1)))}
              />
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={dryRun} onChange={(event) => setDryRun(event.target.checked)} />
              {"只測試，不產生草稿"}
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={force} onChange={(event) => setForce(event.target.checked)} />
              {"強制執行，忽略今日鎖定"}
            </label>
            <Button className="w-full" disabled={isRunning} onClick={() => void runPipeline()}>
              {isRunning ? "執行中" : "立即執行"}
            </Button>
          </CardContent>
        </Card>

        {lastRun ? (
          <Card className="shadow-none">
            <CardHeader>
              <CardTitle>{"本次執行結果"}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <p><strong>{"狀態"}</strong><br />{statusLabel(lastRun.report.status)}</p>
              <p><strong>{"配額"}</strong><br />{quotaLabel(lastRun.report.quota_met)}</p>
              <p><strong>{"選入候選"}</strong><br />{lastRun.selected_candidate_ids.length}</p>
              <p><strong>{"產生草稿"}</strong><br />{lastRun.generated_article_ids.length}</p>
            </CardContent>
          </Card>
        ) : null}
      </aside>

      <section className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">{"AI 撈文"}</h1>
          <p className="mt-2 text-sm text-zinc-600">
            {"這是唯一的手動撈文入口：系統會依照選擇的內容來源與文章數量撈取候選文章，並用 AI 產生草稿供編輯審核。"}
          </p>
        </div>
        {message ? <p className="rounded border border-line bg-white p-3 text-sm">{message}</p> : null}

        <div className="space-y-4">
          {reports.map((report) => (
            <Card className="shadow-none" key={report.id}>
              <CardContent className="space-y-3 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold">{report.report_date}</p>
                    <p className="mt-1 text-sm text-zinc-600">{report.message || "-"}</p>
                  </div>
                  <span className="rounded border border-line px-2 py-1 text-xs">{statusLabel(report.status)}</span>
                </div>
                <div className="grid gap-2 text-sm md:grid-cols-7">
                  <p><strong>{"已發布"}</strong><br />{report.total_published}</p>
                  <p><strong>{"待審草稿"}</strong><br />{report.total_ready_for_review}</p>
                  <p><strong>{"成功／目標"}</strong><br />{reportMetric(report, "successful_total")} / {reportMetric(report, "daily_min_articles")}</p>
                  <p><strong>{"嘗試／失敗"}</strong><br />{reportMetric(report, "attempted_total")} / {reportMetric(report, "generation_failure_total")}</p>
                  <p><strong>{"台灣來源"}</strong><br />{report.taiwan_media_count}</p>
                  <p><strong>{"國際來源"}</strong><br />{report.international_count}</p>
                  <p><strong>{"配額"}</strong><br />{quotaLabel(report.quota_met)}</p>
                </div>
                {report.failed_sources?.length ? <p className="text-sm text-red-600">{"失敗來源："}{report.failed_sources.length}</p> : null}
                {report.degraded_sources?.length ? <p className="text-sm text-amber-700">{"異常來源："}{report.degraded_sources.length}</p> : null}
                <pre className="max-h-56 overflow-auto rounded bg-panel p-2 text-xs">{JSON.stringify(report.quota_detail, null, 2)}</pre>
              </CardContent>
            </Card>
          ))}
          {reports.length === 0 ? <p className="rounded border border-line bg-white p-4 text-sm text-zinc-600">{"尚無執行紀錄。"}</p> : null}
        </div>
      </section>
    </main>
  );
}

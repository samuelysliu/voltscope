"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/src/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/src/components/ui/card";
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
  failed_sources: Record<string, unknown>[] | null;
  degraded_sources: Record<string, unknown>[] | null;
  message: string | null;
  created_at: string;
  updated_at: string;
};

type ContentCandidate = {
  id: string;
  source_title: string;
  source_name: string | null;
  quota_category: string;
  relevance_score: number | null;
};

type SourceHealth = {
  id: string;
  name: string;
  domain: string;
  enabled: boolean;
  quota_role: string;
  health_status: string;
  consecutive_failures: number;
  last_success_at: string | null;
  last_failure_at: string | null;
};

type FailedQualityGate = {
  job_id: string;
  source_id: string;
  source_name: string | null;
  source_title: string;
  status: string;
  error_message: string | null;
  quality_gate_result: {
    issues?: { code: string; severity: string; message: string }[];
    recommendation?: string;
  };
  created_at: string;
};

type Monitoring = {
  latest_report: DailyReport | null;
  quota_preview: {
    candidates: ContentCandidate[];
    taiwan_count: number;
    international_count: number;
    total_count: number;
  };
  source_health: SourceHealth[];
  failed_quality_gates: FailedQualityGate[];
  report_status_counts: Record<string, number>;
  candidate_decision_counts: Record<string, number>;
};

type ReportList = {
  items: DailyReport[];
  total: number;
};

function authHeaders(token: string) {
  return { authorization: `Bearer ${token}` };
}

function formatDateTime(value: string | null) {
  return value ? new Date(value).toLocaleString() : "-";
}

function score(value: number | null) {
  return value === null ? "-" : value.toFixed(2);
}

function statusLabel(value: string | undefined) {
  const labels: Record<string, string> = {
    success: "成功",
    warning: "警示",
    failed: "失敗",
    running: "執行中",
    completed: "已完成",
    pending: "待處理",
    generated: "已產生"
  };
  return value ? labels[value] || value : "-";
}

function quotaLabel(value: boolean | undefined) {
  if (value === undefined) return "-";
  return value ? "已達成" : "未達成";
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

export function ContentReportsManager() {
  const [token, setToken] = useState<string | null>(null);
  const [monitoring, setMonitoring] = useState<Monitoring | null>(null);
  const [reports, setReports] = useState<DailyReport[]>([]);
  const [total, setTotal] = useState(0);
  const [message, setMessage] = useState("");
  const apiBase = adminApiBase();

  function handleUnauthorized(response: Response) {
    if (response.status === 401 || response.status === 403) {
      clearAdminToken();
      setToken(null);
      return true;
    }
    return false;
  }

  async function load(activeToken = token) {
    if (!activeToken) return;
    const [monitoringResponse, reportsResponse] = await Promise.all([
      fetch(`${apiBase}/admin/content-pipeline/monitoring`, { headers: authHeaders(activeToken) }),
      fetch(`${apiBase}/admin/content-pipeline/reports`, { headers: authHeaders(activeToken) })
    ]);
    if (handleUnauthorized(monitoringResponse) || handleUnauthorized(reportsResponse)) return;
    if (!monitoringResponse.ok || !reportsResponse.ok) {
      setMessage("無法載入內容報表。");
      return;
    }
    setMonitoring(await monitoringResponse.json());
    const reportList = (await reportsResponse.json()) as ReportList;
    setReports(reportList.items);
    setTotal(reportList.total);
  }

  useEffect(() => {
    const activeToken = getAdminToken();
    setToken(activeToken);
    if (activeToken) void load(activeToken);
  }, []);

  if (!token) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-3xl font-bold">{"內容報表"}</h1>
        <p className="mt-4 text-zinc-700">{"請先登入管理員帳號。"}</p>
        <Button asChild className="mt-6">
          <Link href="/login">{"前往登入"}</Link>
        </Button>
      </main>
    );
  }

  const latest = monitoring?.latest_report;
  const unhealthySources = monitoring?.source_health.filter((source) => source.health_status !== "healthy" && source.health_status !== "disabled") || [];

  return (
    <main className="mx-auto max-w-6xl space-y-8 px-4 py-10">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold">{"內容報表"}</h1>
          <p className="mt-2 text-sm text-zinc-600">{"查看 AI 擄文的執行狀態、每日配額、來源健康與品質檢查結果。"}</p>
        </div>
        <Button variant="outline" onClick={() => void load()}>
          {"重新載入"}
        </Button>
      </div>

      {message ? <p className="rounded border border-line bg-white p-3 text-sm">{message}</p> : null}

      <Card className="shadow-none">
        <CardHeader>
          <CardTitle>{"這頁用來做什麼"}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 text-sm text-zinc-700 md:grid-cols-2">
          <p>
            <strong>{"確認每日產文是否達標"}</strong><br />
            {"比對已發布、待審草稿與配額狀態，判斷 AI 擄文今天是否已經滿足預期數量。"}
          </p>
          <p>
            <strong>{"找出失敗的來源與原因"}</strong><br />
            {"當來源連續失敗或品質檢查未通過時，可以從這裡判斷需要修正來源設定、重跑 AI 擄文，或改由人工審稿。"}
          </p>
          <p>
            <strong>{"評估候選內容的可用性"}</strong><br />
            {"配額預覽顯示目前可被產文的候選資料，數量太少代表可能需要補來源或放寬篩選條件。"}
          </p>
          <p>
            <strong>{"作為上線前的運維檢查"}</strong><br />
            {"若最新報表為成功、來源健康、品質檢查失敗數為 0，代表內容管線目前沒有明顯異常。"}
          </p>
        </CardContent>
      </Card>

      <section className="grid gap-4 md:grid-cols-4">
        {[
          ["最新狀態", statusLabel(latest?.status)],
          ["每日配額", quotaLabel(latest?.quota_met)],
          ["異常來源", unhealthySources.length],
          ["品質檢查失敗", monitoring?.failed_quality_gates.length || 0]
        ].map(([label, value]) => (
          <Card className="shadow-none" key={String(label)}>
            <CardHeader>
              <CardTitle className="text-sm text-zinc-500">{label}</CardTitle>
            </CardHeader>
            <CardContent className="text-2xl font-bold">{value}</CardContent>
          </Card>
        ))}
      </section>

      <section className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <div className="space-y-6">
          <Card className="shadow-none">
            <CardHeader>
              <CardTitle>{"每日配額"}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 text-sm md:grid-cols-5">
                <p><strong>{"報表日期"}</strong><br />{latest?.report_date || "-"}</p>
                <p><strong>{"已發布"}</strong><br />{latest?.total_published ?? 0}</p>
                <p><strong>{"待審草稿"}</strong><br />{latest?.total_ready_for_review ?? 0}</p>
                <p><strong>{"台灣來源"}</strong><br />{latest?.taiwan_media_count ?? 0}</p>
                <p><strong>{"國際來源"}</strong><br />{latest?.international_count ?? 0}</p>
              </div>
              <div className="grid gap-3 md:grid-cols-3">
                <p className="rounded border border-line p-3 text-sm"><strong>{monitoring?.quota_preview.total_count ?? 0}</strong><br />{"已選入候選"}</p>
                <p className="rounded border border-line p-3 text-sm"><strong>{monitoring?.quota_preview.taiwan_count ?? 0}</strong><br />{"台灣"}</p>
                <p className="rounded border border-line p-3 text-sm"><strong>{monitoring?.quota_preview.international_count ?? 0}</strong><br />{"國際"}</p>
              </div>
              {monitoring?.quota_preview.candidates.map((candidate) => (
                <div className="rounded border border-line p-3 text-sm" key={candidate.id}>
                  <p className="font-semibold">{candidate.source_title}</p>
                  <p className="mt-1 text-xs text-zinc-500">
                    {candidate.source_name || "-"} / {categoryLabel(candidate.quota_category)} / {"相關度"} {score(candidate.relevance_score)}
                  </p>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className="shadow-none">
            <CardHeader>
              <CardTitle>{"品質檢查失敗"}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {monitoring?.failed_quality_gates.length ? (
                monitoring.failed_quality_gates.map((gate) => (
                  <div className="rounded border border-line p-3 text-sm" key={gate.job_id}>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold">{gate.source_title}</p>
                        <p className="mt-1 text-xs text-zinc-500">
                          {gate.source_name || gate.source_id} / {statusLabel(gate.status)} / {formatDateTime(gate.created_at)}
                        </p>
                      </div>
                      <span className="rounded border border-line px-2 py-1 text-xs">{statusLabel(gate.quality_gate_result.recommendation || "failed")}</span>
                    </div>
                    {gate.error_message ? <p className="mt-2 text-red-600">{gate.error_message}</p> : null}
                    {gate.quality_gate_result.issues?.length ? (
                      <ul className="mt-2 space-y-1">
                        {gate.quality_gate_result.issues.map((issue, index) => (
                          <li key={`${gate.job_id}-${issue.code}-${index}`}>
                            {issue.severity}: {issue.message}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                ))
              ) : (
                <p className="text-sm text-zinc-600">{"目前沒有失敗的品質檢查。"}</p>
              )}
            </CardContent>
          </Card>
        </div>

        <aside className="space-y-6">
          <Card className="shadow-none">
            <CardHeader>
              <CardTitle>{"來源健康"}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {monitoring?.source_health.map((source) => (
                <div className="rounded border border-line p-3 text-sm" key={source.id}>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-semibold">{source.name}</p>
                      <p className="mt-1 break-all text-xs text-zinc-500">{source.domain}</p>
                    </div>
                    <span className="rounded border border-line px-2 py-1 text-xs">{statusLabel(source.health_status)}</span>
                  </div>
                  <p className="mt-2 text-xs text-zinc-500">
                    {source.quota_role} / {"失敗"} {source.consecutive_failures} / {source.enabled ? "啟用" : "停用"}
                  </p>
                  <p className="mt-1 text-xs text-zinc-500">{"上次成功"} {formatDateTime(source.last_success_at)}</p>
                  <p className="text-xs text-zinc-500">{"上次失敗"} {formatDateTime(source.last_failure_at)}</p>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className="shadow-none">
            <CardHeader>
              <CardTitle>{"狀態統計"}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <p className="font-semibold">{"報表"}</p>
              <pre className="rounded bg-panel p-2 text-xs">{JSON.stringify(monitoring?.report_status_counts || {}, null, 2)}</pre>
              <p className="font-semibold">{"候選內容"}</p>
              <pre className="rounded bg-panel p-2 text-xs">{JSON.stringify(monitoring?.candidate_decision_counts || {}, null, 2)}</pre>
            </CardContent>
          </Card>
        </aside>
      </section>

      <section className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-xl font-semibold">{"每日報表"}</h2>
          <p className="text-sm text-zinc-600">{total} {"筆報表"}</p>
        </div>
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
              <div className="grid gap-2 text-sm md:grid-cols-5">
                <p><strong>{"已發布"}</strong><br />{report.total_published}</p>
                <p><strong>{"待審草稿"}</strong><br />{report.total_ready_for_review}</p>
                <p><strong>{"台灣"}</strong><br />{report.taiwan_media_count}</p>
                <p><strong>{"國際"}</strong><br />{report.international_count}</p>
                <p><strong>{"配額"}</strong><br />{quotaLabel(report.quota_met)}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </section>
    </main>
  );
}

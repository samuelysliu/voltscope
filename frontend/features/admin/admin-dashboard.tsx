"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/src/components/ui/card";
import { Button } from "@/src/components/ui/button";
import { adminApiBase, clearAdminToken, getAdminToken } from "./auth";

type ScheduleStatus = "success" | "warning" | "failed" | "not_run";

type Dashboard = {
  articles: number;
  published_articles: number;
  draft_articles: number;
  users: number;
  ads: number;
  today_views: number;
  yesterday_ai_schedule: {
    date: string;
    status: ScheduleStatus;
    crawl_success: number;
    crawl_failed: number;
    generation_success: number;
    generation_failed: number;
  };
};

function authHeaders(token: string) {
  return { authorization: `Bearer ${token}` };
}

function scheduleStatusLabel(status: ScheduleStatus) {
  return {
    success: "完成",
    warning: "部分完成",
    failed: "失敗",
    not_run: "未執行"
  }[status];
}

export function AdminDashboard() {
  const [token, setToken] = useState<string | null>(null);
  const [data, setData] = useState<Dashboard | null>(null);

  useEffect(() => {
    const activeToken = getAdminToken();
    setToken(activeToken);
    if (!activeToken) return;
    void fetch(`${adminApiBase()}/admin/dashboard`, { headers: authHeaders(activeToken) })
      .then((response) => (response.ok ? response.json() : null))
      .then(setData);
  }, []);

  if (!token) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-3xl font-bold">後台</h1>
        <p className="mt-4 text-zinc-700">請先登入管理員帳號。</p>
        <Button asChild className="mt-6">
          <Link href="/login">前往登入</Link>
        </Button>
      </main>
    );
  }

  const cards = [
    ["文章總數", data?.articles ?? 0],
    ["已發布", data?.published_articles ?? 0],
    ["草稿", data?.draft_articles ?? 0],
    ["使用者", data?.users ?? 0],
    ["廣告", data?.ads ?? 0],
    ["今日瀏覽", data?.today_views ?? 0]
  ];
  const schedule = data?.yesterday_ai_schedule;
  const scheduleCards = [
    ["排程狀態", schedule ? scheduleStatusLabel(schedule.status) : "讀取中"],
    ["撈文成功", schedule?.crawl_success ?? 0],
    ["撈文失敗", schedule?.crawl_failed ?? 0],
    ["產文成功", schedule?.generation_success ?? 0],
    ["產文失敗", schedule?.generation_failed ?? 0]
  ];

  return (
    <main className="mx-auto max-w-6xl px-4 py-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">後台儀表板</h1>
          <p className="mt-2 text-sm text-zinc-600">查看內容、會員、廣告與每日自動撈文狀態。</p>
        </div>
        <Button variant="outline" onClick={() => { clearAdminToken(); setToken(null); }}>
          登出
        </Button>
      </div>

      <section className="mt-6 grid gap-4 md:grid-cols-3">
        {cards.map(([label, value]) => (
          <Card key={label} className="shadow-none">
            <CardHeader><CardTitle className="text-sm text-zinc-500">{label}</CardTitle></CardHeader>
            <CardContent className="text-3xl font-bold">{value}</CardContent>
          </Card>
        ))}
      </section>

      <section className="mt-8 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold">昨日 AI 撈文排程</h2>
            <p className="mt-1 text-sm text-zinc-600">{schedule?.date ?? "讀取中"}</p>
          </div>
          <Button asChild variant="outline" size="sm">
            <Link href="/admin/content-reports">查看執行報表</Link>
          </Button>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {scheduleCards.map(([label, value]) => (
            <Card key={label} className="shadow-none">
              <CardHeader><CardTitle className="text-sm text-zinc-500">{label}</CardTitle></CardHeader>
              <CardContent className="text-2xl font-bold">{value}</CardContent>
            </Card>
          ))}
        </div>
      </section>
    </main>
  );
}

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/src/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/src/components/ui/card";
import { Input } from "@/src/components/ui/input";
import { clearAdminToken, getAdminToken, adminApiBase } from "./auth";

type AdItem = {
  id: string;
  name: string | null;
  image_url: string | null;
  target_url: string;
  alt_text: string;
  placement: string;
  status: string;
  weight: number;
};

const emptyAd = {
  name: "",
  image_url: "",
  target_url: "https://example.com",
  alt_text: "",
  placement: "home",
  status: "active",
  weight: 0
};

export function AdsManager() {
  const [token, setToken] = useState<string | null>(null);
  const [ads, setAds] = useState<AdItem[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState({ ...emptyAd });
  const [message, setMessage] = useState("");
  const apiBase = adminApiBase();

  async function load(activeToken = token) {
    if (!activeToken) return;
    const response = await fetch(`${apiBase}/admin/ads`, { headers: { authorization: `Bearer ${activeToken}` } });
    if (response.status === 401 || response.status === 403) {
      clearAdminToken();
      setToken(null);
      return;
    }
    setAds(await response.json());
  }

  useEffect(() => {
    const activeToken = getAdminToken();
    setToken(activeToken);
    if (activeToken) void load(activeToken);
  }, []);

  async function uploadImage(file: File | undefined) {
    if (!token || !file) return;
    const data = new FormData();
    data.append("file", file);
    const response = await fetch(`${apiBase}/admin/uploads/image`, { method: "POST", headers: { authorization: `Bearer ${token}` }, body: data });
    if (!response.ok) {
      setMessage("圖片上傳失敗。");
      return;
    }
    const uploaded = (await response.json()) as { url: string };
    setForm((item) => ({ ...item, image_url: uploaded.url }));
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    const response = await fetch(`${apiBase}/admin/ads${editingId ? `/${editingId}` : ""}`, {
      method: editingId ? "PUT" : "POST",
      headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
      body: JSON.stringify({ ...form, weight: Number(form.weight) })
    });
    setMessage(response.ok ? "廣告已儲存。" : "廣告儲存失敗。");
    if (response.ok) {
      setEditingId(null);
      setForm({ ...emptyAd });
      await load();
    }
  }

  async function remove(ad: AdItem) {
    if (!token) return;
    const response = await fetch(`${apiBase}/admin/ads/${ad.id}`, { method: "DELETE", headers: { authorization: `Bearer ${token}` } });
    setMessage(response.ok ? "廣告已刪除。" : "廣告刪除失敗。");
    await load();
  }

  if (!token) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-3xl font-bold">{"廣告"}</h1>
        <p className="mt-4 text-zinc-700">請先登入後台。</p>
        <Button asChild className="mt-6"><Link href="/login">前往登入</Link></Button>
      </main>
    );
  }

  return (
    <main className="mx-auto grid max-w-6xl gap-8 px-4 py-10 lg:grid-cols-[1fr_420px]">
      <section>
        <h1 className="text-3xl font-bold">廣告管理</h1>
        {message ? <p className="mt-4 rounded border border-line bg-white p-3 text-sm">{message}</p> : null}
        <div className="mt-6 space-y-4">
          {ads.map((ad) => (
            <Card className="shadow-none" key={ad.id}>
              <CardContent className="grid gap-4 p-4 md:grid-cols-[180px_1fr_auto]">
                <div className="aspect-[16/9] overflow-hidden rounded bg-panel">
                  {ad.image_url ? <img className="h-full w-full object-cover" src={ad.image_url} alt={ad.alt_text} /> : null}
                </div>
                <div>
                  <p className="font-semibold">{ad.name}</p>
                  <p className="text-sm text-zinc-600">{ad.placement} · {ad.status} · weight {ad.weight}</p>
                  <p className="mt-1 truncate text-sm text-zinc-500">{ad.target_url}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" size="sm" onClick={() => { setEditingId(ad.id); setForm({ name: ad.name || "", image_url: ad.image_url || "", target_url: ad.target_url, alt_text: ad.alt_text, placement: ad.placement, status: ad.status, weight: ad.weight }); }}>編輯</Button>
                  <Button variant="destructive" size="sm" onClick={() => void remove(ad)}>刪除</Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>
      <Card className="h-fit shadow-none">
        <CardHeader>
          <CardTitle>{editingId ? "編輯廣告" : "新增廣告"}</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-3" onSubmit={submit}>
            <Input placeholder="廣告名稱" required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
            <Input placeholder="圖片 URL" required value={form.image_url} onChange={(event) => setForm({ ...form, image_url: event.target.value })} />
            <Input type="file" accept="image/png,image/jpeg,image/webp,image/gif" onChange={(event) => void uploadImage(event.target.files?.[0])} />
            <Input placeholder="連結 URL" required value={form.target_url} onChange={(event) => setForm({ ...form, target_url: event.target.value })} />
            <Input placeholder="Alt text" required value={form.alt_text} onChange={(event) => setForm({ ...form, alt_text: event.target.value })} />
            <select className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm" value={form.placement} onChange={(event) => setForm({ ...form, placement: event.target.value })}>
              <option value="home">home</option>
              <option value="article_top">article_top</option>
              <option value="article_middle">article_middle</option>
              <option value="article_bottom">article_bottom</option>
              <option value="sidebar">sidebar</option>
            </select>
            <select className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm" value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}>
              <option value="active">active</option>
              <option value="inactive">inactive</option>
            </select>
            <Input type="number" value={form.weight} onChange={(event) => setForm({ ...form, weight: Number(event.target.value) })} />
            <div className="flex gap-2">
              <Button>{editingId ? "更新" : "建立"}</Button>
              <Button type="button" variant="outline" onClick={() => { setEditingId(null); setForm({ ...emptyAd }); }}>清空</Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}

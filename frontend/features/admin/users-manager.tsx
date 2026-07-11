"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/src/components/ui/button";
import { Card, CardContent } from "@/src/components/ui/card";
import { Input } from "@/src/components/ui/input";
import { clearAdminToken, getAdminToken, adminApiBase } from "./auth";

type UserItem = {
  id: string;
  email: string;
  display_name: string;
  role: string;
  email_verified: boolean;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
};

export function UsersManager() {
  const [token, setToken] = useState<string | null>(null);
  const [users, setUsers] = useState<UserItem[]>([]);
  const [query, setQuery] = useState("");
  const [message, setMessage] = useState("");
  const apiBase = adminApiBase();

  async function load(activeToken = token, q = query) {
    if (!activeToken) return;
    const response = await fetch(`${apiBase}/admin/users${q ? `?q=${encodeURIComponent(q)}` : ""}`, {
      headers: { authorization: `Bearer ${activeToken}` }
    });
    if (response.status === 401 || response.status === 403) {
      clearAdminToken();
      setToken(null);
      return;
    }
    const data = (await response.json()) as { items: UserItem[] };
    setUsers(data.items);
  }

  useEffect(() => {
    const activeToken = getAdminToken();
    setToken(activeToken);
    if (activeToken) void load(activeToken, "");
  }, []);

  async function updateUser(user: UserItem, patch: Partial<UserItem>) {
    if (!token) return;
    const response = await fetch(`${apiBase}/admin/users/${user.id}`, {
      method: "PUT",
      headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
      body: JSON.stringify(patch)
    });
    setMessage(response.ok ? "會員已更新。" : "會員更新失敗。");
    await load();
  }

  async function deleteUser(user: UserItem) {
    if (!token) return;
    const response = await fetch(`${apiBase}/admin/users/${user.id}`, { method: "DELETE", headers: { authorization: `Bearer ${token}` } });
    if (response.ok) {
      setUsers((current) => current.filter((item) => item.id !== user.id));
      setMessage("會員已刪除。");
      return;
    }
    const payload = (await response.json().catch(() => null)) as { error?: { message?: string } } | null;
    setMessage(payload?.error?.message || "會員刪除失敗。");
  }

  if (!token) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-3xl font-bold">{"使用者"}</h1>
        <p className="mt-4 text-zinc-700">請先登入後台。</p>
        <Button asChild className="mt-6"><Link href="/login">前往登入</Link></Button>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="text-3xl font-bold">會員管理</h1>
      <form className="mt-6 flex max-w-xl gap-2" onSubmit={(event) => { event.preventDefault(); void load(); }}>
        <Input placeholder="搜尋 Email / display name" value={query} onChange={(event) => setQuery(event.target.value)} />
        <Button>搜尋</Button>
      </form>
      {message ? <p className="mt-4 rounded border border-line bg-white p-3 text-sm">{message}</p> : null}
      <div className="mt-6 space-y-4">
        {users.map((user) => (
          <Card className="shadow-none" key={user.id}>
            <CardContent className="grid gap-4 p-4 md:grid-cols-[1.2fr_1fr_auto] md:items-center">
              <div>
                <p className="font-semibold">{user.email}</p>
                <p className="text-sm text-zinc-600">{user.display_name}</p>
                <p className="mt-1 text-xs text-zinc-500">
                  {user.role} · {user.email_verified ? "verified" : "unverified"} · {user.is_active ? "active" : "inactive"}
                </p>
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                <Input defaultValue={user.display_name} onBlur={(event) => event.target.value !== user.display_name && void updateUser(user, { display_name: event.target.value })} />
                <select className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={user.role} onChange={(event) => void updateUser(user, { role: event.target.value })}>
                  <option value="member">member</option>
                  <option value="admin">admin</option>
                </select>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" size="sm" onClick={() => void updateUser(user, { email_verified: !user.email_verified })}>
                  {user.email_verified ? "取消驗證" : "設為已驗證"}
                </Button>
                <Button variant="outline" size="sm" onClick={() => void updateUser(user, { is_active: !user.is_active })}>
                  {user.is_active ? "停用" : "啟用"}
                </Button>
                <Button variant="destructive" size="sm" onClick={() => void deleteUser(user)}>刪除</Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </main>
  );
}

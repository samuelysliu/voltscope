"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/src/components/ui/button";
import { Input } from "@/src/components/ui/input";
import { setAdminToken } from "../admin/auth";
import { authApiBase, setMemberToken } from "./auth";

type CurrentUser = {
  id: number;
  email: string;
  display_name: string;
  role: "member" | "author" | "admin";
  email_verified: boolean;
};

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);

    try {
      const response = await fetch(`${authApiBase()}/auth/login`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ account: email, password })
      });

      if (!response.ok) {
        setError("登入失敗，請確認 Email 或密碼。");
        return;
      }

      const data = (await response.json()) as { access_token: string };

      const meResponse = await fetch(`${authApiBase()}/auth/me`, {
        headers: { authorization: `Bearer ${data.access_token}` }
      });

      if (!meResponse.ok) {
        setError("登入狀態驗證失敗，請重新登入。");
        return;
      }

      const me = (await meResponse.json()) as CurrentUser;
      if (me.role === "admin") {
        setAdminToken(data.access_token);
        router.replace("/admin");
        return;
      }

      setMemberToken(data.access_token);
      router.replace("/zh");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="mt-6 space-y-4" onSubmit={onSubmit}>
      <Input autoComplete="email" placeholder="Email" required type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
      <Input autoComplete="current-password" placeholder="Password" required type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
      {error ? <p className="text-sm font-semibold text-red-600">{error}</p> : null}
      <Button className="w-full" disabled={isSubmitting}>
        {isSubmitting ? "登入中..." : "登入"}
      </Button>
    </form>
  );
}

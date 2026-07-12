"use client";

import { useState } from "react";
import { Button } from "@/src/components/ui/button";
import { Input } from "@/src/components/ui/input";
import { authApiBase } from "./auth";

export function RegisterForm() {
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isRegistered, setIsRegistered] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setIsRegistered(false);
    setIsSubmitting(true);
    try {
      const response = await fetch(`${authApiBase()}/auth/register`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, display_name: displayName, password })
      });
      if (!response.ok) {
        setError("註冊失敗，請確認 Email 未被使用且密碼至少 8 字元。");
        return;
      }
      setIsRegistered(true);
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isRegistered) {
    return (
      <div className="mt-6 rounded-lg border border-line bg-panel p-4 text-sm" role="status" aria-live="polite">
        <p className="font-semibold">驗證信已發出</p>
        <p className="mt-2 text-zinc-700">
          請前往 <span className="font-semibold text-zinc-900">{email}</span> 查看電子郵件，並依照信件內容完成驗證。
        </p>
      </div>
    );
  }

  return (
    <div>
      <form className="mt-6 space-y-4" onSubmit={onSubmit}>
        <Input autoComplete="email" placeholder="Email" required type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
        <Input autoComplete="name" placeholder="Display name" required value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
        <Input autoComplete="new-password" placeholder="Password" required type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
        <label className="flex items-start gap-3 text-sm leading-6 text-zinc-700">
          <input className="mt-1 h-4 w-4 accent-signal" required type="checkbox" />
          <span>
            我已閱讀並同意{" "}
            <a className="font-semibold text-signal underline" href="/zh/terms" target="_blank" rel="noreferrer">
              使用者條款
            </a>
          </span>
        </label>
        {error ? <p className="text-sm font-semibold text-red-600">{error}</p> : null}
        <Button className="w-full" disabled={isSubmitting}>
          {isSubmitting ? "註冊中..." : "註冊"}
        </Button>
      </form>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Button } from "@/src/components/ui/button";
import { authApiBase } from "./auth";

export function VerifyEmailResult() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [status, setStatus] = useState<"pending" | "success" | "error">("pending");

  useEffect(() => {
    async function verify() {
      if (!token) {
        setStatus("error");
        return;
      }
      const response = await fetch(`${authApiBase()}/auth/verify-email?token=${encodeURIComponent(token)}`, { cache: "no-store" });
      setStatus(response.ok ? "success" : "error");
    }
    void verify();
  }, [token]);

  return (
    <div className="mt-6 rounded-lg border border-line bg-white p-5">
      {status === "pending" ? <p>驗證中...</p> : null}
      {status === "success" ? (
        <div>
          <p className="font-semibold">Email 已驗證完成。</p>
          <Button asChild className="mt-4">
            <Link href="/login">前往登入</Link>
          </Button>
        </div>
      ) : null}
      {status === "error" ? <p className="font-semibold text-red-600">驗證連結無效或已過期。</p> : null}
    </div>
  );
}

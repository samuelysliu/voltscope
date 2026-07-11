"use client";

import Link from "next/link";
import { LogOut, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { clearAdminToken, getAdminToken } from "@/features/admin/auth";
import { authApiBase, clearMemberToken, getMemberToken } from "@/features/auth/auth";
import type { Locale } from "@/lib/i18n";
import { Button } from "@/src/components/ui/button";

type CurrentUser = {
  id: number;
  email: string;
  display_name: string;
  role: "member" | "author" | "admin";
  email_verified: boolean;
};

function getActiveToken(): string | null {
  return getMemberToken() ?? getAdminToken();
}

function clearAuthTokens(): void {
  clearMemberToken();
  clearAdminToken();
}

export function AuthNav({ locale }: { locale: Locale }) {
  const [isLoaded, setIsLoaded] = useState(false);
  const [user, setUser] = useState<CurrentUser | null>(null);

  useEffect(() => {
    const token = getActiveToken();
    if (!token) {
      setIsLoaded(true);
      return;
    }

    let isActive = true;
    fetch(`${authApiBase()}/auth/me`, {
      headers: { authorization: `Bearer ${token}` }
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("Invalid auth token");
        return (await response.json()) as CurrentUser;
      })
      .then((currentUser) => {
        if (isActive) setUser(currentUser);
      })
      .catch(() => {
        clearAuthTokens();
        if (isActive) setUser(null);
      })
      .finally(() => {
        if (isActive) setIsLoaded(true);
      });

    return () => {
      isActive = false;
    };
  }, []);

  function logout() {
    clearAuthTokens();
    setUser(null);
  }

  if (!isLoaded) {
    return <span className="text-sm text-zinc-500">{locale === "zh" ? "讀取中" : "Loading"}</span>;
  }

  if (!user) {
    return (
      <>
        <Link href="/login">{locale === "zh" ? "登入" : "Login"}</Link>
        <Link href="/register">{locale === "zh" ? "註冊" : "Register"}</Link>
      </>
    );
  }

  return (
    <div className="flex items-center gap-3">
      <span className="max-w-36 truncate font-semibold text-zinc-900" title={user.email}>
        {user.display_name}
      </span>
      {user.role === "admin" ? (
        <Button asChild variant="outline" size="sm">
          <Link href="/admin">
            <ShieldCheck size={16} />
            {"後台"}
          </Link>
        </Button>
      ) : null}
      <Button type="button" variant="ghost" size="sm" onClick={logout}>
        <LogOut size={16} />
        {locale === "zh" ? "登出" : "Logout"}
      </Button>
    </div>
  );
}

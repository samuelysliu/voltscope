import { Suspense } from "react";
import Link from "next/link";
import { VerifyEmailResult } from "@/features/auth/verify-email-result";

export const metadata = {
  title: "Verify Email | VoltScope",
  robots: { index: false, follow: false }
};

export default function VerifyEmailPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4">
      <Link className="text-lg font-bold" href="/zh">
        VoltScope
      </Link>
      <h1 className="mt-8 text-3xl font-bold">Email 驗證</h1>
      <Suspense fallback={<p className="mt-6">驗證中...</p>}>
        <VerifyEmailResult />
      </Suspense>
    </main>
  );
}

import Link from "next/link";
import { LoginForm } from "@/features/auth/login-form";

export const metadata = {
  title: "登入 | VoltScope",
  robots: { index: false, follow: false }
};

export default function LoginPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4">
      <Link className="text-lg font-bold" href="/zh">
        VoltScope
      </Link>
      <h1 className="mt-8 text-3xl font-bold">{"登入 VoltScope"}</h1>
      <LoginForm />
      <div className="mt-6 flex justify-between text-sm">
        <Link className="font-semibold text-signal" href="/register">
          {"註冊帳號"}
        </Link>
        <Link className="font-semibold text-signal" href="/zh">
          {"回到首頁"}
        </Link>
      </div>
    </main>
  );
}

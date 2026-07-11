import Link from "next/link";
import { RegisterForm } from "@/features/auth/register-form";

export const metadata = {
  title: "Register | VoltScope",
  robots: { index: false, follow: false }
};

export default function RegisterPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4">
      <Link className="text-lg font-bold" href="/zh">
        VoltScope
      </Link>
      <h1 className="mt-8 text-3xl font-bold">註冊會員</h1>
      <RegisterForm />
      <Link className="mt-6 text-sm font-semibold text-signal" href="/login">
        已有帳號，前往登入
      </Link>
    </main>
  );
}

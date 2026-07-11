import { redirect } from "next/navigation";
import type { Route } from "next";

export default function TermsRedirectPage() {
  redirect("/zh/terms" as Route);
}

import { redirect } from "next/navigation";
import type { Locale } from "@/lib/i18n";

export default async function TagPage({ params }: { params: Promise<{ locale: Locale; slug: string }> }) {
  const { locale, slug } = await params;
  redirect(`/${locale}/topics/${slug}`);
}

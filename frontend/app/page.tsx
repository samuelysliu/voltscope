import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { preferredLocale } from "@/src/lib/locale-redirect";

export const dynamic = "force-dynamic";

export default async function IndexPage() {
  const requestHeaders = await headers();
  redirect(`/${preferredLocale(requestHeaders)}`);
}

import Link from "next/link";
import Image from "next/image";
import { Menu, Search } from "lucide-react";
import { AuthNav } from "@/components/auth-nav";
import { Button } from "@/src/components/ui/button";
import { alternateLocale, localeName, type Locale } from "@/lib/i18n";

export function SiteHeader({ locale }: { locale: Locale }) {
  const other = alternateLocale(locale);

  return (
    <header className="fixed inset-x-0 top-0 z-50 border-b border-line bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link href={`/${locale}`} aria-label={locale === "zh" ? "電馳誌首頁" : "VoltScope home"}>
          <Image src="/logo.png" alt="VoltScope 電馳誌" width={180} height={56} className="h-10 w-auto object-contain" priority />
        </Link>
        <nav className="hidden items-center gap-6 text-sm md:flex">
          <Link href={`/${locale}/articles`}>{locale === "zh" ? "文章" : "Articles"}</Link>
          <Link href={`/${locale}/search`} aria-label={locale === "zh" ? "搜尋" : "Search"}>
            <Search size={18} />
          </Link>
          <AuthNav locale={locale} />
          <Button asChild variant="outline" size="sm">
            <Link href={`/${other}`}>{localeName(other)}</Link>
          </Button>
        </nav>
        <Button className="md:hidden" variant="outline" size="icon" aria-label={locale === "zh" ? "開啟選單" : "Open menu"}>
          <Menu size={20} />
        </Button>
      </div>
    </header>
  );
}

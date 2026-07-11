import { notFound } from "next/navigation";
import { SiteHeader } from "@/components/site-header";
import { htmlLang, isLocale, type Locale } from "@/lib/i18n";

export default async function LocaleLayout({ children, params }: { children: React.ReactNode; params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const typedLocale = locale as Locale;
  return (
    <div lang={htmlLang(typedLocale)}>
      <SiteHeader locale={typedLocale} />
      <div className="pt-[65px]">{children}</div>
      <footer className="border-t border-line bg-graphite px-4 py-10 text-white">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 text-sm md:flex-row md:items-center md:justify-between">
          <div>
            <p className="font-semibold">VoltScope</p>
            <p className="mt-1 text-zinc-300">{typedLocale === "zh" ? "電動車、充電與智慧移動科技媒體" : "Electric vehicles, charging, and smart mobility"}</p>
          </div>
          <nav className="flex flex-wrap gap-4" aria-label={typedLocale === "zh" ? "網站資訊" : "Site information"}>
            <a className="hover:underline" href={`/${typedLocale}/terms`}>{typedLocale === "zh" ? "使用者條款" : "Terms of Use"}</a>
            <a className="hover:underline" href="mailto:services@voltscopes.com">{typedLocale === "zh" ? "商務合作" : "Business inquiries"}</a>
          </nav>
        </div>
      </footer>
    </div>
  );
}

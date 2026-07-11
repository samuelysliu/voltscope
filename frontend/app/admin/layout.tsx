export const metadata = {
  title: "後台 | VoltScope",
  robots: { index: false, follow: false }
};

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-panel text-graphite">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <a className="font-bold" href="/admin">
            {"VoltScope 後台"}
          </a>
          <nav className="flex flex-wrap items-center gap-3 text-sm">
            <a href="/admin/articles">{"文章"}</a>
            <a href="/admin/users">{"使用者"}</a>
            <a href="/admin/ads">{"廣告"}</a>
            <a href="/admin/content-pipeline">{"AI 撈文"}</a>
            <a href="/admin/content-reports">{"內容報表"}</a>
            <a href="/admin/content-sources">{"內容來源"}</a>
            <a href="/admin/content-candidates">{"候選內容"}</a>
            <a className="rounded border border-line px-3 py-2 font-semibold" href="/zh">
              {"查看網站"}
            </a>
          </nav>
        </div>
      </header>
      {children}
    </div>
  );
}

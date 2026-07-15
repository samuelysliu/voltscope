import { ArticlesManager } from "@/features/admin/articles-manager";

export default async function AdminEditArticlePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ArticlesManager initialArticleId={id} />;
}

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Eye, Heart, MessageCircle } from "lucide-react";
import { Badge } from "@/src/components/ui/badge";
import { Button } from "@/src/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/src/components/ui/card";
import { Textarea } from "@/src/components/ui/textarea";
import type { PublicComment } from "@/lib/api";
import { clearMemberToken, getMemberToken } from "@/features/auth/auth";

const API_BASE_URL = "/api/v1";

type CurrentUser = {
  id: string;
  email: string;
  display_name: string;
  role: string;
  email_verified: boolean;
};

export function ArticleEngagement({
  articleId,
  locale,
  initialViews,
  likes,
  comments
}: {
  articleId: string;
  locale: string;
  initialViews: number;
  likes: number;
  comments: PublicComment[];
}) {
  const [views, setViews] = useState(initialViews);
  const [likeCount, setLikeCount] = useState(likes);
  const [commentItems, setCommentItems] = useState(comments);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [content, setContent] = useState("");
  const [message, setMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let active = true;
    async function recordView() {
      const response = await fetch(`${API_BASE_URL}/public/articles/${articleId}/view`, { method: "POST" });
      if (response.ok && active) setViews((count) => count + 1);
    }
    void recordView();
    return () => {
      active = false;
    };
  }, [articleId]);

  useEffect(() => {
    async function loadUser() {
      const token = getMemberToken();
      if (!token) return;
      const response = await fetch(`${API_BASE_URL}/auth/me`, {
        headers: { authorization: `Bearer ${token}` },
        cache: "no-store"
      });
      if (!response.ok) {
        clearMemberToken();
        return;
      }
      setCurrentUser(await response.json());
    }
    void loadUser();
  }, []);

  async function likeArticle() {
    const token = getMemberToken();
    if (!token) {
      setMessage(locale === "zh" ? "請先登入會員。" : "Please log in first.");
      return;
    }
    const response = await fetch(`${API_BASE_URL}/member/articles/${articleId}/like`, {
      method: "POST",
      headers: { authorization: `Bearer ${token}` }
    });
    if (response.status === 403) {
      setMessage(locale === "zh" ? "請先完成 Email 驗證。" : "Please verify your email first.");
      return;
    }
    if (!response.ok) {
      setMessage(locale === "zh" ? "按讚失敗。" : "Like failed.");
      return;
    }
    const data = (await response.json()) as { liked: boolean; count: number };
    setLikeCount(data.count);
    setMessage(data.liked ? (locale === "zh" ? "已按讚。" : "Liked.") : locale === "zh" ? "已取消讚。" : "Like removed.");
  }

  async function submitComment(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = getMemberToken();
    if (!token) {
      setMessage(locale === "zh" ? "請先登入會員。" : "Please log in first.");
      return;
    }
    setIsSubmitting(true);
    setMessage("");
    try {
      const response = await fetch(`${API_BASE_URL}/member/articles/${articleId}/comments`, {
        method: "POST",
        headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
        body: JSON.stringify({ content })
      });
      if (response.status === 403) {
        setMessage(locale === "zh" ? "請先完成 Email 驗證。" : "Please verify your email first.");
        return;
      }
      if (!response.ok) {
        setMessage(locale === "zh" ? "留言送出失敗。" : "Comment failed.");
        return;
      }
      const comment = (await response.json()) as PublicComment;
      setCommentItems((items) => [comment, ...items]);
      setContent("");
      setMessage(locale === "zh" ? "留言已送出。" : "Comment posted.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="mt-10 space-y-8 border-t border-line pt-8">
      <div className="flex flex-wrap gap-3">
        <Badge variant="secondary" className="gap-1.5">
          <Eye size={16} /> {views}
        </Badge>
        <Button variant="outline" size="sm" className="gap-1.5" onClick={likeArticle}>
          <Heart size={16} /> {likeCount}
        </Button>
        <Badge variant="secondary" className="gap-1.5">
          <MessageCircle size={16} /> {commentItems.length}
        </Badge>
      </div>
      {message ? <p className="text-sm font-semibold text-signal">{message}</p> : null}

      {currentUser ? (
        currentUser.email_verified ? (
          <Card className="shadow-none">
            <CardHeader>
              <CardTitle className="text-xl">{locale === "zh" ? "新增留言" : "Add comment"}</CardTitle>
            </CardHeader>
            <CardContent>
              <form className="space-y-3" onSubmit={submitComment}>
                <Textarea required minLength={1} maxLength={4000} value={content} onChange={(event) => setContent(event.target.value)} />
                <Button disabled={isSubmitting}>{isSubmitting ? (locale === "zh" ? "送出中..." : "Posting...") : locale === "zh" ? "送出留言" : "Post comment"}</Button>
              </form>
            </CardContent>
          </Card>
        ) : (
          <Card className="shadow-none">
            <CardContent className="p-5 text-sm text-zinc-700">
              {locale === "zh" ? "完成 Email 驗證後即可留言與按讚。" : "Verify your email to comment and like articles."}
            </CardContent>
          </Card>
        )
      ) : (
        <Card className="shadow-none">
          <CardContent className="flex flex-wrap items-center justify-between gap-3 p-5">
            <p className="text-sm text-zinc-700">{locale === "zh" ? "登入會員後可以留言與按讚。" : "Log in to comment and like articles."}</p>
            <div className="flex gap-2">
              <Button asChild variant="outline" size="sm">
                <Link href="/login">{locale === "zh" ? "登入" : "Login"}</Link>
              </Button>
              <Button asChild size="sm">
                <Link href="/register">{locale === "zh" ? "註冊" : "Register"}</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card className="shadow-none">
        <CardHeader>
          <CardTitle className="text-xl">{locale === "zh" ? "留言" : "Comments"}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {commentItems.length ? (
            commentItems.map((comment) => (
              <article className="border-b border-line pb-4 last:border-b-0 last:pb-0" key={comment.id}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-semibold">{comment.author_name}</p>
                  <time className="text-sm text-zinc-500">{new Date(comment.created_at).toLocaleDateString(locale === "zh" ? "zh-TW" : "en-US")}</time>
                </div>
                <p className="mt-2 text-zinc-700">{comment.body}</p>
              </article>
            ))
          ) : (
            <p className="text-zinc-600">{locale === "zh" ? "尚無公開留言。" : "No public comments yet."}</p>
          )}
        </CardContent>
      </Card>
    </section>
  );
}

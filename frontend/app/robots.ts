import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const host = process.env.FRONTEND_URL || "http://localhost:3000";
  return {
    rules: [
      { userAgent: "*", allow: "/", disallow: ["/admin", "/api/admin", "/api/v1/admin", "/preview"] }
    ],
    sitemap: `${host}/sitemap.xml`
  };
}

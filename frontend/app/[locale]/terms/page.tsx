import type { Metadata } from "next";
import type { Locale } from "@/lib/i18n";

const businessEmail = "services@voltscopes.com";

export async function generateMetadata({ params }: { params: Promise<{ locale: Locale }> }): Promise<Metadata> {
  const { locale } = await params;
  const title = locale === "zh" ? "使用者條款" : "Terms of Use";
  return {
    title,
    description: locale === "zh" ? "VoltScope 電馳誌使用者條款" : "VoltScope Terms of Use",
    alternates: {
      canonical: `/${locale}/terms`,
      languages: { "zh-TW": "/zh/terms", en: "/en/terms", "x-default": "/zh/terms" }
    }
  };
}

function ChineseTerms() {
  return (
    <>
      <h1 className="text-4xl font-bold">使用者條款</h1>
      <p className="mt-3 text-sm text-zinc-500">最後更新日期：2026 年 7 月 11 日</p>
      <p className="mt-8 leading-8 text-zinc-700">
        歡迎使用 VoltScope 電馳誌（以下稱「本網站」）。當您瀏覽本網站、註冊會員或使用留言、按讚及其他功能時，即表示您已閱讀、理解並同意遵守本使用者條款。
      </p>

      <h2>一、服務內容</h2>
      <p>本網站提供電動車、充電基礎設施、能源與智慧移動相關的新聞、評論、資料整理、會員互動及其他內容服務。我們可能依營運需求新增、調整、暫停或終止部分功能。</p>

      <h2>二、會員帳號</h2>
      <ul>
        <li>註冊時應提供正確且可使用的 Email，並妥善保管登入資訊。</li>
        <li>您應對帳號下發生的所有活動負責，不得冒用他人身分或轉讓帳號。</li>
        <li>若發現帳號遭未授權使用，請儘速通知本網站。</li>
      </ul>

      <h2>三、使用規範</h2>
      <p>您不得利用本網站從事違法、侵權、詐騙、騷擾、散布惡意程式、干擾系統運作或大量自動擷取等行為，也不得張貼仇恨、威脅、誹謗、垃圾訊息或侵害他人權利的內容。</p>

      <h2>四、會員內容</h2>
      <p>您對自行提交的留言及其他內容負責，並保證擁有必要權利。為維護網站品質與安全，本網站得拒絕顯示、隱藏或移除違反條款、法律或社群秩序的內容。</p>

      <h2>五、智慧財產權</h2>
      <p>除另有標示外，本網站的文章、編輯內容、品牌、版面、圖片、程式及其他素材均受智慧財產權相關法律保護。未經授權，不得重製、改作、散布、公開傳輸或作為商業用途。引用內容時應遵守合理使用規範並清楚標示來源。</p>

      <h2>六、內容聲明</h2>
      <p>本網站亦可能引用或連結第三方資料。相關內容僅供一般資訊參考，不構成投資、法律、技術安全或購買建議；重要決策請自行查證原始資料並諮詢專業人士。</p>

      <h2>七、隱私與資料使用</h2>
      <p>為提供會員、驗證、留言及網站安全功能，本網站可能處理您提供的 Email、顯示名稱、互動紀錄與必要的技術資訊。我們會採取合理措施保護資料，但無法保證網路傳輸或儲存系統絕對安全。</p>

      <h2>八、免責聲明</h2>
      <p>本網站盡力維持內容與服務的正確性及可用性，但不保證所有資訊完整、即時、無誤或服務永不中斷。因使用或無法使用本網站所產生的損失，本網站將在適用法律允許的範圍內限制責任。</p>

      <h2>九、帳號限制與終止</h2>
      <p>若使用者違反本條款、侵害他人權利、危害網站安全或涉及違法行為，本網站得限制功能、移除內容、停用帳號或終止服務。</p>

      <h2>十、條款修改</h2>
      <p>本網站可能因功能、法規或營運調整更新本條款，並於本頁公布最新內容與更新日期。修改後繼續使用本網站，即視為同意更新後的條款。</p>

      <h2>十一、聯絡方式</h2>
      <p>
        如有條款、內容授權或商務合作需求，請聯繫：{" "}
        <a className="font-semibold text-signal underline" href={`mailto:${businessEmail}`}>{businessEmail}</a>
      </p>
    </>
  );
}

function EnglishTerms() {
  return (
    <>
      <h1 className="text-4xl font-bold">Terms of Use</h1>
      <p className="mt-3 text-sm text-zinc-500">Last updated: July 11, 2026</p>
      <p className="mt-8 leading-8 text-zinc-700">
        Welcome to VoltScope. By browsing this website, creating an account, or using comments, likes, and other features, you acknowledge that you have read and agree to these Terms of Use.
      </p>

      <h2>1. Services</h2>
      <p>VoltScope provides news, commentary, reference material, member interactions, and related services concerning electric vehicles, charging infrastructure, energy, and smart mobility. Features may be added, changed, suspended, or discontinued as operational needs evolve.</p>

      <h2>2. Member Accounts</h2>
      <ul>
        <li>Provide an accurate, accessible email address and protect your login credentials.</li>
        <li>You are responsible for activity under your account and may not impersonate others or transfer your account.</li>
        <li>Notify us promptly if you suspect unauthorized account use.</li>
      </ul>

      <h2>3. Acceptable Use</h2>
      <p>You may not use the website for unlawful, fraudulent, infringing, abusive, or disruptive activity. Prohibited conduct includes distributing malware, interfering with the service, excessive automated extraction, harassment, threats, defamation, spam, or violations of another person&apos;s rights.</p>

      <h2>4. User Content</h2>
      <p>You are responsible for comments and other material you submit and represent that you have the necessary rights. We may reject, hide, or remove content that violates these terms, applicable law, or community safety.</p>

      <h2>5. Intellectual Property</h2>
      <p>Unless stated otherwise, articles, editorial material, branding, layouts, images, software, and other website assets are protected by intellectual property laws. They may not be reproduced, adapted, distributed, publicly transmitted, or commercially exploited without authorization.</p>

      <h2>6. AI and Third-Party Material</h2>
      <p>Some material may be prepared with automated or AI-assisted tools and reviewed through system or editorial processes. The website may also cite or link to third-party sources. Content is provided for general information and does not constitute investment, legal, safety, or purchasing advice.</p>

      <h2>7. Privacy and Data</h2>
      <p>To provide accounts, verification, comments, and security functions, we may process your email address, display name, interaction records, and necessary technical information. We take reasonable safeguards but cannot guarantee absolute security of internet transmission or storage systems.</p>

      <h2>8. Disclaimer</h2>
      <p>We work to keep content and services accurate and available, but do not guarantee that all information is complete, current, error-free, or uninterrupted. Liability arising from use of the website is limited to the extent permitted by applicable law.</p>

      <h2>9. Suspension and Termination</h2>
      <p>We may restrict features, remove content, suspend accounts, or terminate access when a user violates these terms, infringes rights, threatens website security, or engages in unlawful conduct.</p>

      <h2>10. Changes to These Terms</h2>
      <p>These terms may be updated in response to product, legal, or operational changes. The latest version and revision date will be published on this page. Continued use after an update constitutes acceptance of the revised terms.</p>

      <h2>11. Contact</h2>
      <p>
        For terms, content licensing, or business inquiries, contact{" "}
        <a className="font-semibold text-signal underline" href={`mailto:${businessEmail}`}>{businessEmail}</a>.
      </p>
    </>
  );
}

export default async function TermsPage({ params }: { params: Promise<{ locale: Locale }> }) {
  const { locale } = await params;
  return (
    <main className="mx-auto max-w-3xl px-4 py-12">
      <article className="terms-content">{locale === "zh" ? <ChineseTerms /> : <EnglishTerms />}</article>
    </main>
  );
}

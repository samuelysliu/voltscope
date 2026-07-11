# VoltScope 電馳誌

VoltScope 是一套以電動車、充電基礎設施與智慧移動為主題的雙語內容平台。專案同時提供公開媒體網站、會員互動、管理後台，以及可排程執行的 AI 內容產線，適合用來建置垂直媒體、技術新聞網站或具自動化內容工作流的 CMS。

公開網站支援繁體中文與英文，文章由伺服器端渲染，並具備搜尋引擎所需的 metadata、結構化資料、sitemap、RSS 與多語系連結。管理者可以維護文章、內容來源、會員與廣告，也可以從來源擷取候選內容，交由 Mistral 產生雙語草稿並通過品質檢查後進入文章流程。

## 專案目標

- 建立可長期營運的雙語垂直媒體網站。
- 將內容來源、候選內容、AI 產文、品質檢查與發布流程集中管理。
- 保留人工審核能力，避免 AI 內容未經檢查直接發布。
- 提供會員註冊、Email 驗證、按讚與留言等互動功能。
- 以 Docker Compose 提供一致的開發與部署環境。

## 核心功能

### 公開網站

- 繁體中文與英文內容路由。
- 首頁焦點文章、最新文章與分類瀏覽。
- 文章列表、分類頁、文章詳情、搜尋與作者頁。
- 文章分類、標籤、上一篇與下一篇導覽。
- 瀏覽數、會員按讚與留言。
- RSS、sitemap、robots.txt、canonical 與 hreflang。
- Open Graph 與 JSON-LD 結構化資料。

### 會員系統

- 註冊、登入與 JWT 身分驗證。
- SMTP Email 驗證。
- 已驗證會員可按讚及留言。
- 登入狀態與會員名稱顯示。

### 管理後台

- 儀表板與每日內容產線狀態。
- 文章新增、編輯、發布、封存與刪除。
- TipTap 富文字編輯器與圖片上傳。
- 會員、廣告及內容來源管理。
- 候選內容審核與人工產文。
- 產文工作、品質檢查與每日執行報表。

### AI 內容產線

- RSS 與 HTML 來源擷取。
- URL 正規化、重複檢查及候選內容評分。
- 使用 Mistral 擷取事實並產生中英文文章。
- 自動建立文章分類與標籤。
- 品質檢查包含：
  - 必要欄位完整性
  - 來源網址白名單
  - 原始來源標示
  - 來源句子重疊率
  - 中英文文章長度
  - 制式內容與編輯流程文字
  - 來源圖片 hotlink
- Redis 分散式鎖，避免同一天重複執行排程。
- 支援人工執行、dry run 與每日排程。

## 系統架構

```text
瀏覽器
  │
  ▼
Nginx
  ├── Next.js 前台與管理後台
  │     └── Server Components / Client Components
  │
  └── FastAPI API
        ├── 身分驗證與會員互動
        ├── CMS 與內容來源管理
        ├── AI 內容產線與品質檢查
        ├── PostgreSQL：主要資料與工作紀錄
        ├── Redis：排程鎖與快取相關狀態
        ├── Mistral API：事實整理與雙語產文
        └── SMTP：Email 驗證信
```

## 技術棧

| 層級 | 技術 |
| --- | --- |
| 前端 | Next.js 15、React 19、TypeScript、Tailwind CSS、Radix UI、TipTap |
| 後端 | FastAPI、SQLAlchemy 2 Async、Pydantic、Alembic |
| 資料庫 | PostgreSQL 16 |
| 快取與鎖 | Redis 7 |
| AI | Mistral API |
| 驗證 | JWT、Argon2、Email verification |
| 部署 | Docker Compose、Nginx |
| 測試 | Pytest、TypeScript typecheck、Next.js production build |

## 專案目錄

```text
voltscope/
├── backend/
│   ├── alembic/                 # 資料庫 migration
│   ├── app/
│   │   ├── api/                 # FastAPI routes
│   │   ├── core/                # 設定、錯誤與共用基礎設施
│   │   ├── db/                  # SQLAlchemy session
│   │   ├── jobs/                # 每日內容產線排程
│   │   ├── models/              # ORM entities
│   │   ├── schemas/             # API request/response schemas
│   │   ├── security/            # JWT 與密碼處理
│   │   └── services/            # CMS、Email、AI 與內容產線服務
│   └── scripts/                 # Seed 與維運腳本
├── frontend/
│   ├── app/                     # Next.js App Router
│   ├── components/              # 公開網站共用元件
│   ├── features/                # Auth 與後台功能模組
│   ├── lib/                     # API、i18n 與共用程式
│   ├── public/                  # Logo、favicon 與公開資產
│   └── src/components/ui/       # UI 基礎元件
├── infra/
│   ├── nginx/                   # Reverse proxy 設定
│   └── scripts/                 # 備份、還原與健康檢查
├── docker-compose.yml           # 共用服務設定
├── docker-compose.dev.yml       # 本機開發 override
├── docker-compose.prod.yml      # 正式環境 override
└── .env.example                 # 環境變數範例
```

## 快速開始

### 環境需求

- Docker Desktop 或 Docker Engine
- Docker Compose v2
- Make（選用）

所有應用程式依賴都安裝在容器中，不需要在本機安裝 Node.js 或 Python 套件。

### 1. 建立環境設定

```bash
cp .env.example .env
```

至少應修改以下敏感設定：

```env
POSTGRES_PASSWORD=請替換為安全密碼
DATABASE_URL=postgresql+asyncpg://voltscope:安全密碼@postgres:5432/voltscope
JWT_SECRET=請替換為足夠長度的隨機字串
DEFAULT_ADMIN_EMAIL=管理員信箱
DEFAULT_ADMIN_PASSWORD=管理員安全密碼
```

請勿將包含正式密鑰的 `.env` 提交到 Git。

### 2. 啟動開發環境

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

### 3. 建立資料表與初始資料

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec backend alembic upgrade head
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec -e PYTHONPATH=/app backend python scripts/seed.py
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec -e PYTHONPATH=/app backend python scripts/seed_content_sources.py
```

### 4. 開啟網站

| 功能 | 網址 |
| --- | --- |
| 中文首頁 | <http://localhost:3000/zh> |
| 英文首頁 | <http://localhost:3000/en> |
| 登入 | <http://localhost:3000/login> |
| 註冊 | <http://localhost:3000/register> |
| 管理後台 | <http://localhost:3000/admin> |
| FastAPI 文件（local 模式） | <http://localhost:8000/docs> |
| API 健康檢查 | <http://localhost:8000/> |

## 常用指令

```bash
make dev                    # 啟動開發環境
make down                   # 停止服務
make migrate                # 執行 Alembic migration
make seed                   # 建立管理員與基礎資料
make seed-content-sources   # 建立預設內容來源
make logs                   # 查看主要服務日誌
make backend-test           # 執行後端測試
make frontend-build         # 執行前端 production build
```

也可以不使用 Make，直接執行對應的 Docker Compose 指令。

## 環境變數

完整欄位請參考 [.env.example](.env.example)。主要設定分為以下幾組。

### 網站與資料庫

```env
APP_ENV=local
FRONTEND_URL=http://localhost:3000
API_BASE_URL=http://localhost:8000/api/v1
DATABASE_URL=postgresql+asyncpg://voltscope:change-me@postgres:5432/voltscope
REDIS_URL=redis://redis:6379/0
```

### Email

本機預設使用 `EMAIL_PROVIDER=console`。正式環境必須改用 SMTP，否則後端會拒絕寄送驗證信。

```env
EMAIL_PROVIDER=smtp
EMAIL_FROM=VoltScope <no-reply@example.com>
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_STARTTLS=true
SMTP_USE_TLS=false
SMTP_TIMEOUT_SECONDS=15
```

- Port 587：使用 `SMTP_STARTTLS=true`、`SMTP_USE_TLS=false`。
- Port 465：使用 `SMTP_STARTTLS=false`、`SMTP_USE_TLS=true`。

### Mistral 與內容產線

```env
MISTRAL_API_KEY=
MISTRAL_MODEL=mistral-large-latest
CONTENT_PIPELINE_DAILY_ENABLED=true
CONTENT_PIPELINE_AUTO_PUBLISH=false
CONTENT_PIPELINE_DAILY_MIN_ARTICLES=3
CONTENT_PIPELINE_DAILY_TAIWAN_MEDIA_MIN=1
CONTENT_PIPELINE_DAILY_INTERNATIONAL_MIN=2
CONTENT_PIPELINE_TIMEZONE=Asia/Taipei
CONTENT_PIPELINE_DAILY_HOUR=5
```

未設定 `MISTRAL_API_KEY` 時，系統仍可管理來源與候選內容，但不會執行 AI 產文。

## 內容產線流程

```text
已啟用來源
  → RSS / HTML 擷取
  → URL 去重與內容評分
  → 建立候選內容
  → 擷取可驗證事實
  → 產生繁中與英文草稿
  → 自動修訂
  → 品質檢查
  → 建立文章草稿或自動發布
  → 寫入每日執行報表
```

管理者可在以下頁面操作與監控：

- `/admin/content-sources`：管理來源及測試擷取。
- `/admin/content-candidates`：查看候選內容與人工產文。
- `/admin/content-pipeline`：人工執行每日流程或 dry run。
- `/admin/content-reports`：查看執行結果及失敗原因。

`CONTENT_PIPELINE_AUTO_PUBLISH=false` 是較保守的預設值。即使開啟自動發布，未通過品質檢查的文章也不會建立或發布。

## 正式環境部署

部署前請至少完成以下事項：

1. 將 `APP_ENV` 設為 `production`。
2. 修改 PostgreSQL、JWT 與管理員預設密碼。
3. 設定正式 `FRONTEND_URL` 與 `API_BASE_URL`。
4. 設定 SMTP，並將 `EMAIL_PROVIDER` 改為 `smtp`。
5. 視需求設定 `MISTRAL_API_KEY`。
6. 準備 Nginx TLS 憑證掛載目錄。
7. 在正式資料庫執行 `alembic upgrade head`。

啟動正式環境：

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend alembic upgrade head
```

## 備份與健康檢查

```bash
BACKUP_RETENTION_DAYS=14 ./infra/scripts/backup_postgres.sh
./infra/scripts/restore_postgres.sh backups/postgres-YYYYMMDDTHHMMSSZ.sql.gz
./infra/scripts/healthcheck.sh
```

正式環境應將資料庫備份排入外部排程，並將備份同步至不同主機或物件儲存空間。

## 安全注意事項

- 不要提交 `.env`、SMTP 密碼、Mistral API key 或正式資料庫密碼。
- 正式環境必須替換 `.env.example` 內所有示範密碼。
- 管理 API 會檢查 JWT 與管理員角色。
- 會員必須完成 Email 驗證後才能按讚與留言。
- AI 產文不儲存 API key 或完整 prompt 內容，但會保留模型、token、延遲與錯誤等工作紀錄。
- 上線前應依實際流量補充 rate limiting、集中式日誌與外部監控。

## 開發與貢獻

提交修改前，建議至少執行：

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm --no-deps backend sh -c "pip install -e '.[dev]' && pytest -q"
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm --no-deps frontend npm run typecheck
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm --no-deps frontend npm run build
```

歡迎透過 Issue 回報問題，或以 Pull Request 提交修正。PR 應說明修改目的、影響範圍、migration 需求與測試結果。

## 授權

目前儲存庫尚未提供開放原始碼授權條款。在加入 LICENSE 前，所有程式碼仍受著作權保護；如需使用、散布或商業部署，請先取得專案擁有者授權。

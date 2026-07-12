# VoltScope 電馳誌

VoltScope 是一套以電動車、充電基礎設施與智慧移動為主題的雙語內容平台。專案包含公開媒體網站、會員互動、內容管理後台，以及結合來源擷取、AI 輔助寫作與品質檢查的內容工作流。

這個儲存庫適合用來理解或建置：

- 繁體中文與英文的垂直媒體網站
- 具會員、留言、按讚與 Email 驗證的內容平台
- 可管理文章、廣告、會員與來源的 CMS
- 保留人工審核與來源追溯能力的 AI 內容產線
- 以 Docker Compose 部署的 Next.js + FastAPI 應用程式

> AI 產生的內容不應被視為事實來源。VoltScope 的工作流會保留來源、執行品質檢查，並預設由管理者審核後發布。

## 主要功能

### 公開網站

- 繁體中文與英文路由
- 首頁、文章列表、文章詳情、主題、標籤、作者與搜尋頁
- SEO metadata、canonical、hreflang、Open Graph 與 JSON-LD
- `sitemap.xml`、`robots.txt` 與 RSS
- 響應式版面與伺服器端渲染

### 會員系統

- 註冊、登入與 JWT 驗證
- SMTP Email 驗證
- 已驗證會員按讚與留言
- 會員停用、軟刪除與 Email 重新註冊

### 管理後台

- 儀表板與內容產線監控
- 文章新增、編輯、發布、封存與刪除
- TipTap 富文字編輯器與圖片管理
- 會員、廣告、來源與候選內容管理
- 產文工作、品質檢查結果與每日報表

### AI 內容工作流

- RSS 與 HTML 來源擷取
- URL 正規化、去重、評分與候選內容建立
- 使用 Mistral 整理事實並產生繁中、英文草稿
- 來源連結、必要欄位、文章長度及文字重疊率檢查
- 避免來源圖片 hotlink 與制式生成內容
- Redis 分散式鎖、人工執行、dry run 與每日排程

## 系統架構

```text
瀏覽器
  |
  v
Nginx (80/443、TLS、反向代理)
  |-- Next.js 15
  |     |-- 公開雙語網站
  |     |-- 會員登入與註冊
  |     `-- 管理後台
  |
  `-- FastAPI
        |-- Auth / CMS / Member API
        |-- AI 內容工作流
        |-- PostgreSQL 16：主要資料與工作紀錄
        |-- Redis 7：排程鎖與狀態
        |-- Mistral API：AI 輔助產文
        `-- SMTP：驗證信
```

所有服務透過 Docker Compose 的私有網路互通。正式環境由 Nginx 對外提供 HTTP/HTTPS，PostgreSQL 與 Redis 不直接公開。

## 技術棧

| 範圍 | 技術 |
| --- | --- |
| 前端 | Next.js 15、React 19、TypeScript、Tailwind CSS、Radix UI、TipTap |
| 後端 | FastAPI、SQLAlchemy 2 Async、Pydantic、Alembic |
| 資料層 | PostgreSQL 16、Redis 7 |
| AI | Mistral API |
| 驗證 | JWT、Argon2、Email verification |
| 基礎設施 | Docker Compose、Nginx、Let's Encrypt、Cloud Build |
| 測試 | Pytest、Ruff、TypeScript typecheck、Next.js production build |

## 目錄結構

```text
voltscope/
|-- backend/
|   |-- alembic/             # 資料庫 migration
|   |-- app/
|   |   |-- api/             # FastAPI routes
|   |   |-- core/            # 設定、錯誤與日誌
|   |   |-- db/              # SQLAlchemy session
|   |   |-- jobs/            # 排程工作
|   |   |-- models/          # ORM entities
|   |   |-- schemas/         # API schemas
|   |   |-- security/        # JWT 與密碼
|   |   `-- services/        # Email、CMS 與內容產線
|   |-- scripts/             # Seed 與維運腳本
|   `-- tests/
|-- frontend/
|   |-- app/                 # Next.js App Router
|   |-- components/          # 公開網站元件
|   |-- features/            # Auth 與後台功能
|   |-- lib/                 # API、i18n 與共用邏輯
|   |-- public/              # 公開資產
|   `-- src/components/ui/   # UI 基礎元件
|-- infra/
|   |-- nginx/               # 開發與正式 Nginx 設定
|   `-- scripts/             # 部署、備份、還原、健康檢查
|-- certbot/www/             # ACME webroot
|-- docker-compose.yml       # 共用服務
|-- docker-compose.dev.yml   # 開發環境 override
|-- docker-compose.prod.yml  # 正式環境 override
|-- cloudbuild.yaml          # Compute Engine 自動部署
`-- Makefile
```

## 快速開始

### 需求

- Docker Desktop 或 Docker Engine
- Docker Compose v2
- Git

Node.js、Python 與專案套件都在容器內安裝，不需要直接安裝到本機。

### 1. 建立 `.env`

儲存庫不包含可直接使用的 `.env`。請在專案根目錄建立 `.env`，至少設定：

```env
APP_ENV=local
FRONTEND_URL=http://localhost:3000
API_BASE_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1

POSTGRES_DB=voltscope
POSTGRES_USER=voltscope
POSTGRES_PASSWORD=replace-with-a-strong-password
DATABASE_URL=postgresql+asyncpg://voltscope:replace-with-a-strong-password@postgres:5432/voltscope
REDIS_URL=redis://redis:6379/0

JWT_SECRET=replace-with-a-long-random-secret
DEFAULT_ADMIN_EMAIL=admin@example.com
DEFAULT_ADMIN_PASSWORD=replace-with-a-strong-password

EMAIL_PROVIDER=console
EMAIL_FROM=VoltScope <no-reply@example.com>
```

`.env` 已被 Git 忽略。請勿提交密碼、SMTP 憑證、JWT secret 或 API key。

### 2. 啟動開發環境

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

  ## migration
  ```bash
  docker compose -f docker-compose.yml -f docker-compose.dev.yml exec backend alembic upgrade head
  ```

### 3. 初始化資料庫

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec backend alembic upgrade head
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec -e PYTHONPATH=/app backend python scripts/seed.py
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec -e PYTHONPATH=/app backend python scripts/seed_content_sources.py
```

### 4. 開啟服務

| 項目 | 網址 |
| --- | --- |
| 中文首頁 | <http://localhost/zh> |
| 英文首頁 | <http://localhost/en> |
| 登入 | <http://localhost/login> |
| 註冊 | <http://localhost/register> |
| 管理後台 | <http://localhost/admin> |
| FastAPI 文件（local） | <http://localhost:8000/docs> |
| Backend health | <http://localhost:8000/> |

開發環境也直接公開 Next.js 的 `3000` port；一般瀏覽建議從 Nginx 的 `http://localhost` 進入，以貼近正式路由。

## Email 設定

`EMAIL_PROVIDER=console` 只會將驗證信寫入 Backend 日誌。若要實際寄信，請改用 SMTP：

```env
EMAIL_PROVIDER=smtp
EMAIL_FROM=VoltScope <no-reply@example.com>
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=no-reply@example.com
SMTP_PASSWORD=replace-with-smtp-password
SMTP_STARTTLS=true
SMTP_USE_TLS=false
SMTP_TIMEOUT_SECONDS=15
```

- Port 587：`SMTP_STARTTLS=true`、`SMTP_USE_TLS=false`
- Port 465：`SMTP_STARTTLS=false`、`SMTP_USE_TLS=true`
- Microsoft 365 必須為寄件信箱啟用 Authenticated SMTP，或改用支援現代驗證的交易信件服務

更新 `.env` 後需重新建立 Backend 容器：

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --force-recreate backend
```

## AI 內容產線設定

```env
MISTRAL_API_KEY=
MISTRAL_MODEL=mistral-large-latest
MISTRAL_REQUEST_TIMEOUT_SECONDS=60
MISTRAL_MAX_RETRIES=3

CONTENT_PIPELINE_DAILY_ENABLED=true
CONTENT_PIPELINE_AUTO_PUBLISH=false
CONTENT_PIPELINE_DAILY_MIN_ARTICLES=3
CONTENT_PIPELINE_DAILY_TAIWAN_MEDIA_MIN=1
CONTENT_PIPELINE_DAILY_INTERNATIONAL_MIN=2
CONTENT_PIPELINE_TIMEZONE=Asia/Taipei
CONTENT_PIPELINE_DAILY_HOUR=5
```

未設定 `MISTRAL_API_KEY` 時，仍可管理來源與候選內容，但無法執行 AI 產文。建議維持 `CONTENT_PIPELINE_AUTO_PUBLISH=false`，由管理者完成審核。

內容流程：

```text
來源擷取
  -> URL 正規化與去重
  -> 候選內容評分
  -> 事實資料整理
  -> 雙語草稿生成
  -> 品質檢查與修訂
  -> 人工審核
  -> 發布與每日報表
```

## 測試與品質檢查

測試依賴同樣只安裝在一次性 Docker 容器：

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm backend \
  sh -lc "pip install --no-cache-dir -e '.[dev]' && pytest"

docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm frontend \
  sh -lc "npm ci && npm run typecheck && npm run build"
```

查看服務日誌：

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f backend frontend nginx
```

## 正式部署

正式環境使用 `docker-compose.prod.yml`：

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend alembic upgrade head
```

正式部署前至少確認：

1. `APP_ENV=production`
2. 使用高強度 PostgreSQL、JWT 與管理員密碼
3. `FRONTEND_URL`、`API_BASE_URL` 使用正式 HTTPS 網域
4. SMTP 與 Mistral 憑證只存在於主機 `.env` 或 Secret Manager
5. `/etc/letsencrypt` 已包含正式網域憑證
6. GCP Firewall 僅開放必要的 22、80、443
7. 每次部署後執行 `alembic upgrade head`

`cloudbuild.yaml` 示範在 push 到 `main` 後，由 Cloud Build 透過 OS Login 連入 Compute Engine，再執行 `/opt/voltscope/deploy.sh`。使用前應將其中的 GCP project、zone、instance 與服務帳號權限改為自己的環境。

## 備份與維運

```bash
BACKUP_RETENTION_DAYS=14 ./infra/scripts/backup_postgres.sh
./infra/scripts/restore_postgres.sh backups/postgres-YYYYMMDDTHHMMSSZ.sql.gz
./infra/scripts/healthcheck.sh
```

正式資料庫應定期備份至不同主機或物件儲存空間，並定期實際演練還原。

## 安全注意事項

- 不要提交 `.env`、資料庫備份、SMTP 密碼或 API key
- 正式環境必須使用 HTTPS，並定期續期憑證
- 管理 API 會驗證 JWT 與管理員角色
- 會員需完成 Email 驗證才能使用受保護的互動功能
- AI 內容應保留來源並通過品質檢查與人工審核
- 公開部署前應加入外部監控、集中式日誌與備份告警

若任何秘密曾進入 Git 歷史，僅刪除檔案並不足夠；應立即撤銷秘密並重寫儲存庫歷史。

## 商務合作

商務合作或專案洽詢：`services@voltscopes.com`

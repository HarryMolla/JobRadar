# Free Hosting, Deployment & Cloud Architecture Guide

JobRadar is engineered specifically to operate **100% free of charge**, within perpetual free-tier quotas of trusted developer services.

---

## 1. Cloud Scheduler: GitHub Actions

### Why GitHub Actions?
- **Quota**: GitHub Free accounts receive **2,000 Action runner minutes every month** for private repositories (unlimited for public repositories).
- **Execution Budget**:
  - The JobRadar collector completes an end-to-end collection run in **~1 to 2 minutes**.
  - Polling interval: **Every 45 minutes** (`*/45 * * * *`).
  - Monthly calculation: 32 runs/day × 30 days = 960 runs.
  - At 1.5 minutes average runtime per run, consumption is **~1,440 minutes/month** — comfortably within the 2,000 monthly free minutes.
- **Computer-Independent**: Your computer can be powered off, asleep, or disconnected; the cloud runner performs the scraping, matching, deduplication, and email dispatch automatically.

---

## 2. Persistent Storage: Supabase Free Tier

### Why Supabase?
- **Database Engine**: Production PostgreSQL 15.
- **Free Tier Quotas**:
  - **500 MB** database storage (holds roughly 150,000+ job listings).
  - **50,000** monthly active users.
  - **5 GB** bandwidth per month.
  - PostgREST auto-generated REST API (allowing secure client-side queries with Row-Level Security).
- **Setup**:
  1. Create a free account at [supabase.com](https://supabase.com).
  2. Create a new project named `jobradar`.
  3. Navigate to **SQL Editor** in the left sidebar.
  4. Paste and execute the contents of `scripts/setup_supabase.sql`.
  5. Go to **Project Settings → API** to obtain:
     - `Project URL` → `SUPABASE_URL`
     - `anon / public` key → `SUPABASE_ANON_KEY`
     - `service_role` key → `SUPABASE_SERVICE_ROLE_KEY` (keep secret!)

---

## 3. Email Alerts: Official Gmail API (OAuth 2.0)

### Why Official Gmail API?
- **No SMTP credential hacking**: Traditional SMTP with password or app-password requires insecure credential storage and frequently triggers Google account fraud flags.
- **Security**: Official OAuth 2.0 with the minimal scope: `https://www.googleapis.com/auth/gmail.send`.
- **Cost**: Completely free. Personal Gmail accounts support up to 500 emails/day; Google Workspace accounts support up to 2,000/day.

---

## 4. Chrome Extension: Manifest V3

### Architecture
- **Service Worker**: `background.js` uses `chrome.alarms` to poll the API every 30 minutes.
- **Direct Fallback**: If the local Python server is not running on `127.0.0.1:8765`, the extension can query Supabase's PostgREST API directly using the public `anon` key.
- **Native Notifications**: `chrome.notifications` triggers native OS notifications for newly detected jobs with direct action buttons (`Apply Now`).


# 🎯 JobRadar — Automated Job Search System & Chrome Extension

JobRadar is an automated, free-to-run job monitoring system designed specifically for **UI/UX Designers**, **Frontend Engineers**, and **WordPress Developers** living in **Ethiopia** (or seeking worldwide remote, visa sponsorship, or relocation opportunities).

The system continuously scans **~20 real job sources** every 6 hours, filters opportunities using transparent rule-based matching, eliminates duplicates, stores results in a persistent Git repository file (`data/job_state.json`), sends **Gmail email alerts**, and displays newly detected jobs inside a modern **Manifest V3 Chrome Extension** with instant "Apply" links.

> **Zero Paused Databases:** JobRadar persists its state directly inside the GitHub repository in `data/job_state.json`. It does not require Supabase or any external database that pauses after inactivity.

---

## 🌟 Key Features

- **Automated Cloud Collection (Every 6 Hours)**: Runs at 00:00, 06:00, 12:00, and 18:00 UTC on GitHub Actions (`0 */6 * * *`).
- **Minimal Actions Quota**: 4 runs/day × 30 days = 120 runs/month (~180 minutes total, using under **10%** of your GitHub 2,000 monthly free allowance).
- **20 Targeted Sources**: Real adapters for RemoteOK, Remotive, WeWorkRemotely, Jobicy, WorkingNomads, Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Recruitee, Personio, Workday, Wellfound, Y Combinator, Dynamite Jobs, RSS Feeds, and LinkedIn/Indeed alerts.
- **Ethiopia Remote & Relocation Intelligence**:
  - Automatically identifies worldwide remote jobs (`Remote Worldwide`, `Work from anywhere`).
  - Detects explicit visa sponsorship (`Visa sponsorship available`, `Will sponsor`).
  - Detects relocation packages (`Relocation assistance`).
  - Distinguishes restricted regional remote (`US only`, `EU only`) from genuinely global roles.
- **Strict 24-Hour Posting Age Filter**:
  - Enforced centrally in `JobMatcher` across every source adapter (`0 <= age <= MAX_POSTING_AGE_HOURS`, defaulting to `24` hours in UTC).
  - Separates original publication timestamps (`posted_at`) from scrape discovery (`detected_at`) and update timestamps (`updated_at`), excluding missing, ambiguous, date-only, or update-only listings by default.
  - Rechecked immediately before sending the Gmail digest so stale jobs never trigger notifications, while logging excluded reasons in `data/job_state.json`.
- **Transparent Match Engine**:
  - High weights for target roles (UI/UX, Product Design, Frontend, React, Next.js, WordPress).
  - Skill boosts for Figma, Design Systems, TypeScript, Tailwind, Accessibility (WCAG).
  - Hard exclusions for irrelevant jobs (Data science, DevOps, Sales, Medical, Mechanical, HR).
  - Human-readable reason for every match (e.g., *"Matched: Title is UI/UX Designer; Skill: Figma (+15); Remote Worldwide"*).
- **Persistent Git Repository Storage (`data/job_state.json`)**:
  - Replaces external databases with atomic Git-tracked state.
  - Automatically commits and pushes updated state when new jobs are detected.
  - Concurrency group prevents overlapping runs or merge conflicts.
- **Real Gmail Alerts (OAuth 2.0)**:
  - Official Gmail API integration with unattended token refresh.
  - Clean HTML digests with match score, company, location, matching reason, and direct 1-click apply links.
- **Manifest V3 Chrome Extension**:
  - Clean popup dashboard with tabs (All, New, Saved, Applied).
  - Native Chrome desktop notifications for newly detected opportunities.
  - **Direct Cloud Mode**: Can fetch `data/job_state.json` directly from your GitHub repository with zero local server running.

---

## 🏗️ Architecture & Free Quotas

```
┌────────────────────────────────────────────────────────┐
│  GitHub Actions (Runs every 6 hours: 0 */6 * * *)      │
│  • Consumes ~180 of 2,000 free runner mins/month (~9%) │
│  • Executes Python backend collector on ubuntu-latest  │
└──────────────────────────┬─────────────────────────────┘
                           │
       ┌───────────────────┴───────────────────┐
       ▼                                       ▼
┌───────────────────────────────┐   ┌──────────────────────────────┐
│  20+ Real Source Adapters     │   │  Rule-Based Matcher Engine   │
│  (APIs, ATS feeds, RSS, CXS)  │──>│  (Titles, Skills, Geo rules) │
└───────────────────────────────┘   └──────────────┬───────────────┘
                                                   │
                                                   ▼
┌───────────────────────────────┐   ┌──────────────────────────────┐
│  Gmail API (OAuth 2.0)        │<──│  Git Repository State        │
│  Sends email digests (Free)   │   │  data/job_state.json         │
└───────────────────────────────┘   └──────────────┬───────────────┘
                                                   │
                                                   ▼
                                    ┌──────────────────────────────┐
                                    │  Chrome Extension (MV3)      │
                                    │  Direct Cloud or Local Sync  │
                                    └──────────────────────────────┘
```

---

## 📊 Actions Minutes & 6-Hour Schedule Budget

| Metric | Calculation | Notes |
|---|---|---|
| **Cron Schedule** | `0 */6 * * *` | 00:00, 06:00, 12:00, 18:00 UTC |
| **Runs per Day** | 4 runs | Every 6 hours |
| **Runs per Month** | 120 runs | 4 × 30 days |
| **Average Run Time** | ~1.5 minutes | With cached pip dependencies on `ubuntu-latest` |
| **Monthly Minutes** | **~180 minutes** | Range: 150 – 240 minutes |
| **Free Allowance** | **2,000 minutes/month** | Private repositories (Unlimited on public) |
| **Quota Used** | **~9% to 12%** | Leaves 1,760+ free minutes every month |

> **Scheduling Latency Notice:** GitHub Actions scheduled workflows are queued on shared cloud runners. During peak global traffic hours, start times may experience a delay of 3–15 minutes. This is standard across GitHub Actions and does not affect collection accuracy.

---

## 📋 Implemented Job Source Integrations

| # | Source | Adapter | Integration Method | Status |
|---|--------|---------|--------------------|--------|
| 1 | **Remote OK** | `remoteok.py` | Official public JSON API (`remoteok.com/api`) | ✅ Active |
| 2 | **Remotive** | `remotive.py` | Public API (`remotive.com/api/remote-jobs`) | ✅ Active |
| 3 | **We Work Remotely** | `weworkremotely.py` | Public category RSS feeds | ✅ Active |
| 4 | **Jobicy** | `jobicy.py` | Official API v2 (`jobicy.com/api/v2/remote-jobs`) | ✅ Active |
| 5 | **Working Nomads** | `workingnomads.py` | Public exposed jobs API (`workingnomads.com/api`) | ✅ Active |
| 6 | **Greenhouse ATS** | `greenhouse.py` | Public board APIs (Figma, Notion, Vercel, etc.) | ✅ Active |
| 7 | **Lever ATS** | `lever.py` | Public posting APIs (Netflix, Stripe, Cloudflare, etc.) | ✅ Active |
| 8 | **Ashby ATS** | `ashby.py` | Public job board APIs (Linear, Ramp, Vercel, etc.) | ✅ Active |
| 9 | **SmartRecruiters** | `smartrecruiters.py` | Public company postings API | ✅ Active |
| 10 | **Workable ATS** | `workable.py` | Public candidate board API (`apply.workable.com`) | ✅ Active |
| 11 | **Recruitee ATS** | `recruitee.py` | Company career subdomain JSON API | ✅ Active |
| 12 | **Personio ATS** | `personio.py` | Open career XML feeds (`jobs.personio.de/xml`) | ✅ Active |
| 13 | **Workday ATS** | `workday.py` | Standard CXS JSON search API (`wday/cxs/...`) | ✅ Active |
| 14 | **Dynamite Jobs** | `dynamitejobs.py` | Public RSS feeds | ✅ Active |
| 15 | **Wellfound (AngelList)** | `wellfound.py` | Public GraphQL endpoint (graceful skip on block) | ✅ Active |
| 16 | **Y Combinator** | `ycombinator.py` | Public startup jobs search endpoint | ✅ Active |
| 17 | **RSS & Atom Feeds** | `rss_feeds.py` | Generic configurable RSS parser | ✅ Active |
| 18 | **LinkedIn & Indeed (incl. UAE)** | `email_alerts.py` | Supported email alert parser (via Gmail) | ✅ Needs Gmail OAuth |
| 19 | **SawaTech (UAE)** | `sawatech.py` | Public WordPress RSS (`/jobs/feed/`) + JSON-LD | ✅ Active |
| 20 | **Prism Digital (UAE)** | `prism_digital.py` | Public Next.js `__NEXT_DATA__` careers feed (`createdAt` verified) | ✅ Active |
| 21 | **Hays UAE** | `hays_uae.py` | Public `/job-search` + Schema.org `JobPosting` JSON-LD (24h UTC timestamps enforced) | ✅ Active |

### 🇦🇪 UAE Job Sources, Target Roles & Benefits

- **Automated UAE Adapters (3):** `SawaTech`, `Prism Digital`, and `Hays UAE` (permitted public RSS / Next.js JSON / Schema.org `JobPosting` endpoints, strictly subject to the central 24-hour UTC `posted_at` rule — date-only strings like `YYYY-MM-DD` are marked unreliable and excluded from notifications).
- **Email-Alert & Manual-Search UAE Sources (16):** `Bayt`, `Indeed UAE`, `Dubizzle Jobs`, `GulfTalent`, `Naukrigulf`, `LinkedIn Jobs UAE`, `Foundit Gulf`, `Glassdoor UAE`, `Laimoon`, `Gulf News`, `Dubai Careers`, `Abu Dhabi TAMM`, `UAE FAHR`, `Sharjah HR`, `Michael Page UAE`, and `Emirates Group` are tracked in the **🇦🇪 UAE 19** extension tab and `/sources/uae` API with instant UAE keyword + Emirate manual search links (without bypassing Cloudflare/Akamai WAF blocks, UAE PASS logins, or `robots.txt` rules).
- **Expanded Target Roles:** UI/UX, Product, Web, Graphic, and Brand & Visual Designers; Frontend, React, Next.js, WordPress, and Web Developers; Digital Marketing, SEO, Social Media, and Digital Content Creators.
- **Separate Benefit Verification:** Jobs report `visa_sponsorship`, `relocation_support`, `flight_covered`, and `accommodation_covered` independently (`confirmed`, `not_confirmed`, or `unavailable`) across backend scoring, Gmail alerts, and Chrome extension badges — never assuming unmentioned benefits are covered.

---

## 🚀 Setup & Deployment Guide

### Step 1: Push Changes to GitHub

Open PowerShell in your project directory:

```powershell
cd c:\Users\hp\Downloads\JobMe
git add .
git commit -m "Update: 6-hour schedule, Git repository state storage, and cloud optimization"
git push origin main
```

---

### Step 2: Configure Gmail API Alerts (Avoiding the 7-Day Expiry)

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and create a project called **JobRadar Alerts**.
2. Go to **APIs & Services → Enable APIs and Services** and enable the **Gmail API**.
3. Go to **APIs & Services → OAuth consent screen**:
   - User Type: **External**.
   - App Name: `JobRadar`.
   - Support Email: your Gmail address.
   - **Crucial Setting (Preventing 7-Day Token Expiry):**
     Under **Publishing status**, click **"PUBLISH APP"** to set the app to **"In production"**.
     *(You do NOT need Google verification for personal use. Leaving verification unsubmitted while in production ensures your refresh token never expires after 7 days!)*
4. Go to **Credentials → Create Credentials → OAuth client ID**:
   - Application type: **Desktop app**.
   - Download the file and rename it to `credentials.json` inside `c:\Users\hp\Downloads\JobMe\`.
5. Run the authorization script locally once:
   ```powershell
   python scripts/gmail_auth.py
   ```
   *(Or if using Node.js, ensure Python is installed with `pip install -r requirements.txt`)*
6. Your browser will prompt you to authorize JobRadar. A test email will be sent to your inbox to confirm delivery, and `token.json` will be generated.

---

### Step 3: Add Secrets to GitHub

In your GitHub repository (**Settings → Secrets and variables → Actions**), add:

| Secret Name | Value | Description |
|---|---|---|
| `NOTIFICATION_EMAIL` | `your-email@gmail.com` | Destination email for job alerts |
| `GMAIL_CREDENTIALS_JSON` | Content of `credentials.json` | Google Cloud OAuth Client ID & Secret |
| `GMAIL_TOKEN_JSON` | Content of `token.json` | OAuth refresh & access tokens |

Optional repository **Variables** (**Settings → Secrets and variables → Actions → Variables**):
- `MAX_POSTING_AGE_HOURS`: Maximum verified job age in UTC hours (default: `24`).

*(Optional Telegram fallback: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`)*

---

### Step 4: Run the First Cloud Scan Manually

1. Go to your repository on GitHub.
2. Click the **Actions** tab at the top.
3. In the left sidebar, click **Job Collector**.
4. Click the **Run workflow** dropdown on the right and click **Run workflow**.
5. Once the run completes (~1.5 minutes):
   - Check your Gmail inbox for your first job alert digest!
   - In your repository, click `data/job_state.json` to verify the detected jobs have been saved.

---

### Step 5: Install & Use the Chrome Extension

1. Open Google Chrome and navigate to `chrome://extensions`.
2. Toggle **Developer mode** (top-right) to **ON**.
3. Click **Load unpacked** (top-left) and select:
   ```
   C:\Users\hp\Downloads\JobMe\extension
   ```
4. Click the gear icon in the extension to open **Settings**:
   - **Direct Cloud Mode (No server needed)**: Enter your GitHub repository (`HarryMolla/JobRadar`) to fetch live jobs directly from GitHub!
   - **Local Server Mode**: Or run `node scripts/server.js` and connect to `http://127.0.0.1:8765`.
5. Click **Sync** (🔄) to view new jobs, save favorites, mark applied, or click direct **Apply →** links.

---

## 🧪 Automated Testing

Run the test suite to verify matching, deduplication, and repository state storage:

```powershell
pytest backend/tests -v
```

All tests pass without requiring any external database connections.

---

## 🛠️ Troubleshooting & Rollback

- **GitHub Workflow Permission Error (`403 Resource not accessible by integration`)**:
  - Go to your repo **Settings → Actions → General → Workflow permissions**.
  - Select **"Read and write permissions"** and click **Save**.
- **Gmail Authorization Error (`Token expired or revoked`)**:
  - Ensure the OAuth consent screen publishing status is set to **"In production"** in Google Cloud Console.
  - Re-run `python scripts/gmail_auth.py` and update `GMAIL_TOKEN_JSON` in GitHub Secrets.
- **Rollback Procedure**:
  - If you ever need to restore previous Supabase configurations, check out the previous commit:
    `git checkout b2c58c5 -- backend/core/storage.py` or review commit history via `git log`.

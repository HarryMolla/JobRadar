# 🎯 JobRadar — Automated Job Search System & Chrome Extension

JobRadar is an automated, free-to-run job monitoring system designed specifically for **UI/UX Designers**, **Frontend Engineers**, and **WordPress Developers** living in **Ethiopia** (or seeking worldwide remote, visa sponsorship, or relocation opportunities).

The system continuously scans **~20 real job sources**, filters out irrelevant positions using transparent rule-based scoring, eliminates duplicates, stores results in a persistent database (Supabase), sends **Gmail email alerts**, and displays newly detected jobs inside a modern **Manifest V3 Chrome Extension** with instant "Apply" links.

---

## 🌟 Key Features

- **Automated Cloud Collection**: Runs every 45 minutes on GitHub Actions without needing your computer on.
- **20 Targeted Sources**: Real adapters for RemoteOK, Remotive, WeWorkRemotely, Jobicy, WorkingNomads, Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Recruitee, Personio, Workday, Wellfound, Y Combinator, Dynamite Jobs, RSS Feeds, and LinkedIn/Indeed alerts.
- **Ethiopia Remote & Relocation Intelligence**:
  - Automatically scores worldwide remote jobs (`Remote Worldwide`, `Work from anywhere`).
  - Detects explicit visa sponsorship (`Visa sponsorship available`, `Will sponsor`).
  - Detects relocation packages (`Relocation assistance`).
  - Differentiates restricted regional remote (`US only`, `EU only`) from truly international positions.
- **Transparent Match Engine**:
  - High weights for target titles (UI/UX, Product Design, Frontend, React, Next.js, WordPress).
  - Skill boosts for Figma, Design Systems, TypeScript, Tailwind, Accessibility (WCAG).
  - Automatic exclusion of irrelevant jobs (Data science, DevOps, Sales, Medical, Mechanical, HR).
  - Human-readable reason for every match (e.g., *"Matched: Title is UI/UX Designer; Skill: Figma (+15); Remote Worldwide"*).
- **Persistent Storage & Deduplication**:
  - Stored in PostgreSQL on **Supabase Free Tier** (holds 150,000+ jobs within 500 MB quota).
  - Deduplicates via source ID and title/company fingerprint — never notifies repeatedly for the same job.
  - Local JSON fallback for offline local testing (`jobs_fallback.json`).
- **Real Gmail Alerts**:
  - Direct integration via official **Gmail API (OAuth 2.0)**.
  - Sends clean HTML digests with match score, company, location, and direct 1-click apply button.
- **Polished Chrome Extension (Manifest V3)**:
  - Clean popup dashboard with tabs (All, New, Saved, Applied).
  - Native Chrome desktop notifications for newly detected opportunities.
  - Search by keywords, filter by category (Design / Frontend / WordPress) or location (Worldwide / Sponsored).
  - Direct 1-click status actions (Save, Mark Applied, Dismiss).

---

## 🏗️ Architecture & Free Quotas

```
┌────────────────────────────────────────────────────────┐
│  GitHub Actions (Cloud Scheduler - Runs every 45m)     │
│  • Consumes ~1,440 of 2,000 free runner mins/month     │
│  • Executes Python backend collector                   │
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
│  Gmail API (OAuth 2.0)        │<──│  Supabase (Free PostgreSQL)  │
│  Sends email digests (Free)   │   │  Stores jobs & run logs      │
└───────────────────────────────┘   └──────────────┬───────────────┘
                                                   │
                                                   ▼
                                    ┌──────────────────────────────┐
                                    │  Chrome Extension (MV3)      │
                                    │  Native desktop alerts & UI  │
                                    └──────────────────────────────┘
```

---

## 📋 Implemented Job Source Integrations

| # | Source | Adapter | Integration Method | Status |
|---|--------|---------|--------------------|--------|
| 1 | **Remote OK** | `remoteok.py` | Official public JSON API (`remoteok.com/api`) | ✅ Working |
| 2 | **Remotive** | `remotive.py` | Public API (`remotive.com/api/remote-jobs`) | ✅ Working |
| 3 | **We Work Remotely** | `weworkremotely.py` | Public category RSS feeds | ✅ Working |
| 4 | **Jobicy** | `jobicy.py` | Official API v2 (`jobicy.com/api/v2/remote-jobs`) | ✅ Working |
| 5 | **Working Nomads** | `workingnomads.py` | Public exposed jobs API (`workingnomads.com/api`) | ✅ Working |
| 6 | **Greenhouse ATS** | `greenhouse.py` | Public board APIs (Figma, Notion, Vercel, etc.) | ✅ Working |
| 7 | **Lever ATS** | `lever.py` | Public posting APIs (Netflix, Stripe, Cloudflare, etc.) | ✅ Working |
| 8 | **Ashby ATS** | `ashby.py` | Public job board APIs (Linear, Ramp, Vercel, etc.) | ✅ Working |
| 9 | **SmartRecruiters** | `smartrecruiters.py` | Public company postings API | ✅ Working |
| 10 | **Workable ATS** | `workable.py` | Public candidate board API (`apply.workable.com`) | ✅ Working |
| 11 | **Recruitee ATS** | `recruitee.py` | Company career subdomain JSON API | ✅ Working |
| 12 | **Personio ATS** | `personio.py` | Open career XML feeds (`jobs.personio.de/xml`) | ✅ Working |
| 13 | **Workday ATS** | `workday.py` | Standard CXS JSON search API (`wday/cxs/...`) | ✅ Working |
| 14 | **Dynamite Jobs** | `dynamitejobs.py` | Public RSS feeds | ✅ Working |
| 15 | **Wellfound (AngelList)** | `wellfound.py` | Public GraphQL endpoint (graceful skip on block) | ✅ Working |
| 16 | **Y Combinator** | `ycombinator.py` | Public startup jobs search endpoint | ✅ Working |
| 17 | **RSS & Atom Feeds** | `rss_feeds.py` | Generic configurable RSS parser | ✅ Working |
| 18 | **LinkedIn & Indeed** | `email_alerts.py` | Supported email alert parser (via Gmail) | ✅ Needs Gmail OAuth |

---

## 🚀 Step-by-Step Setup Guide (Windows)

### Prerequisites
1. **Python 3.11+**: Download from [python.org](https://www.python.org/downloads/) (check *"Add python.exe to PATH"* during installation).
2. **Git**: Download from [git-scm.com](https://git-scm.com/).
3. **Google Chrome**: For the extension.

---

### Step 1: Clone and Install Dependencies

Open PowerShell in your project directory:

```powershell
cd c:\Users\hp\Downloads\JobMe

# Create and activate a Python virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install required dependencies
pip install -r requirements.txt
```

---

### Step 2: Configure Free Persistent Storage (Supabase)

1. Sign up for a free account at [supabase.com](https://supabase.com).
2. Create a new project called **JobRadar** (select the nearest region to you).
3. In the Supabase sidebar, click on **SQL Editor**.
4. Open [scripts/setup_supabase.sql](file:///c:/Users/hp/Downloads/JobMe/scripts/setup_supabase.sql), copy all lines, paste them into the SQL editor, and click **Run**.
5. Go to **Project Settings → API** and copy:
   - `Project URL`
   - `anon public` key
   - `service_role` key (keep secret!)
6. Create your local `.env` file from the template:
   ```powershell
   Copy-Item .env.example .env
   ```
7. Open `.env` and fill in your `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `SUPABASE_SERVICE_ROLE_KEY`.

---

### Step 3: Run the Collector Locally (Verification)

Test the collection engine in dry-run mode (no database or emails required):

```powershell
# Run a dry-run against live sources
python scripts/run_collector.py --dry-run

# Or test a single specific adapter:
python scripts/run_collector.py --dry-run --source remoteok
python scripts/run_collector.py --dry-run --source greenhouse
```

To run a full collection and store matches into Supabase:
```powershell
python scripts/run_collector.py
```

---

### Step 4: Configure Free Gmail Alerts (OAuth 2.0)

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project named **JobRadar Alerts**.
3. In the sidebar, go to **APIs & Services → Enable APIs and Services** and enable the **Gmail API**.
4. Go to **APIs & Services → OAuth consent screen**:
   - Choose **External** user type.
   - Enter your email for support and developer contact.
   - On the **Test users** screen, add your personal Gmail address.
5. Go to **APIs & Services → Credentials**:
   - Click **Create Credentials → OAuth client ID**.
   - Application type: **Desktop app**.
   - Download the JSON file and rename it to `credentials.json` in `c:\Users\hp\Downloads\JobMe\`.
6. Run the local authentication helper:
   ```powershell
   python scripts/gmail_auth.py
   ```
7. Your browser will prompt you to authorize JobRadar to send notification emails.
8. `token.json` will be generated in your project folder.
9. Follow the on-screen prompt to send a test email to your inbox to confirm delivery!

---

### Step 5: Install the Chrome Extension

1. Open Google Chrome and navigate to:
   ```
   chrome://extensions
   ```
2. In the top-right corner, toggle **Developer mode** to **ON**.
3. Click the **Load unpacked** button in the top-left corner.
4. Select the directory:
   ```
   c:\Users\hp\Downloads\JobMe\extension
   ```
5. The **JobRadar** icon (🎯) will appear in your Chrome toolbar!
6. Click the extension icon to open the dashboard.
7. Click the gear icon to open **Settings** and test the connection.

---

### Step 6: Start the Local API Server (for Chrome Extension)

The extension communicates with your local job database via the lightweight API server. You can run either the **Node.js** version (0 dependencies) or the **Python** version:

```powershell
# Option A: Zero-dependency Node.js server (Instant start)
node scripts/server.js

# Option B: Python server
python -m backend.api.server
```
The server will start on `http://127.0.0.1:8765`. 
*(Note: If the server is stopped, the extension automatically falls back to querying Supabase directly if you entered your Supabase URL & Anon Key in the extension Settings!)*

To fetch real live job listings immediately without Python, you can also run:
```powershell
node scripts/fetch_live.js
```

---

### Step 7: Set Up 24/7 Cloud Automation (GitHub Actions)

To let JobRadar run automatically in the cloud without keeping your computer on:

1. Create a **private** repository on [GitHub](https://github.com/new).
2. Initialize and push your code:
   ```powershell
   git init
   git add .
   git commit -m "Initial commit of JobRadar"
   git remote add origin https://github.com/<your-username>/JobRadar.git
   git push -u origin main
   ```
3. In your GitHub repository, go to **Settings → Secrets and variables → Actions**.
4. Under **Repository secrets**, click **New repository secret** and add:
   - `SUPABASE_URL`: Your Supabase URL.
   - `SUPABASE_SERVICE_ROLE_KEY`: Your Supabase service role key.
   - `NOTIFICATION_EMAIL`: Your Gmail address where alerts should be sent.
   - `GMAIL_CREDENTIALS_JSON`: The full contents of your `credentials.json`.
   - `GMAIL_TOKEN_JSON`: The full contents of your `token.json`.
5. Under **Variables**, add:
   - `MIN_MATCH_SCORE`: `40`
   - `NOTIFICATION_MIN_SCORE`: `50`
6. Click on the **Actions** tab in GitHub and click **Job Collector → Run workflow** to test it in the cloud!

---

## 🧪 Running the Automated Test Suite

JobRadar includes unit tests covering job models, keyword matching, skill scoring, deduplication, notifications, and adapter normalizing:

```powershell
pytest backend/tests -v
```

---

## ⚙️ Customizing Search Roles & Scores

You can customize keyword weights and thresholds in [backend/core/matcher.py](file:///c:/Users/hp/Downloads/JobMe/backend/core/matcher.py):

- **Minimum score to save**: Set in `.env` (`MIN_MATCH_SCORE=40`).
- **Minimum score to email**: Set in `.env` (`NOTIFICATION_MIN_SCORE=50`).
- **Adding new company boards**: Edit [sources_config.yaml](file:///c:/Users/hp/Downloads/JobMe/sources_config.yaml) — no Python code changes needed!

---

## 🛡️ Security & Privacy

- **No hardcoded secrets**: All tokens, keys, and credentials are read strictly from `.env` or GitHub Secrets.
- **`.gitignore` protection**: Prevents accidental commits of `credentials.json`, `token.json`, `.env`, and local SQLite/JSON files.
- **Least-privilege permissions**: The Chrome extension only requests `notifications`, `storage`, and `alarms`. It does not request access to read your visited web pages or browser history.
- **No CAPTCHA bypasses**: Respects `robots.txt`, implements polite request rate-limiting, and uses supported APIs.


/**
 * Live Job Fetcher (Node.js version).
 * Fetches real, live listings directly from public APIs (RemoteOK, Remotive, Jobicy),
 * runs the matching & scoring engine, and updates jobs_fallback.json.
 *
 * Run with: node scripts/fetch_live.js
 */

const fs = require('fs');
const path = require('path');

const PRIMARY_DB = path.join(__dirname, '..', 'data', 'job_state.json');
const DB_FILE = fs.existsSync(PRIMARY_DB) ? PRIMARY_DB : (fs.existsSync(path.join(__dirname, '..', 'jobs_fallback.json')) ? path.join(__dirname, '..', 'jobs_fallback.json') : PRIMARY_DB);
const MAX_POSTING_AGE_HOURS = Number(process.env.MAX_POSTING_AGE_HOURS || 24);

// --- Matching configuration ---
const DESIGN_KEYWORDS = [
  'ui/ux', 'ui ux', 'ux/ui', 'ux designer', 'ui designer',
  'product designer', 'web designer', 'interaction designer',
  'visual designer', 'figma designer', 'design engineer'
];

const FRONTEND_KEYWORDS = [
  'frontend', 'front-end', 'front end',
  'react developer', 'react engineer',
  'javascript developer', 'javascript engineer',
  'typescript developer', 'typescript engineer',
  'next.js', 'nextjs',
  'ui developer', 'web developer'
];

const WORDPRESS_KEYWORDS = ['wordpress', 'wp developer', 'wp engineer', 'elementor'];

const EXCLUSION_KEYWORDS = [
  'data scientist', 'machine learning', 'devops', 'sre', 'sales',
  'account executive', 'marketing manager', 'hr manager', 'recruiter',
  'nurse', 'doctor', 'mechanical engineer', 'electrical engineer'
];

const SKILLS = {
  'figma': 15,
  'prototyping': 8,
  'wireframe': 8,
  'design system': 12,
  'responsive design': 8,
  'accessibility': 8,
  'wcag': 10,
  'react': 12,
  'typescript': 10,
  'javascript': 8,
  'next.js': 10,
  'nextjs': 10,
  'html': 6,
  'css': 6,
  'tailwind': 8,
  'wordpress': 8,
};

function parseUtcTimestamp(rawVal) {
  if (rawVal === null || rawVal === undefined) {
    return { dt: null, raw: '', reliable: false };
  }
  if (typeof rawVal === 'number' && Number.isFinite(rawVal)) {
    const ms = rawVal > 1e12 ? rawVal : rawVal * 1000;
    const d = new Date(ms);
    return Number.isNaN(d.getTime()) ? { dt: null, raw: String(rawVal), reliable: false } : { dt: d, raw: String(rawVal), reliable: true };
  }
  const text = String(rawVal).trim();
  if (!text) return { dt: null, raw: '', reliable: false };
  // Reject date-only YYYY-MM-DD or relative phrases ("today", "2 days ago") as ambiguous
  if (/^\d{4}-\d{2}-\d{2}$/.test(text) || /\b(ago|today|yesterday)\b/i.test(text)) {
    return { dt: null, raw: text, reliable: false };
  }
  // Numeric unix timestamp string
  if (/^\d{10,13}$/.test(text)) {
    const num = Number(text);
    const ms = text.length > 10 ? num : num * 1000;
    const d = new Date(ms);
    return Number.isNaN(d.getTime()) ? { dt: null, raw: text, reliable: false } : { dt: d, raw: text, reliable: true };
  }
  // ISO without timezone offset (e.g. "2026-11-11T10:00:00") -> treat as UTC since RemoteOK/Remotive/Jobicy use UTC
  let normalized = text;
  if (/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(text)) {
    normalized = text.replace(' ', 'T') + 'Z';
  }
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) {
    return { dt: null, raw: text, reliable: false };
  }
  return { dt: parsed, raw: text, reliable: true };
}

function evaluatePostingAge(job, now = new Date()) {
  const { dt, raw, reliable } = parseUtcTimestamp(job.posted_at);
  if (!dt || !reliable) {
    return { passed: false, ageHours: null, rawTs: raw, postedAtIso: null, reason: 'Excluded: missing or unreliable original posting timestamp' };
  }
  const ageHours = (now.getTime() - dt.getTime()) / 3600000;
  if (ageHours < 0) {
    return { passed: false, ageHours: Number(ageHours.toFixed(2)), rawTs: raw, postedAtIso: dt.toISOString(), reason: `Excluded: posting timestamp is in the future (${ageHours.toFixed(2)}h)` };
  }
  if (ageHours > MAX_POSTING_AGE_HOURS) {
    return { passed: false, ageHours: Number(ageHours.toFixed(2)), rawTs: raw, postedAtIso: dt.toISOString(), reason: `Excluded: posted ${ageHours.toFixed(1)}h ago (exceeds ${MAX_POSTING_AGE_HOURS}h limit)` };
  }
  return { passed: true, ageHours: Number(ageHours.toFixed(2)), rawTs: raw, postedAtIso: dt.toISOString(), reason: '' };
}

function scoreJob(job) {
  const ageCheck = evaluatePostingAge(job);
  if (!ageCheck.passed) {
    return {
      score: 0,
      reasons: [ageCheck.reason],
      category: 'irrelevant',
      ageCheck,
    };
  }

  const title = (job.title || '').toLowerCase();
  const desc = (job.description || '').toLowerCase();
  const combined = `${title} ${desc} ${(job.location || '').toLowerCase()}`;

  // Check exclusions
  for (const excl of EXCLUSION_KEYWORDS) {
    if (title.includes(excl)) {
      return { score: 0, reasons: [`Excluded: title contains "${excl}"`], category: 'irrelevant', ageCheck };
    }
  }

  let score = 0;
  const reasons = [];
  let category = 'irrelevant';

  // Title matching
  for (const kw of DESIGN_KEYWORDS) {
    if (title.includes(kw)) {
      score += 60;
      reasons.push(`Title matches design role: "${kw}"`);
      category = 'design';
      break;
    }
  }

  if (category === 'irrelevant') {
    for (const kw of FRONTEND_KEYWORDS) {
      if (title.includes(kw)) {
        score += 55;
        reasons.push(`Title matches frontend role: "${kw}"`);
        category = 'frontend';
        break;
      }
    }
  }

  if (category === 'irrelevant') {
    for (const kw of WORDPRESS_KEYWORDS) {
      if (title.includes(kw)) {
        score += 55;
        reasons.push(`Title matches WordPress role: "${kw}"`);
        category = 'wordpress';
        break;
      }
    }
  }

  if (score === 0) {
    return { score: 0, reasons: [], category: 'irrelevant' };
  }

  // Skills
  let skillBonus = 0;
  for (const [skill, pts] of Object.entries(SKILLS)) {
    if (combined.includes(skill)) {
      skillBonus += pts;
      reasons.push(`Skill: ${skill} (+${pts})`);
      if (reasons.length >= 5) break;
    }
  }
  score += Math.min(skillBonus, 35);

  // Remote & Ethiopia eligibility detection
  let remoteType = 'unknown';
  if (combined.includes('worldwide') || combined.includes('anywhere in the world') || combined.includes('global remote') || combined.includes('100% remote')) {
    remoteType = 'remote_worldwide';
    score += 10;
    reasons.push('Remote worldwide — eligible from Ethiopia');
  } else if (combined.includes('us only') || combined.includes('usa only') || combined.includes('europe only')) {
    remoteType = 'remote_restricted';
    score = Math.max(0, score - 10);
    reasons.push('Remote restricted — may not include Ethiopia');
  } else if (combined.includes('remote')) {
    remoteType = 'remote_worldwide'; // default permissive
  }

  // Sponsorship & Relocation
  let sponsorship = 'unknown';
  if (combined.includes('visa sponsorship') || combined.includes('will sponsor') || combined.includes('work permit')) {
    sponsorship = 'sponsored';
    score += 15;
    reasons.push('Visa sponsorship explicitly offered');
  }

  const relocation = combined.includes('relocation package') || combined.includes('relocation assistance');
  if (relocation) {
    score += 8;
    reasons.push('Relocation package mentioned');
  }

  score = Math.min(100, Math.max(0, score));

  return {
    score,
    reasons: reasons.slice(0, 6),
    category,
    remoteType,
    sponsorship,
    relocation,
    ageCheck
  };
}

// --- Live fetchers ---
function isValidJobUrl(rawUrl) {
  if (!rawUrl || typeof rawUrl !== 'string') return false;
  const trimmed = rawUrl.trim();
  if (!trimmed || trimmed.startsWith('#')) return false;
  try {
    const parsed = new URL(trimmed);
    if (!['http:', 'https:'].includes(parsed.protocol)) return false;
    const normPath = parsed.pathname.replace(/^\/+|\/+$/g, '').toLowerCase();
    const genericPaths = new Set([
      '', 'apply', 'jobs', 'job', 'careers', 'career', 'vacancies', 'openings',
      'job-search', 'search', 'search-and-apply', 'remote-jobs', 'j', 'o', 'job-detail'
    ]);
    const hasJobIdParam = ['id', 'jobid', 'job_id', 'gh_jid', 'jk', 'vjk', 'postingid'].some((k) => parsed.searchParams.has(k));
    if (hasJobIdParam) return true;
    if (genericPaths.has(normPath)) return false;
    if (['/jobs', '/careers', '/job-search', '/search-and-apply', '/j', '/job', '/o'].some((s) => normPath.endsWith(s))) {
      return false;
    }
    return true;
  } catch {
    return false;
  }
}

async function fetchRemoteOK() {
  console.log('Fetching live jobs from RemoteOK API...');
  try {
    const res = await fetch('https://remoteok.com/api', {
      headers: { 'User-Agent': 'JobRadar/1.0 (Personal Job Search)' }
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const rawJobs = Array.isArray(data) ? data.filter(d => d && d.id) : [];

    return rawJobs.map(raw => {
      const detailUrl = isValidJobUrl(raw.url) ? raw.url : '';
      const applyUrl = isValidJobUrl(raw.apply_url) ? raw.apply_url : '';
      return {
        source: 'remoteok',
        source_name: 'Remote OK',
        source_id: String(raw.id),
        url: applyUrl || detailUrl,
        source_job_url: detailUrl,
        apply_url: applyUrl,
        title: raw.position || '',
        company: raw.company || '',
        location: raw.location || 'Remote Worldwide',
        description: `${(raw.tags || []).join(', ')}\n\n${raw.description || ''}`,
        posted_at: raw.date || raw.epoch || null,
        salary_min: raw.salary_min ? parseInt(raw.salary_min) : null,
        salary_max: raw.salary_max ? parseInt(raw.salary_max) : null,
        salary_currency: 'USD'
      };
    });
  } catch (err) {
    console.error('RemoteOK fetch failed:', err.message);
    return [];
  }
}

async function fetchHimalayas() {
  console.log('Fetching live jobs from Himalayas API...');
  try {
    const res = await fetch('https://himalayas.app/jobs/api?limit=20', {
      headers: { 'User-Agent': 'JobRadar-Bot/1.0' }
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const rawJobs = data.jobs || [];

    return rawJobs.map(raw => {
      const detailUrl = isValidJobUrl(raw.guid) ? raw.guid : '';
      let applyUrl = '';
      if (isValidJobUrl(raw.applicationLink)) {
        try {
          const u = new URL(raw.applicationLink);
          for (const k of [...u.searchParams.keys()]) {
            if (k.toLowerCase().startsWith('utm_')) u.searchParams.delete(k);
          }
          applyUrl = isValidJobUrl(u.toString()) ? u.toString() : '';
        } catch {
          applyUrl = raw.applicationLink;
        }
      }
      const slug = (detailUrl || raw.companySlug || raw.title || '').split('/').pop();
      const locs = Array.isArray(raw.locationRestrictions) ? raw.locationRestrictions : [];
      return {
        source: 'himalayas',
        source_name: 'Himalayas',
        source_id: `hm_${raw.companySlug || 'job'}_${slug}`.slice(0, 80),
        url: applyUrl || detailUrl,
        source_job_url: detailUrl,
        apply_url: applyUrl,
        title: raw.title || '',
        company: raw.companyName || '',
        location: locs.length ? locs.slice(0, 5).join(', ') : 'Worldwide',
        description: `${(raw.categories || []).join(', ')}\n\n${raw.excerpt || ''}\n\n${(raw.description || '').replace(/<[^>]+>/g, ' ')}`,
        posted_at: raw.pubDate || null,
        salary_min: raw.minSalary ? parseInt(raw.minSalary) : null,
        salary_max: raw.maxSalary ? parseInt(raw.maxSalary) : null,
        salary_currency: raw.currency || 'USD'
      };
    });
  } catch (err) {
    console.error('Himalayas fetch failed:', err.message);
    return [];
  }
}

async function fetchRemotive() {
  console.log('Fetching live jobs from Remotive API...');
  try {
    const res = await fetch('https://remotive.com/api/remote-jobs?category=design&limit=50', {
      headers: { 'User-Agent': 'JobRadar/1.0' }
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const rawJobs = data.jobs || [];

    return rawJobs.map(raw => ({
      source: 'remotive',
      source_id: String(raw.id),
      url: raw.url,
      title: raw.title || '',
      company: raw.company_name || '',
      location: raw.candidate_required_location || 'Remote',
      description: `${(raw.tags || []).join(', ')}\n\n${raw.description || ''}`,
      posted_at: raw.publication_date || null,
      salary_min: null,
      salary_max: null,
      salary_currency: 'USD'
    }));
  } catch (err) {
    console.error('Remotive fetch failed:', err.message);
    return [];
  }
}

async function fetchJobicy() {
  console.log('Fetching live jobs from Jobicy API...');
  try {
    const res = await fetch('https://jobicy.com/api/v2/remote-jobs?count=50&industry=design', {
      headers: { 'User-Agent': 'JobRadar/1.0' }
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const rawJobs = data.jobs || [];

    return rawJobs.map(raw => ({
      source: 'jobicy',
      source_id: String(raw.id || raw.jobSlug),
      url: raw.url,
      title: raw.jobTitle || '',
      company: raw.companyName || '',
      location: raw.jobGeo || 'Remote',
      description: raw.jobDescription || '',
      posted_at: raw.pubDate || null,
      salary_min: raw.annualSalaryMin ? parseInt(raw.annualSalaryMin) : null,
      salary_max: raw.annualSalaryMax ? parseInt(raw.annualSalaryMax) : null,
      salary_currency: raw.salaryCurrency || 'USD'
    }));
  } catch (err) {
    console.error('Jobicy fetch failed:', err.message);
    return [];
  }
}

async function main() {
  console.log('--- Starting Live Job Discovery ---');

  const [remoteokJobs, remotiveJobs, jobicyJobs, himalayasJobs] = await Promise.all([
    fetchRemoteOK(),
    fetchRemotive(),
    fetchJobicy(),
    fetchHimalayas()
  ]);

  const allRaw = [...remoteokJobs, ...remotiveJobs, ...jobicyJobs, ...himalayasJobs];
  console.log(`Fetched ${allRaw.length} total live job listings.`);

  // Load existing storage
  let db = { jobs: {}, source_runs: [] };
  if (fs.existsSync(DB_FILE)) {
    try { db = JSON.parse(fs.readFileSync(DB_FILE, 'utf8')); } catch (e) {}
  }
  db.jobs = db.jobs || {};
  db.recent_exclusions = Array.isArray(db.recent_exclusions) ? db.recent_exclusions : [];

  let matchedCount = 0;
  let newCount = 0;
  let ageExcludedCount = 0;

  for (const raw of allRaw) {
    if (!raw.title) continue;

    const match = scoreJob(raw);
    if (match.ageCheck && !match.ageCheck.passed) {
      ageExcludedCount++;
      db.recent_exclusions.unshift({
        source: raw.source,
        source_id: raw.source_id,
        title: raw.title,
        company: raw.company,
        source_timestamp_raw: match.ageCheck.rawTs,
        posted_at: match.ageCheck.postedAtIso,
        detected_at: new Date().toISOString(),
        exclusion_reason: match.ageCheck.reason,
      });
      continue;
    }
    if (match.score < 40) continue; // Min match threshold

    matchedCount++;
    const fingerprint = `${raw.source}::${raw.source_id}`;

    if (!db.jobs[fingerprint]) {
      newCount++;
      db.jobs[fingerprint] = {
        fingerprint,
        source: raw.source,
        source_name: raw.source_name || raw.source,
        source_id: raw.source_id,
        url: raw.url,
        source_job_url: raw.source_job_url || raw.url,
        apply_url: raw.apply_url || '',
        title: raw.title,
        company: raw.company,
        location: raw.location,
        description: (raw.description || '').slice(0, 3000),
        posted_at: match.ageCheck.postedAtIso,
        source_timestamp_raw: match.ageCheck.rawTs,
        timestamp_reliable: true,
        age_hours: match.ageCheck.ageHours,
        age_filter_passed: true,
        detected_at: new Date().toISOString(),
        remote_type: match.remoteType,
        sponsorship: match.sponsorship,
        relocation_offered: match.relocation,
        salary_min: raw.salary_min,
        salary_max: raw.salary_max,
        salary_currency: raw.salary_currency || 'USD',
        match_score: match.score,
        match_reasons: match.reasons,
        match_category: match.category,
        notified: false,
        application_status: 'new'
      };
    }
  }

  db.recent_exclusions = db.recent_exclusions.slice(0, 50);
  fs.writeFileSync(DB_FILE, JSON.stringify(db, null, 2), 'utf8');

  console.log(`\n======================================================`);
  console.log(`✓ Discovery complete!`);
  console.log(`  Raw fetched:     ${allRaw.length}`);
  console.log(`  Age-excluded:    ${ageExcludedCount} (strict ${MAX_POSTING_AGE_HOURS}h rule)`);
  console.log(`  Profile matched: ${matchedCount}`);
  console.log(`  Newly added:     ${newCount}`);
  console.log(`  Total in store:  ${Object.keys(db.jobs).length}`);
  console.log(`======================================================`);
  console.log(`Now run: node scripts/server.js`);
  console.log(`And click "Sync" in your Chrome extension!`);
}

main().catch(console.error);


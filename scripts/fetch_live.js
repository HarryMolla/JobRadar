/**
 * Live Job Fetcher (Node.js version).
 * Fetches real, live listings directly from public APIs (RemoteOK, Remotive, Jobicy),
 * runs the matching & scoring engine, and updates jobs_fallback.json.
 *
 * Run with: node scripts/fetch_live.js
 */

const fs = require('fs');
const path = require('path');

const DB_FILE = path.join(__dirname, '..', 'jobs_fallback.json');

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

function scoreJob(job) {
  const title = (job.title || '').toLowerCase();
  const desc = (job.description || '').toLowerCase();
  const combined = `${title} ${desc} ${(job.location || '').toLowerCase()}`;

  // Check exclusions
  for (const excl of EXCLUSION_KEYWORDS) {
    if (title.includes(excl)) {
      return { score: 0, reasons: [`Excluded: title contains "${excl}"`], category: 'irrelevant' };
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
    relocation
  };
}

// --- Live fetchers ---
async function fetchRemoteOK() {
  console.log('Fetching live jobs from RemoteOK API...');
  try {
    const res = await fetch('https://remoteok.com/api', {
      headers: { 'User-Agent': 'JobRadar/1.0 (Personal Job Search)' }
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const rawJobs = Array.isArray(data) ? data.filter(d => d && d.id) : [];

    return rawJobs.map(raw => ({
      source: 'remoteok',
      source_id: String(raw.id),
      url: raw.url || `https://remoteok.com/remote-jobs/${raw.id}`,
      title: raw.position || '',
      company: raw.company || '',
      location: raw.location || 'Remote Worldwide',
      description: `${(raw.tags || []).join(', ')}\n\n${raw.description || ''}`,
      posted_at: raw.date || new Date().toISOString(),
      salary_min: raw.salary_min ? parseInt(raw.salary_min) : null,
      salary_max: raw.salary_max ? parseInt(raw.salary_max) : null,
      salary_currency: 'USD'
    }));
  } catch (err) {
    console.error('RemoteOK fetch failed:', err.message);
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
      posted_at: raw.publication_date || new Date().toISOString(),
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
      posted_at: raw.pubDate || new Date().toISOString(),
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

  const [remoteokJobs, remotiveJobs, jobicyJobs] = await Promise.all([
    fetchRemoteOK(),
    fetchRemotive(),
    fetchJobicy()
  ]);

  const allRaw = [...remoteokJobs, ...remotiveJobs, ...jobicyJobs];
  console.log(`Fetched ${allRaw.length} total live job listings.`);

  // Load existing storage
  let db = { jobs: {}, source_runs: [] };
  if (fs.existsSync(DB_FILE)) {
    try { db = JSON.parse(fs.readFileSync(DB_FILE, 'utf8')); } catch (e) {}
  }
  db.jobs = db.jobs || {};

  let matchedCount = 0;
  let newCount = 0;

  for (const raw of allRaw) {
    if (!raw.title || !raw.url) continue;

    const match = scoreJob(raw);
    if (match.score < 40) continue; // Min match threshold

    matchedCount++;
    const fingerprint = `${raw.source}::${raw.source_id}`;

    if (!db.jobs[fingerprint]) {
      newCount++;
      db.jobs[fingerprint] = {
        fingerprint,
        source: raw.source,
        source_id: raw.source_id,
        url: raw.url,
        title: raw.title,
        company: raw.company,
        location: raw.location,
        description: (raw.description || '').slice(0, 3000),
        posted_at: raw.posted_at,
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

  fs.writeFileSync(DB_FILE, JSON.stringify(db, null, 2), 'utf8');

  console.log(`\n======================================================`);
  console.log(`✓ Discovery complete!`);
  console.log(`  Raw fetched:     ${allRaw.length}`);
  console.log(`  Profile matched: ${matchedCount}`);
  console.log(`  Newly added:     ${newCount}`);
  console.log(`  Total in store:  ${Object.keys(db.jobs).length}`);
  console.log(`======================================================`);
  console.log(`Now run: node scripts/server.js`);
  console.log(`And click "Sync" in your Chrome extension!`);
}

main().catch(console.error);

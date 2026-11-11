/**
 * Shared pure URL, UAE classification, benefit, and dropdown filter helpers
 * used by the JobRadar extension popup and verified in automated Node tests.
 */

const UAE_SOURCE_IDS = new Set(['sawatech', 'prism_digital', 'hays_uae']);

const UAE_LOCATION_ALIASES = [
  ['dubai', 'Dubai, UAE'],
  ['abu dhabi', 'Abu Dhabi, UAE'],
  ['sharjah', 'Sharjah, UAE'],
  ['ajman', 'Ajman, UAE'],
  ['ras al khaimah', 'Ras Al Khaimah, UAE'],
  ['fujairah', 'Fujairah, UAE'],
  ['umm al quwain', 'Umm Al Quwain, UAE'],
];

const GENERIC_EXACT_PATHS = new Set([
  '',
  'apply',
  'jobs',
  'job',
  'careers',
  'career',
  'vacancies',
  'openings',
  'positions',
  'open-positions',
  'work-with-us',
  'join-us',
  'job-search',
  'jobs/search',
  'jobs/api',
  'search',
  'search-and-apply',
  'remote-jobs',
  'remote-design-jobs',
  'en/uae/jobs',
  'uae/jobs',
  'srp/results',
  'j',
  'o',
  'job-detail',
  'companies',
  'employment',
]);

const JOB_ID_QUERY_PARAMS = [
  'id', 'jobid', 'job_id', 'gh_jid', 'jk', 'vjk',
  'postingid', 'requisitionid', 'offerid', 'vacancyid', 'reqid', 'rid',
];

const SEARCH_QUERY_PARAMS = [
  'q', 'query', 'keywords', 'keyword', 'search', 'searchtext', 'pos_ref', 'xz',
];

export function isWithinPostingAge(job, maxAgeHours = 24) {
  if (!job || job.timestamp_reliable === false || !job.posted_at) {
    return false;
  }
  const raw = String(job.posted_at).trim();
  if (!raw || /^\d{4}-\d{2}-\d{2}$/.test(raw)) {
    return false;
  }
  const normalized = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(raw)
    ? raw.replace(' ', 'T') + 'Z'
    : raw;
  const postedMs = Date.parse(normalized);
  if (Number.isNaN(postedMs)) {
    return false;
  }
  const ageHours = (Date.now() - postedMs) / 3600000;
  return ageHours >= 0 && ageHours <= maxAgeHours;
}

export function isValidJobUrl(rawUrl) {
  if (!rawUrl || typeof rawUrl !== 'string') return false;
  const trimmed = rawUrl.trim();
  if (!trimmed || trimmed.startsWith('#')) return false;
  try {
    const parsed = new URL(trimmed);
    if (!['http:', 'https:'].includes(parsed.protocol) || !parsed.hostname) return false;

    const normPath = parsed.pathname.replace(/^\/+|\/+$/g, '').toLowerCase();
    const hasJobIdParam = JOB_ID_QUERY_PARAMS.some((k) => {
      const val = parsed.searchParams.get(k);
      return Boolean(val && val.trim());
    });
    if (hasJobIdParam) return true;

    if (GENERIC_EXACT_PATHS.has(normPath)) return false;
    if (['/jobs', '/careers', '/job-search', '/search-and-apply', '/j', '/job', '/o'].some((s) => normPath.endsWith(s))) {
      return false;
    }

    const hasSearchParam = SEARCH_QUERY_PARAMS.some((k) => Boolean(parsed.searchParams.get(k)));
    if (hasSearchParam && !['/job/', '/jobs/', '/job-detail/', '/viewjob', '/companies/'].some((seg) => normPath.includes(seg))) {
      return false;
    }
    return true;
  } catch {
    return false;
  }
}

export function getJobApplyUrl(job) {
  if (!job) return '';
  for (const candidate of [job.apply_url, job.source_job_url, job.url]) {
    if (isValidJobUrl(candidate)) return candidate.trim();
  }
  return '';
}

export function getJobDetailUrl(job) {
  if (!job) return '';
  for (const candidate of [job.source_job_url, job.url]) {
    if (isValidJobUrl(candidate)) return candidate.trim();
  }
  return '';
}

export function getVisaStatus(job) {
  if (!job) return 'not_confirmed';
  if (job.visa_sponsorship) return job.visa_sponsorship;
  if (job.sponsorship === 'sponsored') return 'confirmed';
  if (job.sponsorship === 'not_sponsored') return 'unavailable';
  return 'not_confirmed';
}

export function getRelocationStatus(job) {
  if (!job) return 'not_confirmed';
  if (job.relocation_support) return job.relocation_support;
  return job.relocation_offered ? 'confirmed' : 'not_confirmed';
}

export function formatDescriptionPreview(description, maxLen = 140) {
  if (!description || typeof description !== 'string') return '';
  const stripped = description
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  if (!stripped) return '';
  if (stripped.length <= maxLen) return stripped;
  return `${stripped.slice(0, maxLen - 1).trimEnd()}…`;
}

export function isUaeJob(job) {
  if (!job || typeof job !== 'object') return false;
  if (UAE_SOURCE_IDS.has(String(job.source || '').toLowerCase())) {
    return true;
  }
  const locText = `${job.work_location || ''} ${job.location || ''}`.toLowerCase();
  if (UAE_LOCATION_ALIASES.some(([token]) => locText.includes(token))) {
    return true;
  }
  return locText.includes('united arab emirates') || /\buae\b/.test(locText);
}

export function normalizeUaeLocationKey(rawLoc) {
  const text = String(rawLoc || '').trim();
  if (!text) return null;
  const lower = text.toLowerCase();
  for (const [token, canonical] of UAE_LOCATION_ALIASES) {
    if (lower.includes(token)) {
      return { value: token, label: canonical };
    }
  }
  if (lower.includes('united arab emirates') || /\buae\b/.test(lower)) {
    return { value: 'uae', label: 'UAE (General)' };
  }
  return { value: lower, label: text };
}

export function buildUaeDropdownOptions(uaeJobs = []) {
  const jobs = Array.isArray(uaeJobs) ? uaeJobs.filter(Boolean) : [];

  // 1. Keyword / Role / Benefit options (every option has matching filter logic)
  const keywordOptions = [
    { value: '', label: 'All Roles & Benefits' },
    { value: 'category:design', label: 'Role: Design (UI/UX, Product, Brand, Graphic)' },
    { value: 'category:frontend', label: 'Role: Frontend (React, Next.js, Web Dev)' },
    { value: 'category:wordpress', label: 'Role: WordPress Developer' },
    { value: 'category:marketing', label: 'Role: Digital Marketing, SEO, Social & Content' },
    { value: 'benefit:visa', label: 'Benefit: Visa Sponsorship Confirmed' },
    { value: 'benefit:relocation', label: 'Benefit: Relocation Support Confirmed' },
    { value: 'benefit:flight', label: 'Benefit: Flight Covered' },
    { value: 'benefit:accommodation', label: 'Benefit: Accommodation Covered' },
    { value: 'remote:worldwide', label: 'Work Mode: Worldwide Remote' },
  ];

  // Dynamically add distinct specific role keywords & active UAE sources found in real job data
  const seenValues = new Set(keywordOptions.map((o) => o.value));
  const sourcesSeen = new Map();
  for (const job of jobs) {
    if (job.source) {
      sourcesSeen.set(job.source, job.source_name || job.source);
    }
  }
  for (const [srcId, srcLabel] of [...sourcesSeen.entries()].sort((a, b) => a[1].localeCompare(b[1]))) {
    const val = `source:${srcId}`;
    if (!seenValues.has(val)) {
      seenValues.add(val);
      keywordOptions.push({ value: val, label: `Source: ${srcLabel}` });
    }
  }

  const roleKeywords = [
    ['term:ui/ux', 'Keyword: UI / UX Designer'],
    ['term:product designer', 'Keyword: Product Designer'],
    ['term:graphic designer', 'Keyword: Graphic / Visual Designer'],
    ['term:react', 'Keyword: React / Next.js'],
    ['term:wordpress', 'Keyword: WordPress'],
    ['term:seo', 'Keyword: SEO / Digital Marketing'],
    ['term:social media', 'Keyword: Social Media / Content Creator'],
  ];
  for (const [val, label] of roleKeywords) {
    if (!seenValues.has(val)) {
      seenValues.add(val);
      keywordOptions.push({ value: val, label });
    }
  }

  // 2. UAE Location / Emirate options (baseline emirates + actual data locations)
  const locationMap = new Map([
    ['dubai', 'Dubai, UAE'],
    ['abu dhabi', 'Abu Dhabi, UAE'],
    ['sharjah', 'Sharjah, UAE'],
    ['ajman', 'Ajman, UAE'],
    ['ras al khaimah', 'Ras Al Khaimah, UAE'],
    ['fujairah', 'Fujairah, UAE'],
    ['umm al quwain', 'Umm Al Quwain, UAE'],
    ['uae', 'UAE (General)'],
    ['remote_uae', 'Remote / Hybrid (UAE)'],
  ]);

  for (const job of jobs) {
    const norm = normalizeUaeLocationKey(job.work_location || job.location);
    if (norm && !locationMap.has(norm.value)) {
      locationMap.set(norm.value, norm.label);
    }
  }

  const locationOptions = [{ value: '', label: 'All UAE Locations' }];
  for (const [value, label] of locationMap.entries()) {
    locationOptions.push({ value, label });
  }

  return { keywordOptions, locationOptions };
}

export function matchesUaeKeywordFilter(job, value) {
  if (!value) return true;
  if (!job || typeof job !== 'object') return false;

  if (value.startsWith('category:')) {
    return job.match_category === value.slice('category:'.length);
  }
  if (value === 'benefit:visa') {
    return getVisaStatus(job) === 'confirmed';
  }
  if (value === 'benefit:relocation') {
    return getRelocationStatus(job) === 'confirmed';
  }
  if (value === 'benefit:flight') {
    return job.flight_covered === 'confirmed';
  }
  if (value === 'benefit:accommodation') {
    return job.accommodation_covered === 'confirmed';
  }
  if (value === 'remote:worldwide') {
    return job.remote_type === 'remote_worldwide';
  }
  if (value.startsWith('source:')) {
    return job.source === value.slice('source:'.length);
  }
  if (value.startsWith('term:')) {
    const term = value.slice('term:'.length).toLowerCase();
    const haystack = [
      job.title || '',
      job.company || '',
      job.description || '',
      job.match_category || '',
      ...(Array.isArray(job.match_reasons) ? job.match_reasons : []),
    ]
      .join(' ')
      .toLowerCase();

    if (term === 'ui/ux') {
      return /\b(ui\/ux|ux\/ui|ui ux|ux designer|ui designer)\b/.test(haystack);
    }
    if (term === 'graphic designer') {
      return haystack.includes('graphic designer') || haystack.includes('visual designer') || haystack.includes('brand designer');
    }
    if (term === 'react') {
      return haystack.includes('react') || haystack.includes('next.js') || haystack.includes('nextjs');
    }
    if (term === 'seo') {
      return /\bseo\b/.test(haystack) || haystack.includes('digital marketing');
    }
    if (term === 'social media') {
      return haystack.includes('social media') || haystack.includes('content creator');
    }
    return haystack.includes(term);
  }

  // Fallback raw text match
  const rawHaystack = `${job.title || ''} ${job.description || ''}`.toLowerCase();
  return rawHaystack.includes(value.toLowerCase());
}

export function matchesUaeLocationFilter(job, value) {
  if (!value) return true;
  if (!job || typeof job !== 'object') return false;

  const locStr = String(job.work_location || job.location || '').toLowerCase();
  if (value === 'remote_uae') {
    return (
      ['remote_worldwide', 'remote_restricted', 'hybrid'].includes(job.remote_type) ||
      locStr.includes('remote') ||
      locStr.includes('hybrid')
    );
  }
  if (value === 'uae') {
    return isUaeJob(job);
  }
  const norm = normalizeUaeLocationKey(locStr);
  if (norm && norm.value === value) {
    return true;
  }
  return locStr.includes(value.toLowerCase());
}

export function applyCommonJobFilters(
  allJobs,
  {
    tab = 'all',
    source = '',
    category = '',
    visa = '',
    remote = '',
    searchQuery = '',
    maxAgeHours = 24,
  } = {}
) {
  let jobs = Array.isArray(allJobs) ? [...allJobs] : [];

  if (tab === 'uae_sources') {
    jobs = jobs.filter((j) => isUaeJob(j) && isWithinPostingAge(j, maxAgeHours));
  } else {
    if (tab !== 'all') {
      jobs = jobs.filter((j) => (j.application_status || 'new') === tab);
    }
    if (tab === 'all' || tab === 'new') {
      jobs = jobs.filter((j) => isWithinPostingAge(j, maxAgeHours));
    }
  }

  if (source) {
    jobs = jobs.filter((j) => j.source === source);
  }
  if (category) {
    jobs = jobs.filter((j) => j.match_category === category);
  }
  if (visa) {
    jobs = jobs.filter((j) => getVisaStatus(j) === visa);
  }
  if (remote === 'relocation') {
    jobs = jobs.filter((j) => getRelocationStatus(j) === 'confirmed');
  } else if (remote === 'flight') {
    jobs = jobs.filter((j) => j.flight_covered === 'confirmed');
  } else if (remote === 'accommodation') {
    jobs = jobs.filter((j) => j.accommodation_covered === 'confirmed');
  } else if (remote === 'remote_worldwide') {
    jobs = jobs.filter((j) => j.remote_type === 'remote_worldwide');
  } else if (remote === 'remote_restricted') {
    jobs = jobs.filter((j) => j.remote_type === 'remote_restricted');
  }

  if (searchQuery) {
    const q = searchQuery.toLowerCase();
    jobs = jobs.filter(
      (j) =>
        (j.title || '').toLowerCase().includes(q) ||
        (j.company || '').toLowerCase().includes(q) ||
        (j.work_location || j.location || '').toLowerCase().includes(q) ||
        (j.source_name || j.source || '').toLowerCase().includes(q) ||
        (j.description || '').toLowerCase().includes(q)
    );
  }

  jobs.sort((a, b) => {
    const scoreDiff = (b.match_score || 0) - (a.match_score || 0);
    if (scoreDiff !== 0) return scoreDiff;
    return new Date(b.posted_at || b.detected_at || 0) - new Date(a.posted_at || a.detected_at || 0);
  });

  return jobs;
}

export function filterUaeJobs(
  allJobs,
  { uaeKeyword = '', uaeLocation = '', ...commonFilters } = {}
) {
  let jobs = applyCommonJobFilters(allJobs, { ...commonFilters, tab: 'uae_sources' });
  if (uaeKeyword) {
    jobs = jobs.filter((j) => matchesUaeKeywordFilter(j, uaeKeyword));
  }
  if (uaeLocation) {
    jobs = jobs.filter((j) => matchesUaeLocationFilter(j, uaeLocation));
  }
  return jobs;
}


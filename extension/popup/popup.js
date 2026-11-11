/**
 * JobRadar Popup Script
 * Renders the job dashboard and handles user interactions.
 */

import { storage } from '../lib/storage.js';
import { api, isWithinPostingAge } from '../lib/api.js';
import {
  DEFAULT_UAE_SOURCES,
  UAE_LOCATIONS,
  UAE_SEARCH_KEYWORDS,
  buildUaeSearchUrl,
} from '../lib/uae_sources.js';

let allJobs = [];
let uaeSources = [...DEFAULT_UAE_SOURCES];
let currentFilter = 'all';
let currentSource = '';
let currentCategory = '';
let currentVisa = '';
let currentRemote = '';
let searchQuery = '';
let selectedUaeKeyword = 'UI UX Designer';
let selectedUaeLocation = 'Dubai';
let settings = {};

// DOM refs
const jobList = document.getElementById('jobList');
const emptyState = document.getElementById('emptyState');
const filterBar = document.getElementById('filterBar');
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const syncBtn = document.getElementById('syncBtn');
const optionsBtn = document.getElementById('optionsBtn');
const searchInput = document.getElementById('searchInput');
const sourceFilter = document.getElementById('sourceFilter');
const categoryFilter = document.getElementById('categoryFilter');
const visaFilter = document.getElementById('visaFilter');
const remoteFilter = document.getElementById('remoteFilter');
const footerText = document.getElementById('footerText');

// Stat pills
const countAll = document.getElementById('countAll');
const countNew = document.getElementById('countNew');
const countSaved = document.getElementById('countSaved');
const countApplied = document.getElementById('countApplied');
const countUae = document.getElementById('countUae');

// Initialize
(async () => {
  settings = await storage.getSettings();
  allJobs = await storage.pruneExpiredJobs(24);
  const storedUae = await storage.getUaeSources();
  if (Array.isArray(storedUae) && storedUae.length > 0) {
    uaeSources = storedUae;
  }
  populateSourceFilter();
  updateCounts();
  renderCurrentView();
  updateSyncStatus();
})();

// Sync button
syncBtn.addEventListener('click', async () => {
  syncBtn.classList.add('spinning');
  statusDot.className = 'status-dot syncing';
  statusText.textContent = 'Syncing...';

  try {
    const result = await chrome.runtime.sendMessage({ type: 'SYNC_NOW' });
    allJobs = await storage.getJobs();
    const storedUae = await storage.getUaeSources();
    if (Array.isArray(storedUae) && storedUae.length > 0) {
      uaeSources = storedUae;
    }
    populateSourceFilter();
    updateCounts();
    renderCurrentView();
    updateSyncStatus();
    footerText.textContent = result?.newJobs
      ? `✓ ${result.newJobs} new job${result.newJobs > 1 ? 's' : ''} found`
      : '✓ Up to date';
  } catch (err) {
    statusDot.className = 'status-dot error';
    statusText.textContent = 'Sync failed';
    footerText.textContent = `Error: ${err.message}`;
  } finally {
    syncBtn.classList.remove('spinning');
  }
});

// Options / Settings button
if (optionsBtn) {
  optionsBtn.addEventListener('click', (e) => {
    e.preventDefault();
    if (chrome.runtime.openOptionsPage) {
      chrome.runtime.openOptionsPage();
    } else {
      chrome.tabs.create({ url: chrome.runtime.getURL('options/options.html') });
    }
  });
}

// Tab filters
document.querySelectorAll('.stat-pill').forEach((pill) => {
  pill.addEventListener('click', () => {
    document.querySelectorAll('.stat-pill').forEach((p) => p.classList.remove('active'));
    pill.classList.add('active');
    currentFilter = pill.dataset.filter;
    renderCurrentView();
  });
});

// Search
let searchTimer;
searchInput.addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    searchQuery = searchInput.value.trim().toLowerCase();
    renderCurrentView();
  }, 200);
});

// Source filter
if (sourceFilter) {
  sourceFilter.addEventListener('change', () => {
    currentSource = sourceFilter.value;
    renderCurrentView();
  });
}

// Category filter
categoryFilter.addEventListener('change', () => {
  currentCategory = categoryFilter.value;
  renderCurrentView();
});

// Visa filter
if (visaFilter) {
  visaFilter.addEventListener('change', () => {
    currentVisa = visaFilter.value;
    renderCurrentView();
  });
}

// Remote / Benefits filter
remoteFilter.addEventListener('change', () => {
  currentRemote = remoteFilter.value;
  renderCurrentView();
});

function populateSourceFilter() {
  if (!sourceFilter) return;
  const currentVal = sourceFilter.value;
  const sourcesMap = new Map();
  for (const job of allJobs) {
    if (job.source) {
      sourcesMap.set(job.source, job.source_name || job.source);
    }
  }
  for (const src of uaeSources) {
    if (src.mode === 'automated' && !sourcesMap.has(src.id)) {
      sourcesMap.set(src.id, src.name);
    }
  }
  sourceFilter.innerHTML = '<option value="">All Sources</option>';
  for (const [id, label] of [...sourcesMap.entries()].sort((a, b) => a[1].localeCompare(b[1]))) {
    const opt = document.createElement('option');
    opt.value = id;
    opt.textContent = label;
    sourceFilter.appendChild(opt);
  }
  sourceFilter.value = currentVal;
}

function updateCounts() {
  const all = allJobs.filter((j) => isWithinPostingAge(j, 24)).length;
  const newC = allJobs.filter(
    (j) => (j.application_status || 'new') === 'new' && isWithinPostingAge(j, 24)
  ).length;
  const saved = allJobs.filter((j) => j.application_status === 'saved').length;
  const applied = allJobs.filter((j) => j.application_status === 'applied').length;

  countAll.textContent = all;
  countNew.textContent = newC;
  countSaved.textContent = saved;
  countApplied.textContent = applied;
  if (countUae) countUae.textContent = uaeSources.length;
}

function getVisaStatus(job) {
  if (job.visa_sponsorship) return job.visa_sponsorship;
  if (job.sponsorship === 'sponsored') return 'confirmed';
  if (job.sponsorship === 'not_sponsored') return 'unavailable';
  return 'not_confirmed';
}

function getRelocationStatus(job) {
  if (job.relocation_support) return job.relocation_support;
  return job.relocation_offered ? 'confirmed' : 'not_confirmed';
}

function getFilteredJobs() {
  let jobs = [...allJobs];

  // Status filter
  if (currentFilter !== 'all') {
    jobs = jobs.filter((j) => (j.application_status || 'new') === currentFilter);
  }

  // Enforce 24-hour posting age filter in All and New tabs
  if (currentFilter === 'all' || currentFilter === 'new') {
    jobs = jobs.filter((j) => isWithinPostingAge(j, 24));
  }

  // Source filter
  if (currentSource) {
    jobs = jobs.filter((j) => j.source === currentSource);
  }

  // Category filter
  if (currentCategory) {
    jobs = jobs.filter((j) => j.match_category === currentCategory);
  }

  // Visa sponsorship filter
  if (currentVisa) {
    jobs = jobs.filter((j) => getVisaStatus(j) === currentVisa);
  }

  // Benefits & Remote filter
  if (currentRemote === 'relocation') {
    jobs = jobs.filter((j) => getRelocationStatus(j) === 'confirmed');
  } else if (currentRemote === 'flight') {
    jobs = jobs.filter((j) => j.flight_covered === 'confirmed');
  } else if (currentRemote === 'accommodation') {
    jobs = jobs.filter((j) => j.accommodation_covered === 'confirmed');
  } else if (currentRemote === 'remote_worldwide') {
    jobs = jobs.filter((j) => j.remote_type === 'remote_worldwide');
  } else if (currentRemote === 'remote_restricted') {
    jobs = jobs.filter((j) => j.remote_type === 'remote_restricted');
  }

  // Search
  if (searchQuery) {
    jobs = jobs.filter(
      (j) =>
        j.title?.toLowerCase().includes(searchQuery) ||
        j.company?.toLowerCase().includes(searchQuery) ||
        (j.work_location || j.location || '').toLowerCase().includes(searchQuery) ||
        (j.source_name || j.source || '').toLowerCase().includes(searchQuery) ||
        j.description?.toLowerCase().includes(searchQuery)
    );
  }

  // Sort by score desc, then posted_at desc
  jobs.sort((a, b) => {
    const scoreDiff = (b.match_score || 0) - (a.match_score || 0);
    if (scoreDiff !== 0) return scoreDiff;
    return new Date(b.posted_at || b.detected_at || 0) - new Date(a.posted_at || a.detected_at || 0);
  });

  return jobs;
}

function renderCurrentView() {
  if (currentFilter === 'uae_sources') {
    if (filterBar) filterBar.style.display = 'none';
    renderUaeSources();
  } else {
    if (filterBar) filterBar.style.display = 'flex';
    renderJobs();
  }
}

function renderUaeSources() {
  jobList.innerHTML = '';

  const toolbar = document.createElement('div');
  toolbar.className = 'uae-toolbar';
  const kwSelect = document.createElement('select');
  kwSelect.className = 'filter-select';
  for (const kw of UAE_SEARCH_KEYWORDS) {
    const opt = document.createElement('option');
    opt.value = kw;
    opt.textContent = kw;
    if (kw === selectedUaeKeyword) opt.selected = true;
    kwSelect.appendChild(opt);
  }
  kwSelect.addEventListener('change', () => {
    selectedUaeKeyword = kwSelect.value;
    renderUaeSources();
  });

  const locSelect = document.createElement('select');
  locSelect.className = 'filter-select';
  for (const loc of UAE_LOCATIONS) {
    const opt = document.createElement('option');
    opt.value = loc;
    opt.textContent = loc;
    if (loc === selectedUaeLocation) opt.selected = true;
    locSelect.appendChild(opt);
  }
  locSelect.addEventListener('change', () => {
    selectedUaeLocation = locSelect.value;
    renderUaeSources();
  });

  toolbar.appendChild(kwSelect);
  toolbar.appendChild(locSelect);
  jobList.appendChild(toolbar);

  const groups = [
    ['general', 'General UAE Job Boards'],
    ['government', 'Government Recruitment Portals'],
    ['agency', 'Specialist Recruitment Agencies'],
    ['employer', 'Direct Employer Career Pages'],
  ];

  let autoCount = 0;
  for (const [catKey, groupLabel] of groups) {
    const items = uaeSources.filter((s) => s.category === catKey);
    if (items.length === 0) continue;

    const heading = document.createElement('div');
    heading.className = 'uae-group-title';
    heading.textContent = `${groupLabel} (${items.length})`;
    jobList.appendChild(heading);

    for (const src of items) {
      if (src.mode === 'automated') autoCount++;
      const badgeClass =
        src.mode === 'automated'
          ? 'uae-badge-auto'
          : src.mode === 'email_or_manual'
            ? 'uae-badge-email'
            : 'uae-badge-manual';
      const badgeLabel =
        src.mode === 'automated'
          ? 'Auto (24h Verified)'
          : src.mode === 'email_or_manual'
            ? 'Email Alert / Manual'
            : 'Manual Search';

      const searchHref = buildUaeSearchUrl(src, selectedUaeKeyword, selectedUaeLocation);
      const checkedNote = src.last_checked_at
        ? `Checked ${timeAgo(src.last_checked_at)} (${src.last_success ? `${src.last_jobs_found || 0} found` : 'failed'})`
        : src.mode === 'automated'
          ? 'Pending next 6h run'
          : 'Respects robots/anti-bot rules';

      const card = document.createElement('div');
      card.className = 'uae-source-card';
      card.innerHTML = `
        <div class="uae-source-top">
          <span class="uae-source-name">${escHtml(src.name)}</span>
          <span class="${badgeClass}">${badgeLabel}</span>
        </div>
        <div class="uae-source-reason">${escHtml(src.reason || '')}</div>
        <div class="uae-source-actions">
          <span>${escHtml(checkedNote)}</span>
          <a href="${escHtml(searchHref)}" target="_blank" rel="noopener noreferrer" class="btn-apply">Open / Search →</a>
        </div>
      `;
      jobList.appendChild(card);
    }
  }

  footerText.textContent = `UAE Sources: ${autoCount} automated · ${uaeSources.length - autoCount} manual/email-alert`;
}

function renderJobs() {
  const filtered = getFilteredJobs();
  jobList.innerHTML = '';

  if (filtered.length === 0) {
    emptyState.style.display = 'flex';
    footerText.textContent = allJobs.length ? 'No jobs match current filters' : 'No jobs yet — click sync';
    return;
  }

  emptyState.style.display = 'none';

  for (const job of filtered) {
    jobList.appendChild(createJobCard(job));
  }

  footerText.textContent = `Showing ${filtered.length} of ${allJobs.length} jobs`;
}

function createJobCard(job) {
  const card = document.createElement('div');
  const status = job.application_status || 'new';
  card.className = `job-card${status === 'dismissed' ? ' dismissed' : ''}`;
  card.dataset.fingerprint = job.fingerprint;

  // Score badge
  const score = job.match_score || 0;
  const scoreClass = score >= 70 ? 'score-high' : score >= 50 ? 'score-mid' : 'score-low';

  // Tags & verified benefit indicators
  const tags = [];
  const visaStatus = getVisaStatus(job);
  if (visaStatus === 'confirmed') {
    tags.push(`<span class="tag tag-sponsored">✓ Visa Confirmed</span>`);
  } else if (visaStatus === 'unavailable') {
    tags.push(`<span class="tag tag-unavailable">✕ No Visa</span>`);
  } else {
    tags.push(`<span class="tag tag-unverified">? Visa Unverified</span>`);
  }

  const relocStatus = getRelocationStatus(job);
  if (relocStatus === 'confirmed') {
    tags.push(`<span class="tag tag-relocation">📦 Relocation Confirmed</span>`);
  } else if (relocStatus === 'unavailable') {
    tags.push(`<span class="tag tag-unavailable">✕ No Relocation</span>`);
  }

  if (job.flight_covered === 'confirmed') {
    tags.push(`<span class="tag tag-relocation">✈️ Flight Covered</span>`);
  } else if (job.flight_covered === 'unavailable') {
    tags.push(`<span class="tag tag-unavailable">✕ No Flight</span>`);
  }

  if (job.accommodation_covered === 'confirmed') {
    tags.push(`<span class="tag tag-relocation">🏠 Accommodation Covered</span>`);
  } else if (job.accommodation_covered === 'unavailable') {
    tags.push(`<span class="tag tag-unavailable">✕ No Accommodation</span>`);
  }

  if (job.remote_type === 'remote_worldwide') {
    tags.push(`<span class="tag tag-remote-worldwide">🌍 Worldwide Remote</span>`);
  } else if (job.remote_type === 'remote_restricted') {
    tags.push(`<span class="tag tag-remote-restricted">Remote</span>`);
  }
  if (job.match_category && job.match_category !== 'irrelevant') {
    tags.push(`<span class="tag tag-category">${capitalize(job.match_category)}</span>`);
  }
  if (job.salary_min) {
    const sal = `${job.salary_currency || '$'}${formatSalary(job.salary_min)}${job.salary_max ? `–${formatSalary(job.salary_max)}` : '+'}`;
    tags.push(`<span class="tag tag-salary">💰 ${sal}</span>`);
  }
  tags.push(`<span class="tag tag-source">${escHtml(job.source_name || job.source || '?')}</span>`);

  // Original posting time and age
  const postedIso = job.posted_at || job.detected_at;
  const ageStr = formatDate(postedIso);
  const utcLabel = postedIso ? new Date(postedIso).toISOString().slice(5, 16).replace('T', ' ') + ' UTC' : '';
  const dateStr = utcLabel ? `${ageStr} (${utcLabel})` : ageStr;
  const vacancyUrl = job.source_job_url || job.url || '#';
  const displayLoc = job.work_location || job.location || 'Remote / UAE';

  // Reason
  const reason = job.match_reasons?.slice(0, 3).join('; ') || '';

  // Action button states
  const isSaved = status === 'saved';
  const isApplied = status === 'applied';
  const isDismissed = status === 'dismissed';

  card.innerHTML = `
    <div class="card-top">
      <div class="card-title">${escHtml(job.title || 'Untitled')}</div>
      <span class="score-badge ${scoreClass}">${score}/100</span>
    </div>
    <div class="card-company">${escHtml(job.company || '?')} · ${escHtml(displayLoc)}</div>
    ${tags.length ? `<div class="card-tags">${tags.join('')}</div>` : ''}
    ${reason ? `<div class="card-reason">${escHtml(reason)}</div>` : ''}
    <div class="card-actions">
      <a href="${escHtml(vacancyUrl)}" target="_blank" rel="noopener noreferrer" class="btn-apply">Apply →</a>
      <button class="btn-action ${isSaved ? 'active' : ''}" data-action="saved">
        ${isSaved ? '★ Saved' : '☆ Save'}
      </button>
      <button class="btn-action ${isApplied ? 'active' : ''}" data-action="applied">
        ${isApplied ? '✓ Applied' : 'Applied?'}
      </button>
      <button class="btn-action ${isDismissed ? 'active' : ''}" data-action="dismissed">
        ${isDismissed ? 'Hidden' : '✕'}
      </button>
      <span class="card-date">${dateStr}</span>
    </div>
  `;

  // Action buttons
  card.querySelectorAll('[data-action]').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      const action = btn.dataset.action;
      const fp = card.dataset.fingerprint;
      const currentStatus = job.application_status || 'new';

      // Toggle: clicking active status → revert to 'new'
      const newStatus = currentStatus === action ? 'new' : action;
      job.application_status = newStatus;

      await storage.updateJobStatus(fp, newStatus);

      // Also update backend
      const apiUrl = settings.apiUrl || 'http://127.0.0.1:8765';
      try {
        await api.updateJobStatus(apiUrl, fp, newStatus, { apiKey: settings.apiKey });
      } catch {
        // Backend may not be running — local extension storage update succeeded
      }

      updateCounts();
      renderJobs();
    });
  });

  return card;
}

async function updateSyncStatus() {
  const sync = await storage.getLastSync();
  if (!sync) {
    statusDot.className = 'status-dot';
    statusText.textContent = 'Never synced';
    return;
  }
  if (sync.status === 'ok') {
    statusDot.className = 'status-dot ok';
    const ago = timeAgo(sync.at);
    statusText.textContent = `Synced ${ago}`;
  } else {
    statusDot.className = 'status-dot error';
    statusText.textContent = 'Sync error';
  }
}

// Utilities
function escHtml(str) {
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function capitalize(str) {
  return str ? str[0].toUpperCase() + str.slice(1) : '';
}

function formatSalary(n) {
  if (n >= 1000) return `${Math.round(n / 1000)}k`;
  return String(n);
}

function formatDate(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  if (Number.isNaN(d.getTime())) return '';
  const diffMs = Date.now() - d.getTime();
  const diffHours = Math.floor(diffMs / 3600000);
  if (diffHours < 1) return 'Just now';
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays === 1) return '1d ago';
  if (diffDays < 7) return `${diffDays}d ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function timeAgo(isoStr) {
  if (!isoStr) return 'unknown';
  const mins = Math.floor((Date.now() - new Date(isoStr)) / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

